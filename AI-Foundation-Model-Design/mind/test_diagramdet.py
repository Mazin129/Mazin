"""Tests for the deterministic diagram renderer — no LLM, always non-blank SVG."""
import re

import diagramdet as d


def _ok(label, cond):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}")
    assert cond, label


def _shapes(html):
    return len(re.findall(r"<(?:rect|circle|polygon|ellipse|path|line)\b", html))


def main():
    print("=" * 56 + "\n  DETERMINISTIC DIAGRAM TESTS")

    # zones + edges
    spec = ("zone: External\n Internet\nzone: DMZ\n Web\n Proxy\nzone: Internal\n App\n DB\n"
            "Internet -> Proxy\nProxy -> Web\nWeb -> App\nApp -> DB")
    p = d.parse_spec(spec)
    _ok("graph kind", p["kind"] == "graph")
    _ok("5 nodes parsed", len(p["nodes"]) == 5)
    _ok("4 edges parsed", len(p["edges"]) == 4)
    _ok("3 zones parsed", set(p["zones"]) == {"External", "DMZ", "Internal"})
    g = d.render(p, title="DMZ")
    _ok("graph renders many shapes", _shapes(g) >= 10 and "<svg" in g)
    _ok("graph is self-contained (no external refs)",
        "http://" not in g.replace("http://www.w3.org/2000/svg", "") and "<script" not in g)

    # numbered steps → flow
    f = d.parse_spec("1. detect\n2. contain\n3. eradicate\n4. recover")
    _ok("flow kind", f["kind"] == "flow" and len(f["steps"]) == 4)
    _ok("flow renders 4 boxes", len(re.findall(r"<rect", d.render(f, title="IR"))) >= 4)

    # A: B, C → edges
    t = d.parse_spec("SOC Lead: Tier1, Tier2, Threat Intel")
    _ok("children become edges", len(t["edges"]) == 3)

    # freeform 'then' sequence, no LLM
    r = d.from_description("draw: detect then contain then eradicate then recover", llm=None)
    _ok("freeform then→flow", r["ok"] and r["kind"] == "flow" and _shapes(r["html"]) >= 4)

    # freeform comma list, no LLM
    r2 = d.from_description("diagram: web server, app server, database", llm=None)
    _ok("freeform list→graph", r2["ok"] and _shapes(r2["html"]) >= 3)

    # never blank: even a bare topic yields a valid document
    r3 = d.from_description("draw: our network", llm=None)
    _ok("never blank", "<svg" in r3["html"] and _shapes(r3["html"]) >= 1)

    print("\nALL PASS")


if __name__ == "__main__":
    main()
