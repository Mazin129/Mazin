# 1. Architecture

This section follows the required research process for each subsystem: state of the art →
why it is inefficient → alternatives → mathematical comparison → selected design.

---

## 1.0 Fundamental weaknesses of the dense transformer

Before designing subsystems, name the enemies precisely.

| # | Weakness | Cost it imposes |
|---|---|---|
| W1 | **Uniform compute per token.** Every token, trivial or hard, passes through all L layers and all parameters. | For a dense model, FLOPs/token ≈ 2·N (N = params). Difficulty of tokens varies by orders of magnitude; average compute is set by the hardest case. |
| W2 | **Knowledge stored in weights.** Facts are baked into the FFN layers (which hold ~2/3 of params) and can only be updated by retraining. | Parameters scale with *facts known*, not *skills possessed*. Stale knowledge, hallucination when the weight-lookup misses. |
| W3 | **Quadratic attention.** Softmax attention costs O(n²·d) time and O(n·d) KV-cache memory per layer. | Long context is memory-bound; a 128k-context 70B model needs tens of GB of KV cache alone. |
| W4 | **No persistent state across sessions.** Each query starts from zero; in-context learning is recomputed and then discarded. | Compute is spent re-deriving what the model already "learned" an hour ago. |
| W5 | **No self-verification.** The forward pass is a single sample from a policy with no internal error-checking; correctness comes only from scale and RLHF. | Test-time compute (long CoT) is spent blindly — the model cannot tell which reasoning steps need checking. |
| W6 | **Catastrophic forgetting.** Gradient updates on new data overwrite old capabilities because storage is fully distributed. | Continual learning requires full retraining or accepting degradation. |
| W7 | **Opaque reasoning.** Chain-of-thought text is a rationalization channel, not an inspectable program; there is no typed intermediate representation. | Verification must be done by another LLM at similar cost; errors compound. |

ATLAS assigns one or more subsystems to each weakness. The map:

- W1 → §1.5 (conditional depth/width), §1.6 (compute market)
- W2 → §1.4 (retrieval-first knowledge), §3.2 (memory tiers)
- W3 → §1.2 (hybrid sequence mixer)
- W4 → §3.2 (hierarchical memory), §2.5 (consolidation)
- W5, W7 → §1.7 (deliberation layer, typed workspace)
- W6 → §2.4 (continual learning)

---

## 1.1 System overview (architecture diagram)

```
                              ┌────────────────────────────────────────────────┐
                              │              COMPUTE MARKET (§1.6)             │
                              │  difficulty estimator → budget B per query     │
                              │  all conditional mechanisms bid against B      │
                              └───────┬────────────────────────────────────────┘
                                      │ budget signals
  ┌───────────────────────────────────┼─────────────────────────────────────────┐
  │                                   ▼                                         │
  │   INPUT ──► Tokenizer ──► ┌─────────────────┐      ┌───────────────────┐    │
  │   (text/code/            │  CORE BACKBONE   │◄────►│  MEMORY SYSTEM    │    │
  │    structured)           │  (§1.2–1.5)      │      │  (§3.2)           │    │
  │                          │                  │      │                   │    │
  │                          │  N blocks of:    │      │  M0 working (KV/  │    │
  │                          │   • SSM mixer ×5 │      │      SSM state)   │    │
  │                          │   • sparse global│      │  M1 episodic      │    │
  │                          │     attention ×1 │      │     (session/user │    │
  │                          │   • fine-grained │      │      vector store)│    │
  │                          │     MoE FFN      │      │  M2 semantic      │    │
  │                          │   • early-exit   │      │     (curated KB + │    │
  │                          │     heads        │      │      web/RAG)     │    │
  │                          └───────┬──────────┘      └───────────────────┘    │
  │                                  │ latent states                            │
  │                                  ▼                                          │
  │                     ┌──────────────────────────┐                            │
  │                     │  DELIBERATION LAYER §1.7 │   (engaged only when       │
  │                     │  typed latent workspace  │    budget B is high)       │
  │                     │  ┌────────┐ ┌─────────┐  │                            │
  │                     │  │Proposer│ │ Planner │  │                            │
  │                     │  └───┬────┘ └────┬────┘  │                            │
  │                     │  ┌───▼────┐ ┌────▼────┐  │                            │
  │                     │  │ Critic │ │Verifier │──┼──► symbolic tools:         │
  │                     │  └───┬────┘ └────┬────┘  │    code exec, SMT/CAS,     │
  │                     │      └─── debate ┘       │    retrieval fact-check    │
  │                     └────────────┬─────────────┘                            │
  │                                  ▼                                          │
  │                        OUTPUT + confidence + citations + trace              │
  └──────────────────────────────────────────────────────────────────────────────┘
```

