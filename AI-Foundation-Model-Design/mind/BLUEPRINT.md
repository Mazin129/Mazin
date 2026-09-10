# Vio — Complete System Blueprint

> A **local, private** AI assistant for networking & security. Runs entirely on your own
> PC (no cloud required), reachable anywhere over a private Tailscale network. It reasons
> with a local LLM, retrieves from a growing library, runs a team of expert agents,
> researches the web on demand, notices what it doesn't know and learns it, and can
> improve itself — all under a human approval gate.

This document is the full map — every subsystem, big and small, how they fit, every
command, endpoint, env var, and file.

---

## 1. Principles

- **Local-first / private.** The brain (LLM), memory, and knowledge all live on your
  machine. Nothing is sent to a cloud unless *you* turn on web research or point it at a
  hosted model.
- **Honest.** Answers carry provenance (which agent), a confidence %, and a "verified"
  flag. When it doesn't know or can't finish, it says so — it never dresses a raw config
  line up as a verified answer.
- **Governed.** Anything that reaches outside the box (network) or changes state (write)
  is gated by a Guardrail. Self-improvement stops at a human approval gate.
- **Grows with use.** Every question, correction, and document makes it better.

---

## 2. System map

```
                ┌────────────────────────── Browser / Phone (Tailscale) ───────────────────────────┐
                │   Chat GUI  ·  /dashboard (live control)  ·  login (token → session cookie)        │
                └───────────────────────────────────┬───────────────────────────────────────────────┘
                                                     │ HTTPS (Tailscale serve)
                                        ┌────────────▼─────────────┐
                                        │   web.py  (HTTP server)   │  auth · host-allowlist · API
                                        └────────────┬─────────────┘
                                                     │ reply()  (talk.py)
                                        ┌────────────▼─────────────┐
                                        │  Mind.ask()  (reasoner)   │
                                        │  kernel/executive.py      │  two-clock: confidence + critic
                                        └────────────┬─────────────┘
                                                     │ _route()
                                 ┌───────────────────▼────────────────────┐
                                 │        Master  (agents.py)              │  score → dispatch → validate
                                 │  Registry · Guardrail · council()       │  → guardrail
                                 └───────────────────┬────────────────────┘
        ┌──────────────┬───────────────┬────────────┼────────────┬───────────────┬──────────────┐
        ▼              ▼               ▼             ▼            ▼               ▼              ▼
   Expert agents   WebResearch     Core router   Knowledge    Skill/Math/    Config/Memory   Domain
   (k8s, cloud,    (search+learn)  (_core_front) (retrieval   Planner/World  /Reasoning      (trouble,
    network, IR,                                  + LLM)                                       sec-review)
    threat)
        └──────────────┴───────────────┴─────────────┬───────────┴───────────────┴──────────────┘
                                                      │ all share ↓
                        ┌─────────────────────────────▼──────────────────────────────┐
                        │             SHARED BRAIN  (the Mind)                          │
                        │  Library (TF-IDF + semantic)  ·  Memory facts  ·  Skills      │
                        │  Episodic  ·  Knowledge graph  ·  Curiosity/Gaps              │
                        └─────────────────────────────┬──────────────────────────────┘
                                                      │ generates with
                                        ┌─────────────▼──────────────┐
                                        │   llm.py  →  Ollama          │  qwen2.5:3b / 7b (switchable)
                                        └─────────────────────────────┘
```

The key idea: **agents don't message each other directly — they collaborate through the
shared Mind.** What any one learns (web page, taught fact, trusted source) lands in the
shared library and every other agent can use it on the next question.

---

## 3. How an answer is produced (request lifecycle)

1. **Browser → `POST /api/ask` `{message}`** (auth checked: token session cookie).
2. **`talk.py: reply()`** handles a few deterministic fast paths, else `Mind.ask()`.
3. **`Mind.ask()`** checks reflex/identity/calibration shortcuts, then calls
   **`kernel/executive.py`** — the *two-clock* executive: it decides System-1 (fast,
   verified reflex) vs System-2 (deliberate) and calls `Mind._route()`.
4. **`Mind._route()` → `Master.handle()`**: every agent scores the query (0–1); the
   highest-scoring agent runs; its result is validated, then passed through the
   **Guardrail** (network/write actions gated unless opted-in/confirmed).
5. If no agent claims it, the **CoreRouterAgent** runs `_core_front` (commands, tools,
   math, world-model, planner, aggregate) and the **KnowledgeAgent** runs
   `_knowledge_answer` (retrieval + grounded LLM + honest fallback).
