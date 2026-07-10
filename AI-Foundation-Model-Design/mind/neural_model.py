"""
neural_model  —  Vio's OWN model, built and trained from zero. [Phase 2]

This is not a wrapper around anyone's pretrained weights. It is a real GPT-style
transformer implemented from scratch in PyTorch, with a byte-level BPE tokenizer that
learns its vocabulary from YOUR corpus. Nothing here has seen the internet — it knows
only what you train it on. That is the point: its capability is entirely its own.

Honest scope: capability = data × compute. Trained on a focused domain (e.g. all your
networking/security text) on a GPU, it learns that domain's vocabulary, style, and
patterns and can generate/continue text in it. It will NOT match an internet-scale
pretrained model on general knowledge — that takes trillions of tokens and millions of
dollars of compute. What it gives you instead is a model that is genuinely, verifiably
yours, and that gets sharper the more domain data you feed it.

Contents: a from-scratch BPE tokenizer, the transformer (GPT), a training loop, and
sampling. Save/load round-trips the whole thing (weights + tokenizer + config).
"""

from __future__ import annotations

import json
import math
import os
import pickle
from dataclasses import dataclass, asdict

import torch
import torch.nn as nn
from torch.nn import functional as F


# --------------------------------------------------------------------------- #
# Byte-level BPE tokenizer — learns its merges from your text (truly from zero)
# --------------------------------------------------------------------------- #
class BPETokenizer:
    def __init__(self):
        self.merges = {}          # (int, int) -> new_id
        self.vocab = {i: bytes([i]) for i in range(256)}

    @staticmethod
    def _stats(ids):
        counts = {}
        for a, b in zip(ids, ids[1:]):
            counts[(a, b)] = counts.get((a, b), 0) + 1
        return counts

    @staticmethod
    def _merge(ids, pair, idx):
        out, i = [], 0
        while i < len(ids):
            if i < len(ids) - 1 and ids[i] == pair[0] and ids[i + 1] == pair[1]:
                out.append(idx); i += 2
            else:
                out.append(ids[i]); i += 1
        return out

    def train(self, text, vocab_size=4096, verbose=False):
        """Learn `vocab_size` tokens by repeatedly merging the most frequent byte pair."""
        assert vocab_size >= 256
        ids = list(text.encode("utf-8"))
        num_merges = vocab_size - 256
        self.merges = {}
        self.vocab = {i: bytes([i]) for i in range(256)}
        for k in range(num_merges):
            stats = self._stats(ids)
            if not stats:
                break
            pair = max(stats, key=stats.get)
            idx = 256 + k
            ids = self._merge(ids, pair, idx)
            self.merges[pair] = idx
            self.vocab[idx] = self.vocab[pair[0]] + self.vocab[pair[1]]
            if verbose and k % 500 == 0:
                print(f"    merge {k}/{num_merges}")
        return self

    def encode(self, text):
        ids = list(text.encode("utf-8"))
        while len(ids) >= 2:
            stats = self._stats(ids)
            pair = min(stats, key=lambda p: self.merges.get(p, float("inf")))
            if pair not in self.merges:
                break
            ids = self._merge(ids, pair, self.merges[pair])
        return ids

    def decode(self, ids):
        b = b"".join(self.vocab[i] for i in ids)
        return b.decode("utf-8", errors="replace")

    @property
    def size(self):
        return len(self.vocab)

    def state(self):
        # pickle-friendly: tuples-as-lists for the merge keys
        return {"merges": [[list(k), v] for k, v in self.merges.items()]}

    def load_state(self, st):
        self.merges = {tuple(k): v for k, v in st["merges"]}
        self.vocab = {i: bytes([i]) for i in range(256)}
        for (a, b), idx in sorted(self.merges.items(), key=lambda kv: kv[1]):
            self.vocab[idx] = self.vocab[a] + self.vocab[b]
        return self


# --------------------------------------------------------------------------- #
# The transformer — a from-scratch GPT
# --------------------------------------------------------------------------- #
@dataclass
class GPTConfig:
    vocab_size: int = 4096
    block_size: int = 256          # context length
    n_layer: int = 6
    n_head: int = 6
    n_embd: int = 384
    dropout: float = 0.1


class Block(nn.Module):
    """One transformer block: causal self-attention + MLP, both with residuals."""
    def __init__(self, cfg):
        super().__init__()
        self.ln1 = nn.LayerNorm(cfg.n_embd)
        self.attn = nn.MultiheadAttention(cfg.n_embd, cfg.n_head, dropout=cfg.dropout,
                                          batch_first=True)
        self.ln2 = nn.LayerNorm(cfg.n_embd)
        self.mlp = nn.Sequential(
            nn.Linear(cfg.n_embd, 4 * cfg.n_embd), nn.GELU(),
            nn.Linear(4 * cfg.n_embd, cfg.n_embd), nn.Dropout(cfg.dropout),
        )

    def forward(self, x, mask):
        h = self.ln1(x)
        a, _ = self.attn(h, h, h, attn_mask=mask, need_weights=False)
        x = x + a
        x = x + self.mlp(self.ln2(x))
        return x


