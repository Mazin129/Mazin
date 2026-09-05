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
from think import Thinker
from skills import SkillBook, parse_skill_definition
from memory.episodic import EpisodicMemory
from memory.working import WorkingMemory
from memory.semantic import SemanticMemory
from memory.procedural import ProceduralMemory
from memory.graph import KnowledgeGraph
from kernel.workspace import Workspace
from kernel.executive import Executive
from cognition.reasoning import Reasoning
from cognition.planning import Planner, is_plan_request
from cognition.world_model import WorldModel
from cognition.consolidation import Consolidator
from cognition.learning import LearningEngine
from cognition.curiosity import Curiosity
from cognition.calibration import Calibration
from specialists import Cortex

HERE = os.path.dirname(os.path.abspath(__file__))
# All of Vio's stores live in HERE by default; set VIO_DATA_DIR to relocate them
# (data portability, and lets a test run against a throwaway dir — see capability_test.py).
DATA_DIR = os.environ.get("VIO_DATA_DIR", HERE)
if DATA_DIR != HERE:
    os.makedirs(DATA_DIR, exist_ok=True)
MEM_FILE = os.path.join(DATA_DIR, "mind_memory.json")
KB_FILE = os.path.join(DATA_DIR, "knowledge.json")
TRANSFORMS = standard_transformations + (implicit_multiplication_application, convert_xor)
X = sp.symbols("x")


# --------------------------------------------------------------------------- #
# Symbolic reasoning tool — exact, and self-verifying.
# --------------------------------------------------------------------------- #
# SECURITY: sympy.parse_expr uses eval() internally, so unsanitized input is a
# remote-code-execution risk (e.g. "1+eval(...)"). We whitelist strictly BEFORE
# parsing: no quotes/underscores/brackets, and every multi-letter name must be a
# known maths function. This turns the parser into a maths-only surface.
_MATH_NAMES = {"pi", "sqrt", "cbrt", "root", "sin", "cos", "tan", "cot", "sec", "csc",
               "asin", "acos", "atan", "atan2", "sinh", "cosh", "tanh", "log", "ln",
               "exp", "abs", "sign", "floor", "ceiling", "ceil", "factorial", "gamma",
               "deg", "rad", "re", "im", "conjugate", "gcd", "lcm", "mod"}
_BAD_CHARS = re.compile(r"""["'\[\]{}\\;:@#$%&`~|<>!?_]""")


