"""
train_all  —  ONE command to train Vio's own model on ALL your data.  [Phase 2]

Runs the whole pipeline end to end, so you don't have to chain commands:

    1. Builds the question->answer skills corpus from every knowledge dataset.
    2. Cleans your downloaded RFC corpus into prose-only text (if present).
    3. Trains the from-scratch model on EVERYTHING at once — every datasets/*.md
       knowledge file, the skills, and the cleaned RFCs — in a single run.

    python train_all.py                       # sensible defaults (small model)
    python train_all.py --steps 4000 --batch 24
    python train_all.py --preset gpu --steps 6000

Everything trains together, so the model learns all vendors (FortiGate, F5, Palo
Alto, Cisco, Azure, AWS, Zscaler, CrowdStrike, …), core networking, and the
answering skill in one model. Checkpointed and resumable like a normal run.
"""

from __future__ import annotations

import argparse
import glob
import os
import sys

# Windows consoles default to a legacy codepage (cp1252) that can't encode the
# ✓ → • characters in our progress messages, which would crash the run with a
# UnicodeEncodeError. Force UTF-8 output so printing can never take training
# down, whatever the console's codepage.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("VIO_DATA_DIR", HERE)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Train Vio's own model on all data, one command.")
    ap.add_argument("--preset", default="small")
    ap.add_argument("--steps", type=int, default=4000)
    ap.add_argument("--batch", type=int, default=24)
    ap.add_argument("--patience", type=int, default=8)
    ap.add_argument("--reclean", action="store_true", help="re-clean the RFC corpus")
    ap.add_argument("--resume", action="store_true")
    a = ap.parse_args(argv)

    from data_ingest import build_skills, clean_folder
    import train_model

    print("=" * 64)
    print("  Vio — training your own model on ALL data (one command)")
    print("=" * 64)

    # 1) skills corpus from every knowledge dataset
    print("\n[1/3] Building question->answer skills from knowledge datasets …")
    skills = build_skills()
    extras = [skills]

    # 2) clean the RFC corpus if it was downloaded
    rfc = os.path.join(DATA_DIR, "corpus", "rfc")
    rfc_clean = os.path.join(DATA_DIR, "corpus", "rfc_clean")
    if os.path.isdir(rfc):
        if a.reclean or not os.path.isdir(rfc_clean) or not os.listdir(rfc_clean):
            print("\n[2/3] Cleaning the RFC corpus into prose …")
            clean_folder(rfc, rfc_clean)
        else:
            print(f"\n[2/3] Using already-cleaned RFC corpus at {rfc_clean}")
        extras.append(rfc_clean)
    else:
        print("\n[2/3] No RFC corpus found (corpus/rfc) — training on the knowledge "
              "datasets + skills only.")
        print("      To add the big networking corpus first:  python data_ingest.py rfc --n 800")

    # 3) train on datasets/*.md (added automatically) + skills + cleaned RFCs
    ndatasets = len([p for p in glob.glob(os.path.join(HERE, "datasets", "*.md"))
                     if os.path.basename(p).lower() != "readme.md"])
    print(f"\n[3/3] Training on {ndatasets} knowledge datasets + skills"
          + (" + cleaned RFCs" if len(extras) > 1 else "") + " …\n")

    args = ["--preset", a.preset, "--steps", str(a.steps), "--batch", str(a.batch),
            "--patience", str(a.patience), "--extra", *extras]
    if a.resume:
        args.append("--resume")
    return train_model.main(args)


if __name__ == "__main__":
    sys.exit(main())
