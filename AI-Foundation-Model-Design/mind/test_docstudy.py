"""
test_docstudy — teaching a document is measured, studied and reportable.

Run:  python test_docstudy.py
"""
from __future__ import annotations

import os
import sys
import tempfile

PASS, FAIL = [], []


def check(name, cond):
    (PASS if cond else FAIL).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}")


DOC = """Azure Landing Zone: Single Firewall versus Multiple Firewalls

This comparison evaluates a single centralised Azure Firewall in the hub virtual network against deploying multiple firewalls, one per environment such as production, non-production and DMZ.

A single firewall reduces licensing cost and operational overhead. All spoke traffic is inspected in one place, and routing uses user-defined routes pointing to the hub firewall private IP address.

Multiple firewalls provide blast-radius isolation between environments. A misconfiguration in the non-production firewall cannot affect production traffic. Each firewall must be patched and monitored separately, which increases cost by roughly three times.

Recommendation: deploy a single Azure Firewall Premium in the hub with separate rule collection groups per environment. Production rule changes must be approved by the CAB.
"""

DIGEST = ("**What it is about** — single versus multiple Azure firewalls in a landing "
          "zone. **Recommendation** — one Azure Firewall Premium in the hub, with rule "
          "collection groups per environment.")


def main():
    os.environ["VIO_DATA_DIR"] = tempfile.mkdtemp(prefix="vio_docstudy_")
    for k in ("VIO_SEMANTIC_ASYNC", "VIO_TRAIN_ASYNC", "VIO_STUDY_ASYNC"):
        os.environ[k] = "0"
    import reasoner
    import test_llm

    print("=" * 72)
    print("  DOCUMENT LEARNING — read, self-test, study, report")
    print("=" * 72)

    m = reasoner.Mind()
    m.llm = test_llm.Fake(["qwen3.5:4b"], reply=DIGEST)
    m.llm.context = m._llm_context
    r = m.learn_document(DOC, "Flynas - Crayon - Azure Landing Zone.pdf")
    check("reports how much it actually read", "words" in r and "passage(s)" in r)
    check("self-tests retrieval and reports the score", "Self-test:" in r and "/" in r)
    check("finds the document's rules", "rule(s)" in r)
    check("says it is studying, not that it 'learned' it", "studying it" in r)
    check("the model was asked to study the document",
          any("Part 1 of" in b.get("prompt", "") for b in m.llm.bodies))
    check("…and thought about the digest",
          any(b.get("think") is True for b in m.llm.bodies))

    rep = m.ask("what did you learn from the azure landing zone document")["answer"]
    check("'what did you learn from X' finds the document by name",
          "Flynas - Crayon" in rep)
    check("…and shows what it understood", "What I understood" in rep
          and "Premium in the hub" in rep)
    check("'summarize the last file' works too",
          m.ask("summarize the last file")["how"] == "document report")
    check("the understanding is stored as knowledge for later answers",
          any(d.startswith("Study notes on Flynas") for d in m.lib.docs))

    again = m.learn_document(DOC, "Flynas - Crayon - Azure Landing Zone.pdf")
    check("re-teaching the same file says nothing new was stored",
          "nothing new stored" in again)

    check("an unknown document name lists what it holds",
          "Documents I hold" in m.ask("what did you learn from the cisco ise guide")["answer"])

    m2 = reasoner.Mind()
    m2.llm = None
    r = m2.learn_document("A short note. " * 40, "note.txt")
    check("without a model it says it could store but not study",
          "could not STUDY" in r)

    print("=" * 72)
    print(f"  {len(PASS)} passed, {len(FAIL)} failed")
    print("\nALL PASS" if not FAIL else "\nFAILURES")
    return 1 if FAIL else 0


if __name__ == "__main__":
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    sys.exit(main())
