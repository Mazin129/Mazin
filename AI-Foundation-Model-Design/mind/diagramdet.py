"""
diagramdet — DETERMINISTIC diagram renderer. Produces clean, self-contained SVG from a
compact spec, with NO dependence on the model's SVG skill, so a diagram is never blank.

Two ways in:
  * parse_spec(text) understands a tiny line syntax any model (or a person) can emit:
        zone: NAME              # start a group; following nodes belong to it
        NodeA                   # a node
        A -> B                  # an edge (optional ': label')
        A: B, C, D              # A with children B, C, D (tree/fan-out)
        1. step one             # numbered / 'then' steps -> a flow
  * from_description(request, llm) asks the LLM ONLY for that spec (easy), then renders it
    here deterministically. Without an LLM it best-effort-parses the description directly.

Layout is simple and collision-free (flow = vertical stack; graph = zone bands / grid),
so output is always readable. Palette follows the diagram-design defaults (neutral paper,
one coral accent).
"""
from __future__ import annotations

import html
import re

PAPER, INK, LINE, ACCENT, SUB = "#f5f5f5", "#2d3142", "#c9ccd3", "#eb6c36", "#8a8f99"
FONT = ("-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif")


# --------------------------------------------------------------------------- #
# spec parsing
# --------------------------------------------------------------------------- #
def parse_spec(text: str):
    """-> dict(kind, title, steps, nodes[list], edges[(a,b,label)], zones{zone:[nodes]})."""
    zones, order, edges, steps = {}, [], [], []
    cur_zone = None

    def _node(n):
        n = n.strip().strip('"').strip()
        if n and n not in order:
            order.append(n)
        if n and cur_zone is not None:
            zones.setdefault(cur_zone, [])
            if n not in zones[cur_zone]:
                zones[cur_zone].append(n)
        return n

    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        mz = re.match(r"(?i)^zone\s*[:\-]\s*(.+)$", line) or \
            re.match(r"(?i)^group\s*[:\-]\s*(.+)$", line)
        if mz:
            cur_zone = mz.group(1).strip().strip('"')
            zones.setdefault(cur_zone, [])
            continue
        ms = re.match(r"^\s*(?:\d+[.)]|[-*•])\s+(.+)$", line)
        if ms:
            steps.append(ms.group(1).strip())
            continue
        if "->" in line or "→" in line:
            seg = line.replace("→", "->")
            left, _, rest = seg.partition("->")
            lbl = ""
            if ":" in rest:
                rest, _, lbl = rest.partition(":")
            a, b = _node(left), _node(rest)
            if a and b:
                edges.append((a, b, lbl.strip()))
            continue
        mt = re.match(r"^([^:]{1,60}):\s*(.+)$", line)
        if mt and "," in mt.group(2):
            parent = _node(mt.group(1))
            for child in mt.group(2).split(","):
                c = _node(child)
                if parent and c:
                    edges.append((parent, c, ""))
            continue
        _node(line)

    # freeform fallback: a single unstructured line like "detect then contain then recover"
    # or "web, app, database" — split it so we still get a real diagram, never one box.
    if not edges and not steps and len(order) <= 1:
        blob = (text or "").strip()
        blob = re.sub(r"(?i)^\s*(draw|diagram|sketch|visuali[sz]e|chart)\s*[:\-]\s*", "", blob)
        seq = re.split(r"\s*(?:->|→|\bthen\b|\bto\b|;|\bthen\s+to\b)\s*", blob, flags=re.I)
        seq = [s.strip(" .") for s in seq if s.strip(" .")]
        if len(seq) >= 2:
            return {"kind": "flow", "steps": seq, "nodes": [], "edges": [], "zones": {}}
        parts = re.split(r"\s*(?:,|\band\b|/)\s*", blob, flags=re.I)
        parts = [p.strip(" .") for p in parts if len(p.strip(" .")) > 1]
        if len(parts) >= 2:
            order = parts

    kind = "flow" if steps and not edges and not zones else \
           ("graph" if (edges or zones) else "flow")
    return {"kind": kind, "steps": steps, "nodes": order, "edges": edges, "zones": zones}


