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

    # not-yet-migrated capabilities fall back to the core router (no agent tag) and MATCH it
    for q in ("what is 20% of 50", "what is OSPF"):
        a, c = m.ask_agentic(q), m._ask_core(q)
        check(f"fallback matches core: {q!r}", a.get("agent") is None and a["answer"] == c["answer"],
              f"agent={a.get('agent')} eq={a['answer'] == c['answer']}")

    # the live default path is untouched — a math answer still comes straight from ask()
    check("legacy ask() intact", "10" in m.ask("what is 20% of 50")["answer"])

    print("\n" + ("ALL PASS" if not fails else f"{len(fails)} FAILED: {fails}"))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
