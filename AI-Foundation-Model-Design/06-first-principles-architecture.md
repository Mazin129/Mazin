# 6. AXIOM — A First-Principles, Brain-Native Architecture

> *Brief: invent a new architecture, not a better transformer. Do not assume
> intelligence needs billions of parameters, oceans of data, or a data center —
> those are engineering constraints, not laws. Start from the brain (20 W,
> lifelong learning, few-shot, compact, sparse, modular, predictive) and design
> for 100–1000× fewer parameters, ~100× less compute, and continual learning on a
> single workstation.*

This document does three things: (I) interrogates the transformer's hidden
assumptions from first principles; (II) proposes the new mechanisms, each with
biological inspiration, math, complexity, memory, energy, advantage-vs-transformer,
implementation, and validation; (III) composes them into one architecture and
analyzes the efficiency claim **honestly**.

**What makes this credible rather than a manifesto:** many of these mechanisms are
already implemented and measured in [`prototype/`](prototype/) and [`mind/`](mind/)
in this repo. Where a mechanism is validated, it is marked ✅ **BUILT** with the
file and number. Where it is a research bet, it is marked ⚠️ and the risk is stated.
No claim is dressed up as more than it is.

---

## Part I — Interrogating the transformer's assumptions

Every dominant assumption below is an *engineering choice*, not a law. Naming them
is the first act of invention.

**A1. "Intelligence needs billions of parameters."**
Why are they needed? Overwhelmingly to *memorize facts*, not to *reason*. A large
LM devotes most of its capacity to storing the web verbatim. But the brain stores
~few-bit synapses and offloads episodic detail to a hippocampal index. → **If
knowledge lives in external memory, parameters need only encode *skills*
(language, composition, reasoning), which is a far smaller quantity.** This single
re-decomposition is where most of the 100–1000× lives (Part IV).

**A2. "Knowledge must live in the weights."**
This conflates *skill* (procedural, slow-changing) with *knowledge* (factual,
fast-changing). Baking facts into weights makes them (a) expensive (one param per
fact-fragment), (b) stale (retraining to update), (c) unverifiable. The brain keeps
facts in an addressable, editable store. → **Knowledge belongs in an external,
adaptive memory; weights hold skills.**

**A3. "Compute densely, every layer, every token."**
A transformer spends identical FLOPs on "the" and on a hard inference step. The
brain is silent ~95% of the time and fires sparsely. → **Compute only where and
when something surprising happens (event-driven, sparse).**

**A4. "Attention over everything, O(n²)."**
Quadratic all-pairs mixing is a brute-force stand-in for *relevant* recall. The
brain routes by content and phase, not all-to-all. → **O(1)-state recurrence for
the bulk + sparse, content-selected attention only where exact recall is needed**
(already validated, §1.2 / `bl_language_fast`).

**A5. "Weights are fixed after training."**
Real synapses are context-gated in milliseconds (neuromodulation, short-term
plasticity). The effective connectivity of the brain is *generated per context*. →
**Neurons can generate temporary weights on demand (fast weights / hypernetworks);
the stored network is a generator of task-specific networks, not one frozen net.**

**A6. "One giant network does everything."**
The brain is a federation of specialized regions with a global workspace. →
**Reasoning emerges from modular collaboration + broadcast, not a monolith.**

**A7. "Learning = one big offline gradient pass; deployment is frozen."**
The brain learns every second, without forgetting, and mostly *without* a global
error signal. → **Continual, local, online learning + consolidation.**

The rest of this document is the constructive answer to A1–A7.

---

## Part II — The mechanisms

Format per mechanism: **Bio → Math → Complexity → Memory → Energy → vs Transformer
→ Implementation → Validation.**

### M1 — Sparse, event-driven computation
- **Bio.** Neurons are silent most of the time; they emit sparse all-or-none
  spikes; cortical activity is 1–5% sparse; energy is spent per spike, not per
  neuron.
