"""
Talk  —  a natural-language front-end for The Mind (English + العربية).

The Mind (reasoner.py) reasons and verifies, but expects semi-structured input
("solve x^2-5x+6=0", "teach: ..."). This layer lets you speak normally — it reads
free-form English or Arabic, works out your INTENT, extracts the payload, and drives
the right tool. It even turns spoken math ("x squared minus five x plus six") into
symbols.

HONEST NOTE: this front-end is a rule-based understander (patterns + normalisation),
not a neural language model — so it is precise on math/teach/recall/question shapes,
not open-ended chit-chat. It is the "language cortex" slot in the AXIOM design
(doc 06, direction 3); later our own small trained model can replace these rules
with learned routing. It needs no market model and runs instantly on a laptop.

    python talk.py
"""

import re
import datetime
from reasoner import Mind

# UTC offsets for a few places (Vio computes time from your machine's clock, no internet)
TZ = {"ksa": 3, "saudi": 3, "riyadh": 3, "makkah": 3, "mecca": 3, "jeddah": 3,
      "السعودية": 3, "الرياض": 3, "uae": 4, "dubai": 4, "abu dhabi": 4,
      "egypt": 2, "cairo": 2, "مصر": 2, "qatar": 3, "kuwait": 3, "bahrain": 3,
      "uk": 0, "london": 0, "utc": 0, "gmt": 0, "turkey": 3, "istanbul": 3,
      "germany": 1, "france": 1, "paris": 1, "india": 5.5, "new york": -5, "est": -5}


DATE_FMTS = ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y", "%d.%m.%Y",
             "%B %d %Y", "%B %d, %Y", "%d %B %Y", "%d %b %Y", "%b %d %Y", "%b %d, %Y"]


def parse_date(s):
    s = s.strip().strip("؟?.،")
    for f in DATE_FMTS:
        try:
            return datetime.datetime.strptime(s, f).date()
        except ValueError:
            pass
    return None


def time_answer(text):
    t = text.lower()
    # 1) date math on a specific date
    m = re.search(r"days?\s+(?:between|from)\s+(.+?)\s+(?:and|to|until)\s+(.+)", t)
    if m and parse_date(m.group(1)) and parse_date(m.group(2)):
        d1, d2 = parse_date(m.group(1)), parse_date(m.group(2))
        return f"{abs((d2 - d1).days)} days between {d1} and {d2}."
    m = re.search(r"days?\s+(?:until|till|to|since)\s+(.+)", t)
    if m and parse_date(m.group(1)):
        d = parse_date(m.group(1)); diff = (d - datetime.date.today()).days
        return f"{abs(diff)} days {'until' if diff >= 0 else 'since'} {d} (a {d.strftime('%A')})."
    m = re.search(r"(?:what\s+day\s+(?:is|was|of\s+the\s+week)|day\s+of\s+week\s+for|"
                  r"which\s+day\s+is)\s+(.+)", t)
    if m and parse_date(m.group(1)):
        return f"{parse_date(m.group(1)).strftime('%A, %d %B %Y')}."
    # 2) current time / date  (note: plain 'day' is NOT a trigger, to avoid clashing)
    if not re.search(r"\b(time|clock|now|today|current|date|الوقت|الساعة|التاريخ|اليوم|الآن|الان)\b", t):
        return None
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    place, off = None, None
    for name, o in TZ.items():
        if name in t:
            place, off = name, o
            break
    when = now_utc + datetime.timedelta(hours=off) if off is not None else datetime.datetime.now()
    where = f" in {place.upper()}" if place else " (your machine's local time)"
    if re.search(r"\b(date|today|التاريخ|اليوم)\b", t):
        return f"Today{where} is {when.strftime('%A, %d %B %Y')}."
    return f"The time{where} is {when.strftime('%H:%M')} ({when.strftime('%I:%M %p')})."


CAPS = re.compile(r"what can you do|your (skills|capabilit|abilit)|what are you capable|"
                  r"how can you help|قدرات|ماذا تستطيع|ماذا يمكنك|وش تسوي", re.I)

