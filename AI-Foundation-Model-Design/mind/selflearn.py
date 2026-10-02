"""
selflearn — Vio's Learning Agent, Skill Registry, intent rules and failure review.

Implements the "understand intent → find the gap → learn → validate → reuse → improve"
cycle as working code rather than as a prompt. The point of each piece:

  LEARNING AGENT   Turns material (the user's message, the previous message, the
                   library, the web when allowed) into STRUCTURE — states and
                   transitions, definitions, rules, steps, exceptions — not a copy of
                   the sentences. "Draft → Sent → Accepted / ↘ Rejected" becomes a
                   state model that can answer "what comes after Sent?".
  VALIDATION       A skill is stored as learned only after it passes tests generated
                   from it: it must recognise when it applies, answer normal cases,
                   handle exceptions, refuse to invent states it was never taught, and
                   every element must be traceable to the source text. A skill that
                   fails is not called learned; the user is told what is missing.
  SKILL REGISTRY   Validated skills persist with the full record — name, purpose,
                   triggers, knowledge, inputs, processing, tools, expected output,
                   validation, limitations, examples, version, last updated — and are
                   used automatically whenever a later question matches. Re-teaching a
                   skill that contradicts the stored one is surfaced as a conflict
                   instead of being silently overwritten.
  INTENT RULES     "That's not what I meant" is a learning signal: the misread question
                   and the user's clarification are stored, and the next time the same
                   question arrives it is read the corrected way.
  FAILURE REVIEW   Unanswered questions, corrections and misunderstandings are logged
                   with what was missing; repeated failures are prioritised.

Deterministic throughout — no model call is needed to learn, validate or reuse.
"""
from __future__ import annotations

import json
import os
import re
import time

_ARROW = r"(?:→|->|=>|⟶|➔|➜|⇒)"
_ARROW_RE = re.compile(rf"\s*{_ARROW}\s*")
_BRANCH = re.compile(r"^(\s*)(?:↘|↓|↗|\\|└─*>?|├─*>?|\|->|\+->)\s*(.+)$")
# In prose, a STATE is a capitalised name ("Sent", "In-Review"). The source must be one;
# "A quote moves to Sent" names no source state, so it yields no edge rather than a
# nonsense one. Targets may be a list: "Sent can become Accepted or Rejected".
_CAP = r"[A-Z][\w/-]*"
_VERB_EDGE = re.compile(
    rf"\b({_CAP})\s+(?:can\s+|may\s+|will\s+|then\s+)?(?:move|moves|go|goes|"
    rf"transition|transitions|change|changes|become|becomes|progress|progresses|"
    rf"advance|advances|turn|turns)\s+(?:to\s+|into\s+)?"
    rf"({_CAP}(?:\s*(?:,|\bor\b|\band\b)\s*{_CAP})*)")
_FROM_TO = re.compile(rf"\bfrom\s+({_CAP})\s+to\s+({_CAP})")
_NOT_STATE = {"a", "an", "the", "it", "this", "that", "then", "once", "when", "if",
              "each", "every", "any", "all", "they", "we", "you", "i"}
_RULE = re.compile(r"\b(must|must not|should|should not|never|always|only|cannot|"
                   r"can't|required|requires|not allowed|is allowed|mandatory)\b", re.I)
_EXCEPT = re.compile(r"\b(unless|except|however|but only|exception)\b", re.I)
_STEP = re.compile(r"^\s*(?:\d+[.)]|[-*•])\s+(.+)$")
_DEFN = re.compile(r"^\s*([A-Za-z][\w /-]{0,40}?)\s*(?::|=|—|–|\s-\s|\s+(?:is|are|means|"
                   r"refers to|stands for)\s+)\s*(.{3,})$")
_STOP = {"the", "a", "an", "of", "to", "in", "on", "for", "and", "or", "is", "are",
         "this", "that", "these", "those", "it", "its", "my", "our", "your", "with",
         "about", "how", "what", "learn", "understand", "know", "states", "state"}


def _clean(s):
    return re.sub(r"\s+", " ", (s or "").strip().strip(".,;:!?\"'`*")).strip()


