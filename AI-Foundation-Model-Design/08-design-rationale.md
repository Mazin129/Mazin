# 8. Design Rationale — Why Vio Is Built the Way It Is

Companion to the redesign prompt's §2 ("challenge the one-master architecture") and
§23 item 2 ("problems with the current architecture"). Written from the implemented
system (`mind/`), not from aspirations. Every claim is checkable in code.

---

## Part I — The orchestration decision, on evidence

The prompt asked to compare ten candidate architectures and select on engineering
tradeoffs. Here is that comparison for Vio's actual constraints: **1 local machine,
1 small model (3B–7B), single user, sub-second reflexes preferred, honesty mandatory**.

| Architecture | Quality | Latency | Cost/energy | Fault tolerance | Context mgmt | Verdict for Vio |
|---|---|---|---|---|---|---|
| Central orchestrator ("one master") | medium — every query pays orchestration | poor at scale | high (LLM in the loop per hop) | single point of failure | orchestrator context bloats | the prompt's target: rejected as the *sole* mechanism |
| Hierarchical (executive → master → workers) | good — cheap scores route, expensive reasoning only where earned | excellent (System-1 short-circuits most traffic) | low | degrades to base router if master fails | small per-stage contexts | **adopted (top half)** |
| Planner + workers | good for long tasks | poor for chat (plan-first tax) | high | planner is a SPOF | good | rejected as default; planner survives as a *capability* (`planner` agent) |
| Blackboard (shared workspace) | good — modules decouple via published facts | good | low | good | bounded (TTL/GC) | **adopted (bottom half)** — `kernel/workspace.py` cognits carry percept→answer provenance |
| Event-driven | good decoupling | good | low | good, but hard to trace | risk of unbounded chains | partially adopted (publish/subscribe in the Workspace); full event bus rejected — traceability suffers |
| Capability routing (score → dispatch) | good | excellent (one cheap pass) | lowest | first *validated* result wins, losers free | per-agent only | **adopted** — the `Registry.ranked`/`Master.handle` core |
| Mixture-of-agents (all answer, merge) | highest ceiling | poor (k× model calls) | high | good | merge context large | adopted only on explicit `council:` requests, capped k=3, advisory-only |
| Supervisor/worker | ≈ hierarchical | ≈ hierarchical | ≈ | ≈ | ≈ | subsumed by the hierarchical choice |
| Graph orchestration (LangGraph-style) | excellent for multi-step | per-node overhead | medium | explicit retries/resume | good | rejected for now: no long-horizon tasks yet; revisit when multi-step acting tools exist |
| Hybrid | best fit | best fit | best fit | good | good | **the choice** |

**Selected: hybrid — evidence-class planning → hierarchical dispatch → shared-memory
collaboration → blackboard tracing.**

The decision chain, and where each piece lives:

1. `brain.py` reads the question into a structured `Understanding` (form, subject,
   evidence class) and `decide()` picks a strategy **before** any search — an impossible
   question is refused before it can be answered badly (the "no-source" contract).
2. `kernel/executive.py` chooses System-1 (fast, intrinsically correct paths) vs
   System-2 (deliberation tail: confidence engine + self-critic). Most traffic never
   wakes the expensive machinery — the energy story.
3. `agents.py` `Master` scores every agent (cheap, side-effect-free), dispatches the
   highest fit inside a `Task` record, validates, and passes the result through the
   `Guardrail` (autonomy levels §22).
4. Agents never talk to each other; they collaborate through the **shared Mind**
   (library, memory, skills, graph, episodes) and, on request, through `council()`.
   This kills the two failure modes the prompt worries about — uncontrolled agent chat
   and infinite delegation loops — *structurally*, not by policy: an agent cannot call
   another agent, so recursion is impossible by construction.
5. `kernel/workspace.py` publishes cognits (percept → answer with provenance) so every
   decision is replayable — the observability backbone.

