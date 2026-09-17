"""
BL-Language  —  a character-level language model built on the OSCILLATORY MEMORY
cell (blueprint section 1.2), in PyTorch. It reads text and learns to generate it.

This is the first step toward the language side of the blueprint. The recurrent
core is the same physics-grounded coupled-oscillator cell validated in
`selective_oscillatory_memory.py` (whose symplectic dynamics give stable
long-range gradient flow), here wrapped with a character embedding and a softmax
readout and trained to predict the next character.

Note on learning rule: this demo uses ordinary gradient training (autograd) — it
is showcasing the oscillatory *memory architecture*, a different thread from the
no-backprop brain-native learning shown in bl_deep_local.py / predictive_coding_brain.py.

GPU-accelerated (auto-detects CUDA).
    pip install torch
    python bl_language.py
"""

import torch
import torch.nn as nn
import torch.nn.functional as F

torch.manual_seed(0)
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# A small, self-contained training corpus (no external download needed).
TEXT = (
    "the brain is a network of many small cells. each cell sends a tiny signal to "
    "the next cell. when many cells fire together, a thought appears. the brain learns "
    "by changing the strength of the links between its cells. it learns a little from "
    "every new thing that it sees and hears. a child can learn a new word from only a "
    "few examples, and it does not forget the old words when it learns the new one. "
    "memory lives in the links, not in any single cell. when we sleep, the brain plays "
    "back the day and moves what matters into deeper memory. this is how a small brain, "
    "using very little energy, can learn so much from so little. a good model of the "
    "mind should learn fast, remember long, and never stop learning from the world. "
) * 12


class OscillatoryCell(nn.Module):
    """Coupled damped nonlinear oscillators, symplectic integration (section 1.2).
    y'' = tanh(Wy y + Wu u + b) - gamma*y - alpha*y' ; state (position y, velocity z)."""

    def __init__(self, d_in, d_hid):
        super().__init__()
        self.Wy = nn.Linear(d_hid, d_hid)
        self.Wu = nn.Linear(d_in, d_hid, bias=False)
        self.d_hid = d_hid
        # Per-unit oscillator dynamics are LEARNED (each neuron finds its own
        # frequency/damping/timestep) — parameterised in log-space to stay positive.
        self.log_gamma = nn.Parameter(torch.full((d_hid,), -0.7))   # stiffness
        self.log_alpha = nn.Parameter(torch.full((d_hid,), -2.3))   # damping
        self.log_dt = nn.Parameter(torch.full((d_hid,), -1.6))      # timestep

    def forward(self, u):                          # u: (B, T, d_in)
        B, T, _ = u.shape
        y = torch.zeros(B, self.d_hid, device=u.device)
        z = torch.zeros(B, self.d_hid, device=u.device)
        gamma, alpha, dt = self.log_gamma.exp(), self.log_alpha.exp(), self.log_dt.exp()
        outs = []
        for t in range(T):
            drive = torch.tanh(self.Wy(y) + self.Wu(u[:, t]))
            z = z + dt * (drive - gamma * y - alpha * z)
            y = y + dt * z
            outs.append(y)
        return torch.stack(outs, dim=1)            # (B, T, d_hid)


class OscLM(nn.Module):
    def __init__(self, vocab, d_emb=48, d_hid=256):
        super().__init__()
        self.emb = nn.Embedding(vocab, d_emb)
        self.cell = OscillatoryCell(d_emb, d_hid)
        self.out = nn.Linear(d_hid, vocab)

    def forward(self, x):
        return self.out(self.cell(self.emb(x)))


def main():
    chars = sorted(set(TEXT))
    stoi = {c: i for i, c in enumerate(chars)}
    itos = {i: c for c, i in stoi.items()}
    data = torch.tensor([stoi[c] for c in TEXT], device=DEVICE)
    V = len(chars)
    print(f"Device: {DEVICE.upper()}   corpus={len(TEXT)} chars, vocab={V}\n")

    model = OscLM(V).to(DEVICE)
    opt = torch.optim.Adam(model.parameters(), lr=4e-3)
    T, B = 48, 48

    offsets = torch.arange(T + 1, device=DEVICE)

    def batch():
        ix = torch.randint(0, len(data) - T - 1, (B,), device=DEVICE)
        seq = data[ix[:, None] + offsets[None, :]]     # one vectorized gather (no GPU->CPU sync)
        return seq[:, :-1], seq[:, 1:]

    @torch.no_grad()
    def sample(prompt="the brain ", n=220, temp=0.5):
        model.eval()
        idx = [stoi[c] for c in prompt]
        for _ in range(n):
            x = torch.tensor(idx[-48:], device=DEVICE)[None]
            logits = model(x)[0, -1] / temp
            p = F.softmax(logits, dim=-1)
            idx.append(int(torch.multinomial(p, 1)))
        model.train()
        return "".join(itos[i] for i in idx)

    print("Training the oscillatory language model...")
    for step in range(1, 2501):
        x, y = batch()
        logits = model(x)
        loss = F.cross_entropy(logits.reshape(-1, V), y.reshape(-1))
        opt.zero_grad(); loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        if step % 200 == 0:
            print(f"  step {step:4d}  loss {loss.item():.3f}   sample: "
                  f"\"{sample(n=60).strip()[:60]}...\"")

    print("\n" + "=" * 66)
    print("GENERATED TEXT (prompt = 'the brain '):")
    print("=" * 66)
    print(sample(n=300))
    print("=" * 66)
    print("A physics-grounded oscillatory memory cell, trained to write text.")


if __name__ == "__main__":
    main()
