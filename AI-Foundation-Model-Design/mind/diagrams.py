"""
diagrams  —  turn diagram and image files into text Vio can actually learn.

A network diagram's value is its COMPONENTS and how they CONNECT. draw.io and
Visio files are XML underneath, so we can recover both — a box becomes a
component, an arrow becomes a relationship ("A connects to B") — which is real,
answerable knowledge, unlike a flat picture. Images fall back to OCR.

  .drawio / .xml   → draw.io graph  (components + connections)   [stdlib]
  .vsdx            → Visio graph    (shape text)                 [stdlib]
  .png/.jpg/…      → OCR            (needs: pip install pytesseract pillow + Tesseract)

Everything runs locally. Each reader returns plain text, or "" if it can't.
"""
from __future__ import annotations

import base64
import html
import io
import re
import zlib
import zipfile
import xml.etree.ElementTree as ET
from urllib.parse import unquote


def _clean(v: str) -> str:
    """A cell label may contain HTML (<br>, <b>…); strip tags and unescape."""
    v = re.sub(r"<[^>]+>", " ", v or "")
    return re.sub(r"\s+", " ", html.unescape(v)).strip()


def _inflate_diagram(payload: str) -> str:
    """A <diagram> body is either raw mxGraphModel XML or draw.io's compressed
    form (base64 → raw-deflate → url-encoded XML). Return the XML either way."""
    s = (payload or "").strip()
    if not s:
        return ""
    if s.lstrip().startswith("<"):
        return s
    try:
        raw = base64.b64decode(s)
        try:
            data = zlib.decompress(raw, -15)      # raw DEFLATE (draw.io default)
        except zlib.error:
            data = zlib.decompress(raw)           # zlib-wrapped fallback
        return unquote(data.decode("utf-8", "ignore"))
    except Exception:
        return ""


def drawio_to_text(data: bytes) -> str:
    """Extract components and connections from a .drawio / mxGraph .xml file."""
    txt = data.decode("utf-8", "ignore")
    payloads = re.findall(r"<diagram[^>]*>(.*?)</diagram>", txt, re.S) or [txt]
    nodes: dict[str, str] = {}
    edges: list[tuple[str | None, str | None, str]] = []
    for p in payloads:
        xmlt = _inflate_diagram(p)
        if "mxCell" not in xmlt:
            continue
        try:
            root = ET.fromstring(xmlt)
            cells = list(root.iter("mxCell"))
        except Exception:
            continue
        for c in cells:
            cid, val = c.get("id"), _clean(c.get("value") or "")
            if c.get("edge") == "1" or c.get("source") or c.get("target"):
                edges.append((c.get("source"), c.get("target"), val))
            elif cid and val:
                nodes[cid] = val

    lines: list[str] = []
    comps = sorted({v for v in nodes.values() if v})
    if comps:
        lines.append("Diagram components: " + ", ".join(comps) + ".")
    for src, tgt, label in edges:
        a, b = nodes.get(src or ""), nodes.get(tgt or "")
        if a and b:
            via = f" ({label})" if label else ""
            lines.append(f"{a} connects to {b}{via}.")
        elif label and (a or b):
            lines.append(f"{a or b}: {label}.")
    return "\n".join(lines)


def vsdx_to_text(data: bytes) -> str:
    """Extract shape text from a Visio .vsdx (a zip of page XML)."""
    out: list[str] = []
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
    except Exception:
        return ""
    for name in z.namelist():
        if "pages/" in name and name.endswith(".xml"):
            try:
                xmlt = z.read(name).decode("utf-8", "ignore")
            except Exception:
                continue
            for m in re.findall(r"<Text\b[^>]*>(.*?)</Text>", xmlt, re.S):
                t = _clean(m)
                if len(t) > 1:
                    out.append(t)
    return "\n".join(dict.fromkeys(out))          # de-dup, keep order


def ocr_image(data: bytes) -> str | None:
    """OCR text from an image. Returns None if the OCR stack isn't installed."""
    try:
        import pytesseract
        from PIL import Image
    except Exception:
        return None
    try:
        return pytesseract.image_to_string(Image.open(io.BytesIO(data))) or ""
    except Exception:
        return None


# extensions this module can handle (used by the ingest dispatch)
DRAWIO_EXTS = (".drawio", ".xml")
VISIO_EXTS = (".vsdx",)
IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".webp")


def file_to_text(name: str, data: bytes):
    """Dispatch by extension. Returns (text, kind) or (None, reason)."""
    low = name.lower()
    if low.endswith(DRAWIO_EXTS):
        t = drawio_to_text(data)
        return (t, "diagram") if t else (None, "no components found in the diagram XML")
    if low.endswith(VISIO_EXTS):
        t = vsdx_to_text(data)
        return (t, "diagram") if t else (None, "no readable shape text in the Visio file")
    if low.endswith(IMAGE_EXTS):
        t = ocr_image(data)
        if t is None:
            return (None, "OCR not installed (pip install pytesseract pillow + Tesseract)")
        return (t, "image-ocr") if t.strip() else (None, "no readable text found in the image")
    return (None, "unsupported file type")
