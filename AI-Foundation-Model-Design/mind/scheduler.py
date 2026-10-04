"""
scheduler — proactive autonomy (roadmap T12).

A daemon thread that runs Vio's own maintenance on a schedule, through the same
governed paths the chat commands use (so every run is bounded and audited):

  · nightly  — `cover gaps`  (curiosity engine + web research, bounded 8×2,
               still requires VIO_ALLOW_NET — no net, no run)
  · weekly   — `consolidate` (dedupe/mine/prune) + library cleanup

Off by default: start with VIO_SCHED=1 (web.py starts the thread). Every run is
skipped while a request is in flight (idle check), and all output lands in the
episodic log so the dashboard shows what Vio did on its own.
"""
from __future__ import annotations

import os
import threading
import time


def _enabled():
    return os.environ.get("VIO_SCHED", "").strip().lower() in ("1", "true", "yes", "on")


def start(mind):
    """Start the scheduler thread. Returns the Thread or None (disabled)."""
    if not _enabled():
        return None
    t = threading.Thread(target=_loop, args=(mind,), daemon=True, name="vio-scheduler")
    t.start()
    return t


def _loop(mind):
    last_nightly = 0.0
    last_weekly = 0.0
    while True:
        time.sleep(300)                              # check every 5 minutes
        now = time.time()
        hour = time.localtime(now).tm_hour
        # nightly: once per day, in the 3:00–5:00 window, only when idle
        if 3 <= hour < 5 and now - last_nightly > 20 * 3600:
            _run(mind, "nightly")
            last_nightly = now
            last_weekly = last_weekly or now
        # weekly: once per 7 days, same idle rule
        if now - last_weekly > 7 * 86400:
            _run(mind, "weekly")
            last_weekly = now


def _run(mind, kind):
    """One scheduled pass. Everything goes through the normal chat commands, so
    the guardrails, bounds, and episodic logging all apply unchanged."""
    import websearch
    # idle check: don't compete with a live request
    if getattr(mind, "_busy", False):
        return
    try:
        if kind == "nightly":
            gaps = len(getattr(mind.curiosity, "gaps", {}) or {})
            if not gaps:
                return
            if not websearch.net_enabled():
                return                               # cover gaps needs the web opt-in
            r = mind.cover_gaps()
            mind.episodic.record(f"[scheduler] nightly cover gaps",
                                 str(r.get("answer", ""))[:400], "learned", 0.3,
                                 kind="scheduler")
        elif kind == "weekly":
            r = mind.consolidate()
            mind.episodic.record("[scheduler] weekly consolidate",
                                 json_safe(r), "learned", 0.3, kind="scheduler")
    except Exception:
        pass                                         # a scheduler miss must never matter


def json_safe(d):
    return ", ".join(f"{k}={v}" for k, v in (d or {}).items())[:400]
