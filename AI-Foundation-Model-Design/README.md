# Project ATLAS — A Next-Generation Efficient Foundation Model Blueprint

**A**daptive **T**iered **L**earning **A**rchitecture with **S**parse reasoning.

This directory contains a complete research blueprint for a foundation model designed to
approach frontier-model reasoning quality at a fraction of the compute, by replacing the
dense monolithic transformer with a modular, sparse, memory-augmented, self-verifying
system.

> **Honest framing:** this is a *design document*, not a proof. Every mechanism here is
> either (a) demonstrated in published literature, (b) a principled extrapolation with the
> math shown, or (c) explicitly flagged as speculative. Building a frontier-competitive
> model still requires serious data, engineering, and training compute — the claim is a
> large *constant-factor and asymptotic* efficiency improvement, not magic.

## Contents

| File | Contents |
|---|---|
| [`01-architecture.md`](01-architecture.md) | Weaknesses of current transformers, subsystem-by-subsystem design, architecture diagram, mathematical formulation |
| [`02-training-and-learning.md`](02-training-and-learning.md) | Training pipeline, data strategy, continual/meta/active learning, self-improvement loop |
| [`03-inference-memory-hardware.md`](03-inference-memory-hardware.md) | Inference pipeline, hierarchical memory system, CPU/GPU optimization, quantization |
| [`04-evaluation-deployment-roadmap.md`](04-evaluation-deployment-roadmap.md) | Benchmarks, deployment plan, open-source roadmap, risks and mitigations, future research |
| [`05-brain-native-redesign.md`](05-brain-native-redesign.md) | **Brain-native redesign (codename CORTEX):** spiking neurons, predictive coding / free energy, complementary learning systems, oscillatory phase codes, neuromodulation, global workspace, self-organized criticality — the real neuroscience and math/physics for each |
| [`prototype/`](prototype/) | **Working, runnable code.** Three prototypes: a physics-grounded sequence mixer, a brain-native (no-backprop) learner, and **BL** — a brain-like model that learns real handwritten digits. See [`prototype/RESULTS.md`](prototype/RESULTS.md) |

## Runnable prototype (laptop-scale)

`prototype/selective_oscillatory_memory.py` implements the §1.2 physics-structured
recurrence from scratch and demonstrates its core property on a laptop CPU in ~3–4 min:

```bash
pip install numpy && python3 prototype/selective_oscillatory_memory.py
```

