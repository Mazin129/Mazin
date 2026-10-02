"""
configparse — turn raw network/firewall config text into STRUCTURED objects before
analysis, so queries run against fields rather than fuzzy keyword matches.

Handles FortiGate-style stanza syntax (config … / edit … / set … / next / end), which
covers the common case and nests correctly. Returns ConfigObject(kind, name, fields, raw).
Pure and deterministic — no LLM, no I/O — so counts and filters it produces are exact
and can be marked verified.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field as _field

_CONFIG = re.compile(r"^\s*config\s+(.+?)\s*$", re.I)
_EDIT = re.compile(r"^\s*edit\s+(.+?)\s*$", re.I)
_SET = re.compile(r"^\s*set\s+(\S+)\s+(.+?)\s*$", re.I)
_NEXT = re.compile(r"^\s*next\s*$", re.I)
_END = re.compile(r"^\s*end\s*$", re.I)


@dataclass
class ConfigObject:
    kind: str                       # e.g. "firewall policy", "firewall address"
    name: str                       # the edit key (a numeric id or a "name")
    fields: dict = _field(default_factory=dict)
    raw: str = ""
    # For a row of a nested sub-table (`config rules` inside a profile): the owning
    # object as "kind name". Empty for top-level objects. Nested rows are details of
    # their parent, not objects a user asks for by bare name.
    parent: str = ""

    def get(self, key, default=None):
        return self.fields.get(key.lower(), default)

    def __repr__(self):
        return f"<{self.kind} {self.name} {list(self.fields)}>"


def vendor(text: str):
    """'fortigate', 'panos', 'asa', or None."""
    if re.search(r"(?im)^\s*config\s+\S", text or ""):
        return "fortigate"
    import vendorparse
    return vendorparse.detect(text)


def looks_like_config(text: str) -> bool:
    return vendor(text) is not None


def parse(text: str):
    """Parse any supported vendor's configuration into ConfigObjects. Palo Alto and
    Cisco ASA are translated into the same object shapes as FortiGate (vendorparse),
    so every analysis works on all three."""
    v = vendor(text)
    if v in ("panos", "asa"):
        import vendorparse
        return vendorparse.parse(text, v)
    return _parse_fortigate(text)


def _parse_fortigate(text: str):
    """Parse FortiGate stanza config into a flat list of ConfigObjects.

    Nested blocks are tracked on a stack. A sub-table inside an object (`config rules`
    inside a profile, `config realservers` inside a VIP) produces rows whose kind is
    qualified by the owner ("waf profile > url-access"), whose name is prefixed by
    the owner's name, and which record their parent — so they never masquerade as
    top-level objects. When a sub-table ends, the owning object resumes, so `set`
    lines after it land on the right object instead of creating a nameless one."""
    objs = []
    stack = []            # frames: {"kind", "owner", "resume", "settings"}
    cur = None
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        m = _CONFIG.match(line)
        if m:
            sub = m.group(1).strip()
            owner = cur if cur is not None else (stack[-1]["settings"] if stack else None)
            kind = f"{owner.kind} > {sub}" if owner is not None else sub
            stack.append({"kind": kind, "owner": owner, "resume": cur, "settings": None})
            cur = None
            continue
        if not stack:
            continue
        frame = stack[-1]
        m = _EDIT.match(line)
        if m:
            key = m.group(1).strip().strip('"')
            owner = frame["owner"]
            cur = ConfigObject(
                kind=frame["kind"],
                name=f"{owner.name}/{key}" if owner is not None and owner.name else key,
                raw=raw,
                parent=f"{owner.kind} {owner.name}".strip() if owner is not None else "")
            objs.append(cur)
            continue
        m = _SET.match(line)
        if m:
            if cur is None:
                # A SETTINGS block (`config system global`, or a settings sub-block such
                # as `config ipv6` inside an interface) has `set` lines and no `edit`:
                # one object per block, created on the first `set` and reused after.
                if frame["settings"] is None:
                    owner = frame["owner"]
                    frame["settings"] = ConfigObject(
                        kind=frame["kind"], name=owner.name if owner is not None else "",
                        raw=raw,
                        parent=f"{owner.kind} {owner.name}".strip() if owner is not None else "")
                    objs.append(frame["settings"])
                target = frame["settings"]
            else:
                target = cur
            target.fields[m.group(1).lower()] = m.group(2).strip()
            target.raw += "\n" + raw
            continue
        if _NEXT.match(line):
            cur = None
            continue
        if _END.match(line):
            done = stack.pop()
            cur = done["resume"]          # the owning object continues after its sub-table
            continue
    return objs


def parse_many(docs):
    """Parse a list of passages/documents into one combined object list.

    FortiGate stanzas are self-contained, so each passage parses alone. A Palo Alto
    rule or a Cisco ACL binding is spread over lines that land in different passages,
    so those vendors' passages are re-joined (in library order) and parsed once."""
    combined, joined = [], {"panos": [], "asa": []}
    docs = list(docs or ())
    tags = [vendor(d) for d in docs]
    present = {v for v in tags if v in joined}
    for d, v in zip(docs, tags):
        if v == "fortigate":
            combined.extend(_parse_fortigate(d))
        elif v in joined:
            joined[v].append(d)
        elif v is None and present:
            # a small block of a vendor config that is already loaded (e.g. one ASA
            # object), too short to identify on its own — see vendorparse.belongs_to
            import vendorparse
            for pv in present:
                if vendorparse.belongs_to(d, pv):
                    joined[pv].append(d)
                    break
    if joined["panos"] or joined["asa"]:
        import vendorparse
        for v, parts in joined.items():
            if parts:
                combined.extend(vendorparse.parse("\n".join(parts), v))
    return combined


def of_kind(objs, kind_sub):
    return [o for o in objs if kind_sub.lower() in o.kind.lower()]


def where(objs, **field_contains):
    """Filter objects whose fields contain the given substrings (case-insensitive)."""
    res = []
    for o in objs:
        ok = True
        for k, v in field_contains.items():
            fv = (o.fields.get(k.lower()) or "").lower()
            if v.lower() not in fv:
                ok = False
                break
        if ok:
            res.append(o)
    return res


def summary(o: ConfigObject) -> str:
    """Compact, structured one-line view for an LLM prompt (no wall of text)."""
    keys = ("name", "srcintf", "dstintf", "srcaddr", "dstaddr", "service", "action",
            "status", "nat", "schedule", "subnet", "type", "comment", "comments")
    bits = [f"{k}={o.fields[k]}" for k in keys if k in o.fields]
    return f"{o.kind} {o.name}" + (" | " + "; ".join(bits) if bits else "")
