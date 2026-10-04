# 9. Skills & Tools Roadmap — Making Vio Real-World Powerful

**Status:** recommendation (2026-10-04) · **Grounded in:** the shipped `mind/` architecture
(coordinator, evidence-class planning, provenance layer, guardrail, Task schema) and what
production agent systems actually run on (MCP ecosystems, Claude/Cursor/OpenAI tool
stacks, netops tooling, modern RAG).

**Method:** every recommendation names the exact technology, the existing Vio file it
hooks into, the effort (S < 1 day · M ≈ 1–3 days · L = multi-day), and the guardrail it
requires. No tool is recommended "because it exists" — each closes a gap Vio demonstrably
has today.

---

## 0. Executive summary — the ten highest-leverage moves

| # | Move | Why it's the real-world standard | Effort |
|---|---|---|---|
| 1 | **Native tool-calling for the LLM path** (Ollama function calling) | Every production agent lets the model call tools by name; Vio's regex intents are the single biggest capability ceiling | M |
| 2 | **MCP compatibility** (expose Vio tools as an MCP server; consume MCP servers) | MCP is the industry protocol for tools (Claude, Cursor, Zed…). One adapter plugs Vio into hundreds of existing servers | M |
| 3 | **Sandboxed Python tool** (execution + analysis) | The #1 tool of every real assistant (code interpreter). Unlocks pandas, scapy, netmiko — everything below | M |
| 4 | **Live device interaction** (netmiko/ncclient REST) | "Real world" for a network assistant = talking to actual FortiGate/Cisco boxes, read-only first | M |
| 5 | **SQL/DuckDB over the data engine** | Real systems answer data questions with SQL, not hand-rolled filters | S |
| 6 | **Hybrid retrieval upgrade** (BM25/FTS5 + existing TF-IDF + embeddings + reranker) | Modern RAG default; fixes recall on the 77k library | M |
| 7 | **Local embedding + reranker models** (bge-small / all-MiniLM + bge-reranker via Ollama or sentence-transformers) | Production RAG always reranks; Vio's optional re-rank becomes first-class | S |
| 8 | **Real search APIs** (Tavily/Brave/Serper behind the existing websearch interface) | Keyless HTML scraping breaks constantly; production agents use search APIs | S |
| 9 | **Scheduled autonomy** (nightly `cover gaps`, digest) | Real assistants act proactively; Vio's curiosity engine already wants this | S |
| 10 | **Eval harness as a tool** (DeepEval/Ragas-style graded runs) | Production teams don't guess quality — they measure it per change | M |

---

## 1. Tool architecture — what to add, exactly

Vio's tools today: web search/fetch, file readers (30+ formats), git-doc learning, sympy
math, subnetting, data tables, diagrams, config parse/audit/diff, device facts, doc
study. All are reachable only through hand-written intent regexes, and none can *act*.

### 1.1 Execution layer (unlocks everything else)

**T1. Sandboxed Python tool — `tools/python_sandbox.py` · effort M · guardrail: EXECUTE class**
- Real-world standard: every serious assistant runs code (ChatGPT code interpreter,
  Claude analysis tool). This is the single highest-leverage tool Vio can add.
