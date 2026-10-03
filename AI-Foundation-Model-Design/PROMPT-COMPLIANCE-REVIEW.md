# Vio — Compliance Review Against the Redesign Prompt

**Reviewed:** `Mazin/AI-Foundation-Model-Design/` (docs 01–07, `chat/`, `mind/` implementation, `prototype/`)
**Against:** `Vio_Advanced_AI_Architecture_Redesign_Prompt.md` (23 sections + Mission + Current-Vio constraints + 30-item deliverable + Most Important Requirement)
**Date:** 2026-10-03

**Legend:** ✅ implemented · 🟡 partial · ❌ missing/violated

---

## 0. Executive summary

The codebase is **substantially aligned in spirit and about half-aligned in letter**. It is
not "a chatbot with many prompts" — it is a genuine cognitive system (intent engine,
two-clock executive, confidence engine, self-critic, quality gate, memory tiers, curiosity,
governed self-improvement) with unusually strong honesty/verification discipline and good
web-layer security.

The largest gaps against the prompt are **structural**, not cosmetic:

1. **Knowledge provenance is absent** (§5): library passages are plain strings — no source,
   timestamp, version, confidence, freshness, or validity tracking; web pages learned from
   research immediately become "authoritative facts" for grounding (poisoning / indirect
   prompt-injection surface, §12).
2. **No agent message/task schema** (§3): no task IDs, priority, timeouts, retry policy,
   cancellation, status, or error propagation. `Result` carries only
   answer/how/verified/confidence/agent/trace.
3. **`math` is still a dedicated agent** — the prompt explicitly forbids this.
4. **Skills are not executable, versioned, or tested** (§8) — they are reply templates
   (a deliberate safety choice, but the prompt's registry/testing/versioning requirements
   are unmet).
5. **No model router** (§14/§15): one local model + manual switcher; no fast/reasoning/
   coding/vision/embedding routing (embedding re-rank exists only as retrieval enhancement).
6. **Workflow examples A–E (§19), formal data schemas (§23 items 20–21) are not written
   anywhere.**

I also found **5 real code defects** during the review (§B below), including one that makes
a golden-suite safety check vacuously pass and one `NameError` that misreports folder learning.

| Prompt area | Verdict |
|---|---|
| Mission capabilities (18 bullets) | 10 ✅ · 7 🟡 · 1 ❌ |
| Current-Vio constraints (8) | 6 ✅ · 1 🟡 · 1 ❌ (math agent) |
| Sections 1–23 | 6 ✅ · 13 🟡 · 4 ❌ |
| 30-item final deliverable | 10 ✅ · 14 🟡 · 6 ❌ |
| Most Important Requirement (cognitive OS, not chatbot) | ✅ |

---

## 1. Mission checklist (prompt "Vio must be able to…")

