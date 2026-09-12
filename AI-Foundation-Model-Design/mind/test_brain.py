"""
test_brain — pins Vio's decision core.

The brain decides, for every question, what evidence could answer it and whether that
evidence exists. Get that wrong and no model is good enough to save the answer, so
these checks cover the three stages that matter: the reading, the decision, and the
verification gate. They are deterministic and need no model.
"""
from __future__ import annotations

import sys

import brain

PASS, FAIL = [], []


def check(name, cond):
    (PASS if cond else FAIL).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}")


class Obj:
    """Stand-in for configparse.ConfigObject."""

    def __init__(self, kind, name):
        self.kind, self.name = kind, name


def evidence(objs=(), passages=0, facts=0, model=None):
    ev = brain.Evidence()
    ev.config_objects = list(objs)
    for o in ev.config_objects:
        ev.config_kinds[o.kind] = ev.config_kinds.get(o.kind, 0) + 1
    ev.vocabulary = brain.config_vocabulary(ev.config_objects)
    ev.passages, ev.facts, ev.model = passages, facts, model
    return ev


def main():
    print("=" * 72)
    print("  BRAIN — understanding, decision, verification")
    print("=" * 72)

    FORTI = [Obj("router static", "1"), Obj("router static", "2"),
             Obj("router static", "3"), Obj("firewall policy", "1"),
             Obj("firewall policy", "2"), Obj("firewall address", "LAN")]
    ev_cfg = evidence(FORTI, passages=80, model="qwen2.5:3b")
    ev_docs = evidence([], passages=80, model="qwen2.5:3b")
    ev_bare = evidence([], passages=0)
    V = ev_cfg.vocabulary

    print("\n-- the config vocabulary is LEARNED from the loaded config --")
    check("kinds learned from the config", V.get("policy", (None,))[0] == "firewall policy")
    check("'route' maps to the routing table", V.get("route", (None,))[0] == "router static")
    check("plurals work ('policies')", V.get("policies", (None,))[0] == "firewall policy")
    check("plurals of s-ending nouns ('addresses')",
          V.get("addresses", (None,))[0] == "firewall address")
    check("a device noun ranks below a distinctive word",
          V["firewall"][1] < V["policy"][1])
    # a vendor this code has never heard of works with no code change
    exotic = brain.config_vocabulary([Obj("zone-protection profile", "z1")])
    check("unknown vendor kinds are learned too",
          exotic.get("profile", (None,))[0] == "zone-protection profile")

    print("\n-- reading: instance vs concept --")
    u = brain.understand("show static route on SA-OCC firewall", V)
    check("enumerate form", u.form == "enumerate")
    check("kind resolved past the device noun", u.kind == "router static")
    check("host extracted", u.host == "SA-OCC")
    check("requires the device config", u.requires == brain.CONFIG)

    u = brain.understand("how many policies are configured", V)
    check("count form", u.form == "count")
    check("count of objects requires config", u.requires == brain.CONFIG)

    u = brain.understand("what is a firewall policy", V)
    check("definition is a concept, not a device lookup",
          u.requires == brain.KNOWLEDGE)

    u = brain.understand("why would BGP sessions flap", V)
    check("diagnose form", u.form == "diagnose")
    check("acronym wins as the subject", u.subject == "bgp")
    check("diagnosis requires reasoning", u.requires == brain.REASONING)

    check("live values are recognised",
          brain.understand("what is the current bitcoin price", V).requires == brain.LIVE)
    check("arithmetic is computed, not looked up",
          brain.understand("2^10 + 7*3", V).requires == brain.TOOL)
    check("questions about the user hit memory",
          brain.understand("what is my name", V).requires == brain.MEMORY)

    print("\n-- multi-part messages stay separate --")
    us = brain.read("show static route on SA-OCC firewall\nlist static routes\n"
                    "show me the firewall policies\nhow many policies are configured", V)
    check("four questions split into four", len(us) == 4)
    check("each keeps its own kind",
          us[0].kind == "router static" and us[2].kind == "firewall policy")
    check("the count part is read as a count", us[3].form == "count")

    print("\n-- decisions follow the evidence, not the keywords --")
    u_route = brain.understand("show static route on SA-OCC firewall", V)
    check("config present → exact answer",
          brain.decide(u_route, ev_cfg).strategy == "config-exact")
    u_route_nodocs = brain.understand("show static route on SA-OCC firewall", {})
    check("no config → refuses instead of using documentation",
          brain.decide(u_route_nodocs, ev_docs).strategy == "need-config")
    u_addr = brain.understand("list address objects", V)
    check("config present but wrong kind → says which kinds exist",
          brain.decide(u_addr, evidence(FORTI[:5], passages=80)).strategy
          == "need-config-kind")
    check("live data always abstains",
          brain.decide(brain.understand("what is the weather", V), ev_cfg).strategy
          == "abstain")
    check("reasoning without a model degrades honestly",
          brain.decide(brain.understand("why would BGP flap", V),
                       evidence([], passages=80)).strategy == "grounded")
    check("nothing at all → abstain",
          brain.decide(brain.understand("what is a widget", {}), ev_bare).strategy
          == "abstain")

    print("\n-- the shortfall message is specific, not a vague apology --")
    msg = brain.shortfall_message(brain.decide(u_route_nodocs, ev_docs), ev_docs)
    check("names the host", "SA-OCC" in msg)
    check("says what it holds", "80 passage" in msg)
    check("says what to do", "show full-configuration" in msg)
    msg2 = brain.shortfall_message(
        brain.decide(u_addr, evidence(FORTI[:5], passages=80)),
        evidence(FORTI[:5], passages=80))
    check("missing-kind message lists the kinds present",
          "router static" in msg2 and "firewall policy" in msg2)

    print("\n-- verification: scraps never pass as answers --")
    FRAG = ("config router static. config router static6. "
            "Configure a policy that accepts direct routes.")
    check("scrap pile detected", brain.looks_fragmentary(FRAG) is True)
    check("scrap pile never verified",
          brain.verify({"answer": FRAG, "verified": True, "how": "synthesis"},
                       {"hits": 3}, "show routes")["verified"] is False)
    check("scrap pile is replaced, not shown",
          "only fragments" in brain.verify(
              {"answer": FRAG, "verified": True, "how": "synthesis"},
              {"hits": 3}, "show routes")["answer"])
    check("real prose survives",
          brain.looks_fragmentary("A static route sends traffic for a prefix to a "
                                  "fixed next-hop. Three are configured here.") is False)
    check("exact listings are never called fragments",
          brain.verify({"answer": "  [1] dst 10.0.0.0/8 via 1.1.1.1\n  [2] dst 0.0.0.0/0",
                        "verified": True,
                        "how": "analysis over your config (exact listing)"},
                       {"hits": 2}, "show routes")["verified"] is True)
    check("empty answer never verified",
          brain.verify({"answer": "", "verified": True}, {}, "q")["verified"] is False)
    check("security claim without evidence is unverified",
          brain.verify({"answer": "mTLS uses certificates", "how": "reasoning (LLM)",
                        "verified": True}, {}, "how does mtls work")["verified"] is False)

    print("\n-- stub passages: ingest noise is not knowledge --")
    for t in ("config router static.", "Per Route", "Confirm the policy:", "end",
              "Example 1", "Static Routes"):
        check(f"stub: {t!r}", brain.is_stub_passage(t) is True)
    for t in ("OSPF is link-state", "TLS encrypts traffic", "my name is Mazin",
              "Static routes are configured under config router static on FortiOS.",
              "config router static\n  edit 1\n  set gateway 10.0.0.1\nnext"):
        check(f"real: {t.splitlines()[0][:38]!r}", brain.is_stub_passage(t) is False)
    check("stubs are never cited",
          "Per Route" not in brain.citations(
              {"excerpts": ["Per Route", "Static routes reach a fixed next-hop gateway."]}))

    print("=" * 72)
    print(f"  {len(PASS)} passed, {len(FAIL)} failed")
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
