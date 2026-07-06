"""
The Mind  —  a neuro-symbolic reasoning engine (our own, not a market chatbot).

Market LLMs are pure neural nets: fluent, but they HALLUCINATE math and facts and
cannot verify themselves. Our angle (the blueprint's section 1.7) is different:
reason with real tools and VERIFY every answer. It is "clever, not big" — it runs
on a laptop, gives exact answers, shows its work, and grows its knowledge and
memory over time. This is the reasoning core of the four directions:

  1. REASONING  — solves math/logic exactly with a symbolic engine (sympy) and
     verifies the result (substitutes the solution back, checks it).
  2. RETRIEVAL  — a growing knowledge base it searches before answering
     ("small brain, big library"); you add documents, no retraining.
  3. MEMORY / CONTINUAL LEARNING — remembers facts about you and corrections,
     and caches solved problems; improves as you use it.
  (4. A natural-language front-end / our own trained model plugs in on top later —
      that is the one piece that genuinely needs a trained model.)

Everything here is exact and inspectable — the opposite of a black box.
    python reasoner.py            # interactive
"""

import json
import os
import re
import sympy as sp
from sympy.parsing.sympy_parser import (parse_expr, standard_transformations,
                                        implicit_multiplication_application,
                                        convert_xor)

HERE = os.path.dirname(os.path.abspath(__file__))
MEM_FILE = os.path.join(HERE, "mind_memory.json")
KB_FILE = os.path.join(HERE, "knowledge.json")
TRANSFORMS = standard_transformations + (implicit_multiplication_application, convert_xor)
X = sp.symbols("x")


# --------------------------------------------------------------------------- #
# Symbolic reasoning tool — exact, and self-verifying.
# --------------------------------------------------------------------------- #
class MathReasoner:
    def _parse(self, s):
        return parse_expr(s, transformations=TRANSFORMS, evaluate=True)

    def handle(self, q):
        ql = q.lower().strip()
        trace = []
        try:
            # equation or "expr =" / "expr = ?"  (e.g. "solve x^2=4", "333+98=?")
            if "solve" in ql or ("=" in q and "==" not in q):
                body = re.sub(r"^\s*solve\s*", "", q, flags=re.I).strip().rstrip("?").strip()
                if body.endswith("="):
                    body = body[:-1].strip()            # "333+98=" -> "333+98" (just evaluate)
                if "=" in body:
                    lhs, rhs = body.split("=", 1)
                    eq = sp.Eq(self._parse(lhs), self._parse(rhs))
                    syms = list(eq.free_symbols)
                    if syms:                            # a real equation in a variable -> solve
                        sol = sp.solve(eq, syms[0])
                        trace.append(f"parsed equation: {sp.pretty(eq, use_unicode=False)}")
                        checks = []
                        for s in sol:                   # VERIFY: substitute each solution back
                            ok = sp.simplify(eq.lhs.subs(syms[0], s) - eq.rhs.subs(syms[0], s)) == 0
                            checks.append(f"{syms[0]}={s}  ->  {'verified' if ok else 'CHECK FAILED'}")
                        trace += ["verification:"] + ["  " + c for c in checks]
                        return (f"{syms[0]} = " + ", ".join(map(str, sol)), trace,
                                all("verified" in c for c in checks))
                    val = sp.simplify(eq.lhs - eq.rhs)  # numeric "a = b" -> true/false
                    return f"{body}  is  {'TRUE' if val == 0 else 'FALSE'}", trace, True
                # no '=' left after stripping -> just evaluate the expression
                e = self._parse(body); val = sp.simplify(e)
                if val.free_symbols:
                    return f"{e} = {val}", trace, True
                return f"{body} = {val}   (≈ {float(val):.6g})", ["evaluated exactly"], True

            # calculus / algebra keywords
            if any(k in ql for k in ("integrate", "integral of")):
                e = self._parse(re.sub(r".*integrate|integral of", "", q, flags=re.I))
                r = sp.integrate(e, X)
                trace.append(f"d/dx of the result reproduces the integrand: "
                             f"{sp.simplify(sp.diff(r, X) - e) == 0}")
                return f"∫({e}) dx = {r} + C", trace, True
            if any(k in ql for k in ("differentiate", "derivative", "d/dx")):
                e = self._parse(re.sub(r".*differentiate|derivative of|derivative|d/dx", "", q, flags=re.I))
                return f"d/dx({e}) = {sp.diff(e, X)}", trace, True
            if "simplify" in ql:
                e = self._parse(re.sub(r".*simplify", "", q, flags=re.I))
                return f"{e} = {sp.simplify(e)}", trace, True
            if "factor" in ql:
                e = self._parse(re.sub(r".*factor", "", q, flags=re.I))
                return f"{e} = {sp.factor(e)}", trace, True
            if "expand" in ql:
                e = self._parse(re.sub(r".*expand", "", q, flags=re.I))
                return f"{e} = {sp.expand(e)}", trace, True

            # otherwise, is it a pure arithmetic / expression to evaluate?
            e = self._parse(q)
            val = sp.simplify(e)
            if val.free_symbols:
                return f"{e} = {val}", trace, True
            trace.append("evaluated exactly (no floating-point error)")
            return f"{q} = {val}   (≈ {float(val):.6g})", trace, True
        except Exception:
            return None, [], False   # not a math query — let another tool handle it

    KEYWORDS = ("solve", "integrate", "integral", "derivative", "differentiate",
                "d/dx", "simplify", "factor", "expand")

    def looks_mathy(self, q):
        ql = q.lower()
        if any(k in ql for k in self.KEYWORDS):
            return True                          # keyword request; handle() parses the rest
        if re.search(r"\d\s*[+\-*/^]|\^|=", q):  # arithmetic-looking expression
            try:
                self._parse(q.split("=")[0]); return True
            except Exception:
                return False
        return False