| # | Requirement | Verdict | Evidence |
|---|---|---|---|
| 1 | Understand intent, not only literal words | ✅ | `mind/brain.py:222-302` — `understand()` classifies form/subject/host/vendor and the *evidence class* required (CONFIG/KNOWLEDGE/MEMORY/REASONING/TOOL/LIVE); instance-vs-concept rule is genuinely general |
| 2 | Reason about complex problems | 🟡 | Open LLM reasoning (`reasoner.py:2782-2896`), structured graph reasoning (`cognition/reasoning.py`), planner, world model — bounded by 3B/7B local models; BLUEPRINT §19 is honest about the ceiling |
| 3 | Research the internet when necessary | 🟡 | `WebResearchAgent` + `Mind.research()` (`reasoner.py:1468-1543`) fire on **explicit requests only**; the "when Vio doesn't know → auto-research" loop exists only as the manual `cover gaps` command (`reasoner.py:1681-1722`) |
| 4 | Retrieve and validate knowledge | ✅ | Precision gate, distinctive-term gate, number gate, domain gate, stub gate (`reasoner.py:2687-2771`), fragment gate (`brain.py:656-716`) |
| 5 | Use tools safely | 🟡 | Guardrail + READ/WRITE/NETWORK permissions (`agents.py:615-639`); no shell/Python exec by design — safe, but the tool layer is thin (§11 below) |
| 6 | Learn new knowledge and skills | ✅ | `teach:`/`remember:`/📄/GitHub/datasets + `SkillBook` + `SkillProposalStore` |
| 7 | Create, test, improve, version, reuse skills | 🟡 | Create ✅ reuse ✅; **test ❌ version ❌ improve ❌** (`skills.py` — no version or test fields) |
| 8 | Remember useful information | ✅ | `mind_memory.json` facts, episodic store, solved-cache, corrections |
| 9 | Learn from mistakes and user corrections | ✅ | `corrections.json` served before routing (`reasoner.py:1986-1990`), 👍/👎 grading, calibration scalar, consolidation prune-by-reward |
| 10 | Coordinate specialized capabilities | ✅ | `Master` score→dispatch→validate→guardrail (`agents.py:642-662`), `council()` multi-agent synthesis (`agents.py:664-691`, `reasoner.py:2225-2261`) |
| 11 | Verify important answers | ✅ | Confidence engine + self-critic + `brain.verify()` final gate + sympy substitute-back verification + golden suite — the strongest area |
| 12 | Recover from failures | 🟡 | Fallback chains (search engines, no-LLM degradation, excerpt fallback); no circuit breaker / task cancellation (§13) |
| 13 | Maintain long-term knowledge | ✅ | Persistent JSON stores, consolidation "sleep" cycle (`cognition/consolidation.py`) |
| 14 | Improve workflows continuously | 🟡 | Idle consolidation, promote-repeats, calibration refresh; no workflow-level improvement loop |
| 15 | Avoid hallucination | ✅ | Grounded prompts ("answer only from facts"), unverified labeling, abstention (`llm.py:170-211`, critic honesty threshold 0.35) |
| 16 | Know when it doesn't know | ✅ | `no-source` honest fallback, LIVE-data abstention, curiosity gaps, shortfall messages naming exactly what's missing (`brain.py:533-566`) |
| 17 | Determine what capabilities a task requires | ✅ | `brain.decide()` plans strategy from required-evidence vs held-evidence **before** routing (`brain.py:470-530`) — this is the prompt's "determine required capabilities", done well |
| 18 | Multi-domain, specializing in network/security | 🟡 | 22 vendor/topic datasets + merged `NetworkEngineeringAgent`; new domains currently require a Python subclass (declarative `AgentSpec` is roadmap-only, BLUEPRINT §19) |

---

## 2. Current-Vio constraints (prompt "Current architectural requirement")

| Requirement | Verdict | Evidence |
|---|---|---|
| Agents not isolated | ✅ | All agents share the Mind (library, memory, skills, graph, episodic) |
| Agents not blindly communicating directly | ✅ | No agent-to-agent calls; collaboration via shared brain + orchestrated council |
| Master/Core coordinates work | ✅ | `Master.handle()` (`agents.py:651-662`); `Executive` two-clock above it (`kernel/executive.py`) |
| Shared knowledge/memory/skills/validated research | 🟡 | Shared ✅; research is **not validated** before entering the shared library (see §6 below) |
| Research can access internet | ✅ | `websearch.py` (DuckDuckGo→Bing→DDG-lite), gated by `VIO_ALLOW_NET` |
| One capability's discoveries reusable by all | ✅ | Everything lands in the shared library/graph ("what any one learns, all can use") |
| Replaceable / model-agnostic | 🟡 | `llm.py` abstracts the model and auto-picks; **Ollama API only** — a non-Ollama backend needs code, and there is no model-router abstraction (§14/15) |
| **`math` should NOT be a dedicated agent** | ❌ | `MathAgent` is registered in `DEFAULT_AGENTS` (`agents.py:99-112, 585-587`) and listed in BLUEPRINT §4. Direct violation of an explicit prompt instruction — fold math into the core router's exact-tool branch (it already exists there: `reasoner.py:2601-2607`) and delete the agent |

Note: the prompt's premise says the current model is `Qwen3.5:4B`; the code auto-picks
`qwen2.5:3b/7b` (`llm.py:42-43`). No hard-coding (good), but the docs and the prompt
disagree on what "current" is — worth reconciling in BLUEPRINT §5.

---

## 3. Section-by-section compliance

### §1 Critically audit the current design — 🟡
The audit exists but is distributed, not consolidated: `brain.py:1-46` documents the old
~130-regex failure mode; BLUEPRINT §7.5 documents quality problems; agent docstrings
document merges and dead bugs. There is **no single "problems with the current
architecture" document** (deliverable item 2). The 29 named weakness categories are mostly
addressed in code (loops, token waste, hallucination, delegation) but several are not
analyzed anywhere: knowledge contamination, stale knowledge, memory poisoning, tool abuse.

