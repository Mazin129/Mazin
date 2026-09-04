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

import hashlib
import json
import os
import pickle
import re
import time
from dataclasses import dataclass, asdict

import torch
import torch.nn as nn
from torch.nn import functional as F


# --------------------------------------------------------------------------- #
# Byte-level BPE tokenizer — learns its merges from your text (truly from zero)
# --------------------------------------------------------------------------- #
class BPETokenizer:
    # Split text into small pieces (a word, keeping any leading space, or a run of
    # punctuation/whitespace). Merges are learned WITHIN pieces, which is what makes
    # training scale: the corpus collapses to its unique pieces, and identical words
    # are counted once instead of re-scanned millions of times.
    _SPLIT = re.compile(r" ?\w+| ?[^\w\s]+|\s+")

    def __init__(self):
        self.merges = {}          # (int, int) -> new_id
        self.vocab = {i: bytes([i]) for i in range(256)}
        self._cache = {}          # piece -> ids, so repeated words encode once

    @staticmethod
    def _merge(ids, pair, idx):
        out, i = [], 0
        while i < len(ids):
            if i < len(ids) - 1 and ids[i] == pair[0] and ids[i + 1] == pair[1]:
                out.append(idx); i += 2
            else:
                out.append(ids[i]); i += 1
        return out

    def train(self, text, vocab_size=4096, sample_bytes=12_000_000, verbose=False):
        """Learn `vocab_size` tokens from your text.

        Counts unique pieces once and updates only the pieces a merge actually touches,
        so cost scales with the vocabulary of the corpus rather than its total length —
        the difference between seconds and hours on a multi-megabyte corpus.
        """
        assert vocab_size >= 256
        from collections import Counter
        if len(text) > sample_bytes:      # merges generalise; no need to read it all
            text = text[:sample_bytes]
        self.merges = {}
        self.vocab = {i: bytes([i]) for i in range(256)}
        self._cache = {}

        freqs = Counter(self._SPLIT.findall(text))
        words = [list(w.encode("utf-8")) for w in freqs]
        counts = list(freqs.values())

        pair_counts, pair_words = {}, {}

        def index(i, sign):
            w, c = words[i], counts[i]
            for p in zip(w, w[1:]):
                pair_counts[p] = pair_counts.get(p, 0) + sign * c
                if sign > 0:
                    pair_words.setdefault(p, set()).add(i)

        for i in range(len(words)):
            index(i, +1)

        for k in range(vocab_size - 256):
            if not pair_counts:
                break
            pair = max(pair_counts, key=pair_counts.get)
            if pair_counts[pair] <= 0:                 # only stale entries left
                pair_counts.pop(pair, None); pair_words.pop(pair, None)
                continue
            idx = 256 + k
            for i in list(pair_words.get(pair, ())):
                index(i, -1)                            # withdraw this word's old pairs
                words[i] = self._merge(words[i], pair, idx)
                index(i, +1)                            # re-add its new pairs
            self.merges[pair] = idx
            self.vocab[idx] = self.vocab[pair[0]] + self.vocab[pair[1]]
            pair_counts.pop(pair, None); pair_words.pop(pair, None)
            if verbose and k % 500 == 0:
                print(f"    merge {k}/{vocab_size - 256}")
        return self

    def _encode_piece(self, piece):
        ids = list(piece.encode("utf-8"))
        while len(ids) >= 2:
            # apply the earliest-learned merge present, so encoding mirrors training
            best, rank = None, None
            for p in zip(ids, ids[1:]):
                r = self.merges.get(p)
                if r is not None and (rank is None or r < rank):
                    best, rank = p, r
            if best is None:
                break
            ids = self._merge(ids, best, rank)
        return ids

    def encode(self, text):
        out = []
        for piece in self._SPLIT.findall(text):
            ids = self._cache.get(piece)
            if ids is None:
                ids = self._encode_piece(piece)
                if len(self._cache) < 500_000:
                    self._cache[piece] = ids
            out.extend(ids)
        return out

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
        self._cache = {}
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


