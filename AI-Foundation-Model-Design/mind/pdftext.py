"""
pdftext  —  a tiny, dependency-free PDF text extractor (stdlib zlib only).

So Vio can learn from a real book/PDF, not just .txt — with NO external library.
It inflates the PDF's content streams and reconstructs the visible text from the
text-showing operators (Tj / TJ / ' / "). This covers most ordinary text PDFs
(exported from Word, LaTeX, most manuals/articles). It cannot read scanned/image-only
PDFs (there is no text to extract) or unusual font encodings — in those cases it
returns what it can and the caller falls back to asking for a .txt.

WHY THIS IS NOT A NAIVE REGEX GRAB. In PDF, the space between words is very often
NOT a space character — it is a small negative number inside a TJ array (kerning),
e.g. `[(execute) -250 (ping)]`. A naive extractor concatenates the strings and gets
"executeping", which then matches no search query (the bug this file fixes). Here we:
  • turn a sufficiently-negative TJ adjustment into a real space, and
  • start a new line on text-positioning operators (Td/TD/T*/Tm/'/"),
so words stay separated and lines stay apart — which is what retrieval needs.

Not a security risk: it never executes anything, only decompresses and scans bytes.
Input size is capped by the web layer.
"""

import re
import zlib

# A TJ number more negative than this denotes a word gap -> emit a space.
# (Units are 1/1000 of an em; a real space is ~250-330, inter-word kerning often
#  -120..-400. 100 is a safe, slightly generous threshold.)
_TJ_SPACE = 100

_STR = rb"\((?:\\.|[^()\\])*\)|<[0-9A-Fa-f\s]*>"
# ordered scan: a TJ array, or a single show-string + its operator, or a line-mover.
_SCAN = re.compile(
    rb"(?P<arr>\[(?:" + _STR + rb"|[^\[\]])*\])\s*TJ"
    rb"|(?P<s>" + _STR + rb")\s*(?P<op>Tj|'|\")"
    rb"|(?P<mv>Td|TD|T\*|Tm|ET|BT)",
    re.DOTALL,
)


def _decode_string(tok: bytes) -> str:
    """Decode one PDF string token: (literal) or <hex>."""
    if tok.startswith(b"("):
        s = tok[1:-1]
        s = re.sub(rb"\\n", b"\n", s)
        s = re.sub(rb"\\r", b"", s)
        s = re.sub(rb"\\t", b" ", s)
        s = re.sub(rb"\\[bf]", b"", s)
        s = re.sub(rb"\\([0-7]{1,3})", lambda m: bytes([int(m.group(1), 8) & 0xFF]), s)
        s = re.sub(rb"\\([()\\])", rb"\1", s)
        return s.decode("latin-1", "ignore")
    hx = re.sub(rb"\s+", b"", tok[1:-1])          # <hex>
    if len(hx) % 2:
        hx += b"0"
    try:
        return bytes.fromhex(hx.decode()).decode("latin-1", "ignore")
    except ValueError:
        return ""


_ELEM = re.compile(_STR + rb"|-?\d+\.?\d*")


def _decode_tj_array(arr: bytes) -> str:
    """Decode a TJ array, turning big negative kerns into spaces."""
    out = []
    for m in _ELEM.finditer(arr[1:-1]):           # strip the [ ]
        tok = m.group(0)
        if tok[:1] in (b"(", b"<"):
            out.append(_decode_string(tok))
        else:
            try:
                if -float(tok) >= _TJ_SPACE:
                    out.append(" ")
            except ValueError:
                pass
    return "".join(out)


def _decode_stream(chunk: bytes) -> str:
    out = []
    for m in _SCAN.finditer(chunk):
        if m.lastgroup == "arr" or m.group("arr"):
            out.append(_decode_tj_array(m.group("arr")))
        elif m.group("s"):
            out.append(_decode_string(m.group("s")))
            if m.group("op") in (b"'", b'"'):     # show-and-move-to-next-line
                out.append("\n")
        elif m.group("mv"):                        # line movement / block edges
            out.append("\n")
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
            chunk = zlib.decompress(raw)                   # FlateDecode (common)
        except zlib.error:
            if re.search(rb"\bTj\b|\bTJ\b|\bT\*\b", raw):  # maybe uncompressed
                chunk = raw
        if not chunk:
            continue
        piece = _decode_stream(chunk)
        if piece.strip():
            texts.append(piece)
    text = "\n".join(texts)
    text = re.sub(r"[ \t]+", " ", text)               # collapse runs of spaces
    text = re.sub(r" *\n *", "\n", text)              # trim spaces around newlines
    text = re.sub(r"\n{3,}", "\n\n", text)            # cap blank runs
    return text.strip()