def _sentences(text):
    for part in re.split(r"(?<=[.!?])\s+|\n+", text or ""):
        p = part.strip()
        if p:
            yield p


# =========================================================================== #
# 1. EXTRACTION — concepts, rules, relationships, workflows, exceptions
# =========================================================================== #
def extract(text):
    """Pull the STRUCTURE out of material. Returns a knowledge dict."""
    transitions, states, definitions = [], [], {}
    rules, steps, exceptions = [], [], []

    def add_state(s):
        s = _clean(s)
        if s and s not in states:
            states.append(s)
        return s

    def add_edge(a, b):
        a, b = add_state(a), add_state(b)
        if a and b and a != b and (a, b) not in transitions:
            transitions.append((a, b))

    last_chain = []                          # [(node, start_col)], arrows [(col, src)]
    last_arrows = []
    for raw in (text or "").splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        m = _BRANCH.match(line)
        if m and last_chain:
            indent, rest = len(m.group(1)), m.group(2)
            nodes = [n for n in _ARROW_RE.split(rest) if _clean(n)]
            if not nodes:
                continue
            if indent == 0 or not last_arrows:
                src = last_arrows[-1][1] if last_arrows else last_chain[-1][0]
            else:                            # nearest arrow on the chain above
                src = min(last_arrows, key=lambda a: abs(a[0] - indent))[1]
            add_edge(src, nodes[0])
            for a, b in zip(nodes, nodes[1:]):
                add_edge(a, b)
            continue
        if re.search(_ARROW, line):
            pieces = _ARROW_RE.split(line)
            nodes = [_clean(p) for p in pieces]
            if len([n for n in nodes if n]) >= 2 and all(len(n.split()) <= 4 for n in nodes if n):
                # record columns so an aligned branch below can find its source
                last_chain, last_arrows, pos = [], [], 0
                for i, piece in enumerate(pieces):
                    idx = line.find(piece.strip(), pos) if piece.strip() else pos
                    last_chain.append((nodes[i], idx))
                    pos = idx + len(piece.strip())
                    if i < len(pieces) - 1:
                        am = re.compile(_ARROW).search(line, pos)
                        if am:
                            last_arrows.append((am.start(), nodes[i]))
                            pos = am.end()
                chain = [n for n in nodes if n]
                for a, b in zip(chain, chain[1:]):
                    add_edge(a, b)
                continue
        for s in _sentences(line):
            for a, targets in _VERB_EDGE.findall(s):
                if a.lower() in _NOT_STATE:
                    continue
                for b in re.split(r"\s*(?:,|\bor\b|\band\b)\s*", targets):
                    if b and b.lower() not in _NOT_STATE:
                        add_edge(a, b)
            for a, b in _FROM_TO.findall(s):
                if a.lower() not in _NOT_STATE and b.lower() not in _NOT_STATE:
                    add_edge(a, b)
            if _EXCEPT.search(s):
                exceptions.append(_clean(s))
            elif _RULE.search(s):
                rules.append(_clean(s))
        st = _STEP.match(line)
        if st and not re.search(_ARROW, line):
            steps.append(_clean(st.group(1)))
            continue
        if re.search(_ARROW, line):
            continue
        # definitions may sit anywhere in a paragraph, so test each sentence; a leading
        # article is not part of the term ("A Draft is …" defines "Draft")
        for s in _sentences(line):
            d = _DEFN.match(s)
            if not d or _RULE.search(s) or _VERB_EDGE.search(s):
                continue
            term = re.sub(r"^(?:a|an|the)\s+", "", _clean(d.group(1)), flags=re.I)
            meaning = _clean(d.group(2))
            if 1 <= len(term.split()) <= 5 and term.lower() not in _STOP | _NOT_STATE:
                definitions.setdefault(term, meaning)
    return {"states": states, "transitions": transitions, "definitions": definitions,
            "rules": list(dict.fromkeys(rules)), "steps": list(dict.fromkeys(steps)),
            "exceptions": list(dict.fromkeys(exceptions))}


def _empty(k):
    return not (k["transitions"] or k["definitions"] or k["rules"] or k["steps"])