Key property: the **backbone alone** is a complete fast-path model (System 1). Memory,
deliberation, and tools are *optional escalations* purchased with budget (System 2).

---

## 1.2 Sequence mixer (replacing quadratic attention)

**State of the art.** Softmax attention (GPT/Llama class); sliding-window attention
(Mistral); linear attention (Performer, GLA); state-space models (Mamba-2); hybrids
(Jamba, Griffin, Zamba: mostly-SSM with periodic full attention).

**Why current SOTA is inefficient.** Pure softmax: O(n²) prefill, O(n) per-token decode
memory (W3). Pure SSM/linear: O(n) prefill, O(1) decode state, but a *fixed-size* state
provably cannot support exact random-access recall over long contexts (needle tasks,
in-context copying degrade).

**Alternatives compared.** Let n = sequence length, d = model width, w = window, k = ratio
of attention layers.

| Design | Prefill time | Decode state | Exact recall |
|---|---|---|---|
| A. Full softmax | O(n²d) | O(n·d) per layer | ✔ |
| B. Pure SSM (Mamba-2) | O(n·d²ᵣ) (r = state expansion) | O(d·r) | ✖ (lossy) |
| C. Sliding window + a few global layers | O(n·w·d) | O(w·d) local + O(n·d) global layers | ✔ (via global) |
| D. SSM backbone + 1-in-6 sparse global attention | O(n·d²ᵣ + (n²/6)·s·d), s = sparsity | O(d·r)·5/6 + O(n·d)/6 | ✔ |

Design D dominates: the SSM layers carry syntax/local structure at O(1) decode state; the
sparse global layers (top-k key selection via learned routing, s ≈ 64 keys/query
regardless of n) provide exact recall at O(n·k_keys·d) ≈ linear cost. This is the
Jamba/Zamba finding plus native sparse attention (DeepSeek NSA-style) on the global
layers.

**Selected design.** Blocks of 6 layers: 5× Mamba-2-style SSM mixers, 1× global attention
with learned top-64 key sparsity and shared KV cache across the block's attention layers
(cross-layer KV sharing, à la YOCO/CLA — one KV cache for the whole model, cutting decode
memory by another ~6×).

Mathematical form of the SSM mixer (Mamba-2 / state-space duality form):

```
h_t = A(x_t) ⊙ h_{t-1} + B(x_t) x_tᵀ        h_t ∈ R^{r×d_head}
y_t = C(x_t) h_t
```

with A(x_t) = exp(−Δ(x_t)·a), input-dependent Δ giving selective forgetting. Sparse
global attention:

```
y_i = Σ_{j ∈ TopK_i} softmax_j( q_i·k_j / √d ) v_j ,   |TopK_i| = 64
```

where TopK_i is chosen by a cheap low-dimensional (d=32) routing dot-product over
block-summarized keys — O(n·d_route) selection, hardware-friendly (contiguous block
gathers).

---

## 1.3 Feed-forward layer: fine-grained mixture of experts

**State of the art.** Dense FFN (Llama); coarse MoE, 8–16 large experts, top-2 (Mixtral);
fine-grained MoE, 64–256 small experts + shared experts (DeepSeek-V3, Qwen-MoE);
loss-free-balancing routers.

**Why inefficient.** Dense FFN violates W1 maximally. Coarse MoE has poor expert
specialization (each expert is still a generalist) and load-balancing losses distort
routing. Token-choice routing causes token dropping under capacity limits.

**Alternatives.**

| Design | Active/total params | Specialization | Failure modes |
|---|---|---|---|
| Dense FFN | 1.0 | none | — |
| 8-expert top-2 (Mixtral) | ~0.28 | weak | balance loss hurts quality |
| 64-expert top-2 + 2 shared (DeepSeek-style) | ~0.06 | strong | routing overhead, comms |
| Expert-choice routing | tunable | strong | causality leak at decode |
| PEER / 1M tiny experts (product-key) | ~0.01 | very strong | immature, memory-bandwidth-bound |

Compute per token for MoE FFN: 2·(k/E)·N_ffn vs. 2·N_ffn dense. With E=64, k=2 plus 2
always-on shared experts, active FFN compute is ~6% of a dense model with equal total FFN
params — i.e., **~10× more total capacity per FLOP** once attention/other costs are
included.

**Selected design.** Per FFN layer: 64 experts of width d_ff/8, top-2 token-choice routing
with **loss-free bias balancing** (adjust per-expert routing bias online instead of an
auxiliary loss — no gradient distortion), plus 2 shared experts always active (stable
common substrate; prevents "no expert took this token" failures). Expert granularity is
also the *unit of continual learning*: new domains get new experts (§2.4).

