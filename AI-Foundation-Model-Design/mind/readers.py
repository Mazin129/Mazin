"""
readers — one front door for every kind of file Vio is taught.

`read_file(name, data)` turns raw bytes into clean text plus an honest account of how it
was read. Office formats are read with the standard library alone (a .docx/.xlsx/.pptx is
a zip of XML), so they always work; PDFs use the strongest installed reader and fall back
to OCR for scanned pages; nothing is uploaded anywhere.

    Documents   .pdf  .docx .docm .odt .rtf .txt .md .rst .html .htm
    Sheets      .xlsx .xlsm .ods .csv .tsv           (also kept as a queryable table)
    Slides      .pptx .odp
    Mail        .eml
    Data/config .json .yaml .yml .xml .ini .cfg .conf .log  and any other text file
    Diagrams    .drawio .vsdx                         (components + connections)
    Images      .png .jpg .jpeg .gif .bmp .tif .tiff .webp  (OCR)
    Archives    .zip                                  (every readable member)

Install once for the best PDF and OCR results (doctor.py checks them):
    pip install pymupdf pypdf rapidocr-onnxruntime
"""
from __future__ import annotations

import csv
import io
import json
import re
import zipfile
from dataclasses import dataclass, field as _field
from html.parser import HTMLParser
from xml.etree import ElementTree as ET


@dataclass
class ReadResult:
    text: str = ""
    kind: str = ""                     # "pdf", "word", "sheet", "slides", "image-ocr", …
    method: str = ""                   # which reader actually produced the text
    pages: int = 0                     # pages / slides / sheets seen
    tables: list = _field(default_factory=list)   # [(name, csv_text)] for the data engine
    notes: list = _field(default_factory=list)    # honest remarks for the user
    error: str = ""                    # why nothing usable came out

    @property
    def ok(self):
        return bool(self.text.strip()) and not self.error


DOC_EXTS = (".pdf", ".docx", ".docm", ".odt", ".rtf", ".txt", ".text", ".md", ".markdown",
            ".rst", ".html", ".htm")
SHEET_EXTS = (".xlsx", ".xlsm", ".ods", ".csv", ".tsv")
SLIDE_EXTS = (".pptx", ".odp")
MAIL_EXTS = (".eml",)
DATA_EXTS = (".json", ".yaml", ".yml", ".xml", ".ini", ".cfg", ".conf", ".config",
             ".log", ".toml")
DIAGRAM_EXTS = (".drawio", ".vsdx")
IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tif", ".tiff", ".webp")
ARCHIVE_EXTS = (".zip",)
ALL_EXTS = (DOC_EXTS + SHEET_EXTS + SLIDE_EXTS + MAIL_EXTS + DATA_EXTS + DIAGRAM_EXTS
            + IMAGE_EXTS + ARCHIVE_EXTS)
# legacy binary Office formats: say exactly what to do instead of reading garbage
_LEGACY = {".doc": ".docx", ".xls": ".xlsx", ".ppt": ".pptx", ".msg": ".eml"}


def _ext(name):
    m = re.search(r"(\.[A-Za-z0-9]+)$", (name or "").lower())
    return m.group(1) if m else ""


