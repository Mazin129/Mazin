"""
BL-Language-Fast  —  the GPU-efficient oscillatory language model.

The earlier oscillatory cells use a sequential Python loop over timesteps, which
is launch-overhead-bound on a GPU (low utilisation, slow). The fix, and the real
SSM approach (LinOSS / S5 / Mamba-family), is a LINEAR recurrence that can be
computed with a PARALLEL SCAN instead of a loop.

Key change: the state update is made linear and input-driven —
        w_t = lambda ⊙ w_{t-1} + drive_t          (lambda, w complex, per channel)
where each channel's `lambda = exp(-softplus(nu) + i*theta)` is a damped complex
oscillator (magnitude < 1 for stability, angle theta = its frequency). A linear
time-invariant recurrence like this is a causal convolution with kernel
`lambda^n`, which we compute in one shot with the FFT — O(T log T), fully parallel,
no Python loop. That keeps the oscillatory memory (damped rotations in the complex
plane) while running efficiently on the GPU.

Combined with periodic windowed attention (section 1.2), this is the efficient AND
fast form of the architecture.

    pip install torch
    python bl_language_fast.py
"""

import math
import urllib.request
import torch
import torch.nn as nn
import torch.nn.functional as F

torch.manual_seed(0)
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
# ---- CHOOSE SPEED vs QUALITY (one word) ----
#   "fast"    : light, ~55 ms/step on an MX550, finishes in a few minutes (start here)
#   "quality" : bigger/slower, lower loss & more fluent text (run when you have time)
# Both modes use the same free quality boosts (AdamW + cosine LR schedule).
MODE = "fast"

if MODE == "quality":
    D_MODEL, N_BLOCK, SEQ, BATCH, STEPS = 256, 3, 192, 24, 6000
else:  # "fast" — bigger BATCH uses the idle GPU headroom (same ms/step, more data/step)
    D_MODEL, N_BLOCK, SEQ, BATCH, STEPS = 192, 2, 128, 64, 3000

N_HEAD = 4
ATTN_EVERY = 2         # attention in every 2nd block
WINDOW = 64            # local attention window (0 = full)
LR = 3e-3
WARMUP = 200           # linear warmup, then cosine decay -> lower loss, same speed
PROMPT = "ROMEO:"      # generation prompt (change to anything)
TEMPS = (0.7, 0.9)     # sample at these temperatures at the end
# If "quality" ever says CUDA out of memory: lower BATCH -> SEQ -> D_MODEL above.
CORPUS_URL = "https://raw.githubusercontent.com/karpathy/char-rnn/master/data/tinyshakespeare/input.txt"
FALLBACK = ("to be or not to be that is the question whether tis nobler in the mind ") * 120


def get_corpus():
    try:
        with urllib.request.urlopen(CORPUS_URL, timeout=30) as r:
            return r.read().decode("utf-8"), "tiny-shakespeare"
    except Exception as e:
        print(f"[download failed ({type(e).__name__}); using fallback]")
        return FALLBACK, "fallback"


class ParallelOscillatorySSM(nn.Module):
    """Linear complex-diagonal oscillatory state space, computed with the FFT
    (parallel scan). w_t = lambda*w_{t-1} + drive_t, lambda a damped rotation."""

    def __init__(self, d):
        super().__init__()
        self.inp = nn.Linear(d, d)
        self.out = nn.Linear(2 * d, d)          # combines Re and Im of the state
        # lambda = exp(-softplus(nu) + i*theta): magnitude in (0,1), learnable freq
        self.nu = nn.Parameter(torch.rand(d) * 2.0 + 0.5)      # -> decay
        self.theta = nn.Parameter(torch.rand(d) * 3.0)         # -> frequency

    def forward(self, u):
        B, T, d = u.shape
        drive = self.inp(u).to(torch.complex64)               # (B,T,d) input-driven
        loglam = (-F.softplus(self.nu) + 1j * self.theta)     # (d,) complex, Re<0
        n = torch.arange(T, device=u.device)
        kernel = torch.exp(n[:, None] * loglam[None, :])      # (T,d) = lambda^n, stable
        # causal convolution drive * kernel via FFT (linear conv, take first T)
        L = 1
        while L < 2 * T:
            L *= 2
        Kf = torch.fft.fft(kernel, n=L, dim=0)                # (L,d)
        Df = torch.fft.fft(drive, n=L, dim=1)                 # (B,L,d)
        w = torch.fft.ifft(Df * Kf[None], dim=1)[:, :T]       # (B,T,d) complex state
        return self.out(torch.cat([w.real, w.imag], dim=-1))


class WindowedAttention(nn.Module):
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
            mask = (j <= i) & (i - j < self.window)
            y = F.scaled_dot_product_attention(q, k, v, attn_mask=mask)
        else:
            y = F.scaled_dot_product_attention(q, k, v, is_causal=True)
        return self.proj(y.transpose(1, 2).reshape(B, T, d))


