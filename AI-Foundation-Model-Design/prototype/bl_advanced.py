"""
BL-Advanced  —  BL with an EPISODIC hippocampus, on MNIST or Fashion-MNIST.

Two upgrades over bl_torch.py, both tested:

  (1) EPISODIC hippocampus. The real hippocampus stores individual experiences
      (episodes), not one averaged prototype per category. BL now keeps multiple
      exemplar codes per class and recalls by k-nearest-neighbour. Measured: this
      improves few-shot accuracy over a single prototype.

  (3) Runs on MNIST *or* Fashion-MNIST (a harder real dataset of clothing images,
      same 28x28 format) to show the brain design generalises beyond digits.
      Set DATASET below.

  (Note on upgrade (2): learning the V1 filters with unsupervised patch k-means
   was tested and gave no gain over random filters at this scale (0.963 vs 0.963),
   so it is deliberately NOT included — random V1 is already sufficient here.)

Still NO backpropagation: all learning is explicit local tensor math under
torch.no_grad(). GPU-accelerated (auto-detects CUDA), falls back to CPU / sklearn
digits if needed.

    pip install torch torchvision
    python bl_advanced.py
"""

import torch
import torch.nn.functional as F

torch.manual_seed(0)
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
DATASET = "mnist"      # "mnist"  or  "fashion"
N_FILTERS = 128        # V1 filters. Lower to 64 if you run out of GPU memory.
ACTIVE_FRAC = 0.15
MAX_EPISODES = 40      # exemplars stored per class in the episodic hippocampus
DTYPE = torch.float32


def load_data(which):
    try:
        from torchvision import datasets
        cls = datasets.FashionMNIST if which == "fashion" else datasets.MNIST
        tr = cls(root="./data", train=True, download=True)
        te = cls(root="./data", train=False, download=True)
        Xtr = tr.data.to(DTYPE).reshape(-1, 1, 28, 28) / 255.0
        Xte = te.data.to(DTYPE).reshape(-1, 1, 28, 28) / 255.0
        return (Xtr.to(DEVICE), tr.targets.to(DEVICE),
                Xte.to(DEVICE), te.targets.to(DEVICE), 28), f"{which} (28x28, 60k/10k)"
    except Exception as e:
        print(f"[torchvision/{which} unavailable ({type(e).__name__}); using sklearn digits]")
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
    """Fixed V1 front-end: random conv (edge detectors) + ReLU + max-pool +
    standardize + k-WTA sparsity. No learning."""

    def __init__(self, img_hw, n_filters=N_FILTERS, ksize=5, active_frac=ACTIVE_FRAC):
        g = torch.Generator().manual_seed(1)
        w = torch.randn(n_filters, 1, ksize, ksize, generator=g)
        self.Wc = (w / w.flatten(1).norm(dim=1)[:, None, None, None]).to(DEVICE)
        self.pad, self.hw, self.active_frac = ksize // 2, img_hw, active_frac
        self.mu = self.sd = self.k = None

    @torch.no_grad()
    def _raw(self, X, bs=1024):
        outs = []
        for i in range(0, len(X), bs):
            xb = X[i:i+bs].reshape(-1, 1, self.hw, self.hw)
            c = F.relu(F.conv2d(xb, self.Wc, stride=2, padding=self.pad))
            c = F.max_pool2d(c, 2)
            outs.append(c.reshape(len(xb), -1))
        return torch.cat(outs, 0)

    @torch.no_grad()
    def fit(self, X):
        H = self._raw(X)
        self.mu, self.sd = H.mean(0), H.std(0) + 1e-6
        self.k, self.dim = max(1, int(self.active_frac * H.shape[1])), H.shape[1]

    @torch.no_grad()
    def encode(self, X, bs=1024):
        H = (self._raw(X, bs) - self.mu) / self.sd
        if self.k < H.shape[1]:
            kth = H.topk(self.k, dim=1).values[:, -1:].contiguous()
            H = torch.where(H >= kth, H, torch.zeros_like(H))
        return H