Router:

```
g_i(x) = TopK( softmax( W_r x + b ) , k=2 ),   b updated online: b_e ← b_e − η·(load_e − mean load)
y = Σ_{e ∈ TopK} g_e(x)·FFN_e(x) + Σ_{s ∈ shared} FFN_s(x)
```

---

## 1.4 Knowledge: retrieval-first, parameters-for-skills

**State of the art.** RAG bolted onto a dense LLM (retrieve → stuff context); RETRO
(retrieval integrated into training via cross-attention to nearest neighbors); GraphRAG;
long-context stuffing.

**Why inefficient.** Post-hoc RAG: the model was still *pretrained* to memorize, so
parameters are spent twice (weights + retrieval index hold the same facts), and the model
ignores or fights retrieved context ("knowledge conflicts"). Context stuffing pays
attention cost over mostly-irrelevant tokens.

**Alternatives.**
1. Post-hoc RAG — cheap to build, doesn't reduce model size.
2. RETRO-style trained cross-attention to a fixed corpus — proved 25× parameter reduction
   at equal LM perplexity, but retrieval is frozen into pretraining and chunk-level only.
3. **Retrieval-native training with a skill/knowledge factorization loss (chosen)** —
   train from the start with retrieval available, and *penalize* the closed-book head for
   confidently answering retrievable facts (details and loss in §2.3). Parameters then
   specialize in composition, reasoning, and language skill; the index holds facts.
4. Fully external memory (Memorizing Transformers, kNN-LM at every layer) — strong recall
   but decode-latency-hostile (per-token index lookups).

**Selected design.** Retrieval happens at *query and paragraph boundaries*, not per token:
a retrieval controller (bidding in the compute market, §1.6) decides when to query M1/M2
memory (§3.2); retrieved chunks are injected via **gated cross-attention blocks** placed
after every attention layer (gate initialized to 0, so retrieval is strictly additive and
can be trained post-hoc onto the backbone). Every generated factual claim carries a
provenance pointer to the retrieval hit that supports it (used by the verifier, §1.7, and
for citation output).

---

## 1.5 Conditional depth: early exit and dynamic recursion

**State of the art.** Fixed depth for all tokens; early-exit heads (CALM); mixture-of-depths
(MoD: per-layer token skipping); Universal/looped transformers (weight-tied recursion,
e.g. "recurrent depth" reasoning models).

**Why inefficient.** Depth is the *serial* budget of the network — trivial tokens ("the",
copying, formatting) do not need 80 layers, while a hard algebra step might benefit from
160. Fixed depth misallocates both ways.

**Comparison.** MoD saves FLOPs but keeps max depth fixed; looped blocks allow depth >
trained depth at test time (test-time compute in *latent space*, cheaper per "step" than
generating CoT tokens: one loop iteration costs 1 block-forward, one CoT token costs a
full L-layer forward *plus* attention over it forever after).

**Selected design.** Both:
- **Mixture-of-depths routing:** each block routes only the top-p (p≈0.5) hardest tokens
  through itself; the rest skip via residual. Halves backbone FLOPs at roughly neutral
  quality (published MoD result), and the router confidences feed the difficulty
  estimator (§1.6).
- **A weight-tied recursive block** at 2/3 depth: the "reasoning core" of 4 layers may be
  iterated 1–16 times per token group, iteration count chosen by the compute market. This
  gives smooth test-time-compute scaling *before* resorting to token-level deliberation.

Exit criterion per token: exit at block ℓ when the exit head's KL to the previous exit
drops below τ (state has converged): `KL(p_ℓ ‖ p_{ℓ−1}) < τ`, τ set by budget.

---

## 1.6 The compute market (global conditional-computation controller)

**Problem.** §1.2–1.5 plus retrieval plus deliberation introduce ~6 independent gating
decisions. Independently trained gates fight each other (e.g., MoD skips a token that the
recursion block then loops on 16×). This coordination problem is unaddressed in current
literature — most systems ship one conditional mechanism at a time.

**Design (novel, flagged speculative).** A small (~50M param) **difficulty estimator**
reads the query (and running uncertainty signals: token entropy, router confidence,
retrieval hit scores, verifier failures) and emits a scalar budget B and per-subsystem
prices. Each mechanism's gate is trained not against a local auxiliary loss but against a
shared Lagrangian:

```
max_π  E[ quality(y) ]  −  λ · E[ FLOPs(π) ]        (one λ, annealed to hit a target FLOPs/query)
```

so at optimum every subsystem operates at the *same* marginal quality-per-FLOP —
the condition for allocative efficiency (equalized marginal returns). Practically: train
gates with straight-through estimators / REINFORCE on quality reward minus λ·cost, with λ
adjusted by dual ascent to meet a deployment-time compute target. Deployment exposes λ as
a user-facing knob: "fast / balanced / thorough" are just three values of λ.

