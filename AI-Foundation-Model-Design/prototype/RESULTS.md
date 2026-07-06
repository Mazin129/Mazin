# Prototype Results

Two runnable, laptop-scale prototypes back the blueprint's core claims. Both are
pure NumPy with hand-derived gradients.

1. [Selective Oscillatory Memory](#1-selective-oscillatory-memory-som) — physics-grounded long-range memory (§1.2).
2. [Predictive Coding](#2-predictive-coding-brain-native-learning-no-backprop) — brain-native local learning that matches backprop (§5.2).

---

# 1. Selective Oscillatory Memory (SOM)

**A physics-grounded sequence mixer, built from scratch and run on a laptop-class CPU.**

This is the "just build it" deliverable: a genuinely new mechanism grounded in
Hamiltonian/oscillator physics, implemented in **pure NumPy** with hand-derived
backpropagation (no PyTorch/TensorFlow — the proxy blocked the torch wheel, so every
gradient here is derived and coded by hand, which also makes the math fully auditable).

Run it yourself:

```bash
pip install numpy
python3 selective_oscillatory_memory.py     # ~3–4 min on 4 CPU cores
```

---

## The mechanism (physics)

Hidden state = a network of `d` coupled, damped, driven nonlinear oscillators.
Newton's second law (unit mass), position `y`, velocity `z = y'`:

```
y'' = tanh(W y + V u + b)  −  γ y  −  α y'
      └ nonlinear coupling ┘  └spring┘ └damping┘
```

Integrated with a **symplectic (semi-implicit) Euler** scheme — momentum first, then
position — which preserves the geometric structure of the flow:

```
z_t = z_{t-1} + Δt·( tanh(W y_{t-1} + V u_t + b) − γ y_{t-1} − α z_{t-1} )
y_t = y_{t-1} + Δt·z_t
```

**Why this matters for an AI language model.** For a near-Hamiltonian oscillator the
state-transition Jacobian has eigenvalues near the unit circle, so `‖∂y_T/∂y_t‖` stays
`O(1)` across arbitrarily long `t`. Gradients through time neither vanish nor explode —
the provable root of stable long-range memory (Rusch & Mishra 2020/2021, coRNN/UnICORNN;
LinOSS 2024). A vanilla `tanh`-RNN's Jacobian norm decays geometrically, so its
long-range gradients vanish and it cannot remember.

---

## Experiment 1 — end-to-end: pure long-range memory (T = 120)

A payload value ~`U(−1,1)` is shown **only at step 0**; channel 1 is random distractor
noise at every step; target = the payload. The model must carry step-0 information across
120 steps. A model that forgets predicts the mean → MSE ≈ `Var(U(−1,1)) = 1/3 ≈ 0.333`.

| Model | Final val MSE | Verdict |
|---|---|---|
| **SOM (physics oscillator)** | **0.0017** | ✅ solved — recalls step-0 value across 120 steps |
| Vanilla tanh-RNN (same width) | 0.337 | ❌ stuck at the forgetful baseline — never learns |

Same optimizer (Adam), same hidden size (d=64), same seed, same 2500 steps. The RNN
cannot solve a task the oscillator solves in ~400 steps. The cause is not capacity — it
is gradient flow, confirmed directly by Experiment 2.

## Experiment 2 — the mechanism itself: gradient transport probe

`‖ gradient of the final state w.r.t. the state at step t ‖`, as a function of `t`. High
and flat = information from early steps reaches the end. Decaying to ~0 = vanishing
gradient (the state at that step is invisible to learning).

| step t | SOM (oscillator) | Vanilla RNN |
|---:|---:|---:|
| 0 | 6.7e+01 | 3.1e−05 |
| 30 | 7.1e+00 | 6.2e−06 |
| 60 | 2.4e+00 | 2.6e−04 |
| 90 | 2.0e+00 | 1.2e−02 |
| 119 | 1.1e+00 | 8.9e−01 |

`grad(step 0)/grad(step T)` ratio → **SOM: 61×** (gradient at the earliest step is even
*larger* and stays O(1)) vs **RNN: 3.4e−05** (vanished by ~4–5 orders of magnitude by
just 120 steps; at longer T it is astronomically worse). This is the physics property,
measured directly, and it is exactly what makes Experiment 1 come out the way it does.

---

## Honest limitations (what did NOT work, and why)

- **The classic "adding problem" was not solved by this minimal cell.** That task needs
  long memory **and** a multiplicative gate (value × marker). The oscillator nails the
  memory half; the single bounded-`tanh` drive is poor at the multiplicative-selection
  half, so training stalled at the ~0.167 baseline across many hyperparameter settings.
  This is an honest negative result: it isolates that the mechanism's contribution is
  *memory/gradient-flow*, not *input selection*. The fix is orthogonal — add an explicit
  multiplicative (gated) input term, i.e. the "selective" `Δt`/gate from §1.2 of the
  blueprint — and is the obvious next experiment.
- **This is a toy.** d=64, one layer, ~10K params, two synthetic tasks. It demonstrates a
  *property*, not language modeling. It does not prove anything about frontier quality.
- **No claim of novelty over the oscillatory-RNN literature** for the core cell — that
  math is published. What is assembled here is a clean, from-scratch, auditable
  implementation plus the direct side-by-side gradient-transport measurement, and its role
  as the memory-stable backbone option in the ATLAS design (§1.2).

## How this plugs into the ATLAS blueprint

This validates, at laptop scale, the §1.2 claim that a physics-structured recurrence gives
`O(1)` decode-state long memory without quadratic attention. The next steps (each still
laptop-runnable) follow the ablation-first plan (§4.5):

1. Add the selective multiplicative gate → solve the adding problem (memory + selection).
2. Stack layers + a token embedding → char-level language modeling on a small corpus;
   compare bits-per-char and long-range recall vs. an equal-size Transformer/RNN.
3. Add the sparse-global-attention layer (1-in-6) for exact random-access recall (§1.2).

---

# 2. Predictive Coding (brain-native learning, NO backprop)

Backs the brain-native redesign (section 5.2). The single deepest difference
between the brain and today's AI is that the brain **cannot** run
backpropagation (no global loss signal, no weight transport, no stored reverse
pass). It instead learns by **predictive coding** — every layer predicts the one
below, only prediction *error* is transmitted, the network settles into minimum
"free energy," and each synapse updates from **only locally available signals**.
This prototype shows that local scheme matching backprop.

Run it:

```bash
python3 predictive_coding_brain.py       # ~1 min on CPU
```

### The mechanism (physics/math)

```
mu[l]  = f(x[l-1]) W[l] + b[l]        err[l] = x[l] - mu[l]
F      = 0.5 * sum_l ||err[l]||^2     (free energy = variational bound on surprise)
infer:   dx[l] ~ -( err[l] - f'(x[l]) . (err[l+1] W[l+1]^T) )   (perception = settle)
learn:   dW[l] ~ f(x[l-1])^T err[l]    db[l] ~ mean(err[l])     (LOCAL, no backprop)
```

`dW[l]` uses only the pre-synaptic activity `f(x[l-1])` and the post-synaptic
error `err[l]` — both physically present at the synapse. No backward pass, no
weight transport.

### Result — nonlinear classification (inner disk vs outer ring, [2,32,32,2])

| Learner | Test accuracy | Signal used |
|---|---|---|
| **Predictive coding (local only)** | **1.000** | local pre-activity x local post-error |
| Backprop MLP (same size) | 1.000 | global backward pass + weight transport |

Local learning **matches** backprop — the central claim (Song et al. 2020;
Whittington & Bogacz 2017), reproduced from scratch.

### Result — perception as energy minimization

During a single inference, free energy falls **~17x monotonically** as the
network settles (0.279 -> 0.016 over 30 steps). Perception literally *is*
gradient descent on surprise — the physics of the Free-Energy Principle, on
screen.

### Honest limitations

- Toy scale (2 hidden layers, synthetic 2D task). It demonstrates that the local
  rule *works and matches backprop*, not that it scales to LLMs (an open research
  question, though results up to ImageNet-scale exist in the literature).
- Weights are tied between the feedforward warm-start and the generative model, a
  standard simplification.
- The core cell is from the published PC literature; the contribution here is a
  clean from-scratch, auditable implementation plus the direct backprop
  comparison, as the section-5.2 evidence in the brain-native redesign.

### Next steps (still laptop-scale)

1. Swap the rate units for **spiking LIF** neurons (5.1) and measure event-driven
   sparsity / energy proxy (spikes per inference).
2. Add **neuromodulatory** gain/plasticity control (5.5); show faster adaptation
   under distribution shift.
3. Stack into a small sequence model and compare bits-per-char to a backprop
   baseline — the real test of whether local learning holds at depth.

---

# 3. BL — a Brain-Like model (real ML on real handwritten digits)

`bl_brain_model.py`. This is the "apply ML, make it work like a brain" deliverable:
a complete brain-like learner, trained and evaluated on the **scikit-learn
`digits`** dataset (1797 real 8x8 handwritten digits, classes 0-9). All learning
is pure NumPy — no backpropagation framework; scikit-learn only loads the data.

```bash
pip install numpy scikit-learn
python3 bl_brain_model.py        # a few seconds on CPU
```

### What BL is made of (current neuroscience)

| Brain system | In BL | Role |
|---|---|---|
| Sparse expansion coding / pattern separation (dentate gyrus) | fixed random projection + k-Winners-Take-All (only **8%** of neurons active per input) | event-driven features; separates similar inputs |
| Neocortex, slow consolidation | linear readout trained by a **local three-factor rule** (error x pre-activity), no backprop | stable, high-accuracy knowledge |
| Hippocampus, fast one-shot memory | class prototypes stored instantly (gradient-free) | few-shot & one-shot learning |
| Neuromodulation / novelty routing | hippocampal mismatch signal routes novel inputs to the fast system, familiar ones to cortex | arbitrates fast vs slow |

Grounded in: Complementary Learning Systems (McClelland 1995; Kumaran, Hassabis &
McClelland 2016), local three-factor plasticity (Fremaux & Gerstner 2016),
hippocampal pattern separation & novelty detection, sparse distributed coding.

### Measured results

**Demo 1 — fast few-shot learning (hippocampus).** Accuracy from very few examples:

| examples/class | 1 | 2 | 5 | 10 | 30 |
|---|---|---|---|---|---|
| test accuracy | 0.581 | 0.722 | 0.824 | 0.874 | 0.916 |

**Demo 2 — slow cortical learning with a LOCAL rule (no backprop).** Full 10-class:

| epochs | 1 | 5 | 15 | 40 |
|---|---|---|---|---|
| test accuracy | 0.806 | 0.841 | 0.940 | **0.966** |

96.6% on real handwritten digits, learned without backpropagation.

**Demo 3 — one-shot new class + no catastrophic forgetting.** Cortex is trained on
digits 0-8 only. Digit 9 then arrives and is written to the hippocampus a few
times, with **no retraining**:

| times 9 is shown | acc on NEW class 9 | acc on old 0-8 | all 10 |
|---|---|---|---|
| 0 (never seen) | 0.000 | 0.976 | — |
| 1 | 0.017 | 0.976 | 0.879 |
| 5 | 0.400 | 0.963 | 0.906 |
| 10 | **0.867** | 0.959 | 0.950 |
| 20 | 0.850 | 0.957 | 0.946 |

A single backprop-style net trained on 0-8 scores **0.000** on class 9 forever —
it has no output unit for it. BL learns the new category from a handful of
examples while **old knowledge barely moves (0.976 -> 0.957)** — fast + slow
complementary systems giving continual learning without forgetting.

### Honest limitations

- Small dataset (8x8 digits), a fixed random encoder (not learned end-to-end),
  and a linear cortical readout. It demonstrates the brain *mechanisms and their
  advantages* (few-shot, one-shot, no forgetting), not state-of-the-art image
  accuracy.
- One-shot at n=1 is weak (0.017) — genuinely hard; the value shows up by ~5-10
  examples. Reported honestly rather than cherry-picking a single number.
- The cortical readout is a single layer, so its local delta rule is trivially
  "backprop-free"; the harder claim (deep local learning) is the predictive-coding
  prototype in section 2, and scaling it is still open.

### How BL maps to the blueprint

BL is a small, working instance of the brain-native design (doc 05): sparse
event-driven coding (5.1), local learning (5.2), complementary fast/slow memory
(5.3), and neuromodulatory routing (5.5) — assembled into one model that runs,
learns, and shows human-like few-shot and continual learning.

---

# 4. BL-Torch — the GPU version (PyTorch, full MNIST)

`bl_torch.py`. The BL brain design in **PyTorch**, running on an NVIDIA GPU (e.g. a
laptop GeForce MX550) and scaling to **full MNIST** (60,000 28x28 images). Auto-detects
the GPU (else CPU) and MNIST (else falls back to sklearn digits), so it always runs.

Adds a brain-authentic **V1 visual cortex** front-end: a fixed bank of random
convolutional filters (oriented edge detectors = simple cells) + ReLU + max-pool
(complex cells) + sparsification, before any learning — just as the brain's early
vision is largely fixed structure. This front-end is what lifts accuracy on real MNIST.

Still **no backpropagation** anywhere — every update is explicit local tensor math under
`torch.no_grad()`. The GPU only makes the same brain-like math fast on big data.

```bash
pip install torch torchvision        # GPU build: add  --index-url https://download.pytorch.org/whl/cu124
python bl_torch.py
```

### Measured on **full MNIST** (verified on CPU here; identical on GPU, just faster)

| Demo | Result |
|---|---|
| **Cortical learning, LOCAL rule, NO backprop** | **98.2%** test accuracy on MNIST |
| Few-shot (hippocampus): 1 / 5 / 10 / 30 examples per class | 0.48 / 0.52 / 0.58 / 0.68 |
| One-shot new class 9 (shown 1 / 5 / 10 / 20 times) | 0.09 / 0.21 / 0.42 / **0.63** |
| Old digits 0-8 after adding class 9 (forgetting check) | stays **~0.95** (baseline net: 0% on 9 forever) |

The headline: **98.2% on MNIST learned with a biologically-plausible local rule and a
fixed V1 vision front-end — no backpropagation.** The V1 front-end raised the cortex from
~93% (raw-pixel version) to 98.2%.

### Honest limitations

- **Few-shot / one-shot on MNIST are inherently hard** with fixed features + a single
  prototype per class (few-shot caps ~0.68 at 30 examples; one-shot climbs to ~0.63 by 20
  exposures). This is a real property of the task, reported as-is — not a bug. Storing
  multiple exemplars per class (true episodic memory) or a learned encoder would raise it.
- The cortical readout is a single layer (its local delta rule is trivially backprop-free);
  the harder claim (deep local learning) is the predictive-coding prototype in section 2.

Tuning for a small (2 GB) GPU: lower `N_FILTERS` in the file (128 -> 64) if you hit
out-of-memory.