### §2 Challenge the "one master" architecture — 🟡
Implementation-wise the master was demoted: `Executive` (two-clock) → `Master` (dispatch)
→ agents, plus a `Workspace` blackboard (`kernel/workspace.py`) with publish/subscribe —
so the live design is a **hybrid: hierarchical orchestrator + blackboard**. However the
prompt's actual request — *compare* the 9 candidate architectures (central, hierarchical,
planner+workers, blackboard, event-driven, capability routing, MoA, supervisor/worker,
graph, hybrid) on the 10 criteria and justify the choice on evidence — is **not done
anywhere in the docs**. The choice is implied by the code, never argued.

### §3 Real agent communication + message schema — ❌ (as specified)
The preferred flow (request → orchestrator → capability → result+evidence → shared state)
matches the implementation, and `council` is the documented safe form of controlled
multi-agent exchange. But the required **message schema is absent**: of the 16 required
fields (Task ID, Parent task, Requester, Capability, Priority, Context, Inputs, Expected
output, Timeout, Retry policy, Confidence, Evidence, Status, Error, Cancellation,
Permissions), only Context (`ctx` dict), Confidence, Evidence (`_last_evidence`,
side-channel), and Permissions (agent-level, not message-level) exist in any form.
`Result` (`agents.py:32-51`) carries answer/how/verified/confidence/agent/trace. `Cognit`
(`kernel/workspace.py:41-60`) has id/type/provenance/salience/ttl but is used only for
percept→answer tracing, not capability requests. Agents **cannot request a capability
from another agent at all** — a deliberate simplification the prompt allows only if
justified; no such justification is written.

### §4 Shared intelligence layers — 🟡 (7 ✅ / 4 🟡 / 1 ❌ of 12)

| Layer | Status | Where |
|---|---|---|
| Working memory | ✅ | `memory/working.py` (7±2 slots, salience displacement) |
| Conversation memory | ✅ | episodic store, kind="chat" |
| Episodic memory | ✅ | `memory/episodic.py` (cue/detail/outcome/reward/tags; capped 20k; prune policy) |
| Semantic memory | ✅ | `memory/semantic.py` (adapter over Library) |
| Procedural memory | ✅ | `memory/procedural.py` (skills + solved cache, `reinforce()`) |
| Skill registry | ✅ | `skills.py` + `skill_proposals.py` |
| Knowledge base | ✅ | `Library` (TF-IDF + optional transformer re-rank) |
| Research cache | ❌ | none — identical research queries re-fetch every time; only the *answer* path reuses learned passages |
| User preferences | 🟡 | `mem["facts"]` (free text, no preference semantics) |
| System state | 🟡 | `model_state.json`, telemetry snapshot — not a defined store |
| Task state | 🟡 | `Workspace` cognits — in-RAM, expires by TTL, not persistent |
| Experience / feedback | ✅ | episodic grades (correct/wrong), `traces.jsonl` feedback events |

Per-layer lifecycle attributes (how data enters/is retrieved/is validated/expires/conflict
resolution/supersession) are documented for episodic and working only. **Conflict
resolution between contradicting passages does not exist** (the critic detects
contradictions with *past answers*, not between *sources*).

### §5 Knowledge system — ❌ (the biggest structural gap)
Content-type coverage is good: documents ✅, web ✅, vendor docs ✅ (`sources.py`),
standards/RFC ✅ (RFC 4271), configs ✅ (`configparse`), user info ✅, previous solutions ✅
(solved cache), agent discoveries ✅. Code/logs only partially (gitlearn skips code files).

But the required **tracking metadata is absent**: `Library.docs` are plain strings with no
source, author, timestamp, retrieval date, version, domain, confidence, evidence,
freshness, validity, or relationships. Only `graph.json` adds relations, and
`mem["last_learned"]` remembers the most recent source only. Consequences:

- No freshness/expiry — a 2019 FortiOS passage and today's doc are indistinguishable.
- No supersession — a corrected fact cannot retire the wrong one (only `corrections.json`
  does this for exact question matches).
- The 8 knowledge classes (FACT / ASSUMPTION / HYPOTHESIS / USER-PROVIDED / MODEL
  KNOWLEDGE / RESEARCH RESULT / VALIDATED / OUTDATED / CONFLICTING) are **not modeled**;
  the nearest analog is the verified/unverified flag (2 of 8).
