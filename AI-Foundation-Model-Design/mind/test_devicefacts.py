"""
test_devicefacts — serial / model / firmware / hostname answered exactly, and fast.

Run:  python test_devicefacts.py
"""
from __future__ import annotations

import os
import sys
import tempfile
import time

PASS, FAIL = [], []


def check(name, cond):
    (PASS if cond else FAIL).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}")


CFG = """#config-version=FG100F-7.2.5-FW-build1517-230606:opmode=0:vdom=0:user=admin
#conf_file_ver=1234
config system global
    set hostname "HQ-FGT-01"
end
config firewall policy
    edit 1
        set name "web"
        set srcintf "port2"
        set dstintf "wan1"
        set action accept
    next
end
"""
STATUS = """Version: FortiGate-100F v7.2.5,build1517,230606 (GA.F)
Serial-Number: FG100FTK21012345
Hostname: HQ-FGT-01
Uptime: 45 days, 3 hours, 12 minutes"""


def main():
    os.environ["VIO_DATA_DIR"] = tempfile.mkdtemp(prefix="vio_devfacts_")
    for k in ("VIO_SEMANTIC_ASYNC", "VIO_TRAIN_ASYNC", "VIO_STUDY_ASYNC"):
        os.environ[k] = "0"
    import reasoner
    import test_llm

    print("=" * 72)
    print("  DEVICE FACTS — exact, never guessed")
    print("=" * 72)
    m = reasoner.Mind()
    m.llm = test_llm.Fake(["qwen3.5:4b"], reply="a guess")
    m.llm.context = m._llm_context
    m.learn_file("HQ-FGT-01.conf", CFG.encode())
    calls = len(m.llm.bodies)

    t0 = time.time()
    r = m.ask("what is Serial Number from HQ fortigate")
    check("'HQ' finds HQ-FGT-01, read as a device question (not 'define hq')",
          "HQ-FGT-01" in r["answer"] and r["how"].startswith("device facts"))
    check("…answered without the model, in well under a second",
          len(m.llm.bodies) == calls and time.time() - t0 < 1.0)
    check("…and says honestly the config backup has no serial",
          "does not contain the serial" in r["answer"])
    check("…and how to provide it", "get system status" in r["answer"])
    check("the model comes from the config header",
          "FortiGate-100F" in m.ask("what is the model of HQ firewall")["answer"])
    check("so does the firmware",
          "7.2.5 build 1517" in m.ask("what firmware is the HQ fortigate running")["answer"])

    r = m.ask(STATUS)
    check("pasted 'get system status' output is recognised and kept",
          r["how"] == "device facts (stored)" and "FG100FTK21012345" in r["answer"])
    r = m.ask("what is Serial Number from HQ fortigate")
    check("…then the serial is answered exactly", "`FG100FTK21012345`" in r["answer"]
          and r["verified"])

    m.ask("remember: DR-FGT serial number is FG100FTK21099999")
    check("'remember:' naming a device is saved, not treated as a config question",
          "FG100FTK21099999" in m.ask("serial number of DR fortigate")["answer"])
    check("an unknown device is named as unknown, with the known ones listed",
          "Devices I know" in m.ask("serial number of the Jeddah fortigate JED")["answer"])
    check("'version of TLS' is not a device question",
          not m.ask("what is the version of TLS")["how"].startswith("device facts"))

    print("\n-- thinking only where it pays --")
    m._intents = []
    check("a lookup does not think", not m._think_for("what is the hq serial"))
    check("troubleshooting thinks", m._think_for("troubleshoot BGP flapping between sites"))

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
