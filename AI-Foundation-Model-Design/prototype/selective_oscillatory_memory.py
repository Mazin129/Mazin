"""
Selective Oscillatory Memory (SOM) — a physics-grounded sequence mixer.

Pure NumPy. No deep-learning framework. Forward AND backprop are hand-derived,
so every gradient in the mechanism is explicit. Runs on any laptop CPU.

------------------------------------------------------------------------------
THE PHYSICS
------------------------------------------------------------------------------
Model the hidden state as a network of d coupled, damped, driven nonlinear
oscillators. Newton's second law (unit mass) for position y and velocity z:

        y'' = tanh(W y + V u + b)  -  gamma * y  -  alpha * y'
        (nonlinear coupling/drive)   (restoring)     (damping)

Write as a first-order system with velocity z = y' and integrate with a
SYMPLECTIC (semi-implicit) Euler scheme — update momentum first, then position:

        z_t = z_{t-1} + dt * ( tanh(W y_{t-1} + V u_t + b) - gamma*y_{t-1} - alpha*z_{t-1} )
        y_t = y_{t-1} + dt * z_t

WHY IT MATTERS FOR AN AI LANGUAGE MODEL
    For an undamped oscillator the discrete flow is (near) energy-preserving, so
    the state-transition Jacobian has eigenvalues near the unit circle. Hence
    || d y_T / d y_t || stays ~O(1) across ARBITRARILY long t: gradients neither
    vanish nor explode. That bounded-gradient property is exactly the mechanism
    a language model needs for stable long-range memory, and it is provable
    (Rusch & Mishra 2020/2021). A vanilla tanh-RNN's Jacobian norm decays
    geometrically -> long-range gradients vanish -> it cannot remember.

This script demonstrates the property empirically: it trains SOM and a vanilla
RNN on the long-range "adding problem" and probes || d y_t || across time.
------------------------------------------------------------------------------
"""

import numpy as np

rng = np.random.default_rng(0)


# --------------------------------------------------------------------------- #
# Task: the classic long-range "adding problem".
# Input at each step is 2 features: [random value in (0,1), marker in {0,1}].
# Exactly two positions have marker=1. Target = sum of the two marked values.
# Solving it requires carrying information across the full sequence length T.
# A constant predictor gets MSE ~= Var(sum of two U(0,1)) = 2/12 ~= 0.167.
# --------------------------------------------------------------------------- #
def make_batch(B, T):
    values = rng.random((B, T))
    markers = np.zeros((B, T))
    targets = np.zeros(B)
    for i in range(B):
        j, k = rng.choice(T, size=2, replace=False)
        markers[i, j] = 1.0
        markers[i, k] = 1.0
        targets[i] = values[i, j] + values[i, k]
    u = np.stack([values, markers], axis=-1)  # (B, T, 2)
    return u.astype(np.float64), targets.astype(np.float64)


def make_memory(B, T):
    """PURE long-range MEMORY task (isolates what the oscillator physics buys).
    A payload value ~U(-1,1) appears ONLY at t=0 (channel 0); channel 1 is
    random distractor noise at every step. Target = the payload. The model must
    carry step-0 information across all T steps. A forgetful model predicts the
    mean -> MSE ~= Var(U(-1,1)) = 1/3 ~= 0.333."""
    u = np.zeros((B, T, 2))
    payload = rng.uniform(-1, 1, B)
    u[:, 0, 0] = payload
    u[:, :, 1] = rng.uniform(-1, 1, (B, T))
    return u.astype(np.float64), payload.astype(np.float64)


class Adam:
    def __init__(self, params, lr=3e-3):
        self.lr = lr
        self.m = {k: np.zeros_like(v) for k, v in params.items()}
        self.v = {k: np.zeros_like(v) for k, v in params.items()}
        self.t = 0

    def step(self, params, grads):
        self.t += 1
        for k in params:
            g = grads[k]
            self.m[k] = 0.9 * self.m[k] + 0.1 * g
            self.v[k] = 0.999 * self.v[k] + 0.001 * (g * g)
            mhat = self.m[k] / (1 - 0.9 ** self.t)
            vhat = self.v[k] / (1 - 0.999 ** self.t)
            params[k] -= self.lr * mhat / (np.sqrt(vhat) + 1e-8)


