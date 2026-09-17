"""
BL-Deep-Local  —  a DEEP network that learns MNIST with NO backpropagation.

This is the strongest form of the brain-native learning claim (blueprint section
5.2). Earlier `predictive_coding_brain.py` showed local learning matching backprop
on a toy 2D task; this shows a DEEP, multi-layer network learning its own features
on real MNIST using ONLY local predictive-coding updates — no global backward
pass, no weight transport.

Because it learns its own hidden features (unlike the fixed random encoder in
bl_torch/bl_advanced), this also answers the "learned/adaptive encoder" direction:
the features here are discovered by local plasticity, not hand-fixed.

------------------------------------------------------------------------------
HOW IT LEARNS (discriminative predictive coding; Song et al. 2020)
------------------------------------------------------------------------------
Activities x[0..L] (x[0]=image, x[L]=label). Feedforward predictions and errors:
        mu[l] = relu(x[l-1]) @ W[l] + b[l]        err[l] = x[l] - mu[l]
Free energy F = 0.5 * sum_l ||err[l]||^2.
INFERENCE (perception): relax hidden x[l] to reduce F:
        x[l] -= ilr * ( err[l] - relu'(x[l]) * (err[l+1] @ W[l+1]^T) )
LEARNING (plasticity): after settling, each weight uses ONLY local signals:
        W[l] += lr * relu(x[l-1])^T @ err[l] / B        b[l] += lr * mean(err[l])
Every quantity a synapse needs (its input activity, its output error) is local.
A backprop MLP of the same shape is trained alongside for comparison.
------------------------------------------------------------------------------
GPU-accelerated (auto-detects CUDA). Set TRAIN_N smaller for a fast CPU run.
    pip install torch torchvision
    python bl_deep_local.py
"""

import time
import torch
import torch.nn.functional as F

torch.manual_seed(0)
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
SIZES = [784, 400, 150, 10]
EPOCHS = 40
TRAIN_N = None         # None = full 60k. Set e.g. 20000 for a quicker CPU run.
INFER_STEPS = 20
INFER_LR = 0.2
LR = 0.03
MOMENTUM = 0.9         # momentum on the local weight updates -> faster convergence

act = torch.relu
def dact(z): return (z > 0).float()
L = len(SIZES) - 1


def load_mnist():
    try:
        from torchvision import datasets
        tr = datasets.MNIST(root="./data", train=True, download=True)
        te = datasets.MNIST(root="./data", train=False, download=True)
        Xtr = (tr.data.float().reshape(-1, 784) / 255.0).to(DEVICE)
        Xte = (te.data.float().reshape(-1, 784) / 255.0).to(DEVICE)
        return Xtr, tr.targets.to(DEVICE), Xte, yte_from(te), "MNIST"
    except Exception as e:
        print(f"[MNIST unavailable ({type(e).__name__}); using sklearn digits]")
        from sklearn.datasets import load_digits
        d = load_digits()
        X = torch.tensor(d.data / 16.0, dtype=torch.float32).to(DEVICE)
        y = torch.tensor(d.target).to(DEVICE)
        g = torch.Generator().manual_seed(0)
        p = torch.randperm(len(X), generator=g)
        X, y = X[p], y[p]
        SIZES[0] = 64
        return X[:1200], y[:1200], X[1200:], y[1200:], "digits"


def yte_from(te):
    return te.targets.to(DEVICE)


