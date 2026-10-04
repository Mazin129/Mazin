# 10. Senior Production-Readiness Review — Vio

**Reviewer stance:** staff engineer, first serious audit for real-world use.
**Date:** 2026-10-04 · **Codebase:** 26,353 LOC Python (excl. vendor), 22 test files.
**Method:** load-tested the live server (77,566-passage brain), read the persistence and
concurrency paths, measured before judging. Every blocker below has a number attached.

---

## 0. Verdict

**B+ as a single-user local assistant — genuinely production-worthy for its designed
audience (one user, one machine, honesty-first). C− as a multi-user service — and it
does not pretend otherwise.**

What a senior reviewer notices in the first hour and rarely sees in hobby systems:
deterministic-before-LLM routing, a verification gate on every answer, provenance on
every fact, governed self-modification with a real evaluation gate, and a test suite
that pins behavior invariants (37/37 golden + 26/26 capability, all green today).
What the same reviewer flags by the second hour is below — found by measurement, not
opinion, and the cheap ones are fixed in this same commit.

---

## 1. Blockers (measured today; two already fixed)

### B1 — `/api/status` cost O(model size), polled every 4s — **FIXED**
Measured: **2,285–2,909 ms per call**. `Thinker.stats()` walked every context of the
n-gram model (built from 2.85M tokens) to count vocabulary. The dashboard polls it
every 4 seconds → a background CPU burn of ~60% of one core, and — because of the GIL —
a trivial `solve x²−5x+6=0` measured **52.3 s** while 30 status reads ran in parallel.
Fix shipped: stats computed **once per train** and cached (the model is rebuilt on
train, so one invalidation point). Expected after restart: sub-millisecond status,
no more starvation. *Lesson the codebase already knew and applied elsewhere: teach-time
work, never query-time work (same rule as the knowledge graph).*

### B2 — `traces.jsonl` unbounded + full-file parses — **FIXED (rotation)**
145 KB today, but every interaction appends forever and `read()`/`stats()`/
`agent_stats()` parse the entire file per call — a slow leak that also slows the
curator over months. Fix shipped: rotation at 5 MB (`traces.jsonl.1`, one generation).
Still-open (filed, not fixed): `episodic.json` is capped (20k) but as a single JSON
rewrite per record; see B3's pattern.

### B3 — Brain persistence is not crash-atomic — **FIXED (core files)**
`knowledge.json` (9.2 MB) is a full-file rewrite on every teach/learn, followed by a
synchronous TF-IDF refit. A crash or power loss mid-write could destroy the whole
library. Fix shipped: write-to-temp + `os.replace` (atomic same-volume) for
`knowledge.json`, `knowledge_meta.json`, `mind_memory.json`. Open items: episodic and
graph stores still plain writes; the TF-IDF refit remains synchronous (acceptable at
current size — ~1–2 s — but the right fix is the documented SQLite/SQLite-FTS migration
in the debt register).

### B4 — Golden gate failing under load — **ROOT-CAUSED & FIXED**
The "orchestrator promotes" case in `test_selfimprove` intermittently failed. Root
cause, found by running the gate's child exactly as the gate does: the isolated golden
child **inherited the parent's live Ollama URL**, so the suite that is deterministic
and LLM-free by design was calling the real 4B model — minutes per case — until the
600 s child timeout returned fail-closed (`promotable: false`, empty cases). Fixes
shipped: the child's env pins `VIO_LLM_URL` to a dead port (restoring the suite's own
contract) and carries a 30 s latency budget (its synchronous semantic-model load
measured 9.4 s under CPU contention — setup, not regression). The gate failing closed
was the safe direction; now it also fails *accurately*. test_selfimprove: ALL PASS
under real conditions (live Ollama + training running).

---

## 2. High-priority findings (filed)

| # | Finding | Evidence | Recommendation |
|---|---|---|---|
| H1 | **197 broad `except Exception` sites** — the swallow-and-continue pattern is intentional (a chat assistant must degrade, not 500), but failures are invisible | grep count; partially mitigated by `_brain_error` surfacing | Central failure counter → `/api/telemetry` (`degraded_paths` per module); log at debug |
| H2 | **Server RSS 1.8 GB** (TF-IDF matrix + semantic model + n-gram thinker + 77k library) alongside a 322 MB trainer | measured | Honest single-user ceiling; the SQLite + quantized-vector migration (debt register #4) is also the memory fix |
| H3 | **No CI** — 22 test files exist but run only when someone remembers | repo | GitHub Actions on push: the deterministic suite (golden + capability + test_fixes) needs no LLM and <2 min. This repo is one YAML away from regression safety |
| H4 | **No rate limiting on `/api/ask`** — auth exists (token, SameSite=Strict, bind-guard, SSRF guard — all solid), but a locked browser tab can queue unbounded slow LLM generations | design | Cap concurrent generations; 429 with retry-after |
| H5 | **Tail latency p95 1.3 s / max 2.2 s** on deterministic answers (n=20, p50 83 ms) — the refit-on-write pattern: any teach in the recent past triggers synchronous refits on the next asks | measured | Debounce refits (dirty-flag + refresh on next read), or accept and document |
| H6 | **Ollama dependency for reasoning** — degradation is graceful and *loud* (cortex field says exactly why), but there is no watchdog if Ollama dies mid-session | design | Re-detect on N consecutive failures (the `available` flag is only set at startup/switch) |

## 3. What a senior reviewer would call out as *better than industry norm*

1. **Honesty engineering.** `no-source` as a first-class contract, evidence-class
   planning that refuses impossible questions *before* searching, the fragment gate,
   unvalidated-leads that can never wear a ✓ — measured working (golden 37/37 pins it).
2. **Governed self-modification.** Sandbox eval → golden gate → human approval →
   versioned rollback, with the gate actually re-checked on promote. Most "self-improving
   agent" demos have none of this.
3. **Provenance as a first-class layer** — origin/source/ts/validated per passage, the
   trust-tagged grounding prompt, and a `data report` that makes the brain auditable.
4. **Provenance-joined user feedback** — 👍/👎 attach to agent IDs (`agent_stats`), so
   agent trust is measurable, not vibes.
5. **Deterministic-first routing** — subnetting in 83 ms p50 through a tool instead of
   minutes through a 4B model; the architecture states the rule and the code enforces it
   (three separate hijack paths were found and closed today — each now has a regression
   test).

## 4. Scale & scope honesty

Single process, single user, single machine — by design and stated everywhere. The
ThreadingHTTPServer + shared-Mind model is fine for one human; the GIL makes "a few
tabs" the real limit, and today's hammer test (30 parallel reads + live ask, **zero
errors**) says even that is safe once B1's fix lands. Multi-user would require: the
SQLite migration, process-level isolation of generation, auth hardening, and queuing —
i.e., a different project phase, not a patch.

## 5. Fix-now list (already shipped in this commit)

- ✅ B1 stats cache (measured 2.3–2.9 s → expected <5 ms per poll after restart)
- ✅ B2 trace rotation at 5 MB
- ✅ B3 atomic writes for knowledge/meta/memory (temp + `os.replace`)
- Filed, not fixed: B4 flake, H1–H6 (each with a concrete recommendation above)

## 6. Re-measure after deploy (do this, don't trust the fix)

```
for i in 1 2 3; do curl -s -o /dev/null -w "%{time_total}\n" http://127.0.0.1:8100/api/status; done
```
Expect three numbers under 50 ms where this morning they were 2,285–2,909 ms.
