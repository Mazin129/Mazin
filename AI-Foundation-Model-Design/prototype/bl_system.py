"""
BL-System  —  the full brain-like stack in ONE model.

Wires together every piece built in this folder into a single system:

   image ─► V1 VISUAL CORTEX (fixed random conv edge-detectors + pooling)
              │  (bl_advanced.py)
              ▼
         NEOCORTEX: a DEEP network that learns its own features with the LOCAL
         predictive-coding rule — NO backpropagation   (bl_deep_local.py)
              │
              ▼
         class prediction
              ▲
         HIPPOCAMPUS: fast episodic memory (stored exemplars + k-NN) with
         neuromodulatory novelty routing for one-shot new classes  (bl_advanced.py)

So one model does: learned deep vision features (no backprop) + few-shot + one-shot
new class + no catastrophic forgetting. GPU-accelerated; MNIST or Fashion-MNIST.

    pip install torch torchvision
    python bl_system.py
"""

import torch
import torch.nn.functional as F

torch.manual_seed(0)
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
DATASET = "mnist"          # "mnist" or "fashion"
N_FILTERS = 96
PC_HIDDEN = 300            # deep neocortex hidden width
EPOCHS = 20
TRAIN_N = None             # None = full 60k; set e.g. 20000 for a quick CPU run
act = torch.relu
def dact(z): return (z > 0).float()


def load_data(which):
    from torchvision import datasets
    cls = datasets.FashionMNIST if which == "fashion" else datasets.MNIST
    tr = cls(root="./data", train=True, download=True)
    te = cls(root="./data", train=False, download=True)
    Xtr = tr.data.float().reshape(-1, 1, 28, 28).to(DEVICE) / 255.0
    Xte = te.data.float().reshape(-1, 1, 28, 28).to(DEVICE) / 255.0
    return Xtr, tr.targets.to(DEVICE), Xte, te.targets.to(DEVICE)


class VisualCortex:
    """Fixed V1: random conv edge detectors + ReLU + pool + standardize + k-WTA."""
    def __init__(self, n_filters=N_FILTERS, ksize=5, active_frac=0.15):
        g = torch.Generator().manual_seed(1)
        w = torch.randn(n_filters, 1, ksize, ksize, generator=g)
        self.Wc = (w / w.flatten(1).norm(dim=1)[:, None, None, None]).to(DEVICE)
        self.pad, self.active_frac = ksize // 2, active_frac
        self.mu = self.sd = self.k = None

    @torch.no_grad()
    def _raw(self, X, bs=1024):
        outs = []
        for i in range(0, len(X), bs):
            c = F.relu(F.conv2d(X[i:i+bs], self.Wc, stride=2, padding=self.pad))
            outs.append(F.max_pool2d(c, 2).reshape(len(X[i:i+bs]), -1))
        return torch.cat(outs, 0)

    @torch.no_grad()
    def fit(self, X):
        H = self._raw(X)
        self.mu, self.sd = H.mean(0), H.std(0) + 1e-6
        self.k, self.dim = max(1, int(self.active_frac * H.shape[1])), H.shape[1]

    @torch.no_grad()
    def encode(self, X, bs=1024):
        H = (self._raw(X, bs) - self.mu) / self.sd
        kth = H.topk(self.k, dim=1).values[:, -1:].contiguous()
        return torch.where(H >= kth, H, torch.zeros_like(H))


class DeepLocalCortex:
    """Deep neocortex trained by the LOCAL predictive-coding rule (no backprop),
    on top of the V1 features."""
    def __init__(self, sizes):
        self.sizes, self.L = sizes, len(sizes) - 1
        self.W = [None] + [(torch.randn(sizes[l-1], sizes[l], device=DEVICE)
                            * (2 / sizes[l-1]) ** 0.5) for l in range(1, self.L + 1)]
        self.b = [None] + [torch.zeros(sizes[l], device=DEVICE) for l in range(1, self.L + 1)]
        self.v = [None] + [torch.zeros_like(self.W[l]) for l in range(1, self.L + 1)]

    def ff(self, X):
        x = [X]
        for l in range(1, self.L + 1):
            x.append(act(x[-1]) @ self.W[l] + self.b[l])
        return x

    def errs(self, x):
        e = [None] * (self.L + 1)
        for l in range(1, self.L + 1):
            e[l] = x[l] - (act(x[l-1]) @ self.W[l] + self.b[l])
        return e

    @torch.no_grad()
    def learn(self, H, y, epochs=EPOCHS, steps=20, ilr=0.2, lr=0.03, mom=0.9, bs=128):
        Y = F.one_hot(y, self.sizes[-1]).float()
        for _ in range(epochs):
            perm = torch.randperm(len(H), device=DEVICE)
            for i in range(0, len(H), bs):
                b = perm[i:i+bs]
                x = self.ff(H[b]); x[self.L] = Y[b].clone()
                for _ in range(steps):
                    e = self.errs(x)
                    for l in range(1, self.L):
                        x[l] = x[l] - ilr * (e[l] - dact(x[l]) * (e[l+1] @ self.W[l+1].t()))
                e = self.errs(x)
                for l in range(1, self.L + 1):
                    g = (act(x[l-1]).t() @ e[l]) / len(b)
                    self.v[l] = mom * self.v[l] + g
                    self.W[l] += lr * self.v[l]; self.b[l] += lr * e[l].mean(0)

    @torch.no_grad()
    def logits(self, H):
        return self.ff(H)[self.L]


