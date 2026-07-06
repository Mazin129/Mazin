"""
BL-Torch  —  the Brain-Like model in PyTorch, GPU-ready, trained on full MNIST.

Same brain design as bl_brain_model.py (sparse coding + local-rule neocortex +
one-shot hippocampus + neuromodulatory novelty routing), re-implemented with
PyTorch tensors so it can run on an NVIDIA GPU (e.g. a laptop GeForce MX550) and
scale from the tiny 8x8 sklearn digits up to full MNIST (60,000 28x28 images).

Key point kept from the brain design: NO backpropagation is used anywhere. All
learning is explicit local tensor math (`torch.no_grad()` throughout). The GPU is
used only to make the same brain-like math fast on big data.

Runs on GPU if available, otherwise CPU (slower but identical results).

    pip install torch torchvision
    python bl_torch.py

If you have little GPU memory (the MX550 has ~2 GB), lower HIDDEN below.
"""

import torch
import torch.nn.functional as F

torch.manual_seed(0)
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
HIDDEN = 1200          # sparse-code size. Lower to 800 if you hit out-of-memory.
ACTIVE_FRAC = 0.08     # fraction of neurons allowed to fire per input (k-WTA)
DTYPE = torch.float32


def load_mnist():
    """Load full MNIST via torchvision; fall back to sklearn digits if MNIST
    can't be downloaded, so the script always runs."""
    try:
        from torchvision import datasets
        tr = datasets.MNIST(root="./data", train=True, download=True)
        te = datasets.MNIST(root="./data", train=False, download=True)
        Xtr = tr.data.reshape(-1, 784).to(DTYPE) / 255.0
        Xte = te.data.reshape(-1, 784).to(DTYPE) / 255.0
        ytr, yte = tr.targets.long(), te.targets.long()
        name = "MNIST (28x28, 60k train / 10k test)"
    except Exception as e:
        print(f"[MNIST unavailable ({type(e).__name__}); using sklearn digits]")
        from sklearn.datasets import load_digits
        d = load_digits()
        X = torch.tensor(d.data / 16.0, dtype=DTYPE)
        y = torch.tensor(d.target, dtype=torch.long)
        g = torch.Generator().manual_seed(0)
        p = torch.randperm(len(X), generator=g)
        X, y = X[p], y[p]
        Xtr, ytr, Xte, yte = X[:1200], y[:1200], X[1200:], y[1200:]
        name = "sklearn digits (8x8)"
    return (Xtr.to(DEVICE), ytr.to(DEVICE), Xte.to(DEVICE), yte.to(DEVICE)), name


class BLTorch:
    """Brain-Like model, all tensor math, no autograd/backprop."""

    def __init__(self, d_in, d_hidden=HIDDEN, active_frac=ACTIVE_FRAC):
        g = torch.Generator(device="cpu").manual_seed(1)
        self.R = (torch.randn(d_in, d_hidden, generator=g) / d_in ** 0.5).to(DEVICE)
        self.bias = (0.1 * torch.randn(d_hidden, generator=g)).to(DEVICE)
        self.k = max(1, int(active_frac * d_hidden))
        self.d_hidden = d_hidden
        self.W = None            # neocortex readout (set in slow_learn)
        self.cortex_classes = None
        self.proto = {}          # hippocampus: class -> unit-norm prototype

    @torch.no_grad()
    def encode(self, X, batch=4096):
        """Fixed sparse expansion code: ReLU random projection + k-Winners-Take-All.
        Only k of d_hidden neurons fire per input (event-driven, pattern-separating)."""
        outs = []
        for i in range(0, len(X), batch):
            h = torch.relu(X[i:i+batch] @ self.R + self.bias)
            if self.k < self.d_hidden:
                kth = h.topk(self.k, dim=1).values[:, -1:].contiguous()
                h = torch.where(h >= kth, h, torch.zeros_like(h))
            outs.append(h)
        return torch.cat(outs, 0)

    @torch.no_grad()
    def slow_learn(self, X, y, epochs=15, lr=0.5, batch=512):
        """Neocortex: local three-factor rule  dW ~ (label - prob) x pre-activity.
        No backprop — just the delta rule on a single readout over fixed features."""
        classes = torch.unique(y).tolist()
        self.cortex_classes = classes
        idx = {c: i for i, c in enumerate(classes)}
        C = len(classes)
        self.W = torch.zeros(C, self.d_hidden, device=DEVICE, dtype=DTYPE)
        ymap = torch.tensor([idx[int(c)] for c in y], device=DEVICE)
        H = self.encode(X)
        Y = F.one_hot(ymap, C).to(DTYPE)
        n = len(H)
        for _ in range(epochs):
            perm = torch.randperm(n, device=DEVICE)
            for i in range(0, n, batch):
                b = perm[i:i+batch]
                Hb, Yb = H[b], Y[b]
                probs = torch.softmax(Hb @ self.W.t(), dim=1)
                err = Yb - probs                          # local post-synaptic error
                self.W += lr * (err.t() @ Hb) / len(b)    # Hebbian: error x pre-activity

    @torch.no_grad()
    def fast_store(self, X, y):
        """Hippocampus: instant, gradient-free write of a class prototype."""
        H = self.encode(X)
        for c in torch.unique(y).tolist():
            m = H[y == c].mean(0)
            self.proto[c] = m / (m.norm() + 1e-9)

    @torch.no_grad()
    def _cortex_pred(self, H):
        cls = torch.tensor(self.cortex_classes, device=DEVICE)
        return cls[(H @ self.W.t()).argmax(1)]

    @torch.no_grad()
    def _hippo_sims(self, H):
        classes = sorted(self.proto)
        P = torch.stack([self.proto[c] for c in classes])          # (C,H)
        Hn = H / (H.norm(dim=1, keepdim=True) + 1e-9)
        return classes, Hn @ P.t()                                 # cosine similarity

    @torch.no_grad()
    def predict(self, X, batch=4096):
        preds = []
        for i in range(0, len(X), batch):
            H = self.encode(X[i:i+batch])
            classes, sims = self._hippo_sims(H)
            hippo_pred = torch.tensor(classes, device=DEVICE)[sims.argmax(1)]
            if self.W is None:
                preds.append(hippo_pred); continue
            cortex_pred = self._cortex_pred(H)
            known = set(self.cortex_classes)
            new_cols = [j for j, c in enumerate(classes) if c not in known]
            if not new_cols:
                preds.append(cortex_pred); continue
            known_cols = [j for j, c in enumerate(classes) if c in known]
            s_known = sims[:, known_cols].max(1).values
            s_new = sims[:, new_cols].max(1).values
            novel = s_new > s_known                                # hippocampal novelty
            preds.append(torch.where(novel, hippo_pred, cortex_pred))
        return torch.cat(preds, 0)