class Block(nn.Module):
    def __init__(self, d, n_head, has_attn, window):
        super().__init__()
        self.ln1 = nn.LayerNorm(d); self.ssm = ParallelOscillatorySSM(d)
        self.has_attn = has_attn
        if has_attn:
            self.ln2 = nn.LayerNorm(d); self.att = WindowedAttention(d, n_head, window)
        self.ln3 = nn.LayerNorm(d)
        self.mlp = nn.Sequential(nn.Linear(d, 4 * d), nn.GELU(), nn.Linear(4 * d, d))

    def forward(self, x):
        x = x + self.ssm(self.ln1(x))
        if self.has_attn:
            x = x + self.att(self.ln2(x))
        x = x + self.mlp(self.ln3(x))
        return x


class FastLM(nn.Module):
    def __init__(self, vocab, d=D_MODEL, n_head=N_HEAD, n_block=N_BLOCK,
                 attn_every=ATTN_EVERY, window=WINDOW, seq=SEQ):
        super().__init__()
        self.tok = nn.Embedding(vocab, d); self.pos = nn.Embedding(seq, d)
        self.blocks = nn.ModuleList([
            Block(d, n_head, has_attn=((i + 1) % attn_every == 0), window=window)
            for i in range(n_block)])
        self.ln = nn.LayerNorm(d); self.head = nn.Linear(d, vocab); self.seq = seq

    def forward(self, x):
        T = x.shape[1]
        h = self.tok(x) + self.pos(torch.arange(T, device=x.device))[None]
        for b in self.blocks:
            h = b(h)
        return self.head(self.ln(h))


def main():
    import time
    text, src = get_corpus()
    chars = sorted(set(text)); stoi = {c: i for i, c in enumerate(chars)}
    itos = {i: c for c, i in stoi.items()}
    data = torch.tensor([stoi[c] for c in text], dtype=torch.long, device=DEVICE)
    V = len(chars); n = int(0.95 * len(data)); train, val = data[:n], data[n:]
    print(f"Device: {DEVICE.upper()}   corpus {src}, {len(text)} chars, vocab {V}\n")

    model = FastLM(V).to(DEVICE)
    print(f"Fast oscillatory LM: {sum(p.numel() for p in model.parameters())/1e6:.2f}M params, "
          f"SEQ={SEQ}, parallel-scan SSM (no Python time loop).\n")
    opt = torch.optim.AdamW(model.parameters(), lr=LR, weight_decay=0.01)

    def lr_at(step):                                  # linear warmup -> cosine decay
        if step < WARMUP:
            return LR * step / WARMUP
        p = (step - WARMUP) / max(1, STEPS - WARMUP)
        return 0.1 * LR + 0.9 * LR * 0.5 * (1 + math.cos(math.pi * p))

    offsets = torch.arange(SEQ + 1, device=DEVICE)

    def get_batch(d):
        # Build the batch in ONE vectorized gather — no Python loop over a CUDA
        # tensor (that would force a GPU->CPU sync per element and starve the GPU).
        ix = torch.randint(0, len(d) - SEQ - 1, (BATCH,), device=DEVICE)
        seq = d[ix[:, None] + offsets[None, :]]        # (BATCH, SEQ+1), single op
        return seq[:, :-1], seq[:, 1:]

    @torch.no_grad()
    def val_loss():
        model.eval()
        t = 0.0
        for _ in range(5):
            xb, yb = get_batch(val)
            t += F.cross_entropy(model(xb).reshape(-1, V), yb.reshape(-1)).item()
        model.train(); return t / 5

    @torch.no_grad()
    def sample(prompt="ROMEO:", n_gen=400, temp=0.8):
        model.eval(); idx = [stoi.get(c, 0) for c in prompt]
        for _ in range(n_gen):
            x = torch.tensor(idx[-SEQ:], device=DEVICE)[None]
            idx.append(int(torch.multinomial(F.softmax(model(x)[0, -1] / temp, -1), 1)))
        model.train(); return "".join(itos[i] for i in idx)

    print("Training the parallel-scan oscillatory LM (prints from step 1)...", flush=True)
    t0 = time.time()
    try:
        for step in range(1, STEPS + 1):
            for g in opt.param_groups:
                g["lr"] = lr_at(step)
            x, y = get_batch(train)
            loss = F.cross_entropy(model(x).reshape(-1, V), y.reshape(-1))
            opt.zero_grad(); loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0); opt.step()
            # print immediately for the first steps (so you see ms/step and that it's alive)
            if step in (1, 2, 5, 10, 25, 50, 100, 200, 300) or step % 500 == 0:
                ms = (time.time() - t0) / step * 1000
                msg = f"  step {step:5d}   train {loss.item():.3f}   ({ms:.0f} ms/step)"
                if step % 500 == 0:
                    msg += f"   val {val_loss():.3f}"
                print(msg, flush=True)
    except RuntimeError as e:
        if "out of memory" in str(e).lower():
            print("\n*** CUDA out of memory. Lower BATCH (e.g. 16), then SEQ (e.g. 128),\n"
                  "    then D_MODEL (e.g. 192) at the top of this file and rerun. ***")
            return
        raise

    for temp in TEMPS:
        print("\n" + "=" * 60 + f"\nGENERATED (prompt {PROMPT!r}, temperature {temp}):\n" + "=" * 60)
        print(sample(prompt=PROMPT, temp=temp))


if __name__ == "__main__":
    main()
