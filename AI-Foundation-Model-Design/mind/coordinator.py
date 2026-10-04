"""
coordinator — the one agent every other agent talks through.

Agents never call each other directly. Every question goes to the Coordinator, which:

  1. BRIEFS — before any agent answers, it asks the agents that HOLD data for what
     they know about the question, and puts it on a shared blackboard:
         knowledge  → library passages (taught documents, study notes, web pages)
         memory     → facts the user told Vio
         data       → rows from uploaded tables (Excel, CSV, tables in documents)
         devices    → serial / model / firmware of the user's devices
         config     → what the loaded device configuration contains
  2. FILLS GAPS — if nobody holds enough about a knowledge question, it sends the
     research agent to the internet (only when the user has switched web ON), and the
     pages it reads are LEARNED into the shared library — every agent gains them.
     Nothing private is sent: IP addresses, host names, serials and e-mail addresses
     are removed from the search query, and a question about the user's own systems
     is never searched for.
  3. DISPATCHES — the best-fitting agent answers WITH the blackboard, so the network
     engineer sees the table row the data agent found and the page research fetched.
     An agent that needs more can ask the coordinator mid-task (board.request), which
     routes the request to the agent that serves it.
  4. RECORDS — every message between agents is on the board, and the last
     conversation is shown on the dashboard ("who talked to whom, about what").
"""
from __future__ import annotations

import re
import time

# what each need is served by — agents ask for a NEED, the coordinator picks the agent
SERVES = {
    "knowledge": "knowledge",
    "memory": "memory",
    "data": "data",
    "devices": "devices",
    "config": "config",
    "web": "research",
}