- **"Do not allow unvalidated web content to automatically become trusted knowledge" is
  violated**: `research()` learns every fetched page into the library
  (`reasoner.py:1515`), and `grounded_prompt` later hands passages to the LLM labelled
  *"authoritative"* (`llm.py:171-178, 196-205`). A poisoned page is therefore one
  `research:` away from becoming trusted grounding — exactly the §12 threat
  (knowledge poisoning / indirect prompt injection).

### §6 Autonomous research — 🟡
Flow present: question → check library → gap detection (curiosity) → research → collect →
store → answer, with citations. Missing: **compare sources** (no cross-source agreement
check), **validate** (no authoritativeness test on general results), **freshness**
determination, **disagreement detection**, **how-many-sources** reasoning (fixed `k=4`),
and **whether more research is needed** (no iteration). Source preference order
(official docs → vendor → RFC → repos → trusted → community) exists only as the curated
`sources.py` catalog used by `learn essentials`; general `research:` treats all results
equally. "Never treat search results as automatically correct" — contradicted by the
auto-learn behavior above.

### §7 Real self-learning pipeline — 🟡
Implemented stages: experience (traces) ✅, feedback ✅, error detection 🟡 (no-source →
gap; critic flags), knowledge gap ✅ (curiosity), research ✅, concept extraction 🟡
(`draft_from_research` LLM draft), skill formation 🟡 (proposals), **testing ❌**
(no test runs on learned knowledge/skills), validation 🟡 (golden gate covers models only),
**versioning ❌**, deployment ✅ (approve → install), monitoring 🟡 (skill matches become
episodes; no success-rate tracking). The five separations: knowledge ✅, skills ✅,
behavior 🟡, **workflows ❌**, system-itself ✅ (governed loop).

### §8 Skill learning — 🟡
"A skill must be executable, not merely a text description" — **not met**: skills are
trigger→reply templates (pure data, `skills.py:1-21`). This is a defensible safety choice
(no eval/exec, regex-escaped triggers), but the prompt's Skill Registry is not: of the 16
required fields only Name, Trigger (≈Inputs), Reply (≈Procedure/Expected output), and — on
proposals — ID, Status, Source, Evidence, Owner(agent), Timestamp exist (≈8/16). Lifecycle:
discovery ✅ (`match`), creation ✅, **testing ❌, versioning ❌, improvement ❌**,
disable 🟡 (`remove`, no disable), **rollback ❌**. "Independently testable" ❌ — approving
a proposal installs it untested directly into the live SkillBook
(`skill_proposals.py:107-121`).

### §9 Safe self-improvement — ✅ (for models) / 🟡 overall
The model path is the prompt's flow almost exactly: failure→…→candidate→**isolated sandbox
eval** (throwaway `VIO_DATA_DIR` subprocess, `selfimprove.py:169-189`)→tests
(`capability_test.py`)→compare/regression (**golden suite** with correctness/safety/latency
gates, `golden_eval.py:205-215`)→reject/rollback ✅ (`ModelManager.rollback`)→approval gate
✅ (nothing promotes without `approved=True`; `promote()` re-runs golden)→deploy→monitor 🟡.
Six separations: model ✅, knowledge ❌ (teach/learn write ungated), skill 🟡 (no test),
**prompt ❌, workflow ❌**, code ✅ (rewriting own Python is forbidden — `agents.py:6-9`,
BLUEPRINT §20 forbidden table). "Critical system changes require explicit approval" ✅.

### §10 Verification architecture — ✅ (strongest section)
Generate → Critique ✅ (`cognition/critic.py`: conflict check vs episodic memory incl.
numeric-contradiction detection, re-search with better support, config-dump downgrade)
→ Verify evidence ✅ (`brain.verify()` on **every** path: never verify weak/empty/fragmentary;
factual/security claims need evidence or are labelled "unverified (no local evidence)";
citations appended) → Check assumptions ✅ (evidence-class plan is authoritative;
`need-config`/`abstain` refuse before routing) → Run tests/tools ✅ (sympy substitutes
solutions back, deterministic config counts, golden suite) → Resolve disagreement 🟡
(council merge "note where they disagree") → Final answer ✅. Proportional to risk:
System-1/System-2 (`kernel/executive.py`) scales effort by path certainty — good, but not
by *operational* risk (no acting operations exist yet, so the critical-infrastructure
ladder — simulate → security check → human approval → execute → verify — is not designed
anywhere; it becomes mandatory the day a WRITE tool is added).

