"""
pdftext  —  a tiny, dependency-free PDF text extractor (stdlib zlib only).

So Vio can learn from a real book/PDF, not just .txt — with NO external library.
It inflates the PDF's content streams and pulls the text shown by the Tj / TJ
operators (text in (parentheses) and <hex>). This covers most ordinary text PDFs
(exported from Word, LaTeX, most articles). It cannot read scanned/image-only PDFs
(there is no text to extract) or unusual encodings — in those cases it returns what
it can and the caller falls back to asking for a .txt.

Not a security risk: it never executes anything, only decompresses and regex-scans
bytes. Input size is capped by the web layer.
"""

import re
import zlib


def _decode_text_ops(chunk):
    """Pull visible text from a decoded content stream (Tj strings and TJ arrays)."""
    out = []
    # (string) Tj      and     [(a) -1 (b)] TJ
    for m in re.finditer(rb"\((?:\\.|[^()\\])*\)|<[0-9A-Fa-f\s]+>", chunk):
        tok = m.group(0)
        if tok.startswith(b"("):
            s = tok[1:-1]
            s = re.sub(rb"\\([nrt])", lambda mm: {b"n": b"\n", b"r": b"", b"t": b" "}[mm.group(1)], s)
            s = re.sub(rb"\\([()\\])", rb"\1", s)         # unescape \( \) \\
            s = re.sub(rb"\\[0-9]{1,3}", b"", s)          # drop octal escapes
            out.append(s.decode("latin-1", "ignore"))
        else:                                              # <hex> string
            hx = re.sub(rb"\s+", b"", tok[1:-1])
            if len(hx) % 2:
                hx += b"0"
            try:
                out.append(bytes.fromhex(hx.decode()).decode("latin-1", "ignore"))
            except ValueError:
                pass
    return "".join(out)


def extract_text(data: bytes) -> str:
    """Return the best-effort extracted text of a PDF given as raw bytes."""
    if not data[:5].startswith(b"%PDF"):
        return ""
    texts = []
    for m in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", data, re.DOTALL):
        raw = m.group(1)
        chunk = None
        try:
            chunk = zlib.decompress(raw)                   # FlateDecode (the common case)
        except zlib.error:
            if re.search(rb"\bTj\b|\bTJ\b", raw):          # maybe an uncompressed stream
                chunk = raw
        if not chunk:
            continue
        piece = _decode_text_ops(chunk)
        if piece.strip():
            texts.append(piece)
    text = "\n".join(texts)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
