"""
BL-Language-Sparse  —  the EFFICIENT section-1.2 architecture: oscillatory memory
everywhere, attention used SPARINGLY (only every k-th block, and only over a local
window). This is the blueprint's actual efficiency claim: keep the cheap O(1)
oscillatory memory as the default mixer and pay for attention only where it earns
its cost.

The full-attention hybrid (bl_language_hybrid.py) is fluent but pays O(T^2)
attention in every block. Here attention is:
  * PERIODIC  — only in 1 of every ATTN_EVERY blocks
  * WINDOWED  — each position attends only to the last WINDOW characters (O(T*W))
so its cost is a small fraction of full attention, while keeping most of the gain.

Set COMPARE=True to train a full-attention model and this sparse one side by side
and print both losses and the attention-cost ratio.

Corpus (tiny-shakespeare) downloaded at runtime. GPU-accelerated.
    pip install torch
    python bl_language_sparse.py
"""

import urllib.request
import torch
import torch.nn as nn
import torch.nn.functional as F

torch.manual_seed(0)
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
D_MODEL = 192
N_HEAD = 4
N_BLOCK = 3
ATTN_EVERY = 3         # attention only in every 3rd block (1-of-3)
WINDOW = 32            # local attention window (0 = full causal attention)
SEQ = 64               # main speed knob (oscillator is sequential); raise on a bigger GPU
BATCH = 48
STEPS = 3000
LR = 3e-3
COMPARE = False        # True -> also train a full-attention model for comparison
CORPUS_URL = "https://raw.githubusercontent.com/karpathy/char-rnn/master/data/tinyshakespeare/input.txt"
FALLBACK = ("to be or not to be that is the question whether tis nobler in the mind ") * 90


def get_corpus():
    try:
        with urllib.request.urlopen(CORPUS_URL, timeout=30) as r:
            return r.read().decode("utf-8"), "tiny-shakespeare"
    except Exception as e:
        print(f"[download failed ({type(e).__name__}); using fallback]")
        return FALLBACK, "fallback"


class OscillatoryMixer(nn.Module):
    def __init__(self, d):
        super().__init__()
        self.Wy = nn.Linear(d, d); self.Wu = nn.Linear(d, d, bias=False); self.d = d
        self.log_gamma = nn.Parameter(torch.full((d,), -0.7))
        self.log_alpha = nn.Parameter(torch.full((d,), -2.3))
        self.log_dt = nn.Parameter(torch.full((d,), -1.6))

    def forward(self, u):
        B, T, _ = u.shape
        Uu = self.Wu(u)                        # input projection for all steps at once (parallel)
        y = torch.zeros(B, self.d, device=u.device); z = torch.zeros(B, self.d, device=u.device)
        g, a, dt = self.log_gamma.exp(), self.log_alpha.exp(), self.log_dt.exp()
        outs = []
        for t in range(T):
            drive = torch.tanh(self.Wy(y) + Uu[:, t])
            z = z + dt * (drive - g * y - a * z); y = y + dt * z
            outs.append(y)
        return torch.stack(outs, dim=1)


class WindowedAttention(nn.Module):
    """Causal attention restricted to a local window of `window` keys (0 = full)."""
    def __init__(self, d, n_head, window):
        super().__init__()
        self.qkv = nn.Linear(d, 3 * d); self.proj = nn.Linear(d, d)
        self.n_head, self.window = n_head, window

    def forward(self, x):
        B, T, d = x.shape
        q, k, v = self.qkv(x).split(d, dim=2)
        hd = d // self.n_head
        q, k, v = [t.view(B, T, self.n_head, hd).transpose(1, 2) for t in (q, k, v)]
        if self.window and self.window < T:
            i = torch.arange(T, device=x.device)[:, None]
            j = torch.arange(T, device=x.device)[None, :]
            mask = (j <= i) & (i - j < self.window)          # causal + windowed
            y = F.scaled_dot_product_attention(q, k, v, attn_mask=mask)
        else:
            y = F.scaled_dot_product_attention(q, k, v, is_causal=True)
        return self.proj(y.transpose(1, 2).reshape(B, T, d))


class Block(nn.Module):
    def __init__(self, d, n_head, has_attn, window):
        super().__init__()
        self.ln1 = nn.LayerNorm(d); self.osc = OscillatoryMixer(d)
        self.has_attn = has_attn
        if has_attn:
            self.ln2 = nn.LayerNorm(d); self.att = WindowedAttention(d, n_head, window)
        self.ln3 = nn.LayerNorm(d)
        self.mlp = nn.Sequential(nn.Linear(d, 4 * d), nn.GELU(), nn.Linear(4 * d, d))

    def forward(self, x):
        x = x + self.osc(self.ln1(x))
        if self.has_attn:
            x = x + self.att(self.ln2(x))
        x = x + self.mlp(self.ln3(x))
        return x


