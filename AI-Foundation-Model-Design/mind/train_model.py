"""
train_model  —  train Vio's OWN model from zero on your data.  [Phase 2]

No pretrained weights. This gathers your text corpus, learns a tokenizer from it, and
trains the transformer in neural_model.py from random initialization. What comes out is
a model whose every parameter was shaped by YOUR data and nothing else.

    python train_model.py --scan                  # how much data do I have? (do this first)
    python train_model.py --preset gpu --steps 3000
    python train_model.py --preset gpu --extra C:\\docs\\security --steps 5000
    python train_model.py --sample "a firewall"   # generate from the trained model

HONEST EXPECTATIONS — read this before judging the output:
  A from-scratch model's quality is set by DATA VOLUME first, everything else second.

    < 1 MB      the model learns letter/word shapes; output looks like word salad.
    1 – 10 MB   it learns your domain's vocabulary and phrasing; short fragments read right.
    10 – 100 MB it produces fluent, on-domain sentences and useful completions.
    100 MB +    genuinely useful narrow domain model.

  Vio's bundled datasets are only ~50 KB — far too small on their own. Use data_ingest.py
  (Hugging Face / Kaggle) and --extra to point at your own manuals, configs and notes to
  get into the useful range. More focused domain data beats more mixed data every time.
"""

from __future__ import annotations

import argparse
import glob
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("VIO_DATA_DIR", HERE)
MODEL_DIR = os.path.join(DATA_DIR, "own_model")

# size presets — parameters scale with what your hardware can train
PRESETS = {
    # name:  (n_layer, n_head, n_embd, block_size, vocab_size)   ~params
    "tiny":  (4, 4, 128, 64, 1024),      # ~2M   — CPU smoke test only
    "small": (6, 6, 384, 256, 4096),     # ~15M  — weak GPU / patient CPU
    "gpu":   (8, 8, 512, 256, 8192),     # ~30M  — a real NVIDIA card
    "big":   (12, 12, 768, 512, 16384),  # ~90M  — 12GB+ VRAM
}


def collect_corpus(extra=()):
    """Gather every piece of text we're allowed to train on, newest sources last."""
    chunks, sources = [], []

    def add(text, label):
        text = (text or "").strip()
        if len(text) > 40:
            chunks.append(text)
            sources.append((label, len(text)))

    for p in sorted(glob.glob(os.path.join(HERE, "datasets", "*.md"))):
        if os.path.basename(p).lower() == "readme.md":
            continue
        add(open(p, encoding="utf-8", errors="ignore").read(), os.path.basename(p))

    kb = os.path.join(DATA_DIR, "knowledge.json")
    if os.path.exists(kb):
        try:
            import json
            docs = json.load(open(kb, encoding="utf-8"))
            add("\n".join(docs), f"knowledge.json ({len(docs)} passages)")
        except Exception:
            pass

    for path in extra:
        if os.path.isdir(path):
            for p in glob.glob(os.path.join(path, "**", "*"), recursive=True):
                if p.lower().endswith((".txt", ".md", ".rst", ".log", ".conf", ".cfg", ".json", ".csv")):
                    try:
                        add(open(p, encoding="utf-8", errors="ignore").read(), os.path.relpath(p, path))
                    except Exception:
                        pass
        elif os.path.isfile(path):
            add(open(path, encoding="utf-8", errors="ignore").read(), os.path.basename(path))

    return "\n\n".join(chunks), sources


def report(text, sources):
    mb = len(text.encode("utf-8")) / 1e6
    print(f"\n  Corpus: {mb:.2f} MB  ·  {len(text.split()):,} words  ·  {len(sources)} source(s)")
    for label, n in sorted(sources, key=lambda s: -s[1])[:12]:
        print(f"    {n/1000:8.1f} KB  {label}")
    print()
    if mb < 1:
        print("  ⚠ UNDER 1 MB. The model will only learn word shapes — output will look like")
        print("    word salad. This is a DATA problem, not a code problem. Add much more")
        print("    domain text:  python data_ingest.py preset wikipedia --n 20000")
        print("    or point at your own docs:  --extra <folder>\n")
    elif mb < 10:
        print("  → Enough to learn your domain's vocabulary and phrasing. Fragments will read")
        print("    right; full paragraphs will still wander. More data is the main lever.\n")
    else:
        print("  → Good volume. Expect fluent, on-domain text.\n")
    return mb


def main(argv=None):
    ap = argparse.ArgumentParser(description="Train Vio's own model from zero.")
    ap.add_argument("--preset", default="gpu", choices=list(PRESETS))
    ap.add_argument("--steps", type=int, default=3000)
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--extra", nargs="*", default=[], help="extra files/folders to train on")
    ap.add_argument("--out", default=MODEL_DIR)
    ap.add_argument("--scan", action="store_true", help="only report corpus size, don't train")
    ap.add_argument("--sample", default=None, help="generate from the saved model and exit")
    a = ap.parse_args(argv)

    if a.sample is not None:
        from neural_model import load, sample
        if not os.path.exists(os.path.join(a.out, "weights.pt")):
            print(f"No trained model at {a.out}. Train one first."); return 1
        model, tok = load(a.out)
        print(sample(model, tok, a.sample, max_new_tokens=200))
        return 0

    text, sources = collect_corpus(a.extra)
    if not text:
        print("No training text found. Add datasets, teach Vio, or pass --extra <folder>.")
        return 1
    mb = report(text, sources)
    if a.scan:
        return 0

    from neural_model import GPTConfig, train
    n_layer, n_head, n_embd, block, vocab = PRESETS[a.preset]
    # a tiny corpus cannot support a large BPE vocabulary — scale it down honestly
    vocab = max(256, min(vocab, 256 + len(text) // 40))
    cfg = GPTConfig(vocab_size=vocab, block_size=block, n_layer=n_layer,
                    n_head=n_head, n_embd=n_embd)
    print(f"  Preset '{a.preset}': {n_layer}L/{n_head}H/{n_embd}d, ctx {block}, vocab {vocab}")
    print(f"  Training {a.steps} steps — every weight starts random. Nothing pretrained.\n")

    model, tok = train(text, a.out, cfg=cfg, steps=a.steps, batch_size=a.batch,
                       lr=a.lr, vocab_size=vocab)

    from neural_model import sample
    print("\n  Samples from YOUR model:\n" + "  " + "-" * 50)
    for prompt in ("A firewall", "The network", "Security"):
        out = sample(model, tok, prompt, max_new_tokens=60).replace("\n", " ")
        print(f"    “{prompt}” → {out[:160]}")
    print("\n  Train longer or add data to improve it:  --steps 10000 --extra <folder>")
    return 0


if __name__ == "__main__":
    sys.exit(main())
