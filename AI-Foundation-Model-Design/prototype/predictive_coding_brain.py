"""
Brain-native learning: a Predictive-Coding network (pure NumPy).

The single deepest difference between the brain and today's AI is HOW they learn.
Deep nets use backpropagation: a global backward pass that carries the exact
gradient of a single scalar loss backward through every layer. That is
biologically impossible -- real synapses have no access to a global error signal
or to the transpose of downstream weights ("the weight-transport problem").

The brain instead is believed to run PREDICTIVE CODING (Rao & Ballard 1999;
Friston's Free-Energy Principle): every cortical area predicts the activity of
the area below it; only the PREDICTION ERROR is transmitted; the system settles
into a state of minimum error ("free energy"), and synapses then change using
ONLY locally available signals (the local error and the local activity) --
a Hebbian rule. No backward pass. No weight transport.

Remarkably, this local scheme approximates backprop's gradients
(Whittington & Bogacz 2017). This script demonstrates that on a nonlinear
task: predictive coding learns with LOCAL updates only, and matches a
backprop-trained network of identical size.

------------------------------------------------------------------------------
THE PHYSICS / MATH
------------------------------------------------------------------------------
Activities x[0..L] (x[0]=input, x[L]=label). Each layer top-down predicts the
one below:
        pred[l-1] = tanh(x[l]) @ W[l].T + b[l]
        err[l-1]  = x[l-1] - pred[l-1]
Free energy (Gaussian generative model, unit variance):
        F = 0.5 * sum_l || err[l] ||^2
INFERENCE (fast dynamics, "perception"): relax free activities down F's gradient
        dx[l] = -( err[l] - tanh'(x[l]) ⊙ (err[l-1] @ W[l]) )
LEARNING (slow, "plasticity"): after settling, each synapse uses only the error
on its post-synaptic side and the activity on its pre-synaptic side -- LOCAL:
        ΔW[l] ∝ err[l-1]^T @ tanh(x[l])          Δb[l] ∝ mean(err[l-1])
Everything a synapse needs is physically present at that synapse. That is the
whole point.
------------------------------------------------------------------------------
"""

import numpy as np

rng = np.random.default_rng(0)


def make_circles(n):
    """Two nonlinearly-separable classes: an inner disk vs an outer ring.
    Not linearly separable -> requires real hidden nonlinearity to solve."""
    n2 = n // 2
    r_in = 0.6 * np.sqrt(rng.random(n2))
    r_out = 1.4 + 0.6 * np.sqrt(rng.random(n2))
    th = 2 * np.pi * rng.random(n)
    r = np.concatenate([r_in, r_out])
    X = np.stack([r * np.cos(th), r * np.sin(th)], axis=1)
    X += 0.05 * rng.standard_normal(X.shape)
    y = np.concatenate([np.zeros(n2, int), np.ones(n - n2, int)])
    Y = np.eye(2)[y] * 2.0 - 1.0          # one-hot in {-1,+1}
    idx = rng.permutation(n)
    return X[idx].astype(np.float64), Y[idx], y[idx]


def tanh(z):
    return np.tanh(z)


def dtanh(z):
    return 1.0 - np.tanh(z) ** 2


# --------------------------------------------------------------------------- #
# Predictive-coding network: local learning, no backprop.
# --------------------------------------------------------------------------- #
class PredictiveCoding:
    """Discriminative predictive coding (Song et al. 2020; Whittington & Bogacz
    2017) -- the formulation proven to approximate backprop's gradients using
    only LOCAL updates. Feedforward predictions mu[l] = f(x[l-1]) W[l]; the
    error nodes err[l] = x[l] - mu[l] are the only signals that travel; during
    learning the hidden activities relax to minimize free energy and then every
    synapse updates from its local pre-activity and local post-error."""

    def __init__(self, sizes, lr=0.1, infer_steps=30, infer_lr=0.2):
        self.sizes = sizes
        self.L = len(sizes) - 1
        self.lr, self.infer_steps, self.infer_lr = lr, infer_steps, infer_lr
        self.W = [None] + [rng.normal(0, 1/np.sqrt(sizes[l-1]), (sizes[l-1], sizes[l]))
                           for l in range(1, self.L + 1)]
        self.b = [None] + [np.zeros(sizes[l]) for l in range(1, self.L + 1)]

    def _feedforward(self, X):
        x = [X]
        for l in range(1, self.L + 1):
            x.append(tanh(x[-1]) @ self.W[l] + self.b[l])
        return x

    def _errors(self, x):
        err = [None] * (self.L + 1)        # err[1..L]
        for l in range(1, self.L + 1):
            err[l] = x[l] - (tanh(x[l-1]) @ self.W[l] + self.b[l])
        return err

    def infer(self, x, log_F=False):
        """Relax hidden activities x[1..L-1] to minimize free energy.
        x[0] (input) and x[L] (label) stay clamped."""
        B = x[0].shape[0]
        Fs = []
        for _ in range(self.infer_steps):
            err = self._errors(x)
            for l in range(1, self.L):                       # hidden layers only
                grad = err[l] - dtanh(x[l]) * (err[l+1] @ self.W[l+1].T)
                x[l] = x[l] - self.infer_lr * grad
            if log_F:
                Fs.append(0.5 * sum(np.sum(err[l]**2) for l in range(1, self.L+1)) / B)
        return x, Fs

    def train_epoch(self, X, Y, batch=64):
        order = rng.permutation(len(X))
        for i in range(0, len(X), batch):
            bi = order[i:i+batch]
            x = self._feedforward(X[bi])                     # amortized warm-start
            x[self.L] = Y[bi].copy()                          # clamp the label
            x, _ = self.infer(x)
            err = self._errors(x)
            for l in range(1, self.L + 1):                   # LOCAL plasticity
                self.W[l] += self.lr * (tanh(x[l-1]).T @ err[l]) / len(bi)
                self.b[l] += self.lr * err[l].mean(0)

    def predict(self, X):
        return self._feedforward(X)[self.L].argmax(1)        # pure feedforward read

    def free_energy_trace(self, X, Y):
        x = self._feedforward(X)
        x[self.L] = Y.copy()
        _, Fs = self.infer(x, log_F=True)
        return Fs