### §11 Tool architecture — 🟡
Present: Web ✅, Files (read/ingest) ✅, Git (learn, read-only) ✅, Math/tools ✅,
Data tables ✅, Diagrams ✅, Security config audit ✅, Monitoring (doctor) 🟡.
**Absent: Shell, Python exec, Databases, generic APIs, Network tools (live device access),
Cloud APIs** — partly deliberate (BLUEPRINT §20 forbids exec), but the prompt asks for the
layer; there is **no tool registry** — tools are function calls inside `_core_front`.
Tool attributes: permissions ✅ (agent-level), scope ✅ (`VIO_NET_ALLOW/BLOCK`),
auth ✅ (web token), audit 🟡 (traces record agent/how, not per-tool calls), timeout ✅
(net 15 s, LLM 300 s), **rate limits ❌, approval ✅ (guardrail), rollback 🟡** (models
only). Action classes: only READ/WRITE/NETWORK — **ANALYZE, EXECUTE, DESTRUCTIVE are not
separated** (nothing holds WRITE today, so high-risk gating is untested in practice).

### §12 Security architecture — 🟡 (strong web layer, weak knowledge layer)
Covered: SSRF guard incl. redirect re-validation ✅ (`websearch.py:81-128`), scheme guard,
size/time caps, token auth with constant-time compare + throttle + HttpOnly/SameSite=
Strict (+Secure) cookie ✅, bind guard refusing non-local without token ✅, host-allowlist
(anti DNS-rebinding) ✅, least-privilege agent permissions ✅, secret isolation
(git-ignored token/data) ✅, audit traces ✅, human approval gates ✅, supply-chain 🟡
(vendored skill pinned with license; `trainpipe.py` license-gates training data).
**Gaps:** knowledge/memory poisoning 🟡→❌ (taught and researched text enters the library
unvalidated and later grounds "verified" answers — the indirect-injection chain in §5
above); malicious-document handling relies on "text is data" but learned text is later
relabeled authoritative; no policy engine (env-var gates only); no sandboxing; prompt
improvement security N/A. Prompt §12's own list is the right checklist — items
"poisoned web content", "memory poisoning", "knowledge poisoning", "indirect prompt
injection" are currently open.

### §13 Failure recovery — 🟡
Timeout ✅ (LLM 300 s / net 15 s), retry 🟡 (search-engine fallback chain; no per-task
retry policy), fallback ✅ (no-LLM lexical degradation, excerpt fallback, smaller-model
advice), alternative capability ✅ (master falls through the ranked agents; first
validated result wins), alternative model 🟡 (manual switch only), degraded mode ✅,
**circuit breaker ❌, task cancellation ❌**, rollback ✅ (model manager), human escalation
✅ (guardrail "reply confirm"). Loop prevention: infinite loops / recursive delegation
structurally impossible (agents never call agents; `cover gaps` bounded 8×2;
consolidation time-sliced 400 ms; MAX_EDGES/MAX_GAPS/MAX_EPISODES caps) ✅; repeated
failed searches 🟡 (a gap that fails `cover gaps` stays open and will be retried next run
— bounded but unremembered). "Bounded execution policy per task" 🟡 — timeouts only, no
deadline/budget object.

### §14 Model strategy — 🟡
Single local model with live switcher + auto-pick preference order + from-scratch own
model + no-LLM fallback. **No model router** by task type (fast/reasoning/coding/research),
no vision, no speech, no reranker (embedding model exists solely to re-rank retrieval).
Hybrid local/cloud 🟡 (point `VIO_LLM_URL` at a hosted endpoint — same protocol).
Quality/latency/cost/privacy/hardware tradeoffs are honestly documented (BLUEPRINT §5, §19).

### §15 Model-agnostic Vio — 🟡✅
No hard-coded model ✅ (`llm.py` preference list, `VIO_LLM_MODEL` override, dashboard
switch, `ModelManager` for promotions). 4B→9B→14B→27B growth path: acknowledged as a
hardware ceiling with the same switcher pointed at a bigger endpoint (BLUEPRINT §19) ✅ —
no rewrite needed. Deduction: the *interface* is Ollama-shaped only; a non-Ollama
provider means editing `llm.py`, so "model interface → model router → N backends" from the
prompt is not yet an architecture, just a client.