- **Math.** Leaky integrate-and-fire: `C dV/dt = −g_L(V−V_rest) + I(t)`; emit event
  when `V ≥ V_th`, then reset. Layer output computed only for the top-k active
  units (k-Winners-Take-All): `h = WTA_k(relu(Wx+b))`. Delta/event coding: a unit
  transmits only when its value change exceeds θ.
- **Complexity.** O(ρN) with sparsity ρ instead of O(N); with ρ≈0.05, ~20×.
- **Memory.** One state variable per unit; activations are sparse vectors.
- **Energy.** ∝ number of events, not number of units — the brain's core trick.
- **vs Transformer.** Dense nets pay O(N) every token regardless of difficulty.
- **Implementation.** k-WTA + delta coding; native to neuromorphic silicon
  (Loihi/NorthPole) at ~pJ/event.
- **Validation.** ✅ **BUILT** — `bl_brain_model.py` / `bl_torch.py`: only **8% of
  neurons active per input**, and the sparse code still hits **98.2% on MNIST**.

### M2 — Dynamic parameter generation (weights on demand)
- **Bio.** Synaptic efficacy is gated in real time by neuromodulators and
  short-term plasticity; the brain's *effective* wiring is generated per context,
  not stored per task. "Fast weights" overlay slow weights.
- **Math.** Don't store a weight matrix per context. Keep a small **generator**
  `g_φ` and produce context weights on the fly:
  `W_eff(c) = W_slow + Σ_j u_j(c) v_j(c)ᵀ`, where the low-rank terms `u,v = g_φ(c)`
  are emitted by a hypernetwork from context `c` (Fast-Weight Programmers,
  Schmidhuber 1992; hypernetworks, Ha 2016). Compute uses `W_eff`; only `g_φ` and
  `W_slow` are stored.
- **Complexity.** Generating a rank-r update: O(r·d). Applying it: O(r·d) per token
  vs O(d²) for a full dense layer.
- **Memory.** Store the *generator* (small) instead of many task-specific matrices
  → the combinatorial space of "task networks" is produced, not warehoused.
- **Energy.** Weights materialized only for the active context/token.
- **vs Transformer.** A transformer freezes one enormous weight set for all inputs;
  most of it is irrelevant to any given token.
- **Implementation.** Hypernetwork emits per-token/per-context LoRA-style rank-r
  updates; slow weights consolidated rarely.
- **Validation.** ✅ **BUILT** — `prototype/dynamic_weights.py`: a hypernetwork
  reads 10 examples of a never-seen task and *generates* a target network's weights
  in one forward pass — **MSE 0.027 with zero gradient steps**, vs 0.24 for a
  from-scratch net given 100 gradient steps. The direct answer to "can neurons
  generate temporary weights on demand?" — yes, and it adapts far faster than
  training. (Scaling this to generate the language core's weights per context is the
  open frontier.)

### M3 — Long-term, expandable external memory
- **Bio.** Hippocampus (fast, one-shot, pattern-separated) + neocortex (slow); memory
  is addressable and grows through life, not crammed into a fixed synaptic budget.
- **Math.** External key–value store `M={(k_i,v_i)}`. Read: `r = Σ_i softmax(q·k_i/τ)
  v_i` over an ANN-retrieved shortlist. Write: append `(k,v)`; consolidate hot
  entries. The parametric core `f_θ` conditions on `r`. Capacity of the *system*
  scales with `|M|` (bytes), independent of `θ`.
- **Complexity.** Read O(log|M|) with an ANN index; core cost independent of |M|.
- **Memory.** Knowledge stored as *data* (bytes), not *parameters* — ~orders of
  magnitude cheaper per fact, and editable/deletable.
- **Energy.** Touch only the retrieved shortlist, not all knowledge.
- **vs Transformer.** Weights = fixed knowledge capacity; updating needs retraining;
  facts are unverifiable and entangled.
- **Implementation.** Vector index (FAISS/ScaNN) + graph edges; gated cross-attention
  or prompt injection into the core.
