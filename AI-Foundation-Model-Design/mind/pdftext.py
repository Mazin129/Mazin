"""
pdftext  —  robust PDF text extraction for Vio.

Reads a real book/manual PDF into text. It tries, in order of quality:
  1. PyMuPDF (fitz)   — best: decodes embedded/CID font CMaps, columns, tables.
                        This is what correctly reads professional manuals (e.g. the
                        FortiOS CLI reference) whose glyphs are NOT plain ASCII.
  2. pdfminer.six     — pure-Python, also decodes font encodings well.
  3. a stdlib zlib    — dependency-free last resort for simple PDFs.
     fallback

Then `looks_readable()` sanity-checks the result: if a PDF's fonts can't be mapped
to real letters, extraction yields garbage (glued/garbled characters). Rather than
letting Vio "learn" thousands of unreadable passages and then answer nothing, the
caller checks readability and tells the user honestly.

    pip install pymupdf            # strongly recommended
    # (pdfminer.six also works;  the stdlib fallback needs nothing)
"""

import re
import zlib
from io import BytesIO


# --------------------------------------------------------------------------- #
# 1) PyMuPDF  (best quality)
# --------------------------------------------------------------------------- #
# Each backend is probed for importability at most ONCE and the result cached, so a
# broken optional dependency doesn't repeatedly raise (and spam stderr) on every PDF.
# NB: we catch BaseException, not just Exception — a broken native binding can raise
# non-Exception errors at import (e.g. pdfminer -> cryptography -> a Rust pyo3
# PanicException). That must never take Vio down; we fall through to the next backend.
_backend = {}          # name -> callable / False (unavailable) / absent (untried)


def _load(name, importer):
    if name not in _backend:
        try:
            _backend[name] = importer()
        except (KeyboardInterrupt, SystemExit):
            raise
        except BaseException:
            _backend[name] = False
    return _backend[name]


def _extract_pymupdf(data: bytes):
    fitz = _load("fitz", lambda: __import__("fitz"))
    if not fitz:
        return None
    try:
        with fitz.open(stream=data, filetype="pdf") as doc:
            return "\n".join(page.get_text("text") for page in doc)
    except (KeyboardInterrupt, SystemExit):
        raise
    except BaseException:
        return None


# --------------------------------------------------------------------------- #
# 2) pdfminer.six
# --------------------------------------------------------------------------- #
def _extract_pdfminer(data: bytes):
    def _imp():
        from pdfminer.high_level import extract_text as _pm
        return _pm
    pm = _load("pdfminer", _imp)
    if not pm:
        return None
    try:
        return pm(BytesIO(data))
    except (KeyboardInterrupt, SystemExit):
        raise
    except BaseException:
        return None


# --------------------------------------------------------------------------- #
# 3) stdlib fallback — parse text-showing operators, reconstruct spaces from
#    TJ kerning and line breaks from positioning operators (handles simple PDFs).
# --------------------------------------------------------------------------- #
_TJ_SPACE = 100
_STR = rb"\((?:\\.|[^()\\])*\)|<[0-9A-Fa-f\s]*>"
_SCAN = re.compile(
    rb"(?P<arr>\[(?:" + _STR + rb"|[^\[\]])*\])\s*TJ"
    rb"|(?P<s>" + _STR + rb")\s*(?P<op>Tj|'|\")"
    rb"|(?P<mv>Td|TD|T\*|Tm|ET|BT)",
    re.DOTALL,
)
_ELEM = re.compile(_STR + rb"|-?\d+\.?\d*")


def _decode_string(tok: bytes) -> str:
    if tok.startswith(b"("):
        s = tok[1:-1]
        s = re.sub(rb"\\n", b"\n", s)
        s = re.sub(rb"\\r", b"", s)
        s = re.sub(rb"\\t", b" ", s)
        s = re.sub(rb"\\[bf]", b"", s)
        s = re.sub(rb"\\([0-7]{1,3})", lambda m: bytes([int(m.group(1), 8) & 0xFF]), s)
        s = re.sub(rb"\\([()\\])", rb"\1", s)
        return s.decode("latin-1", "ignore")
    hx = re.sub(rb"\s+", b"", tok[1:-1])
    if len(hx) % 2:
        hx += b"0"
    try:
        return bytes.fromhex(hx.decode()).decode("latin-1", "ignore")
    except ValueError:
        return ""


def _decode_tj_array(arr: bytes) -> str:
    out = []
    for m in _ELEM.finditer(arr[1:-1]):
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
        if m.group("arr"):
            out.append(_decode_tj_array(m.group("arr")))
        elif m.group("s"):
            out.append(_decode_string(m.group("s")))
            if m.group("op") in (b"'", b'"'):
                out.append("\n")
        elif m.group("mv"):
            out.append("\n")
    return "".join(out)


def _extract_stdlib(data: bytes):
    if not data[:5].startswith(b"%PDF"):
        return ""
    texts = []
    for m in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", data, re.DOTALL):
        raw = m.group(1)
        chunk = None
        try:
            chunk = zlib.decompress(raw)
        except zlib.error:
            if re.search(rb"\bTj\b|\bTJ\b|\bT\*\b", raw):
                chunk = raw
        if not chunk:
            continue
        piece = _decode_stream(chunk)
        if piece.strip():
            texts.append(piece)
    return "\n".join(texts)


def _tidy(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# common English words — their presence is a strong signal the text is real prose
_COMMON = {"the", "and", "to", "of", "a", "in", "is", "for", "on", "with", "that",
           "this", "or", "be", "are", "as", "at", "by", "an", "it", "from", "can",
           "you", "your", "not", "if", "when", "use", "set", "all"}


def looks_readable(text: str) -> bool:
    """True if the extracted text looks like real language rather than the
    garbled character soup a failed font-decode produces."""
    if not text or len(text) < 20:
        return False
    words = re.findall(r"[A-Za-z]+", text)
    if len(words) < 10:
        return False
    avg = sum(len(w) for w in words) / len(words)
    long_ratio = sum(1 for w in words if len(w) > 18) / len(words)
    space_ratio = text.count(" ") / len(text)
    common_ratio = sum(1 for w in words if w.lower() in _COMMON) / len(words)
    # real prose: modest average word length, some spaces, and common words present
    return avg < 12 and long_ratio < 0.10 and space_ratio > 0.04 and common_ratio > 0.015


def extract_text(data: bytes) -> str:
    """Best-quality text from a PDF, trying the strongest reader available.
    Returns whichever result looks readable; if none do, returns the best raw
    attempt (the caller decides what to tell the user via looks_readable)."""
    best = ""
    for fn in (_extract_pymupdf, _extract_pdfminer, _extract_stdlib):
        try:
            txt = fn(data)
        except (KeyboardInterrupt, SystemExit):
            raise
        except BaseException:
            txt = None
        if not txt:
            continue
        txt = _tidy(txt)
        if looks_readable(txt):
            return txt                 # first readable result wins (highest quality first)
        if len(txt) > len(best):
            best = txt
    return best
