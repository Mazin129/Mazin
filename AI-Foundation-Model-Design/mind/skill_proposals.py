"""
skill_proposals  —  governed autonomy for agent self-development.

Agents may RESEARCH the web and PROPOSE new SkillBook reflexes (trigger + reply
templates). They never write executable code, never auto-install skills, and never
bypass human approval.

Lifecycle:
  research / train skill: <topic>  →  SkillProposal (pending)
  approve skill: <id|name>         →  SkillBook.add(...)
  reject skill: <id|name>          →  marked rejected

Proposals are plain data (name, trigger, reply, source, evidence). Same safety
contract as skills.py: no eval/exec; triggers compile to escaped regex only.
"""

from __future__ import annotations

import json
import os
import re
import time
import uuid

HERE = os.environ.get("VIO_DATA_DIR") or os.path.dirname(os.path.abspath(__file__))
PROPOSALS_FILE = os.path.join(HERE, "skill_proposals.json")
MAX_PENDING = 200
MAX_LEN = 2000

_SLOT = re.compile(r"\{([a-zA-Z][a-zA-Z0-9_]*)\}")


def _safe_text(s, n=MAX_LEN):
    return (s or "").strip()[:n]


class SkillProposalStore:
    def __init__(self, path=None):
        self.path = path or PROPOSALS_FILE
        self.items = []
        self._load()

    def _load(self):
        try:
            raw = json.load(open(self.path, encoding="utf-8"))
            self.items = list(raw) if isinstance(raw, list) else []
        except Exception:
            self.items = []

    def _save(self):
        dump = [{k: v for k, v in it.items() if not k.startswith("_")}
                for it in self.items]
        try:
            json.dump(dump, open(self.path, "w", encoding="utf-8"),
                      ensure_ascii=False, indent=2)
        except Exception:
            pass

    def list(self, status=None):
        out = []
        for it in self.items:
            if status and it.get("status") != status:
                continue
            out.append({k: v for k, v in it.items() if k != "evidence" or True})
        return out

    def get(self, key):
        key = (key or "").strip().lower()
        for it in self.items:
            if it.get("id", "").lower() == key or it.get("name", "").lower() == key:
                return it
        return None

    def propose(self, name, trigger, reply, source="", evidence="", agent=""):
        name = _safe_text(name, 80)
        trigger = _safe_text(trigger)
        reply = _safe_text(reply)
        if not (name and trigger and reply):
            return None, "A proposal needs name, trigger, and reply."
        t_slots = set(_SLOT.findall(trigger))
        r_slots = set(_SLOT.findall(reply))
        missing = r_slots - t_slots
        if missing:
            return None, f"Reply uses {{{', '.join(missing)}}} not in trigger."
        pending = [i for i in self.items if i.get("status") == "pending"]
        if len(pending) >= MAX_PENDING:
            return None, "Too many pending proposals — approve or reject some first."
        # replace prior pending with same name
        self.items = [i for i in self.items
                      if not (i.get("name", "").lower() == name.lower()
                              and i.get("status") == "pending")]
        item = {
            "id": uuid.uuid4().hex[:10],
            "name": name,
            "trigger": trigger,
            "reply": reply,
            "source": _safe_text(source, 400),
            "evidence": _safe_text(evidence, 4000),
            "agent": _safe_text(agent, 80),
            "status": "pending",
            "ts": time.time(),
        }
        self.items.append(item)
        self._save()
        return item, f"Proposed skill “{name}” (id={item['id']}). Approve with: approve skill: {item['id']}"

    def approve(self, key, skillbook):
        it = self.get(key)
        if not it:
            return False, f"No proposal matching “{key}”."
        if it.get("status") == "approved":
            return True, f"Already approved: {it['name']}"
        if it.get("status") == "rejected":
            return False, f"Proposal “{it['name']}” was rejected — re-propose if needed."
        ok, msg = skillbook.add(it["name"], it["trigger"], it["reply"])
        if not ok:
            return False, msg
        it["status"] = "approved"
        it["approved_ts"] = time.time()
        self._save()
        return True, f"Approved & installed skill “{it['name']}”. {msg}"

    def reject(self, key, reason=""):
        it = self.get(key)
        if not it:
            return False, f"No proposal matching “{key}”."
        it["status"] = "rejected"
        it["reject_reason"] = _safe_text(reason, 400)
        it["rejected_ts"] = time.time()
        self._save()
        return True, f"Rejected proposal “{it['name']}”."


def draft_from_research(topic, answer_text, sources=None, llm=None):
    """Build a conservative skill proposal from a research answer.
    Prefer LLM structured draft when available; else a safe template."""
    topic = _safe_text(topic, 120)
    if not topic:
        return None
    src = "; ".join((sources or [])[:3])[:400]
    body = _safe_text(answer_text, 1500)
    name = re.sub(r"[^a-z0-9_]+", "_", topic.lower()).strip("_")[:40] or "web_skill"
    trigger = f"quick fact {topic}"
    reply = body[:800] if body else f"I researched “{topic}” but had no extract to store."
    if llm is not None and getattr(llm, "available", False):
        prompt = (
            "Draft ONE teachable chat skill as JSON with keys name, trigger, reply.\n"
            "Rules: trigger is a short phrase the user might type (optional {slot}); "
            "reply is a concise factual template (may use same {slots}); "
            "no code, no URLs-only dumps, no markdown fences — ONLY the JSON object.\n"
            f"Topic: {topic}\n"
            f"Evidence excerpt:\n{body[:1200]}\n"
        )
        try:
            raw = llm.generate(prompt, system="You output only valid JSON.", max_tokens=400)
            m = re.search(r"\{[\s\S]*\}", raw or "")
            if m:
                data = json.loads(m.group(0))
                if data.get("name") and data.get("trigger") and data.get("reply"):
                    return {
                        "name": _safe_text(data["name"], 80),
                        "trigger": _safe_text(data["trigger"]),
                        "reply": _safe_text(data["reply"]),
                        "source": src or f"research:{topic}",
                        "evidence": body[:2000],
                    }
        except Exception:
            pass
    return {
        "name": name,
        "trigger": trigger,
        "reply": reply,
        "source": src or f"research:{topic}",
        "evidence": body[:2000],
    }
