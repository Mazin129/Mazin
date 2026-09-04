"""
build_dataset  —  make a LARGE, CLEAN instruction dataset for fine-tuning.

The last fine-tune broke because it trained on ~405 terse one-sentence facts.
This fixes the ROOT cause: it uses your own working local model to EXPAND every
fact and ingested document passage into rich, multi-sentence question→answer
pairs — turning a few hundred terse facts + your documents into thousands of
clean training examples, the kind a good fine-tune actually needs.

    python build_dataset.py                    # datasets + your ingested library
    python build_dataset.py --per 2            # 2 question variants per passage
    python build_dataset.py --limit 50         # quick trial on 50 passages
    python build_dataset.py --out vio_sft.jsonl

Needs Ollama running with a capable model (llama3.1 / qwen2.5). It writes:
  • vio_sft.jsonl   — {"question","answer"} per line, ready for the fine-tune notebook
It saves as it goes and is resumable — rerun to continue where it stopped.
"""
import sys
import os
import re
import json
import time
import argparse
import hashlib

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("VIO_DATA_DIR", HERE)

GEN_SYSTEM = (
    "You write high-quality training examples for a professional networking and "
    "security assistant. Given a SOURCE passage, produce realistic questions an "
    "engineer would ask that the passage answers, each with a clear, correct, "
    "self-contained answer of 2 to 5 sentences. Ground every answer strictly in the "
    "source — never invent product names, numbers, or commands that are not there. "
    "Return ONLY pairs in exactly this format and nothing else:\n"
    "Q: <question>\nA: <answer>"
)

_REFUSAL = re.compile(r"\b(i (?:can(?:not|'t)|don'?t|do not))\b|as an ai|i'm sorry", re.I)
_CFG = re.compile(r"^\s*(config|edit|set|unset|next|end|interface|!|hostname)\b", re.I)


def _is_prose(s):
    """A clean, factual sentence worth turning into training data — not a config
    line, heading, table row, or garbled fragment."""
    s = s.strip()
    if len(s.split()) < 6 or len(s) > 600:
        return False
    if s[0] in "#|-*>" or _CFG.match(s):
        return False
    if not re.search(r"[.!?]$", s):
        return False
    letters = sum(c.isalpha() or c.isspace() for c in s)
    return letters / max(len(s), 1) > 0.75          # mostly words, not symbols


def gather_sources(use_library=True):
    """Clean prose passages from the curated datasets and (optionally) the
    documents you've ingested into the library."""
    import glob
    seen, out = set(), []

    def add(s):
        s = s.strip()
        k = s.lower()[:80]
        if s and k not in seen:
            seen.add(k); out.append(s)

    for p in sorted(glob.glob(os.path.join(HERE, "datasets", "*.md"))):
        if os.path.basename(p).lower() == "readme.md":
            continue
        for line in open(p, encoding="utf-8", errors="ignore").read().splitlines():
            if _is_prose(line):
                add(line)

    if use_library:
        kb = os.path.join(DATA_DIR, "knowledge.json")
        if os.path.exists(kb):
            try:
                for passage in json.load(open(kb, encoding="utf-8")):
                    if isinstance(passage, str) and _is_prose(passage):
                        add(passage)
            except Exception:
                pass
    return out


def parse_pairs(text):
    """Pull Q:/A: pairs out of the model's reply, tolerant of spacing."""
    pairs, q = [], None
    for line in (text or "").splitlines():
        m = re.match(r"\s*Q\s*[:\-.]\s*(.+)", line, re.I)
        if m:
            q = m.group(1).strip(); continue
        m = re.match(r"\s*A\s*[:\-.]\s*(.+)", line, re.I)
        if m and q:
            pairs.append((q, m.group(1).strip())); q = None
    return pairs


def clean_pair(q, a):
    q, a = q.strip(), a.strip()
    if not q.endswith("?"):
        q = q.rstrip(".") + "?"
    if not (4 <= len(q.split()) <= 40):
        return None
    if not (12 <= len(a.split()) <= 220):
        return None
    if _REFUSAL.search(a):
        return None
    return {"question": q, "answer": a}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Generate a large clean fine-tune dataset.")
    ap.add_argument("--per", type=int, default=2, help="questions per passage (1-3)")
    ap.add_argument("--limit", type=int, default=0, help="cap passages (0 = all)")
    ap.add_argument("--out", default=os.path.join(DATA_DIR, "vio_sft.jsonl"))
    ap.add_argument("--no-library", action="store_true", help="datasets only")
    a = ap.parse_args(argv)

    from llm import LLM
    llm = LLM()
    if not llm.available:
        print("No local model found. Start Ollama and pull one (e.g. `ollama pull "
              "llama3.1`), then rerun. This tool USES your model to write the data.")
        return 1
    print(f"Using local model: {llm.model}")

    sources = gather_sources(use_library=not a.no_library)
    if a.limit:
        sources = sources[:a.limit]
    print(f"{len(sources)} clean source passages "
          f"({'datasets only' if a.no_library else 'datasets + ingested library'}).")

    done_file = a.out + ".done"
    done = set()
    if os.path.exists(done_file):
        done = set(open(done_file, encoding="utf-8").read().split())
        print(f"Resuming — {len(done)} passages already processed.")

    per = max(1, min(3, a.per))
    n_pairs, t0 = 0, time.time()
    with open(a.out, "a", encoding="utf-8") as out_fh, \
            open(done_file, "a", encoding="utf-8") as done_fh:
        for i, src in enumerate(sources, 1):
            h = hashlib.md5(src.encode("utf-8", "ignore")).hexdigest()[:12]
            if h in done:
                continue
            prompt = f"SOURCE:\n{src}\n\nWrite {per} Q/A pair(s)."
            reply = llm.generate(prompt, system=GEN_SYSTEM, temperature=0.7, max_tokens=512)
            kept = 0
            for q, ans in parse_pairs(reply or ""):
                rec = clean_pair(q, ans)
                if rec:
                    out_fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    n_pairs += 1; kept += 1
            out_fh.flush()
            done_fh.write(h + "\n"); done_fh.flush()
            if i % 10 == 0 or i == len(sources):
                rate = i / max(time.time() - t0, 1e-9)
                eta = (len(sources) - i) / max(rate, 1e-9)
                print(f"  {i}/{len(sources)} passages · {n_pairs} pairs · "
                      f"{rate*60:.0f}/min · ETA {eta/60:.0f}m", flush=True)

    print(f"\n✓ Wrote {n_pairs} clean Q/A pairs to {a.out}")
    print("  Upload that .jsonl to the fine-tune notebook (it trains on it directly).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