6. The **Confidence engine + Critic** score the answer; **Curiosity** logs a gap on a
   miss or clears one on a confident hit; the **behaviour trace** is recorded.
7. Response returns with `answer`, `how` (provenance), `verified`, `confidence`, `agent`.

---

## 4. The agents (11)

Scores drive dispatch (highest wins); order only breaks ties. Advisory = read-only;
Acting = holds network/write permission and is guardrail-gated.

| Agent | Kind | Fires on |
|---|---|---|
| `research` (WebResearchAgent) | ⚙️ acting (network) | `research:` / `look up` / `search the web` — searches, reads, learns, cites |
| `diagram` (DiagramAgent) | 💬 read-only | `draw:` / `diagram:` / `sketch a …` — LLM follows the vendored diagram-design skill → deterministic self-contained SVG at `/diagram/<id>` (model only emits a node/edge spec; `VIO_DIAGRAM_ENGINE=skill` for full editorial SVG on a strong model) |
| `network_engineering` | 💬 expert (unified) | ALL network & security: routing/switching, firewalls, k8s/mesh (mTLS), cloud/IAM, incident response, threat modeling, troubleshooting, security review, and config analysis (exact structural counts). Merged from the former per-domain experts. |
| `skill` | 💬 reflex | user-taught `skill:` reflexes |
| `math` | 💬 | symbolic math (sympy) |
| `planner` | 💬 | "make a plan to…" |
| `world_model` | 💬 | "what happens if…" causal what-ifs |
| `reasoning` | 💬 | general reasoning |
| `memory` | 💬 | "what did we discuss", "what do you know about me" |
| `core` (CoreRouterAgent) | 💬 catch-all | the proven front router (`_core_front`) |
| `knowledge` (KnowledgeAgent) | 💬 tail | retrieval + grounded/open LLM + honest no-source |

The one `network_engineering` expert is **conceptual**: they strip raw device-config passages from their
grounding so a firewall stanza never pollutes a design answer, and without a local LLM
they self-skip (never regressing the base path).

**Guardrail** (`agents.py`): advisory results pass through; a network-only action passes
when `VIO_ALLOW_NET` is set (standing consent) or `confirmed`; **write always gates** with
a "reply confirm" prompt until approved.

**Council** (`council: <q>` / `team:` / `ask all agents`): the top-3 advisory agents each
contribute and the LLM merges them into one answer naming who weighed in — agents
collaborating on a single question. Acting agents are excluded unless confirmed.

---

## 5. The brain (LLM cortex)

- **`llm.py`** talks to a local **Ollama** server (`VIO_LLM_URL`, default
  `http://localhost:11434`).
- **Model** picked by `VIO_LLM_MODEL`, else auto-picked in preference order
  `qwen2.5 → llama3.1 → llama3.2 → qwen2 → mistral → gemma2 → phi3 → …`.
- **Two brains, switchable live** (hardware: a 2 GB GPU fits ~3B models):
  - `qwen2.5:3b` — fits the GPU, fast, strong on network/security. **Default.**
  - `qwen2.5:7b` — smarter, runs on CPU (~20–60 s/answer).
  - Switch instantly from **/dashboard → Brain dropdown** (or `POST /api/model`), no restart.
- **Timeouts:** detect within 2 s (`available`); generation ceiling `VIO_LLM_TIMEOUT`
  (default 300 s), answer length `VIO_LLM_MAX_TOKENS` (default 3072).
- **Honesty:** if the grounded call returns empty (a timeout on a too-big model), Vio
  returns an honest "model didn't finish — use a smaller/faster one" message instead of
  dumping a raw retrieved passage.

---

## 6. Knowledge & memory (the shared brain)

| Store | Module | What it holds |
|---|---|---|
| **Library** | `reasoner.py: Library` | passages; TF-IDF search (`+ semantic.py` re-rank if `sentence-transformers` installed) |
| **Memory facts** | `reasoner.py` | `remember:` / `teach:` facts about you & the world |
| **Skills** | `skills.py` | user-taught `skill:` reflexes (instant, verified) |
| **Episodic** | `reasoner.py` | past conversations (recall) |
| **Knowledge graph** | `reasoner.py: graph` | relational edges learned at teach-time |
| **Curiosity / Gaps** | `cognition/curiosity.py` | topics it couldn't answer (`gaps.json`) |

- **Config-aware chunking:** FortiGate/router configs are split by stanza (`config/edit/
  set … next/end`) so a config is never shredded into prose fragments; a
  `_is_configish_snippet` guard keeps raw config out of conceptual answers.
