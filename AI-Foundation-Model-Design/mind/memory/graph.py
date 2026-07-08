"""
graph  —  a lightweight Knowledge Graph over Vio's semantic memory.  [CORTEX-OS §3.2/§4]

A concept graph for RELATIONAL questions the flat retrieval store answers poorly:
"how is X related to Y?", "what causes X?", "what is X a kind of?". Nodes are concepts;
edges are typed relations (is_a, causes, uses, has, part_of).

PERFORMANCE CONTRACT (the user's rule: never get slow):
  • Edges are extracted at TEACH time, one cheap regex pass per sentence — never on the
    query hot path.
  • A query touches only the neighbours of one or two nodes: O(degree), not O(graph).
  • The whole thing is a plain dict, persisted to graph.json (gitignored). No indexing
    build, no re-scan.

Extraction is deliberately conservative — a handful of unambiguous English patterns.
It adds edges when confident and stays silent otherwise (better a small true graph than
a big noisy one). It never replaces retrieval; it augments it for relational queries.
"""

from __future__ import annotations

import json
import os
import re

HERE = os.environ.get("VIO_DATA_DIR") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GRAPH_FILE = os.path.join(HERE, "graph.json")
MAX_EDGES = 100000

# "<subject> <relation cue> <object>" — subjects/objects kept short (concept-like).
_PATTERNS = [
    (re.compile(r"^(.{2,40}?)\s+(?:is|are)\s+(?:a|an)\s+(.{2,60}?)[.،؟?]?$", re.I), "is_a"),
    (re.compile(r"^(.{2,40}?)\s+(?:is|are)\s+(?:the\s+)?(.{2,60}?)[.،؟?]?$", re.I), "is"),
    (re.compile(r"(.{2,40}?)\s+(?:causes?|triggers?|leads?\s+to|results?\s+in|"
                r"produces?)\s+(.{2,60}?)[.،؟?]?$", re.I), "causes"),
    (re.compile(r"(.{2,40}?)\s+(?:uses?|use)\s+(?:a\s+|an\s+|the\s+)?(.{2,60}?)[.،؟?]?$", re.I), "uses"),
    (re.compile(r"(.{2,40}?)\s+(?:has|have|contains?)\s+(?:a\s+|an\s+)?(.{2,60}?)[.،؟?]?$", re.I), "has"),
    (re.compile(r"(.{2,40}?)\s+is\s+part\s+of\s+(?:a\s+|an\s+|the\s+)?(.{2,60}?)[.،؟?]?$", re.I), "part_of"),
]
_STOPHEAD = re.compile(r"^(the|a|an|this|that|these|those|it|there|here|they|we|you|i)\b", re.I)


def _norm(s):
    s = re.sub(r"\s+", " ", s.strip().lower()).strip(" .,:;،؟?")
    s = re.sub(r"^(?:the|a|an)\s+", "", s)        # drop a leading article: concepts, not phrases
    return s


def _concept_ok(s):
    # a concept is short, wordy, not a pronoun/filler head, not a whole clause
    if not (1 <= len(s.split()) <= 5) or len(s) < 2:
        return False
    if _STOPHEAD.match(s):
        return False
    return bool(re.search(r"[a-z؀-ۿ]", s))


class KnowledgeGraph:
    def __init__(self, path=GRAPH_FILE):
        self.path = path
        self.adj = {}            # node -> list of [relation, target]
        self._n_edges = 0
        if os.path.exists(path):
            try:
                self.adj = json.load(open(path, encoding="utf-8"))
                self._n_edges = sum(len(v) for v in self.adj.values())
            except (ValueError, OSError):
                self.adj = {}

    # ---- build (teach-time, cheap) ----------------------------------------
    def add_edge(self, subj, rel, obj):
        subj, obj = _norm(subj), _norm(obj)
        if not (_concept_ok(subj) and _concept_ok(obj)) or subj == obj:
            return False
        if self._n_edges >= MAX_EDGES:
            return False
        edges = self.adj.setdefault(subj, [])
        if [rel, obj] not in edges:
            edges.append([rel, obj])
            self._n_edges += 1
            return True
        return False

    def learn_sentence(self, sentence):
        """Extract 0..1 edges from one sentence. Returns the number added."""
        s = sentence.strip()
        for rx, rel in _PATTERNS:
            m = rx.match(s)
            if m and self.add_edge(m.group(1), rel, m.group(2)):
                return 1
        return 0

    def learn_text(self, text):
        added = 0
        for sent in re.split(r"(?<=[.!?؟])\s+|\n+", text or ""):
            added += self.learn_sentence(sent)
        if added:
            self._save()
        return added

    # ---- query (hot path, O(degree)) --------------------------------------
    def neighbors(self, concept):
        return self.adj.get(_norm(concept), [])

    def relation_between(self, a, b):
        """Direct or one-hop relation from a to b (or b to a). Fast: two adjacency lists."""
        a, b = _norm(a), _norm(b)
        for rel, tgt in self.adj.get(a, []):
            if b in tgt or tgt in b:
                return f"{a} {rel.replace('_', ' ')} {tgt}"
        for rel, tgt in self.adj.get(b, []):
            if a in tgt or tgt in a:
                return f"{b} {rel.replace('_', ' ')} {tgt}"
        # one hop: a -> mid -> b
        for rel1, mid in self.adj.get(a, []):
            for rel2, tgt in self.adj.get(_norm(mid), []):
                if b in tgt or tgt in b:
                    return f"{a} {rel1.replace('_',' ')} {mid}, which {rel2.replace('_',' ')} {tgt}"
        return None

    def describe(self, concept):
        """A one-line summary of what the graph knows about a concept."""
        edges = self.neighbors(concept)
        if not edges:
            return None
        parts = [f"{rel.replace('_', ' ')} {tgt}" for rel, tgt in edges[:6]]
        return f"{_norm(concept)}: " + "; ".join(parts)

    def causes_of(self, concept):
        c = _norm(concept)
        return [subj for subj, edges in self.adj.items()
                for rel, tgt in edges if rel == "causes" and (c in tgt or tgt in c)]

    def summary(self):
        return {"concepts": len(self.adj), "edges": self._n_edges}

    def _save(self):
        try:
            json.dump(self.adj, open(self.path, "w", encoding="utf-8"), ensure_ascii=False)
        except OSError:
            pass

    def clear(self):
        self.adj = {}
        self._n_edges = 0
        if os.path.exists(self.path):
            os.remove(self.path)


if __name__ == "__main__":
    g = KnowledgeGraph(path="/tmp/_kg.json"); g.clear(); g = KnowledgeGraph(path="/tmp/_kg.json")
    for s in ["OSPF is a routing protocol.", "A VLAN is a network segment.",
              "A routing protocol uses a routing table.", "Congestion causes packet loss."]:
        g.learn_sentence(s)
    print("summary:", g.summary())
    print("describe ospf:", g.describe("ospf"))
    print("relate ospf & routing table:", g.relation_between("ospf", "routing table"))
    print("causes of packet loss:", g.causes_of("packet loss"))
    g.clear()