# --------------------------------------------------------------------------- #
# text decoding
# --------------------------------------------------------------------------- #
def decode_text(data: bytes) -> str:
    if data.startswith(b"\xef\xbb\xbf"):
        return data[3:].decode("utf-8", "replace")
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16", "replace")
    for enc in ("utf-8", "cp1252", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", "replace")


def looks_binary(data: bytes) -> bool:
    head = data[:4096]
    return b"\x00" in head and not head.startswith((b"\xff\xfe", b"\xfe\xff"))


def _tidy(text):
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


# --------------------------------------------------------------------------- #
# Office Open XML (.docx .pptx .xlsx) — standard library only
# --------------------------------------------------------------------------- #
_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
_S = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"


def _para_text(p):
    out = []
    for node in p.iter():
        if node.tag == _W + "t" and node.text:
            out.append(node.text)
        elif node.tag in (_W + "tab",):
            out.append("\t")
        elif node.tag in (_W + "br", _W + "cr"):
            out.append("\n")
    return "".join(out).strip()


def _docx_body(root):
    """Paragraphs in order (headings as Markdown headings, list items as bullets) and
    tables as 'Header: value' rows, so every cell keeps the meaning of its column."""
    lines, tables = [], []
    body = root.find(_W + "body")
    if body is None:
        return lines, tables
    for el in body:
        if el.tag == _W + "p":
            t = _para_text(el)
            if not t:
                continue
            style = el.find(f"{_W}pPr/{_W}pStyle")
            sv = (style.get(_W + "val") if style is not None else "") or ""
            m = re.match(r"(?i)heading\s*(\d)|title", sv.replace("Heading", "heading "))
            if m:
                lines.append("#" * int(m.group(1) or 1) + " " + t)
            elif el.find(f"{_W}pPr/{_W}numPr") is not None or sv.lower().startswith("list"):
                lines.append("• " + t)
            else:
                lines.append(t)
        elif el.tag == _W + "tbl":
            rows = []
            for tr in el.iter(_W + "tr"):
                cells = [" ".join(_para_text(p) for p in tc.iter(_W + "p")).strip()
                         for tc in tr.iter(_W + "tc")]
                if any(cells):
                    rows.append(cells)
            if rows:
                tables.append(rows)
                lines.append(_table_text(rows))
    return lines, tables


def _table_text(rows):
    """A table as readable lines. With a header row, each data row reads
    'Header1: v1; Header2: v2' — the form retrieval and the model both understand."""
    if len(rows) < 2:
        return " | ".join(rows[0]) if rows else ""
    head = rows[0]
    if len(set(h for h in head if h)) >= max(1, len(head) // 2):
        out = []
        for r in rows[1:]:
            pairs = [f"{h}: {v}" for h, v in zip(head, r) if v and h]
            extra = [v for v in r[len(head):] if v]
            if pairs or extra:
                out.append("; ".join(pairs + extra))
        return "\n".join(out)
    return "\n".join(" | ".join(c for c in r if c) for r in rows)


def _rows_csv(rows):
    buf = io.StringIO()
    csv.writer(buf).writerows(rows)
    return buf.getvalue()


def read_docx(data):
    z = zipfile.ZipFile(io.BytesIO(data))
    parts, tables = [], []
    names = z.namelist()
    for n in ["word/document.xml"] + sorted(x for x in names if re.match(
            r"word/(header|footer|footnotes|endnotes)\d*\.xml$", x)):
        if n not in names:
            continue
        lines, tbls = _docx_body(ET.fromstring(z.read(n))) if n == "word/document.xml" \
            else ([_para_text(p) for p in ET.fromstring(z.read(n)).iter(_W + "p")], [])
        parts += [ln for ln in lines if ln]
        tables += tbls
    r = ReadResult(_tidy("\n".join(parts)), "word", "docx (built-in)")
    r.tables = [(f"table {i + 1}", _rows_csv(t)) for i, t in enumerate(tables)
                if len(t) >= 3]
    if tables:
        r.notes.append(f"{len(tables)} table(s) read row by row")
    return r


def read_pptx(data):
    z = zipfile.ZipFile(io.BytesIO(data))
    slides = sorted((n for n in z.namelist() if re.match(r"ppt/slides/slide\d+\.xml$", n)),
                    key=lambda n: int(re.search(r"(\d+)", n.rsplit("/", 1)[-1]).group(1)))
    out = []
    for i, n in enumerate(slides, 1):
        root = ET.fromstring(z.read(n))
        paras = []
        for p in root.iter(_A + "p"):
            t = "".join(x.text or "" for x in p.iter(_A + "t")).strip()
            if t:
                paras.append(t)
        note_n = f"ppt/notesSlides/notesSlide{i}.xml"
        notes = []
        if note_n in z.namelist():
            for p in ET.fromstring(z.read(note_n)).iter(_A + "p"):
                t = "".join(x.text or "" for x in p.iter(_A + "t")).strip()
                if t and not t.isdigit():
                    notes.append(t)
        if paras or notes:
            out.append(f"## Slide {i}: {paras[0] if paras else ''}".rstrip(": ")
                       + ("\n" + "\n".join("• " + t for t in paras[1:]) if paras[1:] else "")
                       + ("\nSpeaker notes: " + " ".join(notes) if notes else ""))
    r = ReadResult(_tidy("\n\n".join(out)), "slides", "pptx (built-in)", pages=len(slides))
    return r


def _col_index(ref):
    letters = re.match(r"([A-Z]+)", ref or "A").group(1)
    n = 0
    for ch in letters:
        n = n * 26 + ord(ch) - 64
    return n - 1


def read_xlsx(data):
    z = zipfile.ZipFile(io.BytesIO(data))
    names = z.namelist()
    shared = []
    if "xl/sharedStrings.xml" in names:
        for si in ET.fromstring(z.read("xl/sharedStrings.xml")).iter(_S + "si"):
            shared.append("".join(t.text or "" for t in si.iter(_S + "t")))
    # sheet names in workbook order
    sheet_names = {}
    try:
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        target = {r.get("Id"): r.get("Target") for r in rels}
        for s in wb.iter(_S + "sheet"):
            t = target.get(s.get(_R + "id"), "")
            sheet_names["xl/" + t.lstrip("/").replace("xl/", "")] = s.get("name")
    except Exception:
        pass
    sheets = sorted(n for n in names if re.match(r"xl/worksheets/sheet\d+\.xml$", n))
    texts, tables = [], []
    for n in sheets:
        rows = []
        for row in ET.fromstring(z.read(n)).iter(_S + "row"):
            vals = {}
            for c in row.iter(_S + "c"):
                t, v = c.get("t"), c.find(_S + "v")
                if t == "s" and v is not None:
                    val = shared[int(v.text)] if v.text and int(v.text) < len(shared) else ""
                elif t == "inlineStr":
                    val = "".join(x.text or "" for x in c.iter(_S + "t"))
                else:
                    val = v.text if v is not None and v.text else ""
                if val != "":
                    vals[_col_index(c.get("r"))] = val.strip()
            if vals:
                width = max(vals) + 1
                rows.append([vals.get(i, "") for i in range(width)])
        if not rows:
            continue
        sname = sheet_names.get(n) or n.rsplit("/", 1)[-1][:-4]
        texts.append(f"## Sheet: {sname}\n" + _table_text(rows))
        if len(rows) >= 3:
            tables.append((sname, _rows_csv(rows)))
    r = ReadResult(_tidy("\n\n".join(texts)), "sheet", "xlsx (built-in)", pages=len(sheets))
    r.tables = tables
    return r


# --------------------------------------------------------------------------- #
# OpenDocument (.odt .ods .odp) — content.xml
# --------------------------------------------------------------------------- #
def read_odf(data, kind):
    z = zipfile.ZipFile(io.BytesIO(data))
    root = ET.fromstring(z.read("content.xml"))
    tns = "{urn:oasis:names:tc:opendocument:xmlns:text:1.0}"
    out = []
    for el in root.iter():
        if el.tag in (tns + "h", tns + "p"):
            t = "".join(el.itertext()).strip()
            if t:
                out.append(("## " if el.tag == tns + "h" else "") + t)
    return ReadResult(_tidy("\n".join(out)), kind, "opendocument (built-in)")


# --------------------------------------------------------------------------- #
# HTML, RTF, e-mail, JSON
# --------------------------------------------------------------------------- #
class _HTMLText(HTMLParser):
    _BLOCK = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "section",
              "article", "table", "pre"}

    def __init__(self):
        super().__init__()
        self.out, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self.skip += 1
        elif tag in self._BLOCK:
            self.out.append("\n")
            if tag in ("h1", "h2", "h3"):
                self.out.append("#" * int(tag[1]) + " ")
            elif tag == "li":
                self.out.append("• ")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript") and self.skip:
            self.skip -= 1
        elif tag in ("td", "th"):
            self.out.append(" | ")

    def handle_data(self, d):
        if not self.skip:
            self.out.append(d)


def read_html(text):
    p = _HTMLText()
    p.feed(text)
    return ReadResult(_tidy("".join(p.out)), "web page", "html (built-in)")


def read_rtf(text):
    t = re.sub(r"\\par[d]?\b", "\n", text)
    t = re.sub(r"\\'([0-9a-fA-F]{2})", lambda m: bytes.fromhex(m.group(1)).decode("cp1252"), t)
    t = re.sub(r"\\[a-zA-Z]+-?\d* ?|[{}]", "", t)
    return ReadResult(_tidy(t), "document", "rtf (built-in)")


def read_eml(data):
    import email
    from email import policy
    msg = email.message_from_bytes(data, policy=policy.default)
    head = [f"{h}: {msg[h]}" for h in ("From", "To", "Cc", "Date", "Subject") if msg[h]]
    body, attached = "", []
    for part in msg.walk():
        if part.is_attachment():
            attached.append((part.get_filename() or "attachment", part.get_content()))
        elif part.get_content_type() == "text/plain" and not body:
            body = part.get_content()
        elif part.get_content_type() == "text/html" and not body:
            body = read_html(part.get_content()).text
    r = ReadResult(_tidy("\n".join(head) + "\n\n" + (body or "")), "e-mail", "eml (built-in)")
    for fname, content in attached[:10]:
        if isinstance(content, (bytes, bytearray)):
            sub = read_file(fname, bytes(content))
            if sub.ok:
                r.text += f"\n\n## Attachment: {fname}\n" + sub.text
                r.tables += sub.tables
                r.notes.append(f"read attachment {fname}")
    return r


def read_json(text):
    try:
        obj = json.loads(text)
    except Exception:
        return ReadResult(_tidy(text), "data", "text")
    lines = []

    def walk(o, path):
        if isinstance(o, dict):
            for k, v in o.items():
                walk(v, f"{path}.{k}" if path else str(k))
        elif isinstance(o, list):
            for i, v in enumerate(o[:500]):
                walk(v, f"{path}[{i}]")
        else:
            lines.append(f"{path}: {o}")
    walk(obj, "")
    return ReadResult("\n".join(lines[:20000]), "data", "json (flattened)")


# --------------------------------------------------------------------------- #
# PDF and OCR
# --------------------------------------------------------------------------- #
# A broken native dependency can raise a non-Exception at import (pypdf → cryptography
# → a Rust PanicException). Optional readers must never take Vio down, so imports and
# calls of optional libraries catch BaseException (but let Ctrl-C through).
def _safe(fn, *a):
    try:
        return fn(*a)
    except (KeyboardInterrupt, SystemExit):
        raise
    except BaseException:
        return None


def _pypdf(data):
    def run():
        from pypdf import PdfReader
        return "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(data)).pages)
    return _safe(run)


def ocr_available():
    import importlib.util
    if importlib.util.find_spec("rapidocr_onnxruntime") is not None:
        return "rapidocr"
    def tess():
        import pytesseract
        pytesseract.get_tesseract_version()
        return "tesseract"
    return _safe(tess)


_RAPID = None


def ocr_png(png_bytes):
    """Text from an image, with whichever OCR engine is installed; None if none is."""
    return _safe(_ocr_png, png_bytes)


def _ocr_png(png_bytes):
    global _RAPID
    eng = ocr_available()
    if eng == "rapidocr":
        from rapidocr_onnxruntime import RapidOCR
        if _RAPID is None:
            _RAPID = RapidOCR()
        res, _ = _RAPID(png_bytes)
        return "\n".join(r[1] for r in (res or []))
    if eng == "tesseract":
        import pytesseract
        from PIL import Image
        return pytesseract.image_to_string(Image.open(io.BytesIO(png_bytes))) or ""
    return None


def read_pdf(data):
    import pdftext
    best, method = "", ""
    for label, fn in (("PyMuPDF", pdftext._extract_pymupdf), ("pypdf", _pypdf),
                      ("pdfminer", pdftext._extract_pdfminer),
                      ("built-in", pdftext._extract_stdlib)):
        t = _safe(fn, data)
        if t and pdftext.looks_readable(t) and len(t.split()) > len(best.split()):
            best, method = t, label
            if label == "PyMuPDF":
                break
    def count():
        with pdftext._import_pymupdf().open(stream=data, filetype="pdf") as doc:
            return doc.page_count
    pages = _safe(count) or len(re.findall(rb"/Type\s*/Page[^s]", data))
    r = ReadResult(_tidy(best), "pdf", method, pages=pages)
    # tables: PyMuPDF finds them on the page; read each row with its column headers
    # (a design document's subnet plan or rule base is in tables, not in prose)
    tbls = _safe(_pdf_tables, data) or []
    if tbls:
        r.text += "\n\n## Tables\n" + "\n\n".join(_table_text(t) for t in tbls)
        r.tables = [(f"table {i + 1}", _rows_csv(t)) for i, t in enumerate(tbls)
                    if len(t) >= 3]
        r.notes.append(f"{len(tbls)} table(s) read row by row")
    # scanned pages: little text per page → OCR the page images when we can
    thin = pages >= 2 and len(best.split()) < 40 * pages
    if not best or thin:
        ocr = _ocr_pdf(data)
        if ocr and len(ocr.split()) > len(best.split()):
            r.text, r.method = _tidy(ocr), (method + " + OCR" if best else "OCR")
            r.notes.append("pages were images (scanned) — read them with OCR")
        elif not best:
            r.error = _pdf_help()
        elif thin:
            r.notes.append("some pages have little text (pictures or diagrams); "
                           + ("OCR found nothing more" if ocr_available() else
                              "install OCR to read them: pip install rapidocr-onnxruntime"))
    return r


def _pdf_tables(data, max_pages=200):
    import pdftext
    fitz = pdftext._import_pymupdf()
    out = []
    with fitz.open(stream=data, filetype="pdf") as doc:
        for i, page in enumerate(doc):
            if i >= max_pages or not hasattr(page, "find_tables"):
                break
            for t in page.find_tables().tables:
                rows = [[re.sub(r"\s+", " ", c or "").strip() for c in row]
                        for row in t.extract()]
                rows = [r for r in rows if any(r)]
                if len(rows) >= 2:
                    out.append(rows)
    return out


def _ocr_pdf(data, max_pages=60):
    if not ocr_available():
        return None

    def run():
        import pdftext
        out = []
        with pdftext._import_pymupdf().open(stream=data, filetype="pdf") as doc:
            for i, page in enumerate(doc):
                if i >= max_pages:
                    break
                t = ocr_png(page.get_pixmap(dpi=200).tobytes("png")) or ""
                if t.strip():
                    out.append(f"## Page {i + 1}\n{t}")
        return "\n\n".join(out)
    return _safe(run)


def _pdf_help():
    have = []
    for mod in ("pymupdf", "pypdf", "pdfminer"):
        if _safe(__import__, mod) is not None:
            have.append(mod)
    if "pymupdf" not in have:
        return ("no PDF reader strong enough for this file is installed. Run:  "
                "pip install pymupdf pypdf rapidocr-onnxruntime   — then upload it again. "
                "(Most PDFs exported from Word need PyMuPDF to decode their fonts.)")
    if not ocr_available():
        return ("this PDF has no text layer (scanned pages). Install OCR and upload it "
                "again:  pip install rapidocr-onnxruntime")
    return "the PDF contains no readable text, even with OCR"


# --------------------------------------------------------------------------- #
# the front door
# --------------------------------------------------------------------------- #
def read_file(name: str, data: bytes, _depth=0) -> ReadResult:
    ext = _ext(name)
    try:
        if ext in _LEGACY:
            return ReadResult(error=f"{ext} is the old binary Office format — open it and "
                                    f"'Save As' {_LEGACY[ext]}, then upload that")
        if ext == ".pdf" or data[:5] == b"%PDF-":
            return read_pdf(data)
        if ext in (".docx", ".docm"):
            return read_docx(data)
        if ext in (".xlsx", ".xlsm"):
            return read_xlsx(data)
        if ext == ".pptx":
            return read_pptx(data)
        if ext in (".odt", ".ods", ".odp"):
            return read_odf(data, {"t": "document", "s": "sheet", "p": "slides"}[ext[3]])
        if ext in MAIL_EXTS:
            return read_eml(data)
        if ext in DIAGRAM_EXTS:
            from diagrams import file_to_text
            t, kind = file_to_text(name, data)
            return ReadResult(t or "", "diagram", kind, error="" if t else kind)
        if ext in IMAGE_EXTS:
            t = ocr_png(data)
            if t is None:
                return ReadResult(error="no OCR engine installed — run:  "
                                        "pip install rapidocr-onnxruntime")
            return ReadResult(_tidy(t), "image-ocr", ocr_available() or "ocr",
                              error="" if t.strip() else "no readable text in the image")
        if ext in ARCHIVE_EXTS and _depth < 2:
            return _read_zip(data, _depth)
        if looks_binary(data):
            return ReadResult(error=f"{ext or 'this'} is a binary format I can't read")
        text = decode_text(data)
        if ext in (".csv", ".tsv"):
            r = ReadResult(text, "sheet", "csv")
            r.tables = [(re.sub(r"\.(csv|tsv)$", "", name, flags=re.I), text)]
            return r
        if ext in (".html", ".htm") or re.match(r"\s*<!doctype html|\s*<html", text, re.I):
            return read_html(text)
        if ext == ".rtf" or text.startswith("{\\rtf"):
            return read_rtf(text)
        if ext == ".json":
            return read_json(text)
        if ext == ".xml" and "<mxfile" in text[:2000]:
            from diagrams import drawio_to_text
            t = drawio_to_text(data)
            if t:
                return ReadResult(t, "diagram", "draw.io")
        return ReadResult(_tidy(text) if ext not in (".cfg", ".conf", ".config", ".log")
                          else text.strip(), "text", "text")
    except zipfile.BadZipFile:
        return ReadResult(error=f"{name} is not a valid {ext} file (damaged or mislabelled)")
    except (KeyboardInterrupt, SystemExit):
        raise
    except BaseException as e:
        return ReadResult(error=f"could not read {name}: {type(e).__name__}: {e}")


def _read_zip(data, depth):
    z = zipfile.ZipFile(io.BytesIO(data))
    r = ReadResult(kind="archive", method="zip")
    read = 0
    for info in z.infolist()[:200]:
        if info.is_dir() or info.file_size > 50 * 1024 * 1024:
            continue
        if _ext(info.filename) not in ALL_EXTS:
            continue
        sub = read_file(info.filename, z.read(info), depth + 1)
        if sub.ok:
            read += 1
            r.text += f"\n\n## File: {info.filename}\n{sub.text}"
            r.tables += sub.tables
    r.text = r.text.strip()
    r.pages = read
    if not read:
        r.error = "no readable files inside the archive"
    return r


def capabilities():
    """What this machine can read right now — for doctor.py and the UI."""
    have = {}
    for mod, label in (("pymupdf", "PyMuPDF (best PDF reader)"), ("pypdf", "pypdf"),
                       ("pdfminer", "pdfminer")):
        try:
            __import__(mod)
            have[label] = True
        except BaseException:
            have[label] = False
    have["OCR (" + (ocr_available() or "none") + ")"] = bool(ocr_available())
    return have