_PRIVATE = [
    (re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}(?:/\d{1,2})?\b"), ""),            # IPs/CIDRs
    (re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b"), ""),                           # e-mails
    (re.compile(r"\bF[GW][A-Z0-9]{3,6}[A-Z]{2}\d{6,}\b"), ""),                 # serials
    (re.compile(r"\b[A-Z][A-Z0-9]*(?:[-_][A-Z0-9]+)+\b"), ""),                 # HQ-FGT-01
]


def scrub(q):
    """The question with private identifiers removed, for a public search engine."""
    out = q or ""
    for rx, rep in _PRIVATE:
        out = rx.sub(rep, out)
    out = re.sub(r"\b(my|our|mine|we)\b", "", out, flags=re.I)
    return re.sub(r"\s{2,}", " ", out).strip(" ?.,")


_STOP = set("""the and for with from that this what which when where why how does do did
are was were is be been can could should would will your our my mine their there about into
than then them they have has had not but all any each more most some such only very also
difference between versus compare explain describe tell show give please using use used
""".split())


def content_words(text):
    """Words that carry the meaning of a question (no stop words, no short words)."""
    return {w for w in re.findall(r"[a-z0-9][a-z0-9-]{2,}", (text or "").lower())
            if w not in _STOP and len(w) >= 4}


class Board:
    """The shared blackboard for one question: what each agent contributed and every
    request that passed through the coordinator."""

    def __init__(self, q, coordinator):
        self.q = q
        self.coord = coordinator
        self.items = {}          # need → content
        self.log = []            # [(from, to, what)]
        self.t0 = time.time()

    def post(self, sender, need, content, summary=""):
        if content:
            self.items[need] = content
            self.log.append((sender, "coordinator", summary or f"{need}: posted"))

    def get(self, need):
        return self.items.get(need)

    def request(self, sender, need, q=None):
        """An agent asks for something it doesn't have. The coordinator routes it."""
        self.log.append((sender, "coordinator", f"needs {need}"))
        if need in self.items:
            self.log.append(("coordinator", sender, f"{need}: already on the board"))
            return self.items[need]
        got = self.coord.fetch(need, q or self.q, self)
        self.log.append(("coordinator", sender, f"{need}: "
                         + ("delivered" if got else "nobody holds it")))
        return got

    def passages(self):
        return [p for p in (self.items.get("knowledge") or []) if p]

    def brief_text(self):
        """Everything on the board, as facts an LLM-backed agent can ground on."""
        parts = []
        for need, label in (("memory", "What the user told me"),
                            ("devices", "The user's devices"),
                            ("data", "Rows from the user's tables"),
                            ("config", "The loaded configuration")):
            v = self.items.get(need)
            if v:
                parts.append(f"{label}:\n" + (v if isinstance(v, str)
                                              else "\n".join(f"- {x}" for x in v)))
        return "\n\n".join(parts)

    def transcript(self):
        return [f"{a} → {b}: {w}" for a, b, w in self.log]


class Coordinator:
    """The hub. Holds no knowledge itself — it knows which agent holds what."""

    name = "coordinator"
    GAP = 0.18            # top library score below this = the library doesn't cover it

    def __init__(self, mind):
        self.mind = mind
        self.last = None              # the last board, for the dashboard

    # ---------------------------------------------------------------- serving --
    def fetch(self, need, q, board):
        m = self.mind
        try:
            if need == "knowledge":
                hits = m.lib.search(q, k=6)
                board.items["_top"] = hits[0][1] if hits else 0.0
                return [d for d, s in hits if s >= 0.08] or None
            if need == "memory":
                words = content_words(q)
                facts = [f for f in (m.mem or {}).get("facts", [])
                         if len(words & content_words(f)) >= min(2, len(words))]
                return facts[:8] or None
            if need == "data":
                tbl, ans = m._table_answer(q)
                return [f"{ans}  (table “{tbl.name}”)"] if ans else None
            if need == "devices":
                import devicefacts
                inv = devicefacts.inventory(m)
                devs = devicefacts.match_devices(q, inv)
                if not devs:
                    return None
                return [f"{d}: " + ", ".join(f"{devicefacts._LABEL.get(k, k)} {v[0]}"
                                             for k, v in inv[d].items()
                                             if k in devicefacts._LABEL) for d in devs]
            if need == "config":
                import brain
                ev = brain.survey(m)
                if not ev.config_kinds:
                    return None
                top = sorted(ev.config_kinds.items(), key=lambda kv: -kv[1])[:6]
                return (f"{sum(ev.config_kinds.values())} objects: "
                        + ", ".join(f"{n} {k}" for k, n in top))
            if need == "web":
                return self.research(q, board)
        except Exception as e:
            board.log.append(("coordinator", need, f"failed: {type(e).__name__}"))
        return None

    def research(self, q, board):
        """Send the research agent out for a knowledge gap — only with web ON, never
        with private identifiers, never about the user's own systems."""
        import websearch
        if not websearch.net_enabled():
            board.items["_web"] = "off"
            return None
        query = scrub(q)
        if len(query.split()) < 2:
            board.items["_web"] = "private"
            return None
        board.log.append(("coordinator", "research", f"search the web: “{query}”"))
        r = self.mind.research(query, propose_skill=False)
        if r and r.get("ok", True) and not str(r.get("how", "")).endswith("(disabled)"):
            board.items["_web"] = "fetched"
            board.log.append(("research", "knowledge",
                              "learned the pages into the shared library"))
            hits = self.mind.lib.search(q, k=6)
            return [d for d, s in hits if s >= 0.08] or None
        board.items["_web"] = "nothing"
        return None

    # --------------------------------------------------------------- briefing --
    def brief(self, q, ctx):
        """Ask every data-holding agent what it knows, before anyone answers."""
        board = Board(q, self)
        ctx["board"] = board
        for need in ("memory", "devices", "data", "knowledge", "config"):
            got = self.fetch(need, q, board)
            if got:
                n = len(got) if isinstance(got, list) else 1
                board.post(SERVES[need], need, got, f"{need}: {n} item(s)")
        if self._is_gap(q, board):
            board.log.append(("knowledge", "coordinator",
                              "the library doesn't cover this well"))
            got = self.fetch("web", q, board)
            if got:
                board.post("research", "knowledge", got,
                           f"knowledge: {len(got)} passage(s) after web research")
        self.last = board
        return board

    def _is_gap(self, q, board):
        """A knowledge question nobody holds enough about. Questions about the user's
        own systems (devices, tables, config, memory hits) are never web-searched."""
        if board.get("devices") or board.get("data") or board.get("memory"):
            return False
        try:
            import brain
            u = brain.understand(q)
            if u.requires not in (brain.KNOWLEDGE, brain.REASONING):
                return False
            if u.host:
                return False
        except Exception:
            pass
        low = (q or "").lower().strip()
        if len(re.findall(r"[a-z]{3,}", low)) < 3 or re.match(r"^[\w-]+\s*:", low):
            return False                     # chit-chat, or a command
        if not re.search(r"\?|^(what|how|why|which|when|where|explain|compare|describe|"
                         r"difference|best|should|is|are|can|does|do)\b", low):
            return False
        if float(board.items.get("_top") or 0.0) < self.GAP:
            return True
        # covered = the question's own key terms appear in what the library returned.
        # A generic passage on the same topic is not an answer to a specific question,
        # so beside the word-overlap ratio there is a DISTINCTIVE-TERM GATE: the two
        # rarest content words of the question (by library IDF; out-of-vocabulary
        # counts as maximally rare) must actually appear in what was retrieved.
        # Generic passages share "network"/"virtual"/"firewall" with an Azure Virtual
        # WAN question without covering it — which used to hide the gap and skip the
        # web fill entirely.
        want = content_words(q)
        have = content_words(" ".join(board.passages()[:4]))
        stem = lambda w: w[:6]                                     # noqa: E731
        stems = {stem(h) for h in have}
        hit = {w for w in want if w in have or stem(w) in stems}
        if not want:
            return False
        vec = getattr(self.mind.lib, "vec", None)
        vocab = getattr(vec, "vocabulary_", {}) or {}
        idf = getattr(vec, "idf_", None)

        def _rarity(w):
            j = vocab.get(stem(w))
            return 1e9 if (j is None or idf is None) else float(idf[j])

        rarest = sorted(want, key=_rarity, reverse=True)[:2]
        covered = (len(hit) / len(want) >= 0.6 and
                   all(w in have or stem(w) in stems for w in rarest))
        return not covered

    # --------------------------------------------------------------- reporting --
    def footer(self, board):
        """One line for the answer: who contributed, and whether the web was used."""
        if board is None:
            return ""
        who = sorted({a for a, b, w in board.log
                      if b == "coordinator" and a != "coordinator"
                      and ("item(s)" in w or "passage(s)" in w)})
        web = board.items.get("_web")
        note = ""
        if web == "off":
            note = (" · 🌐 the library doesn't cover this well and web research is OFF "
                    "— say “web on” to let my research agent look it up")
        elif web == "fetched":
            note = " · 🌐 researched on the web and learned it for every agent"
        elif web == "private":
            note = " · 🌐 not searched: the question is about your own systems"
        return ("🤝 " + ", ".join(who) + " shared what they hold" if who else "") + note

    def report(self):
        b = self.last
        if b is None:
            return {"question": "", "messages": [], "seconds": 0}
        return {"question": b.q, "messages": b.transcript(),
                "seconds": round(time.time() - b.t0, 1),
                "web": b.items.get("_web", "")}
