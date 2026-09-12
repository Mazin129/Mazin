"""
brain — Vio's decision core. ONE piece of general logic that decides how every
question gets answered, replacing the pattern-per-symptom branches that had
accumulated across the codebase.

WHY THIS EXISTS
---------------
Vio used to decide what to do by racing ~130 hand-written regexes. Each was added to
fix one bad answer, so the system could only handle situations someone had already
seen fail. Ask something new and it fell through to keyword matching and served
whatever text happened to match — a FortiGate manual sentence presented as the
device's routing table.

The fix is not more patterns. It is one general question, asked every time:

    WHAT KIND OF EVIDENCE COULD ANSWER THIS, AND DO I HAVE IT?

Everything follows from that. A question about the user's own device can only be
answered from the user's own device data — no amount of documentation will do, and
knowing that BEFORE searching is what stops prose being served as data. A question
about a concept can be answered from documentation or from the model. A question
about live values cannot be answered at all without a feed.

THE PIPELINE
------------
    understand(q)   →  what is asked; what evidence CLASS it requires
    survey(mind)    →  what evidence actually exists right now
    decide(u, ev)   →  the strategy those two facts allow (never what keywords suggest)
    verify(result)  →  did the answer actually use that evidence and answer the question

GENERALITY, CONCRETELY
----------------------
Two design choices do the work, and neither is a list of special cases:

  1. INSTANCE vs CONCEPT. "How many policies are configured" asks about one specific
     system the user owns; "what is a firewall policy" asks about the idea. The
     difference is marked in the language itself — possessives, demonstratives, a
     named host, state verbs like "configured"/"running" — not in a topic list. This
     one distinction is what routes device questions to device data, and it works for
     subjects nobody has enumerated.

  2. THE CONFIG VOCABULARY IS LEARNED, NOT LISTED. The object kinds Vio recognises
     come from the configuration actually loaded (`config router static` →  "route",
     "static"). Load a Palo Alto, a Cisco, or a device that did not exist when this
     was written, and its object kinds become answerable with no code change.
"""
from __future__ import annotations

import re

# ---------------------------------------------------------------------------- #
# Evidence classes — what a question can be answered FROM.
# ---------------------------------------------------------------------------- #
CONFIG = "config"        # the user's own device/system data
KNOWLEDGE = "knowledge"  # documentation, RFCs, taught passages
MEMORY = "memory"        # facts about the user
REASONING = "reasoning"  # derivation; no lookup can settle it
TOOL = "tool"            # computed exactly (math, tables, units)
LIVE = "live"            # changes by the minute; needs a feed Vio does not have

_NEEDS = {
    CONFIG: "your device configuration",
    KNOWLEDGE: "documentation or taught knowledge",
    MEMORY: "something you told me about yourself",
    REASONING: "reasoning",
    TOOL: "exact computation",
    LIVE: "a live data feed",
}

# ---------------------------------------------------------------------------- #
# Question form. These are general properties of questions in English, not a
# catalogue of topics — the same handful covers networking, security or cooking.
# ---------------------------------------------------------------------------- #
_FORMS = (
    ("count",        r"\bhow many\b|\bhow much\b|\bcount\b|\bnumber of\b|\btotal\b"),
    ("enumerate",    r"^\s*(show|list|display|print|dump|give me)\b|\bwhat are (all )?the\b"),
    ("compare",      r"\b(difference|differences|compare|versus|\bvs\b|better than|"
                     r"instead of)\b"),
    ("diagnose",     r"\bwhy (is|are|does|do|did|would|won'?t|can'?t)\b|not working|"
                     r"\bbroken\b|\bfail\w*|\bflap\w*|\bdrop\w*|\btimeout\b|"
                     r"can'?t (reach|connect|ping|access)|unreachable|troubleshoot|debug"),
    ("procedure",    r"\bhow (do|can|would|should) (i|we|you)\b|\bhow to\b|\bsteps\b|"
                     r"\bconfigure\b|\bset up\b|\bdeploy\b|\binstall\b"),
    ("evaluate",     r"\b(is it|are they) (safe|secure|ok|correct)\b|\brisk\w*|"
                     r"\bvulnerab\w*|\baudit\b|\breview\b|\bharden\b|\bbest practice\b|"
                     r"\bshould (i|we)\b|\bany (issues?|problems?)\b"),
    ("explain",      r"\bexplain\b|\bdescribe\b|\btell me about\b|\bwalk me through\b|"
                     r"\bhow does\b|\bhow do\b|\bwhat happens\b|\bwhy does\b"),
    ("define",       r"^\s*(what|which)\s+(is|are|was|were)\b|\bwhat'?s\b|\bdefine\b|"
                     r"\bmeaning of\b|\bstand(s)? for\b"),
)

