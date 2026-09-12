"""
doctor — one command that answers "why didn't Vio's model answer my question?"

Vio has two very different ways to produce text:

  1. the REASONING CORTEX  — a local model served by Ollama. Real language.
  2. DETERMINISTIC PATHS   — retrieval, structured config parsing, skills, commands.
                             No model involved at all.

When a deterministic path fires, the model never runs — and until now that looked
exactly like "the model gave a bad answer". It isn't the same thing, and the fix is
completely different. This tool separates them, end to end:

    stage 1  is an Ollama server reachable?
    stage 2  which models are installed, and which will Vio pick?
    stage 3  does a real generation actually complete, and how fast?
    stage 4  what is in the library — documentation, or a parsed device config?
    stage 5  route a set of real questions and report, for each one, whether the
             cortex RAN, was SKIPPED (and by which path), or FAILED.

Run:
    python doctor.py                # full check
    python doctor.py "your question"   # trace one specific question
"""
from __future__ import annotations

import os
import sys
import time

BAR = "=" * 74


def _h(t):
    print("\n" + BAR)
    print(f"  {t}")
    print(BAR)


def _line(ok, text, detail=""):
    mark = {True: "✅", False: "❌", None: "⚠️ "}[ok]
    print(f"  {mark} {text}")
    if detail:
        for d in str(detail).splitlines():
            print(f"       {d}")


# --------------------------------------------------------------------------- #
PROBES = [
    "what is a VLAN?",
    "explain the difference between TCP and UDP",
    "why would BGP sessions flap?",
    "show static route on SA-OCC firewall",
    "how many firewall policies are configured?",
]


def stage_server():
    _h("STAGE 1 — is a local model server running?")
    from llm import LLM
    t0 = time.time()
    llm = LLM()
    dt = time.time() - t0
    print(f"  server url : {llm.url}")
    print(f"  probe took : {dt:.2f}s")
    if not llm.available:
        _line(False, "No usable local model.", llm.reason)
        print("\n  Nothing below can work until this is green. Fix it with:")
        print("      ollama serve                 (in its own window, leave it open)")
        print("      ollama pull qwen2.5:3b")
        return llm
    _line(True, f"Ollama is up and Vio will use: {llm.model}")
    if llm.note:
        _line(None, "But note:", llm.note)
    return llm


def stage_models(llm):
    _h("STAGE 2 — installed models")
    if not llm.available:
        _line(None, "skipped (no server)")
        return
    names = llm.list_models()
    if not names:
        _line(False, "Ollama reports zero installed models.",
              "ollama pull qwen2.5:3b")
        return
    for n in names:
        _line(True, n + ("     ← Vio is using this one" if n == llm.model else ""))
    want = os.environ.get("VIO_LLM_MODEL", "")
    if want:
        hit = any(n == want or n.startswith(want + ":") for n in names)
        _line(hit, f"VIO_LLM_MODEL={want}",
              "" if hit else "that name is NOT in the list above — Vio silently used "
                             "a different model. Fix the name or pull it.")


def stage_generate(llm):
    _h("STAGE 3 — does the model actually generate?")
    if not llm.available:
        _line(None, "skipped (no server)")
        return False
    print("  asking it: 'In one sentence, what is a VLAN?'")
    print(f"  timeout   : {llm.gen_timeout}s   (VIO_LLM_TIMEOUT)")
    t0 = time.time()
    out = llm.generate("In one sentence, what is a VLAN?", temperature=0.2, max_tokens=120)
    dt = time.time() - t0
    if not out:
        _line(False, f"The model produced nothing after {dt:.0f}s.", llm.last_error)
        print("\n  This is the real problem — Vio then falls back to keyword retrieval,")
        print("  which is what produces the fragment answers you have been seeing.")
        return False
    _line(True, f"generated {len(out.split())} words in {dt:.1f}s")
    print(f"       “{' '.join(out.split())[:160]}”")
    if dt > 45:
        _line(None, f"That is slow ({dt:.0f}s).",
              "Long answers may hit the timeout and fall back to retrieval. "
              "Try a smaller model, or raise VIO_LLM_TIMEOUT.")
    return True


