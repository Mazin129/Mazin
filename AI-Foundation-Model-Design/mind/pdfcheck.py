"""
pdfcheck  —  see exactly what text Vio can pull out of a PDF.

"I taught a file but Vio knows nothing" almost always means the PDF's text
didn't extract — it's an architecture diagram, a scan, or it needs a better
reader. This tells you which, before you waste time wondering.

    python pdfcheck.py "C:\\Users\\mazin\\Docs\\Azure LandingZone Design.pdf"

It reports the best reader available, how much real text came out, whether it's
readable, how many passages Vio would learn, and shows a sample so you can judge.
"""
import sys
import os

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        print('Usage:  python pdfcheck.py "C:\\path\\to\\file.pdf"')
        return 1
    path = argv[0]
    if not os.path.isfile(path):
        print(f"File not found: {path}")
        return 1

    size = os.path.getsize(path)
    print(f"File: {os.path.basename(path)}  ({size/1024:.0f} KB)\n")

    # which reader do we have?
    try:
        import fitz  # noqa: F401
        print("PDF reader: PyMuPDF ✓ (best quality)")
    except Exception:
        try:
            import pdfminer  # noqa: F401
            print("PDF reader: pdfminer (ok) — for best results: pip install pymupdf")
        except Exception:
            print("PDF reader: stdlib fallback only (weak) — run: pip install pymupdf")

    from pdftext import extract_text, looks_readable
    data = open(path, "rb").read()
    text = extract_text(data)
    chars = len(text or "")
    words = len((text or "").split())
    readable = looks_readable(text or "")

    print(f"\nExtracted: {chars} characters, ~{words} words")
    print(f"Readable:  {'yes ✓' if readable else 'NO ✗ (garbled or empty)'}")

    # how many passages would Vio actually learn?
    passages = 0
    try:
        from reasoner import Mind
        m = Mind()
        passages = len(m._chunk(m._denoise(text or "")))
    except Exception:
        pass
    print(f"Passages Vio would learn: {passages}")

    print("\n--- first 700 characters Vio sees ---")
    print((text or "")[:700] or "(nothing)")
    print("--- end sample ---\n")

    # verdict
    density = words / max(size / 1024, 1)          # words per KB
    if chars < 200 or passages <= 2:
        print("VERDICT: almost no text came out. This PDF is a DIAGRAM or SCANNED image —")
        print("  the 'text' is just picture labels, so there's nothing for Vio to learn.")
        print("  Fix: feed Vio the WRITTEN design/HLD doc (sentences), the device configs,")
        print("  or type the key points into a .md/.txt file and teach that instead.")
    elif not readable:
        print("VERDICT: text came out but it's garbled (bad font encoding).")
        print("  Fix: install a stronger reader — pip install pymupdf — and try again.")
    elif density < 3:
        print("VERDICT: very little prose for the file size — likely mostly diagrams/tables")
        print("  with a little text. Vio learned the little text; the diagrams are lost.")
    else:
        print("VERDICT: good — real text extracted. If Vio still 'knows nothing', it's a")
        print("  retrieval/wording issue, not extraction. Ask using words that appear above,")
        print("  and make sure Vio was restarted after teaching so the new passages are indexed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
