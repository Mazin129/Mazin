"""
procedural  —  Procedural Memory: how-to knowledge.  [CORTEX-OS §3.4]

Phase-1 adapter over Vio's existing know-how: the user-taught SkillBook (reflexes) and
the solved-problem cache (mem["solved"]). Presents the tier API — match a goal to a
known procedure, reinforce on success — that later phases fill out with real procedure
graphs (multi-step DAGs) and automatic chunking, without changing callers.
"""

from __future__ import annotations


class ProceduralMemory:
    def __init__(self, skillbook, solved_cache):
        self.skills = skillbook               # skills.SkillBook
        self.solved = solved_cache            # dict: problem -> answer (mem["solved"])

    def match_skill(self, query):
        """A user-taught reflex that fires for this input, or None."""
        return self.skills.match(query)       # (name, reply) or None

    def recall_solution(self, query):
        """A previously computed answer for this exact input, or None."""
        return self.solved.get(query)

    def reinforce(self, query, answer):
        """Remember a freshly solved problem so it becomes a cheap reflex next time."""
        self.solved[query] = answer

    def summary(self):
        return {"skills": len(self.skills.skills), "solved": len(self.solved)}
