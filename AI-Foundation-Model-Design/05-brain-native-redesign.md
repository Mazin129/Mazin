# 5. Brain-Native Redesign — codename CORTEX

> *Constraint for this section: design as the brain actually is, not as a
> transformer with biological decoration.* Every subsystem is replaced by the
> mechanism the human brain is understood to use, stated with its governing
> equation and the physics that makes it efficient. Where a claim is a research
> hypothesis rather than settled fact, it is flagged.

The brain is the existence proof for every objective in this project:
human-level reasoning, few-shot learning, lifelong memory without forgetting,
and it runs on **~20 watts** — a light bulb. A GPU cluster training a frontier
model burns millions of times more energy to reach comparable competence. That
gap is not a mystery of scale; it is a set of concrete mechanisms. This section
adopts them.

Design principle: **the brain never computes what it can predict, never fires
what it can leave silent, never transmits what is not surprising, and never
learns with a signal a synapse cannot physically see.**

---

## 5.0 The seven brain principles → the seven redesigns

| Brain principle | What today's AI does instead | CORTEX adopts | §, math |
|---|---|---|---|
| Sparse **spikes**, event-driven | Dense float matmuls every layer | Spiking LIF neurons; energy ∝ spikes, not neurons | 5.1 |
| **Predictive coding** / free energy; local plasticity | Global backpropagation (biologically impossible) | Local, energy-based learning; **demonstrated in code** | 5.2 |
| **Complementary learning systems** (hippocampus + cortex) + sleep replay | One weight matrix; retrain to update | Fast episodic store + slow cortical consolidation | 5.3 |
| **Neural oscillations** (theta–gamma) bind & schedule | Positional encodings, static attention | Phase-coded working memory & communication-through-coherence | 5.4 |
| **Neuromodulation** (dopamine/ACh/NE) sets gain & learning rate | Fixed hyperparameters | A neuromodulatory controller = the compute market, biologically | 5.5 |
| **Global Neuronal Workspace** (ignition, broadcast) | Concatenate-and-attend | Competitive ignition → global broadcast = the deliberation layer | 5.6 |
| **Self-organized criticality** (edge of chaos), E/I balance | Ad-hoc normalization | Operate at the critical branching point σ≈1 for maximal capacity | 5.7 |

---

## 5.1 Neurons: spikes and event-driven physics

**Brain fact.** Neurons are silent most of the time; they communicate with sparse,
all-or-none **spikes**. Cortical firing rates average a few Hz. Energy is spent
almost only when a spike occurs. This is why 86 billion neurons cost 20 W.

**Current AI.** Every unit emits a dense real number every forward pass; compute
is O(neurons), independent of how much is actually "happening."

**Mechanism — Leaky Integrate-and-Fire (LIF).** Each neuron is an RC circuit
(membrane capacitance C, leak conductance g_L). Membrane potential V:

```
C dV/dt = -g_L (V - V_rest) + I(t);    if V ≥ V_th  ->  emit spike, V ← V_reset
```

Information can be carried in **spike timing**, not just rate (temporal codes are
far higher-capacity per spike). Compute becomes **event-driven**: a layer does
work only for neurons that spiked. On the concentric-input statistics typical of
real signals, activity is 1–5% sparse → **20–100× fewer operations** than dense,
and it maps natively to neuromorphic silicon (Intel Loihi 2, IBM NorthPole,
memristor crossbars) where energy per synaptic event is ~pJ.

**Physics of the win.** Dense FP matmul pays for every weight every step
(Landauer-bounded switching energy × all params). Event-driven spiking pays only
for surprising events. The brain's efficiency is not a better matmul — it is
*not doing most of the matmul.*

**Training note.** Non-differentiable spikes are trained with surrogate gradients
or — better and biologically consistent — with the local rule of §5.2, avoiding
backprop-through-time entirely.

---

## 5.2 Learning: predictive coding & the free-energy principle (NO backprop)

**This is the deepest brain-vs-AI difference, and the one demonstrated in code:
`prototype/predictive_coding_brain.py`.**