### §16 Network & security domain — 🟡 (~17/22)
FortiGate ✅ (datasets + `configparse` + `configaudit` review), F5 ✅, Cloudflare 🟡,
Azure ✅, AWS ✅, Cisco ✅, Routing/Switching/BGP/OSPF ✅, VPN ✅, IPsec ✅, Kubernetes ✅,
Cloud networking ✅, Security incidents ✅, Logs 🟡, Configurations ✅, Architecture ✅,
Troubleshooting ✅, Threat modeling ✅. **Gaps in the expert's intent regex
(`agents.py:508-534`): SD-WAN, NAC, WAF, DDoS have no trigger terms** — the knowledge
exists in `datasets/` (cisco SD-WAN, cloudflare WAF/DDoS, f5 Advanced WAF, forescout NAC)
and retrieval can still find it, but `network_engineering` will not self-select on those
questions alone. "Not permanently hard-coded to networking" 🟡 — adding a domain means
writing a Python subclass; the declarative `AgentSpec` is explicitly future work.

### §17 Final agent architecture — 🟡
Removals/merges: excellent and documented — the prompt's 14-agent list shrank to 12 with
`learning`→`cognition/learning.py`, `self_improvement`→`selfimprove.py`, `data`→
`datatable`+config engines, and the per-domain experts merged into one
`network_engineering` (with reasons in docstrings). Violations: **math still an agent**
(see §2 above); `ConfigAgent`, `TroubleshootingAgent`, `SecurityReviewAgent` are defined
but never registered (`agents.py:162, 424, 436` vs `DEFAULT_AGENTS:585-587`) — dead code.
Per-capability definitions: roster exposes name/domains/permissions only — the required
12 attributes (Inputs, Outputs, Tools, When invoked, **When NOT invoked**, Dependencies,
Restrictions…) are scattered through docstrings, not specified. `agent_from_how`
(`agents.py:285-305`) returns provenance names for agents that don't exist
("tools", "data", "self_improvement", "feedback", "generation") — traces show phantom agents.

### §18 Final architecture diagram — ✅
BLUEPRINT §2 system map + §3 request lifecycle cover the prompt's chain (user → interface
→ intent/context (brain) → orchestrator (executive/Master) → capability router (registry)
→ capabilities/knowledge/memory/research/tools → verification (quality gate) → shared
state → learning → response). "Task Manager" and the verification node are inside the
executive/quality stages rather than drawn boxes; acceptable, worth one edit.

### §19 Required workflow examples A–E — ❌ as deliverable / 🟡 as mechanisms
- **A — FortiGate HA troubleshooting:** mechanism exists (analytical diagnose routing,
  config audit, grounded expert) but no worked example is written out.
- **B — Teach yourself:** `train skill: <topic>` → research → proposal → approve → reuse —
  the full chain exists (`reasoner.py:1562-1568`, `skill_proposals.py`); not documented as
  an example with steps.
- **C — User correction:** `correct:`/`answer is` → stored correction → served first —
  exists (`reasoner.py:1889-1924`); the prompt's "regression test + error classification"
  steps do not.
- **D — Missing knowledge:** gap → `cover gaps` → research → learn → answer — exists
  (`curiosity.py`, `reasoner.py:1681-1722`); source-validation step missing.
- **E — Multi-agent cooperation:** `council:` exists (`agents.py:664-691`).
The prompt asks to *demonstrate* the redesigned Vio using these examples — none are
written anywhere in docs 01–07 or BLUEPRINT.

### §20 Performance — 🟡
Prevents: too-many-agents ✅ (12, merged), excessive context ✅ (chunking, 60-object cap,
4k-char contexts), repeated retrieval ✅ (solved cache), duplicate knowledge ✅
(consolidation merge), infinite loops ✅, LLM-call discipline 🟡 (cortex audit counts
calls; no budget — council can make 4 LLM calls per question), **repeated research ❌
(no research cache)**, duplicate reasoning 🟡. Techniques: routing ✅, context
compression ✅, result reuse ✅, confidence thresholds ✅ (critic 0.55/0.35), adaptive
verification ✅ (System-1/2), early stopping 🟡, prioritization 🟡 (scores),
caching 🟡, **parallel execution ❌** — council contributions and `cover gaps` run
sequentially in one thread.

