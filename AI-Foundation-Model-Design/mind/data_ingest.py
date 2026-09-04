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
import os
import re
import sys

# Force UTF-8 output so ✓ → • in progress messages never crash on a legacy
# Windows console (cp1252) with UnicodeEncodeError.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("VIO_DATA_DIR", HERE)

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
def fact_to_question(s):
    """Turn a clean statement into the question it answers, so it can be trained as a
    skill (respond to a prompt), not just as text to continue."""
    s = s.strip()
    # "An" must be tried before "A", and \s+ keeps "A" from eating the "n" of "An".
    m = re.match(r"^(?:(An|A|The)\s+)?([A-Za-z][\w /-]{1,40}?)\s+(is|are)\s+", s)
    if m:
        art = (m.group(1).lower() + " ") if m.group(1) else ""   # reuse the real article
        subj = m.group(2).strip()                                # keep casing: FortiGate, OSPF
        return f"What {m.group(3)} {art}{subj}?"
    def _artfix(subj):                                 # lowercase a leading article
        a = re.match(r"^(An|A|The)\s+(.*)", subj)
        return f"{a.group(1).lower()} {a.group(2)}" if a else subj
    m = re.match(r"^([A-Za-z][\w /-]{1,40}?)\s+causes\s+(.+?)\.?$", s)
    if m:
        return f"What does {_artfix(m.group(1).strip())} cause?"
    m = re.match(r"^([A-Za-z][\w /-]{1,40}?)\s+(?:lets|allows|enables|helps)\s+", s)
    if m:
        return f"What does {_artfix(m.group(1).strip())} do?"
    return None


def build_skills(out=None, repeat=3):
    """Build a question->answer 'skills' corpus from Vio's clean curated facts, so the
    model learns the pattern of answering a question — the seed of a skill. Repeated a
    few times so it isn't drowned by a large raw-text corpus during training."""
    import glob
    out = out or os.path.join(DATA_DIR, "corpus", "skills.txt")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    facts, seen = [], set()
    for p in sorted(glob.glob(os.path.join(HERE, "datasets", "*.md"))):
        if os.path.basename(p).lower() == "readme.md":
            continue
        for line in open(p, encoding="utf-8", errors="ignore").read().splitlines():
            s = line.strip()
            if (len(s.split()) >= 5 and re.search(r"[.!?]$", s)
                    and not s.startswith(("#", "|", "-", "*", ">"))):
                k = s.lower()[:60]
                if k not in seen:
                    seen.add(k); facts.append(s)
    pairs = []
    for s in facts:
        q = fact_to_question(s)
        if q:
            pairs.append(f"Question: {q}\nAnswer: {s}\n")
    if not pairs:
        print("No facts found to build skills from."); return out
    block = "\n".join(pairs)
    with open(out, "w", encoding="utf-8") as fh:
        for _ in range(repeat):                        # repeat so the skill format sticks
            fh.write(block + "\n")
    print(f"✓ built {len(pairs)} question->answer skills (x{repeat} = {len(pairs)*repeat} "
          f"examples) -> {out}")
    print("  Sample:\n    " + pairs[0].replace("\n", "\n    "))
    print("  Train the skill (small + fast; skills-only):")
    print(f"    python train_model.py --preset small --extra \"{out}\" --steps 2000 "
          f"--batch 24 --patience 6")
    return out


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
def clean_rfc(text):
    """RFCs are plain text with page furniture — strip it, keep the prose."""
    text = text.replace("\r", "")
    out = []
    for ln in text.split("\n"):
        s = ln.rstrip()
        if "\f" in s:                                  # page break
            continue
        # running headers/footers: "RFC 4271   BGP-4   January 2006" / "[Page 12]"
        if re.search(r"\[Page \d+\]\s*$", s) or re.match(r"^RFC \d+\s+\S.*\d{4}\s*$", s):
            continue
        out.append(s)
    text = "\n".join(out)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def clean_prose(text):
    """Keep only natural-language PROSE, dropping the noise a small model shouldn't waste
    its capacity on: ASCII diagrams, packet-format tables, indented code/pseudo-code,
    tables of contents, and reference lists. Returns clean paragraphs.

    The test each line must pass: it reads like a sentence — mostly letters and spaces,
    not a picture made of +---+ | . _ characters or a row of columns."""
    keep = []
    for raw in text.replace("\r", "").split("\n"):
        s = raw.rstrip()
        if not s.strip():
            keep.append("")                            # blank line = paragraph break
            continue
        core = s.strip()
        letters = sum(c.isalpha() for c in core)
        # 1) too few letters relative to length -> a diagram/table/number row
        if letters < len(core) * 0.55:
            continue
        # 2) ASCII-art / table drawing characters
        if re.search(r"[|+_]{2,}|\+--|--\+|[.|]{4,}", core):
            continue
        # 3) deep indentation = code / diagram body (prose wraps near the left margin)
        if len(s) - len(s.lstrip()) >= 6:
            continue
        # 4) column layout: two or more big internal gaps = a table row
        if len(re.findall(r"\S {3,}\S", core)) >= 2:
            continue
        # 5) reference / TOC lines: "[12] Author, ..." or "... . . . 42"
        if re.match(r"^\[?\d+[\].]", core) or re.search(r"\.\s*\.\s*\.\s*\d+\s*$", core):
            continue
        # 6) must contain at least a few real words and a lowercase run (prose, not a header)
        if len(re.findall(r"[a-zA-Z]{3,}", core)) < 4 or not re.search(r"[a-z]{3,}", core):
            continue
        keep.append(core)
    # rejoin wrapped lines into paragraphs (blank line separates paragraphs)
    text = "\n".join(keep)
    text = re.sub(r"[ \t]*\n[ \t]*(?=[a-z(])", " ", text)   # unwrap mid-sentence breaks
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def clean_folder(src, dst=None):
    """Re-clean an existing text corpus (e.g. downloaded RFCs) into prose-only files —
    turns noisy raw text into the clean data a small model learns best from."""
    import glob
    dst = dst or (src.rstrip("/\\") + "_clean")
    os.makedirs(dst, exist_ok=True)
    files = [p for p in glob.glob(os.path.join(src, "**", "*"), recursive=True)
             if p.lower().endswith((".txt", ".md", ".rst"))]
    raw_mb = clean_mb = 0
    for p in files:
        raw = open(p, encoding="utf-8", errors="ignore").read()
        prose = clean_prose(raw)
        if len(prose) > 500:
            open(os.path.join(dst, os.path.basename(p)), "w", encoding="utf-8").write(prose)
            raw_mb += len(raw) / 1e6
            clean_mb += len(prose) / 1e6
    print(f"✓ cleaned {len(files)} files: {raw_mb:.1f} MB raw -> {clean_mb:.1f} MB clean prose")
    print(f"  in {dst}")
    print(f"  Train on the clean version:  python train_model.py --preset small "
          f"--extra \"{dst}\" --steps 3000 --batch 24 --patience 6")
    return dst