# spoken-math -> symbols (English)
WORD_MATH = [
    (r"\bto the power of\b", "^"), (r"\bsquared\b", "^2"), (r"\bcubed\b", "^3"),
    (r"\bplus\b", "+"), (r"\bminus\b", "-"), (r"\btimes\b", "*"),
    (r"\bmultiplied by\b", "*"), (r"\bdivided by\b", "/"), (r"\bover\b", "/"),
    (r"\bsquare root of\b", "sqrt"), (r"\bpi\b", "pi"),
]
# filler to strip before parsing a math expression
FILLER = [r"what(?:'s| is)", r"whats", r"calculate", r"compute", r"the value of",
          r"work out", r"evaluate", r"tell me", r"can you", r"please", r"for me",
          r"the answer to", r"how much is"]

# intent keywords (English + Arabic)
SOLVE = ("solve", "roots of", "root of", "solutions", "solution to", "حل", "جذور")
INTEGRATE = ("integrate", "integral of", "integral", "تكامل", "تكامل ل")
DERIV = ("derivative", "differentiate", "d/dx", "مشتقة", "اشتق", "اشتقاق")
SIMPLIFY = ("simplify", "بسط", "بسّط")
FACTOR = ("factor", "حلل")
EXPAND = ("expand", "افرد", "وسّع")
REMEMBER = ("remember that", "remember", "note that", "تذكر ان", "تذكر أن", "تذكر")
TEACH = ("teach that", "teach", "the fact that", "did you know", "علمك", "علم ان")
QUESTION = ("what", "who", "where", "when", "why", "how", "which",
            "ما", "من", "اين", "أين", "متى", "لماذا", "كيف", "هل")


KEEP_FUNCS = {"x", "sqrt", "sin", "cos", "tan", "log", "exp", "pi", "y", "t"}


def normalize_math(t):
    """Turn spoken math into symbols and keep ONLY real math tokens — English words
    like 'what/are/the/roots/of' are dropped so the parser never sees them."""
    t = t.lower()
    for pat, rep in WORD_MATH:
        t = re.sub(pat, rep, t, flags=re.I)
    out = []
    for tok in re.findall(r"[a-z]+|\d+\.?\d*|[+\-*/^().=]", t):
        if tok.isalpha():
            if tok in KEEP_FUNCS:
                out.append(tok)                    # keep variables / function names
        else:
            out.append(tok)                        # keep numbers and operators
    return " ".join(out).strip()


def has(t, kws):
    return any(k in t for k in kws)


# a first-person statement of a personal fact -> store it in memory
STATEMENT = re.compile(
    r"^\s*(my\s+\w+.*\b(is|are|was)\b|my name\b|i\s+am\b|i'?m\b|call me\b|"
    r"i\s+(like|love|have|prefer|live|work|enjoy|hate|study|speak|need|want to be)\b|"
    r"اسمي|أنا\b|انا\b|احب|أحب|اعمل|أعمل)", re.I)


def route(text):
    """Map free text -> a structured query for The Mind."""
    t = text.lower().strip()

    # system of equations ("solve x+y=10, x-y=2") -> pass through raw so The Mind's
    # system solver sees the separators (don't normalise the comma away).
    if text.count("=") >= 2 and re.search(r"[,;]|\band\b", text):
        return text

    # explicit teaching / memory (natural phrasing)
    if t.startswith(("remember that", "remember")) or t.startswith(("تذكر",)):
        fact = re.sub(r"^(remember that|remember|تذكر ان|تذكر أن|تذكر)\s*", "", text, flags=re.I).strip(" :؟?.")
        return f"remember: {fact}"
    if t.startswith(("teach that", "teach", "note that")) or t.startswith(("علم", "علمك")):
        fact = re.sub(r"^(teach that|teach|note that|علم ان|علمك|علم)\s*", "", text, flags=re.I).strip(" :؟?.")
        return f"teach: {fact}"

    # math intents -> build the exact Mind command. normalize_math() strips the
    # keyword words too (they aren't math tokens), so we just normalize the whole text.
    if has(t, INTEGRATE):
        return "integrate " + normalize_math(t)
    if has(t, DERIV):
        return "derivative of " + normalize_math(t)
    if has(t, SIMPLIFY):
        return "simplify " + normalize_math(t)
    if has(t, FACTOR):
        return "factor " + normalize_math(t)
    if has(t, EXPAND):
        return "expand " + normalize_math(t)
    if has(t, SOLVE) or ("=" in text and "?" not in text):
        expr = normalize_math(t)
        if "=" not in expr:
            expr += " = 0"
        return f"solve {expr}"

    # a personal STATEMENT ("my name is Mazin", "I love AI", "call me X") -> remember.
    # (Questions start with what/who/... so they don't match; typos like "my nam is" do.)
    if not text.strip().endswith("?") and STATEMENT.match(t):
        return f"remember: {text.strip()}"

    # a bare arithmetic/algebra expression ("15 times 12 plus 7") — decided by what
    # actually survives normalisation, not by question words.
    norm = normalize_math(t)
    if re.search(r"[+\-*/^]", norm) and re.search(r"[0-9x]", norm):
        return norm

    # otherwise a question / statement -> The Mind retrieves from library + memory
    return text