class GPT(nn.Module):
    def __init__(self, cfg: GPTConfig):
        super().__init__()
        self.cfg = cfg
        self.tok = nn.Embedding(cfg.vocab_size, cfg.n_embd)
        self.pos = nn.Embedding(cfg.block_size, cfg.n_embd)
        self.drop = nn.Dropout(cfg.dropout)
        self.blocks = nn.ModuleList([Block(cfg) for _ in range(cfg.n_layer)])
        self.lnf = nn.LayerNorm(cfg.n_embd)
        self.head = nn.Linear(cfg.n_embd, cfg.vocab_size, bias=False)
        self.tok.weight = self.head.weight            # weight tying
        self.apply(self._init)

    def _init(self, m):
        if isinstance(m, nn.Linear):
            nn.init.normal_(m.weight, mean=0.0, std=0.02)
            if m.bias is not None:
                nn.init.zeros_(m.bias)
        elif isinstance(m, nn.Embedding):
            nn.init.normal_(m.weight, mean=0.0, std=0.02)

    def num_params(self):
        return sum(p.numel() for p in self.parameters())

    def forward(self, idx, targets=None):
        B, T = idx.shape
        pos = torch.arange(T, device=idx.device)
        x = self.drop(self.tok(idx) + self.pos(pos))
        mask = torch.triu(torch.ones(T, T, device=idx.device, dtype=torch.bool), 1)
        for blk in self.blocks:
            x = blk(x, mask)
        logits = self.head(self.lnf(x))
        loss = None
        if targets is not None:
            loss = F.cross_entropy(logits.view(-1, logits.size(-1)), targets.view(-1))
        return logits, loss

    @torch.no_grad()
    def generate(self, idx, max_new_tokens, temperature=0.9, top_k=40):
        for _ in range(max_new_tokens):
            idx_cond = idx[:, -self.cfg.block_size:]
            logits, _ = self(idx_cond)
            logits = logits[:, -1, :] / max(temperature, 1e-6)
            if top_k:
                v, _ = torch.topk(logits, min(top_k, logits.size(-1)))
                logits[logits < v[:, [-1]]] = -float("inf")
            probs = F.softmax(logits, dim=-1)
            nxt = torch.multinomial(probs, 1)
            idx = torch.cat([idx, nxt], dim=1)
        return idx


# --------------------------------------------------------------------------- #
# train / save / load / sample
# --------------------------------------------------------------------------- #
def _device():
    return "cuda" if torch.cuda.is_available() else "cpu"


def train(text, out_dir, cfg=None, steps=2000, batch_size=32, lr=3e-4,
          vocab_size=4096, log=print):
    """Train a fresh model from zero on `text`. Saves tokenizer + weights + config."""
    cfg = cfg or GPTConfig(vocab_size=vocab_size)
    dev = _device()
    log(f"device: {dev}")

    tok = BPETokenizer().train(text, vocab_size=cfg.vocab_size)
    data = torch.tensor(tok.encode(text), dtype=torch.long)
    if len(data) < cfg.block_size + 2:
        raise RuntimeError("Not enough text to train — feed the model more data first.")
    n = int(0.9 * len(data))
    train_d, val_d = data[:n], data[n:]
    log(f"tokens: {len(data)} (train {len(train_d)}, val {len(val_d)}) · vocab {tok.size}")

    model = GPT(cfg).to(dev)
    log(f"model parameters: {model.num_params()/1e6:.1f}M")
    opt = torch.optim.AdamW(model.parameters(), lr=lr, betas=(0.9, 0.95))

    def batch(split):
        d = train_d if split == "train" else val_d
        hi = max(1, len(d) - cfg.block_size - 1)
        ix = torch.randint(hi, (batch_size,))
        x = torch.stack([d[i:i + cfg.block_size] for i in ix])
        y = torch.stack([d[i + 1:i + 1 + cfg.block_size] for i in ix])
        return x.to(dev), y.to(dev)

    model.train()
    for step in range(1, steps + 1):
        x, y = batch("train")
        _, loss = model(x, y)
        opt.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        if step % max(1, steps // 20) == 0 or step == 1:
            model.eval()
            with torch.no_grad():
                vx, vy = batch("val")
                vl = model(vx, vy)[1].item()
            model.train()
            log(f"  step {step}/{steps}  train {loss.item():.3f}  val {vl:.3f}")

    save(model, tok, out_dir)
    log(f"✓ saved model to {out_dir}")
    return model, tok


def save(model, tok, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    torch.save(model.state_dict(), os.path.join(out_dir, "weights.pt"))
    json.dump(asdict(model.cfg), open(os.path.join(out_dir, "config.json"), "w"))
    pickle.dump(tok.state(), open(os.path.join(out_dir, "tokenizer.pkl"), "wb"))


def load(out_dir, device=None):
    cfg = GPTConfig(**json.load(open(os.path.join(out_dir, "config.json"))))
    tok = BPETokenizer().load_state(pickle.load(open(os.path.join(out_dir, "tokenizer.pkl"), "rb")))
    dev = device or _device()
    model = GPT(cfg).to(dev)
    model.load_state_dict(torch.load(os.path.join(out_dir, "weights.pt"), map_location=dev))
    model.eval()
    return model, tok


def sample(model, tok, prompt="", max_new_tokens=120, temperature=0.9, top_k=40):
    dev = next(model.parameters()).device
    ids = tok.encode(prompt) if prompt else [tok.encode("\n")[0]]
    idx = torch.tensor([ids], dtype=torch.long, device=dev)
    out = model.generate(idx, max_new_tokens, temperature, top_k)[0].tolist()
    return tok.decode(out)


if __name__ == "__main__":
    # tiny smoke test — train a few steps on this file's own text and generate
    txt = open(__file__, encoding="utf-8").read() * 3
    cfg = GPTConfig(vocab_size=512, block_size=64, n_layer=3, n_head=4, n_embd=128)
    m, t = train(txt, "/tmp/vio_smoke_model", cfg=cfg, steps=60, batch_size=16, vocab_size=512)
    print("\nSAMPLE:\n", sample(m, t, "the model", 80))
