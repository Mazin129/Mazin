"""
test_smoke — call EVERY public entry point once and make sure nothing crashes.

This exists because `learn_folder` referenced an undefined name and raised NameError on
the first file it read. Folder ingest had never worked, and no suite noticed: the other
tests all check answer QUALITY on paths they already exercise, so a path nobody calls
can stay broken indefinitely.

So this suite is deliberately shallow and deliberately wide. It does not judge whether
an answer is good — the other suites do that. It asserts only:

    every public method runs without raising
    every answer is a dict with an "answer" key
    odd input (empty, whitespace, punctuation, very long, multi-line) does not crash
    a fresh Mind with NO configuration behaves, and one WITH a configuration behaves

Run:  python test_smoke.py
"""
from __future__ import annotations

import os
import sys
import tempfile
import traceback

CONFIG = """
config system interface
    edit "port1"
        set ip 10.10.0.2 255.255.255.0
    next
end
config firewall address
    edit "LAN"
        set subnet 192.168.1.0 255.255.255.0
    next
end
config firewall policy
    edit 1
        set name "lan-out"
        set srcintf "port1"
        set dstintf "port1"
        set srcaddr "LAN"
        set dstaddr "all"
        set service "HTTPS"
        set action accept
    next
end
config router static
    edit 1
        set dst 0.0.0.0 0.0.0.0
        set gateway 10.10.0.1
        set device "port1"
    next
end
"""

QUERIES = [
    # config questions
    "show static routes",
    "how many policies are configured",
    "list address objects",
    "audit my config",
    "config status",
    "show static route on SA-OCC firewall\nlist static routes\nhow many policies",
    # knowledge / reasoning
    "what is a VLAN",
    "why would BGP sessions flap",
    "explain the difference between TCP and UDP",
    # tools and memory
    "2^10 + 7*3",
    "what is 15% of 200",
    "remember: my name is Mazin",
    "what is my name",
    # commands
    "understand: list policies",
    "clean library",
    "agents",
    "who answers: show routes",
    "council: what is NAT",
    "list gaps",
    "list sources",
    "teach: QUIC runs over UDP 443",
    "correct: the answer is 42",
    "that's wrong",
    "how calibrated are you",
    "what do you want to learn",
    "what did we talk about",
    # abstention
    "what is the stock price of Apple",
    "what is the flimport protocol xyzzy",
    # malformed / hostile input
    "",
    "   ",
    "?????",
    "a" * 2000,
    "\n\n\n",
    "show\nshow\nshow\nshow",
    "SELECT * FROM users; DROP TABLE x;--",
    "<script>alert(1)</script>",
]

PASS, FAIL = [], []


def check(name, fn):
    try:
        fn()
        PASS.append(name)
        return True
    except Exception as e:
        FAIL.append((name, f"{type(e).__name__}: {e}"))
        print(f"  FAIL  {name}\n        {type(e).__name__}: {e}")
        traceback.print_exc(limit=3)
        return False