class CausalSelfAttention(nn.Module):
    """Multi-head causal self-attention using PyTorch's fused scaled_dot_product_attention
    — the flash / memory-efficient kernel. Much faster than a hand-rolled softmax-matmul
    and far lighter on memory (no T×T score matrix materialised), which is what lets a
    small laptop GPU take a bigger batch and stay busy."""
    def __init__(self, cfg):
        super().__init__()
        assert cfg.n_embd % cfg.n_head == 0
        self.n_head = cfg.n_head
        self.qkv = nn.Linear(cfg.n_embd, 3 * cfg.n_embd)
        self.proj = nn.Linear(cfg.n_embd, cfg.n_embd)
        self.dropout = cfg.dropout

    def forward(self, x):
        B, T, C = x.shape
        q, k, v = self.qkv(x).split(C, dim=2)
        h = self.n_head
        q = q.view(B, T, h, C // h).transpose(1, 2)
        k = k.view(B, T, h, C // h).transpose(1, 2)
        v = v.view(B, T, h, C // h).transpose(1, 2)
        y = F.scaled_dot_product_attention(q, k, v, is_causal=True,
                                           dropout_p=self.dropout if self.training else 0.0)
        y = y.transpose(1, 2).contiguous().view(B, T, C)
        return self.proj(y)


class Block(nn.Module):
    """One transformer block: causal self-attention + MLP, both with residuals."""
    def __init__(self, cfg):
        super().__init__()
        self.ln1 = nn.LayerNorm(cfg.n_embd)
        self.attn = CausalSelfAttention(cfg)
        self.ln2 = nn.LayerNorm(cfg.n_embd)
        self.mlp = nn.Sequential(
            nn.Linear(cfg.n_embd, 4 * cfg.n_embd), nn.GELU(),
            nn.Linear(4 * cfg.n_embd, cfg.n_embd), nn.Dropout(cfg.dropout),
        )

    def forward(self, x):
        x = x + self.attn(self.ln1(x))
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
        for blk in self.blocks:               # causality is handled inside attention now
            x = blk(x)
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
          vocab_size=4096, save_every=500, resume=False, patience=0, compile_model=False, log=print):
    """Train a model from zero on `text`.

    Checkpoints every `save_every` steps AND on Ctrl+C, so a long run is never lost and
    can be continued with resume=True. The best-scoring weights (lowest validation loss)
    are what get kept as the model, so a late overfitting drift can't spoil the result.
    """
    dev = _device()
    if dev == "cuda":
        # let Ampere/Turing GPUs use their tensor cores for matmuls — free speedup
        torch.backends.cuda.matmul.allow_tf32 = True
        torch.backends.cudnn.allow_tf32 = True
    ck_path = os.path.join(out_dir, "checkpoint.pt")
    resuming = resume and os.path.exists(ck_path)

    if resuming:
        # reuse the ORIGINAL tokenizer and config — retraining the tokenizer would
        # renumber every token and make the saved weights meaningless.
        cfg = GPTConfig(**json.load(open(os.path.join(out_dir, "config.json"))))
        tok = BPETokenizer().load_state(pickle.load(open(os.path.join(out_dir, "tokenizer.pkl"), "rb")))
        log(f"device: {dev}  ·  resuming from {ck_path}")
    else:
        cfg = cfg or GPTConfig(vocab_size=vocab_size)
        log(f"device: {dev}")
        t0 = time.time()
        log(f"  [1/2] learning tokenizer from {len(text)/1e6:.0f} MB (CPU, one-time) …")
        tok = BPETokenizer().train(text, vocab_size=cfg.vocab_size)
        log(f"        tokenizer ready in {time.time()-t0:.0f}s")

    os.makedirs(out_dir, exist_ok=True)
    # Tokenising the corpus is pure-Python and single-threaded — minutes on a big
    # corpus, with the GPU idle the whole time. Cache the token ids to disk keyed by a
    # signature of (corpus, vocab), so this cost is paid ONCE: later runs and --resume
    # load the cache in a second and jump straight to GPU training.
    sig = hashlib.md5(text.encode("utf-8", "ignore")).hexdigest()[:16] + f"-v{cfg.vocab_size}"
    tok_cache = os.path.join(out_dir, "tokens.pt")
    data = None
    if os.path.exists(tok_cache):
        try:
            blob = torch.load(tok_cache)
            if blob.get("sig") == sig:
                data = blob["ids"]
                log(f"  [2/2] loaded cached tokenised corpus ({len(data)/1e6:.1f}M tokens)")
        except Exception:
            data = None
    if data is None:
        t0 = time.time()
        log(f"  [2/2] encoding {len(text)/1e6:.0f} MB corpus (CPU, one-time) …")
        data = torch.tensor(tok.encode(text), dtype=torch.long)
        torch.save({"sig": sig, "ids": data}, tok_cache)
        log(f"        encoded {len(data)/1e6:.1f}M tokens in {time.time()-t0:.0f}s "
            f"(cached — instant next time)")
    if len(data) < cfg.block_size + 2:
        raise RuntimeError("Not enough text to train — feed the model more data first.")
    n = int(0.9 * len(data))
    train_d, val_d = data[:n], data[n:]
    # a small corpus can leave the 10% validation split shorter than one context window,
    # which would make the batch stack fail — fall back to measuring val on train data.
    if len(val_d) < cfg.block_size + 2:
        val_d = train_d
    log(f"tokens: {len(data)} (train {len(train_d)}, val {len(val_d)}) · vocab {tok.size}")

    # THE fix for a starved GPU: keep the whole token stream resident on the GPU as
    # int16 (every preset's vocab < 32768), so building a batch is pure GPU indexing —
    # no Python loop, no host→device copy per step. Previously each step waited on the
    # CPU to slice and transfer the batch, leaving the GPU idle ~80% of the time.
    assert cfg.vocab_size <= 32768
    train_d = train_d.to(torch.int16).to(dev)
    val_d = val_d.to(torch.int16).to(dev)
    _ar = torch.arange(cfg.block_size, device=dev)

    model = GPT(cfg).to(dev)
    log(f"model parameters: {model.num_params()/1e6:.1f}M")
    opt = torch.optim.AdamW(model.parameters(), lr=lr, betas=(0.9, 0.95))

    if compile_model:
        # torch.compile fuses the many small kernels into fewer, cutting launch overhead
        # — the one remaining code-side speedup once the GPU is already saturated. It
        # needs a C++/CUDA compiler; if that isn't set up, fall back rather than fail.
        try:
            model = torch.compile(model)
            log("  torch.compile enabled (first step is slow while it compiles)")
        except Exception as e:
            log(f"  torch.compile unavailable ({type(e).__name__}); continuing uncompiled")

    start_step, best_val, worse = 1, float("inf"), 0
    if resuming:
        ck = torch.load(ck_path, map_location=dev)
        model.load_state_dict(ck["model"])
        opt.load_state_dict(ck["opt"])
        start_step, best_val = ck["step"] + 1, ck.get("best_val", float("inf"))
        log(f"  continuing at step {start_step} (best val so far {best_val:.3f})")
        if start_step > steps:
            log(f"  already trained {ck['step']} steps; raise --steps to continue.")
            return model, tok

    def checkpoint(step, best):
        torch.save({"model": model.state_dict(), "opt": opt.state_dict(),
                    "scaler": scaler.state_dict(), "step": step, "best_val": best}, ck_path)

    def batch(split):
        d = train_d if split == "train" else val_d
        # last valid window start leaves room for the block plus its shifted target.
        hi = max(1, d.numel() - cfg.block_size - 1)
        ix = torch.randint(hi, (batch_size, 1), device=dev)   # (B,1) start offsets, on GPU
        rows = ix + _ar                                        # (B, block_size) index matrix
        x = d[rows].long()                                    # gather windows on the GPU
        y = d[rows + 1].long()
        return x, y

    # mixed precision: on a CUDA GPU, do the math in fp16 — ~1.5-2x faster and roughly
    # half the memory, so a bigger model fits. No effect (and no risk) on CPU.
    use_amp = (dev == "cuda")
    try:
        scaler = torch.amp.GradScaler("cuda", enabled=use_amp)      # torch >= 2.4
    except (AttributeError, TypeError):
        scaler = torch.cuda.amp.GradScaler(enabled=use_amp)         # older torch
    if resuming and "scaler" in ck:                    # restore fp16 loss-scale state
        scaler.load_state_dict(ck["scaler"])

    # the model files are written up front so an interrupted run still leaves a
    # loadable model behind, then overwritten whenever validation improves.
    save(model, tok, out_dir)
    every = max(1, min(save_every, steps // 20 or 1))
    model.train()
    step = start_step - 1
    t_mark, s_mark = time.time(), start_step - 1
    try:
        for step in range(start_step, steps + 1):
            x, y = batch("train")
            opt.zero_grad(set_to_none=True)
            with torch.autocast(device_type="cuda", dtype=torch.float16, enabled=use_amp):
                _, loss = model(x, y)
            scaler.scale(loss).backward()
            scaler.unscale_(opt)
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            scaler.step(opt)
            scaler.update()
            if step % every == 0 or step == start_step:
                model.eval()
                with torch.no_grad(), torch.autocast(device_type="cuda",
                                                     dtype=torch.float16, enabled=use_amp):
                    vl = sum(model(*batch("val"))[1].item() for _ in range(3)) / 3
                model.train()
                star = ""
                if vl < best_val:                     # keep the BEST weights, not the last
                    best_val, worse = vl, 0
                    save(model, tok, out_dir)
                    star = " ✓best"
                else:
                    worse += 1
                    # val rising while train falls = memorising the corpus, not learning
                    # the language. More steps make it worse; more DATA is the fix.
                    if worse == 4:
                        log(f"  ⚠ validation has risen {worse} checks running while train "
                            f"falls — the model is starting to memorise.")
                        log(f"    Best weights (val {best_val:.3f}) are already saved and "
                            f"are what you keep. More data helps; more steps will not.")
                checkpoint(step, best_val)
                # live throughput + ETA, so a long run visibly progresses instead of
                # looking stuck — and you can decide whether to wait or stop.
                now = time.time()
                sps = (step - s_mark) / max(now - t_mark, 1e-9)
                t_mark, s_mark = now, step
                tok_s = sps * batch_size * cfg.block_size
                eta = (steps - step) / max(sps, 1e-9)
                eta_s = f"{eta/60:.0f}m" if eta >= 60 else f"{eta:.0f}s"
                log(f"  step {step}/{steps}  train {loss.item():.3f}  val {vl:.3f}{star}"
                    f"   ·  {sps:.1f} it/s · {tok_s/1000:.0f}k tok/s · ETA {eta_s}")
                if patience and worse >= patience:
                    log(f"  ⏹ early stop: no improvement in {patience} checks.")
                    break
    except KeyboardInterrupt:
        checkpoint(step, best_val)
        log(f"\n  ⏸ stopped at step {step}. Progress saved (best val {best_val:.3f}).")
        log(f"  Continue where you left off:  --resume --steps {steps}")

    checkpoint(step, best_val)
    # hand back the BEST weights, not the last ones — otherwise the samples you see
    # come from an overfit model while the good one sits on disk.
    if os.path.exists(os.path.join(out_dir, "weights.pt")):
        model.load_state_dict(torch.load(os.path.join(out_dir, "weights.pt"),
                                         map_location=dev))
        model.eval()
    log(f"✓ model saved to {out_dir}  (best val {best_val:.3f})")
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
