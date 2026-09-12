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

        # Show the REAL reading of the question, not a decorative "Understanding…".
        # The interpretation is what decides routing and what evidence is required, so
        # it has to be visible — a wrong answer is usually a wrong reading, and the user
        # can only catch that if they can see it.
        try:
            import brain
            _its = brain.read(question, brain.survey(self.mind).vocabulary)
            if len(_its) > 1:
                emit(f"🧭 I read this as {len(_its)} questions:")
                for _i, _it in enumerate(_its, 1):
                    emit(f"   {_i}. {_it.summary()}")
            else:
                emit(f"🧭 Understood: {_its[0].summary()}")
            _need = _its[0].requires
        except Exception:
            emit("🧭 Understanding your question…")
            _need = None

        # A question that requires the user's device configuration cannot be answered
        # from documentation, no matter how well it matches. Check the requirement
        # BEFORE searching, and say so plainly instead of serving manual prose.
        if _need == "config":
            try:
                import configparse
                _objs = configparse.parse_many(self.mind.lib.docs)
            except Exception:
                _objs = []
            emit(f"📂 That needs your device configuration — I have "
                 f"{len(_objs)} parsed config object(s).")

        # When the LLM reasoning cortex is available, IT is the "think it through" engine
        # — it understands the whole prompt and reasons (or answers grounded on retrieved
        # facts) in one coherent pass. The old lexical decompose+re-search loop below is
        # for the no-LLM case only; running it over a reasoning prompt is exactly what
        # produced wrong-domain fragments ("Scientist" → biology). So delegate.
        if getattr(self.mind, "llm", None) is not None and self.mind.llm.available:
            # A genuinely MULTI-PART question ("what is X and what is Y") must be answered
            # part by part — otherwise a single-topic agent (math/tools) answers only the
            # first clause. Solve each part through the full router, then combine.
            subs = _split_subquestions(question)
            if len(subs) > 1:
                emit(f"🧩 It has {len(subs)} parts — I'll answer each, then combine.")
                parts, verified = [], True
                for i, sub in enumerate(subs, 1):
                    emit(f"🧠 Part {i}: {sub}")
                    rr = self.mind.ask(sub)
                    parts.append(f"• {sub.strip().rstrip('?')} → {(rr.get('answer') or '').strip()}")
                    verified = verified and bool(rr.get("verified"))
                return {"answer": "\n".join(parts),
                        "how": "self-directed reasoning (%d parts)" % len(subs),
                        "verified": verified, "confidence": 0.9 if verified else 0.5,
                        "steps": steps}
            emit(f"🧠 Reasoning it through with my local model ({self.mind.llm.model})…")
            r = dict(self.mind.ask(question))
            r["steps"] = steps
            return r

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
                # a chain is only as sure as its weakest link
                "confidence": round(min(rr.get("confidence", 0.5) for _, rr in results), 2),
                "trace": [f"decomposed into {len(results)} parts and solved each"],
                "steps": steps}