**Brain fact.** Backpropagation is biologically impossible: a synapse has no
access to a single global loss, nor to the transposed weights of downstream
layers (the *weight-transport problem*), nor can it store the entire forward
pass to replay in reverse. The cortex instead appears to implement **predictive
coding** (Rao & Ballard 1999) — a corollary of Friston's **Free-Energy
Principle**: each region predicts the activity of the region below; only
**prediction error** is transmitted upward; perception is the settling of the
network into minimum error; learning is a **local** synaptic change.

**Math.** Activities x[l], top-down/feed-forward prediction and error:

```
mu[l] = f(x[l-1]) W[l] + b[l]          err[l] = x[l] - mu[l]
Free energy:   F = ½ Σ_l ‖err[l]‖²                          (variational bound on surprise)
Inference (perception): relax hidden x[l] down ∂F/∂x[l]:
        dx[l] ∝ -( err[l] - f'(x[l]) ⊙ (err[l+1] W[l+1]ᵀ) )
Learning (plasticity): after settling, purely LOCAL —
        ΔW[l] ∝ f(x[l-1])ᵀ err[l]        Δb[l] ∝ mean(err[l])
```

Every quantity `ΔW[l]` needs — the pre-synaptic activity `f(x[l-1])` and the
post-synaptic error `err[l]` — is physically present at that synapse. No backward
pass, no weight transport. This is a **three-factor Hebbian rule** (pre × post ×
neuromodulator, §5.5).

