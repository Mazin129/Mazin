"""
test_readers — every file type is read, and what it teaches answers questions.

The Office files are built here with the standard library (a .docx/.xlsx/.pptx is a zip
of XML), so the suite runs anywhere with no extra packages.

Run:  python test_readers.py
"""
from __future__ import annotations

import io
import os
import sys
import tempfile
import zipfile

PASS, FAIL = [], []


def check(name, cond):
    (PASS if cond else FAIL).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}")


W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'


def _zip(files):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for n, t in files.items():
            z.writestr(n, t)
    return buf.getvalue()


def make_docx():
    def p(t, style=None):
        ppr = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
        return f"<w:p>{ppr}<w:r><w:t>{t}</w:t></w:r></w:p>"

    def row(*cells):
        return "<w:tr>" + "".join(f"<w:tc>{p(c)}</w:tc>" for c in cells) + "</w:tr>"
    body = (p("Flynas Landing Zone LLD", "Title") + p("Firewall Design", "Heading1")
            + p("A single Azure Firewall Premium is deployed in the hub at 10.10.1.4.")
            + "<w:tbl>" + row("Subnet", "CIDR", "Purpose")
            + row("AzureFirewallSubnet", "10.10.1.0/26", "Azure Firewall")
            + row("GatewaySubnet", "10.10.2.0/27", "VPN gateway")
            + row("snet-mgmt", "10.10.5.0/24", "Bastion hosts") + "</w:tbl>")
    return _zip({"word/document.xml": f"<w:document {W}><w:body>{body}</w:body></w:document>"})


def make_xlsx():
    S = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
    R = 'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
    strings = ["Rule", "Source", "Port", "allow-web", "10.20.1.0/24", "allow-dns",
               "10.0.0.0/8", "deny-all", "any"]
    sst = f"<sst {S}>" + "".join(f"<si><t>{x}</t></si>" for x in strings) + "</sst>"

    def c(ref, s=None, n=None):
        return (f'<c r="{ref}" t="s"><v>{strings.index(s)}</v></c>' if s is not None
                else f'<c r="{ref}"><v>{n}</v></c>')
    rows = [[c("A1", "Rule"), c("B1", "Source"), c("C1", "Port")],
            [c("A2", "allow-web"), c("B2", "10.20.1.0/24"), c("C2", n=443)],
            [c("A3", "allow-dns"), c("B3", "10.0.0.0/8"), c("C3", n=53)],
            [c("A4", "deny-all"), c("B4", "any"), c("C4", n=0)]]
    sheet = (f"<worksheet {S}><sheetData>" + "".join(
        f'<row r="{i + 1}">' + "".join(r) + "</row>" for i, r in enumerate(rows))
        + "</sheetData></worksheet>")
    wb = (f'<workbook {S} {R}><sheets><sheet name="Firewall Rules" sheetId="1" '
          f'r:id="rId1"/></sheets></workbook>')
    rels = ('<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/'
            'relationships"><Relationship Id="rId1" Target="worksheets/sheet1.xml" '
            'Type="x"/></Relationships>')
    return _zip({"xl/sharedStrings.xml": sst, "xl/worksheets/sheet1.xml": sheet,
                 "xl/workbook.xml": wb, "xl/_rels/workbook.xml.rels": rels})


def make_pptx():
    A = 'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"'

    def slide(*paras):
        return (f"<p:sld {A} xmlns:p=\"x\">" + "".join(
            f"<a:p><a:r><a:t>{t}</a:t></a:r></a:p>" for t in paras) + "</p:sld>")
    return _zip({"ppt/slides/slide1.xml": slide("Single vs Multiple Firewalls",
                                                "Single firewall: lower cost"),
                 "ppt/slides/slide2.xml": slide("Recommendation",
                                                "One Azure Firewall Premium in the hub")})


EML = (b"From: net@flynas.com\nTo: mazin@flynas.com\nSubject: Firewall change window\n"
       b"Content-Type: text/plain\n\nThe firewall change window is Thursday 01:00-03:00 "
       b"AST. All production changes need CAB approval.\n")


