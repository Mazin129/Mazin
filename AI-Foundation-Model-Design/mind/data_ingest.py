"""
data_ingest  —  feed Vio REAL data from Hugging Face and Kaggle.

Vio learns by reading clean, factual sentences. This tool pulls real public
datasets, turns each record into well-formed sentences, and teaches them into Vio's
library (which also retrains the language model). It runs on YOUR machine — the
downloads use your normal internet, no keys leave the box.

    # Hugging Face (needs:  pip install datasets)
    python data_ingest.py hf wikipedia --config 20220301.simple --n 2000
    python data_ingest.py hf ag_news --n 1000
    python data_ingest.py list                 # curated, clean starter datasets

    # Kaggle (needs:  pip install kaggle  + ~/.kaggle/kaggle.json credentials)
    python data_ingest.py kaggle <owner/dataset-slug> --n 2000

QUALITY FIRST (Vio's whole point): every record is cleaned and split into sentences,
short/garbled lines are dropped, and a size cap keeps retrieval fast. Prefer the
curated presets in `list` — random noisy datasets make noisy answers.
"""

from __future__ import annotations

import argparse
import re
import sys

# Curated, clean, mostly-factual datasets that teach well (name → how to pull it).
CURATED = {
    "wikipedia":  ("hf", "wikipedia", "20220301.simple", ("text",),
                   "Simple-English Wikipedia — broad factual prose."),
    "ag_news":    ("hf", "ag_news", None, ("text",),
                   "News articles (world/sports/business/sci-tech)."),
    "squad":      ("hf", "squad", None, ("context",),
                   "Wikipedia paragraphs used for Q&A — dense facts."),
    "sciq":       ("hf", "sciq", None, ("support",),
                   "Science exam support passages."),
    "eli5category": ("hf", "sentence-transformers/eli5", None, ("answer",),
                     "Plain-language explanations of real questions."),
    "wikics":     ("hf", "wikipedia", "20220301.en", ("text",),
                   "Full English Wikipedia (large — use a small --n)."),
}


# --------------------------------------------------------------------------- #
# text cleaning — turn a raw record into clean, teachable sentences
# --------------------------------------------------------------------------- #
_SENT = re.compile(r"(?<=[.!?])\s+")


def to_sentences(text, min_words=5, max_words=60):
    """A raw field → a list of clean, self-contained sentences worth teaching."""
    if not text:
        return []
    text = re.sub(r"\s+", " ", str(text)).strip()
    text = re.sub(r"\[[^\]]*\]", "", text)            # strip [citation]/[1] markup
    out = []
    for s in _SENT.split(text):
        s = s.strip(" -*•\t")
        n = len(s.split())
        if n < min_words or n > max_words:
            continue
        if not re.search(r"[a-zA-Z]", s):             # must contain real words
            continue
        if sum(c.isdigit() for c in s) > len(s) * 0.4:  # mostly numbers/tables → skip
            continue
        if not re.search(r"[.!?]$", s):
            s += "."
        out.append(s)
    return out


def records_to_passages(rows, fields, limit, seen=None):
    """Stream of dataset rows → clean, de-duplicated passages (bounded by `limit`)."""
    seen = seen if seen is not None else set()
    passages = []
    for row in rows:
        for f in fields:
            val = row.get(f) if isinstance(row, dict) else None
            for sent in to_sentences(val):
                key = sent.lower()[:80]
                if key in seen:
                    continue
                seen.add(key)
                passages.append(sent)
                if len(passages) >= limit:
                    return passages
    return passages


# --------------------------------------------------------------------------- #
# sources
# --------------------------------------------------------------------------- #
def pull_huggingface(name, config, fields, limit):
    try:
        from datasets import load_dataset
    except Exception:
        raise RuntimeError("Hugging Face datasets not installed. Run:  pip install datasets")
    print(f"→ streaming Hugging Face dataset '{name}'"
          f"{f' ({config})' if config else ''} …")
    ds = load_dataset(name, config, split="train", streaming=True)
    return records_to_passages(ds, fields, limit)


