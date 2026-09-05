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

import os
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


# permission tokens — an agent declares what it may do. Advisory agents are read-only
# and always safe; write/network make an agent an ACTING agent, gated by the guardrail.
READ, WRITE, NETWORK = "read", "write", "network"


class Agent:
    name = "agent"
    domains: tuple = ()
    permissions = frozenset({READ})

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
_CMD = re.compile(r"^\s*(teach|remember|skill)\s*:", re.I)


class SkillAgent(Agent):
    name, domains = "skill", ("memory", "reflex")

    def score(self, q, ctx):
        # never shadow a teach:/remember:/skill: command with a user reflex
        if _CMD.match(q):
            return 0.0
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


def agent_from_how(how):
    """Map a result's `how` string to a canonical agent name, for provenance on
    answers produced by the catch-all core router (until every branch is its own agent)."""
    h = (how or "").lower()
    table = [("symbolic", "math"), ("quadratic", "math"), ("function plot", "math"),
             ("exact tool", "tools"), ("clock", "tools"),
             ("skill:", "skill"), ("generation", "generation"),
             ("world model", "world_model"), ("planning", "planner"),
             ("reasoning over knowledge", "knowledge"), ("retrieval", "knowledge"),
             ("data analysis", "data"), ("analysis over your", "config"),
             ("reasoning (llm", "reasoning"), ("reasoning (", "reasoning"),
             ("library", "memory"), ("episodic", "memory"), ("memory", "memory"),
             ("github", "research"), ("learned from github", "research"),
             ("consolidation", "self_improvement"), ("calibration", "self_improvement"),
             ("feedback", "feedback"), ("greeting", "core"), ("no-source", "core"),
             ("llm-timeout", "knowledge")]
    for key, name in table:
        if key in h:
            return name
    return "core"


class CoreRouterAgent(Agent):
    """The FRONT of the proven router (commands, tools, generation, math, world,
    reasoning, planning, aggregate) as one agent. It runs _core_front, which returns
    None for a pure knowledge question — so the KnowledgeAgent below handles those, while
    the order-sensitive front branches always get first crack here. Provenance is derived
    from the `how` the core produced."""
    name, domains = "core", ("*",)

    def score(self, q, ctx):
        return 0.05                                  # below the specialized agents, above Knowledge

    def run(self, q, ctx):
        res = Result.from_dict(self.mind._core_front(q))
        if res:
            res.agent = agent_from_how(res.how)
        return res

    def validate(self, result, ctx):
        return result is not None


class KnowledgeAgent(Agent):
    """First-class retrieval agent: grounded answers from the library + memory, the
    grounded/open LLM, and the honest no-source fallback. Sits just BELOW CoreRouter so
    the front branches (exact tools, generation, math) are never intercepted by a weak
    retrieval hit — it only runs when the front handled nothing."""
    name, domains = "knowledge", ("knowledge", "retrieval")

    def score(self, q, ctx):
        return 0.03                                  # just below CoreRouter's front

    def run(self, q, ctx):
        d = self.mind._knowledge_answer(q)
        res = Result.from_dict(d)
        if res and res.agent == "":
            res.agent = agent_from_how(res.how) if res.how else "knowledge"
        return res

    def validate(self, result, ctx):
        return result is not None                    # includes the honest no-source reply


# --------------------------------------------------------------------------- #
# Stage 6 — DOMAIN agents. New expertise plugs in by subclassing DomainAgent and
# adding it to DEFAULT_AGENTS below. The master, executive, router and everything
# else are UNCHANGED — that is the whole point of the architecture. Each fires only
# on its own intent and answers with a domain-specialised prompt grounded on
# retrieved facts; without a local LLM it self-skips (falls back to the base path),
# so it can never regress existing behaviour.
# --------------------------------------------------------------------------- #
class DomainAgent(Agent):
    intent = None            # compiled regex — the query shape this expert owns
    system = ""              # domain system prompt
    base_score = 0.65        # above the catch-alls, below the exact/verified specialists

    def _fires(self, q):
        return bool(self.intent and self.intent.search(q))

    def score(self, q, ctx):
        return self.base_score if self._fires(q) else 0.0

    def run(self, q, ctx):
        if not self._fires(q):
            return None
        llm = getattr(self.mind, "llm", None)
        if not (llm and llm.available):
            return None                          # no LLM → let the base path handle it
        hits = self.mind.lib.search(q, k=8)
        passages = [d for d, _ in hits]
        try:
            from llm import grounded_prompt
            prompt = grounded_prompt(q, passages)
        except Exception:
            prompt = q
        budget = int(os.environ.get("VIO_LLM_MAX_TOKENS", "3072"))
        ans = llm.generate(prompt, system=self.system, max_tokens=budget)
        if not ans:
            return None
        return Result(ans, how=f"{self.name} (LLM)", verified=bool(passages),
                      confidence=0.72 if passages else 0.55,
                      trace=[f"{self.name} agent grounded on {len(passages)} passage(s)"])