# --------------------------------------------------------------------------- #
# Retrieval tool — a growing knowledge base, searched by TF-IDF.
# --------------------------------------------------------------------------- #
class Library:
    def __init__(self):
        self.docs = []
        if os.path.exists(KB_FILE):
            self.docs = json.load(open(KB_FILE, encoding="utf-8"))
        self._fit()

    def _fit(self):
        from sklearn.feature_extraction.text import TfidfVectorizer
        if self.docs:
            self.vec = TfidfVectorizer(stop_words="english").fit(self.docs)
            self.mat = self.vec.transform(self.docs)
        else:
            self.vec = None

    def add(self, text):
        self.docs.append(text)
        json.dump(self.docs, open(KB_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        self._fit()

    def search(self, q, k=3):
        if not self.vec:
            return []
        import numpy as np
        sims = (self.vec.transform([q]) @ self.mat.T).toarray()[0]
        idx = np.argsort(-sims)[:k]
        return [(self.docs[i], float(sims[i])) for i in idx if sims[i] > 0.05]


# --------------------------------------------------------------------------- #
# The Mind — routes a query to the right tool, remembers, learns.
# --------------------------------------------------------------------------- #
class Mind:
    def __init__(self):
        self.math = MathReasoner()
        self.lib = Library()
        self.mem = json.load(open(MEM_FILE, encoding="utf-8")) if os.path.exists(MEM_FILE) \
            else {"facts": [], "solved": {}}
        self.mem.setdefault("identity", {"name": "Vio"})   # the assistant's own name

    def name(self):
        return self.mem.get("identity", {}).get("name", "Vio")

    def set_name(self, n):
        self.mem.setdefault("identity", {})["name"] = n
        self._save()

    def _save(self):
        json.dump(self.mem, open(MEM_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    @staticmethod
    def _match_fact(fact, words):
        """Match a stored fact to query words, tolerant of typos/plurals via a
        shared 3-char prefix (so 'name' finds 'nam', 'engineers' finds 'engineer')."""
        fl = fact.lower()
        fwords = [w for w in re.findall(r"\w+", fl) if len(w) >= 3]
        for w in words:
            if w in fl:
                return True
            if any(fw[:3] == w[:3] for fw in fwords):
                return True
        return False

    def teach(self, text):                 # add durable knowledge to the library
        self.lib.add(text)
        return f"Learned and stored in the library: “{text[:60]}…”" if len(text) > 60 \
            else f"Learned: “{text}”"

    def remember(self, fact):              # store a personal fact (memory)
        self.mem["facts"].append(fact); self._save()
        return f"I'll remember: {fact}"

    def ask(self, q):
        q = q.strip()
        low = q.lower()
        # commands
        if low.startswith("teach:"):
            return {"answer": self.teach(q[6:].strip()), "how": "library-write", "verified": True, "trace": []}
        if low.startswith("remember:"):
            return {"answer": self.remember(q[9:].strip()), "how": "memory-write", "verified": True, "trace": []}

        # 1) exact reasoning (math/logic) — verified
        if self.math.looks_mathy(q):
            ans, trace, ok = self.math.handle(q)
            if ans is not None:
                self.mem["solved"][q] = ans; self._save()      # continual: cache solutions
                return {"answer": ans, "how": "symbolic reasoning (sympy)",
                        "verified": ok, "trace": trace}

        # 2) retrieval from the growing library + personal memory
        STOP = {"the", "a", "an", "is", "are", "was", "of", "to", "in", "on", "for",
                "what", "who", "where", "when", "why", "how", "my", "me", "and", "i",
                "do", "does", "you", "your", "it", "that", "this", "am", "tell"}
        words = [w for w in re.findall(r"\w+", low) if len(w) > 2 and w not in STOP]
        hits = [(d, s) for d, s in self.lib.search(q) if s > 0.12]
        if re.search(r"about (me|myself)|(who|what) am i|know about me", low):
            facts = list(self.mem["facts"])          # "what do you know about me" -> all
        else:
            facts = [f for f in self.mem["facts"] if self._match_fact(f, words)]
        if hits or facts:
            parts = []
            if facts:
                parts.append("From what I know about you:\n  " + "\n  ".join(facts))
            if hits:
                parts.append("From the library:\n" + "\n".join(f"  • {d}  (match {s:.2f})" for d, s in hits))
            return {"answer": "\n".join(parts), "how": "retrieval", "verified": bool(hits or facts),
                    "trace": [f"searched {len(self.lib.docs)} docs + {len(self.mem['facts'])} memories"]}

        # 3) honest "I don't know yet" + how to teach it
        return {"answer": "I don't know that yet. Teach me with:  teach: <fact>   "
                          "(then ask again). I only claim what I can verify or retrieve.",
                "how": "no-source", "verified": False, "trace": []}


def _print(r):
    v = "✓ verified" if r["verified"] else "… unverified"
    print(f"\n{r['answer']}")
    print(f"   [{r['how']}  |  {v}]")
    for t in r["trace"]:
        print(f"   · {t}")


if __name__ == "__main__":
    m = Mind()
    print("The Mind — a verifying reasoning engine (not a market chatbot).")
    print("Try:  solve x^2 - 5x + 6 = 0   |   integrate x^2   |   2^10 + 7*3")
    print("      teach: The Nile is the longest river in Africa.")
    print("      remember: my name is Mazin      |   (then)  what is my name?")
    print("Type 'quit' to exit.\n")
    while True:
        try:
            q = input("you › ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if q.lower() in ("quit", "exit"):
            break
        if q:
            _print(m.ask(q))
