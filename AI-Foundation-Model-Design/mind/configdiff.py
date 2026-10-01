"""
configdiff — what changed between two versions of a configuration, and whether the
change made the device safer or riskier.

A text diff of two FortiGate exports is mostly noise: reordered blocks, UUIDs,
timestamps. This compares PARSED objects instead, keyed by (kind, name), and reports
changes field by field. Then it runs the full configuration review on both versions
and reports the difference in FINDINGS — so a change is judged by its effect
("this edit opened management on wan1"), not just by which lines moved.

Deterministic: no model, same answer every time.
"""
from __future__ import annotations

import configaudit

# fields that change on every save and carry no meaning for a review
_NOISE = {"uuid", "uuid-idx", "_scope", "comments-updated"}


def _key(o):
    return ((o.kind or "").strip().lower(), str(o.name))


def _label(kind, name):
    return f"{kind} {name}".strip() if name else kind


def _fields(o):
    return {k: v for k, v in o.fields.items() if k not in _NOISE}


def diff(old_objects, new_objects):
    """Object- and field-level differences. Returns a dict with lists:
        added    [(kind, name)]
        removed  [(kind, name)]
        changed  [(kind, name, [(field, old_value, new_value)])]
    A value of None means the field was absent on that side."""
    old = {_key(o): o for o in old_objects}
    new = {_key(o): o for o in new_objects}
    added = sorted(k for k in new if k not in old)
    removed = sorted(k for k in old if k not in new)
    changed = []
    for k in sorted(set(old) & set(new)):
        a, b = _fields(old[k]), _fields(new[k])
        deltas = [(f, a.get(f), b.get(f)) for f in sorted(set(a) | set(b))
                  if a.get(f) != b.get(f)]
        if deltas:
            changed.append((k[0], k[1], deltas))
    return {"added": added, "removed": removed, "changed": changed}


def _finding_key(f):
    return (f.rule, f.title)


def risk_delta(old_objects, new_objects):
    """Findings the change INTRODUCED and RESOLVED, worst first."""
    before = {_finding_key(f): f for f in configaudit.audit(old_objects)}
    after = {_finding_key(f): f for f in configaudit.audit(new_objects)}
    order = lambda f: (configaudit._ORDER.get(f.severity, 9), f.rule)   # noqa: E731
    introduced = sorted((after[k] for k in after if k not in before), key=order)
    resolved = sorted((before[k] for k in before if k not in after), key=order)
    return introduced, resolved


def report(old_objects, new_objects, old_name="previous", new_name="current", limit=60):
    """A change review a human can act on: verdict first, then risk, then the edits."""
    d = diff(old_objects, new_objects)
    introduced, resolved = risk_delta(old_objects, new_objects)
    n_changes = len(d["added"]) + len(d["removed"]) + len(d["changed"])
    serious = [f for f in introduced if f.severity in (configaudit.HIGH, configaudit.MEDIUM)]

    if not n_changes:
        verdict = "**No differences.** The two configurations define the same objects."
    elif serious:
        verdict = (f"**⚠️ This change introduced {len(serious)} serious risk(s)** "
                   f"across {n_changes} change(s).")
    elif introduced:
        verdict = (f"**{n_changes} change(s); no serious new risk** — "
                   f"{len(introduced)} minor observation(s).")
    else:
        verdict = f"**{n_changes} change(s); no new risk introduced.**"
    if resolved:
        verdict += f" It also resolved {len(resolved)} earlier finding(s)."

    lines = [f"**Configuration diff** — {old_name} → {new_name}", "", verdict]

    if introduced:
        lines += ["", "**Risks introduced by this change:**"]
        lines += [f.line() for f in configaudit.group(introduced)[:20]]
    if resolved:
        lines += ["", "**Findings resolved by this change:**"]
        lines += [f"✔️ {f.title}" for f in resolved[:20]]

    shown = 0
    if d["added"]:
        lines += ["", f"**Added ({len(d['added'])}):**"]
        for kind, name in d["added"][:limit]:
            lines.append(f"  + {_label(kind, name)}")
            shown += 1
    if d["removed"]:
        lines += ["", f"**Removed ({len(d['removed'])}):**"]
        for kind, name in d["removed"][:limit]:
            lines.append(f"  − {_label(kind, name)}")
            shown += 1
    if d["changed"]:
        lines += ["", f"**Changed ({len(d['changed'])}):**"]
        for kind, name, deltas in d["changed"][:limit]:
            lines.append(f"  ~ {_label(kind, name)}")
            for field, a, b in deltas[:8]:
                if a is None:
                    lines.append(f"      + set {field} {b}")
                elif b is None:
                    lines.append(f"      − set {field} {a}")
                else:
                    lines.append(f"      {field}: {a}  →  {b}")
            if len(deltas) > 8:
                lines.append(f"      … {len(deltas) - 8} more field(s)")
    if n_changes > limit:
        lines.append(f"\n… output limited; {n_changes} change(s) in total.")

    lines += ["", "---", "*Compared parsed objects, not text, so re-ordering and "
              "per-save fields (UUIDs) are ignored. Risks come from the same review as "
              "`audit my config`, run on both versions. No model was involved.*"]
    return "\n".join(lines)