# ---------------------------------------------------------------------------- #
# INSTANCE MARKERS — the general signal that a question is about the user's own
# system rather than about an idea. This one distinction replaces every
# per-object-kind rule that used to exist.
# ---------------------------------------------------------------------------- #
_POSSESSIVE = re.compile(r"\b(my|our|mine|ours)\b", re.I)
_DEMONSTRATIVE = re.compile(r"\b(this|these|that box|the device|the firewall|"
                            r"the router|the switch|the cluster|the server)\b", re.I)
# state verbs: they assert something IS in place somewhere, i.e. a fact about a system
_STATEFUL = re.compile(r"\b(configured|installed|deployed|running|enabled|disabled|"
                       r"set up|in place|applied|active|present|exist|exists|"
                       r"do i have|do we have)\b", re.I)
# a hostname-shaped token: SA-OCC, FGT-DC1, FW01 — capitals with a separator or digits
_HOSTNAME = re.compile(r"\b([A-Z][A-Z0-9]*(?:[-_][A-Z0-9]+)+|[A-Z]{2,}\d{1,3})\b")
_VENDOR = re.compile(r"\b(fortigate|fortios|forti|palo\s*alto|pan-?os|cisco|asa|ios-xe|"
                     r"juniper|junos|checkpoint|sophos|mikrotik|pfsense|opnsense|"
                     r"f5|big-?ip|arista|nsx)\b", re.I)

# live/real-time values Vio has no feed for. The qualifier and the noun need not be
# adjacent — "the current bitcoin price" puts the subject between them.
_LIVE = re.compile(r"\b(stock|share)\s+price|exchange rate|\bweather\b|"
                   r"(latest|current|today'?s|breaking)\s+news|"
                   r"\b(current|latest|real-?time|live|today'?s)\s+(?:\w+\s+){0,3}"
                   r"(price|value|rate|score|temperature|quote)\b", re.I)

# an actual arithmetic expression — settled by computing, never by looking up
_ARITHMETIC = re.compile(r"[0-9]\s*[-+*/^]\s*[0-9]|\b\d+\s*%\s*of\b")
# phrasings that ask for a computation
_COMPUTE = re.compile(r"\bsolve\b|\bintegrate\b|\bderivative\b|\bpercent(age)?\s+of\b|"
                      r"\bconvert\b.*\bto\b|\bsquare root\b|\bfactorial\b", re.I)

_SPLIT = re.compile(r"[\n?]+|(?<=[a-z])\s*;\s*")

_STOP = {"the", "a", "an", "is", "are", "was", "were", "of", "to", "in", "on", "for",
         "what", "which", "who", "where", "when", "why", "how", "my", "our", "me",
         "and", "or", "i", "we", "you", "your", "do", "does", "did", "it", "that",
         "this", "these", "those", "be", "been", "can", "could", "will", "would",
         "should", "show", "list", "display", "give", "tell", "explain", "describe",
         "many", "much", "any", "all", "some", "with", "from", "by", "at", "as",
         "configured", "installed", "running", "there", "have", "has", "had", "get"}


