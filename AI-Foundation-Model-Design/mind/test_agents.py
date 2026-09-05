"""
test_agents  —  Stage 1 guard: the agent master routes correctly and the agentic
path stays behaviour-preserving (migrated capabilities via agents, everything else
falling back to the proven core router). Run:  python test_agents.py
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

    # registry wired
    names = [a.name for a in m.agent_registry.agents]
    check("registry populated", set(("skill", "math", "world_model", "reasoning",
          "config", "memory", "planner")) <= set(names), str(names))

    # seed a little knowledge
    m.skills.add("greet", "hi", "Hey there!")
    m.teach("Congestion causes higher latency.")
    m.teach("OSPF is a link-state routing protocol.")

    # migrated capabilities route through the expected agent
    check("skill -> skill agent", m.ask_agentic("hi").get("agent") == "skill")
    check("symbolic math -> math agent", m.ask_agentic("integrate x^2").get("agent") == "math")
    check("what-if -> world_model agent",
          m.ask_agentic("what happens if congestion occurs").get("agent") == "world_model")

    # Stage 3b: retrieval is a first-class KnowledgeAgent; exact-tool queries with
    # retrieval-tempting words (factorial, roman) must still go to the front, not Knowledge.
    check("retrieval -> knowledge agent", m.ask_agentic("what is OSPF").get("agent") == "knowledge")
    check("exact tool not hijacked by knowledge",
          m.ask_agentic("roman numeral for 42").get("agent") == "core")

    # Stage 2: EVERY answer carries provenance (the core catch-all tags itself from `how`)
    for q in ("what is 20% of 50", "what is OSPF", "hi", "integrate x^2"):
        check(f"provenance present: {q!r}", bool(m.ask_agentic(q).get("agent")))

    # PARITY: routing through the master must equal the proven core router, everywhere
    battery = ["what is 20% of 50", "what is OSPF", "integrate x^2",
               "what happens if congestion occurs", "solve x^2-5x+6=0",
               "what is a VLAN", "hello", "roman numeral for 42"]
    for q in battery:
        a, c = m.ask_agentic(q), m._ask_core(q)
        check(f"parity with core: {q!r}", a["answer"] == c["answer"],
              f"\n     agentic: {a['answer'][:60]}\n     core:    {c['answer'][:60]}")

    # the live default path (ask -> executive -> _route -> master) works end to end
    check("legacy ask() intact", "10" in m.ask("what is 20% of 50")["answer"])

    # R1/R2 guardrail: an ACTING (write) agent is gated behind confirmation; a read-only
    # agent passes straight through. (No live agent has write perms yet, so this is the
    # safety foundation for future Automation/Code/Web agents.)
    from agents import Agent, Result, Registry, Master, WRITE

    class _Write(Agent):
        name = "mock_write"
        permissions = frozenset(("read", WRITE))
        def score(self, q, ctx): return 0.99
        def run(self, q, ctx): return Result("Applied the change.", how="automation", verified=True)

    class _Read(Agent):
        name = "mock_read"
        def score(self, q, ctx): return 0.99
        def run(self, q, ctx): return Result("Here is the info.", how="advice", verified=True)

    gm = Master(Registry()); gm.registry.register(_Write(None))
    gated = gm.handle("apply the config")
    check("acting agent gated", "confirm" in (gated.answer or "").lower() and not gated.verified)
    okr = gm.handle("apply the config", {"confirmed": True})
    check("confirmed action passes ungated", okr.answer.strip() == "Applied the change." and okr.verified)

    rm = Master(Registry()); rm.registry.register(_Read(None))
    ra = rm.handle("tell me something")
    check("advisory passes ungated", ra.answer == "Here is the info." and ra.verified)

    print("\n" + ("ALL PASS" if not fails else f"{len(fails)} FAILED: {fails}"))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