- **Validation.** ✅ **BUILT** — `mind/reasoner.py` (TF-IDF library you grow with
  `teach:`), `chat/brain_chat.py` (persistent user memory), `bl_advanced.py`
  (episodic hippocampus, k-NN recall).

### M4 — Modular cognitive systems + global workspace
- **Bio.** Specialized regions (vision, language, motor, PFC) cooperate; conscious,
  serial reasoning is a *global broadcast* (Global Neuronal Workspace).
- **Math.** Experts `{E_k}`; router `r(x)=TopK(softmax(W_r x))` activates a few;
  a winner coalition's output is broadcast to all: `b = Σ_{k∈win} g_k E_k(x)`; other
  modules read `b`. Mixture-of-experts + workspace.
- **Complexity.** O(k) active experts of E, not O(E).
- **Memory.** Experts are the unit of growth (add an expert for a new domain).
- **Energy.** Only the winning coalition fires.
- **vs Transformer.** Monolithic; even coarse MoE lacks a broadcast/deliberation loop.
- **Implementation.** Fine-grained MoE (§1.3) + a typed workspace (§1.7) + tool
  modules.
- **Validation.** ✅ **partially BUILT** — `mind/reasoner.py` routes a query to
  specialized tools (symbolic math / retrieval / memory) and reports which fired;
  MoE sparsity validated conceptually in §1.3.

### M5 — Predictive world modeling (the core learning signal)
- **Bio.** The cortex is a prediction machine (predictive coding; Free-Energy
  Principle). Perception = minimizing prediction error.
- **Math.** Learn `p(x_{t+1}|x_≤t, a_t)`; minimize free energy `F=½Σ‖x_l−μ_l‖²`
  where `μ_l = f(x_{l+1})` are top-down predictions. Perception = relax activities
  to minimize F; learning = local update from prediction error.
- **Complexity.** Inference = a few relaxation steps; learning is O(fan-in) per synapse.
- **Memory.** Store the *generative model*, not the data (see M9 — compression).
- **Energy.** Only surprising (high-error) signals drive computation/learning.
- **vs Transformer.** Next-token CE is a special case; PC gives calibrated
  uncertainty and needs no global backward pass.
- **Validation.** ✅ **BUILT** — `predictive_coding_brain.py` (free energy drops
  17× as perception settles); it *is* the learning rule in M6.

### M6 — Continual, local learning without catastrophic forgetting
- **Bio.** Complementary Learning Systems: fast hippocampus + slow cortex + **sleep
  replay** interleaving new with old; learning is **local** (no global backprop —
  synapses have no access to a global error or transposed downstream weights).
- **Math.** Local predictive-coding update: `ΔW_l ∝ f(x_{l-1})ᵀ err_l` (only local
  pre-activity × local post-error). Consolidation: `L = CE(new) + γ·KL(p_new(x_old)‖
  p_old(x_old))`, `x_old` from replay — the math of "learn without forgetting".
  New domains → grow experts (M4); frozen core protects old skills.
- **Complexity.** Local, parallel, streaming; no stored full-forward-pass for a
  reverse traversal.
- **Memory.** Fast store cheap; consolidation periodic.
- **Energy.** Local updates; no global backward pass memory.
- **vs Transformer.** Backprop is biologically impossible and needs offline retrain;
  it forgets on new data.
- **Validation.** ✅ **BUILT & measured** — local learning matches backprop:
  `predictive_coding_brain.py` (100% on a nonlinear task, no backprop),
  `bl_deep_local.py` (**96.9% on MNIST, no backprop**); no-forgetting:
  `bl_advanced.py` learns a **new class one-shot while old classes stay ~0.95**.

### M7 — Hierarchical reasoning
- **Bio.** Cortical hierarchy: higher areas represent more abstract, slower-changing
  causes; reasoning = settling constraints across levels.
- **Math.** Stacked predictive-coding levels; abstraction = latent at higher level;
  reasoning = joint relaxation to minimize total F across the hierarchy. For
  discrete reasoning: options/subgoal hierarchy (planning at multiple time scales).