# ============================================================================ #
# 1. UNDERSTANDING
# ============================================================================ #
class Understanding:
    """A structured reading of one question. Everything downstream reads this."""

    __slots__ = ("text", "form", "subject", "host", "vendor", "kind", "qualified",
                 "requires", "why")

    def __init__(self, text):
        self.text = text
        self.form = "explain"
        self.subject = None      # the distinctive thing being asked about
        self.host = None         # a named system, if one is mentioned
        self.vendor = None
        self.kind = None         # a config object kind, when one is recognised
        self.qualified = False   # narrowed by a condition ("…that point to WAN")
        self.requires = KNOWLEDGE
        self.why = ""            # plain-language justification, shown to the user

    def summary(self):
        bits = [self.form]
        if self.kind:
            bits.append(f"{self.kind} objects")
        elif self.subject:
            bits.append(self.subject)
        if self.host:
            bits.append(f"on {self.host}")
        if self.qualified:
            bits.append("(filtered)")
        return " ".join(bits) + f"  ·  needs: {_NEEDS[self.requires]}"

    def as_dict(self):
        return {"text": self.text, "form": self.form, "subject": self.subject,
                "host": self.host, "vendor": self.vendor, "kind": self.kind,
                "qualified": self.qualified, "requires": self.requires,
                "why": self.why}


def _form_of(low):
    for name, pat in _FORMS:
        if re.search(pat, low, re.I):
            return name
    return "explain"


def _subject_of(text, low):
    """The most distinctive content word — what the question is ABOUT.

    An ACRONYM written in capitals (BGP, TLS, VLAN, OSPF) is almost always the topic,
    however short; otherwise the longest non-stopword is. Both are properties of how
    people write, so this needs no topic list and keeps working for subjects nobody
    anticipated — "why would BGP sessions flap" is about BGP, not about sessions."""
    acronyms = [w for w in re.findall(r"\b[A-Z][A-Z0-9]{1,7}\b", text or "")
                if w.lower() not in _STOP]
    if acronyms:
        return acronyms[0].lower()
    words = [w for w in re.findall(r"[a-z0-9_.-]{3,}", low) if w not in _STOP]
    return max(words, key=len) if words else None


def _kind_of(low, vocabulary):
    """Match the question against the config object kinds ACTUALLY LOADED.

    Picks by specificity weight first, phrase length second — so "static route" beats
    "route", and neither is beaten by the device noun "firewall" in a hostname."""
    if not vocabulary:
        return None
    best = None                                   # (weight, length, kind)
    for key, (kind, weight) in vocabulary.items():
        if re.search(rf"(?<![\w-]){re.escape(key)}(?![\w-])", low):
            cand = (weight, len(key), kind)
            if best is None or cand > best:
                best = cand
    return best[2] if best else None


def understand(q, vocabulary=None):
    """Read ONE question into an Understanding."""
    u = Understanding((q or "").strip())
    low = u.text.lower()
    if not low:
        return u

    u.form = _form_of(low)
    u.subject = _subject_of(u.text, low)
    u.qualified = bool(re.search(
        r"\b(that|which|with|without|pointing|matching|using|where|containing|"
        r"having|via|through)\b", low))

    mv = _VENDOR.search(u.text)
    if mv:
        u.vendor = mv.group(1)
    for cand in _HOSTNAME.findall(u.text):
        if not _VENDOR.fullmatch(cand):
            u.host = cand
            break

    u.kind = _kind_of(low, vocabulary or {})

    # ---- the decision everything hangs on: what class of evidence is required --
    if _LIVE.search(low):
        u.requires, u.why = LIVE, "it asks for a value that changes by the minute"
        return u

    # An arithmetic expression is settled by computing it — the question form is
    # irrelevant, which is why this is checked on the expression, not the phrasing.
    if _ARITHMETIC.search(u.text) or (_COMPUTE.search(u.text) and u.form != "define"):
        u.requires, u.why = TOOL, "it can be computed exactly"
        return u

    if re.search(r"\b(about|know)\s+(me|myself)\b|\b(who|what)\s+am\s+i\b|"
                 r"\bmy name\b", low):
        u.requires, u.why = MEMORY, "it asks about you"
        return u

    # Nouns that name entries IN a system rather than ideas about one. Asking to list
    # or count "objects"/"entries"/"rules" is asking about a specific system's contents
    # even when the object kind itself isn't one this config happens to contain — and
    # answering "no such objects here" beats falling through to documentation.
    _CONTENTS = re.search(r"\b(objects?|entries|entr(y|ies)|rules?|table|tables|"
                          r"stanzas?|sections?|records?)\b", low)
    if u.form in ("count", "enumerate") and _CONTENTS:
        u.requires = CONFIG
        u.why = "it asks what a specific system contains"
        return u

    # INSTANCE vs CONCEPT — the general rule.
    instance = bool(_POSSESSIVE.search(low) or _STATEFUL.search(low) or u.host
                    or (u.kind and _DEMONSTRATIVE.search(low)))
    # Enumerating or counting objects is inherently about a specific system: you
    # cannot list or count the contents of an idea.
    if u.kind and u.form in ("count", "enumerate"):
        instance = True

    if instance and (u.kind or u.host or _STATEFUL.search(low)):
        u.requires = CONFIG
        u.why = ("it asks about the state of a specific system"
                 + (f" ({u.host})" if u.host else "")
                 + " — documentation about the feature cannot answer it")
        return u

    if u.form in ("diagnose", "procedure", "evaluate", "compare"):
        u.requires, u.why = REASONING, f"a {u.form} question is worked out, not looked up"
        return u

    u.requires, u.why = KNOWLEDGE, "it asks about a concept"
    return u