def pull_kaggle(slug, fields, limit):
    try:
        from kaggle.api.kaggle_api_extended import KaggleApi
    except Exception:
        raise RuntimeError("Kaggle not installed. Run:  pip install kaggle  and put your "
                           "kaggle.json in ~/.kaggle/ (Account → Create New API Token).")
    import csv
    import glob
    import os
    import tempfile
    api = KaggleApi()
    api.authenticate()
    tmp = tempfile.mkdtemp()
    print(f"→ downloading Kaggle dataset '{slug}' …")
    api.dataset_download_files(slug, path=tmp, unzip=True)
    seen, passages = set(), []
    for path in glob.glob(os.path.join(tmp, "**", "*"), recursive=True):
        low = path.lower()
        if low.endswith((".csv", ".tsv")):
            with open(path, encoding="utf-8", errors="ignore", newline="") as fh:
                rows = list(csv.DictReader(fh))
            cols = fields or [c for c in (rows[0].keys() if rows else [])
                              if any(len(str(r.get(c, "")).split()) >= 5 for r in rows[:50])]
            passages += records_to_passages(rows, cols, limit - len(passages), seen)
        elif low.endswith((".txt", ".md")):
            txt = open(path, encoding="utf-8", errors="ignore").read()
            passages += records_to_passages([{"text": txt}], ("text",),
                                            limit - len(passages), seen)
        if len(passages) >= limit:
            break
    return passages


# --------------------------------------------------------------------------- #
# teach into Vio
# --------------------------------------------------------------------------- #
def teach_into_vio(passages, source):
    if not passages:
        print("No clean, teachable sentences were extracted — nothing added.")
        return 0
    from reasoner import Mind
    m = Mind()
    before = len(m.lib.docs)
    m.lib.add_many(passages)          # add as knowledge (retrieval + language model)
    m._retrain()
    m.mem["last_learned"] = {"source": source, "count": len(passages)}
    m._save()
    print(f"✓ Taught {len(passages)} clean passages from {source}.")
    print(f"  Library: {before} → {len(m.lib.docs)} passages.")
    print("  Ask Vio about the new material, or open web.py.")
    return len(passages)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Feed Vio real data from Hugging Face / Kaggle.")
    sub = ap.add_subparsers(dest="cmd")

    p_hf = sub.add_parser("hf", help="Hugging Face dataset")
    p_hf.add_argument("name"); p_hf.add_argument("--config", default=None)
    p_hf.add_argument("--fields", default="text"); p_hf.add_argument("--n", type=int, default=1000)

    p_kg = sub.add_parser("kaggle", help="Kaggle dataset (owner/slug)")
    p_kg.add_argument("slug"); p_kg.add_argument("--fields", default="")
    p_kg.add_argument("--n", type=int, default=1000)

    p_pre = sub.add_parser("preset", help="one of the curated datasets")
    p_pre.add_argument("name"); p_pre.add_argument("--n", type=int, default=1000)
    sub.add_parser("list", help="show curated datasets")

    a = ap.parse_args(argv)
    if a.cmd == "list" or not a.cmd:
        print("Curated, clean starter datasets (python data_ingest.py preset <name>):\n")
        for k, (_, nm, cfg, _f, desc) in CURATED.items():
            print(f"  {k:14} {desc}")
        print("\nOr any Hugging Face dataset:  python data_ingest.py hf <name> --n 1000")
        return
    if a.cmd == "preset":
        src, nm, cfg, fields, _ = CURATED[a.name]
        passages = pull_huggingface(nm, cfg, fields, a.n)
        teach_into_vio(passages, f"huggingface:{nm}")
    elif a.cmd == "hf":
        passages = pull_huggingface(a.name, a.config, tuple(a.fields.split(",")), a.n)
        teach_into_vio(passages, f"huggingface:{a.name}")
    elif a.cmd == "kaggle":
        fields = tuple(f for f in a.fields.split(",") if f) or None
        passages = pull_kaggle(a.slug, fields, a.n)
        teach_into_vio(passages, f"kaggle:{a.slug}")


if __name__ == "__main__":
    main()
