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

    def __init__(self, installed, reply="ok", model="", old_server=False, thought="",
                 starve=False):
        self.installed, self.reply, self.old_server = installed, reply, old_server
        self.thought, self.starve = thought, starve
        self.bodies = []
        super().__init__(url="http://fake", model=model)

    def _get(self, path, timeout=None):
        return {"models": [{"name": n} for n in self.installed]}

    def _post(self, path, body, timeout=None):
        self.bodies.append(dict(body))
        if self.old_server and "think" in body:
            raise urllib.error.HTTPError(self.url + path, 400, "unknown field think",
                                         {}, io.BytesIO(b""))
        if body.get("think"):
            # a real thinking model: the thought comes back in its own field; a
            # starved one spends the whole budget thinking and gives no answer.
            return {"thinking": self.thought, "response": "" if self.starve else self.reply}
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
    check("a quick answer does not think", f.bodies[-1].get("think") is False)
    check("any <think> trace is stripped from the answer", out == "TCP is reliable.")

    f = Fake(["qwen3.5:4b"], reply="Check MTU first.", thought="step 1 … step 2 …")
    out = f.generate("why does the tunnel drop big packets", max_tokens=1000, think=True)
    check("a reasoning task thinks", f.bodies[-1].get("think") is True)
    check("…with its own budget on top of the answer's",
          f.bodies[-1]["options"]["num_predict"] > 1000)
    check("…the answer is only the answer", out == "Check MTU first.")
    check("…and the reasoning is kept apart", f.last_thought
          and f.last_thinking == "step 1 … step 2 …")

    f = Fake(["qwen3.5:4b"], reply="Direct answer.", thought="…", starve=True)
    check("if thinking eats the whole budget, it answers directly instead",
          f.generate("hard one", think=True) == "Direct answer."
          and f.bodies[-1].get("think") is False)

    L.THINK_MODE = "off"
    f = Fake(["qwen3.5:4b"])
    f.generate("x", think=True)
    check("VIO_LLM_THINK=off never thinks", f.bodies[-1].get("think") is False)
    L.THINK_MODE = "on"
    f.generate("x")
    check("VIO_LLM_THINK=on always thinks", f.bodies[-1].get("think") is True)
    L.THINK_MODE = "auto"

    f = Fake(["llama3.1:latest"])
    f.generate("hi", think=True)
    check("non-thinking models are sent no `think` field", "think" not in f.bodies[-1])

    f = Fake(["qwen3.5:4b"], reply="fine", old_server=True)
    check("an older Ollama that rejects `think` is retried without it",
          f.generate("hi") == "fine" and "think" not in f.bodies[-1])

    f = Fake(["qwen3.5:9b"], model="qwen3.5:9b")
    check("an explicit VIO_LLM_MODEL is honoured", f.model == "qwen3.5:9b" and not f.note)

    print("\n-- every model call knows who it is talking to --")
    import os
    import tempfile
    os.environ["VIO_DATA_DIR"] = tempfile.mkdtemp(prefix="vio_llmctx_")
    os.environ.setdefault("VIO_SEMANTIC_ASYNC", "0")
    os.environ.setdefault("VIO_TRAIN_ASYNC", "0")
    import importlib
    import reasoner
    importlib.reload(reasoner)
    m = reasoner.Mind()
    m.llm = Fake(["qwen3.5:4b"], reply="Check MTU on the tunnel.")
    m.llm.context = m._llm_context
    m.ask("remember: I run the SA-OCC FortiGate firewalls")
    m.ask("troubleshoot IPsec tunnel to branch dropping large packets")
    m.ask("why would that happen only at night")
    sysmsg = (m.llm.bodies or [{}])[-1].get("system", "")
    check("the model is told who Vio is", "senior network and security engineer" in sysmsg)
    check("…what it knows about the user", "SA-OCC FortiGate" in sysmsg)
    check("…and the recent conversation, so 'that' means something",
          "dropping large packets" in sysmsg)
    check("the conversation survives a restart", len(reasoner.Mind()._dialog) == 3)
    f = Fake(["qwen3.5:4b"])
    f.context = lambda: "PERSONAL"
    f.generate("{json please}", system="JSON only", personal=False)
    check("machine-format calls get no conversation context",
          "PERSONAL" not in f.bodies[-1].get("system", ""))

    print("=" * 72)
    print(f"  {len(PASS)} passed, {len(FAIL)} failed")
    print("\nALL PASS" if not FAIL else "\nFAILURES")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
