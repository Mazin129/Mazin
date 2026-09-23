"""
test_selfimprove  —  Stage 4 guard: behaviour-trace capture, the Data Curator's
filtering, and the Model Manager's approval gate + rollback. Run:
    python test_selfimprove.py
"""
import os
import sys
import tempfile

os.environ.setdefault("VIO_DATA_DIR", tempfile.mkdtemp())
from reasoner import Mind


def main():
    m = Mind()
    fails = []

    def check(label, cond, detail=""):
        print(f"  {'PASS' if cond else 'FAIL'}  {label}" + (f"  ({detail})" if detail and not cond else ""))
        if not cond:
            fails.append(label)

    # capture: real interactions are logged with provenance
    m.teach("OSPF is a link-state routing protocol.")
    m.ask("what is OSPF")            # verified knowledge -> kept
    m.ask("integrate x^2")          # verified math -> kept
    m.feedback(True)                # 👍 on the math answer
    m.ask("what is the president of the moon")  # no-source -> dropped by curator
    m.ask("blorptron zzz")          # no-source -> dropped
    m.feedback(False)               # 👎 on the last

    st = m.si.traces.stats()
    check("interactions captured", st["interactions"] >= 4, str(st))
    check("feedback captured", st["feedback"] == 2 and st["thumbs_up"] == 1 and st["thumbs_down"] == 1, str(st))
    check("provenance in traces", "knowledge" in st["by_agent"] and "math" in st["by_agent"], str(st))

    # curator: keeps good, drops no-source and 👎
    curated = m.si.curator.curate()
    check("curator kept some", len(curated) >= 2, str(len(curated)))
    check("curator dropped no-source", all((r.get("how") or "") != "no-source" for r in curated))

    # Model manager: promotion is gated TWICE — by human approval, and by the golden
    # suite. Approval alone is no longer enough for a candidate model; the caller must
    # also present a green golden result. (The UI brain dropdown is a live switch
    # between already-installed models, not a promotion, so it opts out with
    # require_golden=False.) All four paths are checked here.
    mm = m.si.models
    gated = mm.promote("candidate-v2")
    check("promote gated without approval", gated.get("gated") and not gated.get("ok"))

    no_golden = mm.promote("candidate-v2", approved=True)
    check("approved promote still blocked without a green golden suite",
          no_golden.get("gated") and not no_golden.get("ok")
          and "golden" in (no_golden.get("message") or "").lower())

    switched = mm.promote("candidate-v2", approved=True, require_golden=False)
    check("live model switch applies (golden not required)",
          switched.get("ok") and mm.current() == "candidate-v2")

    rb = mm.rollback()
    check("rollback reverts", rb.get("ok") and mm.current() != "candidate-v2")

    # the orchestrator runs the golden suite itself, then promotes if it is green
    promoted = m.si.promote("candidate-v3", approved=True)
    check("orchestrator promotes when the golden suite is green",
          promoted.get("ok") and mm.current() == "candidate-v3", str(promoted.get("message", "")))
    check("rollback reverts the orchestrator promotion too",
          m.si.rollback().get("ok") and mm.current() != "candidate-v3")

    # propose(): runs curate + eval, stops at the approval gate (never trains/promotes)
    prop = m.si.propose()
    check("propose stops at gate", "approval required" in prop["gate"].lower()
          and "curated" in prop and "evaluation" in prop)

    print("\n" + ("ALL PASS" if not fails else f"{len(fails)} FAILED: {fails}"))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
