"""
BL-Torch  —  the Brain-Like model in PyTorch, GPU-ready, trained on full MNIST.

Same brain design as bl_brain_model.py, in PyTorch so it runs on an NVIDIA GPU
(e.g. a laptop GeForce MX550) and scales to full MNIST (60k 28x28 images).

Brain systems in BL:
  * VISUAL CORTEX (V1): a FIXED bank of random convolutional filters + ReLU +
    pooling — like the brain's oriented edge detectors (simple cells) and their
    pooling (complex cells). No learning here; vision is a fixed front-end.
  * NEOCORTEX: a readout trained by a LOCAL three-factor rule (error x
    pre-activity) — NO backpropagation.
  * HIPPOCAMPUS: fast one-shot associative memory (gradient-free prototypes).
  * NEUROMODULATION: a novelty signal routes new stimuli to the hippocampus.

NO backpropagation anywhere: all learning is explicit local tensor math under
torch.no_grad(). The GPU only makes the same brain-like math fast on big data.
Auto-detects GPU (else CPU) and MNIST (else falls back to sklearn digits).

    pip install torch torchvision
    python bl_torch.py

If your GPU has little memory (MX550 ~2 GB) and you hit out-of-memory, lower
N_FILTERS below.
"""

import torch
import torch.nn.functional as F

torch.manual_seed(0)
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
N_FILTERS = 128        # V1 filters. Lower to 64 if you run out of GPU memory.
ACTIVE_FRAC = 0.15     # fraction of cortical features allowed to fire (k-WTA sparsity)
DTYPE = torch.float32


def load_data():
    try:
        from torchvision import datasets
        tr = datasets.MNIST(root="./data", train=True, download=True)
        te = datasets.MNIST(root="./data", train=False, download=True)
        Xtr = tr.data.to(DTYPE).reshape(-1, 1, 28, 28) / 255.0
        Xte = te.data.to(DTYPE).reshape(-1, 1, 28, 28) / 255.0
        return (Xtr.to(DEVICE), tr.targets.to(DEVICE),
                Xte.to(DEVICE), te.targets.to(DEVICE), 28), "MNIST (28x28, 60k/10k)"
    except Exception as e:
        print(f"[MNIST unavailable ({type(e).__name__}); using sklearn digits]")
        from sklearn.datasets import load_digits
        d = load_digits()
        X = torch.tensor(d.data / 16.0, dtype=DTYPE).reshape(-1, 1, 8, 8)
        y = torch.tensor(d.target, dtype=torch.long)
        g = torch.Generator().manual_seed(0)
        p = torch.randperm(len(X), generator=g)
        X, y = X[p], y[p]
        return (X[:1200].to(DEVICE), y[:1200].to(DEVICE),
                X[1200:].to(DEVICE), y[1200:].to(DEVICE), 8), "sklearn digits (8x8)"


class VisualCortex:
    """Fixed V1-like front-end: random conv filters (oriented edge detectors) +
    ReLU (simple cells) + max-pool (complex cells) + standardize + k-WTA sparsity.
    No learning — the brain's early vision is largely fixed structure."""

    def __init__(self, img_hw, n_filters=N_FILTERS, ksize=5, active_frac=ACTIVE_FRAC):
        g = torch.Generator().manual_seed(1)
        w = torch.randn(n_filters, 1, ksize, ksize, generator=g)
        self.Wc = (w / w.flatten(1).norm(dim=1)[:, None, None, None]).to(DEVICE)
        self.pad = ksize // 2
        self.hw = img_hw
        self.active_frac = active_frac
        self.mu = self.sd = self.k = None

    @torch.no_grad()
    def _raw(self, X, bs=1024):
        outs = []
        for i in range(0, len(X), bs):
            xb = X[i:i+bs].reshape(-1, 1, self.hw, self.hw)
            c = F.relu(F.conv2d(xb, self.Wc, stride=2, padding=self.pad))   # simple cells
            c = F.max_pool2d(c, 2)                                          # complex cells
            outs.append(c.reshape(len(xb), -1))
        return torch.cat(outs, 0)

    @torch.no_grad()
    def fit(self, X):                       # learn only normalization statistics
        H = self._raw(X)
        self.mu, self.sd = H.mean(0), H.std(0) + 1e-6
        self.k = max(1, int(self.active_frac * H.shape[1]))
        self.dim = H.shape[1]

    @torch.no_grad()
    def encode(self, X, bs=1024):
        H = (self._raw(X, bs) - self.mu) / self.sd
        if self.k < H.shape[1]:             # k-Winners-Take-All -> sparse, event-driven
            kth = H.topk(self.k, dim=1).values[:, -1:].contiguous()
            H = torch.where(H >= kth, H, torch.zeros_like(H))
        return H