### §21 Observability — 🟡
Traceability ✅ — `traces.jsonl` records id/ts/question/agent/how/verified/confidence/
evidence/citations/reasoning/answer; results carry `understood`/`intent`/`plan`/
`cortex` (ran|skipped|failed|unavailable) — the prompt's TaskID→…→FinalResponse chain is
largely there, plus a live dashboard (System-1/2 split, calibration plot, domains).
Metrics: accuracy ✅ (calibration, Brier), latency ✅ (llm ms, golden per-case),
capability utilization ✅ (`by_agent`), user corrections ✅ (countable), regression ✅
(golden), retrieval/research quality 🟡, failure rate 🟡, **token usage ❌** (only a max
cap — Ollama returns eval counts; they are discarded, `llm.py:145`),
**tool success ❌, hallucination rate ❌** (unmeasured; calibration is the proxy),
**skill success rate ❌**.

### §22 Human control — 🟡
The three levels exist in substance but are not formalized: ADVISORY = read-only agents
(the default for everything), ASSISTED = guardrail "reply confirm" for acting results,
AUTONOMOUS = standing consent via `VIO_ALLOW_NET` for web research; WRITE always gates;
BLUEPRINT §20's allowed/forbidden table is effectively "what should not be autonomous
yet". Missing: the named 3-level model, per-operation risk classification, and the
critical-infrastructure approval ladder (see §10).

---

## 4. The 30-item final deliverable (§23)

| # | Item | Verdict | Where / gap |
|---|---|---|---|
| 1 | Executive assessment | ✅ | BLUEPRINT intro + §19 |
| 2 | Problems with current architecture | 🟡 | scattered (brain.py header, §7.5, docstrings) — no consolidated doc |
| 3 | Recommended architecture | ✅ | BLUEPRINT §2 |
| 4 | Final capability/agent list | ✅ | BLUEPRINT §4 (12 agents) |
| 5 | Responsibilities | 🟡 | "fires on" table; not the full 12-attribute spec |
| 6 | Communication architecture | ✅ | BLUEPRINT §2 + agents.py contract |
| 7 | Shared-state architecture | 🟡 | shared brain ✅; Workspace blackboard exists but only executive posts to it |
| 8 | Memory architecture | ✅ | BLUEPRINT §6 + memory/ modules |
| 9 | Knowledge architecture | 🟡 | library+graph+gaps; **no provenance/validity model** |
| 10 | Research architecture | 🟡 | search+fetch+learn+cite; **no validation/comparison** |
| 11 | Skill-learning architecture | 🟡 | proposals+approval; not executable/versioned/tested |
| 12 | Self-improvement architecture | ✅ | selfimprove.py + golden gate + rollback |
| 13 | Verification architecture | ✅ | §7.5 + critic/confidence/quality/golden |
| 14 | Tool architecture | 🟡 | no tool registry; 3 of 5 action classes |
| 15 | Security architecture | ✅/🟡 | web layer strong (§10 + SECURITY.md); knowledge-poisoning gap open |
| 16 | Model-routing architecture | 🟡 | switcher, not router |
| 17 | Failure-recovery architecture | 🟡 | fallbacks yes; breaker/cancellation no |
| 18 | Observability architecture | ✅ | traces + telemetry + dashboard |
| 19 | Human-approval architecture | ✅ | guardrail + promote gates + §20 table |
| 20 | Data schemas | ❌ | no formal schemas for any store (JSON blobs) |
| 21 | Capability/message schemas | ❌ | see §3 above |
| 22 | Task lifecycle | 🟡 | request lifecycle documented; no formal state machine |
| 23 | Example workflows A–E | ❌ | mechanisms exist; examples not written |
| 24 | Technology recommendations | 🟡 | Ollama/Tailscale/Docker/sentence-transformers named in passing |
| 25 | Implementation roadmap | 🟡 | BLUEPRINT §19 "next ideas"; doc 07 §22 phases (CORTEX-OS-specific) |
| 26 | Phase 1 MVP | 🟡 | doc 07 §22; mind/ is already past MVP |
| 27 | Phase 2 | 🟡 | doc 07 §22 |
| 28 | Phase 3 | 🟡 | doc 07 §22 |
| 29 | Long-term autonomous Vio | ✅ | BLUEPRINT §20 — the governed-autonomy end-state |
| 30 | What should NOT be implemented yet | ✅ | BLUEPRINT §20 forbidden table (no self-exec, no auto-install, no auto-promote) |