def split_questions(q):
    """One message can hold several questions. Answering them as one bag of keywords
    is how a routes question and a policies question ended up answering each other."""
    parts = [p.strip(" .\t") for p in _SPLIT.split(q or "")]
    parts = [p for p in parts if len(p.split()) >= 2]
    return parts or [(q or "").strip()]


def read(q, vocabulary=None):
    """Read a (possibly multi-part) message: one Understanding per question."""
    return [understand(p, vocabulary) for p in split_questions(q)]


# ============================================================================ #
# 2. EVIDENCE SURVEY — what Vio actually holds, right now
# ============================================================================ #
class Evidence:
    """An inventory of answering capacity. Computed fresh; never assumed."""

    __slots__ = ("config_objects", "config_kinds", "passages", "config_passages",
                 "facts", "model", "web", "vocabulary")

    def __init__(self):
        self.config_objects = []
        self.config_kinds = {}
        self.passages = 0
        self.config_passages = 0
        self.facts = 0
        self.model = None        # model name, or None
        self.web = False
        self.vocabulary = {}

    def has(self, cls):
        return {CONFIG: bool(self.config_objects),
                KNOWLEDGE: self.passages > 0,
                MEMORY: self.facts > 0,
                REASONING: bool(self.model),
                TOOL: True,
                LIVE: False}[cls]

    def as_dict(self):
        return {"config_objects": len(self.config_objects),
                "config_kinds": dict(self.config_kinds), "passages": self.passages,
                "facts": self.facts, "model": self.model, "web": self.web}


# Words that name a DEVICE as often as an object class. "on SA-OCC firewall" is a
# machine; "firewall policy" is an object. They must never outrank the distinctive
# word of a kind, or "show static route on SA-OCC firewall" reads as a policy query.
_DEVICE_NOUNS = {"firewall", "router", "switch", "device", "gateway", "appliance",
                 "system", "box", "node", "cluster", "server"}


def _forms_of(word):
    """Plural/singular variants of one word, without a stemming dependency."""
    w = word.lower()
    out = {w}
    # pluralise — note a singular can already end in "s" ("address", "class"), so the
    # "-es" form is always offered, not only for words that don't end in s.
    if w.endswith("y") and len(w) > 2:
        out.add(w[:-1] + "ies")
    else:
        out.add(w + "s")
    if w.endswith(("s", "x", "z", "ch", "sh")):
        out.add(w + "es")
    # singularise
    if w.endswith("ies") and len(w) > 4:
        out.add(w[:-3] + "y")
    if w.endswith("es") and len(w) > 3:
        out.add(w[:-2])
    if w.endswith("s") and len(w) > 2:
        out.add(w[:-1])
    return out