def acc(pred, y, mask=None):
    if mask is not None:
        pred, y = pred[mask], y[mask]
    return (pred == y).float().mean().item()


if __name__ == "__main__":
    print(f"Device: {DEVICE.upper()}"
          + (f"  ({torch.cuda.get_device_name(0)})" if DEVICE == "cuda" else "  (no CUDA GPU found — running on CPU)"))
    (Xtr, ytr, Xte, yte), name = load_mnist()
    print(f"Dataset: {name}   train={len(Xtr)}  test={len(Xte)}\n")

    bl = BLTorch(d_in=Xtr.shape[1])
    frac_active = (bl.encode(Xtr[:1000]) > 0).float().mean().item()
    print(f"Sparse code: {100*frac_active:.1f}% of neurons active per input "
          f"(event-driven, like cortex).\n")

    # DEMO 1 — few-shot learning (hippocampus)
    print("=" * 64)
    print("DEMO 1  Few-shot learning (hippocampus): accuracy vs #examples/class")
    print("=" * 64)
    for n in [1, 5, 10, 30]:
        h = BLTorch(d_in=Xtr.shape[1]); h.R, h.bias = bl.R, bl.bias
        Xs, ys = [], []
        for c in range(10):
            ci = (ytr == c).nonzero(as_tuple=True)[0][:n]
            Xs.append(Xtr[ci]); ys.append(ytr[ci])
        Xs, ys = torch.cat(Xs), torch.cat(ys)
        h.fast_store(Xs, ys)
        print(f"   {n:2d} example(s)/class ->  test accuracy = {acc(h.predict(Xte), yte):.3f}")

    # DEMO 2 — slow cortical learning, LOCAL rule, no backprop
    print("\n" + "=" * 64)
    print("DEMO 2  Cortical learning (LOCAL rule, NO backprop): full 10-class")
    print("=" * 64)
    bl.slow_learn(Xtr, ytr, epochs=15)
    print(f"   test accuracy = {acc(bl._cortex_pred(bl.encode(Xte)), yte):.3f}")

    # DEMO 3 — one-shot new class + no forgetting
    print("\n" + "=" * 64)
    print("DEMO 3  One-shot new class (9) without forgetting 0-8")
    print("=" * 64)
    base = torch.isin(ytr, torch.arange(9, device=DEVICE))
    bl2 = BLTorch(d_in=Xtr.shape[1]); bl2.R, bl2.bias = bl.R, bl.bias
    bl2.slow_learn(Xtr[base], ytr[base], epochs=15)
    bl2.fast_store(Xtr[base], ytr[base])
    known_mask = torch.isin(yte, torch.arange(9, device=DEVICE))
    new_mask = (yte == 9)
    print(f"  Cortex trained on digits 0-8 only.")
    print(f"    accuracy on class 9 before exposure: {acc(bl2.predict(Xte), yte, new_mask):.3f}\n")
    print(f"   {'#9 shown':>9} | {'new 9':>7} | {'old 0-8':>8} | {'all 10':>7}")
    print("  " + "-" * 40)
    for n_new in [1, 5, 10, 20]:
        nine = (ytr == 9).nonzero(as_tuple=True)[0][:n_new]
        bl2.fast_store(Xtr[nine], ytr[nine])
        p = bl2.predict(Xte)
        print(f"   {n_new:>9} | {acc(p, yte, new_mask):>7.3f} | "
              f"{acc(p, yte, known_mask):>8.3f} | {acc(p, yte):>7.3f}")
    print("\n  A single backprop net trained on 0-8 can NEVER score >0 on class 9.")
    print("  BL learns it from a few examples while keeping the old classes intact.")
