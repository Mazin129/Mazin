"""
specialists  —  the specialist cortex.  [CORTEX-OS §6]

Instead of one thinker, a set of small domain experts. Each scores how well it can
handle a query (can_handle) with a cheap keyword test; the Executive can name the
active domain, and the Curiosity/Consolidation engines use it to organize knowledge by
area. Phase-5 experts are lightweight CLASSIFIERS over the shared reasoning/memory
(they route and label, they don't fork the pipeline) — a later phase gives each its own
memory slice and tools.

PERFORMANCE: classification is a handful of substring checks, O(1). It runs once per
turn to tag the domain and never changes the fast routing.
"""

from __future__ import annotations


class Specialist:
    name = "general"
    keywords = ()

    def can_handle(self, q):
        ql = q.lower()
        hits = sum(1 for k in self.keywords if k in ql)
        return min(1.0, hits / 2.0) if hits else 0.0


class MathExpert(Specialist):
    name = "math"
    keywords = ("solve", "integrate", "derivative", "factor", "prime", "equation",
                "calculate", "plus", "minus", "percent", "factorial", "matrix")


class NetworkingExpert(Specialist):
    name = "networking"
    keywords = ("network", "router", "switch", "vlan", "ospf", "bgp", "firewall",
                "fortigate", "ping", "subnet", "packet", "routing", "interface",
                "protocol", "gateway", "dns", "dhcp", "port")


class SecurityExpert(Specialist):
    name = "security"
    keywords = ("security", "vulnerability", "exploit", "encryption", "attack",
                "malware", "authentication", "certificate", "threat", "policy")


class ProgrammingExpert(Specialist):
    name = "programming"
    keywords = ("code", "function", "python", "variable", "class", "compile",
                "algorithm", "bug", "loop", "array", "syntax")


class GeneralExpert(Specialist):
    name = "general"

    def can_handle(self, q):
        return 0.10                      # the fallback — always a little bit applicable


class Cortex:
    """The registry. Picks the best-matching specialist for a query."""

    def __init__(self):
        self.experts = [MathExpert(), NetworkingExpert(), SecurityExpert(),
                        ProgrammingExpert(), GeneralExpert()]

    def classify(self, q):
        """Return (domain_name, score) for the best-matching specialist."""
        best, best_score = "general", 0.0
        for e in self.experts:
            s = e.can_handle(q)
            if s > best_score:
                best, best_score = e.name, s
        return best, best_score

    def domains(self):
        return [e.name for e in self.experts]
