# 4. Evaluation, Deployment, Roadmap, Risks, Future Work

---

## 4.1 Evaluation benchmarks

Because the value proposition is *efficiency at fixed quality*, every quality benchmark is
paired with a cost axis (active FLOPs/query, latency, energy). Report Pareto frontiers,
not single numbers.

**Reasoning & knowledge:** MMLU-Pro, GPQA-Diamond (science), MATH / AIME (math),
LiveCodeBench / SWE-bench Verified (coding), BIG-Bench-Hard, ARC-AGI (fluid reasoning),
FrontierMath (hard math, expect low but track).

**Efficiency (the differentiator):**
- Quality per active-FLOP and per-joule vs. dense baselines at equal quality.
- Test-time-compute scaling curves: accuracy vs. budget B (should rise smoothly — the core
  claim of §1.5–1.7).
- Latency: TTFT and tokens/s on fixed hardware (1× consumer GPU, 1× CPU node).

**Memory & continual learning:**
- Long-context recall: RULER, needle-in-haystack to 1M tokens (tests §1.2 + M0).
- Continual-learning suite: sequential domain acquisition with a **forgetting metric**
  (backward transfer) — the §2.4 audit gate.
- Cross-session persistence: does a fact taught in session 1 survive to session 50 (M1)?

**Factuality & honesty:** SimpleQA / long-form factuality with citation-precision and
citation-recall (retrieval must actually support claims); calibration (ECE) — a verified,
citation-backed model should be *well-calibrated*, a headline claim.

**Reasoning transparency:** fraction of final claims that are tool-verified; faithfulness
of the trace to the actual computation (perturbation tests).

**Data efficiency:** few-shot learning curves; performance vs. pretraining tokens against
dense baselines (the §2.7 claim).

## 4.2 Release gating

No checkpoint ships unless: (1) no capability-suite regression > 1σ (forgetting gate),
(2) calibration ECE below threshold, (3) citation-precision above threshold on factual
eval, (4) red-team safety suite passed (§4.4). Automated, in CI.

## 4.3 Deployment plan

- **Tiered serving.** One model, three λ presets (fast / balanced / thorough) exposed as
  API params; enterprise can set per-request budgets and hard latency caps.
- **Disaggregated prefill/decode** (prefill compute-bound, decode memory-bound) on
  separate pools; MoE experts sharded expert-parallel; retrieval index on a co-located
  vector-DB service.
- **Edge SKU.** Backbone-only + INT4 + local M1, no cloud dependency for the fast path;
  optional cloud escalation for System-2. On-device continual learning via M1 (no
  gradient), preserving privacy.
- **Memory as a service.** Per-tenant M1/M2 with isolation, versioning, and
  right-to-be-forgotten by deletion (not retraining) — a compliance advantage of
  retrieval-first design.
- **Observability.** Every response logs budget spent, experts fired, retrieval hits,
  verifier outcomes → feeds gap detection (§2.6) and cost accounting.

## 4.4 Risks and mitigations

| Risk | Severity | Mitigation |
|---|---|---|
| **Composition risk:** the efficiency multipliers (sparse + retrieval + curriculum + TTC) don't stack as hoped; real gain < projected. | High | Each is individually proven; ablate incrementally (§4.5). Even the *worst case* (only MoE sparsity holds) is a solid 3–5× win. Business case must survive that floor. |
| Routing/gating training instability (§1.6 joint optimization). | High | Stage-wise fallback reduces to published-stable recipes; joint training is upside, not a dependency. |
| MoE serving complexity / expert-imbalance stragglers. | Med | Loss-free balancing; capacity factors; grouped GEMM; mature (Mixtral/DeepSeek in production). |
| Retrieval poisoning / prompt injection via M1/M2. | High (security) | Provenance + trust scores on sources; verifier cross-checks; per-tenant memory isolation; treat retrieved text as untrusted data, never instructions. |
| Verifier gap: not all claims are symbolically checkable; verifier gives false confidence on unverifiable claims. | Med | Confidence output *distinguishes* verified vs. asserted claims; never report unverified as verified. |
| Model collapse from self-generated training data. | Med | Verification-gated synthetic data only (§2.1); always mix real data; monitor diversity metrics. |
| Catastrophic forgetting despite §2.4. | Med | Hard release gate (§4.2); memory-tier learning avoids gradients for most updates. |
| Memory privacy leakage across tenants. | High | Strict M1 isolation, encryption at rest, deletion semantics, no cross-tenant retrieval. |
| **Dual-use / autonomous self-improvement** (§2.6 loop). | High (safety) | The improvement loop is *gated by human-reviewed release (§4.2)*, not closed-loop deployment; verifier + audit in the loop; capability evals with pause thresholds; no autonomous weight updates in production. |
| Efficiency used to lower the cost of misuse. | Policy | Standard usage policy, safety RLHF (Stage D), abuse monitoring; this is a general-purpose-model risk, handled at the deployment layer. |