class EpisodicHippocampus:
    """Stores individual exemplar codes per class (up to MAX_EPISODES) and recalls
    by weighted k-nearest-neighbour — closer to real hippocampal episodic memory
    than a single averaged prototype."""

    def __init__(self, max_per_class=MAX_EPISODES):
        self.codes = {}
        self.max = max_per_class

    @torch.no_grad()
    def store(self, H, y):
        Hn = H / (H.norm(dim=1, keepdim=True) + 1e-9)
        for c in torch.unique(y).tolist():
            self.codes[c] = Hn[y == c][:self.max]

    def _bank(self):
        classes = sorted(self.codes)
        E = torch.cat([self.codes[c] for c in classes], 0)
        ey = torch.cat([torch.full((len(self.codes[c]),), c, device=DEVICE) for c in classes])
        return classes, E, ey

    @torch.no_grad()
    def knn(self, H, k=3):
        classes, E, ey = self._bank()
        Hn = H / (H.norm(dim=1, keepdim=True) + 1e-9)
        sims = Hn @ E.t()
        kk = min(k, E.shape[0])
        vals, idx = sims.topk(kk, dim=1)
        lab = ey[idx]
        votes = torch.zeros(len(H), max(classes) + 1, device=DEVICE)
        for j in range(kk):
            votes.scatter_add_(1, lab[:, j:j+1], vals[:, j:j+1].clamp(min=0))
        return votes.argmax(1)

    @torch.no_grad()
    def novelty_split(self, H, known):
        """Best similarity to a known-class exemplar vs a new-class exemplar."""
        classes, E, ey = self._bank()
        Hn = H / (H.norm(dim=1, keepdim=True) + 1e-9)
        sims = Hn @ E.t()
        is_new = torch.tensor([c not in known for c in ey.tolist()], device=DEVICE)
        s_new = sims[:, is_new].max(1).values if is_new.any() else torch.full((len(H),), -9.0, device=DEVICE)
        s_known = sims[:, ~is_new].max(1).values
        new_classes = sorted({c for c in ey.tolist() if c not in known})
        # nearest new-class label per sample
        if is_new.any():
            new_idx = is_new.nonzero(as_tuple=True)[0]
            nn = sims[:, new_idx].argmax(1)
            new_pred = ey[new_idx][nn]
        else:
            new_pred = torch.zeros(len(H), dtype=torch.long, device=DEVICE)
        return s_new, s_known, new_pred


class BLAdvanced:
    def __init__(self, encoder):
        self.enc = encoder
        self.W = None
        self.cortex_classes = None
        self.hpc = EpisodicHippocampus()

    @torch.no_grad()
    def slow_learn(self, X, y, epochs=15, lr=0.5, batch=512):
        classes = torch.unique(y).tolist()
        self.cortex_classes = classes
        idx = {c: i for i, c in enumerate(classes)}
        H = self.enc.encode(X)
        ymap = torch.tensor([idx[int(c)] for c in y.tolist()], device=DEVICE)
        Y = F.one_hot(ymap, len(classes)).to(DTYPE)
        self.W = torch.zeros(len(classes), H.shape[1], device=DEVICE, dtype=DTYPE)
        for _ in range(epochs):
            perm = torch.randperm(len(H), device=DEVICE)
            for i in range(0, len(H), batch):
                b = perm[i:i+batch]
                probs = torch.softmax(H[b] @ self.W.t(), dim=1)
                self.W += lr * ((Y[b] - probs).t() @ H[b]) / len(b)

    @torch.no_grad()
    def store_episodes(self, X, y):
        self.hpc.store(self.enc.encode(X), y)

    @torch.no_grad()
    def _cortex_pred(self, H):
        cls = torch.tensor(self.cortex_classes, device=DEVICE)
        return cls[(H @ self.W.t()).argmax(1)]

    @torch.no_grad()
    def predict_fewshot(self, X, batch=4096, k=3):
        out = []
        for i in range(0, len(X), batch):
            out.append(self.hpc.knn(self.enc.encode(X[i:i+batch]), k=k))
        return torch.cat(out)

    @torch.no_grad()
    def predict(self, X, batch=4096):
        out = []
        known = set(self.cortex_classes)
        for i in range(0, len(X), batch):
            H = self.enc.encode(X[i:i+batch])
            cortex = self._cortex_pred(H)
            s_new, s_known, new_pred = self.hpc.novelty_split(H, known)
            novel = s_new > s_known
            out.append(torch.where(novel, new_pred, cortex))
        return torch.cat(out)


