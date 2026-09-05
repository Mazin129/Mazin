"""
build_large_sft  —  build a LARGE, CLEAN SFT jsonl for the Colab fine-tune notebook.

Pulls free public data, cleans it hard, and writes Colab-ready
{"question","answer"} lines (same shape as build_dataset.py / finetune_on_colab.ipynb).

Sources (all free, no API key except optional Kaggle):
  • local     — datasets/*.md + knowledge.json (your Vio library)
  • rfc       — corpus/rfc_clean (IETF RFCs you already downloaded)
  • hf        — Hugging Face: SQuAD, SciQ, Simple Wikipedia (pip install datasets)
  • github    — curated public doc repos (OWASP cheatsheets, etc.) via shallow git clone

    python build_large_sft.py                     # all sources → vio_sft_large.jsonl
    python build_large_sft.py --target 30000      # stop around 30k clean pairs
    python build_large_sft.py --sources local,rfc,hf
    python build_large_sft.py --llm-expand        # also expand domain facts with Ollama
                                                 # (slower; quality boost on datasets/*.md)

Then upload vio_sft_large.jsonl in finetune_on_colab.ipynb (Rename to vio_sft.jsonl
or change the upload cell). More clean pairs >> tiny terse fine-tunes.
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import re
import sys
import time

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("VIO_DATA_DIR", HERE)

_REFUSAL = re.compile(r"\b(i (?:can(?:not|'t)|don'?t|do not))\b|as an ai|i'm sorry", re.I)
_CFG = re.compile(r"^\s*(config|edit|set|unset|next|end|interface|!|hostname)\b", re.I)
_SENT = re.compile(r"(?<=[.!?])\s+")

# Public GitHub repos that are mostly documentation (read-only clone; never executed).
GITHUB_DOCS = (
    "OWASP/CheatSheetSeries",
    "trimstray/the-book-of-secret-knowledge",
    "swisskyrepo/PayloadsAllTheThings",          # security reference (md)
    "Fortinet/fortigate-ansible-collection",    # Forti docs/examples (filtered to md)
)


def _is_prose(s: str) -> bool:
    s = (s or "").strip()
    if len(s.split()) < 6 or len(s) > 700:
        return False
    if s[0] in "#|-*>" or _CFG.match(s):
        return False
    if not re.search(r"[.!?]$", s):
        return False
    letters = sum(c.isalpha() or c.isspace() for c in s)
    return letters / max(len(s), 1) > 0.75


def clean_pair(q, a, source=""):
    q, a = (q or "").strip(), (a or "").strip()
    if not q or not a:
        return None
    if not q.endswith("?"):
        q = q.rstrip(".!") + "?"
    # allow slightly longer domain answers than the tiny build_dataset cap
    if not (3 <= len(q.split()) <= 48):
        return None
    if not (8 <= len(a.split()) <= 280):
        return None
    if _REFUSAL.search(a):
        return None
    # drop near-echo garbage
    if a.lower().startswith(q.lower().rstrip("?")):
        return None
    rec = {"question": q, "answer": a}
    if source:
        rec["source"] = source
    return rec


def fact_to_question(s: str):
    """Deterministic Q from a clean statement (same idea as data_ingest.fact_to_question)."""
    s = s.strip()
    m = re.match(r"^(?:(An|A|The)\s+)?([A-Za-z][\w /.+-]{1,50}?)\s+(is|are)\s+", s)
    if m:
        art = (m.group(1).lower() + " ") if m.group(1) else ""
        return f"What {m.group(3)} {art}{m.group(2).strip()}?"
    m = re.match(r"^([A-Za-z][\w /.+-]{1,50}?)\s+causes\s+", s, re.I)
    if m:
        return f"What does {m.group(1).strip()} cause?"
    m = re.match(r"^([A-Za-z][\w /.+-]{1,50}?)\s+(?:lets|allows|enables|helps)\s+", s, re.I)
    if m:
        return f"What does {m.group(1).strip()} do?"
    m = re.match(r"^([A-Za-z][\w /.+-]{1,50}?)\s+(?:provides|uses|supports|requires)\s+", s, re.I)
    if m:
        return f"What does {m.group(1).strip()} provide or require?"
    # fallback: topical "what / how" from leading noun phrase
    m = re.match(r"^([A-Z][A-Za-z0-9][\w /.+-]{2,40})\b", s)
    if m and len(s.split()) >= 8:
        return f"What should I know about {m.group(1)}?"
    return None


# --------------------------------------------------------------------------- #
# Source collectors → list of clean (question, answer, source_tag)
# --------------------------------------------------------------------------- #
def from_local_datasets():
    pairs = []
    for p in sorted(glob.glob(os.path.join(HERE, "datasets", "*.md"))):
        if os.path.basename(p).lower() == "readme.md":
            continue
        tag = f"dataset:{os.path.basename(p)}"
        for line in open(p, encoding="utf-8", errors="ignore"):
            s = line.strip()
            if not _is_prose(s):
                continue
            q = fact_to_question(s)
            if q:
                pairs.append((q, s, tag))
    return pairs


def from_knowledge(limit=8000):
    kb = os.path.join(DATA_DIR, "knowledge.json")
    if not os.path.exists(kb):
        return []
    try:
        docs = json.load(open(kb, encoding="utf-8"))
    except Exception:
        return []
    pairs, n = [], 0
    for passage in docs:
        if n >= limit:
            break
        if not isinstance(passage, str):
            continue
        # split long passages into sentences
        for s in _SENT.split(passage):
            s = s.strip()
            if not _is_prose(s):
                continue
            q = fact_to_question(s)
            if q:
                pairs.append((q, s, "knowledge"))
                n += 1
                if n >= limit:
                    break
    return pairs


def from_rfc_clean(limit=25000):
    root = os.path.join(DATA_DIR, "corpus", "rfc_clean")
    if not os.path.isdir(root):
        print("  (no corpus/rfc_clean — run: python data_ingest.py rfc --n 800)")
        return []
    pairs, n = [], 0
    files = sorted(glob.glob(os.path.join(root, "*.txt")))
    for path in files:
        if n >= limit:
            break
        try:
            text = open(path, encoding="utf-8", errors="ignore").read()
        except Exception:
            continue
        name = os.path.basename(path)
        for para in re.split(r"\n\s*\n", text):
            if n >= limit:
                break
            para = re.sub(r"\s+", " ", para).strip()
            if not _is_prose(para) and not (len(para.split()) >= 10 and re.search(r"[.!?]", para)):
                # take first good sentence from paragraph
                for s in _SENT.split(para):
                    s = s.strip()
                    if _is_prose(s):
                        para = s
                        break
                else:
                    continue
            if not _is_prose(para):
                continue
            q = fact_to_question(para)
            if not q:
                # RFC-style: "This document describes X"
                m = re.match(r"^(?:This (?:document|memo)|RFC \d+)\s+(.+)", para, re.I)
                if m and len(para.split()) >= 10:
                    q = f"What does {name.replace('.txt','')} cover?"
                else:
                    continue
            pairs.append((q, para, f"rfc:{name}"))
            n += 1
    return pairs


def from_huggingface(n_squad=8000, n_sciq=4000, n_wiki=6000):
    try:
        from datasets import load_dataset
    except Exception:
        print("  (Hugging Face `datasets` not installed — pip install datasets)")
        return []

    pairs = []

    def add(q, a, tag):
        if q and a:
            pairs.append((q.strip(), a.strip(), tag))

    print("  → Hugging Face SQuAD …")
    try:
        ds = load_dataset("squad", split="train", streaming=True)
        got = 0
        for row in ds:
            ans = (row.get("answers") or {}).get("text") or []
            a = (ans[0] if ans else "").strip()
            ctx = (row.get("context") or "").strip()
            q = (row.get("question") or "").strip()
            if not (q and a and ctx):
                continue
            # self-contained: short answer + one grounding sentence from context
            sent = next((s.strip() for s in _SENT.split(ctx)
                         if a.lower() in s.lower() and len(s.split()) >= 6), "")
            full = f"{a}. {sent}" if sent and sent.lower() != a.lower() else (sent or a)
            if len(full.split()) < 8:
                full = (ctx[:400] + ("…" if len(ctx) > 400 else "")).strip()
            add(q, full, "hf:squad")
            got += 1
            if got >= n_squad:
                break
        print(f"    +{got} SQuAD")
    except Exception as e:
        print(f"    ! SQuAD skipped: {e}")

    print("  → Hugging Face SciQ …")
    try:
        ds = load_dataset("sciq", split="train", streaming=True)
        got = 0
        for row in ds:
            q = (row.get("question") or "").strip()
            a = (row.get("correct_answer") or "").strip()
            support = (row.get("support") or "").strip()
            if not (q and a):
                continue
            full = f"{a}. {support}" if support else a
            add(q if q.endswith("?") else q + "?", full, "hf:sciq")
            got += 1
            if got >= n_sciq:
                break
        print(f"    +{got} SciQ")
    except Exception as e:
        print(f"    ! SciQ skipped: {e}")

    print("  → Hugging Face Simple Wikipedia …")
    try:
        # Prefer a non-script dataset (HF disabled legacy dataset scripts).
        try:
            ds = load_dataset("rahular/simple-wikipedia", split="train", streaming=True)
            text_field = "text"
        except Exception:
            ds = load_dataset("wikimedia/wikipedia", "20231101.simple",
                              split="train", streaming=True)
            text_field = "text"
        got = 0
        for row in ds:
            text = (row.get(text_field) or row.get("content") or "").strip()
            for s in _SENT.split(text):
                s = s.strip()
                if not _is_prose(s):
                    continue
                q = fact_to_question(s)
                if q:
                    add(q, s, "hf:wikipedia-simple")
                    got += 1
                    if got >= n_wiki:
                        break
            if got >= n_wiki:
                break
        print(f"    +{got} Wikipedia-simple")
    except Exception as e:
        print(f"    ! Wikipedia skipped: {e}")

    return pairs


def from_github(repos=GITHUB_DOCS, max_pairs=8000):
    try:
        from gitlearn import fetch_repo_docs, parse_spec
    except Exception as e:
        print(f"  (gitlearn unavailable: {e})")
        return []

    pairs, n = [], 0
    for spec in repos:
        if n >= max_pairs:
            break
        print(f"  → GitHub {spec} …")
        try:
            if not parse_spec(spec) and not parse_spec(f"https://github.com/{spec}"):
                print("    ! bad spec")
                continue
            _owner, _repo, docs, _skipped = fetch_repo_docs(spec)
            got = 0
            for _src, text in docs:
                if n >= max_pairs:
                    break
                blob = re.sub(r"\s+", " ", text or "")
                for s in _SENT.split(blob):
                    s = s.strip()
                    if not _is_prose(s):
                        continue
                    q = fact_to_question(s)
                    if not q:
                        continue
                    pairs.append((q, s, f"github:{spec}"))
                    got += 1
                    n += 1
                    if n >= max_pairs:
                        break
            print(f"    +{got} pairs from {len(docs)} doc file(s)")
        except Exception as e:
            print(f"    ! skipped: {e}")
    return pairs


def llm_expand_datasets(per=2, limit=400):
    """Optional: use local Ollama to expand datasets/*.md into richer Q/A (slower)."""
    try:
        from llm import LLM
        from build_dataset import GEN_SYSTEM, parse_pairs, gather_sources
    except Exception as e:
        print(f"  (LLM expand skipped: {e})")
        return []
    llm = LLM()
    if not llm.available:
        print("  (no Ollama — skip --llm-expand)")
        return []
    sources = gather_sources(use_library=False)[:limit]
    print(f"  → LLM-expand {len(sources)} domain passages with {llm.model} …")
    pairs = []
    for i, src in enumerate(sources, 1):
        prompt = f"SOURCE:\n{src}\n\nWrite {per} Q/A pair(s)."
        reply = llm.generate(prompt, system=GEN_SYSTEM, temperature=0.6, max_tokens=512)
        for q, a in parse_pairs(reply or ""):
            pairs.append((q, a, "llm:dataset"))
        if i % 25 == 0:
            print(f"    … {i}/{len(sources)}")
    return pairs


# --------------------------------------------------------------------------- #
# Write
# --------------------------------------------------------------------------- #
def dedupe_write(pairs, out_path, target=0):
    seen, kept, by_src = set(), 0, {}
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        for q, a, src in pairs:
            rec = clean_pair(q, a, source=src)
            if not rec:
                continue
            key = hashlib.md5(
                (rec["question"].lower() + "\n" + rec["answer"].lower()[:120]).encode()
            ).hexdigest()
            if key in seen:
                continue
            seen.add(key)
            # Colab reads question + answer only; keep source as optional metadata
            fh.write(json.dumps(
                {"question": rec["question"], "answer": rec["answer"], "source": src},
                ensure_ascii=False) + "\n")
            kept += 1
            by_src[src.split(":")[0]] = by_src.get(src.split(":")[0], 0) + 1
            if target and kept >= target:
                break
    return kept, by_src


def main(argv=None):
    ap = argparse.ArgumentParser(description="Build a large clean SFT jsonl for Colab.")
    ap.add_argument("--out", default=os.path.join(DATA_DIR, "vio_sft_large.jsonl"))
    ap.add_argument("--target", type=int, default=40000,
                    help="approx max clean pairs to keep (0 = all)")
    ap.add_argument("--sources", default="local,rfc,hf,github",
                    help="comma list: local,rfc,hf,github")
    ap.add_argument("--llm-expand", action="store_true",
                    help="also expand datasets/*.md with local Ollama (slow)")
    ap.add_argument("--hf-squad", type=int, default=8000)
    ap.add_argument("--hf-sciq", type=int, default=4000)
    ap.add_argument("--hf-wiki", type=int, default=6000)
    ap.add_argument("--rfc-limit", type=int, default=25000)
    a = ap.parse_args(argv)

    wanted = {s.strip().lower() for s in a.sources.split(",") if s.strip()}
    print("=" * 64)
    print("  Vio — build LARGE clean SFT for Colab fine-tune")
    print("=" * 64)
    print(f"  sources: {', '.join(sorted(wanted))}")
    print(f"  target:  {a.target or 'all'} pairs → {a.out}\n")

    all_pairs = []
    t0 = time.time()

    if "local" in wanted:
        print("[1] local datasets + knowledge …")
        all_pairs += from_local_datasets()
        all_pairs += from_knowledge()
        print(f"    = {len(all_pairs)} so far")

    if "rfc" in wanted:
        print("[2] IETF RFC clean corpus …")
        before = len(all_pairs)
        all_pairs += from_rfc_clean(limit=a.rfc_limit)
        print(f"    +{len(all_pairs) - before} → {len(all_pairs)} so far")

    if "hf" in wanted:
        print("[3] Hugging Face free datasets …")
        before = len(all_pairs)
        all_pairs += from_huggingface(a.hf_squad, a.hf_sciq, a.hf_wiki)
        print(f"    +{len(all_pairs) - before} → {len(all_pairs)} so far")

    if "github" in wanted:
        print("[4] Public GitHub documentation repos …")
        before = len(all_pairs)
        all_pairs += from_github()
        print(f"    +{len(all_pairs) - before} → {len(all_pairs)} so far")

    if a.llm_expand:
        print("[5] LLM expand domain datasets …")
        before = len(all_pairs)
        all_pairs += llm_expand_datasets()
        print(f"    +{len(all_pairs) - before} → {len(all_pairs)} so far")

    print(f"\nCleaning + deduping {len(all_pairs)} raw pairs …")
    kept, by_src = dedupe_write(all_pairs, a.out, target=a.target)
    mb = os.path.getsize(a.out) / 1e6 if os.path.exists(a.out) else 0
    print(f"\n✓ Wrote {kept:,} clean SFT pairs ({mb:.1f} MB) → {a.out}")
    print("  By family: " + ", ".join(f"{k}={v}" for k, v in sorted(by_src.items(), key=lambda x: -x[1])))
    print(f"  Elapsed: {time.time() - t0:.0f}s")
    print("\nNext — Colab fine-tune:")
    print("  1. Open finetune_on_colab.ipynb in Google Colab (T4 GPU)")
    print(f"  2. Upload {os.path.basename(a.out)} (or rename to vio_sft.jsonl)")
    print("  3. Runtime → Run all  → download GGUF → ollama create")
    if kept < 5000:
        print("\n  Note: under ~5k pairs is still small. Add RFCs / raise --hf-* / --llm-expand.")
    elif kept < 15000:
        print("\n  Solid mid-size set. For sharper domain voice, re-run with --llm-expand.")
    else:
        print("\n  Large set — good for QLoRA without the tiny-SFT collapse.")
    return 0 if kept else 1


if __name__ == "__main__":
    raise SystemExit(main())