- How: a persistent Python subprocess (restricted: `resource` limits, no network by
  default, tmpfs workspace, output captured) invoked through a `python` tool with the
  prompt's own generated snippet; **human approval or AUTONOMY=autonomous required**
  (the Guardrail already has the gate — add the EXECUTE permission class to
  `agents.py`'s READ/WRITE/NETWORK set, which the redesign prompt explicitly asks for).
- Unlocks: pandas analysis of the uploaded CSVs, scapy packet parsing, Jinja config
  templating, bulk config transforms, matplotlib charts in chat.
- Hooks: `_core_front` exact-tool chain (score by "run/compute this python" intent) and
  as a callable for the LLM path once T2 lands.

**T2. Native tool-calling for the reasoning path — `cognition/toolcall.py` · effort M**
- Real-world standard: models are *given* tool schemas and decide when to call them
  (function calling). Ollama supports it natively for qwen3.5-family models — Vio's
  current brain.
- How: expose the deterministic tools (subnet, config parse, table query, web search,
  device facts, sandbox) as JSON schemas; when the Executive takes the System-2 LLM
  path, pass the schemas and let the model request calls; results feed back before the
  final answer. Keep the existing deterministic-first routing as the fast path — this
  upgrades the *reasoning* path, not the reflex path.
- Why it matters: the ~130-regex → `brain.py` evolution proved hand-written intents
  don't generalize. Tool schemas are the industry's answer.

**T3. MCP adapter — `tools/mcp_server.py` + `tools/mcp_client.py` · effort M**
- Real-world standard: Model Context Protocol is how Claude/Cursor/Zed expose and
  consume tools. An MCP server for Vio (expose: `ask`, `research`, `config_audit`,
  `subnet`, `teach`) makes Vio usable from real editors; an MCP client lets Vio import
  the ecosystem (filesystem, git, SQL, browser servers) with zero new code per tool.
- Guardrail: imported MCP tools register through the same permission registry;
  network/exec tools arrive gated.

### 1.2 Network & security domain tools (the moat)

**T4. Live device interaction — `tools/netdev.py` · effort M · guardrail: READ first, WRITE gated**
- Libraries: **netmiko** (SSH, multi-vendor incl. FortiGate/Cisco/Arista), **ncclient**
  (NETCONF), and FortiGate **REST API** (requests; token auth). scapy for packet craft
  (labs only).
- Read-only commands first (`show version`, `get system status`, interface/policy
  dumps) — feeding `devicefacts.py` and `configparse.py` with *live* data. This is the
  single biggest "real world" gap: today Vio only knows configurations it was taught.
- Credential storage: OS keyring or git-ignored file (pattern exists: `vio_token.txt`).
- `VIO_ALLOW_DEVICES=1` opt-in, per-host allowlist, every command logged in the Task
  record. Write commands (`configure`) only under ASSISTED with per-command confirm —
  the Guardrail's WRITE gate, finally with something real to gate.

**T5. Packet & log analysis — `tools/netanalysis.py` · effort M**
- Libraries: **dpkt/scapy** (pcap parsing → conversations, retransmits, DNS/TLS
  breakdowns), **tshark** headless if installed. Feeds the troubleshooting agent with
  real evidence instead of textbook patterns.
- Log analysis: the existing `datatable` engine + T5 sandbox covers most; add grok-style
  parsers for FortiGate logs (`type=traffic` fields) as a dataset pack.

**T6. Compliance & hardening packs — extend `configaudit.py` · effort S**
- What production uses: CIS FortiGate benchmark mappings, NSA guides. Vio's auditor
  already has the hardening checks — add rule→benchmark-ID mapping and a `compliance
  report` mode (exportable markdown). Effort small because the engine exists.

### 1.3 Data & retrieval (quality multiplier on the 77k library)

**T7. SQL/DuckDB data engine — extend `datatable.py` · effort S**
- Library: **DuckDB** (pip, embedded, SQL over CSV/DataFrames — the 2024+ standard for
  local analytics). Keep the natural-language front; compile safe SELECTs, keep the
  computed-and-verified contract (answers stay "exact tool" class).
- Why: group-by/join/window questions the row-filter engine can't express.

**T8. Hybrid retrieval + reranker — `semantic.py` · effort M**
- Real-world RAG default: BM25 (lexical) + dense embeddings + cross-encoder rerank.
  Vio has TF-IDF (+optional embeddings). Add **rank_bm25 or SQLite FTS5** as a second
  lexical channel and a **bge-reranker-base** (sentence-transformers, CPU-ok) rerank of
  the top-20 → top-5. Evaluate with T10 before/after on a fixed question set.
- Parent-document retrieval: keep the passage-level index but feed the LLM the *parent
  chunk* (the section) — reduces the fragments class of failures further.

**T9. Search & fetch upgrade — extend `websearch.py` · effort S**
- Real-world standard: search APIs, not HTML scraping. Add **Tavily** (agent-oriented,
  free tier) or **Brave Search API** (free tier) behind the existing `search()` fallback
  chain (DuckDuckGo → Bing → API keys from env). Jina Reader (`r.jina.ai`) as a
  JS-heavy-page fetcher. Keep the SSRF guard and domain allowlists unchanged.

**T10. Eval harness — `evals/` · effort M**
- Real-world standard: production teams gate every change on evals (DeepEval, Ragas,
  promptfoo). Vio already has golden_eval (invariants) — add a *quality* eval set:
  ~50 real questions with graded rubrics (correctness, groundedness, conciseness) run
  per model/prompt/retrieval change, reported in the dashboard. The SFT set (82/200)
  and your 👍/👎 history seed it.

### 1.4 Memory & proactivity

**T11. Entity/semantic memory upgrade — `memory/graph.py` · effort M**
- Today's graph is regex-extracted at teach time. Upgrade path: LLM-assisted extraction
  (batch, off hot-path) + **networkx** for multi-hop queries; store in SQLite (one file,
  no server — the JSON stores are at their limit). Feed relational questions and the
  coordinator's brief.

**T12. Scheduled autonomy — `scheduler.py` · effort S · guardrail: time-boxed, Web-gated**
- Real assistants are proactive. A stdlib cron thread (VIO_NO_SLEEP already gates idle
  work): nightly `cover gaps` (bounded 8×2 as today), weekly library dedupe/consolidate,
  optional morning digest. Each run is a Task with the standard guardrail; nothing new
  is trusted automatically.

### 1.5 What NOT to build yet (prompt §30 discipline)

- **Voice/speech** — no user need expressed; heavy models for this hardware.
- **Browser automation (Playwright)** — only when a real vendor-doc target needs login;
  the reader + search APIs cover 95%.
- **Multi-agent frameworks (LangGraph/AutoGen)** — the coordinator already implements
  the pattern; adopting a framework adds dependency weight without a demonstrated gap.
- **Fine-tuning infrastructure** — the 82→200 SFT examples and the external Colab path
  stay external until the data justifies it.
- **Cloud LLMs by default** — hybrid via `VIO_LLM_URL` exists; keep local-first.

---

## 2. Skill recommendations — packs, not single tricks

Vio's skills today are chat reflexes + proposals + the selflearn registry. The
real-world pattern to grow into: **skills = parameterized, validated procedures**
(Voyager-style skill libraries, Claude Agent Skills). Recommended packs, in order:

| Pack | Contents (each a validated skill) | Builds on | Effort |
|---|---|---|---|
| **Network troubleshooting runbooks** | "HA out-of-sync", "BGP flapping", "asymmetric routing", "IPsec phase2 down" — each: ranked causes → exact checks (T4 live where allowed) → fix → verification | configparse + configaudit + T4 | M |
| **Subnetting & IP toolkit** (started: `try_subnet`) | supernetting, VLSM tables, wildcard drills, IPv6 (EUI-64, compressed notation) — pure arithmetic skills, instant + verified | existing try_subnet | S |
| **Config migration** | FortiGate→Palo Alto / FortiOS upgrade diffs (configdiff.py exists) as guided, report-generating skills | configdiff | M |
| **Compliance** | CIS/NSA checks per platform → scored report (T6) | configaudit | S |
| **Incident response playbooks** | phishing, ransomware, lateral movement: STRIDE-mapped checklists with evidence-collection commands (read-only) | expert prompts | M |
| **Study/exam coach** | NSE4/NSE7-style drill mode: generate questions from the library, grade answers, track weak domains (docstudy.py exists) | docstudy + datasets | S |
| **Report writer** | "weekly network report": config posture + audit findings + gaps → markdown file (file-write under WRITE gate) | configaudit + Task | S |

**Skill engineering requirements** (to grow from reflex → procedure, prompt §8):
parameterized inputs, a validation step per run (the pre-install test exists — add
post-run self-check), composition (a skill may invoke tools/other skills through the
coordinator), and registry fields Vio already has (version/status/tests).

---

## 3. Phased plan

**Phase A — capability unlock (start here, ~1–2 weeks part-time)**
T7 DuckDB (S) → T9 search APIs (S) → T8 reranker (M) → T12 scheduler (S).
*Effect:* better answers on the existing library immediately; Vio becomes proactive.

**Phase B — real-world reach (~2–4 weeks)**
T1 sandbox (M, EXECUTE class + guardrail) → T2 native tool-calling (M) → T4 live
devices read-only (M, DEVICE class + allowlist).
*Effect:* Vio talks to real infrastructure and reasons with general tools — the two
things that define "real-world agent".

**Phase C — ecosystem & scale (ongoing)**
T3 MCP server/client (M) → T10 eval harness + dashboard integration (M) → T11 memory
upgrade (M) → skill packs per demand (T4-dependent ones first).

**Phase D — scale hardware** (when justified): GPU upgrade → 14B–32B reasoning brain +
own-model fine-tune on the 200+ SFT set; nothing architectural changes (the switcher,
Task schema, and router already abstract the model).

---

## 4. Guardrails every new tool must pass (non-negotiable)

1. Register in the permission registry with the correct class (READ/ANALYZE/WRITE/
   **EXECUTE**/DESTRUCTIVE — the prompt's five; add EXECUTE/DESTRUCTIVE tokens now).
2. Flow through the Guardrail: advisory passes, acting gates on autonomy level, writes
   always confirm; every call is a Task with audit fields.
3. Networked tools honor `VIO_NET_ALLOW/BLOCK` and the SSRF guard; device tools get a
   per-host allowlist + keyring credentials.
4. Sandboxed execution: no network, resource-limited, temp workspace, output captured.
5. Provenance: anything a tool learns enters the library through `add_many` with its
   origin; unvalidated stays unvalidated.
6. Bounded: timeouts + retry caps in the Task schema (already carried; enforce per-tool).