- **Complexity.** Depth = serial reasoning budget; allocate dynamically (M8-style
  recursion) rather than fixed.
- **vs Transformer.** Fixed depth spends equal serial compute on trivial and hard.
- **Validation.** ✅ deep local hierarchy in `bl_deep_local.py`; recursive tool
  chaining in `mind/reasoner.py`.

### M8 — Adaptive (event-driven) compute allocation
- **Bio.** Effort is metered (PFC/neuromodulation); the brain thinks harder only on
  hard problems.
- **Math.** A controller sets a compute budget `B` per input; conditional depth
  (early exit when `KL(p_ℓ‖p_{ℓ-1})<τ`), recursion count, expert count, and
  retrieval all bid against one Lagrangian `max E[quality] − λ·E[FLOPs]` so every
  mechanism runs at equal marginal quality-per-FLOP (§1.6, the "compute market").
- **Complexity.** Average cost ≈ easy-case cost; tail scales with genuine difficulty.
- **vs Transformer.** Uniform compute per token.
- **Validation.** ⚠️ controller not yet trained; the individual gates are standard.

### M9 — Compression-based knowledge (intelligence ≈ compression)
- **Bio.** The brain stores compact *generative models*, not raw episodes;
  prediction *is* compression.
- **Math.** Minimum Description Length: pick the model minimizing
  `L(model) + L(data|model)`. A good predictor `p` yields a short code
  (`−log p(x)` bits, arithmetic coding). Learning = finding the shortest program
  that explains the data (Solomonoff/Hutter view). Knowledge = the compressed model
  + external memory for incompressible specifics.
- **Complexity.** Favors small, general models over large memorizers.
- **Memory.** Compressed generative model ≪ memorized corpus.
- **vs Transformer.** Large LMs achieve poor *knowledge compression* (they store
  facts near-verbatim in weights); MDL says push facts to M3 and keep weights for
  the compressible regularities (skills).
- **Validation.** ⚠️ conceptual; our LMs learn generative (predictive) models, and
  M3 supplies the external store for incompressible facts.

### M10 — Meta-learning (learning to learn)
- **Bio.** The brain tunes its own learning (neuromodulated plasticity, learning
  rates set by uncertainty); a child learns *how* to learn categories.
- **Math.** Outer loop optimizes for fast inner adaptation:
  `min_θ Σ_tasks L(adapt(θ, support), query)` (MAML). Or in-context learning as
  implicit meta-learning; or a learned local plasticity rule (M6) whose coefficients
  are meta-optimized.
- **Complexity.** Cost at deployment ~ few-shot adaptation, not full training.
- **vs Transformer.** ICL exists but isn't *trained for*; adaptation doesn't persist.
- **Validation.** ✅ few-shot demonstrated — `bl_advanced.py` learns a category from
  1–30 examples; persistence added via M3 memory.

### M11 — Active, curiosity-driven learning
- **Bio.** Dopaminergic novelty/prediction-error signals; intrinsic motivation drives
  exploration.
- **Math.** Intrinsic reward = Bayesian surprise / information gain:
  `r_int = KL(posterior‖prior)` or prediction-error magnitude; the agent selects
  data/actions maximizing expected model improvement. Detect knowledge gaps from
  low-retrieval-score / high-verifier-failure clusters and seek those.
- **Complexity.** A small predictor + gap tracker.
- **vs Transformer.** Passive on a fixed corpus.
- **Validation.** ⚠️ design (§2.6); The Mind's "I don't know — teach me" is a
  primitive gap signal.

### M12 — Recursive planning
- **Bio.** PFC decomposes goals into subgoals; mental simulation ("what if") over a
  world model.
- **Math.** Plan = search over the learned world model (M5): recursive subgoal
  decomposition + model-based rollouts (MCTS / model-predictive control); memoize
  solved subgoals in M3.
- **Complexity.** Search budget metered by M8; memoization avoids re-solving.
- **vs Transformer.** No explicit planner or simulator.
- **Validation.** ⚠️ tool-chaining in `mind/reasoner.py` is proto-planning; full
  planner is a build.

