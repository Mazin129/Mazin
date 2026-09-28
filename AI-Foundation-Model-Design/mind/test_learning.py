"""
test_learning — pins Vio's self-learning pipeline and its safety rails.

Three failures motivated this file, and each is pinned here:

  1. The GitHub learner ignored licences and learned from any repository. It now
     reads the repo's own LICENSE and refuses non-commercial, no-derivatives,
     all-rights-reserved and unlicensed repos BEFORE storing anything.
  2. Running self-improvement inside a live Vio executed the golden test suite
     in-process, and its fixture config (three fake firewall policies) was written
     into the user's REAL library. The suite now runs isolated, and Mind removes
     any fixture passages an earlier run left behind.
  3. The library had no de-duplication, so every re-run of a learning pass stacked
     identical copies. `learn everything` must be safe to run repeatedly.

The GitHub path is driven through the real learn_github → fetch_repo_docs code with
the clone step replaced by a local copy, so no network is needed.

Run:  python test_learning.py
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile

PASS, FAIL = [], []


def check(name, cond):
    (PASS if cond else FAIL).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}")


MIT = ("MIT License\n\nCopyright (c) 2024 Someone\n\nPermission is hereby granted, free "
       "of charge, to any person obtaining a copy of this software...")
LICENCES = {
    "MIT": ("allow", MIT),
    "Apache-2.0": ("allow", "Apache License\nVersion 2.0, January 2004\n"
                   "http://www.apache.org/licenses/ ... Derivative Works ..."),
    "BSD-3 (says 'All rights reserved')": (
        "allow", "Copyright (c) 2020, Acme\nAll rights reserved.\n\nRedistribution and use "
        "in source and binary forms ... Neither the name of the copyright holder nor the "
        "names of its contributors may be used ..."),
    "GPL-3 (says 'noncommercially')": (
        "allow", "GNU GENERAL PUBLIC LICENSE\nVersion 3, 29 June 2007\n... only "
        "occasionally and noncommercially ..."),
    "CC-BY-4.0": ("allow", "Creative Commons Attribution 4.0 International ... "
                  "creativecommons.org/licenses/by/4.0"),
    "CC-BY-NC-SA (the CIS benchmark licence)": (
        "refuse", "Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International"),
    "CC-BY-ND": ("refuse", "Attribution-NoDerivatives 4.0 International"),
    "Proprietary": ("refuse", "Copyright 2025 BigCorp. All rights reserved."),
    "Unrecognised": ("refuse", "Please ask before using this."),
    "No licence file": ("none", None),
}

SKILL_DOC = ("# Firewall review skill\n\nWhen reviewing a firewall rule base, check for "
             "shadowed rules, any-any accepts, and management access on WAN interfaces. "
             "Rank findings by exposure and name the exact objects involved.\n")


def make_repo(licence_text):
    d = tempfile.mkdtemp(prefix="vio_fake_repo_")
    if licence_text is not None:
        with open(os.path.join(d, "LICENSE"), "w", encoding="utf-8") as f:
            f.write(licence_text)
    with open(os.path.join(d, "SKILL.md"), "w", encoding="utf-8") as f:
        f.write(SKILL_DOC)
    return d


def main():
    os.environ["VIO_DATA_DIR"] = tempfile.mkdtemp(prefix="vio_learning_")
    os.environ.setdefault("VIO_SEMANTIC_ASYNC", "0")
    os.environ.setdefault("VIO_TRAIN_ASYNC", "0")
    os.environ.pop("VIO_LEARN_UNLICENSED", None)

    print("=" * 72)
    print("  SELF-LEARNING — licences, isolation, idempotence")
    print("=" * 72)

    import gitlearn

    # ---- 1. licence detection ------------------------------------------------
    print("\n-- licence detection (including the traps) --")
    for name, (want, text) in LICENCES.items():
        verdict = gitlearn.detect_license(make_repo(text))[1]
        check(f"{name} → {want}", verdict == want)

    # ---- 1b. the gate inside the real learn_github path --------------------------
    print("\n-- the gate runs before anything is stored --")
    from reasoner import Mind
    m = Mind()
    os.environ["VIO_ALLOW_NET"] = "1"                  # learn_github's opt-in
    real_clone = gitlearn._clone
    current = {"src": None}

    def fake_clone(owner, repo, dest):                  # no network: copy a local dir
        shutil.copytree(current["src"], dest)
    gitlearn._clone = fake_clone
    try:
        before = len(m.lib.docs)
        current["src"] = make_repo(LICENCES["CC-BY-NC-SA (the CIS benchmark licence)"][1])
        refused = None
        try:
            m.learn_github("someone/nc-repo")
        except gitlearn.LicenseRefused as e:
            refused = str(e)
        check("a non-commercial repo is refused", refused is not None)
        check("the refusal names the reason", refused and "commercial" in refused)
        check("nothing from a refused repo is stored", len(m.lib.docs) == before)

        current["src"] = make_repo(None)
        try:
            m.learn_github("someone/no-licence")
            nolic = None
        except gitlearn.LicenseRefused as e:
            nolic = str(e)
        check("an unlicensed repo is refused", nolic is not None)
        check("…with the override hint for your own repos",
              nolic and "VIO_LEARN_UNLICENSED" in nolic)

        os.environ["VIO_LEARN_UNLICENSED"] = "1"
        current["src"] = make_repo(None)
        r = m.learn_github("me/my-own-notes")
        check("the override learns your own unlicensed repo", r.get("ok"))
        os.environ.pop("VIO_LEARN_UNLICENSED", None)

        current["src"] = make_repo(MIT)
        r = m.learn_github("someone/mit-skills")
        check("an MIT repo is learned", r.get("ok") and r.get("passages", 0) > 0)
        check("the licence is reported", (r.get("licence") or {}).get("spdx") == "MIT")
        check("provenance is recorded",
              any(s.get("source") == "github:someone/mit-skills" and s.get("licence") == "MIT"
                  for s in m.mem.get("sources_learned", [])))
        check("the learned skill is retrievable",
              any("shadowed rules" in d for d in m.lib.docs))
    finally:
        gitlearn._clone = real_clone
        os.environ.pop("VIO_ALLOW_NET", None)

    # ---- 2. golden-suite isolation and clean-up ------------------------------
    print("\n-- self-improvement never writes test data into your library --")
    import brain
    import golden_eval
    cfg_before = len(brain.survey(m).config_objects)
    docs_before = len(m.lib.docs)
    g = m.si.propose().get("golden") or {}
    check("the golden gate still runs from a live Vio",
          (g.get("correctness") or {}).get("total", 0) > 0 and not g.get("error"))
    check("it added no config objects to the live library",
          len(brain.survey(m).config_objects) == cfg_before)
    check("it added no passages to the live library", len(m.lib.docs) == docs_before)

    leaked = list(golden_eval.fixture_passages(m._smart_chunks))
    m.lib.add_many(leaked)                              # simulate an old, leaky run
    polluted = len(brain.survey(m).config_objects)
    m2 = Mind()                                         # restart cleans it up
    check("a library polluted by an old run had the fake policies", polluted > cfg_before)
    check("restarting removes exactly the fixture passages",
          len(brain.survey(m2).config_objects) == cfg_before)

    # ---- 3. idempotence ------------------------------------------------------
    print("\n-- learning is safe to repeat --")
    n = len(m2.lib.docs)
    added = m2.lib.add_many(["A unique passage about BGP route reflectors.",
                             "A unique passage about BGP route reflectors."])
    check("identical passages in one batch are stored once", added == 1)
    check("re-adding an existing passage adds nothing",
          m2.lib.add_many(["A unique passage about BGP route reflectors."]) == 0)
    check("library grew by exactly one", len(m2.lib.docs) == n + 1)

    r1 = m2.ask("learn everything")
    size1 = len(m2.lib.docs)
    r2 = m2.ask("learn everything")
    check("learn everything runs every level",
          all(f"**{i}." in r1["answer"] for i in range(1, 7)))
    check("the bundled datasets are learned", size1 > n + 100)
    check("a second run adds nothing", len(m2.lib.docs) == size1)
    check("offline, the web levels say why they were skipped",
          "VIO_ALLOW_NET=1" in r1["answer"])
    check("it never trains or promotes", "Nothing was trained or promoted" in r2["answer"])
    check("ordinary questions are not mistaken for the command",
          m2.ask("what is self learning").get("how") != "self-learning (all levels)")

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