# --------------------------------------------------------------------------- #
# Backprop MLP baseline (identical architecture), for a fair comparison.
# --------------------------------------------------------------------------- #
class BackpropMLP:
    def __init__(self, sizes, lr=0.05):
        self.sizes, self.lr = sizes, lr
        self.W = [rng.normal(0, 1/np.sqrt(sizes[l]), (sizes[l], sizes[l+1]))
                  for l in range(len(sizes)-1)]
        self.b = [np.zeros(sizes[l+1]) for l in range(len(sizes)-1)]

    def forward(self, X):
        a = [X]; z = []
        for l in range(len(self.W)):
            zz = a[-1] @ self.W[l] + self.b[l]; z.append(zz)
            a.append(tanh(zz))
        return a, z

    def train_epoch(self, X, Y, batch=64):
        order = rng.permutation(len(X))
        for i in range(0, len(X), batch):
            bi = order[i:i+batch]; a, z = self.forward(X[bi])
            d = (a[-1] - Y[bi]) * dtanh(z[-1])        # GLOBAL backward pass:
            for l in reversed(range(len(self.W))):
                gW = a[l].T @ d / len(bi); gb = d.mean(0)
                if l > 0:
                    d = (d @ self.W[l].T) * dtanh(z[l-1])  # needs W[l].T (weight transport)
                self.W[l] -= self.lr * gW; self.b[l] -= self.lr * gb

    def predict(self, X):
        a, _ = self.forward(X); return a[-1].argmax(1)


if __name__ == "__main__":
    Xtr, Ytr, ytr = make_circles(1000)
    Xte, Yte, yte = make_circles(400)
    sizes = [2, 32, 32, 2]
    print(f"Task: inner-disk vs outer-ring (nonlinear). Architecture {sizes}.")
    print("Chance accuracy = 50%.\n")

    print("Training PREDICTIVE CODING (local learning, NO backprop):")
    pc = PredictiveCoding(sizes)
    for ep in range(60):
        pc.train_epoch(Xtr, Ytr)
        if ep % 10 == 0 or ep == 59:
            acc = (pc.predict(Xte) == yte).mean()
            print(f"  epoch {ep:2d}  test_acc = {acc:.3f}")

    print("\nTraining BACKPROP MLP (same size, global backward pass):")
    mlp = BackpropMLP(sizes)
    for ep in range(60):
        mlp.train_epoch(Xtr, Ytr)
        if ep % 10 == 0 or ep == 59:
            acc = (mlp.predict(Xte) == yte).mean()
            print(f"  epoch {ep:2d}  test_acc = {acc:.3f}")

    print("\n" + "=" * 60)
    print("FREE-ENERGY DESCENT during a single perception (inference):")
    print("F should fall monotonically as the network 'settles' -- the")
    print("physics of perception as energy minimization.")
    print("=" * 60)
    Fs = pc.free_energy_trace(Xte[:64], Yte[:64])
    for t in [0, 2, 5, 10, len(Fs) - 1]:
        print(f"  inference step {t:2d}  free_energy F = {Fs[t]:.4f}")
    print(f"\n  F reduced {Fs[0]/max(Fs[-1],1e-9):.1f}x from settling.")
