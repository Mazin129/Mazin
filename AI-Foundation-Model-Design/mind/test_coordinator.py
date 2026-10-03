"""
test_coordinator — every agent talks through one coordinator, shares one board, and
the web fills knowledge gaps (only when switched on, never with private data).

Run:  python test_coordinator.py
"""
from __future__ import annotations

import os
import sys
import tempfile

PASS, FAIL = [], []


def check(name, cond):
    (PASS if cond else FAIL).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}")


Q = ("what is the difference between Azure Virtual WAN secured hub and a hub VNet "
     "with Azure Firewall?")
WEB_PAGE = ("Azure Virtual WAN secured hub is a Microsoft-managed virtual hub with Azure "
            "Firewall Manager policies; a hub VNet with Azure Firewall is customer-managed "
            "with user-defined routes.")


def main():
    os.environ["VIO_DATA_DIR"] = tempfile.mkdtemp(prefix="vio_coord_")
    for k in ("VIO_SEMANTIC_ASYNC", "VIO_TRAIN_ASYNC", "VIO_STUDY_ASYNC"):
        os.environ[k] = "0"
    os.environ.pop("VIO_ALLOW_NET", None)
    import coordinator
    import reasoner
    import test_llm

    print("=" * 72)
    print("  COORDINATOR — one hub, one board, web for gaps")
    print("=" * 72)
    m = reasoner.Mind()
    m.llm = test_llm.Fake(["qwen3.5:4b"], reply=(
        "Lower the tunnel MTU to 1400 and clamp TCP MSS; the Riyadh datacenter end must "
        "match."))
    m.llm.context = m._llm_context
    m.ask("remember: the HQ IPsec tunnel goes to the Riyadh datacenter")
    r = m.ask("troubleshoot the HQ IPsec tunnel dropping large packets")
    check("the coordinator briefs the answering agent from the others",
          "memory" in (r.get("team") or "") and "knowledge" in (r.get("team") or ""))
    sysmsg = m.llm.bodies[-1].get("prompt", "")
    check("…so the expert's prompt carries what the memory agent holds",
          "Riyadh datacenter" in sysmsg)
    talk = m.agent_conversation()
    check("the agents' conversation is recorded",
          "coordinator → network_engineering" in talk and "memory → coordinator" in talk)

    r = m.ask(Q)
    check("a knowledge gap with web OFF is reported, not hidden",
          "web research is OFF" in (r.get("team") or ""))

    queries = []

    def fake_research(query, **_k):
        queries.append(query)
        m.lib.add_many([WEB_PAGE])
        return {"answer": "ok", "how": "web research", "ok": True}
    m.research = fake_research
    m.ask("web on")
    r = m.ask(Q)
    check("with web ON the research agent fills the gap",
          len(queries) == 1 and "researched on the web" in (r.get("team") or ""))
    check("…and what it read is in the shared library for every agent",
          WEB_PAGE in m.lib.docs)
    m.ask(Q)
    check("…so the same question is not searched again", len(queries) == 1)
    m.ask("why is HQ-FGT-01 at 10.10.1.4 dropping traffic from mazin@flynas.com?")
    check("a question about the user's own systems is never web-searched",
          len(queries) == 1)
    s = coordinator.scrub("HQ-FGT-01 at 10.10.1.4 mail mazin@flynas.com FG100FTK21012345")
    check("private identifiers are stripped from any query",
          not any(x in s for x in ("HQ-FGT", "10.10", "@", "FG100F")))
    os.environ.pop("VIO_ALLOW_NET", None)          # a fresh process: no env setting
    reasoner.Mind()
    check("the web switch is remembered across restarts",
          os.environ.get("VIO_ALLOW_NET") == "1")
    m.ask("web off")
    check("web off turns it off", os.environ.get("VIO_ALLOW_NET") == "0")
    rep = m.agents_report()
    check("the dashboard gets the coordinator's last conversation",
          rep.get("coordinator", {}).get("messages"))

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