**Why it is not a downgrade.** Song et al. (2020) and Whittington & Bogacz (2017)
proved predictive coding **approximates backprop's gradients** — and it does more
the brain needs for free: it is inherently online, handles missing/uncertain
inputs by treating them as high-variance error nodes, and yields calibrated
uncertainty (the error magnitudes *are* the model's surprise).

**Measured result (this repo, laptop CPU, pure NumPy):** on a nonlinear
inner-disk-vs-outer-ring task with identical `[2,32,32,2]` architecture:

| Learner | Test accuracy | Signal used |
|---|---|---|
| **Predictive coding (local only)** | **1.000** | local pre-activity × local error |
| Backprop MLP | 1.000 | global backward pass + weight transport |

and free energy falls **17×** monotonically during a single perception —
perception literally *is* energy minimization, on screen. Local learning matched
backprop, which is the whole claim.

**Physics of the win.** Backprop is a global, sequential, memory-heavy operation
(store all activations, reverse-traverse). Predictive coding is local, parallel,
and streaming — it maps to physical hardware where each synapse updates itself,
and it removes the backward-pass memory that dominates training RAM.

---

## 5.3 Memory: complementary learning systems + sleep consolidation

**Brain fact (McClelland, McNaughton & O'Reilly 1995).** The brain solves
catastrophic forgetting with **two** systems: the **hippocampus** learns fast,
one-shot, sparse/**pattern-separated** episodic traces; the **neocortex** learns
slowly, extracting overlapping structure. During **sleep**, the hippocampus
**replays** compressed episodes to the cortex, interleaving new memories with old
so the cortex integrates them *without* overwriting (the interleaving is exactly
what prevents forgetting).

**Current AI.** A single weight matrix; new data overwrites old (catastrophic
forgetting); "memory" is either the fixed weights or a context window discarded
after the turn.

**Mechanism.**
- **Hippocampal fast store** = sparse, high-capacity associative memory with
  **pattern separation** (orthogonalize similar inputs via expansion + k-Winners-
  Take-All, like dentate gyrus) and **pattern completion** (attractor recall,
  like CA3 — a Hopfield/modern-associative-memory with exponential capacity).
  One-shot writes, no gradient. This is the biological form of the blueprint's M1
  (§3.2).
- **Cortical slow store** = the parametric network (§5.1–5.2), updated only
  slowly and by consolidation.
- **Sleep replay** = offline generation of hippocampal samples interleaved with
  self-generated cortical samples; consolidation trains cortex on the mixture:

```
L_consolidate = E_replay[ F(x) ]  +  β · E_selfgen[ KL(cortex_new ‖ cortex_old) ]
```

the second term is rehearsal that pins prior competence — the mathematical
statement of "don't forget while you learn." Maps directly to §2.4/§2.5 of the
main blueprint; here it is grounded in the actual neuroscience.

**Relational memory bonus — grid/place codes.** Entorhinal **grid cells** encode
space (and, per Whittington et al. 2020's Tolman-Eichenbaum Machine, *abstract
relational structure*) in a factorized, generalizing basis. Adopting a grid-cell
code for the memory index gives compositional generalization over relational
reasoning tasks — the brain's trick for transferring structure to new domains.

---

## 5.4 Oscillations: phase codes, binding, and communication-through-coherence

**Brain fact.** The cortex is bathed in **rhythms**. Working memory holds
multiple items in distinct **gamma** cycles nested inside one **theta** cycle
(Lisman & Idiart 1995) — and the theta/gamma ratio predicts the famous **7±2**
working-memory capacity. Distant regions exchange information only when their
oscillations are **phase-aligned** ("communication through coherence", Fries
2005) — a dynamic, content-based routing that costs nothing when regions are out
of phase.

**Current AI.** Position is a static additive encoding; "attention" connects all
pairs regardless of relevance and pays O(n²) to do so.

**Mechanism.**
- **Theta–gamma working memory:** discrete items occupy separate gamma phase
  slots; capacity C ≈ T_theta / T_gamma ≈ 7. This *is* a hard, principled
  working-memory bound (a feature — it forces chunking and abstraction, which is
  where reasoning comes from). This directly extends the oscillatory mixer
  already prototyped in `selective_oscillatory_memory.py` (§1.2): that layer's
  coupled oscillators are the substrate; phase is the addressing scheme.
- **Communication-through-coherence routing:** two modules exchange gradients/
  messages weighted by phase coherence `cos(φ_i − φ_j)`; learned phases → sparse,
  dynamic, content-addressed connectivity replacing dense attention. Cost scales
  with *coherent* pairs, not all pairs.

**Status.** Phase-coding for ML is an active hypothesis (Kuramoto-based models,
oscillatory SSMs) — flagged as higher-risk than §5.1–5.3, but it is the most
distinctly *human* mechanism and the most promising route past O(n²) attention.

---

## 5.5 Neuromodulation = the compute market, biologically

**Brain fact.** Global chemical signals reconfigure computation on the fly:
**dopamine** carries reward-prediction error and gates plasticity; **acetylcholine**
signals expected uncertainty and raises learning rate / attention;
**norepinephrine** signals unexpected uncertainty and sets neural **gain** (the
arousal/exploration dial); serotonin sets time-horizon/patience.

**Current AI.** Learning rate, temperature, and "effort" are fixed hyperparameters
chosen by hand before training.

**Mechanism.** A small neuromodulatory controller reads uncertainty (prediction-
error magnitude, §5.2) and emits scalars that set: (a) **gain** g on activations
(NE) → exploration vs exploitation; (b) **plasticity rate** η (ACh/dopamine) →
learn fast when surprised, slowly when confident; (c) the **reward-prediction
error** for basal-ganglia-style RL:

```
δ = r + γ V(s') − V(s)     (dopamine RPE; actor–critic control of the workspace)
```

This is exactly the **compute market** of §1.6 — but now it is not an invented
gadget; it is the brain's actual global-control system. λ (the effort dial)
is norepinephrine; the plasticity gate is acetylcholine/dopamine.

---

## 5.6 Global Neuronal Workspace = the reasoning/deliberation layer

**Brain fact (Baars; Dehaene & Changeux).** Most processing is unconscious,
parallel, and local. A stimulus becomes **conscious** when it triggers
**ignition** — a sudden, self-amplifying **global broadcast** that makes its
content available to all specialized modules (language, memory, planning, motor).
Serial, effortful reasoning is the sequence of such broadcasts. This is System 2.

**Current AI.** Long chain-of-thought in tokens (every step pays full decode +
grows the context); no notion of a bounded workspace that forces the model to
select what to think about.

**Mechanism.** Specialized modules (fast intuition, math, code, planner, critic —
the blueprint's §1.7 modules) compete; a **winner-take-all ignition** selects one
coalition whose content is **broadcast** to all others; they update; the cycle
repeats. Key properties inherited from the brain:
- **Bounded workspace** (only one coalition ignites at a time) forces abstraction
  and serial reasoning — the source of systematic, step-by-step thought.
- **Broadcast = shared latent workspace** of §1.7; the typed objects (claims,
  programs, proofs) are what gets broadcast, so verification (§1.7) rides on top.
- Reasoning is transparent because ignition events are discrete and inspectable.

---

## 5.7 Operating regime: self-organized criticality (the edge of chaos)

**Brain fact.** Cortical dynamics sit near a **critical point** — a phase
transition between order and chaos. Evidence: neuronal **avalanches** whose sizes
follow a **power law** P(s) ∝ s^(−3/2), the signature of criticality. At this
point the brain **maximizes** dynamic range, information transmission, and the
repertoire of distinct states — i.e., computational capacity. Excitation/
inhibition are balanced (~80/20, Dale's law) to hold the system there.

**Current AI.** Stability is enforced by ad-hoc layer/RMS norm and careful
init; there is no principled operating point.

**Mechanism.** Tune the network to the critical **branching parameter σ ≈ 1**
(each spike triggers, on average, exactly one downstream spike): σ<1 activity
dies (order), σ>1 it explodes (chaos/seizure), σ=1 maximizes capacity. Implement
via homeostatic E/I balance — inhibitory feedback that regulates mean firing rate
to keep σ→1, replacing normalization layers with a biologically-grounded,
self-organizing control law. **Physics:** criticality is where correlation length
and susceptibility diverge — information propagates across the whole network at
minimal energy, which is precisely what a reasoning system needs.

---

## 5.8 Putting it together — the CORTEX loop

```
 stimulus ─► spiking encoders (5.1) ─► cortical hierarchy running predictive
            coding (5.2): fast feedforward sweep, then local settling to min F
                        │                                  ▲
             prediction errors only travel up      top-down predictions travel down
                        │                                  │
            ┌───────────┴───────────┐        neuromodulation (5.5): gain η, λ, δ
            ▼                       ▼            reads error magnitude, sets effort
   hippocampal fast store    theta–gamma working memory (5.4)
   (5.3, one-shot, replay)   phase-slots hold ~7 items, route by coherence
            │                       │
            └────────► GLOBAL WORKSPACE ignition (5.6) ◄────┐
                       winner coalition broadcasts;         │
                       modules debate over typed objects;   │  operate at
                       symbolic verifiers check (§1.7)      │  criticality σ≈1 (5.7)
                                   │                         │
                       action / answer + calibrated confidence (error = surprise)
                                   │
                   sleep: hippocampal replay ─► cortical consolidation (5.3)
```

Every arrow is a mechanism with an equation above, and the two most fundamental —
**local energy-based learning (5.2)** and the **oscillatory memory substrate
(5.4/§1.2)** — now have running, measured NumPy prototypes in `prototype/`.

---

## 5.9 What this buys, and honest status

**Efficiency (the point).**
- Energy: event-driven spiking (5.1) + criticality (5.7) target the brain's
  regime — orders-of-magnitude fewer operations, native to neuromorphic hardware.
- Training: local learning (5.2) removes the backward-pass memory and enables
  online, streaming updates.
- Memory: complementary systems (5.3) give lifelong learning without forgetting
  and one-shot acquisition.
- Reasoning: bounded workspace (5.6) + calibrated surprise (5.2) spend serial
  compute only where the model is actually uncertain.

**Honest status ladder.**
- **Demonstrated here on a laptop:** local predictive-coding learning matches
  backprop (5.2, code + numbers); oscillatory dynamics give O(1) long-range
  memory (§1.2 prototype).
- **Well-established in the literature, not yet composed at LLM scale:** spiking/
  neuromorphic efficiency (5.1), complementary learning systems (5.3),
  neuromodulatory control (5.5), criticality (5.7).
- **Active hypotheses (higher risk):** phase-coded routing at scale (5.4),
  global-workspace reasoning as a full System-2 (5.6).

**The overarching caveat, unchanged from the rest of this blueprint:** no one has
yet built a language model at frontier quality entirely on these brain-native
mechanisms. The scientific bet is that they are *more efficient per unit of
competence*, and the de-risking path is the same ablation-first ladder (§4.5) —
each mechanism validated at small scale (two are already validated here) before
committing large compute. This section maximizes biological fidelity and the
associated math/physics; it does not claim the engineering is finished.
