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
from reasoner import Mind

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


def route(text):
    """Map free text -> a structured query for The Mind."""
    t = text.lower().strip()

    # explicit teaching / memory (natural phrasing)
    if t.startswith(("remember that", "remember")) or t.startswith(("تذكر",)):
        fact = re.sub(r"^(remember that|remember|تذكر ان|تذكر أن|تذكر)\s*", "", text, flags=re.I).strip(" ؟?.")
        return f"remember: {fact}"
    if t.startswith(("teach that", "teach", "note that")) or t.startswith(("علم", "علمك")):
        fact = re.sub(r"^(teach that|teach|note that|علم ان|علمك|علم)\s*", "", text, flags=re.I).strip(" ؟?.")
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

    # a bare arithmetic/algebra expression ("15 times 12 plus 7") — decided by what
    # actually survives normalisation, not by question words.
    norm = normalize_math(t)
    if re.search(r"[+\-*/^]", norm) and re.search(r"[0-9x]", norm):
        return norm

    # otherwise a question / statement -> The Mind retrieves from library + memory
    return text


GREET = re.compile(r"^(hi|hello|hey|salam|salaam|مرحبا|سلام|اهلا|أهلا)\b", re.I)


def reply(mind, text):
    if GREET.match(text.strip()):
        return {"answer": "Hello. Ask me to solve/integrate/simplify something, teach me a "
                          "fact ('remember that ...'), or ask what I know. (English or العربية)",
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