def config_vocabulary(objects):
    """Build the recognisable config vocabulary FROM THE LOADED CONFIG.

    Returns {word or phrase: (kind, weight)}. Weight encodes specificity so an
    ambiguous word cannot beat a precise one:

        3  the full kind phrase          "router static", "static router"
        2  the kind's distinctive word   "static", "policy", "address"
        1  a device noun in the kind     "router", "firewall"

    Nothing here is hardcoded per vendor: load a Palo Alto or a device this code has
    never seen and its object kinds become answerable with no change."""
    vocab = {}

    def put(key, kind, weight):
        cur = vocab.get(key)
        if cur is None or weight > cur[1]:
            vocab[key] = (kind, weight)

    for o in objects:
        kind = (o.kind or "").strip().lower()
        if not kind:
            continue
        words = kind.split()
        put(kind, kind, 3)
        if len(words) > 1:
            put(" ".join(reversed(words)), kind, 3)
        for w in words:
            weight = 1 if w in _DEVICE_NOUNS else 2
            for f in _forms_of(w):
                put(f, kind, weight)
        # "config router static" is the routing table; users say "route"/"routes"
        if "static" in words and "router" in words:
            for f in _forms_of("route"):
                put(f, kind, 2)
            put("static route", kind, 3)
            put("routing table", kind, 3)
    return vocab


def survey(mind):
    """Take stock of everything that could answer a question."""
    ev = Evidence()
    docs = getattr(getattr(mind, "lib", None), "docs", []) or []
    ev.passages = len(docs)
    try:
        import configparse
        ev.config_objects = configparse.parse_many(docs)
        for o in ev.config_objects:
            k = (o.kind or "?").strip()
            ev.config_kinds[k] = ev.config_kinds.get(k, 0) + 1
        ev.vocabulary = config_vocabulary(ev.config_objects)
    except Exception:
        pass
    try:
        ev.config_passages = sum(1 for d in docs if mind._is_configish_snippet(d))
    except Exception:
        pass
    try:
        ev.facts = len(mind.mem["facts"])
    except Exception:
        pass
    llm = getattr(mind, "llm", None)
    if llm is not None and getattr(llm, "available", False):
        ev.model = llm.model
    try:
        import websearch
        ev.web = websearch.net_enabled()
    except Exception:
        pass
    return ev


# ============================================================================ #
# 3. DECISION — strategy comes from evidence, never from keywords
# ============================================================================ #
class Plan:
    __slots__ = ("strategy", "reason", "missing", "understanding")

    def __init__(self, strategy, reason, understanding, missing=""):
        self.strategy = strategy
        self.reason = reason
        self.missing = missing
        self.understanding = understanding

    def as_dict(self):
        return {"strategy": self.strategy, "reason": self.reason,
                "missing": self.missing}


