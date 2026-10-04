"""
toolcall — native tool-calling for the reasoning path (roadmap T2).

The deterministic tools stay the fast path (deterministic-first routing); this module
upgrades the SYSTEM-2 LLM path: instead of only reasoning over retrieved text, the
model can now CALL Vio's tools by name — Ollama native function calling — and ground
its answer on the real results.

Tools exposed (read-only, deterministic or network-gated):
    subnet            — exact IPv4 subnetting
    config_summary    — what the loaded device configuration contains (brain survey)
    table_sql         — DuckDB SELECT over the uploaded tables
    device_facts      — serial/model/firmware Vio knows
    web_search        — search the public web (only when VIO_ALLOW_NET)

Every call is bounded (max 3 rounds), every result enters the conversation as a
tool role message, and the final answer is produced grounded on the gathered facts.
Falls back silently ({"text": None, "steps": []}) when the model/server lacks
tool support — the plain reasoning path continues unchanged.
"""
from __future__ import annotations

import json

MAX_ROUNDS = 3

TOOLS_SCHEMA = [
    {"type": "function", "function": {
        "name": "subnet",
        "description": "Exact IPv4 subnetting: usable hosts, mask/CIDR conversions, "
                       "least-waste subnet for a host requirement, derived subnets.",
        "parameters": {"type": "object", "properties": {
            "question": {"type": "string", "description": "the subnetting question"}},
            "required": ["question"]}}},
    {"type": "function", "function": {
        "name": "config_summary",
        "description": "What the user's loaded device configuration contains "
                       "(object kinds and counts). Call before config questions.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "table_sql",
        "description": "Run a read-only SQL SELECT over the user's uploaded tables "
                       "(registered as t). Exact, computed.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "a SELECT statement"}},
            "required": ["query"]}}},
    {"type": "function", "function": {
        "name": "device_facts",
        "description": "Serial/model/firmware of the user's known devices, if any.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "web_search",
        "description": "Search the public web (needs the user's web opt-in). "
                       "Returns result titles and URLs.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string"}}, "required": ["query"]}}},
]

_SYSTEM = ("You are Vio, a local networking & security assistant with TOOLS. Use a tool "
           "when it can produce an exact or live fact (subnet math, the user's config, "
           "their tables, their devices, or a web lookup); then answer the user grounded "
           "on the tool results. If no tool helps, answer directly. Never invent tool "
           "output you did not receive.")


def _exec(mind, name, args):
    """Execute one tool call — read-only tools only, everything bounded."""
    try:
        if name == "subnet":
            from reasoner import try_subnet
            return try_subnet(str(args.get("question", ""))) or "no subnet answer"
        if name == "config_summary":
            import brain
            ev = brain.survey(mind)
            if not ev.config_kinds:
                return "no device configuration is loaded"
            top = sorted(ev.config_kinds.items(), key=lambda kv: -kv[1])[:8]
            return (f"{sum(ev.config_kinds.values())} objects: "
                    + ", ".join(f"{n} {k}" for k, n in top))
        if name == "table_sql":
            q = str(args.get("query", ""))
            for tbl in reversed(getattr(mind, "tables", [])):
                r = tbl.sql(q)
                if r is not None:
                    return f"[{tbl.name}] {r}"
            return "no loaded table accepted that query"
        if name == "device_facts":
            import devicefacts
            inv = devicefacts.inventory(mind)
            return json.dumps(inv) if inv else "no devices known"
        if name == "web_search":
            import websearch
            if not websearch.net_enabled():
                return "web research is OFF (user opt-in)"
            import re as _re
            q = _re.sub(r"\s+", " ", str(args.get("query", "")))[:200]
            res = websearch.search(q, k=4)
            return json.dumps([{"title": r["title"][:80], "url": r["url"]} for r in res])
    except Exception as e:
        return f"tool error: {type(e).__name__}: {e}"[:200]
    return f"unknown tool: {name}"


def run(mind, question, max_rounds=MAX_ROUNDS):
    """One bounded tool-calling conversation. Returns
    {'text': final answer | None, 'steps': [tool call descriptions]} — text None
    means the model/server has no tool support and the caller should fall back."""
    llm = mind.llm
    messages = [{"role": "system", "content": _SYSTEM},
                {"role": "user", "content": question}]
    steps = []
    for _ in range(max_rounds):
        out = llm.chat_tools(messages, TOOLS_SCHEMA)
        calls = out.get("tool_calls") or []
        if not calls:
            return {"text": out.get("text"), "steps": steps}
        messages.append({"role": "assistant", "content": out.get("text") or "",
                         "tool_calls": out.get("tool_calls")})
        for tc in calls:
            name = tc.get("name", "")
            result = _exec(mind, name, tc.get("arguments") or {})
            steps.append(f"{name}({json.dumps(tc.get('arguments') or {})[:80]}) "
                         f"→ {str(result)[:120]}")
            messages.append({"role": "tool", "content": str(result)[:4000]})
    # rounds exhausted: one final grounded answer from what the tools returned
    out = llm.chat_tools(messages + [{"role": "system", "content":
                          "Answer the user's question now, grounded on the tool results above."}],
                         [])
    return {"text": out.get("text"), "steps": steps}
