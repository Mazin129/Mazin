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
    """Parse FortiGate stanza config into a flat list of ConfigObjects (nested configs
    keep the innermost kind). Returns [] when the text isn't stanza config."""
    objs, kinds, cur = [], [], None
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        m = _CONFIG.match(line)
        if m:
            kinds.append(m.group(1).strip())
            continue
        m = _EDIT.match(line)
        if m and kinds:
            if cur is not None:
                objs.append(cur)
            cur = ConfigObject(kind=kinds[-1], name=m.group(1).strip().strip('"'), raw=raw)
            continue
        m = _SET.match(line)
        if m and cur is None and kinds:
            # A SETTINGS block — `config system global`, `config log setting`,
            # `config system password-policy` — has `set` lines and no `edit`. Those
            # lines used to be dropped, which made every device-wide security setting
            # (admin TLS versions, strong-crypto, password policy) invisible. Represent
            # the block as one object with an empty name.
            cur = ConfigObject(kind=kinds[-1], name="", raw=raw)
        if m and cur is not None:
            cur.fields[m.group(1).lower()] = m.group(2).strip()
            cur.raw += "\n" + raw
            continue
        if _NEXT.match(line):
            if cur is not None:
                objs.append(cur)
                cur = None
            continue
        if _END.match(line):
            if cur is not None:
                objs.append(cur)
                cur = None
            if kinds:
                kinds.pop()
            continue
    if cur is not None:
        objs.append(cur)
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
