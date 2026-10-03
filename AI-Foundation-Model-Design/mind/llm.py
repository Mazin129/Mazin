"""
llm  —  Vio's reasoning cortex (a local LLM, no cloud).

Retrieval can only hand back sentences it already stored; it cannot REASON — which is
why "rank the missing information and decide under uncertainty" came back as a CIA-triad
fact. This module gives Vio a real reasoning engine by talking to a local LLM served by
Ollama (https://ollama.com) on your own machine — no API key, nothing leaves the box.

    1.  Install Ollama (one download).
    2.  Pull a model:   ollama pull llama3.1      (or qwen2.5, mistral, phi3, …)
    3.  Start Vio. It auto-detects the running server and uses it.

Design contract — reason freely, but stay honest:
  • Exact tools still win first. Math goes to sympy, tables to the data engine, so the
    LLM never "reasons" about arithmetic it could get wrong.
  • For knowledge questions the LLM is GROUNDED: it is handed Vio's retrieved passages
    and told to answer ONLY from them and to say so when they don't cover it — so the
    no-hallucination promise holds.
  • For open reasoning (logic, planning, decision-under-uncertainty) it reasons openly,
    and the answer is labelled as reasoning, not a stored fact.

Pure stdlib client (urllib) — no new Python dependencies. If no server is running,
`.available` is False and Vio falls back to its lexical engine unchanged.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request

URL = os.environ.get("VIO_LLM_URL", "http://localhost:11434")
MODEL = os.environ.get("VIO_LLM_MODEL", "")          # empty → auto-pick from installed
_TRUE = {"1", "true", "yes", "on"}
# preference order when auto-picking an installed model (best general reasoners first).
# NOTE: a narrow fine-tune on a few hundred terse pairs tends to DAMAGE a base model
# (overfitting → degenerate, tautological answers), so we do NOT auto-prefer a local
# fine-tune here. A capable base model + retrieval over your data is the reliable path.
# You can still force any model explicitly with VIO_LLM_MODEL=<name> (e.g. a good
# fine-tune you've validated).
_PREFER = ("qwen2.5", "llama3.1", "llama3.2", "qwen2", "mistral", "gemma2", "phi3",
           "llama3", "llama2")


def _model_size(name):
    """'qwen2.5:3b' → 3.0 · 'llama3.1:8b-instruct-q4' → 8.0 · unknown → 0.0."""
    m = re.search(r":(\d+(?:\.\d+)?)b", (name or "").lower())
    return float(m.group(1)) if m else 0.0


# what makes a call worth the SLOW model (redesign prompt §14: route by task, not by
# popularity): explicit analytic verbs, or a prompt too big for a quick lookup.
_ANALYTIC = re.compile(
    r"\b(analy[sz]e|why\b|compare|versus|\bvs\b|trade-?off|design|architect|threat|"
    r"debug|troubleshoot|root ?cause|attack|hardening|incident|correlat\w*|assess\w*|"
    r"walk me|step by step|plan)\b", re.I)


def pick_model(inventory, prompt, prefer=_PREFER):
    """The model router (§14/§15), pure and testable: within the most-preferred
    installed family, SHORT/simple prompts go to the small fast model and analytic /
    heavy prompts go to the largest one. One model installed → no routing."""
    if not inventory:
        return None
    fams = {}
    for n in inventory:
        fams.setdefault((n or "").split(":")[0], []).append(n)

    def fam_rank(f):
        return next((i for i, p in enumerate(prefer)
                     if f == p or f.startswith(p + ":") or p.startswith(f)), len(prefer))

    best = min(fams, key=fam_rank)
    sizes = sorted(fams[best], key=_model_size)
    if len(sizes) == 1:
        return sizes[0]
    analytic = bool(_ANALYTIC.search(prompt or "")) or len(prompt or "") > 1200
    return sizes[-1] if analytic else sizes[0]


class LLM:
    def __init__(self, url=URL, model=MODEL, timeout=6):
        self.url = url.rstrip("/")
        self.timeout = timeout
        # local CPU inference is slow, and a big prompt (e.g. "simulate five experts
        # and debate") can take minutes — give generation a generous, configurable
        # ceiling so it finishes instead of silently timing out into a bad fallback.
        self.gen_timeout = int(os.environ.get("VIO_LLM_TIMEOUT", "300"))
        self.model = model
        self.available = False
        # ---- honesty counters -------------------------------------------------
        # Vio used to answer from lexical retrieval while LOOKING like it had reasoned.
        # These make every call auditable: how often the cortex actually ran, how long
        # it took, why it failed, and — when unavailable — the precise reason.
        self.calls = 0            # successful generations
        self.attempts = 0         # generate() entered with a live server
        self.total_ms = 0.0
        self.last_ms = 0.0
        self.last_error = ""
        self.reason = ""          # why .available is False (empty when it is True)
        self.note = ""            # a warning even when available (e.g. model not installed)
        # ---- model router + token accounting (redesign prompt §14, §21) --------
        self.inventory = []       # every installed model tag (routing + switcher)
        self.auto_picked = False  # True when no explicit model was requested
        self.last_model = ""      # the model the last generate() actually used
        self.usage_counts = {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0}
        self._detect()

    # ---- discovery ----
    def _detect(self):
        """Is a local Ollama server up, and which model should we use?"""
        try:
            tags = self._get("/api/tags", timeout=2)
        except Exception as ex:
            self.available = False
            self.reason = (f"no Ollama server answering at {self.url} ({type(ex).__name__}). "
                           "Start it with:  ollama serve")
            return
        names = [m.get("name", "") for m in (tags or {}).get("models", [])]
        self.inventory = [n for n in names if n]
        if not names:
            self.available = False
            self.reason = ("Ollama is running but has NO models installed. "
                           "Install one with:  ollama pull qwen2.5:3b")
            return
        if self.model and not any(n == self.model or n.startswith(self.model + ":")
                                  for n in names):
            # a typo'd or uninstalled VIO_LLM_MODEL silently fell through to auto-pick,
            # so the user thought they were running a model they had never installed.
            self.note = (f"VIO_LLM_MODEL={self.model!r} is NOT installed "
                         f"(installed: {', '.join(names)}) — auto-picked another model")
        if self.model and any(n == self.model or n.startswith(self.model + ":")
                              for n in names):
            self.available = True
            self.auto_picked = False              # an explicit choice — routing stays off
            return
        # auto-pick: first installed model matching the preference order, else the first
        for pref in _PREFER:
            for n in names:
                if n == pref or n.startswith(pref + ":"):
                    self.model = n
                    self.available = True
                    self.auto_picked = True
                    return
        self.model = names[0]
        self.available = True
        self.auto_picked = True

    # ---- inventory ----
    def list_models(self):
        """Names of all models installed in the local Ollama, for the model switcher."""
        try:
            tags = self._get("/api/tags", timeout=3)
        except Exception:
            return []
        return [m.get("name", "") for m in (tags or {}).get("models", []) if m.get("name")]

    def usage(self):
        """Token/call accounting for observability (prompt §21 — 'token usage' metric).
        Counts come from Ollama's eval counts; zero without a live server."""
        u = dict(self.usage_counts)
        u["avg_ms"] = round(self.total_ms / u["calls"], 1) if u["calls"] else 0.0
        return u

    # ---- generation ----
    def generate(self, prompt, system=None, temperature=0.2, max_tokens=1024):
        """One-shot completion. Returns the text, or None if the server/model fails.

        Every call is counted and timed, and every failure keeps its reason in
        .last_error — silent `except: return None` is exactly how Vio ended up
        answering from raw keyword matches while looking like it had reasoned.
        MODEL ROUTING (§14, opt-in with VIO_MODEL_ROUTING=1): when several models
        of the preferred family are installed and the user has NOT pinned a model,
        short/simple prompts go to the small fast model, analytic/heavy ones to the
        largest. An explicit VIO_LLM_MODEL or a dashboard switch disables routing."""
        if not self.available:
            self.last_error = self.reason or "no local model available"
            return None
        use_model = self.model
        if (os.environ.get("VIO_MODEL_ROUTING", "").strip().lower() in _TRUE
                and self.auto_picked and self.inventory
                and not os.environ.get("VIO_LLM_MODEL", "").strip()):
            routed = pick_model(self.inventory, prompt)
            if routed:
                use_model = routed
        self.last_model = use_model
        body = {
            "model": use_model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        if system:
            body["system"] = system
        self.attempts += 1
        t0 = time.time()
        try:
            out = self._post("/api/generate", body, timeout=self.gen_timeout)
        except Exception as ex:
            self.last_ms = (time.time() - t0) * 1000.0
            self.last_error = (f"{type(ex).__name__}: {ex} "
                               f"(after {self.last_ms/1000:.0f}s, limit "
                               f"{self.gen_timeout}s — raise VIO_LLM_TIMEOUT or use a "
                               f"smaller model)")
            return None
        self.last_ms = (time.time() - t0) * 1000.0
        self.total_ms += self.last_ms
        text = (out or {}).get("response", "").strip()
        if not text:
            self.last_error = f"model returned empty text after {self.last_ms/1000:.1f}s"
            return None
        self.last_error = ""
        self.calls += 1
        self.usage_counts["calls"] += 1
        self.usage_counts["prompt_tokens"] += int((out or {}).get("prompt_eval_count") or 0)
        self.usage_counts["completion_tokens"] += int((out or {}).get("eval_count") or 0)
        return text

    # ---- http (stdlib) ----
    def _get(self, path, timeout=None):
        req = urllib.request.Request(self.url + path, method="GET")
        with urllib.request.urlopen(req, timeout=timeout or self.timeout) as r:
            return json.loads(r.read().decode("utf-8"))

    def _post(self, path, body, timeout=None):
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(self.url + path, data=data, method="POST",
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout or self.timeout) as r:
            return json.loads(r.read().decode("utf-8"))


# --------------------------------------------------------------------------- #
# Prompt builders — keep Vio grounded and honest.
# --------------------------------------------------------------------------- #
GROUNDED_SYSTEM = (
    "You are Vio, a local networking and security assistant. You are given FACTS "
    "retrieved from the user's own knowledge base — treat them as authoritative and "
    "prefer them over your own memory if they conflict. Answer completely and "
    "concretely: define terms, explain how and why, and cite specific names, ids, "
    "interfaces, or settings from the facts when present. If the facts do not cover "
    "the question, say what is missing and ask ONE clarifying question instead of "
    "inventing device-specific details. Do not use a rigid Understanding/Logic/Answer "
    "template. Do not mention 'the context' or 'the facts' — just answer well."
)

REASON_SYSTEM = (
    "You are Vio, a careful local reasoning assistant for networking, security, and "
    "general problem-solving. Give a clear, well-structured answer with the key steps. "
    "If the question is vague or needs device/config details you do not have, say what "
    "you need and ask ONE clarifying question — do not invent specifics. Do not use a "
    "rigid Understanding/Logic/Answer template."
)

# Legacy aliases — DELIBERATE template removed (it burned tokens on meta framing and
# produced weak Understanding/Logic/Answer waffle). Keep names so older imports work.
DELIBERATE = ""
GROUNDED_SYSTEM_D = GROUNDED_SYSTEM
REASON_SYSTEM_D = REASON_SYSTEM


def grounded_prompt(question, passages, unvalidated=None):
    """Build the grounding prompt with a provenance split (redesign prompt §5/§12):
    `passages` are validated knowledge (authoritative); `unvalidated` are auto-learned
    web notes the model may use only as clearly-flagged leads — never as facts."""
    un = [p for p in (unvalidated or []) if p]
    if not passages and not un:
        return (
            f"Question: {question}\n\n"
            "No retrieved facts are available. If you can answer generally and usefully, "
            "do so briefly; if the question needs the user's config or specifics, ask one "
            "clarifying question instead of inventing them."
        )
    head = ""
    if passages:
        head += ("Facts from the user's knowledge base (authoritative):\n"
                 + "\n".join(f"- {p}" for p in passages) + "\n\n")
    if un:
        head += ("Unvalidated research notes (auto-collected from the web — NOT verified. "
                 "Treat as leads only: never state them as certain facts, and say "
                 "explicitly when your answer relies on them):\n"
                 + "\n".join(f"- {p}" for p in un) + "\n\n")
    return (
        head
        + f"Question: {question}\n\n"
        "Answer using the facts above where they apply. Quote concrete settings "
        "(policy ids, interfaces, addresses, actions). If the facts are insufficient, "
        "say exactly what is missing and ask one clarifying question."
    )


if __name__ == "__main__":
    llm = LLM()
    print("available:", llm.available, "| model:", llm.model or "(none)")
    if llm.available:
        print(llm.generate("In one sentence, what is a firewall?"))
    else:
        print("No local LLM detected. Install Ollama and `ollama pull llama3.1`.")
