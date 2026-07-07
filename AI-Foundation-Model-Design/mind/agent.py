"""
agent  —  Vio's self-directed "think it through" loop.

The plain reasoner does ONE pass: it routes a question to a single tool. This layer
lets Vio work on a harder question the way a person does — break it into parts, try
each part with its own tools and library, and if a part comes back empty, RE-SEARCH
with reformulated keywords before giving up — then compose the pieces into one answer.

It is still 100% grounded and honest: every sub-answer comes from the same verified
tools / retrieval as normal; the agent only ORCHESTRATES them (decompose, retry,
combine). It never invents facts. It emits its steps as it goes so the UI can show
Vio thinking in real time.

    steps = []
    agent.solve("what is 15% of 200 and who wrote Hamlet?", on_step=steps.append)

No eval/exec — it composes calls to Mind's existing tools only.
"""

import re


_QWORD = re.compile(r"\b(what|who|whom|whose|where|when|why|how|which|solve|"
                    r"calculate|convert|define|is|are|does)\b", re.I)


def _answerable(part):
    """A piece is worth splitting off only if it can stand on its own —
    it asks something (question word) or contains a number/expression."""
    return bool(_QWORD.search(part) or re.search(r"\d", part))


def _split_subquestions(q):
    """Break a compound request into parts a person would answer separately —
    but keep equation systems ('x+y=10 and x-y=2') intact for the system solver."""
    q = q.strip()
    if q.count("=") >= 2:                       # looks like a system of equations
        return [q]
    # explicit multi-question: split on '?' keeping each question
    if q.count("?") >= 2:
        parts = [p.strip() + "?" for p in q.split("?") if p.strip()]
        if len(parts) >= 2:
            return parts
    # connective splits: ';', 'then', ', and', or plain ' and '
    parts = re.split(r"\s*;\s*|\s+then\s+|\s*,\s+and\s+|\s+and\s+also\s+|\s+and\s+",
                     q, flags=re.I)
    parts = [p.strip(" ,.;") for p in parts if len(p.strip(" ,.;")) > 2]
    # only treat as multi-part if EVERY piece is independently answerable
    if 2 <= len(parts) <= 5 and all(_answerable(p) and len(p.split()) >= 2 for p in parts):
        return parts
    return [q]


_STOP = {"the", "a", "an", "is", "are", "was", "were", "of", "to", "in", "on", "for",
         "what", "who", "where", "when", "why", "how", "which", "my", "me", "and",
         "i", "do", "does", "you", "your", "it", "that", "this", "am", "tell", "about",
         "can", "could", "would", "please", "give", "show"}


def _keywords(q):
    return [w for w in re.findall(r"[a-zA-Z؀-ۿ]+", q.lower())
            if len(w) > 2 and w not in _STOP]


class SolveAgent:
    def __init__(self, mind):
        self.mind = mind

    def solve(self, question, on_step=None):
        """Run the multi-step loop. Returns the same dict shape as Mind.ask,
        plus a 'steps' list. on_step(text) is called live for streaming."""
        steps = []

        def emit(text):
            steps.append(text)
            if on_step:
                try:
                    on_step(text)
                except Exception:
                    pass

        emit("🧭 Understanding your question…")
        subs = _split_subquestions(question)
        if len(subs) > 1:
            emit(f"🧩 It has {len(subs)} parts — I'll take them one at a time.")

        results = []
        all_verified = True
        for i, sub in enumerate(subs, 1):
            label = f"Part {i}: “{sub}”" if len(subs) > 1 else f"“{sub}”"
            emit(f"🔎 {label} — checking my tools and library…")
            r = self.mind.ask(sub)

            # self-directed retry: unknown or weak -> reformulate and re-search
            if r["how"] in ("no-source",) or (not r["verified"] and r["how"] == "generation"):
                kws = _keywords(sub)
                if kws:
                    emit(f"🤔 Nothing direct. Re-searching for: {', '.join(kws[:6])}")
                    hits = self.mind.lib.search(" ".join(kws), k=4)
                    hits = [(d, s) for d, s in hits if s > 0.06]
                    if hits:
                        syn = self.mind.thinker.synthesize(sub, [d for d, _ in hits],
                                                           self.mind.mem.get("facts", []))
                        if syn:
                            emit(f"💡 Found {len(hits)} related source(s) — piecing it together.")
                            r = {"answer": syn, "how": "self-directed research (synthesis)",
                                 "verified": True, "trace": [f"re-searched, used {len(hits)} sources"]}
                        else:
                            emit("📖 Found related text; showing the closest passages.")
                            r = {"answer": "\n".join(f"  • {d}" for d, _ in hits[:3]),
                                 "how": "self-directed research (retrieval)",
                                 "verified": True, "trace": []}
                    else:
                        emit("🚧 I couldn't find anything I can stand behind for this part.")
            else:
                emit(f"✓ Got it via {r['how']}.")

            all_verified = all_verified and r["verified"]
            results.append((sub, r))

        emit("🧠 Composing the final answer…")

        if len(results) == 1:
            final = dict(results[0][1])
            final["steps"] = steps
            return final

        # combine multiple parts into one grounded answer
        lines = []
        for sub, r in results:
            head = sub if sub.endswith("?") else sub
            lines.append(f"▸ {head}\n{r['answer']}")
        return {"answer": "\n\n".join(lines),
                "how": f"self-directed reasoning ({len(results)} parts)",
                "verified": all_verified,
                "trace": [f"decomposed into {len(results)} parts and solved each"],
                "steps": steps}