- **Aggregate queries:** "list/how many/which policies…" are answered over the whole
  config, not a single passage.

---

## 7. Learning systems

- **Teach directly:** `teach: <fact>`, `remember: <fact>`, drop a file (📄 PDF/TXT/MD via
  `pdftext.py`/`ingest.py`; diagrams via `diagrams.py`), a folder, or a GitHub repo
  (`gitlearn.py`, docs only — never runs repo code).
- **Web research** (`websearch.py` + `Mind.research`): `research: <topic>` searches
  (DuckDuckGo → Bing → DuckDuckGo-lite fallback), reads the top pages, **learns them into
  the library**, and answers grounded with citations. Off unless `VIO_ALLOW_NET=1`.
- **Trusted sources** (`sources.py`): a curated catalog (Istio, K8s hardening, AWS
  IAM/IMDS, OWASP, MITRE ATT&CK, NIST, CIS, RFC 4271, doc-heavy repos). `list sources`
  to view, `learn essentials` to ingest all.
- **Cover gaps** (`Mind.cover_gaps`): `cover gaps` auto-researches each open gap, learns
  it, and closes it — the curiosity engine + web research + shared library working
  together. Bounded per run (8 gaps × 2 pages); repeat for the rest.
- **Governed self-improvement** (`selfimprove.py`):
  - **TraceLog** — passively records every interaction + 👍/👎 (`traces.jsonl`).
  - **Curator** — turns clean traces into SFT training data (`curated_sft.jsonl`).
  - **Evaluator** — runs the capability benchmark in isolation as a promotion gate.
  - **ModelManager** — versioned promote/rollback of the live model (`model_state.json`).
  - **`propose()`** runs curate + evaluate and **stops at the human approval gate** — it
    never trains or promotes on its own.

---

## 7.5 Answer-quality guarantees (quality > more agents)

Quality is enforced centrally, so it holds no matter which agent answered:

- **Never verify weak/empty** — `quality.finalize()` runs on **every** response after the
  critic: an empty, too-short, or hedging answer can never wear a ✓; a factual/security
  claim with **no local evidence and no web source** is shown but tagged *"unverified (no
  local evidence)."*
- **Critic on every deliberate answer** — `cognition/critic.py` runs on all System-2
  paths (LLM, unverified, empty-evidence): it flags memory conflicts, re-searches thin
  support, downgrades a config-dump served for an analytic question, and — below the
  honesty threshold — **abstains and asks for clarification instead of bluffing.**
- **Citations** — a verified grounded answer carries a *Sources:* (web) or *Grounded on:*
  (passages) footer; evidence is published by the knowledge path, web research, and the
  expert agents.
- **Structured config** — `configparse.py` parses firewall/router config into objects
  before analysis; `how many …` is an **exact structural count** (no LLM → verified).
- **Read-only experts** — expert agents declare `permissions={read}` and `validate()`
  their own output (reject stubs/degenerate loops).
- **Golden gate** — `golden_eval.py` scores correctness + safety + latency over real use
  cases; `propose()` reports `promotable`, and a model/prompt/retrieval/training change is
  promoted only when the golden suite is green.
- **Full reasoning traces** — behaviour traces store the evidence and reasoning steps, so
  fine-tuning learns judgement, not shallow Q→A mimicry.

## 8. Inspection & collaboration (how to check it)

- `agents` / `list agents` → the roster (advisory vs acting) + shared-brain counts.
- `who answers: <q>` → ranked agent scores for a question (routing proof).
- `council: <q>` → several agents team up on one answer.
- `GET /api/agents` → roster + shared stats (used by the dashboard).

---

## 9. The dashboard (`/dashboard`, `dashboard_page.py`)

Live, interactive, refreshes every 3 s:
- **Agents — live blueprint**: every agent as a card + model & web-research pills + the
  shared-brain counts.
- **Learn & cover**: one-click `List gaps`, `Cover gaps`, `Learn essentials`, `Sources`,
  `Roster` (each POSTs to `/api/ask` and streams the result).
- **Brain & self-improvement**: switch the live model (dropdown of installed models);
  `Propose` / `Approve & promote` / `Rollback`.
- **Cognitive views**: "how Vio answered" flow, architecture map, calibration plot,
  confidence histogram, memory tiers, answer quality, System-1/2 split, domains, wishlist.

---

## 10. Security model

- **Token auth:** `VIO_TOKEN` → login page → HttpOnly, `SameSite=Strict` session cookie
  (`+Secure` when `VIO_HTTPS=1`); brute-force throttle. No token = localhost-only.
