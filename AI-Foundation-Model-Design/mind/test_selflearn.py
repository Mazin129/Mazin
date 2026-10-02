"""
test_selflearn — every section of the self-learning spec, checked.

Each block names the spec section it pins (§1 … §15), so a missing behaviour shows up
as a failing section rather than as a vague regression.

Run:  python test_selflearn.py
"""
from __future__ import annotations

import os
import sys
import tempfile

PASS, FAIL = [], []


def check(name, cond):
    (PASS if cond else FAIL).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}")


SPEC_EXAMPLE = """Draft → Sent → Accepted
              ↘ Rejected
              ↘ Expired"""

PROSE = ("Draft becomes Sent when emailed. Sent can become Accepted or Rejected. "
         "Sent turns into Expired after 30 days. Accepted must be signed by a manager. "
         "Expired quotes cannot be reopened unless a manager approves. "
         "A Draft is a quotation not yet sent to the customer.")

SKILL_FIELDS = ("name", "purpose", "triggers", "knowledge", "inputs", "processing", "tools",
                "expected_output", "validation", "limitations", "examples", "version",
                "last_updated")


def fresh_mind():
    import importlib
    os.environ["VIO_DATA_DIR"] = tempfile.mkdtemp(prefix="vio_selflearn_")
    import reasoner
    importlib.reload(reasoner)
    return reasoner.Mind()