## 4.5 Ablation-first validation plan (de-risking the composition claim)

Validate the thesis cheaply *before* a full run, at ~1–3B active scale:

1. Backbone only (hybrid SSM/attn) vs. dense transformer — confirm equal quality, lower
   long-context memory. (Tests §1.2.)
2. + MoE — confirm ~10× total/active ratio at equal quality. (Tests §1.3.)
3. + retrieval & factorization loss — confirm factual quality holds with fewer params;
   measure closed-book memorization drop. (Tests §1.4, §2.3.)
4. + conditional compute — confirm TTC scaling curve rises smoothly; measure FLOPs saved
   on easy traffic. (Tests §1.5–1.6.)
5. + deliberation — confirm verified-reasoning accuracy gains on MATH/code at fixed budget
   vs. long-CoT baseline. (Tests §1.7.)
6. Continual-learning + memory persistence over a task stream. (Tests §2.4, §3.2.)

Each step has a *kill criterion*: if the projected multiplier fails to materialize at
small scale, cut that mechanism before it costs a large run. This is the core discipline —
the design is modular precisely so it can be validated and de-risked piecewise.

## 4.6 Open-source implementation roadmap

| Phase | Deliverable | Reuses (overhang) |
|---|---|---|
| P0 | Reference impl of hybrid SSM/attn backbone + eval harness | `mamba`, `flash-attn`, `lm-eval-harness` |
| P1 | Fine-grained MoE + loss-free balancing + grouped-GEMM kernels | Megablocks, DeepSeek kernels |
| P2 | Retrieval-native training + factorization loss; vector/graph memory service | FAISS/ScaNN, a graph store |
| P3 | Conditional compute (MoD, recursion, early-exit) + compute-market controller | CALM, MoD reference code |
| P4 | Typed deliberation layer + symbolic tool bridges (exec sandbox, CAS, SMT, proof checker) | Z3, SymPy, Lean, firejail |
| P5 | Continual-learning + consolidation + gap-detection loop | — (novel) |
| P6 | Quantization/distillation/serving stack; edge SKU | vLLM/SGLang, TensorRT-LLM, llama.cpp |

Bootstrap strategy: **start from a strong open-weights dense model, don't pretrain from
zero.** Up-cycle it into the MoE (initialize experts from the dense FFN — proven
"sparse-upcycling"), graft on retrieval cross-attention (zero-init gates), and distill the
deliberation behavior. This exploits the *model overhang* directly: buy the base
capability, spend the compute budget only on the new efficiency machinery.

## 4.7 Future research directions

1. **Byte-latent tokenization** integrated with retrieval chunking (§1.9-1).
2. **Parallel/diffusion decoding** to break autoregressive serialization (§1.9-3).
3. **Learned symbolic representations** — let the model *invent* the type system of the
   workspace (§1.7) rather than hand-designing it.
4. **True online RL in deployment** with safety guarantees — currently gated to offline
   (§4.4); the research question is provably-safe closed-loop improvement.
5. **Better-than-backprop credit assignment** at scale (§1.9-2).
6. **Analog/neuromorphic execution of SSM layers** — the O(1)-state recurrence maps
   naturally to in-memory-compute hardware; potential order-of-magnitude energy win.
7. **Mechanistic verification** — prove properties of the typed traces, moving from
   empirical to formal transparency.

---

## Closing note on intellectual honesty

This blueprint composes mechanisms that are, individually, established in the literature
(hybrid SSM/attention, fine-grained MoE, retrieval-native training, conditional compute,
verifier-graded reasoning, memory hierarchies) with four flagged novel pieces (compute
market §1.6, factorization loss §2.3, typed workspace §1.7, consolidation distillation
§2.5). The efficiency claims for the *individual* mechanisms are grounded; the aggregate
claim depends on their **composition**, which is unproven and is explicitly the top risk
(§4.4) with a concrete de-risking plan (§4.5). No mechanism here violates known physical
or mathematical constraints. Building this to frontier parity still requires substantial
data, engineering, and compute — the contribution is a coherent path to spending far less
of each for the same reasoning quality.