**Fallback if joint training is unstable:** stage-wise — freeze backbone, train gates one
mechanism at a time against the shared λ, then brief joint fine-tune. This reduces to the
known-stable published recipes and sacrifices only the cross-subsystem coordination gain.

---

## 1.7 Deliberation layer: typed workspace, debate, verification

**State of the art.** Long chain-of-thought RL (o1/R1-style); self-consistency (sample-k,
vote); multi-agent debate with separate LLM instances; process reward models; tool use
(code interpreter).

**Why inefficient.**
- CoT reasons in *tokens*: every reasoning step pays full-model decode cost and inflates
  the attention context for all subsequent steps.
- Sample-k self-consistency multiplies cost by k with no reuse across samples.
- Debate between separate model instances re-encodes shared context repeatedly.
- Free-text thoughts cannot be checked by cheap symbolic tools — only by another LLM.

**Selected design.**
1. **Shared latent workspace.** All reasoning modules are *heads/adapters on the same
   backbone* reading and writing a shared context — no re-encoding. Modules: Proposer
   (fast answer), Planner (task decomposition, produces a DAG of subgoals), Critic
   (adversarial: trained on a corpus of *known-flawed* reasoning to find errors),
   Verifier (routes checkable claims to symbolic tools), Reflector (post-hoc: writes
   lessons to episodic memory, §3.2).
2. **Typed intermediate objects.** Workspace entries are typed: `Claim(stmt, support)`,
   `Program(code, spec)`, `ProofStep(premises, rule, conclusion)`, `Plan(dag)`,
   `Citation(chunk_id, span)`. Types determine the verification route:
   - `Program` → sandboxed execution against `spec` (unit tests / property checks)
   - arithmetic / algebraic `Claim` → computer algebra system / SMT solver
   - factual `Claim` → retrieval fact-check against M2 with provenance match
   - `ProofStep` → lightweight proof checker (Lean-style kernel for formalizable steps)
   Symbolic checks cost ~10³–10⁶× less than LLM re-checking and return ground truth, not
   opinion. This is the neuro-symbolic hybrid: neural proposes, symbolic disposes.
3. **Debate protocol.** Rounds of (Propose → Criticize → Verify → Revise), budgeted by the
   compute market. Termination: verifier-weighted agreement exceeds threshold, or budget
   exhausted (then output carries an explicit low-confidence flag). Because critique and
   verification operate on typed objects, convergence is measurable (count of surviving
   unverified claims) rather than vibes-based.
4. **Confidence output.** Final answer ships with: fraction of claims verified, citation
   list, and the (compressed) trace — transparent reasoning as a *product feature* and as
   training signal (§2.2).

**Recursion and planning.** The Planner's subgoal DAG re-enters the whole pipeline per
node (multi-stage planning = recursive self-calls with budgets split by the market);
memoization via episodic memory prevents re-solving repeated subgoals.

---

## 1.8 Parameter budget (reference configuration "ATLAS-1")

| Component | Params (total) | Params (active/token) |
|---|---|---|
| Backbone: 48 layers (40 SSM + 8 sparse-attn), d=4096 | 9 B | 9 B |
| MoE FFN: 48 layers × 64 experts × 42M + shared | 135 B | ~11 B |
| Gated retrieval cross-attention | 2 B | 0–2 B (conditional) |
| Deliberation heads/adapters + difficulty estimator | 1.5 B | 0–1.5 B (conditional) |
| **Total** | **~148 B** | **~13–23 B** |

Design point: dense-70B-class quality floor from ~13B active params on easy queries,
scaling smoothly to frontier-class reasoning on hard queries via recursion + deliberation
+ retrieval — instead of paying frontier cost on every query.

---

## 1.9 Remaining known inefficiencies (frontier-distance audit)

Per the mandate ("continue until no obvious inefficiencies remain"), what still leaks:

1. **Tokenization** — byte-pair encoding wastes capacity on orthography. Candidate fix:
   byte-latent patching (dynamic entropy-based patches). Deferred: interacts badly with
   the retrieval index's chunking; revisit in v2.
2. **Backprop itself** — training pass costs 3× forward. No credible replacement at scale
   (forward-forward, local losses all underperform); accepted.
3. **Autoregressive decoding serialization** — mitigated by speculative decoding (§3.4)
   and diffusion-style parallel drafting is a v2 research item (§4.6).
4. **Router discreteness** — top-k gradients are biased; soft-merging (SMEAR-style) during
   training, hard routing at inference, narrows but doesn't close this.
