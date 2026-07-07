"""
Selective Oscillatory Memory, GATED — adds the input-dependent multiplicative gate
that `selective_oscillatory_memory.py` (RESULTS.md, "Honest limitations") documented
as the missing piece: the oscillator solves long-range MEMORY but not the "adding
problem", which also needs SELECTION (value x marker).

Pure NumPy, hand-derived BPTT (same style/discipline as the base file: no
autodiff framework, every gradient explicit and auditable).

------------------------------------------------------------------------------
THE FIX (blueprint §1.2: "input-dependent Delta giving selective forgetting",
the Mamba-style selective-SSM idea, grafted onto the oscillator)
------------------------------------------------------------------------------
Base cell (unselective):
    z_t = z_{t-1} + dt*( tanh(W y_{t-1} + V u_t + b)              - gamma*y - alpha*z )
Gated cell (this file) -- an input-dependent gate multiplies the drive before it
ever reaches the oscillator state, so irrelevant timesteps cannot perturb memory:
    g_t = sigmoid(Wg u_t + bg)                                     <- learned, input-dependent
    z_t = z_{t-1} + dt*( g_t * tanh(W y_{t-1} + V u_t + b)         - gamma*y - alpha*z )
    y_t = y_{t-1} + dt*z_t

On the adding problem, u_t = [value, marker]. The gate only needs to learn
"open when marker=1" (a linear function of its own input -- trivial for Wg to
represent) to solve the selection half of the task, while the oscillator physics
(unchanged) still supplies the long-range memory half.
------------------------------------------------------------------------------
"""

import numpy as np

rng = np.random.default_rng(0)


def make_batch(B, T):
    """The adding problem: target = sum of the two marker=1 values.
    Forgetful/no-selection baseline MSE ~= Var(sum of two U(0,1)) = 2/12 ~= 0.167."""
    values = rng.random((B, T))
    markers = np.zeros((B, T))
    targets = np.zeros(B)
    for i in range(B):
        j, k = rng.choice(T, size=2, replace=False)
        markers[i, j] = 1.0
        markers[i, k] = 1.0
        targets[i] = values[i, j] + values[i, k]
    u = np.stack([values, markers], axis=-1)
    return u.astype(np.float64), targets.astype(np.float64)


def make_memory(B, T):
    """Regression check: the pure long-range memory task the base file already
    solves (MSE 0.0017). The gate must not break this."""
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


def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


class GatedOscillatoryModel:
    """Same physics-grounded oscillator as the base file, plus a per-timestep
    input-dependent multiplicative gate on the drive (the "selective" half)."""

    def __init__(self, d=64, m=2, dt=0.1, gamma=1.0, alpha=0.1):
        s = 1.0 / np.sqrt(d)
        self.p = {
            "W": rng.normal(0, s, (d, d)),
            "V": rng.normal(0, s, (d, m)),
            "b": np.zeros(d),
            "Wg": rng.normal(0, s, (d, m)),
            "bg": np.zeros(d),
            "wout": rng.normal(0, s, d),
            "bout": np.zeros(1),
        }
        self.d, self.dt, self.gamma, self.alpha = d, dt, gamma, alpha

    def forward(self, u, keep_cache=True):
        B, T, _ = u.shape
        d, dt, gam, alp = self.d, self.dt, self.gamma, self.alpha
        W, V, b, Wg, bg = self.p["W"], self.p["V"], self.p["b"], self.p["Wg"], self.p["bg"]
        y = np.zeros((B, d))
        z = np.zeros((B, d))
        cache = []
        for t in range(T):
            y_prev, z_prev = y, z
            pre = y_prev @ W.T + u[:, t] @ V.T + b
            s = np.tanh(pre)
            gpre = u[:, t] @ Wg.T + bg
            g = sigmoid(gpre)
            drive = g * s
            z = z_prev + dt * (drive - gam * y_prev - alp * z_prev)
            y = y_prev + dt * z
            if keep_cache:
                cache.append((y_prev, z_prev, s, g, u[:, t]))
        yhat = y @ self.p["wout"] + self.p["bout"]
        return yhat, (y, cache)

    def loss_and_grads(self, u, target):
        B, T, _ = u.shape
        d, dt, gam, alp = self.d, self.dt, self.gamma, self.alpha
        W = self.p["W"]
        yhat, (yT, cache) = self.forward(u)
        err = yhat - target
        loss = 0.5 * np.mean(err ** 2)

        grads = {k: np.zeros_like(v) for k, v in self.p.items()}
        dyhat = err / B
        grads["wout"] += (dyhat[:, None] * yT).sum(0)
        grads["bout"] += dyhat.sum()
        dy = dyhat[:, None] * self.p["wout"]
        dz = np.zeros((B, d))

        for t in reversed(range(T)):
            y_prev, z_prev, s, g, u_t = cache[t]
            dz = dz + dt * dy                     # y_t = y_prev + dt*z_t
            ddrive = dz * dt                       # z_t = z_prev + dt*(drive - ...)
            ds = ddrive * g                        # drive = g * s
            dg = ddrive * s
            dpre = ds * (1.0 - s ** 2)             # tanh'
            dgpre = dg * g * (1.0 - g)             # sigmoid'
            grads["W"] += dpre.T @ y_prev
            grads["V"] += dpre.T @ u_t
            grads["b"] += dpre.sum(0)
            grads["Wg"] += dgpre.T @ u_t
            grads["bg"] += dgpre.sum(0)
            dy_prev = dy + dz * (-dt * gam) + dpre @ W
            dz_prev = dz * (1.0 - dt * alp)
            dy, dz = dy_prev, dz_prev
        return loss, grads


def train(model, task, T=120, B=64, steps=3000, lr=3e-3, tag=""):
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

    print("=" * 66)
    print(f"EXPERIMENT — the ADDING PROBLEM (T = {T}), the base file's open failure")
    print("No-selection baseline MSE ~= 0.167 (sum ignoring which values are marked)")
    print("=" * 66)

    rng = np.random.default_rng(0)
    print("Gated Selective Oscillatory Memory (multiplicative input-dependent gate):")
    gated = GatedOscillatoryModel(d=64, dt=0.1, gamma=0.3, alpha=0.05)
    train(gated, make_batch, T=T, tag="gated-SOM")

    rng = np.random.default_rng(0)
    print("\nUngated SOM, for comparison (same physics, no selection mechanism):")
    from selective_oscillatory_memory import OscillatoryModel
    ungated = OscillatoryModel(d=64, dt=0.1, gamma=0.3, alpha=0.05)
    train(ungated, make_batch, T=T, tag="ungated-SOM")

    print("\n" + "=" * 66)
    print("REGRESSION CHECK — pure long-range memory task (must still be solved)")
    print("Forgetful baseline MSE ~= 0.333")
    print("=" * 66)
    rng = np.random.default_rng(0)
    gated_mem = GatedOscillatoryModel(d=64, dt=0.1, gamma=0.3, alpha=0.05)
    train(gated_mem, make_memory, T=T, steps=2500, tag="gated-SOM/memory")