# =========================================================================== #
# 2. THE SKILL — a reusable capability built from the knowledge
# =========================================================================== #
def _topic_words(name):
    return {w for w in re.findall(r"[a-z][a-z0-9-]+", (name or "").lower())
            if w not in _STOP and len(w) > 2}


def build_skill(name, knowledge, sources, examples):
    k = knowledge
    kinds = [x for x, has in (("state model", k["transitions"]),
                              ("definitions", k["definitions"]),
                              ("rules", k["rules"]), ("procedure", k["steps"])) if has]
    triggers = sorted(_topic_words(name) | {s.lower() for s in k["states"]}
                      | {t.lower() for t in k["definitions"]})
    return {
        "name": name,
        "purpose": f"Answer questions about {name} from the {', '.join(kinds)} I was taught.",
        "triggers": triggers,
        "knowledge": {**k, "transitions": [list(t) for t in k["transitions"]]},
        "inputs": "a question that names this topic, one of its states, or a defined term",
        "processing": [
            "recognise the question as belonging to this skill",
            "identify what is asked: next/previous state, a transition, a definition, "
            "a rule, the list of states, or the procedure",
            "answer only from the stored structure",
            "if a state or term was never taught, say so instead of guessing"],
        "tools": ["state-model reasoning", "definition lookup", "rule lookup"],
        "expected_output": "a direct answer naming the exact states, terms or rules",
        "validation": {},
        "limitations": [
            "knows only what the taught material states — it cannot tell whether that "
            "material is complete",
            "does not infer business rules that were not written down"],
        "examples": examples,
        "sources": sources,
        "version": 1,
        "last_updated": time.strftime("%Y-%m-%d %H:%M"),
    }


# --------------------------------------------------------------------------- #
# answering from a skill
# --------------------------------------------------------------------------- #
def _graph(skill):
    edges = [tuple(t) for t in skill["knowledge"]["transitions"]]
    out, inc = {}, {}
    for a, b in edges:
        out.setdefault(a, []).append(b)
        inc.setdefault(b, []).append(a)
    return out, inc


def _find_state(skill, text):
    """The taught state named in `text`, matched case-insensitively."""
    for s in sorted(skill["knowledge"]["states"], key=len, reverse=True):
        if re.search(rf"(?<![\w-]){re.escape(s)}(?![\w-])", text, re.I):
            return s
    return None


def _path(out, a, b):
    seen, queue = {a}, [[a]]
    while queue:
        p = queue.pop(0)
        for n in out.get(p[-1], []):
            if n == b:
                return p + [n]
            if n not in seen:
                seen.add(n)
                queue.append(p + [n])
    return None


def _join(items):
    items = list(items)
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " or " + items[-1]


def matches(skill, q):
    """Does this question belong to the skill? Needs the topic, or a taught state/term
    together with state/definition wording — so 'sent' in an unrelated sentence does
    not hijack the question."""
    low = (q or "").lower()
    words = set(re.findall(r"[a-z][a-z0-9-]+", low))
    if words & _topic_words(skill["name"]):
        return True
    k = skill["knowledge"]
    state = _find_state(skill, q) if k["states"] else None
    if state and re.search(r"\b(after|before|next|previous|from|to|into|go|move|become|"
                           r"transition|state|stage|status|final|initial|start|end|"
                           r"what is|what's|mean|reach)\b", low):
        return True
    term = next((t for t in k["definitions"]
                 if re.search(rf"\b{re.escape(t.lower())}\b", low)), None)
    return bool(term and re.search(r"\b(what is|what's|define|meaning|mean)\b", low))


