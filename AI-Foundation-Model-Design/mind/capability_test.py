"""
capability_test  —  a hard, honest capability benchmark for Vio.

Runs a wide battery across every subsystem — exact math, everyday tools, grounded
retrieval, structured reasoning, world-model simulation, planning, memory, skills, the
multi-part agent, and (crucially) the cases Vio SHOULD refuse. Prints a per-category
scorecard so you can see exactly what it can and can't do.

SAFE TO RUN: it points Vio's stores at a throwaway temp directory (VIO_DATA_DIR), so it
NEVER touches your real knowledge base, memory, skills, or graph. Nothing you taught Vio
is read or changed.

    python capability_test.py
"""

import os
import tempfile

# Isolate BEFORE importing Vio: every store will read/write this throwaway dir.
os.environ["VIO_DATA_DIR"] = tempfile.mkdtemp(prefix="vio_captest_")

from reasoner import Mind          # noqa: E402  (must come after VIO_DATA_DIR is set)
from talk import reply            # noqa: E402
from agent import SolveAgent      # noqa: E402


def main():
    m = Mind()
    ag = SolveAgent(m)

    # ---- teach a small, self-contained knowledge base to reason over ----
    for f in [
        "OSPF is a link-state routing protocol used inside an autonomous system.",
        "A VLAN is a virtual LAN that segments a network into broadcast domains.",
        "Congestion causes packet loss.", "Packet loss causes retransmission.",
        "Retransmission causes higher latency.",
        "To configure a VLAN, first create the VLAN. Then assign ports to it. "
        "Finally enable the interface.",
        "If a link fails then OSPF recalculates the best route.",
    ]:
        m.ask("teach: " + f)
    m.ask("remember: my name is Mazin.")
    m.ask("skill: hi | when: hi {who} | reply: Hey {who}!")

    R = []   # (category, name, ok, detail)

    def T(cat, name, q, contains=None, want=None, how_prefix=None, fn=None):
        r = (fn or m.ask)(q)
        ans = r["answer"] if isinstance(r, dict) else str(r)
        ok = True
        if want is not None:
            ok = ok and ans.strip() == want
        if contains is not None:
            ok = ok and contains.lower() in ans.lower()
        if how_prefix is not None:
            ok = ok and r.get("how", "").startswith(how_prefix)
        R.append((cat, name, ok,
                  f"[{r.get('how','')} · {r.get('confidence','')}] {ans[:64]}"))

    # 1. EXACT MATH — verified, must be exactly right
    T("Math", "quadratic", "solve x^2 - 5x + 6 = 0", want="x = 2, 3")
    T("Math", "system", "solve x+y=10, x-y=2", contains="x = 6")
    T("Math", "calculus", "integrate x^2", contains="x**3/3")
    T("Math", "derivative", "derivative of sin(x)", contains="cos(x)")
    T("Math", "inequality", "solve x^2 - 4 > 0", contains="x")
    T("Math", "big arithmetic", "2^10 + 7*3", contains="1045")
    T("Math", "factorial", "12 factorial", contains="479001600")
    T("Math", "prime", "is 97 prime", contains="prime")
    T("Math", "combinatorics", "10 choose 3", contains="120")
    T("Math", "percent", "15% of 200", contains="30")
    T("Math", "statistics", "average of 4, 8, 15, 16, 23, 42", contains="18")
    T("Math", "unit convert", "5 km to miles", contains="3.10")
    T("Math", "number base", "255 in hex", contains="ff")

    # 2. GROUNDED RETRIEVAL — only from what it was taught
    T("Retrieval", "definition", "what is a vlan?", contains="segments")
    T("Retrieval", "definition 2", "what is ospf?", contains="link-state")
    T("Retrieval", "personal fact", "what is my name?", contains="mazin")

    # 3. STRUCTURED REASONING — knowledge graph
    T("Reasoning", "causal", "what causes packet loss?", contains="congestion", how_prefix="reasoning")
    T("Reasoning", "deductive", "if a link fails what happens?", contains="recalcul", how_prefix="reasoning")

    # 4. WORLD MODEL — simulate before answering
    T("World model", "forward chain", "what happens if congestion occurs?", contains="latency", how_prefix="world model")
    T("World model", "counterfactual", "what if packet loss didn't happen?", contains="latency", how_prefix="world model")

    # 5. PLANNING — grounded steps
    T("Planning", "how-to", "how do I configure a vlan?", contains="port", how_prefix="planning")

    # 6. SKILLS + MEMORY
    T("Skills", "user reflex", "hi Sara", want="Hey Sara!", fn=lambda q: reply(m, q))
    T("Memory", "episodic recall", "what did we talk about?", contains="vlan", how_prefix="episodic")

    # 7. MULTI-PART AGENT
    T("Agent", "two-part question", "what is 20% of 50 and what is 9 factorial?",
      contains="362880", fn=lambda q: ag.solve(q))

    # 8. HONESTY — these SHOULD be refused (the most important category)
    T("Honesty", "untaught fact", "who won the 2050 world cup?", how_prefix="no-source")
    T("Honesty", "live data", "what is the stock price of Apple?", how_prefix="no-source")

    # ---- scorecard ----
    cats = {}
    for cat, name, ok, detail in R:
        cats.setdefault(cat, []).append((name, ok, detail))
    passed = sum(1 for *_, ok, _ in R for _ in [0] if ok)
    passed = sum(1 for _, _, ok, _ in R if ok)

    print("\n" + "=" * 76)
    print(f"  VIO CAPABILITY BENCHMARK        {passed}/{len(R)} passed "
          f"({passed*100//len(R)}%)")
    print("=" * 76)
    for cat, items in cats.items():
        p = sum(1 for _, ok, _ in items if ok)
        print(f"\n  {cat}  ({p}/{len(items)})")
        for name, ok, detail in items:
            print(f"    {'PASS' if ok else 'FAIL'}  {name:18} {detail}")
    print("\n" + "=" * 76)
    print("  Runs against a throwaway data dir — your real Vio was not touched.")
    print("=" * 76)


if __name__ == "__main__":
    main()