def main():
    tmp = tempfile.mkdtemp(prefix="vio_smoke_")
    os.environ["VIO_DATA_DIR"] = tmp
    os.environ.setdefault("VIO_SEMANTIC_ASYNC", "0")
    os.environ.setdefault("VIO_TRAIN_ASYNC", "0")
    os.environ.pop("VIO_ALLOW_NET", None)

    print("=" * 72)
    print("  SMOKE — every entry point, nothing may crash")
    print("=" * 72)

    from reasoner import Mind
    m = Mind()

    # a folder to ingest: this is the path that was silently broken
    folder = tempfile.mkdtemp(prefix="vio_smoke_docs_")
    with open(os.path.join(folder, "device.conf"), "w", encoding="utf-8") as fh:
        fh.write(CONFIG)
    with open(os.path.join(folder, "notes.txt"), "w", encoding="utf-8") as fh:
        fh.write("OSPF is a link-state routing protocol.\n"
                 "BGP uses TCP port 179 to establish sessions.\n")

    print("\n-- folder ingest (the path that was broken) --")

    def _folder():
        r = m.learn_folder(folder)
        assert r["ok"], f"learn_folder reported failure: {r}"
        assert r["files"] == 2, f"expected 2 files, got {r['files']}: {r}"
        assert r["passages"] > 0, f"no passages learned: {r}"
    check("learn_folder ingests a folder without crashing", _folder)

    def _folder_config():
        r = m.ask("how many policies are configured")
        assert "1 firewall policy object" in r["answer"], r["answer"][:120]
    check("a config learned from a folder is queryable", _folder_config)

    print("\n-- every public method --")
    methods = [
        ("teach", lambda: m.teach("MTU mismatch causes fragmentation.")),
        ("remember", lambda: m.remember("my name is Mazin")),
        ("learn_text", lambda: m.learn_text("TLS 1.3 removed RSA key exchange.", "n.txt")),
        ("load_csv", lambda: m.load_csv("a,b\n1,2\n3,4\n", "t.csv")),
        ("config_status", lambda: m.config_status()),
        ("audit_config", lambda: m.audit_config()),
        ("clean_library", lambda: m.clean_library()),
        ("load_builtin", lambda: m.load_builtin()),
        ("list_gaps", lambda: m.list_gaps()),
        ("list_sources", lambda: m.list_sources()),
        ("agents_summary", lambda: m.agents_summary()),
        ("agents_report", lambda: m.agents_report()),
        ("who_answers", lambda: m.who_answers("show static routes")),
        ("council", lambda: m.council("what is a VLAN")),
        ("telemetry", lambda: m.telemetry()),
        ("consolidate", lambda: m.consolidate()),
        ("feedback", lambda: m.feedback(True)),
        ("correct", lambda: m.correct("what is X", "X is Y")),
        ("draw", lambda: m.draw("a DMZ behind a firewall")),
        ("research", lambda: m.research("bgp")),
        ("own_model", lambda: m.own_model()),
        ("_library_summary", lambda: m._library_summary()),
    ]
    for name, fn in methods:
        check(f"{name}()", fn)

    print("\n-- every query shape returns a well-formed answer --")
    bad_shape = []
    for q in QUERIES:
        label = (q[:38] + "…") if len(q) > 38 else (repr(q) if not q.strip() else q)
        label = label.replace("\n", "⏎")

        def _q(q=q, label=label):
            r = m.ask(q)
            assert isinstance(r, dict), f"not a dict: {type(r)}"
            assert "answer" in r, f"no 'answer' key: {list(r)}"
            assert isinstance(r["answer"], str), f"answer not a str: {type(r['answer'])}"
            assert "verified" in r, f"no 'verified' key: {list(r)}"
        if not check(f"ask({label})", _q):
            bad_shape.append(q)

    print("\n-- the brain survives a library with no config --")

    def _no_config():
        import brain
        ev = brain.Evidence()
        u = brain.understand("how many policies are configured", {})
        p = brain.decide(u, ev)
        assert p.strategy == "need-config", p.strategy
        assert brain.shortfall_message(p, ev)
    check("decide + shortfall_message on an empty Evidence", _no_config)

    print("\n-- a hostname is never mistaken for the subject --")

    def _host_subject():
        import brain
        u = brain.understand("show static route on SA-OCC firewall", {})
        assert u.host == "SA-OCC", u.host
        assert u.subject != "sa", f"device name taken as the topic: {u.subject}"
    check("SA-OCC is the device, not the topic", _host_subject)

    print("\n-- every answer declares whether the model ran --")

    def _cortex():
        for q in ("show static routes", "how many policies are configured",
                  "audit my config", "what is the weather"):
            r = m.ask(q)
            assert r.get("cortex"), f"{q!r} has no cortex field: {r.get('how')}"
    check("cortex is set on deterministic paths too", _cortex)

    print("=" * 72)
    print(f"  {len(PASS)} passed, {len(FAIL)} failed")
    for name, err in FAIL:
        print(f"    FAILED: {name} — {err}")
    print("\nALL PASS" if not FAIL else "\nFAILURES")
    return 1 if FAIL else 0


if __name__ == "__main__":
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    sys.exit(main())