# --------------------------------------------------------------------------- #
# Selective Oscillatory Memory layer + scalar readout, with analytic BPTT.
# --------------------------------------------------------------------------- #
class OscillatoryModel:
    def __init__(self, d=64, m=2, dt=0.1, gamma=1.0, alpha=0.1):
        s = 1.0 / np.sqrt(d)
        self.p = {
            "W": rng.normal(0, s, (d, d)),
            "V": rng.normal(0, s, (d, m)),
            "b": np.zeros(d),
            "wout": rng.normal(0, s, d),
            "bout": np.zeros(1),
        }
        self.d, self.dt, self.gamma, self.alpha = d, dt, gamma, alpha

    def forward(self, u, keep_cache=True):
        B, T, _ = u.shape
        d, dt, g, a = self.d, self.dt, self.gamma, self.alpha
        W, V, b = self.p["W"], self.p["V"], self.p["b"]
        y = np.zeros((B, d))
        z = np.zeros((B, d))
        cache = []
        for t in range(T):
            y_prev, z_prev = y, z
            pre = y_prev @ W.T + u[:, t] @ V.T + b
            s = np.tanh(pre)
            z = z_prev + dt * (s - g * y_prev - a * z_prev)
            y = y_prev + dt * z
            if keep_cache:
                cache.append((y_prev, z_prev, s, u[:, t]))
        yhat = y @ self.p["wout"] + self.p["bout"]
        return yhat, (y, cache)

    def loss_and_grads(self, u, target):
        B, T, _ = u.shape
        d, dt, g, a = self.d, self.dt, self.gamma, self.alpha
        W = self.p["W"]
        yhat, (yT, cache) = self.forward(u)
        err = yhat - target
        loss = 0.5 * np.mean(err ** 2)

        grads = {k: np.zeros_like(v) for k, v in self.p.items()}
        dyhat = err / B                       # (B,)
        grads["wout"] += (dyhat[:, None] * yT).sum(0)
        grads["bout"] += dyhat.sum()
        dy = dyhat[:, None] * self.p["wout"]  # (B,d)
        dz = np.zeros((B, d))

        for t in reversed(range(T)):
            y_prev, z_prev, s, u_t = cache[t]
            dz = dz + dt * dy                 # y_t = y_prev + dt*z_t
            ds = dz * dt                       # z_t = z_prev + dt*(s - ...)
            dpre = ds * (1.0 - s ** 2)         # tanh'
            grads["W"] += dpre.T @ y_prev
            grads["V"] += dpre.T @ u_t
            grads["b"] += dpre.sum(0)
            dy_prev = dy + dz * (-dt * g) + dpre @ W
            dz_prev = dz * (1.0 - dt * a)
            dy, dz = dy_prev, dz_prev
        return loss, grads

    def grad_norm_over_time(self, u):
        """Probe: || d(loss surrogate) / d y_t || as a function of t.
        Surrogate = sum of final-state components (isolates temporal transport)."""
        B, T, _ = u.shape
        d, dt, g, a = self.d, self.dt, self.gamma, self.alpha
        W = self.p["W"]
        _, (yT, cache) = self.forward(u)
        dy = np.ones((B, d)) / B
        dz = np.zeros((B, d))
        norms = np.zeros(T)
        for t in reversed(range(T)):
            y_prev, z_prev, s, u_t = cache[t]
            dz = dz + dt * dy
            ds = dz * dt
            dpre = ds * (1.0 - s ** 2)
            dy_prev = dy + dz * (-dt * g) + dpre @ W
            dz_prev = dz * (1.0 - dt * a)
            dy, dz = dy_prev, dz_prev
            norms[t] = np.linalg.norm(dy) + np.linalg.norm(dz)
        return norms


