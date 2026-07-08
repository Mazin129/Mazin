"""
teach_datasets  —  feed Vio the whole bundled clean knowledge base at once.

Teaches every .md file in datasets/ into your Vio (networking, security, computing,
programming, science, world). One retrain per file, so it's fast. After this, Vio can
answer conceptual questions across all those domains with clean definitions, causal
reasoning, and a populated knowledge graph.

    python teach_datasets.py

It ADDS to whatever Vio already knows (de-duplicated on re-run). To start clean first,
use "Forget everything" in the browser, or delete knowledge.json / graph.json.
"""

import glob
import os

from reasoner import Mind

HERE = os.path.dirname(os.path.abspath(__file__))
DATASETS = os.path.join(HERE, "datasets")


def main():
    m = Mind()
    before_docs = len(m.lib.docs)
    before_edges = m.graph.summary()["edges"]

    # only real knowledge files — NOT the README / docs (their example questions and
    # style-guide lines would otherwise be learned as "facts" and pollute answers).
    files = [f for f in sorted(glob.glob(os.path.join(DATASETS, "*.md")))
             if os.path.basename(f).lower() != "readme.md"]
    if not files:
        print("No datasets found in", DATASETS)
        return
    for path in files:
        name = os.path.basename(path)
        text = open(path, encoding="utf-8").read()
        msg = m.learn_text(text, name)
        print(f"  ✓ {name:22} {msg}")

    print("\nDone.")
    print(f"  Library:      {before_docs} → {len(m.lib.docs)} passages")
    print(f"  Graph edges:  {before_edges} → {m.graph.summary()['edges']}")
    print(f"  Vocabulary:   {m.thinker.stats()['vocab']} words")
    print("\nAsk Vio things like:  what is a firewall?   what causes packet loss?   "
          "what happens if a computer overheats?")


if __name__ == "__main__":
    main()
