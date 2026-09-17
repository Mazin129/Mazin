"""
ingest  —  bulk-load a whole FOLDER of documents into Vio's library.

Point it at a folder of manuals, cheat sheets, and device configs and Vio reads
them all into its knowledge in one pass — then it answers from YOUR material.
This is the reliable, free way to make Vio know your stack (retrieval), and it
also grows the question→answer data a future fine-tune would learn from.

    python ingest.py "C:\\Users\\mazin\\Docs\\network"     # a folder of files
    python ingest.py .                                       # the current folder

Reads PDFs (needs: pip install pymupdf for clean text), text, markdown, .cfg/.conf
running-configs, .log, .csv/.tsv. It only READS files — it never runs anything.
Configs are kept whole per stanza; prose is split into passages; tables load as data.
"""
import sys
import os

# UTF-8 output so ✓ → • never crash a legacy Windows console (cp1252).
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        print("Usage:  python ingest.py <folder>")
        print('Example: python ingest.py "C:\\Users\\mazin\\Docs\\network"')
        return 1
    path = argv[0]
    if not os.path.isdir(path):
        print(f"Not a folder: {path}")
        return 1

    from reasoner import Mind
    mind = Mind()
    print(f"Scanning {os.path.abspath(path)} …\n")
    r = mind.learn_folder(path)

    for name, info in r.get("per", []):
        print(f"  ✓ {name}: {info}")
    for name, why in r.get("skipped", []):
        print(f"  – skipped {name}: {why}")

    if not r.get("files"):
        print("\nNothing learned. Put PDFs / text / configs in the folder and try again.")
        print("(Scanned-image PDFs need OCR — save them as text first, or install pymupdf.)")
        return 0
    print(f"\n✓ Learned {r['passages']} passages from {r['files']} file(s)"
          + (f", skipped {len(r['skipped'])}" if r.get("skipped") else "") + ".")
    print("  Start Vio (python web.py) and ask about them — answers now use your documents.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
