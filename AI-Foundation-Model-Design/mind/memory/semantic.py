"""
semantic  —  Semantic Memory: timeless knowledge.  [CORTEX-OS §3.2]

Phase-1 adapter: presents the tier API the cognitive OS will use, delegating to Vio's
existing `Library` (the TF-IDF passage store). Later phases grow this into a knowledge
graph + quantized vector index + symbolic rules behind the SAME interface, so nothing
that depends on SemanticMemory has to change.

    sem = SemanticMemory(mind.lib)
    sem.search("execute ping", k=6)  ->  [(passage, score), …]
    sem.add(["a new fact"])
"""

from __future__ import annotations


class SemanticMemory:
    def __init__(self, library):
        self.lib = library                     # the existing reasoner.Library

    def search(self, query, k=6):
        return self.lib.search(query, k=k)

    def add(self, passages):
        self.lib.add_many(list(passages))

    @property
    def size(self):
        return len(self.lib.docs)

    def summary(self):
        return {"passages": self.size}