---

## 5. Most Important Requirement — ✅

"Do not design Vio as a chatbot with many prompts; design it as an intelligent operating
system for AI capabilities." **Met.** Doc 07 is literally titled "CORTEX-OS — Redesigning
Vio as a Cognitive Operating System"; the LLM is one swappable component ("cortex") behind
an executive that decides when it runs at all; system intelligence comes from memory
tiers + knowledge graph + curiosity + skills + planning + confidence + critic + governed
self-improvement, with deterministic tools outranking the model. The `cortex` audit field
even tells you per answer whether the model ran, was skipped, or failed.

---

## 6. Bugs found during this review (not in the prompt — found in the code)

1. **`learn_folder` NameError — files reported as "skipped" while actually being learned**
   (`reasoner.py:1287-1289`): after `all_chunks.extend(self._smart_chunks(text))` the code
   appends `f"{len(chunks)} passages"` but `chunks` is never defined in that scope →
   `NameError` caught by the outer handler → the file lands in `skipped` with
   "name 'chunks' is not defined" even though its passages were already added and
   `learned` is never incremented. Fix: compute `chunks = self._smart_chunks(text)` first.
2. **Vacuous golden safety check** (`golden_eval.py:199-203`): "experts are read-only"
   filters agents by `k8s_security/cloud_security/incident_response/threat_modeling/
   network_engineering`, but only `network_engineering` exists after the merge — `all()`
   over one agent passes trivially and four dead names hide the regression the check was
   written to catch. Update the name list to the merged roster.
3. **Dead agents** — `ConfigAgent`, `TroubleshootingAgent`, `SecurityReviewAgent` defined
   but never registered (`agents.py:162,424,436` vs `DEFAULT_AGENTS:585-587`). Delete or
   register.
4. **Phantom provenance** — `agent_from_how` (`agents.py:285-305`) maps answers to agent
   names that don't exist ("tools", "data", "self_improvement", "feedback", "generation"),
   so traces/dashboard can attribute answers to agents that aren't running.
5. **Token usage discarded** — Ollama returns eval counts; `llm.py:145` keeps only the
   response text, so the §21 metrics "token usage/cost" can't be computed without a code
   change.

---

## 7. Priority fix list

**P0 — correctness/safety**
1. Remove `MathAgent` from `DEFAULT_AGENTS` (explicit prompt violation); math already
   lives in the core router's exact-tool branch.
2. Fix the `learn_folder` NameError (bug #1) and the golden-eval agent names (bug #2).
3. Close the poisoning chain: tag learned passages with source + timestamp + origin
   (web/teach/file/github), and stop labelling research-derived passages "authoritative"
   in `grounded_prompt` until a validation step (source agreement / trusted-domain check /
   human confirm) has marked them validated. This is prompt §5's central demand.

**P1 — prompt alignment**
4. Add a `Task`/`Message` dataclass (16 fields from §3) around `Master.handle`, even if
   the fields are mostly informational at first — it unlocks status/error/timeout tracking.
5. Add provenance & knowledge-class metadata to `Library` (upgrade docs from `str` to
   dicts or a parallel index); implement supersession and freshness expiry.
6. Research validation: require ≥2 agreeing sources or one trusted-domain source before a
   researched passage may ground a "verified" answer; prefer authoritative domains
   (extend `sources.py`).
7. Skill registry: add version/status/owner/test fields; run a proposal's trigger against
   a sample of stored episodes before install (cheap regression test); keep the data-only
   design (it's safer than executable skills) but document the deviation from §8 as a
   deliberate decision.
8. Write the five workflow examples (§19 A–E) into BLUEPRINT with the actual stage traces.
9. Extend `network_engineering` intent with `sd-?wan|nac|waf|ddos|forescout|zero trust`.

**P2 — architecture maturity**
10. Model router: classify query → pick model tag (fast vs reasoning) from Ollama's
    installed list; record token usage from Ollama's eval counts.
11. Research cache keyed by normalized query (TTL-bounded) — kills repeat fetches.
12. Formalize the three human-control levels (§22) and the acting-operation approval
    ladder before any WRITE-capable tool is ever added.
13. Replace provenance phantom names (bug #4) with real module names.
14. Run council contributions and `cover gaps` pages in parallel threads.
15. Consolidate "problems with the current architecture" (deliverable #2) and the
    architecture-comparison rationale (§2) into one doc.