class LM(nn.Module):
    def __init__(self, vocab, attn_every, window, d=D_MODEL, n_head=N_HEAD,
                 n_block=N_BLOCK, seq=SEQ):
        super().__init__()
        self.tok = nn.Embedding(vocab, d); self.pos = nn.Embedding(seq, d)
        self.blocks = nn.ModuleList([
            Block(d, n_head, has_attn=((i + 1) % attn_every == 0), window=window)
            for i in range(n_block)])
        self.n_attn = sum(b.has_attn for b in self.blocks)
        self.ln = nn.LayerNorm(d); self.head = nn.Linear(d, vocab); self.seq = seq

    def forward(self, x):
        T = x.shape[1]
        h = self.tok(x) + self.pos(torch.arange(T, device=x.device))[None]
        for b in self.blocks:
            h = b(h)
        return self.head(self.ln(h))


def train_model(model, train, val, V, steps, tag):
    opt = torch.optim.Adam(model.parameters(), lr=LR)

    offsets = torch.arange(SEQ + 1, device=DEVICE)

    def get_batch(d):
        ix = torch.randint(0, len(d) - SEQ - 1, (BATCH,), device=DEVICE)
        seq = d[ix[:, None] + offsets[None, :]]        # one vectorized gather (no GPU->CPU sync)
        return seq[:, :-1], seq[:, 1:]

    for step in range(1, steps + 1):
        x, y = get_batch(train)
        loss = F.cross_entropy(model(x).reshape(-1, V), y.reshape(-1))
        opt.zero_grad(); loss.backward()
        nn.utils.clip_grad_norm_(model.parameters(), 1.0); opt.step()
        if step % 500 == 0:
            print(f"  [{tag}] step {step:4d}  train {loss.item():.3f}", flush=True)
    return model


def main():
    text, src = get_corpus()
    chars = sorted(set(text)); stoi = {c: i for i, c in enumerate(chars)}
    itos = {i: c for c, i in stoi.items()}
    data = torch.tensor([stoi[c] for c in text], dtype=torch.long, device=DEVICE)
    V = len(chars); n = int(0.95 * len(data)); train, val = data[:n], data[n:]
    print(f"Device: {DEVICE.upper()}   corpus {src}, {len(text)} chars, vocab {V}\n")

    @torch.no_grad()
    def final_val(model):
        model.eval()
        offs = torch.arange(SEQ + 1, device=DEVICE)

        def gb():
            ix = torch.randint(0, len(val) - SEQ - 1, (BATCH,), device=DEVICE)
            s = val[ix[:, None] + offs[None, :]]
            return s[:, :-1], s[:, 1:]
        t = 0.0
        for _ in range(10):
            xb, yb = gb(); t += F.cross_entropy(model(xb).reshape(-1, V), yb.reshape(-1)).item()
        return t / 10

    # attention-cost proxy: sum over attention layers of keys-attended per query
    def attn_cost(n_attn, window):
        w = window if window else SEQ
        return n_attn * min(w, SEQ)

    sparse = LM(V, attn_every=ATTN_EVERY, window=WINDOW).to(DEVICE)
    print(f"SPARSE model: {N_BLOCK} blocks, attention in {sparse.n_attn} of them, "
          f"window={WINDOW}. attn-cost proxy={attn_cost(sparse.n_attn, WINDOW)}\n")
    train_model(sparse, train, val, V, STEPS, "sparse")
    sv = final_val(sparse)
    print(f"\nSPARSE final val loss: {sv:.3f}")

    if COMPARE:
        full = LM(V, attn_every=1, window=0).to(DEVICE)   # attention every block, full
        print(f"\nFULL model: attention in {full.n_attn} of {N_BLOCK} blocks, full. "
              f"attn-cost proxy={attn_cost(full.n_attn, 0)}")
        train_model(full, train, val, V, STEPS, "full")
        fv = final_val(full)
        cost_ratio = attn_cost(sparse.n_attn, WINDOW) / attn_cost(full.n_attn, 0)
        print(f"\n=== EFFICIENCY COMPARISON ===")
        print(f"  full   attention:  val {fv:.3f}   attn-cost 1.00x")
        print(f"  sparse attention:  val {sv:.3f}   attn-cost {cost_ratio:.2f}x "
              f"({1/cost_ratio:.0f}x cheaper attention)")

    @torch.no_grad()
    def sample(prompt="ROMEO:", n_gen=300, temp=0.8):
        sparse.eval(); idx = [stoi.get(c, 0) for c in prompt]
        for _ in range(n_gen):
            x = torch.tensor(idx[-SEQ:], device=DEVICE)[None]
            idx.append(int(torch.multinomial(F.softmax(sparse(x)[0, -1] / temp, -1), 1)))
        return "".join(itos[i] for i in idx)
    print("\n" + "=" * 60 + "\nGENERATED (sparse hybrid):\n" + "=" * 60)
    print(sample())


if __name__ == "__main__":
    main()