- **Bind guard:** binds `127.0.0.1` by default; **refuses** to bind elsewhere without a
  token (unless `VIO_ALLOW_INSECURE`).
- **Host-header allowlist:** `VIO_ALLOWED_HOSTS` (anti DNS-rebinding). A wrong host → 403.
- **Web-research SSRF guard:** a URL resolving to private/loopback/link-local/reserved is
  refused; http/https only; size/time caps; redirects re-validated; fetched text treated
  as **data, not instructions**. Scope with `VIO_NET_ALLOW` / `VIO_NET_BLOCK`.
- **Port-in-use guard:** loud message (with the kill command) instead of a silent second
  process serving stale code.

---

## 11. Remote access — Tailscale (recommended)

1. Install Tailscale on the PC + phone (same account); enable MagicDNS + HTTPS.
2. `tailscale serve --bg 8100` (proxies your `<name>.ts.net` → `127.0.0.1:8100`).
3. Start Vio with `VIO_TOKEN`, `VIO_ALLOWED_HOSTS=<name>.ts.net`, `VIO_HTTPS=1`.
4. Open `https://<name>.ts.net/` on any device on your tailnet and log in.

A private WireGuard mesh — never a public port. `start_vio_remote.bat` sets all of this
(and asks for a token once, saved to git-ignored `vio_token.txt`).

---

## 12. Chat command reference

| Command | Does |
|---|---|
| *(any question)* | routed to the best agent |
| `teach: <fact>` | store a fact |
| `remember: <fact>` | store a personal fact |
| `skill: name \| when: trigger \| reply: text` | define a reflex |
| `research: <topic \| URL>` | search/read the web, learn, answer with sources |
| `look up …` / `search the web for …` | same |
| `list sources` | show the trusted-source catalog |
| `learn essentials` | learn all trusted sources |
| `list gaps` / `gaps` | show open knowledge gaps |
| `cover gaps` | auto-research + learn each gap |
| `agents` / `list agents` | agent roster + shared brain |
| `who answers: <q>` | which agents would handle it |
| `council: <q>` / `team: <q>` / `ask all agents <q>` | agents collaborate |
| `learn from github owner/repo` | learn a repo's docs |
| `draw: <description>` / `diagram:` / `sketch a …` | generate an HTML/SVG diagram (diagram-design skill) |
| `what do you want to learn` | curiosity wishlist |
| `what's in your library` | library summary |

---

## 13. HTTP API reference

**GET:** `/` (chat) · `/dashboard` · `/api/status` · `/api/telemetry` · `/api/agents` ·
`/api/models` · `/api/memory` · `/api/skills` · `/api/improve` · `/api/pack` ·
`/api/solve` · `/api/models` · `/diagram/<id>` · `/api/train_all/status`

**POST:** `/api/login` (open) · `/api/ask` `{message}` · `/api/feedback` `{good}` ·
`/api/learn` · `/api/learn_folder` · `/api/model` `{model}` · `/api/improve/propose` ·
`/api/improve/promote` `{model,approved}` · `/api/improve/rollback` · `/api/train` ·
`/api/train_all` · `/api/train_all/stop` · `/api/skills` · `/api/pack/import` ·
`/api/forget`

All routes except `/` and `/api/login` require a valid session (token login first).

---

## 14. Environment variables

| Var | Default | Meaning |
|---|---|---|
| `VIO_TOKEN` | — | access code; set = login required, unset = localhost-only |
| `MIND_HOST` | `127.0.0.1` | bind address (refuses non-local without a token) |
| `MIND_PORT` | `8100` | port |
| `VIO_ALLOWED_HOSTS` | — | comma-separated allowed `Host` headers (your tailnet name) |
| `VIO_HTTPS` | — | mark cookie `Secure` (TLS terminates in front) |
| `VIO_LLM_URL` | `http://localhost:11434` | Ollama endpoint |
| `VIO_LLM_MODEL` | *(auto)* | force a model tag |
| `VIO_LLM_TIMEOUT` | `300` | generation timeout (s) |
| `VIO_LLM_MAX_TOKENS` | `3072` | max answer length |
| `VIO_ALLOW_NET` | off | enable web research |
| `VIO_NET_ALLOW` / `VIO_NET_BLOCK` | — | restrict fetchable domains |
| `VIO_DATA_DIR` | *(mind/)* | where the brain-on-disk lives |
| `VIO_NO_BROWSER` | — | don't auto-open a browser (service mode) |
| `VIO_NO_SLEEP` | — | disable idle consolidation |
| `VIO_ALLOW_INSECURE` | — | override the non-local bind guard (not recommended) |