def pull_rfcs(count=200, start=1, out_dir=None, quiet=False):
    """Download IETF RFCs (plain text) — the real specifications of networking and
    security. This is the highest-quality free domain corpus for training."""
    import time
    import urllib.error
    import urllib.request
    out_dir = out_dir or os.path.join(DATA_DIR, "corpus", "rfc")
    os.makedirs(out_dir, exist_ok=True)
    got = bytes_total = 0
    n = start
    while got < count and n < 9700:
        path = os.path.join(out_dir, f"rfc{n}.txt")
        if os.path.exists(path):
            n += 1; got += 1; continue
        url = f"https://www.rfc-editor.org/rfc/rfc{n}.txt"
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                body = r.read().decode("utf-8", errors="ignore")
            body = clean_rfc(body)
            if len(body) > 2000:
                open(path, "w", encoding="utf-8").write(body)
                got += 1; bytes_total += len(body)
                if not quiet and got % 25 == 0:
                    print(f"  … {got} RFCs, {bytes_total/1e6:.1f} MB")
            time.sleep(0.2)                            # be polite to the server
        except urllib.error.HTTPError:
            pass                                       # gaps in RFC numbering are normal
        except Exception as e:
            print(f"  ! stopped at RFC {n}: {e}")
            break
        n += 1
    print(f"✓ {got} RFCs ({bytes_total/1e6:.1f} MB) in {out_dir}")
    print(f"  Train on them:  python train_model.py --preset gpu --extra \"{out_dir}\" --steps 5000")
    return out_dir


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

    p_rfc = sub.add_parser("rfc", help="download IETF RFCs — the best free networking corpus")
    p_rfc.add_argument("--n", type=int, default=200, help="how many RFCs")
    p_rfc.add_argument("--start", type=int, default=1, help="starting RFC number")
    p_rfc.add_argument("--out", default=None)

    p_cl = sub.add_parser("clean", help="strip a text corpus down to clean prose")
    p_cl.add_argument("src", help="folder of .txt/.md files to clean (e.g. corpus/rfc)")
    p_cl.add_argument("--out", default=None)

    p_sk = sub.add_parser("skills", help="build a question->answer skills corpus for training")
    p_sk.add_argument("--out", default=None)

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
    if a.cmd == "rfc":
        pull_rfcs(a.n, a.start, a.out)
        return
    if a.cmd == "clean":
        clean_folder(a.src, a.out)
        return
    if a.cmd == "skills":
        build_skills(a.out)
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
