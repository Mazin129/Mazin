# CORTEX-OS — Redesigning Vio as a Cognitive Operating System

**A digital brain, not a chatbot. Runs on a 16–64 GB consumer laptop, no cloud, and gets
smarter with age instead of with parameters.**

> **Honest framing (same rule as the rest of this repo).** Sections are tagged **[BUILT]**
> (running code exists in `prototype/` or `mind/`), **[EXTRAPOLATION]** (a principled design
> with the math/algorithm shown), or **[SPECULATIVE]** (a research bet, flagged with its risk).
> This is a specification, not a proof. What makes it credible is that the four hardest ideas —
> predictive-coding inference, complementary fast/slow memory, oscillatory binding, and sparse
> event-driven coding — are **already prototyped and measured** in this repo; CORTEX-OS is the
> control architecture that wires them into one mind.

CORTEX-OS is the successor to the current Vio (`mind/`, an input→route→search→answer engine)
and the concrete instantiation of the brain-native redesign (§05 *CORTEX*) and the
first-principles rethink (§06 *AXIOM*). Where Vio *reacts*, CORTEX-OS *thinks*: it perceives,
predicts, simulates, decides, acts, critiques, and consolidates — as a loop that never stops.

---

## Table of contents

0. [Design philosophy — the brain-first question](#0-design-philosophy)
1. [High-level architecture](#1-high-level-architecture)
2. [The Cognitive Workspace — communication protocol](#2-the-cognitive-workspace)
3. [Memory architecture](#3-memory-architecture)
4. [Knowledge representation — eight views of one fact](#4-knowledge-representation)
5. [Cognitive module designs (all 14)](#5-cognitive-module-designs)
6. [The specialist cortex — a multi-agent brain](#6-the-specialist-cortex)
7. [Reasoning engine — eight modes](#7-reasoning-engine)
8. [Planning engine](#8-planning-engine)
9. [World model & internal simulation](#9-world-model--internal-simulation)
10. [Confidence evaluation](#10-confidence-evaluation)
11. [Self-critic & self-correction](#11-self-critic--self-correction)
12. [Curiosity & active inference](#12-curiosity--active-inference)
13. [Learning engine — experience → skill](#13-learning-engine)
14. [Memory consolidation — the sleep cycle](#14-memory-consolidation)
15. [The thinking loop — end-to-end data flow](#15-the-thinking-loop)
16. [Energy optimization](#16-energy-optimization)
17. [Long-term intelligence trajectory](#17-long-term-intelligence)
18. [Performance analysis](#18-performance-analysis)
19. [Scalability roadmap](#19-scalability-roadmap)
20. [Risks & mitigations](#20-risks--mitigations)
21. [Comparison vs LLM architectures](#21-comparison-vs-llm-architectures)
22. [Phased implementation plan](#22-phased-implementation-plan)
23. [Folder structure & code organization](#23-folder-structure)
24. [What already exists to build on](#24-what-already-exists)

---

## 0. Design philosophy

Every decision answers **"how would the brain solve this?"** — not "how does a transformer?"
The brain runs on ~20 W, ~86 B neurons but only **~1–2 % active at any moment**, has **no global
loss and no backprop**, never stops learning, and represents the same knowledge many ways at
once. Intelligence there is *organization*, not *scale*. Eight assumptions of modern AI, and the
brain-like replacement CORTEX-OS adopts:

| Transformer assumption | CORTEX-OS challenge |
|---|---|
| One giant model does everything | **Modular cortex** — dozens of small specialists, only the relevant few active |
| Attend to *every* token, every layer | **Event-driven, salience-gated routing** — compute follows surprise |
| Knowledge lives in weights | **Knowledge lives in external, editable memory**; weights hold *skills* |
| Fixed context window | **Hierarchical working memory + episodic recall** — effectively unbounded, addressable |
| Stateless forward pass | **Persistent internal state** — the mind is always "on", predicting |
| Learn only by gradient descent, offline | **Local plasticity + Hebbian + replay consolidation**, online, forever |
| Bigger data + params = smarter | **More *experience*, better *organized* = smarter** |
| Generate first, hope it's right | **Simulate and self-critique before speaking** |

The North Star: after two years of daily use, CORTEX-OS is materially smarter than on day one —
because it has *lived* more, not because anyone shipped a bigger checkpoint.

---

## 1. High-level architecture

CORTEX-OS is a **Global-Workspace blackboard** (Baars/Dehaene) surrounded by independent
modules. No module calls another directly; they **publish and subscribe to the Workspace**. A
salience-gated **ignition** event decides which coalition of modules "wins" access to
consciousness (the broadcast state) at each tick — this *is* the sparse-activation mechanism.

```
                         ┌───────────────────────────────────────────────┐
   sensory in ──────────►│           ATTENTION CONTROLLER                 │
   (text / file / event) │   salience scoring · filtering · gating        │
                         └───────────────┬───────────────────────────────┘
                                         │ admitted percepts
                    ┌────────────────────▼────────────────────┐
                    │        EXECUTIVE CONTROLLER              │  ◄── goals, budget
                    │  picks module coalition · sets budget    │
                    └───────┬───────────────────────┬─────────┘
                            │  writes/reads          │ activates (sparse)
              ┌─────────────▼─────────────────────────────────────────┐
              │             COGNITIVE WORKSPACE (blackboard)           │
              │   typed slots · pub/sub · ignition/broadcast · trace   │
              └──┬────┬────┬────┬────┬────┬────┬────┬────┬────┬────┬───┘
                 │    │    │    │    │    │    │    │    │    │    │
      ┌──────────▼─┐ ┌▼───┐ ┌▼──┐ ┌▼──┐ ┌▼──┐ ┌▼──┐ ┌▼──┐ ┌▼──┐ ┌▼──┐ ┌▼───────┐
      │  WORKING   │ │SEM │ │EPI│ │PRO│ │WRLD│ │PLAN│ │REAS│ │CONF│ │CRIT│ │CURIOSITY│
      │  MEMORY    │ │MEM │ │MEM│ │MEM│ │MODEL│ │NER │ │ONER│ │IDNC│ │IC  │ │+LEARNER │
      └────────────┘ └────┘ └───┘ └───┘ └────┘ └────┘ └────┘ └────┘ └────┘ └─────────┘
                 │                                                        │
                 └───────────► LANGUAGE GENERATOR ──► response ◄──────────┘
                                        │
                          (idle) ► MEMORY CONSOLIDATION ◄ episodic replay
```

**Two clocks.** A **fast reactive clock** (System-1: a cached answer, a reflex skill, a
verified tool) can respond in one tick. A **slow deliberative clock** (System-2: retrieve →
predict → reason → simulate → critique → revise) engages only when the Executive judges the
task hard or the Confidence Engine flags risk. This is the single biggest energy lever: **most
messages never wake System-2.**

---

## 2. The Cognitive Workspace

The communication protocol. A shared, in-RAM, append-mostly structure with typed slots. Modules
never hold references to each other — total decoupling, testable in isolation, brain-like.

**Message schema (a "cognit"):**
```
Cognit {
  id, tick, source_module, type,            # type ∈ {percept, goal, hypothesis, plan,
  salience   : float 0..1,                   #        evidence, prediction, critique, answer,…}
  confidence : float 0..1,
  ttl        : int,                          # decays; low-salience cognits evaporate
  payload    : typed object (see §4),        # KG-fragment | vector | rule | plan-DAG | …
  provenance : [cognit_id,…],                # full audit trail → explainability
  links      : [cognit_id,…]
}
```

**Protocol:**
- **Publish**: any module posts cognits. Cost O(1).
- **Subscribe**: modules register interest by `type` + a salience threshold. The Workspace
  pushes matching cognits — **event-driven, not polled** (no busy-waiting = no idle burn).
- **Ignition (broadcast)**: each tick, a winner-take-all selects the highest-salience *coalition*
  of mutually-linked cognits and broadcasts it globally. Only broadcast content is "conscious"
  and drives the response; everything else is subliminal processing that may or may not surface.
- **Decay**: `salience *= γ` per tick; cognits below ε are garbage-collected. Working memory
  stays small automatically (§3.1).

**Why a blackboard, not function calls?** Direct calls impose a fixed control flow (the
transformer's fixed layer stack). A blackboard lets control **emerge** from whichever module has
something salient to say — the same reason cortex uses broadcast, not a call graph.

Complexity: ignition is a top-k over active cognits, O(A log k) with A = live cognits (kept
small, hundreds). Memory: a ring buffer, ~1–10 MB.

---

## 3. Memory architecture

Four specialized stores + a consolidation process, mirroring the hippocampal–neocortical
Complementary Learning Systems already prototyped in `bl_system.py` / `bl_advanced.py`.

### 3.1 Working Memory (WM) — [BUILT seed: `mind/` context; oscillatory binding prototyped]
- **Purpose**: the active scratchpad — current goal, retrieved facts, partial reasoning.
- **Structure**: a bounded set of "slots" (≈7±2 chunks, Miller) each holding a cognit + a
  **phase tag**. Binding of which-fact-goes-with-which-variable uses **oscillatory phase codes**
  (co-firing = bound) — the mechanism from `selective_oscillatory_memory.py`, whose symplectic
  dynamics keep binding stable over long chains.
- **Algorithm**: attention-weighted refresh; unrefreshed slots decay (interference-based
  forgetting, not a hard window). **Challenge to the fixed context window**: WM is a *dynamic
  attractor network*, not a fixed-length buffer — capacity trades gracefully against precision.
- **Complexity/Memory/Energy**: O(slots) per tick; < 5 MB; near-zero at idle.

### 3.2 Semantic Memory (SEM) — [BUILT seed: `Library` TF-IDF; graph is EXTRAPOLATION]
- **Purpose**: timeless knowledge — concepts, relations, facts.
- **Structure (multi-view, §4)**: a **Knowledge Graph** (concepts=nodes, typed edges) +
  **quantized vector index** (HNSW/IVF-PQ, int8) + **symbolic rule set** + **concept network**.
- **Algorithms**: hybrid retrieval — vector ANN for fuzzy recall, graph traversal for relational
  queries, symbolic match for exact rules; results fused by a learned gate. Today's Vio already
  does the TF-IDF half and a precision gate; CORTEX-OS adds the graph + embeddings.
- **Complexity/Memory/Energy**: ANN query O(log N); graph hop O(deg); vectors int8-quantized
  ≈ 40 GB→**4 GB for ~4 M facts**; cold nodes memory-mapped on disk, LRU-cached.

### 3.3 Episodic Memory (EPI) — [BUILT: episodic hippocampus in `bl_advanced.py`]
- **Purpose**: autobiographical timeline — conversations, solved problems, mistakes, successes.
- **Structure**: append-only event log; each episode = {time, context embedding, actions,
  outcome, reward, links}. Indexed by time **and** by content vector (recall by *when* or by
  *what it was like*). Fast, one-shot write — exactly the hippocampal exemplar store already
  demonstrated (k-NN recall of stored exemplars).
- **Algorithms**: pattern-separated write (sparsify to avoid collisions — the k-WTA code from
  `bl_torch.py`), similarity + recency + reward weighted recall.
- **Complexity/Memory/Energy**: write O(1); recall O(log M); on disk, hot window in RAM.

### 3.4 Procedural Memory (PRO) — [BUILT seed: `skills.py`, `agent.py`]
- **Purpose**: *how-to* — learned workflows, skills, multi-step automations.
- **Structure**: a library of **procedure graphs** (typed DAGs: nodes=steps/tool-calls,
  edges=data/precondition). Each carries usage stats + a success prior. Today's user skills and
  the solve-agent's decomposition are the seed.
- **Algorithms**: match current goal → retrieve best procedure by success-weighted similarity;
  execute; on success, reinforce; **chunk** frequently co-run sub-procedures into one (the
  brain's automatization — practice makes a skill "one move").
- **Complexity/Memory/Energy**: retrieval O(log P); tiny; running a cached procedure is
  System-1 cheap (no reasoning).

### 3.5 Consolidation (see §14) turns EPI → SEM/PRO during idle "sleep".

**Hierarchical retrieval order (energy-first):** WM (free) → PRO cache → EPI hot → SEM ANN →
SEM graph → (only if all weak) escalate to reasoning/simulation. Stop at the first confident hit.

---

## 4. Knowledge representation

**Never store only text.** Every fact is materialized in whichever of these views a query needs;
a **Representation Router** picks per-access and caches the chosen form.

| View | Best for | Structure |
|---|---|---|
| Knowledge Graph | relational / "how is X related to Y" | typed property graph |
| Vector embedding | fuzzy similarity, analogy | int8 vector + ANN index |
| Symbolic rules | exact logic, constraints, math | Horn clauses / sympy exprs |
| Concept network | spreading activation, priming | weighted association net |
| Procedural graph | how-to, multi-step | typed DAG (§3.4) |
| Temporal memory | sequence, "what happened before" | ordered episode links |
| Decision tree | fast classification / routing | learned tree |
| Causal graph | prediction, counterfactuals | DAG with structural equations |

**Auto-selection**: the router scores each view's fitness for the query type (learned from which
view historically yielded confident answers) and consults the top one first, falling back on
miss. **Challenge to "embeddings are enough":** a single vector space collapses relations,
causality, and logic into cosine distance; the brain keeps them as *distinct* circuits, so we do
too. A causal question must hit the **causal graph**, not a nearest-neighbor lookup.

---

## 5. Cognitive module designs

Each module: **Purpose · Inputs · Outputs · Algorithm · Data · Interactions · Complexity ·
Memory · Energy.** All communicate only through the Workspace (§2).

### 5.1 Executive Controller — [EXTRAPOLATION; seed: §01.6 compute market]
- **Purpose**: the prefrontal cortex — choose which modules to activate, prioritize goals,
  allocate a compute budget.
- **Inputs**: admitted percepts, current goals, Confidence signals, resource meter.
- **Outputs**: an **activation set** (which specialists/modules to wake) + a **budget token**.
- **Algorithm**: a difficulty estimator scores the task; a learned policy (contextual bandit,
  reward = correctness − energy) maps (task-type, difficulty, budget) → activation set. Reuses
  §01.6's "difficulty-priced compute market": every mechanism *bids* against the budget.
- **Data**: policy table + running cost model.
- **Interactions**: gates every other module; reads Confidence/Critic to escalate.
- **Complexity/Memory/Energy**: O(1) per decision; KB; **its whole job is to save energy.**

### 5.2 Attention Controller — [EXTRAPOLATION; seed: §01, event-driven §05.1]
- **Purpose**: decide what deserves focus; filter distraction.
- **Inputs**: raw sensory stream + WM context.
- **Outputs**: salience-scored, filtered percepts admitted to the Workspace.
- **Algorithm**: bottom-up salience (novelty vs. prediction, surprise = high error from the World
  Model) + top-down bias (current goal). Only above-threshold events ignite — **event-driven**.
- **Data**: salience weights, novelty baselines.
- **Interactions**: feeds Workspace; biased by Executive goals; driven by World-Model error.
- **Complexity/Memory/Energy**: O(input); tiny; suppresses ~everything → huge savings.

### 5.3 Working Memory — see §3.1. 5.4 Semantic — §3.2. 5.5 Episodic — §3.3. 5.6 Procedural — §3.4.

### 5.7 World Model — [SPECULATIVE→EXTRAPOLATION; substrate BUILT: predictive coding]
- **Purpose**: represent cause→effect; predict the next state; host internal simulation.
- **Inputs**: current state (WM), a candidate action/answer.
- **Outputs**: predicted next state + prediction-error signal.
- **Algorithm**: a **predictive-coding network** (already built: `predictive_coding_brain.py`)
  runs generative top-down predictions; the mismatch (free energy) is the learning and attention
  signal. Causal structure stored as a **causal graph** (§4) with local structural equations.
- **Data**: PC network weights (small) + causal DAG.
- **Interactions**: Attention (surprise), Planning/Simulation (rollouts), Learning (error).
- **Complexity/Memory/Energy**: inference = a few settling iterations, O(iters·layers); MBs; the
  no-backprop local rule is cheap and CPU-friendly.

### 5.8 Planning Engine — see §8. 5.9 Reasoning Engine — see §7. 5.10 Confidence — see §10.
### 5.11 Self-Critic — see §11. 5.12 Curiosity — see §12. 5.13 Learning — see §13.
### 5.14 Language Generator
- **Purpose**: turn a chosen internal answer (typed cognits) into fluent text (EN/AR).
- **Inputs**: the broadcast answer coalition + style/context.
- **Outputs**: surface text + the `{how, verified, confidence, trace}` envelope.
- **Algorithm**: **grounded surface realization** — today's extractive-composer (`think.py`)
  organizes verified/retrieved content; the oscillatory/hybrid LM (`bl_language_*`) is the
  optional neural realizer for free-form writing, *constrained to only phrase content the rest of
  the brain already validated* (generation never invents facts — §21).
- **Complexity/Memory/Energy**: O(answer length); the small LM is laptop-sized.

---

## 6. The specialist cortex

Instead of one thinker, a **cortex of small experts** (like cortical areas). Each is a self-
contained package exposing `{can_handle(task)->score, activate(workspace)}`. The Executive wakes
only those scoring high — **sparse activation in practice**.

```
Networking · Programming · Security · Research · Planner · Teacher ·
Writer · Scientist · Engineer · Analyst · Critic · Optimizer · Math · Medical …
```

- Each specialist owns: its slice of Semantic/Procedural memory, its preferred reasoning modes,
  its tools. E.g. **Networking Expert** owns the FortiOS knowledge the current Vio already learns
  from PDFs/repos; **Math** owns the verified sympy tools already shipped.
- **Routing**: the Executive scores `can_handle` (a cheap learned classifier over the goal) and
  activates the top-1–3. A math question wakes Math only; a networking question wakes Networking
  (+ maybe Research). This is **§21's answer to "one giant model": many tiny ones, few awake.**
- **Adding intelligence = adding a package**, not retraining a monolith. Zero catastrophic
  forgetting by construction (new expert ≠ overwritten weights — the CLS guarantee).
- Complexity: routing O(#experts) cheap scores; only active experts consume real compute.
  Memory: experts **lazy-loaded** from disk on demand, LRU-evicted (§16 dynamic loading).

---

## 7. Reasoning engine

A dispatcher over eight modes; the Executive/specialist picks the mode(s) the goal needs. Each
mode reads WM + memories and posts hypotheses + a self-check to the Workspace.

| Mode | Mechanism | Verification |
|---|---|---|
| **Logical / Deductive** | forward/backward chaining over symbolic rules (§4) | proof re-checkable |
| **Inductive** | generalize episodes → candidate rule; test on held-out episodes | coverage/accuracy |
| **Abductive** | best-explanation search: hypothesis that minimizes World-Model error | simulation agreement |
| **Analogical** | structure-mapping between graph neighborhoods (not just vector cosine) | mapping consistency |
| **Mathematical** | sympy engine — **already built & self-verifying** in `mind/reasoner.py` | substitute-back check |
| **Causal** | do-calculus over the causal graph (§4) | intervention consistency |
| **Counterfactual** | run the World Model with a changed antecedent | rollout stability |
| **Probabilistic** | belief propagation over the concept/causal net | calibration |

**Algorithm (meta):** try the cheapest applicable mode first (deductive/math are exact and
cheap); escalate to abductive/counterfactual (which invoke simulation) only if confidence is low.
Every result carries its own verification score into the Confidence Engine. **Challenge to
"reasoning = next-token prediction":** here reasoning is *typed operations over structured
knowledge with checkable intermediates*, not free-text chains — auditable and far cheaper.

Complexity: deductive O(rules·depth) with indexing; analogical O(subgraph); causal O(graph).
Memory: rule/graph indices, MBs–GBs shared with SEM.

---

## 8. Planning engine

- **Purpose**: turn a goal into an ordered, dependency-aware action plan.
- **Inputs**: goal cognit, world state (WM), available procedures/tools.
- **Outputs**: a **plan DAG** (nodes=subgoals/actions, edges=dependencies) with expected cost.
- **Algorithm**: **recursive goal decomposition** (HTN-style) — expand a goal into subgoals via
  Procedural memory templates + means-ends analysis; stop when a subgoal maps to a known
  procedure or tool. Order by a topological sort of the dependency graph. Before committing, the
  plan is **rolled out in the World Model** (§9) and scored; the best of k sampled plans wins
  (model-predictive control). The current `agent.py` decomposition is the seed of this.
- **Data**: plan DAG, procedure library, cost model.
- **Interactions**: World Model (rollouts), Confidence (plan risk), Executive (budget), Learning
  (store successful plans as new procedures).
- **Complexity/Memory/Energy**: decomposition O(subgoals·branching); k rollouts × sim cost —
  bounded by the Executive budget so planning depth scales with task importance.

---

## 9. World model & internal simulation

**Think before you act.** [substrate BUILT: predictive coding + oscillatory dynamics]

- **Framework**: a differentiable-ish **generative model** `s' = f(s, a)` predicting the next
  internal state from a state+action, plus a value/outcome head. Implemented as the
  predictive-coding net (§5.7) over the causal graph.
- **Simulation loop**: given a candidate plan/answer, **roll it forward N steps** internally,
  observe predicted outcomes, and score them *without touching the outside world*. Multiple
  candidates run as parallel rollouts (the "imagination" of options).
- **Active inference**: the system doesn't just predict — it chooses actions that it *expects to
  reduce future prediction error / reach the goal state* (minimize expected free energy). This
  unifies attention, planning, and curiosity under one objective.
- **Interactions**: Planning (evaluate plans), Reasoning (abductive/counterfactual),
  Confidence (simulation agreement), Curiosity (high predicted-error = interesting).
- **Complexity/Memory/Energy**: N-step rollout × k candidates × settle-iters; bounded by budget;
  local PC updates are backprop-free and CPU-cheap.

---

## 10. Confidence evaluation

Every answer ships a **calibrated confidence** — a weighted fusion, not a softmax guess.

```
confidence = w1·knowledge_quality      # source strength, recency, corroboration count
           + w2·reasoning_quality      # did a verification pass? proof/substitute-back?
           + w3·memory_consistency     # agreement across SEM/EPI; penalize contradictions
           + w4·evidence_support       # #independent sources backing it
           + w5·simulation_agreement   # did World-Model rollouts corroborate?
```
- Weights are **learned by calibration** against logged outcomes (Brier-score minimization) so
  the number *means* something (0.8 ⇒ right ~80 % of the time).
- **Thresholds drive behavior**: high → answer; medium → self-critique/re-search (§11); low →
  ask the user or say "I don't know" (today's Vio already refuses to guess — this generalizes it
  to *every* path, not just retrieval).
- Complexity: O(1) fusion; trivial memory. **This module is what makes the system trustworthy.**

---

## 11. Self-critic & self-correction

Before broadcasting an answer, a dedicated Critic interrogates it — the brain's error-monitoring
(anterior cingulate). It posts critique cognits that can veto or revise.

Checklist (each a cheap check, escalating cost):
1. **Am I correct?** re-run the verifier / a second reasoning mode; compare.
2. **Did I assume something?** list unstated premises; are they in memory or invented?
3. **Can I verify this?** is there a tool/source to confirm? if yes and unused → use it.
4. **Conflicting memory?** query SEM/EPI for contradictions; if found, reconcile or lower confidence.
5. **Search again?** if evidence thin, trigger another retrieval with reformulated keys (today's
   `agent.py` re-search is the seed).
6. **Ask the user?** if genuinely ambiguous/underspecified, prefer a clarifying question over a guess.

**Loop**: critique → if veto, revise (back to Reasoning/Planning) → re-evaluate confidence →
at most K iterations, then answer with the best confidence achieved (and say so). This is the
"Simulate → Self-critic → Revise" stretch of the thinking loop (§15).

Complexity: K× a subset of module calls; the Executive caps K by budget. **Most easy answers pass
the checklist in one cheap pass.**

---

## 12. Curiosity & active inference

The drive that makes it smarter over time.

- **Detect the unknown**: a query, or an episode, whose World-Model prediction error is high, or
  that hits a **knowledge gap** (sparse graph neighborhood, low-confidence answer).
- **Generate learning goals**: post a `goal:learn(topic)` cognit; queue intelligent follow-up
  questions ("You mentioned X — is it related to Y I already know?").
- **Autonomous expansion**: during idle time (§14), pursue queued learning goals from existing
  material (re-read, cross-link) or *ask the user* / offer to learn a source (a repo, a doc) —
  building on today's "learn from GitHub/PDF".
- **Objective**: choose what to learn by **expected information gain** (largest predicted drop in
  future prediction error per unit energy) — active inference, not random exploration.
- Complexity: gap detection O(1) per answer; learning-goal pursuit is idle-time only.

---

## 13. Learning engine

**Convert every solved problem into reusable knowledge** — online, no offline retraining, no
catastrophic forgetting (the CLS + local-plasticity guarantee, already demonstrated: new class
learned one-shot while old accuracy barely moves, `bl_advanced.py`).

**On each completed task, extract an experience record:**
```
Experience { problem, context, goal, reasoning_trace, tools_used,
             solution, outcome(success/fail), reward, lessons }
```
**Three learning pathways (fast→slow), all local:**
1. **Episodic write [O(1), instant]** — store the Experience verbatim (hippocampus). Available
   immediately for one-shot recall.
2. **Procedural chunking [minutes]** — if a reasoning trace succeeded, generalize it into a
   **procedure graph** (variables abstracted) and add to Procedural memory; reinforce/decay by
   outcome. Repeated wins get *chunked* into a single automatic skill.
3. **Semantic integration [idle, §14]** — distill recurring episodes into durable facts/rules and
   new graph edges; update embeddings incrementally (streaming index insert, no full re-fit).

Weight updates use **local predictive-coding / Hebbian rules** (`bl_deep_local.py` shows a deep
net learning MNIST to 96.9 % with *no backprop*), so learning is cheap, online, and stable.

Complexity: pathway 1 O(1); 2 O(trace); 3 amortized at idle. **Challenge to "training is a
separate offline phase":** here using the system *is* training it.

---

## 14. Memory consolidation — the sleep cycle

When idle, CORTEX-OS "sleeps": a background process that reorganizes memory — the single biggest
source of long-term improvement (§17). Analogous to hippocampal replay → neocortical
consolidation; §02.5 calls this "memory-consistency distillation".

**Cycle (interruptible, low-priority):**
1. **Replay** salient/rewarding episodes from EPI (prioritized by reward × surprise).
2. **Merge duplicates** — cluster near-identical facts/episodes; keep one canonical, link the rest.
3. **Strengthen** frequently-useful memories (raise retrieval prior); **forget** obsolete/never-
   recalled ones (decay + prune) — active forgetting is a feature: it keeps retrieval fast and
   models current.
4. **Create relationships** — mine co-occurrence/causal links across episodes → new graph edges
   (this is where genuinely *new* knowledge emerges from old, offline).
5. **Compress** — distill many episodes into a general rule/schema (episodic→semantic).
6. **Re-optimize retrieval** — rebuild/annotate indices, re-cluster the vector store, re-balance
   the graph, refresh the decision-tree routers.

**Challenge to "a model is frozen after training":** CORTEX-OS is *never* frozen; it improves
most while doing nothing visible. Runs at low priority / low-power (§16); fully interruptible by
a new user message.

Complexity: batch, amortized over idle; bounded time-slices. Memory: operates on-disk with a RAM
working set.

---

## 15. The thinking loop

The end-to-end control flow for one interaction. **System-1 exits early**; **System-2 runs the
full loop only when needed.**

```
                    ┌────────────────────────── new message ──────────────────────────┐
                    ▼                                                                    │
 1 UNDERSTAND   Attention scores salience, admits percepts ─► Workspace                 │
                    ▼                                                                    │
 2 GOAL         Executive infers the goal + task type + difficulty                      │
                    ▼                                                                    │
        ┌── System-1? (cached answer / reflex skill / one verified tool) ──► yes ──► ANSWER ─┤
        │           ▼ no (hard / risky)                                                  │
 3 RETRIEVE     hierarchical recall: WM→PRO→EPI→SEM (stop at confident hit)              │
                    ▼                                                                    │
 4 PREDICT      World Model predicts; Attention flags surprise/gaps                      │
                    ▼                                                                    │
 5 REASON       Reasoning Engine (right mode/specialist) forms hypotheses                │
                    ▼                                                                    │
 6 SIMULATE     Planning rolls candidates forward in the World Model, scores them        │
                    ▼                                                                    │
 7 SELF-CRITIC  Critic runs the checklist; Confidence fuses signals                      │
                    ▼                                                                    │
 8 REVISE ◄──── low confidence? loop to 3/5 (≤K times) or ask the user                   │
                    ▼ high enough                                                        │
 9 RESPOND      Language Generator realizes the answer + {how, verified, confidence}      │
                    ▼                                                                    │
10 LEARN        Learning Engine writes the Experience (episodic; queue procedural)       │
                    ▼                                                                    │
11 STORE/SLEEP  on idle, Consolidation integrates it into semantic/procedural memory ───┘
```

Data-flow (who reads/writes the Workspace) is exactly the module graph of §1; every arrow is a
typed cognit with full provenance, so the whole chain is replayable and explainable.

---

## 16. Energy optimization

Assume 16 GB RAM, a modest CPU (maybe a 2–4 GB GPU). Never waste a cycle.

| Technique | Mechanism |
|---|---|
| **Sparse activation** | Executive wakes only needed modules/specialists; ignition gates the rest |
| **Two-clock design** | System-1 answers most messages; System-2 (the expensive loop) rarely fires |
| **Event-driven compute** | Attention suppresses non-salient input; no polling, no idle spin |
| **Hierarchical retrieval** | stop at the first confident memory tier; cheap tiers first |
| **Memory caching** | WM + LRU caches for hot facts/procedures/experts |
| **Incremental indexing** | streaming inserts into ANN/graph — never re-fit the whole store |
| **Adaptive compute** | budget token scales reasoning depth / #rollouts / critique iters K with task value |
| **Dynamic model loading** | specialists + neural realizers memory-mapped, lazy-loaded, LRU-evicted |
| **Quantization** | int8/int4 vectors and any neural weights |
| **Low-power idle + background consolidation** | sleep runs at low priority, time-sliced, interruptible |
| **Backprop-free local learning** | Hebbian/predictive-coding updates avoid the cost of a global backward pass |

Budget discipline: **every module reports its energy cost**; the Executive's bandit policy is
rewarded for correctness *minus* energy, so the system *learns to think cheaply*.

---

## 17. Long-term intelligence

Why it grows smarter with age, not parameters:

- **More experiences** → richer episodic base → better one-shot recall and analogies.
- **Better organization** → consolidation keeps merging, linking, compressing → denser, cleaner
  knowledge graph → faster, more accurate retrieval.
- **Refined procedures** → repeated tasks get chunked into reliable skills → more answers become
  cheap System-1 reflexes.
- **Calibrated confidence** → the confidence model self-tunes on outcomes → fewer mistakes, better
  "know what you don't know".
- **Curiosity-driven gap-filling** → it actively closes its own blind spots over time.

Result: a machine whose competence curve *keeps rising* from daily use — the opposite of a frozen
checkpoint. The measurable promise (track it): rising first-try accuracy, rising System-1 hit-rate,
falling energy-per-answer, shrinking calibration error — all as functions of *days used*.

---

## 18. Performance analysis

Indicative budgets for a 16 GB laptop, ~4 M facts / ~100 k episodes (grows to disk):

| Resource | Steady state | Notes |
|---|---|---|
| Workspace + WM | 1–10 MB | ring buffer, tiny |
| Semantic vectors (int8) | ~2–4 GB RAM (hot) + disk | mmap cold, LRU |
| Knowledge graph | ~0.5–2 GB | adjacency + props |
| Episodic log | disk; ~200 MB hot window | recency+content indexed |
| Active specialists (1–3) | ~0.2–1 GB | lazy-loaded, evictable |
| Neural realizer / PC nets | ~50–500 MB | small, quantized |
| **Total resident** | **~4–8 GB** | fits 16 GB with headroom; 64 GB → bigger hot set |

Latency: System-1 answer ≈ tens of ms (cache/tool/skill). System-2 full loop ≈ 0.2–2 s depending
on budget (retrieval + a few reasoning/simulation/critique iterations), all CPU-feasible because
each op is sparse and small. Retrieval O(log N); reasoning bounded by budget; consolidation off
the critical path.

---

## 19. Scalability roadmap

- **Vertical (per device)**: 16 GB (personal assistant, ~M-scale facts) → 64 GB (bigger hot set,
  more concurrent specialists, deeper simulation). Everything degrades gracefully via LRU/mmap.
- **Knowledge scale**: sharded ANN + graph partitioning keep retrieval sub-linear into the
  hundreds of millions of facts (cold on disk).
- **Specialist scale**: adding experts is O(1) organizationally (drop a package); routing cost
  grows with a cheap learned classifier, not with total experts awake.
- **Multi-device (optional, still no cloud)**: episodic/semantic stores can sync between a user's
  own machines (encrypted) — a *personal* distributed brain, not a shared model.
- **Community skills (opt-in)**: procedures/specialists are shareable artifacts (like today's
  `skills.json`) — import a "Networking Expert" someone else grew, without any shared weights.

---

## 20. Risks & mitigations

| Risk | Mitigation |
|---|---|
| **World model unreliable at scale** (hardest bet) | keep it advisory: simulation *scores* candidates but exact tools/verification remain the source of truth; ship value even if sim is weak |
| **Consolidation corrupts memory** (bad merges/forgetting) | consolidation is *additive + reversible* (canonical + links, tombstones not deletes); verify merges against held-out episodes; keep audit trail |
| **Confidence miscalibration** | continuous Brier-score recalibration on logged outcomes; conservative default thresholds; prefer "I don't know" |
| **Latency from over-deliberation** | strict Executive budget; System-1 fast path; K-capped critique loops |
| **Knowledge-graph construction is noisy** | start with the *already-working* retrieval+precision-gate; add graph edges only above an evidence threshold; symbolic rules require proof |
| **Runaway curiosity / distraction** | curiosity is idle-time only and budget-gated; user goals always preempt |
| **Complexity / build risk** | the phased plan (§22) ships value at every phase; each module is independently testable via the Workspace |
| **Security (learning from the world)** | read-only ingestion (never execute repo/file code — already enforced in `gitlearn.py`); sandbox tools; memory writes are provenance-tracked and user-inspectable |
| **Privacy** | 100 % local by default; no telemetry; memory stores are plain, user-owned, forgettable (the "Forget everything" control already exists) |

---

## 21. Comparison vs LLM architectures

| Dimension | Transformer LLM | CORTEX-OS |
|---|---|---|
| Core unit | one dense network | many small modules + external memory |
| Activation | all params, every token | sparse — a few modules/specialists |
| Knowledge | baked into weights (static, hallucination-prone) | external, editable, cited memory |
| Context | fixed window | hierarchical WM + unbounded episodic recall |
| Learning | offline gradient descent; frozen after | online local plasticity + replay; never frozen |
| Forgetting | catastrophic on fine-tune | none by construction (CLS + modularity) |
| Reasoning | implicit next-token | explicit typed operations, checkable intermediates |
| Verification | none intrinsic | Confidence + Self-Critic + tool verification built in |
| Improves with | more params/data | more experience + better organization |
| Energy | datacenter-scale | ~laptop, ~watts; compute follows surprise |
| Explainability | opaque | full provenance trace per answer |
| Failure mode | confident hallucination | calibrated "I don't know" |

CORTEX-OS is not a smaller transformer; it's a **different computational theory of mind** —
control-and-memory-centric rather than weights-centric. It *can* host a small neural LM (the
oscillatory/hybrid model) as the **language cortex**, but strictly as a realizer of already-
validated content, never as the source of facts.

---

## 22. Phased implementation plan

Each phase ships something usable and testable; no big-bang.

- **Phase 0 — Today [DONE].** Vio: verified math tools, TF-IDF retrieval + precision gate,
  grounded synthesis, skills, the solve-agent, PDF/GitHub ingestion, memory, the browser UI.
  *This is System-1 + seed retrieval + seed procedural memory.*
- **Phase 1 — Workspace & memory tiers. [IN PROGRESS]** Introduce the Cognitive Workspace
  (blackboard) and split memory into WM/EPI/SEM/PRO. **Shipped:** `kernel/workspace.py` (cognits,
  pub/sub, salience-gated ignition, decay/GC), `memory/working.py` (bounded slots),
  `memory/episodic.py` (autobiographical log with one-shot write + content/recency/reward recall),
  and Semantic/Procedural adapters over the existing library + skills. Wired into `Mind`: every
  interaction is now recorded as an episode, and Vio recalls past chats ("what did we talk
  about?", "did we discuss X?"). *Remaining:* migrate modules onto the Workspace bus; add
  embeddings alongside TF-IDF. *Grounds on `bl_advanced.py` episodic memory.*
- **Phase 2 — Executive, Confidence, Self-Critic.** Add the difficulty-priced Executive
  (two-clock), the calibrated Confidence Engine, and the Self-Critic loop. Generalize "I don't
  know" to every path. *Biggest single quality jump.*
- **Phase 3 — Reasoning modes & Planning.** Add the multi-mode reasoning dispatcher, the
  Knowledge Graph + causal graph, and the recursive Planner. *Grounds on the existing sympy
  engine as the math mode.*
- **Phase 4 — World Model & simulation.** Wire in the predictive-coding net
  (`predictive_coding_brain.py`) as the World Model; add internal rollouts + active inference for
  planning/abduction/counterfactuals.
- **Phase 5 — Learning, Consolidation, Curiosity, specialists.** Turn on the Learning Engine
  (experience→skill), the idle Consolidation "sleep", the Curiosity drive, and the specialist
  cortex (starting with Math + Networking, which already have knowledge). *This is where lifelong
  self-improvement begins.*
- **Phase 6 — Long-horizon.** Multi-device personal sync, community-shareable specialists,
  richer neural realizer (oscillatory/hybrid LM), continuous calibration dashboards.

Exit criteria per phase: measurable rise in first-try accuracy and System-1 hit-rate, and fall in
energy-per-answer and calibration error, on a fixed personal benchmark that grows with use.

---

## 23. Folder structure

Evolving `mind/` from a flat module set into a cognitive OS. Each module = an independently
testable package that only talks to `workspace/`.

```
mind/
├── kernel/
│   ├── workspace.py          # the blackboard: cognits, pub/sub, ignition, decay (§2)
│   ├── executive.py          # Executive Controller: activation set + budget (§5.1)
│   ├── attention.py          # Attention Controller: salience gating (§5.2)
│   └── scheduler.py          # two-clock loop, energy meter, idle detection (§15,§16)
├── memory/
│   ├── working.py            # WM: slots + oscillatory binding (§3.1)
│   ├── semantic.py           # KG + vector ANN + symbolic index (§3.2)  ← today's Library grows here
│   ├── episodic.py           # autobiographical log, one-shot write (§3.3)
│   ├── procedural.py         # procedure graphs; today's skills.py folds in (§3.4)
│   ├── representations.py    # the 8 views + Representation Router (§4)
│   └── consolidation.py      # the sleep cycle (§14)
├── cognition/
│   ├── reasoning.py          # 8-mode dispatcher (§7); wraps today's reasoner.py math tools
│   ├── planning.py           # recursive planner / plan DAGs (§8); grows from agent.py
│   ├── world_model.py        # predictive-coding net + causal graph + simulation (§9)
│   ├── confidence.py         # calibrated confidence fusion (§10)
│   ├── critic.py             # self-critique checklist + revise loop (§11)
│   ├── curiosity.py          # gap detection, learning goals, active inference (§12)
│   └── learning.py           # experience → episodic/procedural/semantic (§13)
├── specialists/
│   ├── base.py               # Specialist interface: can_handle(), activate()
│   ├── math_expert.py        # wraps the verified sympy engine (BUILT)
│   ├── networking_expert.py  # FortiOS etc. — owns ingested manual/repo knowledge (BUILT ingest)
│   ├── programming_expert.py · security_expert.py · research_expert.py · writer.py · …
├── language/
│   ├── understand.py         # NL intent → goal (today's talk.py grows here)
│   └── generate.py           # grounded realization + optional neural LM (think.py + bl_language_*)
├── io/
│   ├── ingest.py             # pdftext + gitlearn (read-only, BUILT) → memory writes
│   └── web.py                # the browser UI (BUILT) — now shows the reasoning trace live
├── data/                     # user-owned stores (gitignored): semantic/, episodic/, procedural/
└── COGNITIVE-OS-DESIGN.md    # pointer to this spec
```

Prototypes that become module cores live in `prototype/` today and graduate into `mind/` per
§24.

---

## 24. What already exists to build on

CORTEX-OS is an evolution, not a rewrite. The hardest neuroscience is **already running code**:

| CORTEX-OS module | Already prototyped as | Result |
|---|---|---|
| World Model / predictive processing | `prototype/predictive_coding_brain.py` | matches backprop, 100 %; free energy falls ~17× as it "perceives" |
| Working-memory binding / sequence | `prototype/selective_oscillatory_memory*.py` | stable long-range memory (MSE 0.0017 vs RNN 0.337); gated variant adds selection |
| Complementary fast/slow memory (EPI/SEM) | `prototype/bl_system.py`, `bl_advanced.py` | one-shot new class + **no catastrophic forgetting** |
| Sparse event-driven coding | `prototype/bl_torch.py` (k-WTA, V1 front-end) | 98.2 % MNIST, ~8 % neurons active, no backprop |
| Local lifelong learning | `prototype/bl_deep_local.py` | deep net to 96.9 % MNIST with **no backpropagation** |
| Language cortex (realizer) | `prototype/bl_language_{hybrid,sparse,fast}.py` | oscillator+sparse-attention LM, GPU-efficient |
| Reasoning (math mode), retrieval, procedural seed, ingestion, UI | `mind/` (reasoner, think, agent, skills, gitlearn, pdftext, web) | verified answers, grounded synthesis, learn-from-repo, browser chat |

The remaining work is **integration and control** — the Workspace, Executive, Confidence,
Self-Critic, Planner, and Consolidation that turn a box of brain parts into a mind. That is what
this specification defines.

---

*CORTEX-OS is the §05 (CORTEX) brain-native principles and §06 (AXIOM) first-principles
mechanisms, assembled into a buildable, laptop-scale cognitive operating system for Vio — designed
to get wiser the longer you use it.*
