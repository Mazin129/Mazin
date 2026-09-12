"""
test_understand — pins the question-understanding layer.

Understanding is upstream of everything: get the reading wrong and the right agent is
never asked, the wrong evidence is used, and the answer is wrong no matter how good the
model is. These cases pin the readings that were actually getting mis-routed.
"""
from __future__ import annotations

import sys

import understand as u

PASS, FAIL = [], []


def check(name, cond):
    (PASS if cond else FAIL).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}")


def main():
    print("=" * 70)
    print("  UNDERSTANDING LAYER")
    print("=" * 70)

    # ---- the failure that started this: a config lookup read as documentation ----
    it = u.parse_one("show static route on SA-OCC firewall")
    check("list op detected", it.operation == "list")
    check("route object detected", it.object == "route")
    check("device SA-OCC extracted", it.device == "SA-OCC")
    check("requires the device config", it.evidence == "config")
    check("routed to network_engineering", it.agent == "network_engineering")

    it = u.parse_one("how many policies are configured?")
    check("count op detected", it.operation == "count")
    check("policy object detected", it.object == "policy")
    check("count requires config", it.evidence == "config")

    # ---- concept questions must NOT be read as device lookups -------------------
    it = u.parse_one("what is a VLAN?")
    check("define op detected", it.operation == "define")
    check("VLAN read as a concept, not an interface table", it.object is None)
    check("definition needs knowledge, not config", it.evidence == "knowledge")

    it = u.parse_one("explain the difference between TCP and UDP")
    check("compare op detected", it.operation == "compare")
    check("comparison never needs a config", it.evidence != "config")

    # ---- troubleshooting is reasoning, not a table dump -------------------------
    it = u.parse_one("why would BGP sessions flap?")
    check("troubleshoot op detected", it.operation == "troubleshoot")
    check("BGP concept detected", it.concept == "bgp")
    check("troubleshooting needs reasoning", it.evidence == "reasoning")

    # ---- filters turn an exact listing into a search ----------------------------
    it = u.parse_one("show me firewall policies that point to the internet")
    check("filter detected", it.filtered is True)
    check("filtered listing still needs config", it.evidence == "config")

    it = u.parse_one("list static routes")
    check("unfiltered listing is not marked filtered", it.filtered is False)

    # ---- a pasted blob is several questions, not one bag of keywords ------------
    blob = ("show static route on SA-OCC firewall\nlist static routes\n"
            "show me the firewall policies\nhow many policies are configured")
    its = u.parse(blob)
    check("four-question paste splits into 4", len(its) == 4)
    check("last part read as a count", its[3].operation == "count")
    check("parts keep their own objects",
          its[0].object == "route" and its[2].object == "policy")

    # ---- vendor vs device: "on FortiGate" is not a hostname ---------------------
    it = u.parse_one("how do I configure OSPF on FortiGate")
    check("vendor detected", (it.vendor or "").lower().startswith("forti"))
    check("vendor is not mistaken for a device name", it.device is None)

    # ---- the summary is human-checkable -----------------------------------------
    s = u.parse_one("show static route on SA-OCC firewall").summary()
    check("summary names the device", "SA-OCC" in s)
    check("summary names the evidence needed", "device configuration" in s)

    print("=" * 70)
    print(f"  {len(PASS)} passed, {len(FAIL)} failed")
    if FAIL:
        for f in FAIL:
            print(f"    FAILED: {f}")
    print("\nALL PASS" if not FAIL else "\nFAILURES")
    return 1 if FAIL else 0


if __name__ == "__main__":
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    sys.exit(main())
