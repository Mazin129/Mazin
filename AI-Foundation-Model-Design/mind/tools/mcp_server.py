"""
tools.mcp_server — expose Vio's tools over MCP (roadmap T3, server side).

Model Context Protocol (stdio transport) lets real editors and agent hosts
(Claude Desktop, Cursor, Zed, …) use Vio as a tool provider:

    python tools/mcp_server.py

Implements the JSON-RPC methods a stdio MCP session needs: initialize,
tools/list, tools/call — no third-party dependency. Tools exposed are Vio's
own, through the same governed paths the chat uses (research stays gated by
VIO_ALLOW_NET; nothing here can write or execute).
"""
from __future__ import annotations

import json
import sys

PROTOCOL_VERSION = "2024-11-05"


def _tool(name, desc, props):
    return {"name": name, "description": desc,
            "inputSchema": {"type": "object", "properties": props,
                            "required": list(props.keys())}}


def tools():
    return [
        _tool("vio_ask", "Ask Vio a question — full pipeline: routing, tools, "
              "verification, provenance.", {"message": {"type": "string"}}),
        _tool("vio_subnet", "Exact IPv4 subnetting (usable hosts, masks, "
              "least-waste carving).", {"question": {"type": "string"}}),
        _tool("vio_research", "Web research (requires VIO_ALLOW_NET=1 on the "
              "Vio host); returns a grounded answer with sources.",
              {"topic": {"type": "string"}}),
        _tool("vio_config_audit", "Audit the loaded device configuration for "
              "shadowed rules, any/any accepts, hardening gaps.",
              {"nothing": {"type": "string", "description": "unused"}}),
    ]


def call(name, args):
    """Run one tool through Vio's normal path. Returns (content_text, is_error)."""
    args = args or {}
    try:
        if name == "vio_subnet":
            from reasoner import try_subnet
            r = try_subnet(str(args.get("question", "")))
            return (r or "not a subnetting question"), False
        if name == "vio_ask":
            import os, tempfile
            if not os.environ.get("VIO_DATA_DIR"):
                os.environ["VIO_DATA_DIR"] = tempfile.mkdtemp(prefix="vio_mcp_")
            from reasoner import Mind
            global _MIND
            try:
                mind = _MIND
            except NameError:
                mind = _MIND = Mind()
            r = mind.ask(str(args.get("message", "")))
            return r.get("answer", ""), not r.get("verified", False)
        if name == "vio_research":
            import os, tempfile, websearch
            if not os.environ.get("VIO_DATA_DIR"):
                os.environ["VIO_DATA_DIR"] = tempfile.mkdtemp(prefix="vio_mcp_")
            from reasoner import Mind
            global _MIND2
            try:
                mind = _MIND2
            except NameError:
                mind = _MIND2 = Mind()
            r = mind.research(str(args.get("topic", "")))
            return r.get("answer", ""), not r.get("ok")
        if name == "vio_config_audit":
            import os, tempfile
            if not os.environ.get("VIO_DATA_DIR"):
                os.environ["VIO_DATA_DIR"] = tempfile.mkdtemp(prefix="vio_mcp_")
            from reasoner import Mind
            global _MIND3
            try:
                mind = _MIND3
            except NameError:
                mind = _MIND3 = Mind()
            r = mind.audit_config()
            return r.get("answer", ""), False
    except Exception as e:
        return f"{type(e).__name__}: {e}", True
    return f"unknown tool: {name}", True


def main():
    """stdio JSON-RPC loop (line-delimited MCP messages)."""
    global _MIND
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except Exception:
            continue
        method = req.get("method", "")
        rid = req.get("id")
        if method == "initialize":
            result = {"protocolVersion": PROTOCOL_VERSION,
                      "capabilities": {"tools": {}},
                      "serverInfo": {"name": "vio", "version": "1.0"}}
        elif method == "tools/list":
            result = {"tools": tools()}
        elif method == "tools/call":
            p = req.get("params", {})
            text, is_err = call(p.get("name", ""), p.get("arguments"))
            result = {"content": [{"type": "text", "text": text}],
                      "isError": is_err}
        elif method in ("notifications/initialized",):
            continue
        else:
            if rid is None:
                continue
            result = None
        if rid is not None:
            resp = {"jsonrpc": "2.0", "id": rid,
                    "result" if result is not None else "error":
                        result if result is not None else
                        {"code": -32601, "message": f"unknown method {method}"}}
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