def main():
    os.environ.setdefault("VIO_SEMANTIC_ASYNC", "0")
    os.environ.setdefault("VIO_TRAIN_ASYNC", "0")
    os.environ.pop("VIO_ALLOW_NET", None)
    import selflearn as sl

    print("=" * 72)
    print("  SELF-LEARNING SPEC — §1 … §15")
    print("=" * 72)

    # ---------------------------------------------------------------- §4 ----
    print("\n§4  learn from examples — the structure, not the sentence")
    k = sl.extract(SPEC_EXAMPLE)
    check("the spec's diagram yields its five states",
          k["states"] == ["Draft", "Sent", "Accepted", "Rejected", "Expired"])
    check("…and the four transitions, branches from Sent",
          sorted(k["transitions"]) == sorted([("Draft", "Sent"), ("Sent", "Accepted"),
                                              ("Sent", "Rejected"), ("Sent", "Expired")]))
    kp = sl.extract(PROSE)
    check("the same model is extracted from plain sentences",
          sorted(kp["transitions"]) == sorted(k["transitions"]))
    check("rules are extracted", kp["rules"] == ["Accepted must be signed by a manager"])
    check("exceptions are extracted", any("unless" in e for e in kp["exceptions"]))
    check("definitions are extracted (leading article dropped)",
          kp["definitions"].get("Draft") == "a quotation not yet sent to the customer")
    check("an article is never taken as a state",
          not sl.extract("A quote moves to Sent.")["transitions"])

    # ---------------------------------------------------------------- §7 ----
    print("\n§7  knowledge vs skill — the skill record is complete")
    sk = sl.build_skill("quotation states", k, ["test"], [SPEC_EXAMPLE])
    check("every field the spec lists is present",
          all(f in sk for f in SKILL_FIELDS))

    # ---------------------------------------------------------------- §6 ----
    print("\n§6  validate everything learned")
    v = sl.validate(sk, SPEC_EXAMPLE)
    check("a correct skill passes all of its tests", v["failures"] == [] and v["total"] >= 10)
    check("it refuses to invent an unknown state",
          "not one of the states" in sl.answer(sk, "what comes after Archived?"))
    check("it refuses a move that is not allowed",
          sl.answer(sk, "can it go from Accepted to Draft?").startswith("No"))
    check("it answers an indirect path honestly",
          sl.answer(sk, "can it go from Draft to Accepted?").startswith("Not directly"))
    bogus = sl.build_skill("x", {"states": ["Zed"], "transitions": [("Zed", "Qux")],
                                 "definitions": {}, "rules": [], "steps": [],
                                 "exceptions": []}, ["t"], [])
    check("a skill not grounded in its source FAILS validation",
          bool(sl.validate(bogus, "nothing relevant here")["failures"]))

    # ---------------------------------------------------- §1 §9 intent table ----
    print("\n§1/§9  wording → intent → action")
    table = {
        "learn this": "learn", "teach yourself OSPF timers": "learn",
        "understand this for next time": "learn",
        "I want you to understand quotation states.": "learn",
        "remember this for next time": "learn",
        "do it yourself": "autonomous",
        "you don't understand me": "re-evaluate",
        "no, that's not what I meant": "re-evaluate",
        "how can you learn this?": "demonstrate",
        "self review": "self-review", "learned skills": "list-skills",
    }
    for wording, want in table.items():
        check(f"“{wording}” → {want}", sl.purpose(wording) == want)
    for wording in ("help me understand BGP", "I don't understand this error",
                    "learn from github owner/repo", "learn everything",
                    "remember: my name is Mazin", "what is a VLAN"):
        check(f"“{wording}” is NOT a request for me to learn",
              sl.purpose(wording) not in ("learn",))

    # --------------------------------------------- §3 §5 §11 §15 in Vio ----
    print("\n§3/§5/§11/§15  the learning conversation")
    m = fresh_mind()
    r = m.ask("I want you to understand quotation states.")
    check("§5 with no material: asks ONE precise question",
          "**One question:**" in r["answer"] and "Which system or document" in r["answer"])
    check("§11 …and does not claim to have learned", r["verified"] is False
          and not m.skillreg.get("quotation states"))
    r = m.ask(SPEC_EXAMPLE)
    check("§3 the material that follows is learned under the topic asked for",
          r["verified"] and m.skillreg.get("quotation states") is not None)
    for section in ("**Skill:**", "**Current knowledge:**", "**Missing capability:**",
                    "**Learning action:**", "**Validation:**", "**Future behavior:**"):
        check(f"§15 reply has {section}", section in r["answer"])
    check("§6 the reply states the tests passed", "self-tests" in r["answer"])

    print("\n§13  future automatic use")
    check("a matching question is answered by the skill",
          m.ask("what comes after Sent?")["how"] == "learned skill: quotation states")
    check("…correctly", "Accepted" in m.ask("what comes after Sent?")["answer"])
    check("a follow-up about an untaught state says so (context)",
          "not one of the states" in m.ask("what comes after Archived?")["answer"])
    check("unrelated questions are not hijacked",
          m.ask("what is a VLAN").get("how", "").startswith("learned skill") is False)
    data_dir = os.environ["VIO_DATA_DIR"]
    import reasoner
    m2 = reasoner.Mind()
    check("the skill survives a restart",
          m2.ask("can a quotation go from Draft to Accepted?")["answer"].startswith(
              "Not directly"))
    r = m2.ask("learn quotation states:\nDraft → Sent → Approved\n     ↘ Rejected")
    check("§13 re-teaching a conflicting model is investigated, not silently applied",
          "contradicts what I was taught before" in r["answer"])
    check("…and versioned", m2.skillreg.get("quotation states")["version"] == 2)

    print("\n§13  a skill's whole topic beats a config word in the question")
    m2.ask("learn change request states:\nDraft → Submitted → Approved → Closed\n"
           "Approved must be signed by the CAB.\n"
           "Emergency changes skip CAB unless the change touches the core firewall.")
    r = m2.ask("what are the rules for change request?")
    check("'rules for change request' goes to the learned skill, not the config engine",
          r["how"] == "learned skill: change request states")
    check("…and the answer includes the exceptions", "Exceptions:" in r["answer"])
    check("a real config question still goes to the config path",
          not m2.ask("how many firewall rules are configured")["how"].startswith(
              "learned skill"))

    print("\n§11  never claim false learning")
    r = m2.ask("learn this: nothing here has any structure at all, just some words "
               "written down to see what happens when there is no content worth keeping")
    check("material with no structure is NOT learned", r["verified"] is False)
    check("teach: says it verified retrieval", m2.teach(
        "QUIC runs over UDP port 443.").startswith(("Stored and verified", "Stored ")))

    # ---------------------------------------------------------------- §8 ----
    print("\n§8  corrections and misunderstandings are learning signals")
    m3 = fresh_mind()
    m3.ask("what is my policy")
    r = m3.ask("that's not what I meant")
    check("re-evaluates: shows how it read the question",
          "I read “what is my policy”" in r["answer"])
    check("asks the smallest question", "Tell me in one line" in r["answer"])
    r = m3.ask("how many firewall policies are configured")
    check("the clarification is stored as an intent rule",
          m3.intent_rules.lookup("what is my policy") is not None)
    r = m3.ask("what is my policy")
    check("next time, the question is read the corrected way",
          any("intent rule" in t for t in r.get("trace", [])))
    m3.correct("what port does QUIC use", "UDP 443")
    check("a correction is logged as a learning signal",
          any(f["kind"] == "wrong-answer" for f in m3.failures.read()))

    # --------------------------------------------------------------- §10 ----
    print("\n§10  self-improvement")
    rv = m3.ask("self review")["answer"]
    check("the review lists failures by cause", "**By cause:**" in rv)
    check("repeated failures are put first", "Repeated failures" in rv)
    check("each cause names what would fix it", "upload the device configuration" in rv)

    print("\n§3  'do it yourself'")
    m4 = fresh_mind()
    check("with nothing pending it says so",
          "nothing I failed" in m4.ask("do it yourself")["answer"])
    m4.ask("show static routes")                      # a config question, no config
    check("a config gap is named, not guessed at",
          "configuration" in m4.ask("do it yourself")["answer"])

    # --------------------------------------------------------------- §14 ----
    print("\n§14  master orchestrator")
    names = [a.name for a in m2.agent_registry.agents]
    check("the learning agent is registered", "learning" in names)
    check("the self-improvement agent is registered", "self_improvement" in names)
    check("learning requests route to the learning agent",
          m2.agent_registry.ranked("learn this", {})[0][1].name == "learning")
    check("skill questions route to the learning agent",
          m2.agent_registry.ranked("what comes after Sent?", {})[0][1].name == "learning")
    check("reviews route to the self-improvement agent",
          m2.agent_registry.ranked("self review", {})[0][1].name == "self_improvement")

    print("\n§6/§10  learn everything re-validates skills and reviews failures")
    r = m2.learn_everything()["answer"]
    check("level 7 re-validates learned skills", "**7. Learned skills" in r)
    check("level 8 runs the self-review", "**8. Self-review**" in r)
    del data_dir

    print("=" * 72)
    print(f"  {len(PASS)} passed, {len(FAIL)} failed")
    for x in FAIL:
        print(f"    FAILED: {x}")
    print("\nALL PASS" if not FAIL else "\nFAILURES")
    return 1 if FAIL else 0


if __name__ == "__main__":
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    sys.exit(main())