class DeepPredictiveCoding:
    """Deep net, local learning only. No autograd anywhere."""

    def __init__(self, sizes):
        self.W = [None] + [(torch.randn(sizes[l-1], sizes[l], device=DEVICE)
                            * (2 / sizes[l-1]) ** 0.5) for l in range(1, L + 1)]
        self.b = [None] + [torch.zeros(sizes[l], device=DEVICE) for l in range(1, L + 1)]
        self.vW = [None] + [torch.zeros_like(self.W[l]) for l in range(1, L + 1)]  # momentum

    def feedforward(self, X):
        x = [X]
        for l in range(1, L + 1):
            x.append(act(x[-1]) @ self.W[l] + self.b[l])
        return x

    def errors(self, x):
        e = [None] * (L + 1)
        for l in range(1, L + 1):
            e[l] = x[l] - (act(x[l-1]) @ self.W[l] + self.b[l])
        return e

    @torch.no_grad()
    def train_epoch(self, X, Y, bs=128):
        perm = torch.randperm(len(X), device=DEVICE)
        for i in range(0, len(X), bs):
            b = perm[i:i+bs]
            x = self.feedforward(X[b])
            x[L] = Y[b].clone()                       # clamp the label
            for _ in range(INFER_STEPS):              # perception: settle to min F
                e = self.errors(x)
                for l in range(1, L):
                    x[l] = x[l] - INFER_LR * (e[l] - dact(x[l]) * (e[l+1] @ self.W[l+1].t()))
            e = self.errors(x)
            for l in range(1, L + 1):                 # plasticity: LOCAL updates
                g = (act(x[l-1]).t() @ e[l]) / len(b)
                self.vW[l] = MOMENTUM * self.vW[l] + g
                self.W[l] += LR * self.vW[l]
                self.b[l] += LR * e[l].mean(0)

    @torch.no_grad()
    def acc(self, X, y):
        return (self.feedforward(X)[L].argmax(1) == y).float().mean().item()


class BackpropMLP:
    def __init__(self, sizes):
        self.W = [(torch.randn(sizes[l], sizes[l+1], device=DEVICE)
                   * (2 / sizes[l]) ** 0.5).requires_grad_() for l in range(L)]
        self.b = [torch.zeros(sizes[l+1], device=DEVICE, requires_grad=True) for l in range(L)]

    def forward(self, X):
        a = X
        for l in range(L - 1):
            a = act(a @ self.W[l] + self.b[l])
        return a @ self.W[-1] + self.b[-1]

    def train_epoch(self, X, Y, lr=0.2, bs=128):
        perm = torch.randperm(len(X), device=DEVICE)
        for i in range(0, len(X), bs):
            b = perm[i:i+bs]
            loss = ((self.forward(X[b]) - Y[b]) ** 2).mean()
            loss.backward()                            # GLOBAL backward pass
            with torch.no_grad():
                for w in self.W + self.b:
                    w -= lr * w.grad
                    w.grad = None

    def acc(self, X, y):
        with torch.no_grad():
            return (self.forward(X).argmax(1) == y).float().mean().item()


if __name__ == "__main__":
    print(f"Device: {DEVICE.upper()}" +
          (f"  ({torch.cuda.get_device_name(0)})" if DEVICE == "cuda" else "  (CPU — set TRAIN_N smaller)"))
    Xtr, ytr, Xte, yte, name = load_mnist()
    if TRAIN_N:
        Xtr, ytr = Xtr[:TRAIN_N], ytr[:TRAIN_N]
    Y = F.one_hot(ytr, 10).float()
    print(f"Dataset: {name}   train={len(Xtr)}  test={len(Xte)}   net={SIZES}\n")

    print("Training DEEP PREDICTIVE CODING (local learning, NO backprop):")
    t = time.time()
    pc = DeepPredictiveCoding(SIZES)
    for ep in range(EPOCHS):
        pc.train_epoch(Xtr, Y)
        if (ep + 1) % 5 == 0 or ep == 0:
            print(f"   epoch {ep+1:2d}  test acc = {pc.acc(Xte, yte):.3f}")
    pc_acc = pc.acc(Xte, yte)
    print(f"   -> deep local-learning accuracy: {pc_acc:.3f}   ({time.time()-t:.0f}s)\n")

    print("Training BACKPROP MLP (same architecture) for comparison:")
    bp = BackpropMLP(SIZES)
    for ep in range(EPOCHS):
        bp.train_epoch(Xtr, Y)
    bp_acc = bp.acc(Xte, yte)
    print(f"   -> backprop accuracy:            {bp_acc:.3f}")

    print("\n" + "=" * 60)
    print(f"Deep network, MNIST:  local learning {pc_acc:.3f}  vs  backprop {bp_acc:.3f}")
    print("A DEEP net learned its own features with NO backward pass — the")
    print("core brain-native claim, now on real images instead of a toy task.")
    print("=" * 60)
