"""
test_llm — model choice and Qwen3.5 "thinking" handling, against a fake Ollama.

Run:  python test_llm.py
"""
from __future__ import annotations

import io
import sys
import urllib.error

import llm as L

PASS, FAIL = [], []


def check(name, cond):
    (PASS if cond else FAIL).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}")


class Fake(L.LLM):
    """An LLM whose HTTP layer is a stub: `installed` models, a canned reply, and
    optionally an old server that rejects the `think` field."""

    def __init__(self, installed, reply="ok", model="", old_server=False):
        self.installed, self.reply, self.old_server = installed, reply, old_server
        self.bodies = []
        super().__init__(url="http://fake", model=model)

    def _get(self, path, timeout=None):
        return {"models": [{"name": n} for n in self.installed]}

    def _post(self, path, body, timeout=None):
        self.bodies.append(dict(body))
        if self.old_server and "think" in body:
            raise urllib.error.HTTPError(self.url + path, 400, "unknown field think",
                                         {}, io.BytesIO(b""))
        return {"response": self.reply}


def main():
    print("=" * 72)
    print("  LLM — model choice and thinking-model handling")
    print("=" * 72)

    f = Fake(["llama3.1:latest", "qwen3.5:4b", "mistral:latest"])
    check("qwen3.5 is auto-picked first", f.model == "qwen3.5:4b")
    check("no qwen2.5 left in the preference order",
          not any(p.startswith("qwen2") for p in L._PREFER))

    f = Fake(["qwen3.5:4b"], reply="<think>\nlong hidden trace\n</think>\n\nTCP is reliable.")
    out = f.generate("what is tcp")
    check("thinking is switched off for qwen3.5", f.bodies[-1].get("think") is False)
    check("any <think> trace is stripped from the answer", out == "TCP is reliable.")

    f = Fake(["llama3.1:latest"])
    f.generate("hi")
    check("non-thinking models are sent no `think` field", "think" not in f.bodies[-1])

    f = Fake(["qwen3.5:4b"], reply="fine", old_server=True)
    check("an older Ollama that rejects `think` is retried without it",
          f.generate("hi") == "fine" and "think" not in f.bodies[-1])

    f = Fake(["qwen3.5:9b"], model="qwen3.5:9b")
    check("an explicit VIO_LLM_MODEL is honoured", f.model == "qwen3.5:9b" and not f.note)

    print("=" * 72)
    print(f"  {len(PASS)} passed, {len(FAIL)} failed")
    print("\nALL PASS" if not FAIL else "\nFAILURES")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
