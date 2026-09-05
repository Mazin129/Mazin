"""
agents  —  Stage 1 of the agentic architecture (see the blueprint).

This introduces the AGENT CONTRACT and a REGISTRY + MASTER, and wraps Vio's
existing engines as agents WITHOUT changing the live router. Nothing here alters
behaviour: Mind.ask() still uses the proven _ask_core chain. The new
Mind.ask_agentic() routes through the master and falls back to _ask_core for any
capability not yet migrated — so the two paths agree, and later stages can move
logic out of _ask_core into agents one at a time.

The contract every agent implements:
    name         — stable identifier, shown in provenance
    domains      — tags (networking, math, memory, …) for classification/telemetry
    permissions  — {"read"} advisory (safe) · add "write"/"network" for acting agents
    score(q,ctx) — 0..1 fit for this query (cheap; no side effects)
    run(q,ctx)   — do the work → Result, or None if it turns out not to apply
    validate(r)  — is the result trustworthy enough to return?
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

try:
    from cognition.planning import is_plan_request
except Exception:                                  # pragma: no cover
    def is_plan_request(_q):
        return False


@dataclass
class Result:
    answer: str
    how: str = ""
    verified: bool = False
    confidence: float = 0.5
    agent: str = ""
    trace: list = field(default_factory=list)

    def as_dict(self):
        return {"answer": self.answer, "how": self.how, "verified": self.verified,
                "confidence": self.confidence, "agent": self.agent, "trace": self.trace}

    @classmethod
    def from_dict(cls, d, agent=""):
        if not d or not d.get("answer"):
            return None
        return cls(answer=d["answer"], how=d.get("how", ""), verified=bool(d.get("verified")),
                   confidence=float(d.get("confidence", 0.5)), agent=agent,
                   trace=list(d.get("trace") or []))


class Agent:
    name = "agent"
    domains: tuple = ()
    permissions = frozenset({"read"})

    def __init__(self, mind):
        self.mind = mind

    def score(self, q, ctx):            # 0..1 — how well this agent fits
        return 0.0

    def run(self, q, ctx):              # -> Result | None
        raise NotImplementedError

    def validate(self, result, ctx):    # gate before returning
        return bool(result and result.answer)


# --------------------------------------------------------------------------- #
# Concrete agents — thin wrappers over Vio's existing, proven engines.
# --------------------------------------------------------------------------- #
class SkillAgent(Agent):
    name, domains = "skill", ("memory", "reflex")

    def score(self, q, ctx):
        return 0.97 if self.mind.skills.match(q) else 0.0

    def run(self, q, ctx):
        sk = self.mind.skills.match(q)
        if not sk:
            return None
        return Result(sk[1], how=f"skill: {sk[0]}", verified=True, confidence=0.9)


class MathAgent(Agent):
    name, domains = "math", ("math",)

    def score(self, q, ctx):
        return 0.92 if self.mind.math.looks_mathy(q) else 0.0

    def run(self, q, ctx):
        if not self.mind.math.looks_mathy(q):
            return None
        ans, trace, ok = self.mind.math.handle(q)
        if ans is None:
            return None
        return Result(ans, how="symbolic reasoning (sympy)", verified=ok,
                      confidence=0.95 if ok else 0.5, trace=list(trace or []))


class PlannerAgent(Agent):
    name, domains = "planner", ("planning",)

    def score(self, q, ctx):
        return 0.7 if is_plan_request(q) else 0.0

    def run(self, q, ctx):
        if not is_plan_request(q):
            return None
        return Result.from_dict(self.mind.planner.plan(q))


class WorldModelAgent(Agent):
    name, domains = "world_model", ("reasoning", "simulation")

    def score(self, q, ctx):
        return 0.6

    def run(self, q, ctx):
        return Result.from_dict(self.mind.world.answer(q))


class ReasoningAgent(Agent):
    name, domains = "reasoning", ("reasoning",)

    def score(self, q, ctx):
        return 0.55

    def run(self, q, ctx):
        return Result.from_dict(self.mind.reasoning.answer(q))


class ConfigAgent(Agent):
    name, domains = "config", ("networking", "security", "config")

    def score(self, q, ctx):
        return 0.5

    def run(self, q, ctx):
        return Result.from_dict(self.mind._aggregate_answer(q))


class MemoryAgent(Agent):
    name, domains = "memory", ("memory",)
    # _episodic_recall returns a generic "nothing yet" message for ANY query, so this
    # agent must only claim genuine recall-intent questions — otherwise it swallows math
    # and retrieval queries that should fall through to their own agents / the core router.
    _RECALL = re.compile(
        r"what did we|what have we|did we (talk|discuss)|what did i ask|talked about|"
        r"remember when|last time we|our (past |previous )?(chat|conversation)|"
        r"about (me|myself)|who am i|know about me", re.I)

    def score(self, q, ctx):
        return 0.8 if self._RECALL.search(q) else 0.0

    def run(self, q, ctx):
        if not self._RECALL.search(q):
            return None
        return Result.from_dict(self.mind._episodic_recall(q))


# order is only a tie-breaker; each agent self-skips (returns None) when N/A.
DEFAULT_AGENTS = (SkillAgent, MathAgent, PlannerAgent, WorldModelAgent,
                  ReasoningAgent, ConfigAgent, MemoryAgent)


class Registry:
    def __init__(self):
        self.agents = []

    def register(self, agent):
        self.agents.append(agent)
        return agent

    def ranked(self, q, ctx, threshold=0.0):
        scored = [(a.score(q, ctx), a) for a in self.agents]
        scored = [(s, a) for s, a in scored if s > threshold]
        scored.sort(key=lambda sa: sa[0], reverse=True)
        return scored


class Master:
    """The control plane: score → dispatch → validate, highest-fit first, first
    validated result wins. Returns None if no agent handled the query (the caller
    then falls back to the legacy router)."""

    def __init__(self, registry):
        self.registry = registry

    def handle(self, q, ctx=None):
        ctx = ctx or {}
        for _score, agent in self.registry.ranked(q, ctx):
            try:
                res = agent.run(q, ctx)
            except Exception:
                res = None
            if res and agent.validate(res, ctx):
                res.agent = agent.name
                return res
        return None


def build_master(mind):
    reg = Registry()
    for cls in DEFAULT_AGENTS:
        reg.register(cls(mind))
    return Master(reg), reg
