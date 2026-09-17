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
    hows = {r.get("how", "").split(" ")[0] for r in curated}
    check("curator kept some", len(curated) >= 2, str(len(curated)))
    check("curator dropped no-source", all((r.get("how") or "") != "no-source" for r in curated))

    # model manager: promotion is GATED, rollback works
    mm = m.si.models
    gated = mm.promote("candidate-v2")
    check("promote gated without approval", gated.get("gated") and not gated.get("ok"))
    ok = mm.promote("candidate-v2", approved=True)
    check("approved promote applies", ok.get("ok") and mm.current() == "candidate-v2")
    rb = mm.rollback()
    check("rollback reverts", rb.get("ok") and mm.current() != "candidate-v2")

    # propose(): runs curate + eval, stops at the approval gate (never trains/promotes)
    prop = m.si.propose()
    check("propose stops at gate", "approval required" in prop["gate"].lower()
          and "curated" in prop and "evaluation" in prop)

    print("\n" + ("ALL PASS" if not fails else f"{len(fails)} FAILED: {fails}"))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