def decide(u: Understanding, ev: Evidence) -> Plan:
    """Choose how to answer, from what the question needs vs what exists.

    Returns a strategy name the caller executes. The point is that an impossible
    question is identified HERE — before any search — so nothing downstream can
    improvise an answer out of whatever text happened to match."""
    if u.requires == LIVE:
        return Plan("abstain", "no live feed exists for this", u,
                    missing="a real-time data source")

    if u.requires == CONFIG:
        if not ev.config_objects:
            return Plan("need-config",
                        "this asks about a specific system and no device "
                        "configuration is loaded", u,
                        missing="the device configuration")
        wanted = u.kind or u.subject
        # Either the named kind isn't in this config, or the question named a kind the
        # loaded config has no vocabulary for at all. Both mean the same thing to the
        # user — say which kinds DO exist rather than falling through to documentation.
        unknown = (u.kind and u.kind not in ev.config_kinds
                   and not any(u.kind in k for k in ev.config_kinds))
        if unknown or (u.kind is None and u.form in ("count", "enumerate")):
            return Plan("need-config-kind",
                        f"a configuration is loaded, but it contains no "
                        f"'{wanted}' objects", u,
                        missing=f"the {wanted} section of the configuration")
        if u.form in ("count", "enumerate") and not u.qualified:
            return Plan("config-exact",
                        "a loaded configuration answers this exactly, with no model", u)
        return Plan("config-analyse",
                    "answer by analysing the loaded configuration", u)

    if u.requires == MEMORY:
        return Plan("memory" if ev.facts else "need-memory",
                    "answered from what you told me" if ev.facts
                    else "you have not told me this yet", u,
                    missing="" if ev.facts else "a fact about you (use `remember:`)")

    if u.requires == TOOL:
        return Plan("tool", "computed exactly", u)

    if u.requires == REASONING:
        if ev.model:
            return Plan("reason", f"worked through with the local model ({ev.model})", u)
        if ev.passages:
            return Plan("grounded",
                        "no reasoning model is running — answering from stored "
                        "knowledge instead", u, missing="a running local model")
        return Plan("abstain", "this needs reasoning and no model is running", u,
                    missing="a running local model (`ollama serve`)")

    # KNOWLEDGE
    if ev.passages and ev.model:
        return Plan("grounded", "answered from stored knowledge, composed by the model", u)
    if ev.passages:
        return Plan("grounded", "answered from stored knowledge", u)
    if ev.model:
        return Plan("reason", "nothing stored on this — answering from the model", u)
    return Plan("abstain", "nothing stored on this and no model is running", u,
                missing="knowledge on this topic, or a running local model")


def shortfall_message(plan: Plan, ev: Evidence) -> str:
    """What to say when the evidence needed does not exist. Names what was searched,
    what is held, and the one action that fixes it — never a vague apology."""
    u = plan.understanding
    if plan.strategy == "need-config":
        held = (f"I hold {ev.passages} passage(s); "
                + (f"{ev.config_passages} look config-shaped but none parsed into "
                   "complete objects (a stanza was probably cut mid-block)."
                   if ev.config_passages else
                   "all of them are prose/documentation, not configuration."))
        return (f"I can't answer that from what I have. You're asking about "
                f"{'the state of ' + u.host if u.host else 'a specific system'}"
                f", which only a device configuration can answer — documentation "
                f"about the feature is not an answer to it.\n\n{held}\n\n"
                "Upload the configuration (📄 the `.conf` backup, or the output of "
                "`show full-configuration`) and ask again — I'll read the objects "
                "straight out of it. Run `config status` to see what I currently hold.")
    if plan.strategy == "need-config-kind":
        want = u.kind or u.subject or "those"
        have = ", ".join(f"{n}× `{k}`" for k, n in sorted(ev.config_kinds.items()))
        return (f"A configuration is loaded, but it has no `{want}` objects in it.\n\n"
                f"What it does contain: {have}.\n\n"
                f"Ask me about any of those and I'll list them exactly. If the {want} "
                "section lives in a different file or vdom, upload that part and I'll "
                "read it too.")
    if plan.strategy == "need-memory":
        return ("I don't know that about you yet. Tell me with  remember: <fact>  "
                "and I'll use it from then on.")
    if u.requires == LIVE:
        return ("I can't look up live or real-time data — I have no market, weather or "
                "news feed, and I won't guess a number that changes by the minute.")
    miss = plan.missing or "evidence"
    return (f"I don't have what this needs ({miss}), so I won't guess at it.\n\n"
            f"Why: {plan.reason}.")


# ============================================================================ #
# 4. VERIFICATION — an answer must survive this to be shown as one
# ============================================================================ #
# phrases that mean "this isn't really an answer" — never verified
_WEAK = re.compile(
    r"i'?m not confident|treat it as a lead|didn'?t finish|couldn'?t finish|"
    r"i don'?t know( that)? yet|web search failed|couldn'?t (read|find|cover)|"
    r"no (open )?results|not enough|internet (research )?(is )?(currently )?off|"
    r"needs? (internet|web) access|didn'?t answer in time|timed out", re.I)