class EpisodicHippocampus:
    def __init__(self, max_per_class=40):
        self.codes, self.max = {}, max_per_class

    @torch.no_grad()
    def store(self, H, y):
        Hn = H / (H.norm(dim=1, keepdim=True) + 1e-9)
        for c in torch.unique(y).tolist():
            self.codes[c] = Hn[y == c][:self.max]

    def _bank(self):
        cs = sorted(self.codes)
        E = torch.cat([self.codes[c] for c in cs], 0)
        ey = torch.cat([torch.full((len(self.codes[c]),), c, device=DEVICE) for c in cs])
        return cs, E, ey

    @torch.no_grad()
    def knn(self, H, k=3):
        cs, E, ey = self._bank()
        Hn = H / (H.norm(dim=1, keepdim=True) + 1e-9)
        vals, idx = (Hn @ E.t()).topk(min(k, len(E)), dim=1)
        votes = torch.zeros(len(H), max(cs) + 1, device=DEVICE)
        for j in range(vals.shape[1]):
            votes.scatter_add_(1, ey[idx[:, j:j+1]], vals[:, j:j+1].clamp(min=0))
        return votes.argmax(1)

    @torch.no_grad()
    def novelty(self, H, known):
        cs, E, ey = self._bank()
        Hn = H / (H.norm(dim=1, keepdim=True) + 1e-9)
        sims = Hn @ E.t()
        is_new = torch.tensor([c not in known for c in ey.tolist()], device=DEVICE)
        s_new = sims[:, is_new].max(1).values
        s_known = sims[:, ~is_new].max(1).values
        ni = is_new.nonzero(as_tuple=True)[0]
        new_pred = ey[ni][sims[:, ni].argmax(1)]
        return s_new > s_known, new_pred


def acc(p, y, m=None):
    if m is not None: p, y = p[m], y[m]
    return (p == y).float().mean().item()


if __name__ == "__main__":
    print(f"Device: {DEVICE.upper()}" +
          (f"  ({torch.cuda.get_device_name(0)})" if DEVICE == "cuda" else "  (CPU)"))
    Xtr, ytr, Xte, yte = load_data(DATASET)
    if TRAIN_N:
        Xtr, ytr = Xtr[:TRAIN_N], ytr[:TRAIN_N]
    print(f"Dataset: {DATASET}   train={len(Xtr)}  test={len(Xte)}\n")

    # V1 vision (fixed)
    vc = VisualCortex(); vc.fit(Xtr)
    Htr, Hte = vc.encode(Xtr), vc.encode(Xte)
    print(f"V1 visual cortex: {N_FILTERS} filters -> {vc.dim} features.\n")

    print("=" * 62)
    print("FULL SYSTEM  V1 vision -> DEEP local-learning cortex (NO backprop)")
    print("=" * 62)
    cortex = DeepLocalCortex([vc.dim, PC_HIDDEN, 10])
    cortex.learn(Htr, ytr)
    print(f"   test accuracy = {acc(cortex.logits(Hte).argmax(1), yte):.3f}"
          f"   (deep features learned with no backward pass)\n")

    print("=" * 62)
    print("ONE-SHOT new class via the hippocampus, no forgetting")
    print("=" * 62)
    base = ytr < 9
    cx = DeepLocalCortex([vc.dim, PC_HIDDEN, 9])
    # remap base labels 0-8 -> 0-8 (already contiguous)
    cx.learn(Htr[base], ytr[base])
    hpc = EpisodicHippocampus(); hpc.store(Htr[base], ytr[base])
    known = set(range(9))
    known_mask, new_mask = yte < 9, yte == 9

    def system_predict(H):
        cpred = cx.logits(H).argmax(1)
        novel, new_pred = hpc.novelty(H, known)
        return torch.where(novel, new_pred, cpred)

    print(f"  Cortex trained on classes 0-8 only.")
    print(f"   {'#9 shown':>9} | {'new 9':>7} | {'old 0-8':>8} | {'all 10':>7}")
    print("  " + "-" * 40)
    for n_new in [1, 5, 10, 20]:
        nine = (ytr == 9).nonzero(as_tuple=True)[0][:n_new]
        hpc.store(Htr[nine], ytr[nine])
        p = system_predict(Hte)
        print(f"   {n_new:>9} | {acc(p, yte, new_mask):>7.3f} | "
              f"{acc(p, yte, known_mask):>8.3f} | {acc(p, yte):>7.3f}")
    print("\n  One integrated brain-like system: learned deep vision (no backprop),")
    print("  plus one-shot learning of a new class with no forgetting.")
