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
import urllib.error
import urllib.request

URL = os.environ.get("VIO_LLM_URL", "http://localhost:11434")
MODEL = os.environ.get("VIO_LLM_MODEL", "")          # empty → auto-pick from installed
# preference order when auto-picking an installed model (best general reasoners first)
_PREFER = ("llama3.1", "llama3.2", "qwen2.5", "qwen2", "mistral", "gemma2", "phi3",
           "llama3", "llama2")


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
        self._detect()

    # ---- discovery ----
    def _detect(self):
        """Is a local Ollama server up, and which model should we use?"""
        try:
            tags = self._get("/api/tags", timeout=2)
        except Exception:
            self.available = False
            return
        names = [m.get("name", "") for m in (tags or {}).get("models", [])]
        if not names:
            self.available = False
            return
        if self.model and any(n == self.model or n.startswith(self.model + ":")
                              for n in names):
            self.available = True
            return
        # auto-pick: first installed model matching the preference order, else the first
        for pref in _PREFER:
            for n in names:
                if n == pref or n.startswith(pref + ":"):
                    self.model = n
                    self.available = True
                    return
        self.model = names[0]
        self.available = True

    # ---- generation ----
    def generate(self, prompt, system=None, temperature=0.2, max_tokens=1024):
        """One-shot completion. Returns the text, or None if the server/model fails."""
        if not self.available:
            return None
        body = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        if system:
            body["system"] = system
        try:
            out = self._post("/api/generate", body, timeout=self.gen_timeout)
        except Exception:
            return None
        text = (out or {}).get("response", "").strip()
        return text or None

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
    "You are Vio, a careful local assistant. Answer the user's question USING ONLY the "
    "context passages provided. Do not add facts that are not in the context. If the "
    "context does not contain the answer, say plainly that you don't have that "
    "information. Be concise, direct, and correct. Do not mention 'the context'."
)

REASON_SYSTEM = (
    "You are Vio, a careful local reasoning assistant. Think the problem through and "
    "give a clear, well-structured answer: logic, planning, analysis, comparisons, and "
    "decisions under uncertainty are your job. Show the key steps briefly. If the "
    "question requires specific real-world facts you are not sure of, say so honestly "
    "rather than inventing them."
)

# The human-like loop the user asked for: understand the question, decide the logic,
# THEN answer — and make those steps visible. Appended to whichever system prompt runs.
DELIBERATE = (
    " Think like a person before replying, and show it in exactly this shape:\n"
    "Understanding: <one line — what the user is really asking>\n"
    "Logic: <one line — the approach/steps you'll use to get there>\n"
    "Answer: <your actual answer, as long as it needs to be>"
)

GROUNDED_SYSTEM_D = GROUNDED_SYSTEM + DELIBERATE
REASON_SYSTEM_D = REASON_SYSTEM + DELIBERATE


def grounded_prompt(question, passages):
    ctx = "\n".join(f"- {p}" for p in passages)
    return f"Context passages:\n{ctx}\n\nQuestion: {question}\n\nAnswer:"


if __name__ == "__main__":
    llm = LLM()
    print("available:", llm.available, "| model:", llm.model or "(none)")
    if llm.available:
        print(llm.generate("In one sentence, what is a firewall?"))
    else:
        print("No local LLM detected. Install Ollama and `ollama pull llama3.1`.")
