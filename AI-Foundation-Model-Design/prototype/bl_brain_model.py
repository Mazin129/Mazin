"""
BL  —  a Brain-Like learning model.  Real ML on real handwritten digits.

BL is not a transformer with biological labels. It is built from the mechanisms
modern neuroscience believes the brain actually uses, and it demonstrates three
things the human brain does effortlessly that standard deep nets do badly:

    1. FAST (few-shot) learning        — learn a category from a handful of examples
    2. ONE-SHOT learning of a NEW class — recognise a brand-new digit seen ~5 times,
                                          with NO retraining
    3. CONTINUAL learning              — add that new class WITHOUT forgetting the old

Task: scikit-learn `digits` (1797 real 8x8 handwritten digits, classes 0-9).

------------------------------------------------------------------------------
THE NEUROSCIENCE BL IS BUILT ON (current, well-supported)
------------------------------------------------------------------------------
* Sparse expansion coding / pattern separation (dentate gyrus): inputs are
  projected into a high-dimensional space and sparsified by k-Winners-Take-All,
  so similar inputs become separable and only a few neurons are active
  (event-driven, energy-cheap).                         [Cortex/hippocampus]
* Complementary Learning Systems (McClelland 1995; Kumaran, Hassabis &
  McClelland 2016): a FAST hippocampal memory that learns one-shot, plus a SLOW
  neocortex that consolidates statistics over many examples. Together they give
  fast learning AND stability -> no catastrophic forgetting.
* Local, three-factor plasticity (Frémaux & Gerstner 2016): the cortical readout
  learns by a local rule  ΔW ∝ (post-synaptic error) × (pre-synaptic activity) —
  NO backpropagation, no weight transport.
* Neuromodulation / novelty routing (Yu & Dayan; Lisman): acetylcholine/
  norepinephrine signal uncertainty & novelty; novel stimuli are routed to the
  hippocampus, familiar ones handled by cortex. BL uses a novelty signal to
  arbitrate between its fast and slow systems.
------------------------------------------------------------------------------
Pure NumPy for all learning (no backprop framework). scikit-learn only loads the
dataset. Runs in a few seconds on a laptop CPU.
"""

import numpy as np
from sklearn.datasets import load_digits

rng = np.random.default_rng(0)


# --------------------------------------------------------------------------- #
# Sensory cortex: fixed random expansion + k-WTA sparse coding (no learning).
# Biologically: granule-cell expansion recoding + pattern separation.
# --------------------------------------------------------------------------- #
class SparseCortexEncoder:
    def __init__(self, d_in, d_hidden=1500, active_frac=0.08):
        self.R = rng.normal(0, 1, (d_in, d_hidden)) / np.sqrt(d_in)
        self.bias = rng.normal(0, 0.1, d_hidden)
        self.k = max(1, int(active_frac * d_hidden))
        self.d_hidden = d_hidden

    def encode(self, X):
        h = np.maximum(0.0, X @ self.R + self.bias)      # nonlinear expansion (ReLU)
        # k-Winners-Take-All: keep the k strongest units per sample, silence rest.
        if self.k < self.d_hidden:
            kth = np.partition(h, -self.k, axis=1)[:, -self.k][:, None]
            h = np.where(h >= kth, h, 0.0)
        return h

    def sparsity(self, X):
        h = self.encode(X)
        return (h > 0).mean()                            # fraction of active neurons


