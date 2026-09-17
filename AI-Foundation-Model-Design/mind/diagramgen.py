"""
diagramgen — generate a diagram by having Vio's LLM follow the vendored diagram-design
skill (Cathryn Lavery, MIT — see vendor/diagram-design/). It picks a visual type from
the request, loads that type's reference plus the style guide and output spec, and asks
the local LLM to emit ONE self-contained HTML document (inline SVG + CSS, no external
deps). Read-only. Output quality tracks the model — small local models are rough; a
bigger/hosted model produces editorial-quality diagrams from the same plumbing.
"""
from __future__ import annotations

import os
import re
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.join(HERE, "vendor", "diagram-design")
REF = os.path.join(SKILL_DIR, "references")

# request pattern → type slug (references/type-<slug>.md). First match wins; ordered so
# the more specific/network-security-relevant types are tried before generic ones.
TYPE_MAP = [
    (r"\b(sequence|handshake|oauth|request[/ ]response|round[- ]?trip|actors? exchang)\b", "sequence"),
    (r"\b(state ?machine|\bfsm\b|states? and transitions?|transitions?)\b", "state"),
    (r"\b(swimlane|cross[- ]functional|handoffs?)\b", "swimlane"),
    (r"\b(data ?flow|pipeline stages?)\b", "data-flow"),
    (r"\b(deployment|where .*runs?|zones?|hosts?|replicas?|ports? and)\b", "deployment"),
    (r"\b(dependenc\w+|what depends on|fan[- ]in|import graph)\b", "dependency"),
    (r"\b(\ber\b|entity[- ]relationship|data model|erd)\b", "er"),
    (r"\b(db schema|database schema|sql tables?|columns?)\b", "db-schema"),
    (r"\b(uml|class diagram)\b", "uml-class"),
    (r"\b(layers?|osi|stack|tiers?)\b", "layers"),
    (r"\b(org chart|reporting|escalation|team structure)\b", "org-chart"),
    (r"\b(fishbone|root ?cause|ishikawa)\b", "fishbone"),
    (r"\b(sankey|splits? and merges?)\b", "sankey"),
    (r"\b(wardley)\b", "wardley"),
    (r"\b(kanban|\bwip\b|board)\b", "kanban"),
    (r"\b(user journey|journey map|experience)\b", "journey"),
    (r"\b(timeline|roadmap|milestones?)\b", "timeline"),
    (r"\b(gantt|schedule)\b", "gantt"),
    (r"\b(quadrant|2x2|prioriti\w+|matrix)\b", "quadrant"),
    (r"\b(pyramid|funnel)\b", "pyramid"),
    (r"\b(venn|overlap between)\b", "venn"),
    (r"\b(tree|hierarchy)\b", "tree"),
    (r"\b(flow ?chart|decision|branch\w*|if / |logic)\b", "flowchart"),
    (r"\b(process|workflow|steps?)\b", "process"),
    (r"\b(bar chart|bars?)\b", "bar"),
    (r"\b(line chart|trend over time)\b", "line"),
    (r"\b(architecture|topology|network diagram|system design|components?|attack path)\b",
     "architecture"),
]
DEFAULT_TYPE = "architecture"

SYSTEM = (
    "You are a diagram generator that follows the diagram-design system. Produce ONE "
    "complete, self-contained HTML document: inline <svg> and inline <style> ONLY — no "
    "external scripts, stylesheets, fonts, images, or network requests, and no Mermaid. "
    "Obey the style tokens and the chosen type's layout grammar in the reference provided. "
    "Keep density about 4/10; reserve the accent color for the 1-2 focal nodes. Output ONLY "
    "the HTML document — start with <!doctype html> and nothing before or after it."
)


def available() -> bool:
    return os.path.isdir(REF) and os.path.isfile(os.path.join(SKILL_DIR, "SKILL.md"))


def pick_type(request: str) -> str:
    low = (request or "").lower()
    for pat, slug in TYPE_MAP:
        if re.search(pat, low):
            return slug
    return DEFAULT_TYPE


def _read(name: str, cap: int) -> str:
    try:
        with open(os.path.join(REF, name), encoding="utf-8") as f:
            return f.read()[:cap]
    except Exception:
        return ""


def build_prompt(request: str, slug: str) -> str:
    parts = []
    style = _read("style-guide.md", 6000)
    outspec = _read("output-spec.md", 4000)
    typedoc = _read(f"type-{slug}.md", 8000)
    if style:
        parts.append("# STYLE GUIDE (tokens & rules)\n" + style)
    if outspec:
        parts.append("# OUTPUT SPEC\n" + outspec)
    if typedoc:
        parts.append(f"# LAYOUT REFERENCE — {slug}\n" + typedoc)
    parts.append("# DIAGRAM REQUEST\n" + (request or "").strip())
    parts.append("Now output the complete self-contained HTML diagram for the request "
                 "above, following the style guide, output spec, and layout reference.")
    return "\n\n".join(parts)


def extract_html(text: str) -> str:
    if not text:
        return ""
    m = re.search(r"```(?:html)?\s*(.*?)```", text, re.S | re.I)
    if m:
        text = m.group(1)
    m = re.search(r"(<!doctype html.*?</html>|<html\b.*?</html>|<svg\b.*?</svg>)",
                  text, re.S | re.I)
    return (m.group(1) if m else text).strip()


def generate(request: str, llm, max_tokens=None) -> dict:
    if not available():
        return {"ok": False, "error": "diagram-design skill is not vendored"}
    if not (llm and getattr(llm, "available", False)):
        return {"ok": False, "error": "no local LLM"}
    slug = pick_type(request)
    prompt = build_prompt(request, slug)
    budget = int(max_tokens or os.environ.get("VIO_DIAGRAM_MAX_TOKENS", "6000"))
    out = llm.generate(prompt, system=SYSTEM, temperature=0.4, max_tokens=budget)
    html = extract_html(out)
    if not html or "<" not in html:
        return {"ok": False, "type": slug, "error": "the model did not return HTML"}
    return {"ok": True, "type": slug, "html": html}


_ID = re.compile(r"^\d+$")


def save(html: str, data_dir: str):
    d = os.path.join(data_dir, "diagrams")
    os.makedirs(d, exist_ok=True)
    did = "%d" % int(time.time() * 1000)
    with open(os.path.join(d, did + ".html"), "w", encoding="utf-8") as f:
        f.write(html)
    return did, os.path.join(d, did + ".html")


def load(did: str, data_dir: str):
    if not _ID.match(did or ""):                       # digits only — no path traversal
        return None
    path = os.path.join(data_dir, "diagrams", did + ".html")
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except Exception:
        return None