### M13 — Symbolic + neural hybrid, with self-verification
- **Bio.** Dual-process cognition: fast intuitive System 1 (neural) + slow symbolic
  System 2; metacognitive monitoring (PFC) catches errors.
- **Math.** Neural proposer emits *typed* objects (Claim, Program, Proof, Plan);
  symbolic verifiers *dispose*: programs → execute against a spec, arithmetic/algebra
  → CAS/SMT (exact), facts → retrieval-entailment. Answer confidence = fraction of
  claims verified. Symbolic checks cost ~10³–10⁶× less than an LLM "re-check" and
  return ground truth, not opinion.
- **Complexity.** Cheap verifiers gate expensive generation.
- **vs Transformer.** Pure neural nets hallucinate math/facts and can't self-verify.
- **Validation.** ✅ **BUILT** — `mind/reasoner.py`: exact symbolic math that
  **verifies itself** (substitutes solutions back; differentiates integrals back),
  and says "I don't know" instead of bluffing. This is the sharpest *practical*
  advantage over market LLMs today.

---

## Part III — The AXIOM architecture (how the mechanisms compose)

```
            ┌──────────── neuromodulatory controller (M8) ─────────────┐
            │  meters compute budget B, plasticity η, curiosity (M11)  │
   input ───▼──────────────────────────────────────────────────────────┐
   (event-  │  SENSORY CORTEX: spiking / sparse encoder (M1)           │
    coded)  │        ↓ sparse code                                     │
            │  PREDICTIVE HIERARCHY (M5,M7): local learning (M6),      │
            │        weights generated per context (M2)                │
            │        ↕ prediction errors travel up, predictions down   │
            │  ┌───────────────┐        ┌──────────────────────────┐   │
            │  │ EXTERNAL MEM  │◄──────►│ MODULES + WORKSPACE (M4)  │   │
            │  │ (M3): fast    │        │ intuition│math│code│plan  │   │
            │  │ episodic +    │        │ + CRITIC/VERIFIER (M13)   │──┼─► symbolic
            │  │ slow semantic │        │ recursive planning (M12)  │   │   tools
            │  └───────────────┘        └──────────────────────────┘   │
            │        ▲ consolidation (sleep replay, M6)                │
            └─────────┴───────────────────────────────────────────────┘
                                     │
                     answer + confidence + citations + trace
                                     │
                 curiosity (M11): detect gaps → seek data → learn (M6/M10)
```

The loop: encode sparsely → predict & settle (cheap, local) → escalate to modules,
memory, and symbolic verifiers *only* under budget → answer with verified confidence
→ write durable results to memory → detect gaps and learn continually.

---

## Part IV — The efficiency claim, analyzed honestly

The target is 100–1000× fewer parameters, ~100× less compute, lifelong learning on
one workstation. Where does each factor *actually* come from, and how solid is it?

| Source | Mechanism | Factor | Confidence |
|---|---|---|---|
| Facts → external memory (params encode skills, not facts) | M3, M9 | ~10–100× fewer **stored** params | High on knowledge-heavy tasks; this is the biggest and best-supported lever (RETRO showed 25× at equal perplexity) |
| Sparse / event-driven active compute | M1, M8 | ~10–50× fewer **active** FLOPs/token | High (brain + MoE evidence; 8%-active validated here) |
| Weights generated, not stored | M2 | multiplies M3's param win | Medium (fast-weights literature; unbuilt here) |
| Local learning enables on-device continual training | M6 | qualitative (no data-center retrain) | High — **measured** (96.9% MNIST, no backprop) |
| Symbolic verification replaces scale-for-reliability | M13 | quality, not size | High — **built** (exact verified math) |

**Honest composition.** These attack *different* axes (stored params, active FLOPs,
knowledge capacity, update cost), so they multiply rather than overlap — which is
why 100–1000× on the *right* axes is plausible. **But** the parametric core still
needs enough capacity to encode *skills* (language, composition, reasoning), and
that floor is not near zero. So the honest claim is:

