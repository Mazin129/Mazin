"""
skills  —  Vio's user-teachable skill book.

A "skill" lets you teach Vio a new reflex from the chat WITHOUT any coding and
WITHOUT any risk: it is pure data (patterns + a reply template), never executable
code. When your message matches a skill's trigger, Vio answers with that skill's
reply — optionally filling in {slots} captured from what you said.

    trigger:  "greet {name}"     reply: "Hello {name}! 👋"
    you say:  "greet Mazin"      Vio:   "Hello Mazin! 👋"

Design/safety:
  - Triggers and replies are plain text. Placeholders are written as {word}.
  - A trigger compiles to a strict regex where the ONLY dynamic part is each
    {slot} -> a bounded, non-greedy capture. Every other character is escaped, so
    a malicious trigger cannot inject regex or code. No eval/exec anywhere.
  - Skills persist to skills.json next to the other memory files.

This is the AXIOM "add-a-skill" idea (doc 06) at its simplest honest form: the user
grows the assistant's competence at runtime, and every skill is inspectable.
"""

import json
import os
import re

HERE = os.environ.get("VIO_DATA_DIR") or os.path.dirname(os.path.abspath(__file__))
SKILLS_FILE = os.path.join(HERE, "skills.json")

_SLOT = re.compile(r"\{([a-zA-Z][a-zA-Z0-9_]*)\}")
MAX_SKILLS = 500
MAX_LEN = 2000


def _compile(trigger):
    """Turn a trigger string into (regex, slot_names). Everything is escaped
    except {slot} placeholders, which become bounded non-greedy captures."""
    slots = []
    out = ["^\\s*"]
    i = 0
    for m in _SLOT.finditer(trigger):
        out.append(re.escape(trigger[i:m.start()]))
        name = m.group(1)
        slots.append(name)
        out.append(r"(.{1,200}?)")
        i = m.end()
    out.append(re.escape(trigger[i:]))
    out.append("\\s*$")
    # collapse escaped runs of whitespace so spacing is forgiving
    pattern = "".join(out).replace(r"\ ", r"\s+")
    return re.compile(pattern, re.IGNORECASE | re.UNICODE), slots


class SkillBook:
    def __init__(self):
        self.skills = []
        if os.path.exists(SKILLS_FILE):
            try:
                self.skills = json.load(open(SKILLS_FILE, encoding="utf-8"))
            except (ValueError, OSError):
                self.skills = []
        self._recompile()

    def _recompile(self):
        for s in self.skills:
            try:
                s["_rx"], s["_slots"] = _compile(s["trigger"])
            except re.error:
                s["_rx"], s["_slots"] = None, []

    def _save(self):
        dump = [{"name": s["name"], "trigger": s["trigger"], "reply": s["reply"]}
                for s in self.skills]
        json.dump(dump, open(SKILLS_FILE, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)

    def add(self, name, trigger, reply):
        name = (name or "").strip()[:80]
        trigger = (trigger or "").strip()[:MAX_LEN]
        reply = (reply or "").strip()[:MAX_LEN]
        if not (name and trigger and reply):
            return False, "A skill needs a name, a trigger, and a reply."
        if len(self.skills) >= MAX_SKILLS:
            return False, "Skill limit reached — remove some skills first."
        # slot names in the reply must exist in the trigger
        t_slots = set(_SLOT.findall(trigger))
        r_slots = set(_SLOT.findall(reply))
        missing = r_slots - t_slots
        if missing:
            return False, f"Reply uses {{{', '.join(missing)}}} not found in the trigger."
        self.skills = [s for s in self.skills if s["name"].lower() != name.lower()]
        self.skills.append({"name": name, "trigger": trigger, "reply": reply})
        self._recompile()
        self._save()
        return True, f"Skill “{name}” learned. Try it: {trigger}"

    def remove(self, name):
        before = len(self.skills)
        self.skills = [s for s in self.skills if s["name"].lower() != (name or "").lower()]
        self._save()
        return len(self.skills) < before

    def match(self, query):
        """Return (skill_name, reply) for the first matching skill, else None."""
        for s in self.skills:
            rx = s.get("_rx")
            if not rx:
                continue
            m = rx.match(query.strip())
            if m:
                reply = s["reply"]
                for slot, val in zip(s["_slots"], m.groups()):
                    reply = reply.replace("{" + slot + "}", val.strip())
                return s["name"], reply
        return None

    def list(self):
        return [{"name": s["name"], "trigger": s["trigger"], "reply": s["reply"]}
                for s in self.skills]


# natural-language skill definition from chat, e.g.:
#   skill: greet | when: greet {name} | reply: Hello {name}!
#   teach skill greet when "hi" say "hey!"
_DEF_PATTERNS = [
    re.compile(r"^\s*(?:add |teach |new )?skill[:\s]+(?P<name>[^|]+?)\s*\|\s*"
               r"(?:when|trigger)[:\s]+(?P<trigger>.+?)\s*\|\s*"
               r"(?:reply|say|then|answer)[:\s]+(?P<reply>.+)$", re.I | re.S),
]


def parse_skill_definition(text):
    """If the message defines a skill, return (name, trigger, reply); else None."""
    for rx in _DEF_PATTERNS:
        m = rx.match(text.strip())
        if m:
            return m.group("name").strip(), m.group("trigger").strip(), m.group("reply").strip()
    return None