Why this beats a pure central orchestrator: the master is no longer a bottleneck — it
owns *dispatch*, not intelligence. Routing decisions are 0–1 score evaluations (no LLM);
the model is invoked only by the agent that needs it. Why it beats free-form agent
meshes: no emergent loops, no prompt-injection relays between agents, bounded cost per
question by construction.

## Part II — Problems with the (historical) architecture, and their resolutions

The v0 system decided what to do by racing ~130 hand-written regexes; each was a patch
for one observed failure (`brain.py` header documents this). Consolidated register of
the systemic problems and where each is now solved:

| Problem (prompt §1 category) | Was | Now |
|---|---|---|
| Hallucination | LLM answered from its own memory while looking grounded | grounded-only prompts + validated-passage split (`llm.py`) + verified badge needs validated evidence (`reasoner.py`, `brain.verify`) |
| Context loss between turns | none | episodic memory + working memory + corrections served first |
| Knowledge contamination | manual prose served as device data | evidence-class plan (`brain.decide`) refuses `need-config` questions before routing |
| Infinite delegation loops | N/A (agents couldn't talk) | still impossible: no agent→agent calls; bounded `cover gaps` (8×2); capped stores |
| Stale knowledge | no timestamps | provenance per passage (`knowledge_meta.json`); research cache TTL; freshness = unvalidated-until-revalidated on the roadmap |
| Unvalidated web content → trusted | auto-learned pages grounded as "authoritative" | validation gate: trusted domain or ≥2 domains ⇒ validated; else flagged leads that can never verify |
| Token waste / excessive LLM calls | hidden calls, no accounting | cortex audit (`r["cortex"]`), call/token counters (`llm.usage()`), System-1 short-circuits |
| Tool abuse | no acting tools | guardrail + permission tokens + autonomy ladder; still zero write tools by design |
| Prompt injection via web | fetched text passed to prompts undifferentiated | "data not instructions" + unvalidated-lead framing; layered defenses remain a debt (Part III) |
| Bad self-learning | none | governed loop: sandbox eval → golden gate → human approval → versioned rollback (`selfimprove.py`) |

## Part III — Honest debt register (what is still weak)

1. **Model ceiling.** A 2 GB GPU caps the reasoning cortex at ~3B; analytic depth is
   bounded until a bigger GPU or hosted endpoint. The switcher is ready; the hardware
   is the limit (BLUEPRINT §19).
2. **Retrieval is TF-IDF + optional embeddings.** No reranker stage, no hybrid BM25,
   no chunk-level citation of *which sentence* answered. Adequate for the library
   sizes in use; the first thing to upgrade for 100k+ passages.
3. **Intent regexes remain at the edges.** `brain.py` replaced the per-symptom patches
   with one general rule, but agent *scoring* and command *triggers* are still regex
   surfaces — novel phrasings fall to the catch-alls (which degrade honestly).
   An `AgentSpec` (declarative, learnable) is the planned successor.
4. **JSON stores, not a database.** Every store is a JSON file rewritten on change.
   Fine at personal scale (tens of MB); a real vector store + SQLite is the migration
   path, and `SemanticMemory`'s adapter interface is built so nothing above it changes.
5. **Conflict resolution between sources is not implemented.** The critic detects
   contradiction with *past answers*; contradicting *passages* still coexist. The
   provenance layer (origin/ts/validated) is the substrate the resolver will need.
6. **Model routing is opt-in and family-local** (`VIO_MODEL_ROUTING=1` routes within
   the most-preferred installed family). Cross-family routing and quality-aware
   selection (per-model eval scores) are future work.
7. **No long-horizon autonomy.** No scheduler, no acting tools, no multi-step graph
   execution — deliberately (BLUEPRINT §20). The Task schema and autonomy ladder exist
   so that adding them is behavior change, not interface change.
8. **Council parallelism shares side-channels.** Contributions run in parallel, but
   agents stash retrieval evidence on the shared Mind; the last writer wins. Harmless
   today (council synthesis doesn't read it), worth per-agent evidence bags later.