def stage_library(mind):
    _h("STAGE 4 — what knowledge does Vio actually have?")
    docs = mind.lib.docs
    _line(bool(docs), f"{len(docs)} passage(s) in the library")
    try:
        import configparse
        objs = configparse.parse_many(docs)
    except Exception as ex:
        objs, _ = [], ex
    if objs:
        kinds = {}
        for o in objs:
            kinds[o.kind] = kinds.get(o.kind, 0) + 1
        _line(True, f"{len(objs)} structured config object(s) parsed")
        for k, n in sorted(kinds.items(), key=lambda kv: -kv[1])[:10]:
            print(f"       {n:>4} × {k}")
    else:
        _line(False, "ZERO device-config objects parsed.",
              "Your library is documentation/prose, not a config export.\n"
              "Questions like 'show static route on <device>' have nothing to list.\n"
              "Upload the output of  show full-configuration  (or the .conf backup).")
    return objs


def stage_route(mind, questions):
    _h("STAGE 5 — for each question: did the model run, or not?")
    print("  This is the heart of it. 'skipped' means a deterministic path answered")
    print("  and the model was never consulted.\n")
    rows = []
    for q in questions:
        t0 = time.time()
        try:
            r = mind.ask(q)
        except Exception as ex:
            print(f"  ❌ {q}\n       crashed: {type(ex).__name__}: {ex}")
            rows.append("crash")
            continue
        dt = time.time() - t0
        cortex = r.get("cortex", "?")
        mark = {"skipped": "⚠️ ", "unavailable": "❌", "failed": "❌"}.get(cortex, "✅")
        rows.append(cortex)
        ans = " ".join((r.get("answer") or "").split())
        print(f"  {mark} {q}")
        print(f"       path   : {r.get('how', '?')}   ({dt:.1f}s)"
              f"   {'✓ verified' if r.get('verified') else '… unverified'}")
        print(f"       cortex : {cortex}")
        print(f"       answer : {ans[:150]}{'…' if len(ans) > 150 else ''}")
        print()
    return rows


def verdict(rows, generated):
    _h("VERDICT")
    ran = sum(1 for r in rows if r not in ("skipped", "unavailable", "failed", "crash"))
    skipped = rows.count("skipped")
    failed = rows.count("failed") + rows.count("unavailable")
    print(f"  model ran      : {ran}/{len(rows)}")
    print(f"  model skipped  : {skipped}/{len(rows)}   (deterministic path answered)")
    print(f"  model failed   : {failed}/{len(rows)}")
    print()
    if failed:
        print("  ➜ The model is not producing answers. That is a SETUP problem, not a")
        print("    knowledge problem — fix stage 1/3 above before judging answer quality.")
    elif not generated:
        print("  ➜ The model server is unusable. Start Ollama and pull a model.")
    elif skipped > ran:
        print("  ➜ Most questions never reached the model: a deterministic path claimed")
        print("    them. If those answers were good, that is correct and fast. If they")
        print("    were fragments, tell me which question and which 'path' it printed —")
        print("    that names the exact gate to fix.")
    else:
        print("  ➜ The reasoning model is running on most questions. Remaining bad")
        print("    answers are a knowledge/retrieval problem — check stage 4.")
    print(BAR)


def main(argv):
    here = os.path.dirname(os.path.abspath(__file__))
    if here not in sys.path:
        sys.path.insert(0, here)

    print(BAR)
    print("  VIO DOCTOR — is the mind thinking, or just matching keywords?")
    print(BAR)

    llm = stage_server()
    stage_models(llm)
    generated = stage_generate(llm)

    from reasoner import Mind
    print("\n  loading the Mind…")
    t0 = time.time()
    mind = Mind()
    print(f"  ready in {time.time()-t0:.1f}s")

    stage_library(mind)
    qs = [argv[1]] if len(argv) > 1 else PROBES
    rows = stage_route(mind, qs)
    verdict(rows, generated)
    return 0


if __name__ == "__main__":
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    sys.exit(main(sys.argv))