---

## 15. The brain on disk (data files, in `VIO_DATA_DIR`)

`knowledge.json` (library) · `mind_memory.json` (facts) · `skills.json` · `episodic.json`
· `graph.json` · `gaps.json` · `traces.jsonl` (behaviour) · `curated_sft.jsonl` ·
`model_state.json` (promotions) · `vio_token.txt` (git-ignored secret). **These are your
brain — back them up.** All git-ignored (per-machine).

---

## 16. Module map

- **Serving:** `web.py` (server/API/auth), `dashboard_page.py`, `talk.py` (front replies).
- **Cognition core:** `reasoner.py` (the Mind), `kernel/executive.py` (two-clock),
  `kernel/workspace.py`.
- **Agents:** `agents.py`.
- **Brain:** `llm.py`, `make_modelfile.py`.
- **Cognition modules:** `cognition/` — `confidence`, `critic`, `calibration`,
  `curiosity`, `consolidation`, `learning`, `planning`, `reasoning`, `world_model`.
- **Knowledge/IO:** `semantic.py`, `think.py`, `ingest.py`, `pdftext.py`, `pdfcheck.py`,
  `diagrams.py`, `datatable.py`, `gitlearn.py`, `packs.py`, `seed_knowledge.py`,
  `teach_datasets.py`.
- **Web research:** `websearch.py`, `sources.py`.
- **Diagrams:** `diagramdet.py` (deterministic SVG — default, never blank), `diagramgen.py` + `vendor/diagram-design/` (skill engine, Cathryn Lavery MIT — `VIO_DIAGRAM_ENGINE=skill`).
- **Answer quality:** `quality.py` (verification gate + citations), `configparse.py`
  (structured config), `golden_eval.py` (correctness/safety/latency gate).
- **Self-improvement:** `selfimprove.py`.
- **Training (external/offline):** `train_all.py`, `train_model.py`, `build_dataset.py`,
  `build_large_sft.py`, `data_ingest.py`, `neural_model.py`.
- **Tests:** `capability_test.py` (26 checks), `golden_eval.py` (quality gate),
  `test_agents.py`, `test_selfimprove.py`, `test_websearch.py`, `test_configparse.py`.

---

## 17. Setup & run (Windows)

```bat
:: one-time
ollama pull qwen2.5:3b
ollama pull qwen2.5:7b          :: optional, smarter, CPU

:: every start — double-click start_vio_remote.bat, or:
cd C:\Users\mazin\Mazin\AI-Foundation-Model-Design\mind
set VIO_TOKEN=your-long-code
set VIO_ALLOWED_HOSTS=<name>.ts.net
set VIO_HTTPS=1
set VIO_LLM_MODEL=qwen2.5:3b
set VIO_ALLOW_NET=1
python web.py
```

Banner confirms `🧠 model:` and `🌐 web research:`. Then open `http://localhost:8100`
(PC) or `https://<name>.ts.net/` (phone).

---

## 18. Deployment options (see `deploy/`, `SECURITY.md`)

| Path | Speed | Cost/mo | Notes |
|---|---|---|---|
| **Tailscale → home PC** | your GPU | $0 | private, recommended for personal use |
| CPU VPS all-in-one | slow | ~$6–12 | Docker: Caddy(TLS)→Vio→Ollama |
| GPU VPS | fast | ~$150–500 | uncomment GPU block in `docker-compose.yml` |
| Small VPS + hosted LLM API | fast | ~$5 + usage | set `VIO_LLM_URL` off-box |

`deploy/` has `Dockerfile`, `docker-compose.yml`, `Caddyfile`, `vio.service`, `DEPLOY.md`.

---

## 19. Limits & roadmap

- **Hardware ceiling:** a 2 GB GPU caps local models at ~3B (fast) or 7B (CPU, slow).
  Senior-architect, multi-hop questions want a 14B–32B model → bigger GPU or a hosted
  endpoint pointed at the same switcher.
- **Retrieval:** install `sentence-transformers` to turn on semantic re-rank (sharper
  retrieval than lexical-only).
- **Self-improvement:** the fine-tune/train step is external (GPU-heavy); `propose` tells
  you when there's enough curated data. Promotion is always human-gated.
- **Next ideas:** a "🌐 Research" and "📊 Dashboard" link in the chat header; scheduled
  idle `cover gaps`; per-domain source packs.

---

*Vio is a local reasoning assistant. Keep the token secret, back up the data files, and
enable web access only on a machine you trust.*