def answer(skill, q):
    """Answer `q` from the skill's structure. Never invents a state or term."""
    k = skill["knowledge"]
    low = (q or "").lower()
    out, inc = _graph(skill)
    states = k["states"]
    finals = [s for s in states if s in inc and s not in out]
    starts = [s for s in states if s in out and s not in inc]

    # a capitalised name the question asks about, which was never taught
    asked = re.search(r"\b(?:after|before|from|is|to)\s+(?:the\s+)?([A-Z][\w-]+)", q or "")
    if asked and states and _find_state(skill, asked.group(1)) is None and \
            asked.group(1).lower() not in _topic_words(skill["name"]) and \
            asked.group(1).lower() not in {t.lower() for t in k["definitions"]} and \
            re.search(r"\b(after|before|next|previous|from|state|stage)\b", low):
        return (f"“{asked.group(1)}” is not one of the states I was taught for "
                f"{skill['name']} ({', '.join(states)}). I won't guess where it fits — "
                "teach me how it connects and I'll add it.")

    pair = re.search(r"\bfrom\s+(.+?)\s+(?:to|into)\s+(.+?)(?:\?|$)", q or "", re.I) or \
        re.search(r"\bcan\s+(?:an?\s+|the\s+)?(?:\w+\s+)?(.+?)\s+(?:go|move|become|"
                  r"transition|change|turn)\s+(?:to|into)\s+(.+?)(?:\?|$)", q or "", re.I)
    if pair and states:
        a, b = _find_state(skill, pair.group(1)), _find_state(skill, pair.group(2))
        if a and b:
            if b in out.get(a, []):
                return f"Yes — {a} can move directly to {b}."
            p = _path(out, a, b)
            if p:
                return (f"Not directly. {a} reaches {b} only through "
                        f"{' → '.join(p)}.")
            return (f"No — in {skill['name']} there is no way from {a} to {b}."
                    + (f" {a} is a final state." if a in finals else ""))

    if re.search(r"\b(final|end|terminal|last)\s+(states?|stages?)\b|\bwhere does it end\b",
                 low) and states:
        return f"The final states are {_join(finals) or '(none — every state leads on)'}."
    if re.search(r"\b(initial|start(?:ing)?|first)\s+(states?|stages?)\b|\bwhere does it start\b",
                 low) and states:
        return f"It starts at {_join(starts) or '(no single start state)'}."

    state = _find_state(skill, q) if states else None
    if state and re.search(r"\b(after|next|from|following|lead to|leads to|go to|"
                           r"move to|then)\b", low):
        nxt = out.get(state, [])
        if not nxt:
            return f"Nothing comes after {state} — it is a final state."
        return (f"After {state}, it can move to {_join(nxt)}."
                if len(nxt) > 1 else f"After {state} comes {nxt[0]}.")
    if state and re.search(r"\b(before|previous|precede|leads? into|comes? from)\b", low):
        prv = inc.get(state, [])
        if not prv:
            return f"Nothing comes before {state} — it is where the process starts."
        return f"{state} is reached from {_join(prv)}."

    if re.search(r"\b(what|which|list|show|all)\b.*\b(states|stages|statuses)\b", low) and states:
        return (f"{skill['name'].capitalize()} has {len(states)} states: "
                f"{', '.join(states)}. It starts at {_join(starts) or '?'} and ends at "
                f"{_join(finals) or '?'}.")

    term = next((t for t in sorted(k["definitions"], key=len, reverse=True)
                 if re.search(rf"\b{re.escape(t.lower())}\b", low)), None)
    if term:
        return f"{term}: {k['definitions'][term]}."
    if state:
        parts = [f"{state} is a state in {skill['name']}."]
        if inc.get(state):
            parts.append(f"It is reached from {_join(inc[state])}.")
        parts.append(f"From it, the next step is {_join(out[state])}." if out.get(state)
                     else "It is a final state.")
        return " ".join(parts)

    if re.search(r"\b(rule|rules|must|allowed|policy|condition)\b", low) and k["rules"]:
        return "The rules I was taught: " + " ".join(f"({i}) {r}." for i, r in
                                                     enumerate(k["rules"], 1))
    if re.search(r"\b(steps?|procedure|process|how do|workflow)\b", low) and k["steps"]:
        return "The steps: " + " ".join(f"{i}. {s}." for i, s in enumerate(k["steps"], 1))

    return summary(skill)