class TroubleshootingAgent(DomainAgent):
    name, domains = "troubleshooting", ("networking", "support")
    intent = re.compile(
        r"\b(troubleshoot|diagnos\w*|root ?cause|debug|not working|isn'?t working|"
        r"won'?t \w+|failing|keeps? (dropping|failing)|no connectivity|"
        r"can'?t (ping|connect|reach|browse)|why is .*\b(down|failing|slow|dropping))\b", re.I)
    system = ("You are a senior network & security TROUBLESHOOTING agent. Respond as a "
              "structured diagnosis: (1) the most likely causes, ranked; (2) the exact check "
              "or command to confirm each; (3) the fix. Ground device/vendor specifics in the "
              "provided facts; use expert knowledge for the method. Be concrete and ordered.")


class SecurityReviewAgent(DomainAgent):
    name, domains = "security_review", ("security",)
    intent = re.compile(
        r"is (this|it|my|the)\b[\w\s'-]{0,50}\b(secure|safe|hardened)|"
        r"\b(security (review|risk|posture|concern|audit)|harden\w*|best practice|"
        r"misconfigur\w*|vulnerab\w*|attack surface|least privilege|any (security )?risk|"
        r"review (this|my|the) (policy|config|firewall|rule)|"
        r"what.?s wrong with (this|the|my) (policy|config|rule))\b", re.I)
    system = ("You are a SECURITY REVIEW agent. Assess the described config/design for risk: "
              "call out misconfigurations, over-permissive rules, and exposure, each with why it "
              "matters and the recommended hardening. Ground specifics in the provided facts; do "
              "not invent rules that aren't there. Prioritise the highest-risk findings first.")


# order is only a tie-breaker; scores drive dispatch. Domain experts sit above the
# catch-alls but fire only on their intent; CoreRouter (front) then Knowledge (tail)
# remain the bottom fallbacks.
DEFAULT_AGENTS = (SkillAgent, MathAgent, PlannerAgent, WorldModelAgent, ReasoningAgent,
                  TroubleshootingAgent, SecurityReviewAgent, ConfigAgent, MemoryAgent,
                  CoreRouterAgent, KnowledgeAgent)


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


class Guardrail:
    """R1/R2 — consulted by the master before any result is returned. Advisory
    (read-only) answers pass straight through. A result from an ACTING agent
    (write/network permission) is GATED behind explicit confirmation, so Vio never
    changes anything or reaches outside itself without a yes. This is the safety
    foundation that must exist before Automation/Code/Web agents are ever added."""

    def check(self, q, agent, result, ctx):
        acts = bool(set(getattr(agent, "permissions", ())) & {WRITE, NETWORK})
        if not acts or ctx.get("confirmed"):
            return result                       # advisory, or already approved
        scope = "reach outside Vio" if NETWORK in agent.permissions else "change something"
        result.answer = (result.answer or "").rstrip() + (
            f"\n\n⚠️ This would {scope}. I won't run it without your OK — reply "
            "'confirm' to proceed.")
        result.how = (result.how or agent.name) + " · needs confirmation"
        result.verified = False
        result.trace = list(result.trace) + ["guardrail: acting result gated pending confirmation"]
        return result


class Master:
    """The control plane: score → dispatch → validate → guardrail, highest-fit first,
    first validated result wins. Returns None if no agent handled the query (the caller
    then falls back to the legacy router)."""

    def __init__(self, registry, guardrail=None):
        self.registry = registry
        self.guardrail = guardrail or Guardrail()

    def handle(self, q, ctx=None):
        ctx = ctx or {}
        for _score, agent in self.registry.ranked(q, ctx):
            try:
                res = agent.run(q, ctx)
            except Exception:
                res = None
            if res and agent.validate(res, ctx):
                if not res.agent:               # keep a finer name the agent already set
                    res.agent = agent.name
                return self.guardrail.check(q, agent, res, ctx)
        return None


def build_master(mind):
    reg = Registry()
    for cls in DEFAULT_AGENTS:
        reg.register(cls(mind))
    return Master(reg), reg
