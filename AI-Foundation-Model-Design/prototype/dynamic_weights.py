"""
Dynamic Weight Generation (M2)  —  neurons that generate weights ON DEMAND.

The most radical assumption to break: that a network's weights are fixed after
training. The brain's effective wiring is generated per context in milliseconds
(neuromodulation, short-term / "fast" weights). This prototype demonstrates the
principle directly: a small HYPERNETWORK reads a few examples of a task and OUTPUTS
the weights of a target network that solves THAT task — instantly, with NO gradient
descent at test time.

Testbed (the classic meta-learning sinusoid): each task is a wave y = A*sin(x+phase)
with random A and phase. Given K sample points from a NEW wave the model has never
seen, the hypernetwork generates a network that fits the whole wave in ONE forward
pass. We compare against a normal network trained from scratch with gradient descent.

Biological inspiration : fast weights / context-generated connectivity (M2, doc 06).
Math                   : W_task = Hypernet(encode(support));  y = Target(x; W_task).
Advantage vs transformer: weights are produced on demand from a small generator
                          instead of a huge fixed weight set; instant adaptation.

Pure PyTorch, runs in ~1 min on CPU.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F

torch.manual_seed(0)
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
H = 20                                   # target-network hidden width
# flattened target weights: W1(H) b1(H) W2(H*H) b2(H) W3(H) b3(1)
SIZES = [H, H, H * H, H, H, 1]
NW = sum(SIZES)


def target_forward(x, w):
    """Run the TARGET net whose weights are the generated vector w (per task)."""
    B = w.shape[0]
    i = 0
    def take(n):
        nonlocal i
        s = w[:, i:i + n]; i += n; return s
    W1 = take(H).view(B, 1, H); b1 = take(H).view(B, 1, H)
    W2 = take(H * H).view(B, H, H); b2 = take(H).view(B, 1, H)
    W3 = take(H).view(B, H, 1); b3 = take(1).view(B, 1, 1)
    h = torch.tanh(x @ W1 + b1)          # (B,Q,H)
    h = torch.tanh(h @ W2 + b2)          # (B,Q,H)
    return h @ W3 + b3                    # (B,Q,1)


class HyperNet(nn.Module):
    """Reads a support set and emits the target network's weights."""
    def __init__(self, ctx=64):
        super().__init__()
        self.enc = nn.Sequential(nn.Linear(2, 64), nn.ReLU(), nn.Linear(64, ctx))  # per-point
        self.gen = nn.Sequential(nn.Linear(ctx, 128), nn.ReLU(),
                                 nn.Linear(128, 128), nn.ReLU(), nn.Linear(128, NW))

    def forward(self, support):          # support: (B, K, 2) = (x,y) pairs
        ctx = self.enc(support).mean(dim=1)          # set encoder: mean over points
        return self.gen(ctx)                          # (B, NW) generated weights


def sample_tasks(B, K, Q):
    """B random sine tasks; K support points + Q query points each."""
    A = torch.rand(B, 1, device=DEVICE) * 1.5 + 0.5          # amplitude 0.5..2
    ph = torch.rand(B, 1, device=DEVICE) * 3.14159            # phase 0..pi
    def pts(n):
        x = torch.rand(B, n, device=DEVICE) * 10 - 5          # x in [-5,5]
        y = A * torch.sin(x + ph)
        return x.unsqueeze(-1), y.unsqueeze(-1)
    xs, ys = pts(K); xq, yq = pts(Q)
    support = torch.cat([xs, ys], dim=-1)                     # (B,K,2)
    return support, xq, yq


if __name__ == "__main__":
    print(f"Device: {DEVICE.upper()}   target net has {NW} weights (generated on demand)\n")
    hyper = HyperNet().to(DEVICE)
    opt = torch.optim.Adam(hyper.parameters(), lr=1e-3)

    print("Meta-training the hypernetwork across random sine tasks...")
    for step in range(1, 4001):
        support, xq, yq = sample_tasks(64, K=10, Q=20)
        w = hyper(support)                                   # generate weights
        loss = F.mse_loss(target_forward(xq, w), yq)
        opt.zero_grad(); loss.backward(); opt.step()
        if step % 800 == 0:
            print(f"  step {step:4d}   meta train MSE = {loss.item():.4f}")

    # ---- Test on BRAND-NEW sine waves: generate weights, NO gradient steps ----
    with torch.no_grad():
        support, xq, yq = sample_tasks(500, K=10, Q=50)
        w = hyper(support)
        gen_mse = F.mse_loss(target_forward(xq, w), yq).item()

    # ---- Baseline: train a fresh net from scratch on the 10 support points ----
    def scratch_baseline(steps):
        support, xq, yq = sample_tasks(200, K=10, Q=50)
        xs, ys = support[..., :1], support[..., 1:]
        w = torch.zeros(200, NW, device=DEVICE, requires_grad=True)
        nn.init.normal_(w, std=0.3)
        o = torch.optim.Adam([w], lr=0.05)
        for _ in range(steps):
            o.zero_grad(); F.mse_loss(target_forward(xs, w), ys).backward(); o.step()
        with torch.no_grad():
            return F.mse_loss(target_forward(xq, w), yq).item()

    print("\n" + "=" * 62)
    print("ADAPTING TO NEW, UNSEEN SINE WAVES (10 example points each)")
    print("=" * 62)
    print(f"  Hypernet — weights GENERATED, 0 gradient steps : MSE {gen_mse:.4f}")
    print(f"  From-scratch net —  10 gradient steps          : MSE {scratch_baseline(10):.4f}")
    print(f"  From-scratch net — 100 gradient steps          : MSE {scratch_baseline(100):.4f}")
    print("=" * 62)
    print("The hypernetwork fits a new wave INSTANTLY (one forward pass, no training)")
    print("by generating the target network's weights on demand — the M2 principle:")
    print("weights produced from context, not stored and frozen.")
