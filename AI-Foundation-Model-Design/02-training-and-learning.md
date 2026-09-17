# 2. Training Pipeline, Data Strategy, and Learning System

---

## 2.1 Data strategy: quality-weighted, skill-targeted, retrieval-aware

**State of the art.** Web-scale crawls (~15T tokens) with heuristic + model-based
filtering (FineWeb-Edu class); synthetic textbooks (phi class); heavy dedup.

**Why inefficient.** Chinchilla-optimal training treats all tokens as equal; measured
per-token utility varies by >100×. Most web text teaches facts the retrieval tier will
hold anyway (W2), so training on it to memorization is wasted gradient.

**Pipeline.**
1. **Corpus tiers.** T0: curated reasoning-dense data (textbooks, code with tests, math
   with solutions, high-quality QA) ~1T tokens. T1: filtered web ~5T. T2: everything else
   → **not trained on; ingested into the M2 retrieval index instead.** This is the
   overhang exploit: data that current practice burns compute memorizing becomes a
   zero-training-cost knowledge asset.
2. **Value-weighted sampling.** Per-document influence proxy (small-model loss delta on a
   held-out skill suite) sets sampling weight; re-estimated as training progresses
   (online data curriculum).
3. **Synthetic data with verification-gating.** Self-generated math/code/reasoning data is
   admitted *only if it passes symbolic verification* (unit tests, CAS, proof checker) —
   the typed workspace (§1.7) makes generation-with-guarantees natural. Verified-only
   synthetic data avoids the model-collapse failure mode of raw self-training.
4. **Curriculum.** Ordered by measured difficulty (small-model perplexity percentile ×
   reasoning-depth estimate): short/clean → long/multi-step → adversarial/flawed (for
   the Critic). Curriculum interacts with the recursive block: loop counts are annealed
   upward as harder data arrives, teaching "more iterations = harder problems."

## 2.2 Training stages

```
Stage A  Backbone pretraining          ~5T tokens, retrieval ON from step 0
Stage B  Conditional-compute fitting    gates/MoD/recursion trained under shared λ (§1.6)
Stage C  Deliberation training          SFT on typed traces → RL with verifier rewards
Stage D  Preference + calibration       DPO/RLHF + confidence-calibration loss
Stage E  Distillation & quantization    QAT to FP8/INT4; self-distill fast path (§3.4)
```

Stage C detail (the reasoning-quality engine): reinforcement learning where the reward is
**verifier-graded**, not preference-graded — a `Program` that passes tests, a `Claim`
whose citation entails it, a `ProofStep` the checker accepts. Process-level reward comes
free from the typed trace (each object is individually checkable), avoiding the known
instability of outcome-only RL on long traces. The Critic is trained adversarially on
mined + synthesized flawed traces (GAN-flavored: Proposer tries to sneak errors past a
Critic that is simultaneously trained to catch them).

## 2.3 Skill/knowledge factorization loss (novel)

Goal: force facts out of weights (into retrieval) and skills into weights.

For token t with retrieval available, let p_open = model with retrieval, p_closed = same
model with retrieval gates masked. Training loss:

```
L = CE(p_open, y)  +  α · max(0, log p_closed(y) − log p_open(y))     (conflict term)
      +  β · Σ_{t ∈ RetrievableFacts} log p_closed(y_t)               (anti-memorization)
```

- The conflict term punishes the closed-book path for *overriding* retrieval (mitigates
  knowledge-conflict hallucination).
- The anti-memorization term applies only to spans tagged (by an auxiliary classifier) as
  retrievable atomic facts — entity attributes, dates, figures — and *maximizes* their
  closed-book loss, i.e., actively discourages weight-memorization of them. Skills
  (syntax, composition, algorithmic patterns) are untagged and learned normally.

Risk: β too high degrades fluency on entity-dense text; tune on a knob of closed-book vs
open-book factual-QA gap. Fallback: β=0 recovers standard retrieval-augmented training
(RETRO-class, already a proven win).

## 2.4 Continual learning without catastrophic forgetting

**State of the art.** Full fine-tuning (forgets); LoRA per task (adapter zoo, no
composition); replay buffers; EWC/regularization (weak at scale); MoE expert-addition.

**Selected design — three mechanisms, matched to three timescales:**

1. **Seconds–days (no gradients): memory-based learning.** New facts/preferences/lessons
   are *written to episodic memory M1* (§3.2) and used via retrieval immediately. Most
   "learning" in deployment needs no weight change at all — this is the cheapest and
   safest tier, and it is inherently forgetting-free.
2. **Weeks (localized gradients): expert growth.** New domains → spawn fresh MoE experts
   (initialized from nearest existing experts) + extend router; old experts frozen.
   Because FFN experts are the knowledge-adjacent units, growth adds capacity where it's
   needed at zero interference cost. Capacity control: prune experts whose routing mass
   stays < ε for a full cycle (safe forgetting of redundant capacity).
3. **Months (consolidation): memory-consistency distillation (novel).** Periodically,
   high-value episodic memories (frequently retrieved, verifier-confirmed) are converted
   to training data and distilled into new experts / the semantic index, with the *old
   model as teacher on old-skill data* (self-distillation replay) to pin prior behavior:

   ```
   L_consol = CE(new data) + γ · KL( p_new(·|x_old) ‖ p_old(·|x_old) ),  x_old ~ replay+self-gen
   ```

   This is the sleep-consolidation analog: episodic → semantic transfer with rehearsal.

Forgetting audit: a frozen capability benchmark suite runs after every update; any
regression > 1σ blocks the release of that update (see §4.2).

## 2.5 Few-shot and meta-learning

The backbone's in-context learning is the meta-learner (transformers already implement
gradient-descent-like adaptation in context). ATLAS strengthens it:
- **Meta-training episodes** in the data mix: (support set → query) formatted tasks, so
  ICL is an explicitly trained skill rather than a byproduct.
- **ICL → memory persistence:** what a session "learned in context" is summarized by the
  Reflector into M1 at session end, so few-shot adaptation *persists* (fixes W4). Next
  session, retrieval reloads it — few-shot learning with one-shot cost.

## 2.6 Active learning and gap detection

The model detects its own knowledge gaps from live signals it already computes:
- retrieval queries with low hit scores (missing knowledge in M2),
- verifier failures clustered by topic (broken skills),
- high-entropy answers with high user-correction rates.

Gap reports are ranked by query frequency × failure severity and drive: (a) targeted M2
index expansion (cheap), (b) targeted synthetic-data generation with verification gating
(medium), (c) expert growth (expensive). The compute market philosophy again: spend the
cheapest remedy that closes the gap. This closes the autonomous-improvement loop:
**detect → prioritize → acquire/generate → verify → consolidate → audit.**

## 2.7 Training-compute estimate

Stage A dominates. FLOPs ≈ 6 · N_active · D = 6 · 13e9 · 6e12 ≈ 4.7e23 — roughly the
compute of a dense 13B trained on 6T tokens, i.e. **~15–25× less than a dense frontier
run**, while the quality target is carried by (i) 148B total sparse capacity, (ii)
retrieval offloading, (iii) data curation, (iv) test-time compute on hard queries. The
honest caveat: (ii)–(iv) multipliers are supported by published point results (RETRO,
phi, o1-class scaling) but their *composition* is unproven; §4.5 treats this as the top
research risk.