# --------------------------------------------------------------------------- #
# SVG helpers
# --------------------------------------------------------------------------- #
def _esc(s):
    return html.escape(str(s), quote=True)


def _wrap(label, maxc=22):
    words, lines, cur = str(label).split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 <= maxc:
            cur = (cur + " " + w).strip()
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines[:3] or [str(label)]


def _box(x, y, w, h, label, accent=False):
    fill = "#fff"
    stroke = ACCENT if accent else LINE
    sw = 2.2 if accent else 1.4
    lines = _wrap(label)
    ly = y + h / 2 - (len(lines) - 1) * 9
    tspans = "".join(
        f'<tspan x="{x + w/2:.0f}" y="{ly + i*18:.0f}">{_esc(l)}</tspan>'
        for i, l in enumerate(lines))
    return (f'<rect x="{x:.0f}" y="{y:.0f}" width="{w:.0f}" height="{h:.0f}" rx="10" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>'
            f'<text font-family="{FONT}" font-size="13" font-weight="{600 if accent else 500}" '
            f'fill="{INK}" text-anchor="middle">{tspans}</text>')


def _arrow(x1, y1, x2, y2, label=""):
    mid = ""
    if label:
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2 - 4
        mid = (f'<text x="{mx:.0f}" y="{my:.0f}" font-family="{FONT}" font-size="11" '
               f'fill="{SUB}" text-anchor="middle">{_esc(label)}</text>')
    return (f'<line x1="{x1:.0f}" y1="{y1:.0f}" x2="{x2:.0f}" y2="{y2:.0f}" '
            f'stroke="{SUB}" stroke-width="1.6" marker-end="url(#a)"/>' + mid)


def _doc(title, w, h, body):
    return (
        f'<!doctype html><html><head><meta charset="utf-8">'
        f'<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>{_esc(title)}</title></head>'
        f'<body style="margin:0;background:{PAPER};font-family:{FONT}">'
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
        f'width="100%" style="max-width:{w}px;display:block;margin:24px auto">'
        f'<defs><marker id="a" markerWidth="10" markerHeight="10" refX="8" refY="3" '
        f'orient="auto"><path d="M0,0 L8,3 L0,6 z" fill="{SUB}"/></marker></defs>'
        f'<rect x="0" y="0" width="{w}" height="{h}" fill="{PAPER}"/>'
        f'<text x="28" y="38" font-family="{FONT}" font-size="20" font-weight="700" '
        f'fill="{INK}">{_esc(title)}</text>'
        f'{body}</svg></body></html>')


# --------------------------------------------------------------------------- #
# renderers
# --------------------------------------------------------------------------- #
def _render_flow(title, steps):
    bw, bh, gap, x0, y0 = 300, 56, 34, 60, 70
    parts = []
    for i, s in enumerate(steps):
        y = y0 + i * (bh + gap)
        parts.append(_box(x0, y, bw, bh, s, accent=(i == 0 or i == len(steps) - 1)))
        if i < len(steps) - 1:
            parts.append(_arrow(x0 + bw / 2, y + bh, x0 + bw / 2, y + bh + gap))
    h = y0 + len(steps) * (bh + gap) + 20
    return _doc(title, bw + 2 * x0, max(h, 200), "".join(parts))