class MathReasoner:
    def _parse(self, s):
        if _BAD_CHARS.search(s):
            raise ValueError("unsafe characters in expression")
        for name in re.findall(r"[A-Za-z]{2,}", s):      # multi-letter names must be maths
            if name.lower() not in _MATH_NAMES:
                raise ValueError(f"unknown name in expression: {name}")
        return parse_expr(s, transformations=TRANSFORMS, evaluate=True)

    def handle(self, q):
        ql = q.lower().strip()
        trace = []
        try:
            # inequality: "solve x^2 - 4 > 0", "x >= 5"
            if re.search(r"<=|>=|<|>", q):
                body = re.sub(r"^\s*solve\s*", "", q, flags=re.I).strip().rstrip("?").strip()
                mm = re.search(r"^(.*?)(<=|>=|<|>)(.*)$", body)
                lhs, rhs = self._parse(mm.group(1)), self._parse(mm.group(3))
                rel = {"<": sp.Lt, "<=": sp.Le, ">": sp.Gt, ">=": sp.Ge}[mm.group(2)]
                syms = list((lhs - rhs).free_symbols)
                if syms:
                    sol = sp.solve_univariate_inequality(rel(lhs, rhs), syms[0], relational=True)
                    return f"{sol}", ["solved inequality"], True
                return f"{body} is {'TRUE' if bool(rel(lhs, rhs)) else 'FALSE'}", trace, True
            # equation / "solve … for x" / "expr =" / "expr = ?"
            if "solve" in ql or ("=" in q and "==" not in q):
                body = re.sub(r"^\s*solve\s*", "", q, flags=re.I).strip().rstrip("?").strip()
                target = None                           # "solve A = pi*r^2 for r"
                mfor = re.search(r"\s+for\s+([a-zA-Z])\s*$", body)
                if mfor:
                    target = sp.Symbol(mfor.group(1)); body = body[:mfor.start()].strip()
                if body.endswith("="):
                    body = body[:-1].strip()            # "333+98=" -> "333+98" (just evaluate)
                if "=" in body:
                    lhs, rhs = body.split("=", 1)
                    eq = sp.Eq(self._parse(lhs), self._parse(rhs))
                    syms = list(eq.free_symbols)
                    if syms:                            # a real equation in a variable -> solve
                        var = target if (target is not None and target in eq.free_symbols) else syms[0]
                        sol = sp.solve(eq, var)
                        trace.append(f"parsed equation: {sp.pretty(eq, use_unicode=False)}")
                        checks = []
                        for s in sol:                   # VERIFY: substitute each solution back
                            ok = sp.simplify(eq.lhs.subs(var, s) - eq.rhs.subs(var, s)) == 0
                            checks.append(f"{var}={s}  ->  {'verified' if ok else 'CHECK FAILED'}")
                        trace += ["verification:"] + ["  " + c for c in checks]
                        return (f"{var} = " + ", ".join(map(str, sol)), trace,
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
        if re.search(r"\d\s*[+\-*/^]|\^|=|[<>]", q):  # arithmetic/inequality-looking
            try:
                self._parse(q.split("=")[0]); return True
            except Exception:
                return False
        return False


# --------------------------------------------------------------------------- #
# Everyday exact tools: percentages, statistics, unit conversions.
# --------------------------------------------------------------------------- #
def _fmt(v):
    return f"{v:g}" if isinstance(v, float) else str(v)


def _stem(w):
    """Conservative prefix fold so word forms match: powered/powers/powering → 'power',
    overfit/overfitting → 'overfi'. Words of 5 chars or fewer are left as-is (ram, tcp,
    vlan, ospf), so it never over-collapses short, distinctive terms."""
    return w[:5] if len(w) > 5 else w


def _stem_analyzer(text):
    """Tokenize → drop English stop words → prefix-stem. Used by the TF-IDF vectorizer
    so retrieval matches across word forms on both documents and queries."""
    from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS
    return [_stem(w) for w in re.findall(r"[a-z0-9؀-ۿ]+", text.lower())
            if len(w) > 1 and w not in ENGLISH_STOP_WORDS]


def try_percent(q):
    ql = q.lower()
    m = re.search(r"(-?\d+\.?\d*)\s*%\s*(?:of|من)\s*(-?\d+\.?\d*)", ql)
    if m:
        a, b = float(m[1]), float(m[2]); return f"{m[1]}% of {m[2]} = {_fmt(a/100*b)}"
    m = re.search(r"what\s*percent(?:age)?\s*(?:is)?\s*(-?\d+\.?\d*)\s*of\s*(-?\d+\.?\d*)", ql)
    if m:
        a, b = float(m[1]), float(m[2]); return f"{m[1]} is {_fmt(a/b*100)}% of {m[2]}"
    m = re.search(r"(increase|raise|decrease|reduce)\s*(-?\d+\.?\d*)\s*by\s*(-?\d+\.?\d*)\s*%", ql)
    if m:
        base, p = float(m[2]), float(m[3])
        r = base * (1 + p/100) if m[1] in ("increase", "raise") else base * (1 - p/100)
        return f"{m[2]} {m[1]}d by {m[3]}% = {_fmt(r)}"
    m = re.search(r"percent(?:age)?\s+change\s+from\s+(-?\d+\.?\d*)\s+to\s+(-?\d+\.?\d*)", ql)
    if m:
        a, b = float(m[1]), float(m[2]); ch = (b - a) / a * 100
        return f"change from {m[1]} to {m[2]} = {'+' if ch >= 0 else ''}{_fmt(ch)}%"
    return None


def try_stats(q):
    import statistics as st
    m = re.search(r"\b(mean|average|median|sum|total|max|maximum|min|minimum|std|"
                  r"standard deviation|variance|range|count)\b[^0-9\-]*(.+)", q.lower())
    if not m:
        return None
    xs = [float(n) for n in re.findall(r"-?\d+\.?\d*", m[2])]
    if len(xs) < 1:
        return None
    fns = {"mean": st.mean, "average": st.mean, "median": st.median, "sum": sum,
           "total": sum, "max": max, "maximum": max, "min": min, "minimum": min,
           "count": len, "std": st.pstdev, "standard deviation": st.pstdev,
           "variance": st.pvariance, "range": lambda x: max(x) - min(x)}
    return f"{m[1]} of {len(xs)} values = {_fmt(fns[m[1]](xs))}"


_LEN = {"m": 1, "meter": 1, "meters": 1, "km": 1000, "cm": .01, "mm": .001, "mile": 1609.34,
        "miles": 1609.34, "mi": 1609.34, "foot": .3048, "feet": .3048, "ft": .3048,
        "inch": .0254, "inches": .0254, "yard": .9144, "yd": .9144}
_MASS = {"kg": 1, "g": .001, "gram": .001, "grams": .001, "mg": 1e-6, "lb": .453592,
         "pound": .453592, "pounds": .453592, "oz": .0283495, "ton": 1000, "tonne": 1000}
_TIME = {"s": 1, "sec": 1, "second": 1, "seconds": 1, "min": 60, "minute": 60, "minutes": 60,
         "hour": 3600, "hours": 3600, "hr": 3600, "day": 86400, "days": 86400, "week": 604800}


_DATA = {"b": 1, "byte": 1, "bytes": 1, "kb": 1e3, "mb": 1e6, "gb": 1e9, "tb": 1e12,
         "kib": 1024, "mib": 1024**2, "gib": 1024**3, "bit": 0.125, "bits": 0.125}
_AREA = {"sqm": 1, "m2": 1, "sqkm": 1e6, "km2": 1e6, "sqft": .092903, "sqyd": .836127,
         "acre": 4046.86, "acres": 4046.86, "hectare": 10000, "hectares": 10000, "ha": 10000}


def try_units(q):
    m = re.search(r"(-?\d+\.?\d*)\s*([a-z°0-9]+)\s*(?:to|in|into|=)\s*([a-z°0-9]+)", q.lower())
    if not m:
        return None
    val, u1, u2 = float(m[1]), m[2].strip("°"), m[3].strip("°")
    for tbl in (_LEN, _MASS, _TIME, _DATA, _AREA):
        if u1 in tbl and u2 in tbl:
            return f"{m[1]} {u1} = {_fmt(val*tbl[u1]/tbl[u2])} {u2}"
    temp = {"c", "celsius", "f", "fahrenheit", "k", "kelvin"}
    if u1 in temp and u2 in temp:
        c = val if u1[0] == "c" else (val-32)*5/9 if u1[0] == "f" else val-273.15
        out = c if u2[0] == "c" else c*9/5+32 if u2[0] == "f" else c+273.15
        return f"{m[1]} {u1} = {_fmt(round(out, 4))} {u2}"
    return None


def try_numtheory(q):
    ql = q.lower()
    m = re.search(r"is\s+(\d+)\s+(?:a\s+)?prime", ql)
    if m:
        n = int(m[1]); return f"{n} is {'a PRIME' if sp.isprime(n) else 'NOT prime'} number."
    m = re.search(r"(?:prime\s+factors?\s+of|factor(?:ize|ise)?)\s+(\d+)", ql)
    if m:
        n = int(m[1]); f = sp.factorint(n)
        s = " × ".join(f"{p}^{e}" if e > 1 else f"{p}" for p, e in f.items())
        return f"{n} = {s}" + ("  (prime)" if sp.isprime(n) else "")
    m = re.search(r"gcd\s+(?:of\s+)?(\d+)\D+(\d+)", ql)
    if m:
        return f"gcd({m[1]}, {m[2]}) = {sp.igcd(int(m[1]), int(m[2]))}"
    m = re.search(r"lcm\s+(?:of\s+)?(\d+)\D+(\d+)", ql)
    if m:
        return f"lcm({m[1]}, {m[2]}) = {sp.ilcm(int(m[1]), int(m[2]))}"
    return None


def try_base(q):
    ql = q.lower()
    m = re.search(r"(\d+)\s+(?:in|to|as|into)\s+binary", ql)
    if m:
        return f"{m[1]} in binary = {bin(int(m[1]))[2:]}"
    m = re.search(r"(\d+)\s+(?:in|to|as|into)\s+hex(?:adecimal)?", ql)
    if m:
        return f"{m[1]} in hex = {hex(int(m[1]))[2:].upper()}"
    m = re.search(r"binary\s+([01]+)\s+(?:in|to)\s+decimal", ql)
    if m:
        return f"binary {m[1]} = {int(m[1], 2)} in decimal"
    m = re.search(r"hex\s+([0-9a-fA-F]+)\s+(?:in|to)\s+decimal", ql)
    if m:
        return f"hex {m[1]} = {int(m[1], 16)} in decimal"
    return None


def try_combinatorics(q):
    ql = q.lower()
    m = re.search(r"(\d+)\s*(?:choose|c)\s*(\d+)", ql)
    if m:
        n, r = int(m[1]), int(m[2]); return f"C({n}, {r}) = {sp.binomial(n, r)}"
    m = re.search(r"permutations?\s+of\s+(\d+)\s+(?:take|pick|choose)?\s*(\d+)", ql)
    if m:
        n, r = int(m[1]), int(m[2]); return f"P({n}, {r}) = {sp.factorial(n)//sp.factorial(n-r)}"
    m = (re.search(r"factorial\s+of\s+(\d+)", ql) or re.search(r"(\d+)\s+factorial", ql)
         or re.search(r"\b(\d+)\s*!", q))
    if m:
        n = int(m[1])
        if n > 10000:
            return "That factorial is too large to display."
        return f"{n}! = {sp.factorial(n)}"
    m = re.search(r"(\d+)(?:st|nd|rd|th)?\s+fibonacci", ql)
    if m:
        n = int(m[1]); return f"Fibonacci #{n} = {sp.fibonacci(n)}"
    return None


def try_random(q):
    import random
    ql = q.lower()
    if re.search(r"(flip|toss).*coin|coin\s*(flip|toss)", ql):
        return f"🪙 {random.choice(['Heads', 'Tails'])}"
    if re.search(r"\broll\b|\bdice\b|\bdie\b", ql):
        m = re.search(r"d(\d+)|(\d+)[\s-]*sided", ql)
        sides = int(m[1] or m[2]) if m else 6
        return f"🎲 (d{sides}): {random.randint(1, sides)}"
    m = re.search(r"random\s+number\s+(?:between\s+)?(-?\d+)\s*(?:and|to|-)\s*(-?\d+)", ql)
    if m:
        a, b = int(m[1]), int(m[2]); return f"Random {a}–{b}: {random.randint(min(a, b), max(a, b))}"
    return None


_ROMAN = [(1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"),
          (50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]


def try_roman(q):
    ql = q.lower()
    m = re.search(r"(\d+)\s+(?:to|in|as)\s+roman|roman\s+(?:numeral\s+)?(?:of|for)\s+(\d+)", ql)
    if m:
        n = int(m[1] or m[2])
        if not 0 < n < 4000:
            return "Roman numerals cover 1–3999."
        out = ""
        for v, sym in _ROMAN:
            while n >= v:
                out += sym; n -= v
        return f"{m[1] or m[2]} = {out}"
    m = re.search(r"\b([ivxlcdm]{1,15})\b\s+(?:to|in|as)\s+(?:number|decimal|arabic)", ql)
    if m:
        s = m[1].upper(); vals = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
        tot, prev = 0, 0
        for ch in reversed(s):
            v = vals[ch]; tot += -v if v < prev else v; prev = v
        return f"{s} = {tot}"
    return None


def try_interest(q):
    ql = q.lower()
    nums = re.findall(r"\d+\.?\d*", ql)
    if "compound interest" in ql and len(nums) >= 3:
        p, r, t = float(nums[0]), float(nums[1]), float(nums[2])
        amt = p * (1 + r/100) ** t
        return f"Compound: {_fmt(p)} at {_fmt(r)}%/yr for {_fmt(t)}yr = {amt:.2f} (interest {amt-p:.2f})"
    if "simple interest" in ql and len(nums) >= 3:
        p, r, t = float(nums[0]), float(nums[1]), float(nums[2])
        i = p * r/100 * t
        return f"Simple: interest = {i:.2f}, total = {p+i:.2f}"
    return None


def try_text(q):
    m = re.search(r"(?:count|how many)\s+(word|character|letter)s?\s+(?:in|of|are in)?\s*[:\-]?\s*(.+)",
                  q, re.I)
    if m:
        text = m.group(2).strip(" \"'")
        return f"{len(text.split())} words" if m.group(1).lower() == "word" else f"{len(text)} characters"
    m = re.search(r"reverse\s+(?:the\s+)?(?:text|string|word)?s?\s*[:\-]?\s*(.+)", q, re.I)
    if m:
        return m.group(1).strip()[::-1]
    m = re.search(r"\b(upper\s?case|lower\s?case)\s*[:\-]?\s*(.+)", q, re.I)
    if m:
        s = m.group(2).strip(); return s.upper() if "upper" in m.group(1).lower() else s.lower()
    return None


def try_matrix(q):
    mm = re.search(r"\[\[.*?\]\]", q)
    if not mm:
        return None
    txt = mm.group(0)
    if re.search(r"[^0-9,.\[\]\s+-]", txt):          # SECURITY: numbers only, no code
        return None
    rows = re.findall(r"\[([^\[\]]+)\]", txt)
    try:
        mat = sp.Matrix([[sp.Rational(x) for x in re.split(r"[,\s]+", r.strip()) if x] for r in rows])
    except Exception:
        return None
    ql = q.lower()
    if "determinant" in ql or re.search(r"\bdet\b", ql):
        return f"determinant = {mat.det()}" if mat.rows == mat.cols else "determinant needs a square matrix."
    if "inverse" in ql:
        return f"inverse = {mat.inv().tolist()}" if mat.det() != 0 else "not invertible (determinant is 0)."
    if "transpose" in ql:
        return f"transpose = {mat.T.tolist()}"
    if "rank" in ql:
        return f"rank = {mat.rank()}"
    return None


def try_range(q):
    ql = q.lower()
    m = re.search(r"sum\s+(?:of\s+)?(?:the\s+)?(?:squares?\s+)?(?:of\s+)?(?:numbers?\s+|integers?\s+)?"
                  r"(?:from\s+)?(-?\d+)\s+to\s+(-?\d+)", ql)
    if m:
        a, b = int(m[1]), int(m[2])
        if abs(b - a) > 2_000_000:
            return "That range is too large."
        rng = range(min(a, b), max(a, b) + 1)
        if "square" in ql:
            return f"sum of squares {a}..{b} = {sum(i*i for i in rng)}"
        return f"sum {a} to {b} = {sum(rng)}"
    m = re.search(r"next\s+prime\s+(?:after\s+)?(\d+)", ql)
    if m:
        return f"next prime after {m[1]} = {sp.nextprime(int(m[1]))}"
    m = re.search(r"primes?\s+(?:up\s+to|below|under)\s+(\d+)", ql)
    if m:
        n = min(int(m[1]), 5000); ps = list(sp.primerange(2, n + 1))
        return f"primes up to {n} ({len(ps)}): {', '.join(map(str, ps[:60]))}" + (" …" if len(ps) > 60 else "")
    m = re.search(r"first\s+(\d+)\s+primes?", ql)
    if m:
        n = min(int(m[1]), 200); ps = []
        c = 2
        while len(ps) < n:
            if sp.isprime(c):
                ps.append(c)
            c += 1
        return f"first {n} primes: {', '.join(map(str, ps))}"
    return None


def try_round(q):
    m = re.search(r"round\s+(-?\d+\.?\d*)\s+to\s+(\d+)\s*(?:decimal|place|dp|digit)", q.lower())
    if m:
        return f"{m[1]} rounded to {m[2]} places = {round(float(m[1]), int(m[2]))}"
    m = re.search(r"round\s+(-?\d+\.?\d*)\b", q.lower())
    if m:
        return f"{m[1]} rounded = {round(float(m[1]))}"
    return None


def try_geometry(q):
    ql = q.lower()
    pts = re.findall(r"\(\s*(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)\s*\)", q)   # numbers only (safe)
    if len(pts) < 2:
        return None
    (x1, y1), (x2, y2) = [(float(a), float(b)) for a, b in pts[:2]]
    if "distance" in ql:
        import math
        return f"distance ({_fmt(x1)},{_fmt(y1)})–({_fmt(x2)},{_fmt(y2)}) = {_fmt(math.hypot(x2-x1, y2-y1))}"
    if "midpoint" in ql:
        return f"midpoint = ({_fmt((x1+x2)/2)}, {_fmt((y1+y2)/2)})"
    if "slope" in ql or "line" in ql:
        if x2 == x1:
            return f"vertical line, undefined slope, x = {_fmt(x1)}"
        m = (y2 - y1) / (x2 - x1); b = y1 - m * x1
        return f"slope = {_fmt(m)}, line: y = {_fmt(m)}x + {_fmt(b)}"
    return None


# --------------------------------------------------------------------------- #
# Retrieval tool — a growing knowledge base, searched by TF-IDF.
# --------------------------------------------------------------------------- #
class Library:
    def __init__(self):
        import threading
        # the web UI serves requests on multiple threads; learning (add_many → _fit)
        # rebuilds the matrices while another thread may be searching. This lock keeps
        # a search and a refit from interleaving, so retrieval never reads a half-rebuilt
        # index (which crashed with an IndexError).
        self._lock = threading.RLock()
        self.docs = []
        self.sem = None
        if os.path.exists(KB_FILE):
            self.docs = json.load(open(KB_FILE, encoding="utf-8"))
        else:
            self._seed()                     # first ever run: load built-in knowledge
        self._fit()

    def _seed(self):
        """Give a fresh Vio a starter library so it isn't blank on day one."""
        try:
            from seed_knowledge import SEED
        except Exception:
            return
        self.docs = list(SEED)
        json.dump(self.docs, open(KB_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    def _fit(self):
        from sklearn.feature_extraction.text import TfidfVectorizer
        with self._lock:
            docs = self.docs
            if docs:
                # prefix-stemming analyzer so a query word matches every form of it in
                # the library ("overfit"↔"overfitting", "powered"↔"powering"), on BOTH
                # documents and query. Precision is still enforced by the distinctive-
                # term and multi-keyword gates. Everything is built locally and assigned
                # together, so a concurrent search never sees a half-rebuilt index.
                vec = TfidfVectorizer(analyzer=_stem_analyzer).fit(docs)
                mat = vec.transform(docs)
                sem = self._build_semantic(docs)
                self.vec, self.mat, self.sem = vec, mat, sem
            else:
                self.vec, self.mat, self.sem = None, None, None

    @staticmethod
    def _build_semantic(docs):
        """Build the meaning layer (best backend available). Optional: on any failure
        returns None and retrieval stays purely lexical."""
        try:
            from semantic import SemanticIndex
            # neural_only: only blend the high-quality transformer embeddings into
            # ranking. LSA is too coarse here and destabilises the precision gates, so
            # out of the box Vio stays purely lexical (proven) until the user installs
            # sentence-transformers, which flips on real semantic understanding.
            si = SemanticIndex(neural_only=True).fit(docs)
            return si if si.ready else None
        except Exception:
            return None

    def add(self, text):
        self.add_many([text])

    def add_many(self, texts):
        with self._lock:
            self.docs = self.docs + list(texts)     # rebind, don't mutate in place
            json.dump(self.docs, open(KB_FILE, "w", encoding="utf-8"),
                      ensure_ascii=False, indent=2)
            self._fit()

    def search(self, q, k=3):
        with self._lock:                    # take a coherent snapshot of the index
            vec, mat, docs, sem = self.vec, self.mat, self.docs, self.sem
        if not vec:
            return []
        import numpy as np
        sims = (vec.transform([q]) @ mat.T).toarray()[0]
        combined = sims
        # HYBRID re-rank: nudge the ORDER of lexically-plausible passages by meaning, so
        # the most on-meaning of the candidates leads. Confined to passages that already
        # have lexical support (sims>0), weighted below the lexical signal, so it only
        # reorders real candidates — never drags in an unrelated passage on a spurious
        # meaning match. The transformer backend, when installed, is less noisy → more
        # weight. Only blended when its row count matches, so it can never mis-index.
        if sem is not None and sem.ready and sem.mat is not None:
            qv = sem.encode([q])
            if qv is not None and sem.mat.shape[0] == sims.shape[0]:
                s = np.clip(sem.mat @ qv[0].astype(np.float32), 0.0, None)
                w = 0.30 if sem.backend == "transformer" else 0.15
                combined = sims + w * s * (sims > 0.0)
        idx = np.argsort(-combined)[:k]
        n = len(docs)
        return [(docs[i], float(combined[i]))
                for i in idx if i < n and combined[i] > 0.05]


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
        self.mem.setdefault("solved", {})
        self.thinker = Thinker()                           # open-ended thinking engine
        self.skills = SkillBook()                          # user-teachable reflexes
        # CORTEX-OS Phase 1 — the four memory tiers (§3). Working/Semantic/Procedural
        # are live adapters over existing stores; Episodic is a new autobiographical log.
        self.wm = WorkingMemory()
        self.episodic = EpisodicMemory()
        self.semantic = SemanticMemory(self.lib)
        self.procedural = ProceduralMemory(self.skills, self.mem["solved"])
        # CORTEX-OS Phase 2 — the deliberation kernel (§2, §5.1, §10, §11):
        # a Cognitive Workspace trace + the two-clock Executive with the
        # Confidence Engine and Self-Critic behind it.
        self.ws = Workspace()
        self.executive = Executive(self)
        # CORTEX-OS Phase 3 — structured reasoning (§7), knowledge graph (§4), planning (§8).
        # Graph edges are extracted at teach-time; the modes trigger only on their specific
        # phrasing, so the fast path for ordinary questions is untouched.
        self.graph = KnowledgeGraph()
        self.reasoning = Reasoning(self.graph, self)
        self.planner = Planner(self)
        # CORTEX-OS Phase 4 — the World Model: forward simulation + counterfactuals
        # over the learned causal graph (§9). Only runs on prediction phrasings.
        self.world = WorldModel(self.graph)
        self.tables = []                    # uploaded CSV/data tables (computed answers)
        # CORTEX-OS Phase 5 — self-improvement (§12–§14): learn from experience,
        # consolidate memory at idle, notice knowledge gaps, and organize by domain.
        self.learning = LearningEngine(self)
        self.consolidator = Consolidator(self)
        self.curiosity = Curiosity()
        self.cortex = Cortex()
        # CORTEX-OS Phase 6 — close the confidence loop: calibrate against feedback.
        self.calibration = Calibration(self)
        # Reasoning cortex — a local LLM (via Ollama) for genuine reasoning: grounded on
        # Vio's retrieved facts for knowledge questions, open for logic/planning/decisions.
        # Optional: if no local server is running, .available is False and Vio stays
        # purely on its exact + lexical engine.
        try:
            from llm import LLM
            self.llm = LLM()
        except Exception:
            self.llm = None
        # Stage 1 agentic layer: a master + registry wrapping the engines above. This does
        # NOT change ask()/_ask_core — it powers the parallel ask_agentic() path, which
        # falls back to _ask_core for anything not yet migrated. Optional/never fatal.
        try:
            from agents import build_master
            self.master, self.agent_registry = build_master(self)
        except Exception:
            self.master, self.agent_registry = None, None
        self._retrain()

    def _own_model_info(self):
        """Describe Vio's own trained model for the dashboard, without loading it
        (reading config.json is cheap; loading weights is not)."""
        d = os.path.join(DATA_DIR, "own_model")
        cfg_path = os.path.join(d, "config.json")
        if not os.path.exists(os.path.join(d, "weights.pt")) or not os.path.exists(cfg_path):
            return None
        try:
            c = json.load(open(cfg_path, encoding="utf-8"))
            # parameter count ≈ embeddings + blocks (attn + mlp) — close enough to display
            e, L, V, B = c["n_embd"], c["n_layer"], c["vocab_size"], c["block_size"]
            params = V * e + B * e + L * (4 * e * e + 8 * e * e)
            return {"params_m": round(params / 1e6, 1), "layers": L,
                    "n_embd": e, "vocab": V, "ctx": B}
        except Exception:
            return None

    def own_model(self):
        """Vio's OWN model — the from-scratch transformer trained by train_model.py on
        your data only (no pretrained weights). Loaded lazily on first use so startup
        stays instant, and cached. Returns (model, tokenizer) or None if none trained."""
        if getattr(self, "_own", "unset") == "none":
            return None
        if getattr(self, "_own", "unset") == "unset":
            d = os.path.join(DATA_DIR, "own_model")
            if not os.path.exists(os.path.join(d, "weights.pt")):
                self._own = "none"
                return None
            try:
                from neural_model import load
                self._own = load(d)
            except Exception:
                self._own = "none"
                return None
        return self._own

    def consolidate(self):
        """Run one idle 'sleep' pass: reorganize memory + promote repeated wins into
        instant reflexes + recalibrate confidence against feedback. Safe anytime."""
        report = self.consolidator.consolidate()
        report["promoted"] = self.learning.promote_repeats()
        report["calibration"] = self.calibration.refresh()
        return report

    def feedback(self, correct):
        """Grade the last answer (👍/👎) so calibration can learn how much to trust
        Vio's confidence (§10)."""
        ep = self.episodic.grade_last(correct)
        self.calibration.refresh()
        if ep is None:
            return "Nothing to grade yet — ask me something first."
        return ("Thanks — glad that helped. I'll trust that kind of answer a bit more."
                if correct else
                "Got it — I'll be more careful with that kind of answer.")

    def _retrain(self):
        """(Re)train the open-ended thinker on everything Vio has learned."""
        self.thinker.train(self.lib.docs + self.mem.get("facts", []))

    def train_model(self, extra_text=None):
        """Explicitly (re)train Vio's own language model on everything it knows,
        optionally folding in extra text (e.g. the current chat) as new knowledge
        first. Returns real, inspectable training statistics."""
        added = 0
        if extra_text and extra_text.strip():
            chunks = self._chunk(extra_text)
            self.lib.add_many(chunks)
            added = len(chunks)
        self._retrain()
        stats = self.thinker.stats()
        stats["added"] = added
        stats["library"] = len(self.lib.docs)
        return stats

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

    # table-of-contents / index / cross-reference noise common in manuals — these
    # lines are navigation, not content, and they pollute retrieval badly.
    _NOISE_LINE = re.compile(
        r"on page\s+\d+"                                   # "… on page 3448" cross-refs
        r"|this topic includes the following"              # index preamble
        r"|^\s*l\s+\S+\s+\S+.*\bon page\b"                 # "l execute … on page N" bullets
        r"|^\s*(table of contents|index)\b"
        r"|^\s*(chapter|section|page|figure|table)\s+\d+\s*$"
        r"|^\s*\d{1,5}\s*$"                                # bare page numbers
        r"|^\s*(fortios|fortinet|copyright|©).{0,40}$",    # running headers/footers
        re.I)

    def _denoise(self, text):
        """Drop manual/markdown boilerplate (TOC, cross-references, headers, badges)
        while PRESERVING blank lines — they are paragraph/section boundaries that the
        chunker needs to keep sections apart."""
        kept = []
        for ln in text.splitlines():
            s = ln.strip()
            if s and self._NOISE_LINE.search(s):
                continue
            if re.match(r"^#{1,6}\s+\S", s):            # markdown section heading — a
                kept.append("")                         # navigation label, not knowledge;
                continue                                # drop it but keep the boundary
            # drop a stray skill-definition that got pasted into content, and strip
            # leaked command prefixes ("teach:", "remember:") so they never appear in answers
            if re.match(r"^\s*skill\s*:\s*.+\|.*\breply\b", s, re.I):
                continue
            if s:
                s = re.sub(r"^\s*(?:teach|remember|note)\s*:\s*", "", s, flags=re.I)
                s = re.sub(r"\s+(?:teach|remember)\s*:\s*", ". ", s, flags=re.I)  # mid-blob
                s = re.sub(r"^\s*l\s+", "", s)             # leftover "l " bullet glyph
                s = re.sub(r"(?<!\w)#(\w+)", r"\1", s)     # #hashtag -> hashtag (keep word)
            kept.append(s)                                 # keep blank lines as boundaries
        return "\n".join(kept)

    # a line that begins a new reference entry (CLI command heading, etc.). Keeping
    # each entry in its own passage is what lets retrieval answer about one command
    # without dragging in the next.
    _HEADING = re.compile(r"^(execute|config|set|unset|get|show|diagnose|diag|edit|"
                          r"delete|append|end|next)\b.{0,70}$", re.I)

    @staticmethod
    def _size_split(text, size):
        sents = [s.strip() for s in re.split(r"(?<=[.!?؟])\s+|\n+", text.strip())
                 if len(s.strip()) > 2]
        chunks, cur = [], ""
        for s in sents:
            if not cur or len(cur) + len(s) + 1 <= size:
                cur = (cur + " " + s).strip()
            else:
                chunks.append(cur); cur = s
        if cur:
            chunks.append(cur)
        return chunks

    # a sentence opening with one of these leans on the previous sentence (procedure
    # step / narrative continuation), so its block must be kept whole, not split.
    _CONT = re.compile(r"^(then|next|finally|first|second|third|fourth|lastly|also|"
                       r"therefore|thus|hence|so|it|its|this|that|these|they|he|she|"
                       r"their|afterwards?|meanwhile|additionally|furthermore|moreover|"
                       r"consequently|after that|once)\b", re.I)

    def _focus(self, words, passages):
        """The query's most distinctive (highest-idf) in-vocabulary word that also
        appears in the best passage — the topic being answered. Used to keep synthesis
        on-topic. Returns None when there's nothing distinctive to key on."""
        voc = getattr(self.lib.vec, "vocabulary_", {}) or {}
        idfa = getattr(self.lib.vec, "idf_", None)
        if not (words and voc and idfa is not None and passages):
            return None
        topset = {_stem(t) for t in re.findall(r"[a-z0-9؀-ۿ]+", passages[0].lower())}
        invocab = [w for w in words if _stem(w) in voc and _stem(w) in topset]
        if not invocab:
            invocab = [w for w in words if _stem(w) in voc]
        if not invocab:
            return None
        return max(invocab, key=lambda w: float(idfa[voc[_stem(w)]]))

    # config-object words a "list/filter all" query can target, mapped to the token that
    # identifies that object's config passages (per-object chunks start "config … <word>").
    _AGG_ITEMS = {"policy": "policy", "policies": "policy", "rule": "policy",
                  "rules": "policy", "interface": "interface", "interfaces": "interface",
                  "vlan": "vlan", "vlans": "vlan", "address": "address",
                  "addresses": "address", "object": "object", "objects": "object",
                  "route": "route", "routes": "route", "vpn": "vpn", "tunnel": "phase"}

    def _aggregate_answer(self, q):
        """Answer 'show/list ALL <objects> that <condition>' by scanning EVERY matching
        config object and letting the LLM filter — instead of returning the top few by
        keyword match. Returns None when it isn't an aggregate query (or no LLM)."""
        if not (self.llm is not None and self.llm.available):
            return None
        low = q.lower()
        if not re.search(r"\b(all|every|each|list|which|how many|count|any)\b", low):
            return None
        item = next((base for w, base in self._AGG_ITEMS.items()
                     if re.search(rf"\b{w}\b", low)), None)
        if not item:
            return None
        # gather every config passage for that object type (per-object chunks make this exact)
        cand = [d for d in self.lib.docs
                if item in d.lower() and re.search(r"^\s*(config|edit|set)\b", d, re.M | re.I)]
        if not cand:                                   # nothing config-shaped — let retrieval try
            return None
        capped = cand[:40]                             # keep the prompt within the model's window
        ctx = "\n\n".join(f"[{i + 1}]\n{d}" for i, d in enumerate(capped))
        system = ("You analyze device configuration objects. Examine EVERY object listed and "
                  "select those that satisfy the request. For each match give its id/name and a "
                  "one-line reason grounded in that object's own settings. If none match, say so. "
                  "Use ONLY the objects shown — never invent objects, names, or settings.")
        prompt = f"Configuration objects:\n{ctx}\n\nRequest: {q}\n\nList every matching object."
        budget = int(os.environ.get("VIO_LLM_MAX_TOKENS", "3072"))
        ans = self.llm.generate(prompt, system=system, max_tokens=budget)
        if not ans:
            return None
        note = f"\n\n(Scanned the first 40 of {len(cand)} objects.)" if len(cand) > 40 else ""
        return {"answer": ans + note,
                "how": f"analysis over your {item} config (LLM, {self.llm.model})",
                "verified": True,
                "trace": [f"scanned {len(capped)} '{item}' config object(s)"]}

    def _chunk(self, text, size=320):
        """Split into passages, keeping each reference ENTRY together: a new entry
        heading (or a blank line) starts a new passage. Long free-prose blocks are
        then split by size, so ordinary books/articles still chunk sensibly."""
        blocks, cur = [], []
        for ln in text.split("\n"):
            s = ln.strip()
            if not s:                                   # blank line = block boundary
                if cur:
                    blocks.append(cur); cur = []
                continue
            if cur and self._HEADING.match(s):          # a new entry heading
                blocks.append(cur); cur = [s]
            else:
                cur.append(s)
        if cur:
            blocks.append(cur)

        chunks = []
        for blk in blocks:
            joined = " ".join(blk)
            is_entry = bool(blk and self._HEADING.match(blk[0]))
            if is_entry:
                # a reference entry (CLI command etc.) — keep the whole entry in one
                # passage so its Syntax/Example lines stay with it.
                if len(joined) <= size * 2:
                    chunks.append(joined)
                else:
                    chunks.extend(self._size_split(joined, size))
            else:
                sents = [s.strip() for s in re.split(r"(?<=[.!?؟])\s+", joined)
                         if len(s.strip()) > 2]
                # A block whose later sentences open with a connective ("Then …",
                # "Finally …", "It …") is ONE coherent unit — a procedure or a narrative
                # where sentences depend on each other — so keep it together. A block of
                # independent declarative facts is split one-per-passage, so two unrelated
                # facts never share a passage (what dragged a BGP fact into an OSPF answer).
                if len(sents) > 1 and any(self._CONT.match(s) for s in sents[1:]):
                    if len(joined) <= size * 2:
                        chunks.append(joined)
                    else:
                        chunks.extend(self._size_split(joined, size))
                else:
                    chunks.extend(sents or [joined])
        return chunks or [text.strip()]

    @staticmethod
    def _looks_like_config(text):
        """A device config/running-config, not prose: mostly config/set/edit/interface
        lines. Such files must be chunked by stanza, never sentence-split."""
        lines = [l for l in text.splitlines() if l.strip()]
        if len(lines) < 5:
            return False
        cfg = sum(1 for l in lines if re.match(
            r"^\s*(config|edit|set|unset|next|end|interface|ip |no |!|hostname|"
            r"router |access-list|policy|object|rule)\b", l, re.I))
        return cfg >= len(lines) * 0.4

    def _chunk_config(self, text):
        """Split a device config into per-OBJECT passages, each kept whole. A FortiGate
        config yields one passage per top-level `edit … next` (prefixed with its
        `config …` header for context), so asking about one policy retrieves exactly that
        policy — not all of them, and not a stray `set` line. A Cisco config splits on
        `!` / new top-level sections. The opposite of the prose chunker, which shatters
        every `set …` line into its own fragment (what gave wrong answers)."""
        lines = text.splitlines()
        is_forti = (any(re.match(r"^\s*config\b", l, re.I) for l in lines)
                    and any(re.match(r"^\s*edit\b", l, re.I) for l in lines))
        if is_forti:
            return self._chunk_forti(lines)
        # Cisco / generic: '!', a blank line, or a new non-indented section = boundary.
        chunks, cur = [], []

        def flush():
            blk = "\n".join(cur).strip()
            if blk:
                chunks.append(blk)
            cur.clear()

        for l in lines:
            st = l.strip()
            if not st or st == "!":
                flush(); continue
            if cur and not l.startswith((" ", "\t")):
                flush()                                   # new top-level section
            cur.append(l)
        flush()
        return chunks or [text.strip()]

    @staticmethod
    def _chunk_forti(lines):
        """One passage per top-level `edit … next` block (with its `config` header),
        keeping nested config/edit inside that object together."""
        chunks, headers, plain, k = [], [], [], 0

        def flush_plain():
            if plain:
                blk = "\n".join(headers + plain).strip()
                if blk:
                    chunks.append(blk)
                plain.clear()

        while k < len(lines):
            st = lines[k].strip()
            if re.match(r"^edit\b", st, re.I):            # capture a whole balanced object
                flush_plain()
                block, bal, k = [lines[k]], 1, k + 1
                while k < len(lines) and bal > 0:
                    s2 = lines[k].strip()
                    if re.match(r"^(config|edit)\b", s2, re.I):
                        bal += 1
                    elif re.match(r"^(end|next)\b", s2, re.I):
                        bal -= 1
                    block.append(lines[k]); k += 1
                pre = [headers[-1]] if headers else []    # nearest config header = context
                blk = "\n".join(pre + block).strip()
                if blk:
                    chunks.append(blk)
                continue
            if re.match(r"^config\b", st, re.I):
                flush_plain(); headers.append(lines[k])
            elif re.match(r"^end\b", st, re.I):
                flush_plain()
                if headers:
                    headers.pop()
            elif st:
                plain.append(lines[k])
            k += 1
        flush_plain()
        return chunks or ["\n".join(lines).strip()]

    def learn_folder(self, path, recursive=True):
        """Bulk-ingest every readable document in a folder — PDFs, text, markdown,
        config/running-config and log files — into the library in ONE batch (one
        retrain). Configs are chunked by stanza; prose is chunked normally; CSVs load
        as tables. Reads only; never executes anything. Returns a summary dict."""
        import glob
        from diagrams import file_to_text, DRAWIO_EXTS, VISIO_EXTS, IMAGE_EXTS
        diagram_exts = DRAWIO_EXTS + VISIO_EXTS + IMAGE_EXTS
        exts = (".pdf", ".txt", ".md", ".markdown", ".text", ".rst", ".cfg", ".conf",
                ".config", ".log", ".ini", ".yaml", ".yml", ".csv", ".tsv") + diagram_exts
        if not os.path.isdir(path):
            return {"ok": False, "answer": f"Not a folder: {path}", "files": 0,
                    "passages": 0, "skipped": [], "per": []}
        pattern = os.path.join(path, "**", "*") if recursive else os.path.join(path, "*")
        files = sorted(p for p in glob.glob(pattern, recursive=recursive)
                       if os.path.isfile(p) and os.path.splitext(p)[1].lower() in exts)
        all_chunks, per, skipped, learned = [], [], [], 0
        for fp in files:
            name = os.path.basename(fp)
            ext = os.path.splitext(fp)[1].lower()
            try:
                if ext == ".pdf":
                    from pdftext import extract_text, looks_readable
                    with open(fp, "rb") as fh:
                        text = extract_text(fh.read())
                    if not looks_readable(text):
                        skipped.append((name, "unreadable PDF (scanned/encoded)")); continue
                elif ext in (".csv", ".tsv"):
                    with open(fp, encoding="utf-8", errors="ignore") as fh:
                        self.load_csv(fh.read(), name)
                    per.append((name, "loaded as table")); learned += 1; continue
                elif ext in diagram_exts:
                    with open(fp, "rb") as fh:
                        raw = fh.read()
                    text, kind = file_to_text(name, raw)          # diagram → sentences, image → OCR
                    if not text:
                        if ext == ".xml":                          # a non-drawio .xml: use as text
                            text = raw.decode("utf-8", "ignore")
                        else:
                            skipped.append((name, kind)); continue
                else:
                    with open(fp, encoding="utf-8", errors="ignore") as fh:
                        text = fh.read()
            except Exception as e:
                skipped.append((name, str(e)[:60])); continue
            if len((text or "").strip()) < 20:
                skipped.append((name, "empty / too short")); continue
            all_chunks.extend(self._smart_chunks(text))
            self.graph.learn_text(text)
            per.append((name, f"{len(chunks)} passages")); learned += 1
        if all_chunks:
            self.lib.add_many(all_chunks)
            self._retrain()
        self.mem["last_learned"] = {"source": f"folder:{path}", "count": len(all_chunks)}
        self._save()
        return {"ok": learned > 0, "files": learned, "passages": len(all_chunks),
                "skipped": skipped, "per": per, "path": path}

    def _smart_chunks(self, text):
        """Pick the right chunker. A device config must be kept WHOLE per stanza; prose
        gets denoised and sentence-chunked. Decide BEFORE denoising — denoise mangles a
        config. This is what keeps a firewall policy's settings in one passage instead of
        scattering each `set …` line into its own fragment."""
        if self._looks_like_config(text):
            return self._chunk_config(text)
        return self._chunk(self._denoise(text))

    def teach(self, text):                 # add durable knowledge to the library
        chunks = self._smart_chunks(text)
        self.lib.add_many(chunks)
        self.graph.learn_text(text)        # extract relational edges (cheap, teach-time)
        self._retrain()                    # keep the thinker current with new knowledge
        return (f"Learned {len(chunks)} passages into the library." if len(chunks) > 1
                else f"Learned: “{chunks[0]}”")

    def load_csv(self, text, name="table"):
        """Load a CSV as an analyzable data table (not memorized text). Returns a
        human summary, or None if it isn't a usable table."""
        from datatable import DataTable
        t = DataTable.from_csv(text, re.sub(r"\.csv$", "", name, flags=re.I))
        if not t:
            return None
        self.tables.append(t)
        self.tables = self.tables[-5:]              # keep the last few tables
        return t.describe()

    def learn_text(self, text, source=""):
        chunks = self._smart_chunks(text)           # config-aware: keeps stanzas whole
        self.lib.add_many(chunks)
        self.graph.learn_text(text)                 # relational edges (cheap, teach-time)
        self._retrain()
        if source:                                  # remember the most recent source
            self.mem["last_learned"] = {"source": source, "count": len(chunks)}
            self._save()
        where = f" from {source}" if source else ""
        return f"Learned {len(chunks)} passages{where}. You can now ask me about it."

    def learn_github(self, spec):
        """Clone a public GitHub repo and learn its docs (Markdown/txt/PDF). Reads
        only — never runs repo code. Returns a summary dict."""
        from gitlearn import fetch_repo_docs
        owner, repo, docs, skipped = fetch_repo_docs(spec)
        if not docs:
            return {"ok": False,
                    "answer": f"I cloned {owner}/{repo} but found no readable docs "
                              f"(Markdown/text/PDF) to learn — it may be mostly images or code. "
                              f"({skipped} file(s) skipped.)"}
        all_chunks = []
        for source, text in docs:
            all_chunks.extend(self._smart_chunks(text))
        self.lib.add_many(all_chunks)                  # one add + one retrain (efficient)
        self._retrain()
        self.mem["last_learned"] = {"source": f"github:{owner}/{repo}",
                                    "count": len(all_chunks)}
        self._save()
        return {"ok": True, "owner": owner, "repo": repo, "files": len(docs),
                "passages": len(all_chunks), "skipped": skipped,
                "answer": f"✓ Learned {len(all_chunks)} passages from {len(docs)} document(s) "
                          f"in {owner}/{repo}. You can now ask me about it. "
                          f"(Skipped {skipped} non-text file(s) like images/code.)"}

    def _plot(self, q):
        """ASCII plot of y = f(x) over x∈[-10,10]. Expression is safely parsed."""
        m = re.search(r"(?:plot|graph|draw)\s+(?:of\s+|the\s+)?(?:y\s*=\s*)?(.+)", q, re.I)
        if not m:
            return None
        try:
            expr = self.math._parse(m.group(1).strip().strip("?.").replace("^", "**"))
        except Exception:
            return None
        syms = list(expr.free_symbols)
        if len(syms) > 1:
            return None
        xs = syms[0] if syms else sp.Symbol("x")
        W, H = 61, 15
        xvals = [-10 + 20 * i / (W - 1) for i in range(W)]
        ys = []
        for xv in xvals:
            try:
                v = float(expr.subs(xs, xv))
                ys.append(v if abs(v) < 1e7 else None)
            except Exception:
                ys.append(None)
        finite = [v for v in ys if v is not None]
        if not finite:
            return None
        ymin, ymax = min(finite), max(finite)
        if ymax - ymin < 1e-9:
            ymin, ymax = ymin - 1, ymax + 1
        grid = [[" "] * W for _ in range(H)]
        if ymin <= 0 <= ymax:                       # x-axis
            grid[H - 1 - round((0 - ymin) / (ymax - ymin) * (H - 1))] = ["-"] * W
        zc = round(10 / 20 * (W - 1))               # y-axis at x=0
        for r in range(H):
            grid[r][zc] = "|"
        for i, v in enumerate(ys):                  # the curve
            if v is None:
                continue
            r = H - 1 - round((v - ymin) / (ymax - ymin) * (H - 1))
            if 0 <= r < H:
                grid[r][i] = "●"
        art = "\n".join("".join(row) for row in grid)
        return (f"y = {expr}   (x: -10..10,  y: {ymin:g}..{ymax:g})\n" + art)

    def _analyze(self, q):
        m = re.search(r"(?:vertex|analy[sz]e|roots and vertex)\s+(?:of\s+)?(.+)", q, re.I)
        if not m:
            return None
        try:
            expr = self.math._parse(m.group(1).strip().strip("?.").replace("^", "**"))
        except Exception:
            return None
        x = sp.Symbol("x")
        if x not in expr.free_symbols:
            return None
        try:
            poly = sp.Poly(expr, x)
        except Exception:
            return None
        if poly.degree() != 2:
            return None
        a, b, c = [poly.coeff_monomial(x ** 2), poly.coeff_monomial(x), poly.coeff_monomial(1)]
        xv = sp.nsimplify(-b / (2 * a)); yv = sp.nsimplify(expr.subs(x, xv))
        disc = sp.simplify(b * b - 4 * a * c)
        roots = sp.solve(expr, x)
        opens = "upward" if a > 0 else "downward"
        return (f"{expr}: vertex ({xv}, {yv}), opens {opens}; "
                f"discriminant = {disc}; roots: {', '.join(map(str, roots)) or 'none real'}")

    def remember(self, fact):              # store a personal fact (memory)
        self.mem["facts"].append(fact); self._save()
        self._retrain()
        return f"I'll remember: {fact}"

    def _library_summary(self):
        """'What have I taught you?' — Vio summarises its whole library + memory."""
        docs = self.lib.docs
        parts = []
        last = self.mem.get("last_learned")
        if last:
            parts.append(f"Most recently I learned {last['count']} passage(s) "
                         f"from {last['source']}.")
        if self.mem.get("facts"):
            parts.append(f"I remember {len(self.mem['facts'])} thing(s) about you:")
            parts += [f"  • {f}" for f in self.mem["facts"][:12]]
        if docs:
            parts.append(f"\nMy library holds {len(docs)} passage(s). Topics I can discuss:")
            for d in docs[:12]:
                first = re.split(r"(?<=[.!?؟])\s+", d.strip())[0]
                parts.append(f"  • {first[:110]}" + ("…" if len(first) > 110 else ""))
            if len(docs) > 12:
                parts.append(f"  …and {len(docs) - 12} more. Ask me about any of it.")
        if not parts:
            return ("You haven't taught me anything yet. Use the 📄 button to feed me a "
                    "book/notes, or say 'teach: <a fact>'. Then ask me about it.")
        return "\n".join(parts)

    # ---- episodic wrapper (CORTEX-OS §3.3, §15 step 10) --------------------
    def ask(self, q):
        """Public entry: recall past chats on request, run the core reasoner, then
        write the interaction to episodic memory so Vio remembers it."""
        q = (q or "").strip()
        low = q.lower()
        # "what did we talk about", "have we discussed…", "did I ask you before" -> recall
        if re.search(r"\bwhat did we\b|\bwhat have we\b|\bdid we (talk|discuss)|"
                     r"what did i ask|talked about|(have we|did we) discuss|"
                     r"remember when|last time we|our (past |previous )?(chat|conversation)", low):
            r = self._episodic_recall(q)
            if r:
                r.setdefault("confidence", 0.85)
                return r                                # recall itself is not recorded

        # Phase-5 commands: idle consolidation, and Vio's own learning wishlist
        if re.search(r"\b(consolidate|organi[sz]e your (memory|knowledge)|"
                     r"go to sleep|sleep now|clean up your memory)\b", low):
            rep = self.consolidate()
            return {"answer": (f"Done. Merged {rep['merged']} duplicate passage(s), mined "
                    f"{rep['edges']} new relation(s), promoted {rep['promoted']} repeated "
                    f"answer(s) to instant reflexes, pruned {rep['pruned']} stale memories. "
                    f"Library: {rep['library']} passages."), "how": "consolidation",
                    "verified": True, "confidence": 0.9, "trace": [f"{rep['ms']} ms"]}
        # Phase-6 feedback (👍/👎) — grades the previous answer for calibration
        if re.fullmatch(r"(that('?s| is)\s+)?(correct|right|good( answer)?|yes|👍|"
                        r"perfect|exactly|helpful)\s*[.!]*", low):
            return {"answer": self.feedback(True), "how": "feedback",
                    "verified": True, "confidence": 0.9, "trace": []}
        if re.fullmatch(r"(that('?s| is)\s+)?(wrong|incorrect|not right|no|👎|"
                        r"bad( answer)?|nope|false)\s*[.!]*", low):
            return {"answer": self.feedback(False), "how": "feedback",
                    "verified": True, "confidence": 0.9, "trace": []}
        # Phase-6 calibration report — "how accurate is your confidence"
        if re.search(r"how (calibrated|accurate|reliable) (are|is) (you|your confidence)|"
                     r"calibration report|how much should i trust you", low):
            return {"answer": self.calibration.report(), "how": "calibration",
                    "verified": True, "confidence": 0.85, "trace": []}

        if re.search(r"what do you want to learn|what are you curious|"
                     r"what.*gaps?\b|what have you gotten good at|what are you learning", low):
            wl = self.curiosity.wishlist()
            lines = [self.learning.lessons()]
            if wl:
                lines.append("Most of all I'd like to learn: "
                             + ", ".join(f"{w['topic']} (asked {w['count']}×)" for w in wl))
            return {"answer": "\n".join(lines), "how": "self-reflection",
                    "verified": True, "confidence": 0.85, "trace": []}

        r = self.executive.process(q)                   # two-clock: confidence + critic

        # Curiosity (§12): a miss becomes a tracked knowledge gap + a teachable follow-up;
        # a confident answer closes any gap on that topic.
        if r.get("how", "").startswith("no-source"):
            follow = self.curiosity.note_gap(q)
            if follow:
                r = dict(r, answer=r["answer"] + "\n\n" + follow)
        elif r.get("confidence", 0) >= 0.6:
            self.curiosity.resolved(q)

        r["domain"] = self.cortex.classify(q)[0]        # tag the specialist domain
        # remember the path this answer took, so the dashboard can light up the live
        # "how Vio answered" flow diagram (which route fired, where it stopped).
        self._last_route = {
            "how": r.get("how", ""),
            "system": r.get("system"),
            "confidence": r.get("confidence"),
            "verified": r.get("verified"),
            "domain": r.get("domain"),
            "q": (q[:80] + "…") if len(q) > 80 else q,
        }
        self._remember_episode(q, r)
        return r

    def _route(self, q):
        """Stage 2 live router: the agent master IS the entry point. Specialized agents
        handle what they've claimed; the CoreRouterAgent catch-all preserves every
        not-yet-migrated branch of _ask_core, so making the master live cannot change
        behaviour. Resets the retrieval-evidence slot first (as _ask_core does) so the
        Confidence Engine scores correctly whichever agent wins. Falls back to _ask_core
        only if the master failed to build (never in normal operation)."""
        q = (q or "").strip()
        self._last_evidence = {}
        if getattr(self, "master", None) is not None:
            res = self.master.handle(q)
            if res is not None:
                return res.as_dict()
        return self._ask_core(q)

    def ask_agentic(self, q):
        """Alias kept for callers/tests — routing now goes through the live master."""
        return self._route(q)

    def _episodic_recall(self, q):
        eps = self.episodic.recall(q, k=3)
        if not eps:
            eps = self.episodic.recent(6, kind="chat")
            if not eps:
                return {"answer": "We haven't talked about anything yet — ask me something "
                        "and I'll remember it.", "how": "episodic recall",
                        "verified": True, "trace": []}
            lines = ["Recently you asked me about:"] + [f"  • {e['cue']}" for e in eps]
            return {"answer": "\n".join(lines), "how": "episodic recall",
                    "verified": True, "trace": []}
        lines = ["Here's what I recall from our past chats:"]
        for e in eps:
            d = e["detail"].replace("\n", " ")
            lines.append(f"  • You asked “{e['cue']}” — I said: {d[:100]}"
                         + ("…" if len(d) > 100 else ""))
        return {"answer": "\n".join(lines), "how": "episodic recall",
                "verified": True, "trace": [f"recalled {len(eps)} past episode(s)"]}

    def _remember_episode(self, q, r):
        """Turn a completed interaction into an episode (one-shot write)."""
        how = r.get("how", "")
        if how in ("episodic recall", "welcome"):
            return
        if how.endswith("-write") or how in ("skill-write", "learned from GitHub", "github"):
            outcome, reward = "learned", 0.3
        elif how == "no-source":
            outcome, reward = "unknown", 0.0
        elif r.get("verified") and ("symbolic" in how or "exact tool" in how):
            outcome, reward = "solved", 1.0
        elif r.get("verified"):
            outcome, reward = "answered", 0.5
        else:
            outcome, reward = "answered", 0.2
        try:
            # confidence/how/system/domain are logged with each episode so calibration
            # (§10) and the dashboard can aggregate real telemetry over time.
            self.episodic.record(q, r.get("answer", ""), outcome, reward,
                                 tags={"confidence": r.get("confidence"), "how": how,
                                       "system": r.get("system"), "domain": r.get("domain")})
        except Exception:
            pass

    def telemetry(self):
        """Live snapshot of the cognitive system, for the dashboard."""
        from collections import Counter
        eps = self.episodic.episodes
        st = self.thinker.stats()

        # confidence histogram + system split + domain + answer-quality, from episodes
        hist = Counter()
        systems = Counter()
        domains = Counter()
        quality = Counter()
        for e in eps:
            t = e.get("tags") or {}
            c = t.get("confidence")
            if c is not None:
                hist[min(9, int(float(c) * 10))] += 1
            if t.get("system"):
                systems[f"System {t['system']}"] += 1
            if t.get("domain"):
                domains[t["domain"]] += 1
            quality[e.get("outcome", "?")] += 1

        # calibration reliability bands (stated confidence -> observed accuracy)
        graded = [( (e.get("tags") or {}).get("confidence"), e["outcome"])
                  for e in eps if e.get("outcome") in ("correct", "wrong")]
        graded = [(float(c), 1 if o == "correct" else 0) for c, o in graded if c is not None]
        bands = {}
        for c, k in graded:
            b = round(c * 10) / 10
            bands.setdefault(b, []).append(k)
        reliability = [{"stated": b, "accuracy": sum(v) / len(v), "n": len(v)}
                       for b, v in sorted(bands.items())]

        return {
            "name": self.name(),
            "tiers": {"working": len(self.wm), "episodic": len(eps),
                      "semantic": len(self.lib.docs), "procedural": len(self.skills.skills)
                      + len(self.mem.get("solved", {}))},
            "reasoning_cortex": {
                "llm": bool(self.llm and self.llm.available),
                "model": (self.llm.model if self.llm and self.llm.available else None),
                "semantic": (self.lib.sem.backend if getattr(self.lib, "sem", None) else None),
                # Vio's OWN from-scratch model (trained by you, on your data only)
                "own_model": self._own_model_info(),
            },
            "last_route": getattr(self, "_last_route", None),
            "graph": self.graph.summary(),
            "vocab": st["vocab"],
            "gaps": len(self.curiosity.gaps),
            "wishlist": self.curiosity.wishlist(6),
            "calibration": {"scalar": self.calibration.scalar, "graded": len(graded),
                            "reliability": reliability},
            "confidence_hist": [{"band": i * 10, "n": hist.get(i, 0)} for i in range(10)],
            "systems": dict(systems),
            "domains": dict(domains.most_common(6)),
            "quality": dict(quality),
        }

    def _ask_core(self, q):
        q = q.strip()
        low = q.lower()
        self._last_evidence = {}          # retrieval metadata for the Confidence Engine
        # commands
        if low.startswith("teach:"):
            return {"answer": self.teach(q[6:].strip()), "how": "library-write", "verified": True, "trace": []}
        if low.startswith("remember:"):
            return {"answer": self.remember(q[9:].strip()), "how": "memory-write", "verified": True, "trace": []}

        # define a new skill from chat:  "skill: name | when: trigger | reply: text"
        sdef = parse_skill_definition(q)
        if sdef:
            ok, msg = self.skills.add(*sdef)
            return {"answer": msg, "how": "skill-write", "verified": ok, "trace": []}

        # a user-taught skill reflex fires before the built-in tools
        sk = self.skills.match(q)
        if sk:
            return {"answer": sk[1], "how": f"skill: {sk[0]}", "verified": True, "trace": []}

        # learn from a GitHub repo: "gh repo clone owner/repo", "learn from github owner/repo",
        # "learn https://github.com/owner/repo" — clones and learns its docs (never runs code).
        gh = re.match(r"^\s*(?:gh|git)\s+(?:repo\s+)?clone\s+(.+)$", q, re.I) or \
            re.match(r"^\s*(?:learn|read|study|ingest)\s+(?:from\s+)?(?:the\s+)?"
                     r"(?:github|git|repo|repository)\s*[:\-]?\s*(.+)$", q, re.I) or \
            re.match(r"^\s*(?:learn|read|study)\s+(?:from\s+)?"
                     r"(https?://github\.com/\S+)\s*$", q, re.I)
        if gh:
            from gitlearn import parse_spec
            if parse_spec(gh.group(1)):
                try:
                    r = self.learn_github(gh.group(1).strip())
                    return {"answer": r["answer"], "how": "learned from GitHub",
                            "verified": r.get("ok", False), "trace": []}
                except (ValueError, RuntimeError) as e:
                    return {"answer": str(e), "how": "github", "verified": False, "trace": []}

        # 0) "what have I taught you / what did you learn / what's in your library"
        #    (NOT "what do you know about X" — that is a topic query -> retrieval below)
        if re.search(r"what (have i|did i) (taught|told)|what do you know$|"
                     r"what('?s| is) in your (library|memory|head|brain)|"
                     r"what\s+(did\s+|have\s+)?(you|u)\s+(learn|lern|learnt|learned|read)"
                     r"(?!\s+about)|"
                     r"summari[sz]e (your |the )?(library|knowledge|memory)", low):
            return {"answer": self._library_summary(), "how": "library summary",
                    "verified": True, "trace": []}

        # 0=) conversational INTENT: the user is telling me they will give me data /
        #     teach me — that is a statement, not a question. Retrieving facts at it is
        #     exactly the bug where "im give you data to learn" returned ML definitions.
        #     Recognise the intent and invite the actual content instead.
        if (not q.endswith("?")
                and not re.match(r"^\s*(what|how|why|who|where|when|which|whose|is|are|"
                                 r"do|does|did|can|could|should|would|will)\b", low)
                and re.search(r"\b(?:i|i'?m|im|let\s+me|lemme|we|we'?ll)\b[\w\s'’]{0,24}?"
                              r"\b(give|giv|gonna|feed|send|provide|share|upload|paste|"
                              r"teach|train|show|load)\b", low)
                and re.search(r"\b(you|u|vio|it|data|dataset|datasets|file|files|"
                              r"document|documents|docs?|info|information|knowledge|"
                              r"text|notes|material|content|stuff)\b", low)):
            return {"answer": "Great — go ahead. Paste the text right here and I'll learn "
                    "it, or drop a file (📄 PDF/TXT/MD, or a CSV to analyze). To store one "
                    "fact, start the line with  teach:  — e.g.  teach: OSPF is a "
                    "link-state routing protocol.",
                    "how": "greeting", "verified": True, "trace": []}

        # 0-) open-ended GENERATION: "write/continue/imagine/compose about …"
        #     (typo-tolerant: 'rite'/'wirte' for 'write')
        gm = re.match(r"\s*(w?rite|wirte|write|continue|compose|imagine|generate|dream|"
                      r"make up|tell me a story|اكتب|أكتب|اكمل|أكمل|تخيل|ألّف|الف|احك|احكي)\b(.*)",
                      low, re.I)
        if gm:
            seed = re.sub(r"\b(a|an|the|about|something|some|text|paragraph|sentence|story|"
                          r"me|for|on|عن|قصة|شيء|نص|فقرة)\b", " ", gm.group(2)).strip()
            # Vio's OWN trained model writes it, when one exists — every weight learned
            # from your data, nothing pretrained. Falls back to the n-gram writer.
            own = self.own_model()
            if own:
                try:
                    from neural_model import sample
                    model, tok = own
                    txt = sample(model, tok, seed or "The", max_new_tokens=140).strip()
                    if txt:
                        return {"answer": txt, "how": "generation (your own trained model)",
                                "verified": False,
                                "trace": [f"{model.num_params()/1e6:.1f}M-parameter transformer "
                                          f"trained from zero on your data",
                                          "generated text — not a retrieved fact"]}
                except Exception:
                    pass
            out = self.thinker.generate(seed)
            if out:
                return {"answer": out, "how": "generation (learned from your library)",
                        "verified": False,
                        "trace": [f"n-gram model trained on {self.thinker._trained_on} passages",
                                  "generated text — not a retrieved fact"]}
            return {"answer": "I can't generate yet — I haven't read enough. Teach me a book "
                              "or some notes first (📄 or 'teach: …'), then ask me to write.",
                    "how": "generation", "verified": False, "trace": []}

        # 1-) visual/analysis skills first (they consume "plot …", "vertex …")
        if re.match(r"\s*(plot|graph|draw)\b", low):
            r = self._plot(q)
            if r:
                return {"answer": r, "how": "function plot", "verified": True, "trace": []}
        if re.match(r"\s*(vertex|analy[sz]e)\b", low):
            r = self._analyze(q)
            if r:
                return {"answer": r, "how": "quadratic analysis", "verified": True, "trace": []}

        # 1a) everyday exact tools (order matters: most specific first)
        for tool in (try_percent, try_interest, try_combinatorics, try_roman, try_base,
                     try_numtheory, try_geometry, try_matrix, try_range, try_round, try_random,
                     try_units, try_stats, try_text):
            r = tool(q)
            if r:
                return {"answer": r, "how": "exact tool", "verified": True, "trace": []}

        # 1b) systems of equations: "solve x+y=10, x-y=2"
        if q.count("=") >= 2 and re.search(r"[,;]|and", q):
            try:
                body = re.sub(r"^\s*solve\s*", "", q, flags=re.I)
                parts = [p for p in re.split(r"[,;]|\band\b", body) if "=" in p]
                eqs = [sp.Eq(self.math._parse(l), self.math._parse(r))
                       for l, r in (p.split("=", 1) for p in parts)]
                syms = sorted(set().union(*[e.free_symbols for e in eqs]), key=str)
                sol = sp.solve(eqs, syms, dict=True)
                if sol:
                    ans = ", ".join(f"{k} = {v}" for k, v in sol[0].items())
                    self.mem["solved"][q] = ans; self._save()
                    return {"answer": ans, "how": "symbolic reasoning (system)",
                            "verified": True, "trace": [f"solved {len(eqs)} equations"]}
            except Exception:
                pass

        # 1) exact reasoning (math/logic) — verified
        if self.math.looks_mathy(q):
            ans, trace, ok = self.math.handle(q)
            if ans is not None:
                self.mem["solved"][q] = ans; self._save()      # continual: cache solutions
                return {"answer": ans, "how": "symbolic reasoning (sympy)",
                        "verified": ok, "trace": trace}

        # 1a1) data-table analysis — COMPUTED answers over an uploaded CSV (counts, totals,
        #      averages, group-by, top-N). The analyzer returns None for non-data questions.
        for tbl in reversed(self.tables):
            da = tbl.answer(q)
            if da:
                return {"answer": da, "how": f"data analysis ({tbl.name})",
                        "verified": True, "trace": [f"computed over {len(tbl.rows)} rows"]}
        # If a table is loaded and this is clearly a data/analytical question that no
        # table could answer, say so honestly — do NOT fall through to text retrieval
        # (that is what returned networking facts for an airline question).
        if self.tables and re.search(
                r"\b(total|sum|average|mean|count|how many|top|best|worst|highest|lowest|"
                r"most|least|maximum|minimum|per|by |rank|revenue|sales|performance|trend)\b", low):
            t = self.tables[-1]
            return {"answer": f"I can't compute that from the loaded data “{t.name}”. "
                    f"Its columns are: {', '.join(t.headers)}. Ask about those "
                    f"(e.g. total {t.numeric[0] if t.numeric else 'a column'}, "
                    f"or top 5 by a column), or upload a dataset that has what you need.",
                    "how": "data analysis (no matching column)", "verified": False,
                    "confidence": 0.2, "trace": []}

        # 1a2) world model (§9) — "what happens if X" / "what if X didn't…". Simulates
        #      forward over learned causal edges; returns None instantly otherwise.
        wm = self.world.answer(q)
        if wm:
            return wm

        # 1b) structured reasoning (§7) — relational / causal / taxonomic / deductive.
        #     Cheap specific triggers; returns None instantly for ordinary questions.
        rr = self.reasoning.answer(q)
        if rr:
            return rr

        # 1c) planning (§8) — only fires on "how do I …" / "steps to …" phrasings.
        if is_plan_request(q):
            pr = self.planner.plan(q)
            if pr:
                return pr

        # 1d) analyze-ALL over the config: "show all policies pointing to internet",
        #     "which interfaces allow https", "how many rules deny FTP" — an aggregation
        #     ACROSS every object of a type, not a single lookup. Returns None (falls
        #     through to normal retrieval) when it isn't that kind of question.
        agg = self._aggregate_answer(q)
        if agg:
            return agg

        # 2) retrieval from the growing library + personal memory
        STOP = {"the", "a", "an", "is", "are", "was", "of", "to", "in", "on", "for",
                "what", "who", "where", "when", "why", "how", "my", "me", "and", "i",
                "do", "does", "you", "your", "it", "that", "this", "am", "tell",
                # generic fillers — never the distinctive topic word of a question
                "happens", "happen", "happened", "get", "gets", "got", "off", "use",
                "used", "using", "make", "makes", "made", "work", "works", "need",
                "want", "like", "goes", "go", "put", "take", "give", "let", "kind",
                "sort", "thing", "things", "way", "really", "actually", "mean",
                "means", "if", "can", "will", "would", "should", "could", "with",
                # framing words — question shape, not the topic ("why does X matter",
                # "difference between X and Y", "explain X", "purpose of X")
                "difference", "differences", "between", "versus", "compare",
                "compared", "comparison", "matter", "matters", "importance",
                "important", "purpose", "meaning", "definition", "define", "explain",
                "explained", "describe", "description", "example", "examples",
                "reason", "reasons", "benefit", "benefits", "point", "idea"}
        words = [w for w in re.findall(r"\w+", low) if len(w) > 2 and w not in STOP]
        # Retrieve a broad candidate set: with a reasoning LLM we prefer RECALL — give it
        # enough passages that the right one (e.g. a specific just-taught document) is in
        # the pile even when generic facts share the query's common words — and let the
        # model pick. Semantic re-rank (install sentence-transformers) sharpens the order.
        k = 12 if (self.llm is not None and self.llm.available) else 6
        hits = [(d, s) for d, s in self.lib.search(q, k=k) if s > 0.10]
        # PRECISION GATE: don't answer from a passage that only shares a common word
        # with the question (e.g. "who won the 2050 world cup" matching "the largest
        # desert in the world" on just "world"). Trust a hit only if it is strong, or
        # covers >=2 distinct query keywords, or the question is single-topic.
        if hits:
            # prefix-fold so morphological variants count as the same word ("powered"
            # ↔ "powers" ↔ "powering", "overfit" ↔ "overfitting") — otherwise a passage
            # that clearly answers the question gets rejected on a verb-tense mismatch.
            qkw = {_stem(w) for w in words}
            top = hits[0][1]
            multi = any(len(qkw & {_stem(t) for t in re.findall(r"[a-z؀-ۿ]+", d.lower())}) >= 2
                        for d, _ in hits)
            if not (top >= 0.28 or multi or len(qkw) <= 1):
                hits = []
        # DISTINCTIVE-TERM GATE: the query's rarest content word must actually appear
        # in what we retrieved. A wrong-domain hit shares only common words ("best
        # route performance") and never the distinctive one ("airline") — so if the
        # single most specific query word is absent from every passage, refuse rather
        # than answer from the wrong domain. Always applied: a short passage can score a
        # high cosine on one shared word ("the moon") without the distinctive term
        # ("president") ever appearing, so cosine strength is not a safe exemption.
        if hits and words:
            vec = self.lib.vec
            vocab = getattr(vec, "vocabulary_", {}) or {}
            idf = getattr(vec, "idf_", None)

            def _spec(w):
                j = vocab.get(_stem(w))          # vocabulary is prefix-stemmed
                if j is None:
                    return 1e9                    # out-of-vocabulary → maximally distinctive
                return float(idf[j]) if idf is not None else 1.0

            # rarest word wins; ties (e.g. two out-of-vocabulary words) break toward
            # the longer one, which is the more topical content word.
            key = max(words, key=lambda w: (_spec(w), len(w)))
            blob = " ".join(d.lower() for d, _ in hits)
            if key[:5] not in blob:              # prefix match tolerates morphology
                hits = []
        if re.search(r"about (me|myself)|(who|what) am i|know about me", low):
            facts = list(self.mem["facts"])          # "what do you know about me" -> all
        else:
            facts = [f for f in self.mem["facts"] if self._match_fact(f, words)]
        self._last_evidence = {"top": (hits[0][1] if hits else 0.0),
                               "hits": len(hits), "facts": len(facts)}
        if hits or facts:
            # FOCUS WORD: the query's most distinctive (highest-idf) in-vocabulary word
            # — "ram" over "computer", "encryption" over "matter". The synthesiser uses
            # it to keep multi-passage answers on topic instead of drifting to a
            # neighbouring fact that merely shares a common word.
            # the focus word keeps synthesis on-topic — it must appear in the best
            # passage, so it is the topic being answered, not an incidental rare verb
            # ("how does OSPF choose…" must key on OSPF, not on "choose").
            focus = self._focus(words, [d for d, _ in hits])
            # REASONING CORTEX (grounded): if a local LLM is available, let it compose
            # the answer from ONLY the retrieved passages — real language, still no
            # hallucination (it is told to answer from the context or say it can't).
            if self.llm is not None and self.llm.available:
                from llm import grounded_prompt, GROUNDED_SYSTEM_D
                ctx = [d for d, _ in hits] + list(facts)
                budget = int(os.environ.get("VIO_LLM_MAX_TOKENS", "3072"))
                ans = self.llm.generate(grounded_prompt(q, ctx), system=GROUNDED_SYSTEM_D,
                                        max_tokens=budget)
                if ans:
                    # "Verified" only when retrieval genuinely backs the answer. A weak,
                    # off-topic hit still lets the model answer from its own knowledge
                    # (the hybrid prompt allows that) — but that answer must NOT wear a
                    # "verified" badge, or a general-knowledge reply looks sourced.
                    top = hits[0][1] if hits else 0.0
                    strong = bool(facts) or len(hits) >= 2 or top >= 0.30
                    return {"answer": ans,
                            "how": ("reasoning over knowledge (LLM, grounded)" if strong
                                    else "reasoning (LLM)"),
                            "verified": bool(strong),
                            "trace": [f"local LLM ({self.llm.model}) "
                                      + (f"grounded on {len(hits)} passage(s) + "
                                         f"{len(facts)} fact(s)" if strong
                                         else f"answered from general knowledge "
                                         f"(weak retrieval, top {top:.2f})")]}
            # open-ended THINKING: synthesise the exact sentences that answer the
            # question, drawn from several passages at once (grounded, no guessing).
            syn = self.thinker.synthesize(q, [d for d, _ in hits], facts, focus=focus)
            if syn:
                return {"answer": syn, "how": "reasoning over knowledge (synthesis)",
                        "verified": True,
                        "trace": [f"synthesised from {len(hits)} passage(s) + "
                                  f"{len(facts)} memory fact(s)"]}
            # fallback: show the passages/facts directly
            parts = []
            if facts:
                parts.append("From what I know about you:\n  " + "\n  ".join(facts))
            if hits:
                parts.append("From the library:\n" + "\n".join(f"  • {d}  (match {s:.2f})" for d, s in hits))
            return {"answer": "\n".join(parts), "how": "retrieval", "verified": bool(hits or facts),
                    "trace": [f"searched {len(self.lib.docs)} docs + {len(self.mem['facts'])} memories"]}

        # 3) REASONING CORTEX (open): no stored knowledge matched — but this may be a
        # reasoning task (logic, planning, decision under uncertainty), not a fact
        # lookup. If a local LLM is available, reason it through (told to stay honest
        # about facts it doesn't have). This is what turns "rank the missing info and
        # decide under uncertainty" from a CIA-triad misfire into an actual answer.
        if self.llm is not None and self.llm.available:
            from llm import REASON_SYSTEM_D
            # big deliverables (root-cause tree + timeline + appendix …) need room to
            # finish — a low cap truncates them mid-section. Configurable for slower PCs.
            budget = int(os.environ.get("VIO_LLM_MAX_TOKENS", "3072"))
            ans = self.llm.generate(q, system=REASON_SYSTEM_D, temperature=0.3, max_tokens=budget)
            if ans:
                return {"answer": ans, "how": "reasoning (LLM)", "verified": False,
                        "trace": [f"local LLM ({self.llm.model}) reasoning — "
                                  "not a stored fact"]}
            # the model is running but didn't answer in time — be honest, don't fall
            # through to lexical retrieval that would return unrelated facts.
            return {"answer": f"My local reasoning model ({self.llm.model}) didn't finish "
                    "in time on this one. Try a shorter prompt, or a smaller/faster model "
                    "(e.g. `ollama pull llama3.2`) and set VIO_LLM_MODEL=llama3.2.",
                    "how": "llm-timeout", "verified": False, "confidence": 0.2, "trace": []}

        # 4) honest "I don't know yet" + how to teach it
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
