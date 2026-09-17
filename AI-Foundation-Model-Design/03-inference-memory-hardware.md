# 3. Inference Pipeline, Memory Architecture, and Hardware Optimization

---

## 3.1 Inference pipeline

```
query
  │
  ├─► difficulty estimator (§1.6) ── sets budget B, prices, λ knob
  │
  ├─► retrieval controller: query M1 (episodic) + M2 (semantic) if budget/uncertainty warrants
  │
  ├─► BACKBONE fast path (System 1)
  │     • MoD skips easy tokens
  │     • MoE top-2 routing
  │     • early-exit when converged
  │     └─► candidate answer + per-token uncertainty
  │
  ├─► escalation test: if uncertainty·B above threshold → engage recursion / deliberation
  │
  ├─► DELIBERATION (System 2, budgeted): Plan → Propose → Critique → Verify(tools) → Revise
  │     └─► verified answer + citations + confidence + trace
  │
  ├─► Reflector: write durable lessons/facts to M1
  │
  └─► output
```

The escalation test is the latency lever: ~80% of real traffic (easy/lookup queries) exits
at the fast path in tens of milliseconds; only hard queries pay System-2 cost. Average
latency ≈ fast-path latency; tail latency scales with genuine difficulty — the desired
profile.

## 3.2 Hierarchical memory architecture

Modeled on the human memory hierarchy; each tier has distinct capacity, write cost, and
persistence.

| Tier | Analog | Substance | Persistence | Write cost | Read cost |
|---|---|---|---|---|---|
| **M0 working** | working memory | SSM recurrent state + rolling KV cache (cross-layer shared) | current sequence | free (forward pass) | free |
| **M1 episodic** | episodic/hippocampal | per-user/session vector store of turns, lessons, corrections, subgoal solutions | session→persistent | cheap (embed+insert) | ANN lookup |
| **M2 semantic** | semantic/cortical | curated global KB + web/tool corpora, dense+sparse hybrid index, graph edges | durable, versioned | offline indexing | ANN + graph walk |
| **weights** | procedural/skill | MoE experts, backbone | very durable | training only | forward pass |

Design details:
- **M0** is bounded by construction (SSM state O(1), KV cache cross-layer-shared and
  sliding) — long context does not blow up memory (fixes W3).
- **M1** enables cross-session continual learning with *no gradient step* (§2.4 tier 1).
  Entries carry provenance, timestamp, verifier-confirmation flag, and retrieval-frequency
  counter (drives consolidation, §2.5). Privacy: per-user M1 is isolated and
  user-deletable — memory is data, not weights, so "forget me" is a delete, not a retrain.
- **M2** is a **graph-augmented** store (GraphRAG-style): nodes = entity/claim chunks,
  edges = relations, enabling multi-hop graph-based reasoning (the Planner walks the graph
  for chains of evidence). Hybrid dense+BM25 retrieval; results re-ranked by a small
  cross-encoder before injection.
- **Consolidation path** M1→M2→weights is §2.5 (the sleep analog).

Retrieval is *gated cross-attention* into the backbone (§1.4), not context stuffing, so
retrieved volume doesn't inflate the attention budget.

## 3.3 Hardware optimization strategy

Design principle: sparsity is only a win if it is *hardware-realizable*. Each mechanism is
chosen for GPU/CPU friendliness.

**GPU.**
- MoE: expert-parallel across devices; grouped-GEMM kernels; capacity chosen so expert
  batches are GEMM-efficient; loss-free balancing keeps utilization even (no straggler
  experts). Communication hidden with compute (DeepSeek DualPipe-style overlap).
- SSM layers: hardware-aware selective-scan kernel (Mamba-2 chunked form → matmul-heavy,
  Tensor-Core-friendly). Cross-layer KV sharing cuts HBM traffic ~6×, the real decode
  bottleneck.
- Sparse global attention: block-sparse top-k with contiguous gathers (NSA-style),
  avoiding random-access memory patterns.
- Precision: FP8 (E4M3) for GEMMs via QAT (§3.5); BF16 master weights; FP32 for router
  logits, layernorm, SSM state accumulation (stability-critical).

**CPU / edge.**
- MoE + conditional compute is a *natural* fit for memory-bandwidth-limited CPUs: only
  active experts are loaded. Cold experts memory-mapped from INT4 storage, paged on demand
  (routing is predictable enough to prefetch).
- SSM decode is O(1)-state → no growing KV cache → constant memory, ideal for long-running
  edge/CPU sessions.
- The fast path alone (backbone, no deliberation) targets a 13B-active/INT4 ≈ 7GB
  footprint — runnable on a laptop or single consumer GPU.

**Energy.** Per-query energy ∝ active FLOPs × difficulty. The compute market's λ knob is
directly an energy-per-query dial. Idle-token skipping (MoD) and early-exit cut the
dominant everyday-traffic energy; System-2 energy is spent only where correctness demands.

## 3.4 Latency: speculative decoding against the model's own fast path

The backbone's early-exit (§1.5) yields a *free draft model*: exit at layer L/3 to draft,
verify with the full model in one parallel pass (self-speculative decoding, ~2–3× decode
speedup, zero extra params, provably identical output distribution). Combined with:
- continuous batching + paged KV,
- FP8/INT4 kernels,
- retrieval/deliberation only on hard queries,

the target is <100 ms first token and interactive throughput on a single consumer GPU for
the fast path.

## 3.5 Neural compression, quantization, distillation, LoRA

- **Quantization-aware training (Stage E):** train with simulated FP8 forward + INT4
  weight quantization so accuracy is retained at deployment precision (post-hoc PTQ loses
  more). Per-channel/group scales; keep sensitive tensors (router, SSM state) high
  precision.
- **Knowledge distillation:** two roles — (a) *self-distillation* to sharpen the fast path
  using the full deliberation pipeline as teacher (bake common System-2 conclusions into
  System-1); (b) *consolidation distillation* (§2.5).
- **Low-rank adaptation:** LoRA/DoRA is the deployment-time customization primitive —
  per-tenant behavioral adapters that compose with the frozen core; distinct from expert
  growth (which adds capacity) — LoRA adapts *style/policy* cheaply and reversibly.
- **Neural compression of memory:** M1 entries are stored as compressed latent summaries
  (learned autoencoder) rather than raw text, trading a small recall loss for large
  storage/bandwidth savings; hot entries kept in full fidelity.