_FACTUAL_SEC = re.compile(
    r"\b(mtls|bgp|ospf|eigrp|firewall|vpn|tls|ssl|iam|s3|vlan|nat|acl|cve|"
    r"vulnerab\w*|exploit|secure|security|encrypt\w*|kubernetes|k8s|istio|port|"
    r"protocol|cidr|subnet|route|routing|polic\w*|attack|breach|exfiltrat\w*|"
    r"ransomware|malware|rfc|dns|dhcp|ipsec|wireguard|conntrack|mtu|ecmp)\b", re.I)

_INTRINSIC = ("symbolic", "quadratic", "function plot", "exact tool", "clock",
              "skill:", "data analysis", "math", "greeting", "library summary",
              "sources", "gaps", "agents", "who-answers", "library-write",
              "memory-write", "skill-write", "config status", "understanding")

_GROUNDED = ("planning (grounded", "reasoning over knowledge", "world model",
             "reasoning (causal", "reasoning (deductive", "reasoning (rule",
             "synthesis", "analysis over your config", "episodic")

# a device-config directive line: `config router static`, `set gateway 1.1.1.1`, `end`
_CFG_STUB = re.compile(r"^\s*(config|edit|set|unset|next|end|append|select)\b", re.I)
# a bare heading / dangling label: "Per Route", "Confirm the policy:", "Example 1"
_LABEL_STUB = re.compile(r"^[\w ()/-]{1,40}:?$")
# paths whose short output is exact by construction — never "fragments"
_EXACT = ("exact listing", "exact count", "library-write", "memory-write",
          "skill-write", "correction-write", "feedback", "calibration",
          "consolidation", "config status")


def is_factual_or_security(q):
    return bool(_FACTUAL_SEC.search(q or ""))


def has_evidence(evidence):
    e = evidence or {}
    return bool(e.get("hits") or e.get("facts") or e.get("sources"))


def _is_intrinsic(how):
    h = (how or "").lower()
    return any(k in h for k in _INTRINSIC)


def _heading_shaped(t):
    """A heading is Title Case or ends with a colon; a statement has a lowercase word.

    Shape beats a verb list: in this domain 'route', 'block' and 'allow' are nouns as
    often as verbs, so a verb test lets 'Per Route' through. But a real statement —
    'OSPF is link-state', 'TLS encrypts traffic' — always carries a lowercase word."""
    if t.endswith(":"):
        return True
    words = t.rstrip(".").split()
    return all(w[:1].isupper() or w[:1].isdigit() or not w[:1].isalpha() for w in words)


def is_stub_passage(text):
    """True for a retrieved passage carrying no information on its own: a lone config
    directive or a dangling heading, chunked away from its body. Grounding on these
    produces text that looks sourced and says nothing. A MULTI-LINE stanza is not a
    stub — it has `set` lines and real content."""
    t = (text or "").strip()
    if not t or "\n" in t:
        return False
    words = t.split()
    if len(words) > 8:
        return False
    if _CFG_STUB.match(t):
        return True
    return bool(_LABEL_STUB.match(t)) and len(words) <= 4 and _heading_shaped(t)


def _units(ans):
    body = re.split(r"\n\s*(?:Grounded on|Sources|Sources I read)\s*:", ans or "")[0]
    out = []
    for p in re.split(r"(?:\n+|(?<=[.!?:])\s+)", body):
        p = p.strip().lstrip("•-*·").strip()
        if p:
            out.append(p)
    return out


def looks_fragmentary(ans):
    """True when the 'answer' is a pile of config directives or dangling labels."""
    units = _units(ans)
    if len(units) < 2:
        return False
    stubs = sum(1 for u in units
                if _CFG_STUB.match(u) or (_LABEL_STUB.match(u) and len(u.split()) <= 4))
    if stubs / len(units) >= 0.5:
        return True
    return all(len(u.split()) < 6 for u in units)


def fragment_reply(ans, q):
    leads = _units(ans)[:6]
    lead_txt = ("\n".join(f"  • {l}" for l in leads)) if leads else "  (nothing usable)"
    return ("I don't have a real answer to this. What I retrieved is only fragments — "
            "device-config lines and stray sentences from documentation — not anything "
            "that answers the question, so I won't dress it up as one.\n\n"
            f"The fragments (leads only, not an answer):\n{lead_txt}\n\n"
            "To answer it properly I need one of:\n"
            "  • the real device configuration — upload 📄 the `.conf` backup or the "
            "output of `show full-configuration`; or\n"
            "  • the local reasoning model running — start it with `ollama serve`.\n\n"
            "Run  python doctor.py  to see which of the two is missing.")


