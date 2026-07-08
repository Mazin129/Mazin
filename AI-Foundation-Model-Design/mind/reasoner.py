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
        self.docs = []
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
        if self.docs:
            self.vec = TfidfVectorizer(stop_words="english").fit(self.docs)
            self.mat = self.vec.transform(self.docs)
        else:
            self.vec = None

    def add(self, text):
        self.add_many([text])

    def add_many(self, texts):
        self.docs.extend(texts)
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
        # CORTEX-OS Phase 5 — self-improvement (§12–§14): learn from experience,
        # consolidate memory at idle, notice knowledge gaps, and organize by domain.
        self.learning = LearningEngine(self)
        self.consolidator = Consolidator(self)
        self.curiosity = Curiosity()
        self.cortex = Cortex()
        # CORTEX-OS Phase 6 — close the confidence loop: calibrate against feedback.
        self.calibration = Calibration(self)
        self._retrain()

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
            if s:
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
            if len(joined) <= size * 2:
                chunks.append(joined)                   # a whole entry / short paragraph
            else:
                chunks.extend(self._size_split(joined, size))   # long prose -> by size
        return chunks or [text.strip()]

    def teach(self, text):                 # add durable knowledge to the library
        chunks = self._chunk(text)
        self.lib.add_many(chunks)
        self.graph.learn_text(text)        # extract relational edges (cheap, teach-time)
        self._retrain()                    # keep the thinker current with new knowledge
        return (f"Learned {len(chunks)} passages into the library." if len(chunks) > 1
                else f"Learned: “{chunks[0]}”")

    def learn_text(self, text, source=""):
        text = self._denoise(text)                  # strip manual boilerplate first
        chunks = self._chunk(text)
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
            all_chunks.extend(self._chunk(self._denoise(text)))
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
        self._remember_episode(q, r)
        return r

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

        # 0-) open-ended GENERATION: "write/continue/imagine/compose about …"
        #     (typo-tolerant: 'rite'/'wirte' for 'write')
        gm = re.match(r"\s*(w?rite|wirte|write|continue|compose|imagine|generate|dream|"
                      r"make up|tell me a story|اكتب|أكتب|اكمل|أكمل|تخيل|ألّف|الف|احك|احكي)\b(.*)",
                      low, re.I)
        if gm:
            seed = re.sub(r"\b(a|an|the|about|something|some|text|paragraph|sentence|story|"
                          r"me|for|on|عن|قصة|شيء|نص|فقرة)\b", " ", gm.group(2)).strip()
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

        # 2) retrieval from the growing library + personal memory
        STOP = {"the", "a", "an", "is", "are", "was", "of", "to", "in", "on", "for",
                "what", "who", "where", "when", "why", "how", "my", "me", "and", "i",
                "do", "does", "you", "your", "it", "that", "this", "am", "tell"}
        words = [w for w in re.findall(r"\w+", low) if len(w) > 2 and w not in STOP]
        hits = [(d, s) for d, s in self.lib.search(q, k=6) if s > 0.10]
        # PRECISION GATE: don't answer from a passage that only shares a common word
        # with the question (e.g. "who won the 2050 world cup" matching "the largest
        # desert in the world" on just "world"). Trust a hit only if it is strong, or
        # covers >=2 distinct query keywords, or the question is single-topic.
        if hits:
            qkw = set(words)
            top = hits[0][1]
            multi = any(len(qkw & set(re.findall(r"[a-z؀-ۿ]+", d.lower()))) >= 2
                        for d, _ in hits)
            if not (top >= 0.28 or multi or len(qkw) <= 1):
                hits = []
        if re.search(r"about (me|myself)|(who|what) am i|know about me", low):
            facts = list(self.mem["facts"])          # "what do you know about me" -> all
        else:
            facts = [f for f in self.mem["facts"] if self._match_fact(f, words)]
        self._last_evidence = {"top": (hits[0][1] if hits else 0.0),
                               "hits": len(hits), "facts": len(facts)}
        if hits or facts:
            # open-ended THINKING: synthesise the exact sentences that answer the
            # question, drawn from several passages at once (grounded, no guessing).
            syn = self.thinker.synthesize(q, [d for d, _ in hits], facts)
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