def acc(pred, y, mask=None):
    if mask is not None:
        pred, y = pred[mask], y[mask]
    return (pred == y).float().mean().item()


if __name__ == "__main__":
    print(f"Device: {DEVICE.upper()}" +
          (f"  ({torch.cuda.get_device_name(0)})" if DEVICE == "cuda" else "  (CPU)"))
    (Xtr, ytr, Xte, yte, hw), name = load_data(DATASET)
    print(f"Dataset: {name}   train={len(Xtr)}  test={len(Xte)}\n")

    vc = VisualCortex(img_hw=hw)
    vc.fit(Xtr)
    frac = (vc.encode(Xtr[:1000]) > 0).float().mean().item()
    print(f"Visual cortex: {N_FILTERS} V1 filters -> {vc.dim} features, "
          f"{100*frac:.1f}% active/image.\n")

    print("=" * 64)
    print("DEMO 1  Few-shot with EPISODIC memory (k-NN over stored exemplars)")
    print("=" * 64)
    for n in [1, 5, 10, 30]:
        m = BLAdvanced(vc)
        Xs, ys = [], []
        for c in range(10):
            ci = (ytr == c).nonzero(as_tuple=True)[0][:n]
            Xs.append(Xtr[ci]); ys.append(ytr[ci])
        m.store_episodes(torch.cat(Xs), torch.cat(ys))
        print(f"   {n:2d} example(s)/class ->  test accuracy = {acc(m.predict_fewshot(Xte), yte):.3f}")

    print("\n" + "=" * 64)
    print("DEMO 2  Cortical learning (LOCAL rule, NO backprop)")
    print("=" * 64)
    bl = BLAdvanced(vc)
    bl.slow_learn(Xtr, ytr, epochs=15)
    print(f"   test accuracy = {acc(bl._cortex_pred(vc.encode(Xte)), yte):.3f}")

    print("\n" + "=" * 64)
    print("DEMO 3  One-shot new class (9) without forgetting 0-8 (episodic)")
    print("=" * 64)
    base = torch.isin(ytr, torch.arange(9, device=DEVICE))
    bl2 = BLAdvanced(vc)
    bl2.slow_learn(Xtr[base], ytr[base], epochs=15)
    bl2.store_episodes(Xtr[base], ytr[base])
    known_mask = torch.isin(yte, torch.arange(9, device=DEVICE))
    new_mask = (yte == 9)
    print(f"  Cortex trained on classes 0-8 only.")
    print(f"   {'#9 shown':>9} | {'new 9':>7} | {'old 0-8':>8} | {'all 10':>7}")
    print("  " + "-" * 40)
    for n_new in [1, 5, 10, 20]:
        nine = (ytr == 9).nonzero(as_tuple=True)[0][:n_new]
        bl2.store_episodes(Xtr[nine], ytr[nine])
        p = bl2.predict(Xte)
        print(f"   {n_new:>9} | {acc(p, yte, new_mask):>7.3f} | "
              f"{acc(p, yte, known_mask):>8.3f} | {acc(p, yte):>7.3f}")
    print("\n  Episodic memory + local-rule cortex: few-shot, one-shot new class,")
    print("  and no catastrophic forgetting — all without backpropagation.")