def citations(evidence):
    """A short, honest 'where this came from' footer, or '' if nothing to cite."""
    e = evidence or {}
    src = [s for s in (e.get("sources") or []) if s]
    if src:
        return "Sources:\n" + "\n".join(f"  • {s}" for s in src[:5])
    exc = [x for x in (e.get("excerpts") or [])
           if x and x.strip() and not is_stub_passage(x)]
    if exc:
        return "Grounded on:\n" + "\n".join(
            "  • " + x.strip().replace("\n", " ")[:130] + ("…" if len(x) > 130 else "")
            for x in exc[:3])
    return ""


def verify(result, evidence, q):
    """The final gate every answer passes. Returns a new dict — never mutates."""
    r = dict(result or {})
    ans = (r.get("answer") or "").strip()
    how = r.get("how") or ""
    intrinsic = _is_intrinsic(how)

    # 1. empty / too-short / weak → cannot be verified
    if not ans or len(ans) < 2 or _WEAK.search(ans):
        r["verified"] = False

    # 2. a pile of scraps is not an answer, whatever path produced it. Replace it:
    #    leaving the scraps as the body is what made Vio look like it had answered.
    if ans and not any(k in how.lower() for k in _EXACT) and looks_fragmentary(ans):
        return {**r, "answer": fragment_reply(ans, q), "verified": False,
                "confidence": min(float(r.get("confidence") or 0.1), 0.1),
                "how": "fragments (not an answer)",
                "trace": list(r.get("trace") or [])
                + [f"quality gate: '{how or 'unknown path'}' returned "
                   f"{len(_units(ans))} fragment(s), not an answer"]}

    # 3. a factual/security claim with no local evidence is never "verified"
    hl = how.lower()
    grounded = any(g in hl for g in _GROUNDED)
    if (not intrinsic and not grounded and "web research" not in hl
            and is_factual_or_security(q) and not has_evidence(evidence)):
        if r.get("verified"):
            r["verified"] = False
            if "unverified" not in hl:
                r["how"] = how + " · unverified (no local evidence)"

    # 4. cite a verified, grounded answer (never double-cite)
    if r.get("verified"):
        low = ans.lower()
        if "source" not in low and "grounded on" not in low:
            c = citations(evidence)
            if c:
                r["answer"] = ans + "\n\n" + c
    return r


# ============================================================================ #
# 5. REPORTING — let the user see and correct the reading
# ============================================================================ #
def explain(q, ev=None):
    """Human-readable account of how Vio read a question and what it will do."""
    vocab = ev.vocabulary if ev else {}
    us = read(q, vocab)
    lines = []
    if len(us) > 1:
        lines.append(f"I read this as **{len(us)} separate questions**:")
        for i, u in enumerate(us, 1):
            lines.append(f"  {i}. “{u.text}” → {u.summary()}")
        lines.append("")
    u = us[0]
    lines.append(f"**{u.summary()}**")
    lines.append("")
    lines.append(f"  question form : {u.form}")
    lines.append(f"  about         : {u.kind or u.subject or '(not identified)'}")
    lines.append(f"  system named  : {u.host or '(none)'}")
    lines.append(f"  vendor        : {u.vendor or '(none)'}")
    lines.append(f"  needs         : {_NEEDS[u.requires]} — {u.why}")
    if ev is not None:
        plan = decide(u, ev)
        lines.append(f"  I have        : {len(ev.config_objects)} config object(s), "
                     f"{ev.passages} passage(s), {ev.facts} fact(s), "
                     f"model {ev.model or 'NOT running'}")
        lines.append(f"  plan          : {plan.strategy} — {plan.reason}")
        if plan.missing:
            lines.append(f"  missing       : {plan.missing}")
    return "\n".join(lines)