def summary(skill):
    k = skill["knowledge"]
    bits = []
    if k["transitions"]:
        bits.append("transitions " + "; ".join(f"{a} → {b}" for a, b in k["transitions"]))
    if k["definitions"]:
        bits.append(f"{len(k['definitions'])} definition(s)")
    if k["rules"]:
        bits.append(f"{len(k['rules'])} rule(s)")
    if k["steps"]:
        bits.append(f"{len(k['steps'])} step(s)")
    return f"For {skill['name']} I know " + "; ".join(bits) + "."


# =========================================================================== #
# 3. VALIDATION — a skill is learned only when it passes
# =========================================================================== #
def validate(skill, source_text):
    """Generate tests from the skill and run them. Returns {passed, total, failures}."""
    tests = []

    def t(name, ok):
        tests.append((name, bool(ok)))

    k = skill["knowledge"]
    out, inc = _graph(skill)
    src = (source_text or "").lower()

    # grounding: nothing in the skill may be absent from what it was learned from
    for s in k["states"]:
        t(f"state '{s}' appears in the source", s.lower() in src)
    for term in k["definitions"]:
        t(f"term '{term}' appears in the source", term.lower() in src)

    # recognition: it should apply to its own topic and not to unrelated questions
    if _topic_words(skill["name"]):
        t("recognises a question about its topic",
          matches(skill, f"tell me about {skill['name']}"))
    t("ignores an unrelated question",
      not matches(skill, "what is the capital of France?"))

    # normal cases
    for a, nxts in out.items():
        r = answer(skill, f"what comes after {a}?")
        t(f"after {a} → {', '.join(nxts)}", all(n in r for n in nxts))
    for b, prvs in inc.items():
        r = answer(skill, f"what comes before {b}?")
        t(f"before {b} → {', '.join(prvs)}", all(p in r for p in prvs))
    for term, meaning in list(k["definitions"].items())[:6]:
        t(f"defines {term}", meaning[:20].lower() in answer(skill, f"what is {term}?").lower())

    # exceptions: transitions that are NOT allowed must be refused
    for a, b in k["transitions"][:6]:
        if a not in out.get(b, []):
            r = answer(skill, f"can it go from {b} to {a}?")
            t(f"refuses the reverse move {b} → {a}", r.startswith(("No", "Not directly")))

    # unknown information: must not invent a state
    if k["states"]:
        r = answer(skill, "what comes after Zebraflux?")
        t("refuses to invent an unknown state", "not one of the states" in r)

    passed = sum(1 for _n, ok in tests if ok)
    return {"passed": passed, "total": len(tests),
            "failures": [n for n, ok in tests if not ok],
            "validated_at": time.strftime("%Y-%m-%d %H:%M")}


def conflicts(old, new):
    """Differences between two versions of a skill's state model and definitions."""
    o, n = old["knowledge"], new["knowledge"]
    ot, nt = {tuple(x) for x in o["transitions"]}, {tuple(x) for x in n["transitions"]}
    out = []
    for a, b in sorted(ot - nt):
        out.append(f"{a} → {b} was taught before but is not in the new material")
    for a, b in sorted(nt - ot):
        out.append(f"{a} → {b} is new")
    for term in set(o["definitions"]) & set(n["definitions"]):
        if o["definitions"][term] != n["definitions"][term]:
            out.append(f"'{term}' was defined differently before")
    return out


# =========================================================================== #
# 4. REGISTRY — validated skills, intent rules, failure log
# =========================================================================== #
class SkillRegistry:
    def __init__(self, data_dir):
        self.path = os.path.join(data_dir, "learned_skills.json")
        try:
            with open(self.path, encoding="utf-8") as f:
                self.skills = json.load(f)
        except (OSError, ValueError):
            self.skills = {}

    def _save(self):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.skills, f, ensure_ascii=False, indent=2)

    def get(self, name):
        return self.skills.get(name.lower())

    def put(self, skill):
        self.skills[skill["name"].lower()] = skill
        self._save()

    def match(self, q):
        """The best validated skill for a question, or None."""
        found = [s for s in self.skills.values()
                 if s.get("status") == "validated" and matches(s, q)]
        if not found:
            return None
        low = (q or "").lower()
        return max(found, key=lambda s: len(_topic_words(s["name"])
                                            & set(re.findall(r"[a-z][a-z0-9-]+", low))))

    def listing(self):
        if not self.skills:
            return "I haven't learned any skills yet. Teach me with  learn this:  followed " \
                   "by the material, or paste the material and then say  learn this."
        lines = [f"Skills I have learned ({len(self.skills)}):"]
        for s in self.skills.values():
            v = s.get("validation", {})
            lines.append(f"  • **{s['name']}** — v{s['version']}, {s['status']}, "
                         f"tests {v.get('passed', 0)}/{v.get('total', 0)}, "
                         f"updated {s['last_updated']}")
        return "\n".join(lines)