def _render_graph(title, nodes, edges, zones):
    bw, bh, hgap, vgap, x0, y0 = 190, 54, 40, 46, 40, 64
    pos = {}
    parts_zone, parts_node = [], []
    # bands: each zone is a full-width row; ungrouped nodes go in a trailing band
    grouped = {n for ns in zones.values() for n in ns}
    bands = list(zones.items())
    loose = [n for n in nodes if n not in grouped]
    if loose:
        bands.append((None, loose))
    per_row = 4
    y = y0
    maxw = 0
    for zname, zn in bands:
        rows = [zn[i:i + per_row] for i in range(0, len(zn), per_row)] or [[]]
        band_h = len(rows) * (bh + vgap) + (28 if zname else 8)
        if zname:
            parts_zone.append(
                f'<rect x="20" y="{y:.0f}" width="__W__" height="{band_h - 12:.0f}" rx="14" '
                f'fill="none" stroke="{LINE}" stroke-width="1.4" stroke-dasharray="6 5"/>'
                f'<text x="34" y="{y + 20:.0f}" font-family="{FONT}" font-size="12" '
                f'font-weight="700" fill="{SUB}">{_esc(zname)}</text>')
        ry = y + (26 if zname else 4)
        for r, row in enumerate(rows):
            for c, n in enumerate(row):
                x = x0 + c * (bw + hgap)
                yy = ry + r * (bh + vgap)
                pos[n] = (x + bw / 2, yy + bh / 2, x, yy)
                parts_node.append(_box(x, yy, bw, bh, n))
                maxw = max(maxw, x + bw)
        y += band_h
    W = max(maxw + x0, 560)
    parts_zone = [p.replace("__W__", str(W - 40)) for p in parts_zone]
    # edges (drawn under nodes)
    parts_edge = []
    for a, b, lbl in edges:
        if a in pos and b in pos:
            ax, ay, _, _ = pos[a]
            bx, by, _, _ = pos[b]
            parts_edge.append(_arrow(ax, ay, bx, by, lbl))
    body = "".join(parts_zone) + "".join(parts_edge) + "".join(parts_node)
    return _doc(title, W, y + 24, body)


def render(spec: dict, title="Diagram"):
    """Render a parsed spec dict to a self-contained HTML/SVG document."""
    if spec.get("kind") == "flow" and spec.get("steps"):
        return _render_flow(title, spec["steps"])
    nodes = spec.get("nodes") or []
    if not nodes and spec.get("steps"):
        return _render_flow(title, spec["steps"])
    if not nodes:
        nodes = ["(no elements parsed)"]
    return _render_graph(title, nodes, spec.get("edges") or [], spec.get("zones") or {})


# --------------------------------------------------------------------------- #
# entry point
# --------------------------------------------------------------------------- #
SPEC_SYSTEM = (
    "Turn the request into a DIAGRAM SPEC — plain lines only, no prose, no SVG:\n"
    "  zone: NAME        (optional grouping; nodes after it belong to it)\n"
    "  NodeName          (a box)\n"
    "  A -> B            (an arrow; optional ': label')\n"
    "  A: B, C           (A connects to B and C)\n"
    "  1. step           (numbered steps become a flow)\n"
    "Keep labels short (1-4 words). 4-9 nodes is ideal. Output ONLY the spec lines.")


def _title_from(request, kind):
    t = re.sub(r"(?i)^\s*(draw|diagram|sketch|visuali[sz]e|chart)\s*[:\-]\s*", "", request or "")
    t = t.strip().rstrip(".?!")
    return (t[:60] or "Diagram").strip().capitalize()


def from_description(request, llm=None, max_tokens=700):
    """Preferred path: ask the LLM ONLY for a compact spec (easy for any model), then
    render the SVG deterministically here. No LLM → best-effort parse of the request."""
    spec_text = ""
    if llm is not None and getattr(llm, "available", False):
        try:
            spec_text = llm.generate("Request: " + (request or "").strip(),
                                     system=SPEC_SYSTEM, temperature=0.2,
                                     max_tokens=max_tokens) or ""
        except Exception:
            spec_text = ""
    spec = parse_spec(spec_text) if spec_text.strip() else {"kind": "", "nodes": [],
                                                            "edges": [], "zones": {}, "steps": []}
    if not (spec.get("nodes") or spec.get("steps")):
        spec = parse_spec(request or "")               # fall back to the raw request
    title = _title_from(request, spec.get("kind"))
    html_doc = render(spec, title=title)
    return {"ok": True, "kind": spec.get("kind") or "graph", "html": html_doc,
            "nodes": len(spec.get("nodes") or []), "used_llm": bool(spec_text.strip())}