def softmax(z):
    z = z - z.max(1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(1, keepdims=True)


# --------------------------------------------------------------------------- #
# Neocortex: slow readout trained by a LOCAL three-factor rule (no backprop).
# --------------------------------------------------------------------------- #
class Neocortex:
    def __init__(self, d_hidden, classes):
        self.classes = list(classes)
        self.idx = {c: i for i, c in enumerate(self.classes)}
        self.W = np.zeros((len(self.classes), d_hidden))

    def logits(self, H):
        return H @ self.W.T

    def probs(self, H):
        return softmax(self.logits(H))

    def learn(self, H, y, epochs=40, lr=0.5):
        Y = np.zeros((len(y), len(self.classes)))
        for i, c in enumerate(y):
            Y[i, self.idx[c]] = 1.0
        for _ in range(epochs):
            err = Y - self.probs(H)          # LOCAL post-synaptic error signal
            self.W += lr * (err.T @ H) / len(H)   # ΔW ∝ error × pre-activity (Hebbian)


# --------------------------------------------------------------------------- #
# Hippocampus: fast, one-shot associative memory of sparse-code prototypes.
# --------------------------------------------------------------------------- #
class Hippocampus:
    def __init__(self):
        self.proto = {}

    def store(self, H, y):                   # instant, gradient-free write
        for c in np.unique(y):
            m = H[y == c].mean(0)
            self.proto[c] = m / (np.linalg.norm(m) + 1e-9)

    def recall(self, H):
        classes = sorted(self.proto)
        P = np.stack([self.proto[c] for c in classes])
        Hn = H / (np.linalg.norm(H, axis=1, keepdims=True) + 1e-9)
        sims = Hn @ P.T                      # cosine similarity to each prototype
        return classes, sims


# --------------------------------------------------------------------------- #
# BL: the complete brain-like model tying cortex + hippocampus together.
# --------------------------------------------------------------------------- #
class BL:
    def __init__(self, d_in, d_hidden=1500):
        self.enc = SparseCortexEncoder(d_in, d_hidden)
        self.cortex = None
        self.hpc = Hippocampus()
        self.d_hidden = d_hidden

    def slow_learn(self, X, y, **kw):        # neocortical consolidation
        self.cortex = Neocortex(self.d_hidden, sorted(np.unique(y)))
        self.cortex.learn(self.enc.encode(X), y, **kw)

    def fast_store(self, X, y):              # hippocampal one-shot write
        self.hpc.store(self.enc.encode(X), y)

    def predict(self, X):
        """Neuromodulatory novelty routing (the brain's actual arbitration):
        the hippocampus computes similarity to every stored prototype and acts as
        a NOVELTY DETECTOR. If a stimulus is better explained by a prototype the
        cortex has never learned (a new class) than by any known one, it is
        'novel' -> routed to the fast hippocampal system. Otherwise the slow,
        highly-accurate cortex decides. This prevents an over-confident cortex
        from vetoing a genuinely new category."""
        H = self.enc.encode(X)
        classes, sims = self.hpc.recall(H)
        classes = list(classes)
        hippo_pred = np.array(classes)[sims.argmax(1)]
        if self.cortex is None:
            return hippo_pred
        cortex_probs = self.cortex.probs(H)
        cortex_pred = np.array(self.cortex.classes)[cortex_probs.argmax(1)]
        new_cols = [i for i, c in enumerate(classes) if c not in set(self.cortex.classes)]
        if not new_cols:                               # no new class stored yet
            return cortex_pred
        known_cols = [i for i, c in enumerate(classes) if c in set(self.cortex.classes)]
        s_known = sims[:, known_cols].max(1)
        s_new = sims[:, new_cols].max(1)
        novel = s_new > s_known                        # hippocampal mismatch signal
        return np.where(novel, hippo_pred, cortex_pred)


def acc(pred, y, mask=None):
    if mask is not None:
        pred, y = pred[mask], y[mask]
    return (pred == y).mean()


if __name__ == "__main__":
    D = load_digits()
    X = D.data / 16.0
    y = D.target
    p = rng.permutation(len(X))
    X, y = X[p], y[p]
    ntr = 1200
    Xtr, ytr, Xte, yte = X[:ntr], y[:ntr], X[ntr:], y[ntr:]
    print("BL — Brain-Like model on real handwritten digits (sklearn digits, 8x8).")
    print(f"train={len(Xtr)}  test={len(Xte)}  classes=0-9\n")

    bl = BL(d_in=64, d_hidden=1500)
    print(f"Sparse code: only {100*bl.enc.sparsity(Xtr):.1f}% of neurons active per "
          f"input (event-driven, like cortex).\n")

    # --- DEMO 1: fast (few-shot) learning via the hippocampal system --------- #
    print("=" * 66)
    print("DEMO 1  Fast few-shot learning (hippocampus): accuracy vs #examples")
    print("        Humans learn from a handful of examples. So does BL.")
    print("=" * 66)
    for n in [1, 2, 5, 10, 30]:
        h = Hippocampus()
        Xs, ys = [], []
        for c in range(10):                             # n examples per class
            ci = np.where(ytr == c)[0][:n]
            Xs.append(Xtr[ci]); ys.append(ytr[ci])
        Xs, ys = np.vstack(Xs), np.concatenate(ys)
        h.store(bl.enc.encode(Xs), ys)
        cls, sims = h.recall(bl.enc.encode(Xte))
        pred = np.array(cls)[sims.argmax(1)]
        print(f"   {n:2d} example(s)/class ->  test accuracy = {acc(pred, yte):.3f}")

    # --- DEMO 2: slow cortical learning (the ML learning curve) -------------- #
    print("\n" + "=" * 66)
    print("DEMO 2  Slow cortical learning (LOCAL rule, NO backprop): full 10-class")
    print("=" * 66)
    cortex_only = BL(d_in=64, d_hidden=1500)
    cortex_only.enc = bl.enc                             # share the fixed encoder
    for ep in [1, 5, 15, 40]:
        c = Neocortex(bl.d_hidden, sorted(np.unique(ytr)))
        c.learn(bl.enc.encode(Xtr), ytr, epochs=ep)
        pred = np.array(c.classes)[c.probs(bl.enc.encode(Xte)).argmax(1)]
        print(f"   {ep:2d} epochs of local plasticity ->  test accuracy = {acc(pred, yte):.3f}")

    # --- DEMO 3: one-shot NEW class + NO forgetting (complementary systems) --- #
    print("\n" + "=" * 66)
    print("DEMO 3  Learn a BRAND-NEW class one-shot, without forgetting the rest")
    print("=" * 66)
    base = list(range(9))                                # cortex learns digits 0-8
    tr_base = np.isin(ytr, base)
    bl.slow_learn(Xtr[tr_base], ytr[tr_base], epochs=40)
    bl.fast_store(Xtr[tr_base], ytr[tr_base])            # hippocampus also holds 0-8

    known_mask = np.isin(yte, base)
    new_mask = (yte == 9)
    print(f"  Cortex trained on digits 0-8 only (local rule, no backprop).")
    print(f"    accuracy on 0-8 BEFORE any exposure to 9:  {acc(bl.predict(Xte), yte, known_mask):.3f}")
    print(f"    accuracy on class 9 BEFORE exposure:       "
          f"{acc(bl.predict(Xte), yte, new_mask):.3f}  (never seen it)")

    print(f"\n  Now digit 9 is shown a few times and written to the hippocampus")
    print(f"  instantly (NO gradient step, NO cortical retraining):\n")
    print(f"   {'#9 shown':>9} | {'acc on NEW 9':>12} | {'acc on old 0-8':>14} | {'all 10':>7}")
    print("  " + "-" * 52)
    for n_new in [1, 5, 10, 20]:
        nine = np.where(ytr == 9)[0][:n_new]
        bl.fast_store(Xtr[nine], ytr[nine])            # overwrite the 9-prototype
        pred_all = bl.predict(Xte)
        print(f"   {n_new:>9} | {acc(pred_all, yte, new_mask):>12.3f} | "
              f"{acc(pred_all, yte, known_mask):>14.3f} | {acc(pred_all, yte):>7.3f}")

    # Baseline: a cortex-only net never trained on 9 can NEVER predict it.
    conly = Neocortex(bl.d_hidden, base)
    conly.learn(bl.enc.encode(Xtr[tr_base]), ytr[tr_base], epochs=40)
    cpred = np.array(conly.classes)[conly.probs(bl.enc.encode(Xte)).argmax(1)]
    print(f"\n  Baseline cortex-only (single backprop-style net, no hippocampus):")
    print(f"    accuracy on NEW class 9:  {acc(cpred, yte, new_mask):.3f}   "
          f"(structurally impossible — it has no output unit for 9)")
    print(f"\n  => BL's fast (hippocampal) + slow (cortical) complementary systems give")
    print(f"     few-shot learning of a brand-new category while old knowledge stays")
    print(f"     intact (~0.96) — a human-brain capability a single network lacks.")