# --------------------------------------------------------------------------- #
# Vanilla tanh-RNN baseline (matched hidden size), analytic BPTT + same probe.
# --------------------------------------------------------------------------- #
class VanillaRNN:
    def __init__(self, d=64, m=2):
        s = 1.0 / np.sqrt(d)
        self.p = {
            "W": rng.normal(0, s, (d, d)),
            "V": rng.normal(0, s, (d, m)),
            "b": np.zeros(d),
            "wout": rng.normal(0, s, d),
            "bout": np.zeros(1),
        }
        self.d = d

    def forward(self, u, keep_cache=True):
        B, T, _ = u.shape
        W, V, b = self.p["W"], self.p["V"], self.p["b"]
        h = np.zeros((B, self.d))
        cache = []
        for t in range(T):
            h_prev = h
            pre = h_prev @ W.T + u[:, t] @ V.T + b
            h = np.tanh(pre)
            if keep_cache:
                cache.append((h_prev, h, u[:, t]))
        yhat = h @ self.p["wout"] + self.p["bout"]
        return yhat, (h, cache)

    def loss_and_grads(self, u, target):
        B, T, _ = u.shape
        W = self.p["W"]
        yhat, (hT, cache) = self.forward(u)
        err = yhat - target
        loss = 0.5 * np.mean(err ** 2)
        grads = {k: np.zeros_like(v) for k, v in self.p.items()}
        dyhat = err / B
        grads["wout"] += (dyhat[:, None] * hT).sum(0)
        grads["bout"] += dyhat.sum()
        dh = dyhat[:, None] * self.p["wout"]
        for t in reversed(range(T)):
            h_prev, h, u_t = cache[t]
            dpre = dh * (1.0 - h ** 2)
            grads["W"] += dpre.T @ h_prev
            grads["V"] += dpre.T @ u_t
            grads["b"] += dpre.sum(0)
            dh = dpre @ W
        return loss, grads

    def grad_norm_over_time(self, u):
        B, T, _ = u.shape
        W = self.p["W"]
        _, (hT, cache) = self.forward(u)
        dh = np.ones((B, self.d)) / B
        norms = np.zeros(T)
        for t in reversed(range(T)):
            h_prev, h, u_t = cache[t]
            dpre = dh * (1.0 - h ** 2)
            dh = dpre @ W
            norms[t] = np.linalg.norm(dh)
        return norms


def train(model, task, T=120, B=64, steps=2500, lr=3e-3, tag=""):
    opt = Adam(model.p, lr=lr)
    hist = []
    for it in range(steps):
        u, y = task(B, T)
        loss, grads = model.loss_and_grads(u, y)
        opt.step(model.p, grads)
        if it % 400 == 0 or it == steps - 1:
            uv, yv = task(512, T)
            vpred, _ = model.forward(uv, keep_cache=False)
            vmse = np.mean((vpred - yv) ** 2)
            hist.append((it, vmse))
            print(f"  [{tag}] step {it:4d}  val_MSE = {vmse:.5f}")
    return hist


if __name__ == "__main__":
    T = 120

    # ================================================================= #
    # EXPERIMENT 1 — end-to-end: pure long-range memory (T=120).
    # This isolates exactly what the oscillator physics guarantees:
    # carrying information across many steps. SOM should solve it; a
    # vanilla RNN, whose gradients to step 0 vanish, should not.
    # ================================================================= #
    print("=" * 62)
    print(f"EXPERIMENT 1  Pure long-range memory task, T = {T}")
    print("Forgetful-baseline MSE ~= 0.333 (predict the mean = 'forgot')")
    print("=" * 62)
    rng = np.random.default_rng(0)
    print("Selective Oscillatory Memory (physics-grounded):")
    som = OscillatoryModel(d=64, dt=0.1, gamma=0.3, alpha=0.05)
    train(som, make_memory, T=T, tag="SOM")
    rng = np.random.default_rng(0)
    print("\nVanilla tanh-RNN (same hidden size):")
    van = VanillaRNN(d=64)
    train(van, make_memory, T=T, tag="RNN")

    # ================================================================= #
    # EXPERIMENT 2 — the mechanism itself: gradient transport probe.
    # ================================================================= #
    print("\n" + "=" * 62)
    print("EXPERIMENT 2  GRADIENT TRANSPORT PROBE: || grad w.r.t. state at step t ||")
    print("(higher/flatter = information from early steps still reaches the")
    print(" loss = long memory. Decaying to ~0 = vanishing gradient.)")
    print("=" * 62)
    u, _ = make_memory(64, T)
    gs = som.grad_norm_over_time(u)
    gv = van.grad_norm_over_time(u)
    print(f"{'step t':>8} | {'SOM (oscillator)':>18} | {'Vanilla RNN':>14}")
    print("-" * 48)
    for t in [0, 10, 30, 60, 90, 119]:
        print(f"{t:>8} | {gs[t]:>18.3e} | {gv[t]:>14.3e}")
    ratio_som = gs[0] / (gs[-1] + 1e-30)
    ratio_van = gv[0] / (gv[-1] + 1e-30)
    print("-" * 48)
    print(f"grad(step 0)/grad(step T) ratio  ->  SOM: {ratio_som:.2e}   RNN: {ratio_van:.2e}")
    print("(ratio near 1 = gradients preserved across time; huge = vanished)")
