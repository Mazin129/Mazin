"""
BL-Language-Real  —  the oscillatory language model, trained on a REAL corpus
(tiny-shakespeare, ~1 MB of actual text), in PyTorch.

Scales bl_language.py from a toy embedded string to real text. The recurrent core
is still the physics-grounded coupled-oscillator cell (blueprint section 1.2) with
learnable per-neuron dynamics, now stacked two deep with layer-norm and trained to
predict the next character over Shakespeare.

The corpus is downloaded at runtime (tiny-shakespeare); if the download fails it
falls back to a small built-in text, so the script always runs.

    pip install torch
    python bl_language_real.py

Defaults are sized for a GPU. On CPU, lower D_HID / STEPS (see the constants).
GPU-accelerated (auto-detects CUDA).
"""

import urllib.request
import torch
import torch.nn as nn
import torch.nn.functional as F

torch.manual_seed(0)
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
D_EMB = 64
D_HID = 384            # hidden width. Lower to 256 on CPU / small GPU.
SEQ = 96              # sequence length (the oscillator is sequential — main speed knob)
BATCH = 64
STEPS = 6000          # training steps. Lower for a quick look.
LR = 3e-3
CORPUS_URL = "https://raw.githubusercontent.com/karpathy/char-rnn/master/data/tinyshakespeare/input.txt"

FALLBACK = ("to be or not to be that is the question whether tis nobler in the mind "
            "to suffer the slings and arrows of outrageous fortune or to take arms "
            "against a sea of troubles and by opposing end them ") * 40


def get_corpus():
    try:
        with urllib.request.urlopen(CORPUS_URL, timeout=30) as r:
            text = r.read().decode("utf-8")
        return text, "tiny-shakespeare (downloaded)"
    except Exception as e:
        print(f"[download failed ({type(e).__name__}); using built-in fallback text]")
        return FALLBACK, "built-in fallback"


class OscillatoryCell(nn.Module):
    """Coupled damped oscillators, symplectic integration, LEARNABLE per-unit
    frequency (gamma), damping (alpha), and timestep (dt) (blueprint section 1.2)."""

    def __init__(self, d_in, d_hid):
        super().__init__()
        self.Wy = nn.Linear(d_hid, d_hid)
        self.Wu = nn.Linear(d_in, d_hid, bias=False)
        self.d_hid = d_hid
        self.log_gamma = nn.Parameter(torch.full((d_hid,), -0.7))
        self.log_alpha = nn.Parameter(torch.full((d_hid,), -2.3))
        self.log_dt = nn.Parameter(torch.full((d_hid,), -1.6))

    def forward(self, u):
        B, T, _ = u.shape
        Uu = self.Wu(u)                       # input projection for all steps at once (parallel, GPU-friendly)
        y = torch.zeros(B, self.d_hid, device=u.device)
        z = torch.zeros(B, self.d_hid, device=u.device)
        g, a, dt = self.log_gamma.exp(), self.log_alpha.exp(), self.log_dt.exp()
        outs = []
        for t in range(T):
            drive = torch.tanh(self.Wy(y) + Uu[:, t])
            z = z + dt * (drive - g * y - a * z)
            y = y + dt * z
            outs.append(y)
        return torch.stack(outs, dim=1)


class OscLM(nn.Module):
    def __init__(self, vocab, d_emb=D_EMB, d_hid=D_HID):
        super().__init__()
        self.emb = nn.Embedding(vocab, d_emb)
        self.cell1 = OscillatoryCell(d_emb, d_hid)
        self.norm = nn.LayerNorm(d_hid)
        self.cell2 = OscillatoryCell(d_hid, d_hid)
        self.head = nn.Linear(d_hid, vocab)

    def forward(self, x):
        h = self.cell1(self.emb(x))
        h = h + self.cell2(self.norm(h))          # stacked oscillators + residual
        return self.head(h)


def main():
    text, src = get_corpus()
    chars = sorted(set(text))
    stoi = {c: i for i, c in enumerate(chars)}
    itos = {i: c for c, i in stoi.items()}
    data = torch.tensor([stoi[c] for c in text], dtype=torch.long, device=DEVICE)
    V = len(chars)
    n = int(0.95 * len(data))
    train, val = data[:n], data[n:]
    print(f"Device: {DEVICE.upper()}   corpus: {src}, {len(text)} chars, vocab {V}\n")

    model = OscLM(V).to(DEVICE)
    nparam = sum(p.numel() for p in model.parameters())
    opt = torch.optim.Adam(model.parameters(), lr=LR)
    print(f"Oscillatory LM: {nparam/1e6:.2f}M params, {D_HID} hidden.\n")

    def get_batch(split):
        d = train if split == "train" else val
        ix = torch.randint(0, len(d) - SEQ - 1, (BATCH,), device=DEVICE)
        x = torch.stack([d[i:i+SEQ] for i in ix])
        y = torch.stack([d[i+1:i+SEQ+1] for i in ix])
        return x, y

    @torch.no_grad()
    def val_loss():
        model.eval()
        tot = 0.0
        for _ in range(5):
            xb, yb = get_batch("val")                 # x and y from the SAME location
            tot += F.cross_entropy(model(xb).reshape(-1, V), yb.reshape(-1)).item()
        model.train()
        return tot / 5

    @torch.no_grad()
    def sample(prompt="ROMEO:", n_gen=400, temp=0.8):
        model.eval()
        idx = [stoi.get(c, 0) for c in prompt]
        for _ in range(n_gen):
            x = torch.tensor(idx[-SEQ:], device=DEVICE)[None]
            logits = model(x)[0, -1] / temp
            idx.append(int(torch.multinomial(F.softmax(logits, -1), 1)))
        model.train()
        return "".join(itos[i] for i in idx)

    print("Training on real text...")
    for step in range(1, STEPS + 1):
        x, y = get_batch("train")
        loss = F.cross_entropy(model(x).reshape(-1, V), y.reshape(-1))
        opt.zero_grad(); loss.backward()
        nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        if step % 500 == 0:
            print(f"  step {step:5d}   train {loss.item():.3f}   val {val_loss():.3f}")

    print("\n" + "=" * 66)
    print("GENERATED SHAKESPEARE (prompt 'ROMEO:'):")
    print("=" * 66)
    print(sample())
    print("=" * 66)


if __name__ == "__main__":
    main()
