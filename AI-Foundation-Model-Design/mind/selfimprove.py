"""
selfimprove  —  Stage 4: the GOVERNED self-improvement loop.

Vio proposes better versions of itself, but never promotes one automatically. The
pieces map 1:1 to the blueprint's loop:

    Production Vio → Feedback → Data Curator → Training → Candidate
                  → Evaluation → [Policy Approval gate] → Model Manager → new version

This module owns everything except Training (which is train_all.py / the Colab
fine-tune, run out-of-process). Nothing here changes an answer or a model on its
own — the approval gate is a hard stop that a human (or an explicit policy) must
pass. All local; append-only; safe to import even when unused.
"""
from __future__ import annotations

import os
import json
import time
import threading
from collections import Counter


# --------------------------------------------------------------------------- #
# 1) Behaviour-trace capture  — the audit trail (R3) AND the training raw material
# --------------------------------------------------------------------------- #
class TraceLog:
    """Append-only log of every interaction's decision path: question → agent →
    evidence → validation → answer, plus 👍/👎 feedback events that reference it.
    This is what the Curator turns into behaviour-trace training data, and what makes
    every answer auditable (why did Vio say that, via which agent, how sure)."""

    def __init__(self, path):
        self.path = path
        self._lock = threading.Lock()
        self._last_id = None

    def record(self, q, result, evidence=None):
        ev = evidence or {}
        rec = {
            "id": "%d" % int(time.time() * 1000),
            "ts": time.time(),
            "question": (q or "")[:2000],
            "agent": result.get("agent", ""),
            "how": result.get("how", ""),
            "verified": bool(result.get("verified")),
            "confidence": result.get("confidence"),
            "system": result.get("system"),
            "domain": result.get("domain"),
            "evidence": {k: ev.get(k) for k in ("top", "hits", "facts")},
            "answer": (result.get("answer") or "")[:4000],
        }
        try:
            with self._lock:
                with open(self.path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                self._last_id = rec["id"]
        except Exception:
            pass
        return rec["id"]

    def add_feedback(self, good):
        """Attach 👍/👎 to the most recent interaction — as an append-only event, so
        the log is never rewritten (the Curator joins events to interactions by id)."""
        try:
            with self._lock:
                if not self._last_id:
                    return
                with open(self.path, "a", encoding="utf-8") as f:
                    f.write(json.dumps({"type": "feedback", "ref": self._last_id,
                                        "good": bool(good), "ts": time.time()}) + "\n")
        except Exception:
            pass

    def read(self):
        out = []
        try:
            with open(self.path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            out.append(json.loads(line))
                        except Exception:
                            pass
        except FileNotFoundError:
            pass
        return out

    def stats(self):
        recs = self.read()
        inter = [r for r in recs if r.get("type") != "feedback"]
        fb = [r for r in recs if r.get("type") == "feedback"]
        return {
            "interactions": len(inter),
            "feedback": len(fb),
            "thumbs_up": sum(1 for r in fb if r.get("good")),
            "thumbs_down": sum(1 for r in fb if not r.get("good")),
            "verified": sum(1 for r in inter if r.get("verified")),
            "by_agent": dict(Counter(r.get("agent") or "?" for r in inter)),
        }


# --------------------------------------------------------------------------- #
# 2) Data Curator  — turn traces + feedback into CLEAN training data
# --------------------------------------------------------------------------- #
class Curator:
    """Selects the interactions worth learning from — verified answers, 👍'd answers,
    and confident ones — while dropping 👎, no-source, and error turns. Emits both a
    plain question→answer set AND the richer behaviour trace (question → intent/agent →
    answer) the blueprint calls for, so a future fine-tune learns judgement, not mimicry."""

    BAD_HOW = {"no-source", "error", "llm-timeout", "feedback", "welcome", "reset", "greeting"}

    def __init__(self, tracelog):
        self.log = tracelog

    def curate(self):
        recs = self.log.read()
        fb = {r["ref"]: r["good"] for r in recs if r.get("type") == "feedback" and r.get("ref")}
        keep = []
        for r in recs:
            if r.get("type") == "feedback":
                continue
            thumbs = fb.get(r.get("id"))
            if thumbs is False:                       # explicitly marked wrong
                continue
            if (r.get("how") or "") in self.BAD_HOW:
                continue
            good = r.get("verified") or thumbs is True or (r.get("confidence") or 0) >= 0.7
            if good and r.get("question") and r.get("answer"):
                keep.append(r)
        return keep

    def write(self, out_path):
        rows = self.curate()
        n = 0
        with open(out_path, "w", encoding="utf-8") as f:
            for r in rows:
                rec = {
                    "question": r["question"],
                    "answer": r["answer"],
                    # the behaviour trace — what a judgement-learning fine-tune trains on
                    "trace": {"agent": r.get("agent"), "how": r.get("how"),
                              "verified": r.get("verified"), "domain": r.get("domain")},
                }
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                n += 1
        return {"written": n, "out": out_path, "considered": len(self.log.read())}


# --------------------------------------------------------------------------- #
# 3) Evaluation  — the gate a candidate must pass
# --------------------------------------------------------------------------- #
class Evaluator:
    """Runs the capability benchmark (the golden set) in-process and returns a score.
    A candidate must not regress it — Evaluation is what blocks a bad promotion before
    the human ever sees it."""

    def run(self):
        # Run the benchmark in ISOLATION — a throwaway data dir subprocess — so it never
        # reads the live library (whose taught facts would break the honesty tests) and
        # gives a true, reproducible score for the gate.
        import subprocess
        import sys
        import tempfile
        import os
        import re
        try:
            here = os.path.dirname(os.path.abspath(__file__))
            env = {**os.environ, "VIO_DATA_DIR": tempfile.mkdtemp()}
            out = subprocess.run([sys.executable, os.path.join(here, "capability_test.py")],
                                 cwd=here, env=env, capture_output=True, text=True, timeout=600)
            text = (out.stdout or "") + (out.stderr or "")
            m = re.search(r"(\d+)\s*/\s*(\d+)\s+passed", text)
            passed, total = (int(m.group(1)), int(m.group(2))) if m else (0, 0)
            return {"passed": passed, "total": total,
                    "ratio": (passed / total) if total else 0.0}
        except Exception as e:
            return {"passed": 0, "total": 0, "ratio": 0.0, "error": str(e)[:120]}


# --------------------------------------------------------------------------- #
# 4) Model Manager  — version, promote (behind the gate), roll back
# --------------------------------------------------------------------------- #
class ModelManager:
    """Records which model Vio runs and keeps a promotion history so a bad version is
    reverted in one step (blueprint R4). Promotion requires approved=True — there is no
    path here that promotes automatically."""

    def __init__(self, path):
        self.path = path
        self.state = self._load()

    def _load(self):
        try:
            return json.load(open(self.path, encoding="utf-8"))
        except Exception:
            return {"current": os.environ.get("VIO_LLM_MODEL", ""), "history": []}

    def _save(self):
        try:
            json.dump(self.state, open(self.path, "w", encoding="utf-8"), indent=2)
        except Exception:
            pass

    def current(self):
        return self.state.get("current") or os.environ.get("VIO_LLM_MODEL", "(auto)")

    def promote(self, model, approved=False, note=""):
        if not approved:
            return {"ok": False, "gated": True,
                    "message": f"Promotion of '{model}' needs approval. Nothing changed."}
        prev = self.state.get("current")
        self.state.setdefault("history", []).append(
            {"from": prev, "to": model, "ts": time.time(), "note": note})
        self.state["current"] = model
        self._save()
        return {"ok": True, "current": model, "previous": prev}

    def rollback(self):
        hist = self.state.get("history") or []
        if not hist:
            return {"ok": False, "message": "No previous version to roll back to."}
        last = hist[-1]
        self.state["current"] = last.get("from")
        self.state.setdefault("history", []).append(
            {"from": last.get("to"), "to": last.get("from"), "ts": time.time(),
             "note": "rollback"})
        self._save()
        return {"ok": True, "current": self.state["current"]}


# --------------------------------------------------------------------------- #
# 5) Orchestrator  — runs the loop UP TO the approval gate, never through it
# --------------------------------------------------------------------------- #
class SelfImprovement:
    def __init__(self, data_dir):
        self.traces = TraceLog(os.path.join(data_dir, "traces.jsonl"))
        self.curator = Curator(self.traces)
        self.evaluator = Evaluator()
        self.models = ModelManager(os.path.join(data_dir, "model_state.json"))
        self.data_dir = data_dir

    def propose(self):
        """Do everything a candidate needs EXCEPT train and promote: curate the data,
        run the evaluation gate, and stop at 'awaiting approval'. Training (train_all.py
        / the fine-tune notebook) and promotion (models.promote(approved=True)) are the
        human-gated steps that live outside this call."""
        curated = self.curator.write(os.path.join(self.data_dir, "curated_sft.jsonl"))
        gate = self.evaluator.run()
        ready = curated["written"] >= 200
        return {
            "curated": curated,
            "evaluation": gate,
            "current_model": self.models.current(),
            "status": ("ready to train a candidate" if ready
                       else f"not enough curated data yet ({curated['written']}/200)"),
            "next": ("1) train on curated_sft.jsonl  2) evaluate the candidate  "
                     "3) approve  4) models.promote(model, approved=True)"),
            "gate": "Nothing was trained or promoted — approval required.",
        }