class IntentRules:
    """Wording that was misread, and what the user actually meant."""

    def __init__(self, data_dir):
        self.path = os.path.join(data_dir, "intent_rules.json")
        try:
            with open(self.path, encoding="utf-8") as f:
                self.rules = json.load(f)
        except (OSError, ValueError):
            self.rules = []

    @staticmethod
    def _key(q):
        return " ".join(w for w in re.findall(r"[a-z0-9]+", (q or "").lower())
                        if w not in _STOP)

    def add(self, misread, meant, reason=""):
        k = self._key(misread)
        self.rules = [r for r in self.rules if r["key"] != k]
        self.rules.append({"key": k, "said": misread.strip(), "meant": meant.strip(),
                           "reason": reason, "at": time.strftime("%Y-%m-%d %H:%M")})
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.rules, f, ensure_ascii=False, indent=2)

    def lookup(self, q):
        k = self._key(q)
        return next((r for r in self.rules if r["key"] and r["key"] == k), None)


class FailureLog:
    """What went wrong, why, and what would prevent it — for self-review."""

    KINDS = {
        "missing-knowledge": "learn it (learn this: …) or load sources (learn everything)",
        "need-config": "upload the device configuration",
        "no-model": "start the local model (ollama serve)",
        "misunderstood": "an intent rule now reads that wording correctly",
        "wrong-answer": "the correction is stored and served next time",
        "validation-failed": "provide clearer material for that skill",
    }

    def __init__(self, data_dir):
        self.path = os.path.join(data_dir, "failures.jsonl")

    def log(self, q, kind, detail=""):
        rec = {"at": time.strftime("%Y-%m-%d %H:%M"), "q": (q or "")[:300],
               "kind": kind, "detail": detail[:300]}
        try:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        except OSError:
            pass

    def read(self):
        try:
            with open(self.path, encoding="utf-8") as f:
                return [json.loads(ln) for ln in f if ln.strip()]
        except (OSError, ValueError):
            return []

    def review(self):
        recs = self.read()
        if not recs:
            return ("**Self-review** — no failures recorded. Nothing to improve from "
                    "yet; I review unanswered questions, corrections and "
                    "misunderstandings as they happen.")
        by_kind, by_topic = {}, {}
        for r in recs:
            by_kind[r["kind"]] = by_kind.get(r["kind"], 0) + 1
            key = IntentRules._key(r["q"])[:60]
            if key:
                by_topic.setdefault(key, []).append(r)
        lines = [f"**Self-review** — {len(recs)} failure(s) recorded.", ""]
        repeated = sorted(((k, v) for k, v in by_topic.items() if len(v) >= 2),
                          key=lambda kv: -len(kv[1]))
        if repeated:
            lines.append("**Repeated failures (fix these first):**")
            for _k, v in repeated[:6]:
                lines.append(f"  🔁 “{v[-1]['q'][:80]}” — failed {len(v)}× "
                             f"({v[-1]['kind']}) → {self.KINDS.get(v[-1]['kind'], '')}")
            lines.append("")
        lines.append("**By cause:**")
        for kind, n in sorted(by_kind.items(), key=lambda kv: -kv[1]):
            lines.append(f"  • {kind}: {n} → {self.KINDS.get(kind, '')}")
        lines.append("")
        lines.append("**Most recent:**")
        for r in recs[-5:][::-1]:
            lines.append(f"  · {r['at']} — {r['kind']}: “{r['q'][:70]}”")
        return "\n".join(lines)