def main():
    os.environ["VIO_DATA_DIR"] = tempfile.mkdtemp(prefix="vio_readers_")
    for k in ("VIO_SEMANTIC_ASYNC", "VIO_TRAIN_ASYNC", "VIO_STUDY_ASYNC"):
        os.environ[k] = "0"
    import readers

    print("=" * 72)
    print("  READERS — every file type, and what it teaches")
    print("=" * 72)

    r = readers.read_file("lld.docx", make_docx())
    check("Word: headings kept", "# Firewall Design" in r.text)
    check("Word: table rows keep their column names",
          "Subnet: GatewaySubnet; CIDR: 10.10.2.0/27" in r.text)
    check("Word: the table is also handed to the data engine", len(r.tables) == 1)

    r = readers.read_file("plan.xlsx", make_xlsx())
    check("Excel: sheet read by name", "## Sheet: Firewall Rules" in r.text)
    check("Excel: shared strings and numbers decoded",
          "Rule: allow-dns; Source: 10.0.0.0/8; Port: 53" in r.text)

    r = readers.read_file("deck.pptx", make_pptx())
    check("PowerPoint: slides in order with titles",
          r.text.index("Slide 1") < r.text.index("Slide 2") and r.pages == 2)

    r = readers.read_file("mail.eml", EML)
    check("E-mail: headers and body", "Subject: Firewall change window" in r.text
          and "Thursday" in r.text)

    r = readers.read_file("page.html", b"<html><script>x=1</script><h1>Title</h1>"
                                       b"<p>Body text here.</p></html>")
    check("HTML: text without scripts", "Body text" in r.text and "x=1" not in r.text)

    r = readers.read_file("data.json", b'{"hub": {"cidr": "10.10.0.0/16"}}')
    check("JSON: flattened to path: value", "hub.cidr: 10.10.0.0/16" in r.text)

    r = readers.read_file("bundle.zip", _zip({"a/lld.docx": make_docx(),
                                              "b/mail.eml": EML.decode()}))
    check("Zip: every readable member", "GatewaySubnet" in r.text and "Thursday" in r.text)

    check("old .doc: says to save as .docx",
          ".docx" in readers.read_file("old.doc", b"\xd0\xcf\x11\xe0").error)
    check("a damaged .docx is reported, not crashed on",
          "not a valid" in readers.read_file("bad.docx", b"not a zip").error)
    check("UTF-16 text decodes", "hello" in readers.read_file(
        "n.txt", "hello world".encode("utf-16")).text)
    check("an unreadable PDF says exactly what to install or do",
          bool(readers.read_file("x.pdf", b"%PDF-1.4\n%%EOF").error))

    print("\n-- what a file teaches is used to answer --")
    import reasoner
    import test_llm
    m = reasoner.Mind()
    m.llm = test_llm.Fake(["qwen3.5:4b"], reply=(
        "The firewall change window is Thursday from 01:00 to 03:00 AST, and every "
        "production change needs CAB approval first."))
    m.llm.context = m._llm_context
    msg = m.learn_file("lld.docx", make_docx())
    check("the reply says how it was read", "Read as word" in msg)
    check("…and that its table is queryable", "table(s) as data" in msg)
    m.learn_file("plan.xlsx", make_xlsx())
    m.learn_file("mail.eml", EML)
    r = m.ask("what is the CIDR of GatewaySubnet")
    check("a cell is looked up exactly", "10.10.2.0/27" in r["answer"]
          and r["how"].startswith("data analysis"))
    r = m.ask("show rule allow-dns")
    check("a row is shown whole", "Port: 53" in r["answer"])
    r = m.ask("when is the firewall change window")
    check("a question about THEIR system is answered from their own e-mail",
          "Thursday" in r["answer"] and not r["how"].startswith("no-source"))
    r = m.ask("show static routes on SA-OCC firewall")
    check("…but a device question their documents don't cover still needs the config",
          r["how"].startswith("no-source"))

    print("=" * 72)
    print(f"  {len(PASS)} passed, {len(FAIL)} failed")
    print("\nALL PASS" if not FAIL else "\nFAILURES")
    return 1 if FAIL else 0


if __name__ == "__main__":
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    sys.exit(main())