GREET = re.compile(r"^(hi|hello|hey|salam|salaam|مرحبا|سلام|اهلا|أهلا)\b", re.I)
# name the assistant:  "your name is Vio" / "i'll call you Vio" / "اسمك ڤيو"
NAME_ME = re.compile(r"(?:your name is|you are called|i'?ll call you|i will call you|"
                     r"let me call you|اسمك|سمّيتك|سميتك)\s+([^\s،.?!]+)", re.I)
# ask who it is
WHO_ARE_YOU = re.compile(r"\b(what'?s your name|what is your name|who are you|"
                         r"what are you|ما اسمك|ما إسمك|من انت|من أنت)\b", re.I)


def reply(mind, text):
    t = text.strip()

    # identity: name the assistant
    m = NAME_ME.search(t)
    if m:
        new = m.group(1).strip("؟?.،")
        mind.set_name(new)
        return {"answer": f"Understood — I'm {new} now. Nice to meet you.",
                "how": "identity", "verified": True, "trace": []}
    # identity: who are you
    if WHO_ARE_YOU.search(t):
        return {"answer": f"I'm {mind.name()}, your own local reasoning assistant. I solve and "
                          f"verify maths, remember what you tell me, retrieve what you teach me, "
                          f"and I say 'I don't know' rather than guess. (English / العربية)",
                "how": "identity", "verified": True, "trace": []}
    # capabilities — honest list of what it can and can't do
    if CAPS.search(t):
        return {"answer":
                f"I'm {mind.name()}. Here's what I can actually do — reliably and verified:\n"
                "• Maths, exactly: arithmetic (333+98), algebra (solve x^2-5x+6=0), calculus "
                "(integrate/derivative), simplify/factor/expand — and I check my own answers.\n"
                "• Remember facts about you ('remember that …' or just 'my name is …').\n"
                "• Learn facts you teach me ('teach: …') and retrieve them later.\n"
                "• Tell the time/date (e.g. 'what time is it in KSA').\n"
                "• Be honest: I say 'I don't know' instead of guessing.\n"
                "What I can't do: I run 100% on your machine with no internet, so I don't know "
                "live world facts (news, prices, someone's biography) unless you teach me — and "
                "I'm not a chit-chat model. That's by design: everything I tell you is verified "
                "or something you gave me.",
                "how": "capabilities", "verified": True, "trace": []}

    # time / date
    ta = time_answer(t)
    if ta:
        return {"answer": ta, "how": "clock", "verified": True, "trace": []}

    if GREET.match(t):
        return {"answer": f"Hello — I'm {mind.name()}. Ask me to solve/integrate something, tell "
                          f"me a fact ('remember that …'), ask the time, or ask what I can do. "
                          f"(English / العربية)",
                "how": "greeting", "verified": True, "trace": []}
    return mind.ask(route(text))


if __name__ == "__main__":
    m = Mind()
    print("Talk to The Mind — plain English or العربية. (type 'quit')")
    print("e.g.  what are the roots of x squared minus 5x plus 6")
    print("      remember that my favourite language is Arabic")
    print("      what is my favourite language\n")
    while True:
        try:
            q = input("you › ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if q.lower() in ("quit", "exit"):
            break
        if not q:
            continue
        r = reply(m, q)
        print(f"\n{r['answer']}\n   [{r['how']} | {'✓ verified' if r['verified'] else '… unverified'}]\n")