Result: on a pure long-range memory task (T=120), the oscillatory mixer reaches **MSE
0.0017** while an equal-size vanilla RNN stays stuck at the **0.337** forgetful baseline —
because the oscillator physics keeps gradients-through-time `O(1)` (measured: 61× vs the
RNN's `3e-5`).

`prototype/predictive_coding_brain.py` backs the brain-native redesign (§5): a
**predictive-coding** network that learns with **only local updates — no backpropagation**
(the brain can't do backprop). On a nonlinear classification task it reaches **100% test
accuracy, matching a backprop MLP of identical size**, and its free energy falls ~17× as
"perception" settles.

```bash
python3 prototype/predictive_coding_brain.py
```

`prototype/bl_brain_model.py` is **BL** — a Brain-Like model that does real ML on real
handwritten digits (scikit-learn `digits`), assembling the brain-native mechanisms into one
runnable system: sparse event-driven coding (only 8% of neurons active), a neocortex that
learns by a **local rule with no backprop** (96.6% test accuracy), and a hippocampal
one-shot memory. It demonstrates three things standard nets do badly:

- **few-shot learning** — 58% from 1 example/class, 92% from 30;
- **one-shot learning of a brand-new class** — learns digit 9 from ~10 examples (0→87%) while a backprop net stays at 0%;
- **no catastrophic forgetting** — old digits stay at ~0.96 after adding the new class.

```bash
pip install numpy scikit-learn && python3 prototype/bl_brain_model.py
```

`prototype/bl_torch.py` is the **GPU version** of BL: the same brain design in PyTorch
with a fixed **V1 visual-cortex** front-end (random edge filters + pooling), auto-detecting
an NVIDIA GPU and scaling to **full MNIST**. It reaches **98.2% test accuracy with no
backpropagation** (local learning only), plus few-shot and one-shot new-class learning
without forgetting. Falls back to CPU / the digits dataset when a GPU or MNIST isn't available.

```bash
pip install torch torchvision && python3 prototype/bl_torch.py
```

`prototype/bl_advanced.py` adds an **episodic hippocampus** (multiple stored memories per
class + k-NN recall, like the real hippocampus) and runs on **MNIST or Fashion-MNIST**.
It improves few-shot/one-shot over a single prototype, and on Fashion-MNIST learns a new
visually-distinct class one-shot to **97%** — all still with no backpropagation. (Learning
the V1 filters was tested and gave no gain at this scale, so it was deliberately left out —
a documented negative result.)

```bash
python3 prototype/bl_advanced.py     # set DATASET = "mnist" or "fashion"
```

`prototype/bl_deep_local.py` is the strongest brain-native learning result: a **deep
network (784-400-150-10) that learns MNIST with NO backpropagation** — only local
predictive-coding updates. With momentum it reaches **96.9% — backprop-class accuracy** —
learning its own hidden features with no backward pass and no weight transport. This
scales the section-5.2 claim from a toy task to real images.

```bash
python3 prototype/bl_deep_local.py
```

`prototype/bl_system.py` is the **whole brain-like stack in one model**: V1 vision → a deep
local-learning neocortex (no backprop) → an episodic hippocampus. One model does learned
deep vision, one-shot new classes, and no catastrophic forgetting (MNIST or Fashion-MNIST).

`prototype/bl_language.py` steps toward **language**: a character-level model built on the
oscillatory memory cell (with learnable per-neuron dynamics) that reads text and learns to
**generate coherent English** (loss ~0.09).

```bash
python3 prototype/bl_system.py       # the full stack
python3 prototype/bl_language.py     # the oscillatory language model
```

Full write-ups, including honest limitations and negative results, in
[`prototype/RESULTS.md`](prototype/RESULTS.md).

## Design thesis in one paragraph

Dense transformers are inefficient because they (1) spend identical compute on every token
regardless of difficulty, (2) store all world knowledge in weights that must be touched on
every forward pass, (3) recompute reasoning from scratch on every query with no persistent
memory, and (4) have no internal mechanism to check their own outputs, forcing scale to
substitute for verification. ATLAS attacks each: **conditional computation** (hierarchical
mixture-of-experts + early exit + dynamic depth) so compute scales with difficulty;
**retrieval-first knowledge** (a small parametric core + large external memory) so
parameters store *skills*, not *facts*; **hierarchical persistent memory** (working /
episodic / semantic tiers) so the model learns continuously without retraining; and a
**deliberation layer** (proposer–critic–verifier modules over a shared latent workspace)
so extra test-time compute is spent only where it buys accuracy, with verifiable
intermediate artifacts (programs, proofs, citations) instead of unauditable chains of
thought.

## Headline efficiency targets (with the reasoning behind them)

| Target | Mechanism | Basis |
|---|---|---|
| ~10× fewer *active* parameters per token vs. dense peer | Fine-grained MoE (top-2 of 64 experts per layer) + shared backbone | Mixtral/DeepSeek-V3 show sparse models match dense models ~5–10× their active size |
| ~5–20× less pretraining compute for equal downstream skill | Retrieval offloads factual memorization; curriculum + synthetic-data filtering raises tokens-per-skill efficiency | RETRO matched GPT-3-class perplexity with 25× fewer params; phi-series shows data quality ≫ data volume |
| O(n) prefill, O(1) per-token decode memory for long context | Hybrid SSM/linear-attention backbone with sparse global attention every k layers | Mamba-2/Jamba/Griffin-class results |
| Continual learning without forgetting | Frozen core + expert growth + episodic replay from memory tiers | Standard PEFT/expansion + replay results; flagged assumptions in §2 |
| Latency: <100 ms first token on a single consumer GPU (7B-active class) | Speculative decoding against the model's own fast path + INT4/FP8 kernels | Established engineering, no research risk |

## What is genuinely novel here (vs. assembled from literature)

1. **Difficulty-priced compute market** — a learned scheduler allocates a *compute budget
   token* per query; every conditional mechanism (depth, experts, retrieval, deliberation
   rounds) bids against it. One global controller instead of many uncoordinated gates. (§1.6)
2. **Skill/knowledge factorization objective** — an explicit training loss that *penalizes*
   the parametric core for memorizing retrievable facts, forcing knowledge into the
   retrieval tier and skills into weights. (§2.3)
3. **Typed latent workspace** — reasoning modules exchange structured, typed objects
   (claims, programs, proofs, plans) rather than free text, making the debate loop
   checkable by cheap symbolic verifiers. (§1.7)
4. **Memory-consistency distillation** — the model is periodically distilled against its
   own episodic memory to consolidate durable knowledge into semantic memory/weights,
   an explicit analog of sleep consolidation. (§2.5)

Items 1–4 are speculative to varying degrees; each section states the risk and a fallback.
