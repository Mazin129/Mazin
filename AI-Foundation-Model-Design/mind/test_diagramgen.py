"""Tests for the diagram generator (LLM-free parts): the vendored skill is present,
type selection, prompt assembly, HTML extraction, and safe save/load."""
import os
import tempfile

import diagramgen as d


def _ok(label, cond):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}")
    assert cond, label


def main():
    print("=" * 56 + "\n  DIAGRAM GENERATOR TESTS")
    _ok("vendored skill present", d.available())

    _ok("architecture picked", d.pick_type("network architecture of the DMZ") == "architecture")
    _ok("sequence picked", d.pick_type("sequence diagram of the oauth handshake") == "sequence")
    _ok("flowchart picked", d.pick_type("flowchart of the decision logic") == "flowchart")
    _ok("er picked", d.pick_type("entity relationship data model") == "er")
    _ok("swimlane picked", d.pick_type("cross-functional swimlane of the process") == "swimlane")
    _ok("default is architecture", d.pick_type("something totally unspecified") == "architecture")

    p = d.build_prompt("a flowchart of login", "flowchart")
    _ok("prompt assembles sections",
        all(s in p for s in ("STYLE GUIDE", "OUTPUT SPEC", "LAYOUT REFERENCE", "DIAGRAM REQUEST")))
    _ok("prompt carries the request", "a flowchart of login" in p)

    _ok("extract from fenced html",
        d.extract_html("sure:\n```html\n<!doctype html><html><body><svg></svg></body></html>\n```")
        .startswith("<!doctype html>"))
    _ok("extract bare svg",
        d.extract_html("<svg width='1'><rect/></svg>").startswith("<svg"))
    _ok("extract empty on junk", d.extract_html("no html here") == "no html here")

    tmp = tempfile.mkdtemp()
    did, path = d.save("<!doctype html><html>ok</html>", tmp)
    _ok("save writes under diagrams/", os.path.isfile(path) and "diagrams" in path)
    _ok("load roundtrips", (d.load(did, tmp) or "").startswith("<!doctype html>"))
    _ok("load rejects path traversal", d.load("../../etc/passwd", tmp) is None)
    _ok("load rejects non-numeric id", d.load("abc", tmp) is None)

    print("\nALL PASS")


if __name__ == "__main__":
    main()