class BLTorch:
    def __init__(self, encoder):
        self.enc = encoder
        self.W = None
        self.cortex_classes = None
        self.proto = {}

    @torch.no_grad()
    def slow_learn(self, X, y, epochs=15, lr=0.5, batch=512):
        classes = torch.unique(y).tolist()
        self.cortex_classes = classes
        idx = {c: i for i, c in enumerate(classes)}
        H = self.enc.encode(X)
        ymap = torch.tensor([idx[int(c)] for c in y.tolist()], device=DEVICE)
        Y = F.one_hot(ymap, len(classes)).to(DTYPE)
        self.W = torch.zeros(len(classes), H.shape[1], device=DEVICE, dtype=DTYPE)
        n = len(H)
        for _ in range(epochs):
            perm = torch.randperm(n, device=DEVICE)
            for i in range(0, n, batch):
                b = perm[i:i+batch]
                probs = torch.softmax(H[b] @ self.W.t(), dim=1)
                self.W += lr * ((Y[b] - probs).t() @ H[b]) / len(b)   # local rule

    @torch.no_grad()
    def fast_store(self, X, y):
        H = self.enc.encode(X)
        for c in torch.unique(y).tolist():
            m = H[y == c].mean(0)
            self.proto[c] = m / (m.norm() + 1e-9)

    @torch.no_grad()
    def _cortex_pred(self, H):
        cls = torch.tensor(self.cortex_classes, device=DEVICE)
        return cls[(H @ self.W.t()).argmax(1)]

    @torch.no_grad()
    def predict(self, X, batch=4096):
        preds = []
        for i in range(0, len(X), batch):
            H = self.enc.encode(X[i:i+batch])
            classes = sorted(self.proto)
            P = torch.stack([self.proto[c] for c in classes])
            Hn = H / (H.norm(dim=1, keepdim=True) + 1e-9)
            sims = Hn @ P.t()
            hippo = torch.tensor(classes, device=DEVICE)[sims.argmax(1)]
            if self.W is None:
                preds.append(hippo); continue
            cortex = self._cortex_pred(H)
            known = set(self.cortex_classes)
            new_cols = [j for j, c in enumerate(classes) if c not in known]
            if not new_cols:
                preds.append(cortex); continue
            known_cols = [j for j, c in enumerate(classes) if c in known]
            novel = sims[:, new_cols].max(1).values > sims[:, known_cols].max(1).values
            preds.append(torch.where(novel, hippo, cortex))
        return torch.cat(preds, 0)


def acc(pred, y, mask=None):
    if mask is not None:
        pred, y = pred[mask], y[mask]
    return (pred == y).float().mean().item()


if __name__ == "__main__":
    print(f"Device: {DEVICE.upper()}" +
          (f"  ({torch.cuda.get_device_name(0)})" if DEVICE == "cuda"
           else "  (no CUDA GPU found — running on CPU)"))
    Xtr, ytr, Xte, yte, hw = None, None, None, None, None
    (Xtr, ytr, Xte, yte, hw), name = load_data()
    print(f"Dataset: {name}   train={len(Xtr)}  test={len(Xte)}\n")

    vc = VisualCortex(img_hw=hw)
    vc.fit(Xtr)
    frac = (vc.encode(Xtr[:1000]) > 0).float().mean().item()
    print(f"Visual cortex: {N_FILTERS} fixed V1 filters -> {vc.dim} features, "
          f"{100*frac:.1f}% active per image (sparse, event-driven).\n")

    print("=" * 64)
    print("DEMO 1  Few-shot learning (hippocampus): accuracy vs #examples/class")
    print("=" * 64)
    for n in [1, 5, 10, 30]:
        m = BLTorch(vc)
        Xs, ys = [], []
        for c in range(10):
            ci = (ytr == c).nonzero(as_tuple=True)[0][:n]
            Xs.append(Xtr[ci]); ys.append(ytr[ci])
        m.fast_store(torch.cat(Xs), torch.cat(ys))
        print(f"   {n:2d} example(s)/class ->  test accuracy = {acc(m.predict(Xte), yte):.3f}")

    print("\n" + "=" * 64)
    print("DEMO 2  Cortical learning (LOCAL rule, NO backprop): full 10-class")
    print("=" * 64)
    bl = BLTorch(vc)
    bl.slow_learn(Xtr, ytr, epochs=15)
    print(f"   test accuracy = {acc(bl._cortex_pred(vc.encode(Xte)), yte):.3f}")

    print("\n" + "=" * 64)
    print("DEMO 3  One-shot new class (9) without forgetting 0-8")
    print("=" * 64)
    base = torch.isin(ytr, torch.arange(9, device=DEVICE))
    bl2 = BLTorch(vc)
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