> **100–1000× fewer parameters for equal *knowledge capacity and reliability*, and
> ~100× less *active* compute — by moving facts out of weights, computing sparsely,
> and verifying symbolically. NOT a 1000× shrink of raw linguistic/reasoning skill
> itself, which still requires real (if far smaller) scale and data.**

Anyone claiming otherwise is selling a vacuum tube as a fusion reactor. The
architecture makes the *decomposition* possible; the remaining skill-core is a real,
if much smaller, training problem.

---

## Part V — What is already validated (so this isn't a manifesto)

| Mechanism | Prototype | Measured result |
|---|---|---|
| M1 sparse/event-driven | `bl_brain_model.py`, `bl_torch.py` | 8% active neurons, 98.2% MNIST |
| M3 external memory | `mind/reasoner.py`, `chat/brain_chat.py`, `bl_advanced.py` | grow-by-teaching, persistent recall, k-NN episodic |
| M5 predictive world model | `predictive_coding_brain.py` | free energy ↓17× (perception = inference) |
| M6 local learning, no forgetting | `bl_deep_local.py`, `bl_advanced.py` | **96.9% MNIST no backprop**; one-shot new class, old kept ~0.95 |
| M10 few-shot / meta | `bl_advanced.py` | learns a category from 1–30 examples |
| M13 symbolic + self-verify | `mind/reasoner.py` | exact verified math; refuses to bluff |
| §1.2 efficient sequence core | `bl_language_fast.py` | parallel-scan oscillator + sparse attention, fluent text |

Seven of the thirteen mechanisms have running code. The gaps (M2 dynamic weights,
M8 compute market, M11 curiosity, M12 planner) are the explicit build queue.

---

## Part VI — Honest risks and open problems

1. **The skill-core floor (biggest risk).** Language/reasoning skill still needs
   real scale+data; "1000× everything" is not established. Mitigation: measure
   knowledge-vs-skill separately; carry knowledge in M3.
2. **Composition risk.** Each mechanism is individually supported; their *product*
   at scale is unproven. Mitigation: the ablation ladder (§4.5) — validate each
   increment, kill what doesn't pay (we already killed learned V1 filters when they
   gave no gain — honest negatives are part of the method).
3. **Dynamic weights (M2) stability/serving.** Generating weights per token is
   powerful but training-unstable and hardware-awkward. Mitigation: low-rank, slow-
   weight anchor, generate only per-context not per-token.
4. **Local learning at LLM depth.** Matched backprop on MNIST; scaling local rules
   to deep language models is open (active literature).
5. **Symbolic coverage.** Not everything is symbolically checkable; confidence must
   distinguish *verified* from *asserted* (already the case in The Mind).

---

## Part VII — Build roadmap (from here)

1. **Language front-end (direction 3):** a small router (our `bl_language_fast`
   core) that turns free English/Arabic into typed tool calls for The Mind — the
   "language cortex" over the verified reasoning core.
2. **M2 dynamic weights:** a hypernetwork emitting per-context low-rank updates on
   the small core — the highest-upside unbuilt idea.
3. **M8 compute market:** one controller metering depth/experts/retrieval/deliberation.
4. **M11 curiosity + M12 planner:** gap-seeking data selection and model-based
   recursive planning.
5. **Consolidation (M6 sleep):** periodic distillation of hot episodic memory into
   the core.

Each step is laptop/workstation-scale and validated before the next — transistor
by transistor, not one giant leap.

---

### Closing

AXIOM is not a transformer with biological labels. It is a different decomposition
of intelligence: **skills in a small sparse predictive core, facts in expandable
memory, weights generated on demand, computation only on surprise, reasoning by
modular collaboration and symbolic verification, learning continuously and locally.**
The parts that can be tested on a laptop today already work and are measured here.
The claim is disciplined: enormous efficiency on the axes the brain exploits —
*not* magic, and every remaining hard problem is named rather than hidden.