# =========================================================================== #
# 5. INTENT PATTERNS — wording → intent → action
# =========================================================================== #
_LEARN_EXCLUDE = re.compile(r"^\s*(?:learn|study|read)\s+(?:from\s+)?(?:github|git|repo|"
                            r"everything|it all|all\b|essentials|sources|the\s+gaps|gaps)",
                            re.I)
_LEARN = re.compile(
    r"^\s*(?:(?:i\s+want\s+you\s+to|please|can\s+you|could\s+you|go\s+and)\s+)?"
    r"(learn|understand|study|master|memori[sz]e|remember|teach\s+yourself)"
    r"(?:\s+(this|that|it|these))?"
    r"(?:\s+(?:for\s+next\s+time|for\s+later|for\s+the\s+future|permanently))?"
    r"(?:\s+(?:about|on))?"
    r"\s*[:\-]?\s*(.*)$", re.I | re.S)


def learn_request(q):
    """(topic, material) when the user asks Vio to acquire a capability, else None.

    "help me understand X" / "I don't understand" are the user wanting to learn —
    not a request for Vio to learn — and are left alone, as are the existing
    learn-from-github / learn everything / learn essentials commands."""
    text = (q or "").strip()
    low = text.lower()
    if re.match(r"^\s*(?:help\s+me|i\s+don'?t|do\s+you|i\s+can'?t|did\s+you)\b", low) or \
            _LEARN_EXCLUDE.match(text) or re.match(r"^\s*remember\s*:", low):
        return None
    m = _LEARN.match(text)
    if not m:
        return None
    rest = (m.group(3) or "").strip()
    first, _, body = rest.partition("\n")
    if body.strip():                         # "learn quotation states:\n<material>"
        return _clean(first) or None, body.strip()
    if re.search(_ARROW, rest) or len(rest.split()) > 12:
        return None, rest                    # the material itself, inline
    return _clean(rest) or None, ""


def purpose(q):
    """Map wording to the intent class the spec's intent table defines."""
    low = (q or "").strip().lower()
    if re.search(r"\b(that'?s\s+not\s+what\s+i\s+(?:meant|asked|mean)|not\s+what\s+i\s+"
                 r"(?:meant|asked)|you\s+(?:don'?t|do\s+not|didn'?t)\s+understand(?:\s+me)?|"
                 r"you\s+misunderstood|wrong\s+question)\b", low):
        return "re-evaluate"
    if re.search(r"^\s*(?:do\s+it\s+yourself|figure\s+it\s+out|find\s+out\s+yourself|"
                 r"work\s+it\s+out\s+yourself)\b", low):
        return "autonomous"
    if re.search(r"^\s*how\s+(?:can|could|would|will)\s+you\s+(?:learn|do)\s+(?:this|that|it)\b",
                 low) and not re.search(r"\bexplain\b", low):
        return "demonstrate"
    if re.search(r"^\s*(?:self[-\s]?review|review\s+(?:your|my)?\s*(?:mistakes|failures)|"
                 r"what\s+(?:have\s+you\s+)?learn(?:ed|t)\s+from\s+(?:your\s+)?mistakes|"
                 r"what\s+(?:did\s+you\s+|have\s+you\s+)?fail(?:ed)?(?:\s+at)?)\b", low):
        return "self-review"
    if re.search(r"^\s*(?:learned\s+skills|what\s+skills\s+(?:have\s+you|did\s+you)\s+"
                 r"learn(?:ed|t)?|list\s+(?:learned|your)\s+skills|skill\s+registry)\b", low):
        return "list-skills"
    if learn_request(q):
        return "learn"
    return None


def learning_response(skill, current, missing, action, validation, future):
    """The concise structured reply the spec's §15 describes."""
    return "\n".join([
        "I understand the capability you want.", "",
        f"**Skill:** {skill}", "",
        f"**Current knowledge:** {current}", "",
        f"**Missing capability:** {missing}", "",
        f"**Learning action:** {action}", "",
        f"**Validation:** {validation}", "",
        f"**Future behavior:** {future}"])
