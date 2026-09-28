"""
gitlearn  —  let Vio learn from a public GitHub repository.

Given "owner/repo" (or a github.com URL, or "gh repo clone owner/repo"), this shallow-
clones the repo and returns its readable DOCUMENTATION as plain text — Markdown, plain
text, reStructuredText, AsciiDoc, and PDFs. Vio then learns those the same way it learns
an uploaded file.

SAFETY — this reads, it never runs:
  • It only ever READS text/doc files. It does NOT execute any code, scripts, hooks, or
    build steps from the repo. "Learn from a repo" must never mean "run a stranger's code."
  • The clone URL is built from a strictly-validated owner/repo (GitHub only), passed to
    git as argv (no shell), so a repo name can't inject a command.
  • Size is capped (files, per-file bytes, total) so a huge repo can't exhaust memory/disk.
  • The clone goes to a temp dir that is deleted afterwards.

Requires `git` on PATH (used via subprocess). Network access happens ONLY when you ask
Vio to learn from a repo — the rest of Vio stays fully local.
"""

import os
import re
import shutil
import subprocess
import tempfile

# owner/repo with optional github.com URL or "gh repo clone" / "git clone" prefixes
_SPEC = re.compile(
    r"^\s*(?:(?:gh|git)\s+(?:repo\s+)?(?:clone|learn)\s+)?"
    r"(?:https?://github\.com/|git@github\.com:)?"
    r"([A-Za-z0-9](?:[A-Za-z0-9_.-]*[A-Za-z0-9])?)/"
    r"([A-Za-z0-9](?:[A-Za-z0-9_.-]*[A-Za-z0-9])??)(?:\.git)?/?\s*$")

DOC_EXT = {".md", ".markdown", ".mdx", ".txt", ".text", ".rst", ".adoc", ".asciidoc", ".pdf"}
SKIP_DIRS = {".git", ".github", "node_modules", "vendor", "dist", "build", ".venv"}

MAX_FILES = 400
MAX_FILE_BYTES = 3_000_000
MAX_TOTAL_BYTES = 25_000_000
CLONE_TIMEOUT = 240


def parse_spec(text):
    """Return (owner, repo) from many phrasings, or None if it isn't a GitHub repo."""
    m = _SPEC.match(text or "")
    if not m:
        return None
    owner, repo = m.group(1), m.group(2)
    if repo.endswith(".git"):
        repo = repo[:-4]
    return owner, repo


def _markdown_to_text(md):
    """Strip Markdown syntax to plain prose so retrieval sees words, not markup."""
    md = re.sub(r"```.*?```", " ", md, flags=re.DOTALL)      # fenced code blocks
    md = re.sub(r"`([^`]*)`", r"\1", md)                     # inline code
    md = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", md)            # images
    md = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", md)         # links -> link text
    md = re.sub(r"<[^>]+>", " ", md)                         # raw HTML tags
    md = re.sub(r"^\s{0,3}#{1,6}\s*", "", md, flags=re.M)    # headings
    md = re.sub(r"^\s{0,3}>\s?", "", md, flags=re.M)         # blockquotes
    md = re.sub(r"^[ \t]*[-*+]\s+", "", md, flags=re.M)      # bullet markers
    md = re.sub(r"[*_~]{1,3}", "", md)                       # emphasis
    md = re.sub(r"^\s*\|.*\|\s*$", lambda m: m.group(0).replace("|", " "), md, flags=re.M)
    md = re.sub(r"^[-|:\s]+$", "", md, flags=re.M)           # table rule lines
    return md


def _clone(owner, repo, dest):
    url = f"https://github.com/{owner}/{repo}.git"
    # GIT_TERMINAL_PROMPT=0 / GIT_ASKPASS: never block waiting for credentials on a
    # private or missing repo — fail fast instead of hanging the server.
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0", GIT_ASKPASS="echo",
               GCM_INTERACTIVE="never")
    # --depth 1: history not needed. argv form: no shell, no injection.
    subprocess.run(["git", "clone", "--depth", "1", "--quiet", url, dest],
                   check=True, timeout=CLONE_TIMEOUT, env=env,
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)


# --------------------------------------------------------------------------- #
# LICENCE GATE
#
# "Learn from a repo" used to mean "learn whatever is in it" — licence ignored. Vio's
# own data policy says nothing is learned without permission, so a repository is now
# read only when its LICENSE grants that permission. The licence is read from the
# repo itself; the decision is made BEFORE any document is ingested.
# --------------------------------------------------------------------------- #

class LicenseRefused(RuntimeError):
    """The repository's licence does not permit Vio to learn from it."""


# Permissive: reuse permitted, attribution at most. These are allowed.
_PERMISSIVE = [
    ("Apache-2.0", r"apache license\s*,?\s*version 2\.0|apache-2\.0"),
    ("MIT", r"\bmit license\b|permission is hereby granted, free of charge"),
    ("BSD-3-Clause", r"neither the name of .{0,120} nor the names of its contributors"),
    ("BSD-2-Clause", r"redistribution and use in source and binary forms"),
    ("ISC", r"\bisc license\b|permission to use, copy, modify, and(/or)? distribute"),
    ("CC0-1.0", r"\bcc0\b|creative commons zero|creativecommons\.org/publicdomain/zero"),
    ("Unlicense", r"this is free and unencumbered software released into the public domain"),
    ("CC-BY-4.0", r"creative commons attribution 4\.0(?! .{0,40}(noncommercial|non-commercial))|"
                  r"creativecommons\.org/licenses/by/4\.0"),
    ("CC-BY-SA-4.0", r"attribution-sharealike 4\.0|creativecommons\.org/licenses/by-sa/4\.0"),
    ("MPL-2.0", r"mozilla public license,?\s*v(ersion)?\.?\s*2\.0"),
]
# Refused: Creative Commons licences that forbid commercial use or derivatives, which
# is exactly what training is. Matched on the licence's own NAME, never on a bare word:
# GPL-3.0 says "noncommercially" and BSD says "All rights reserved", and both permit
# reuse. Checked before the permissive rules because a CC-NC text also matches CC-BY.
_RESTRICTIVE = [
    ("CC-BY-NC", r"attribution-noncommercial|attribution-non-commercial|"
                 r"creativecommons\.org/licenses/by-nc|\bcc by-nc\b"),
    ("CC-BY-ND", r"attribution-noderivatives|attribution-noderivs|"
                 r"creativecommons\.org/licenses/by-nd|\bcc by-nd\b"),
]
# Only after every permissive/copyleft grant has failed to match does "all rights
# reserved" mean what it says. (BSD texts contain it too, followed by a grant.)
_PROPRIETARY = r"all rights reserved"
# Copyleft: allowed to read, but flagged — learned passages must not be redistributed
# as part of a closed product. Vio is local and personal, so these are permitted.
_COPYLEFT = [
    ("GPL-3.0", r"gnu general public license.{0,40}version 3|gpl-3\.0"),
    ("GPL-2.0", r"gnu general public license.{0,40}version 2|gpl-2\.0"),
    ("AGPL-3.0", r"gnu affero general public license"),
    ("LGPL", r"gnu lesser general public license"),
]

LICENSE_FILES = ("LICENSE", "LICENSE.md", "LICENSE.txt", "LICENCE", "LICENCE.md",
                 "COPYING", "COPYING.md", "LICENSE-APACHE", "LICENSE-MIT")


def detect_license(repo_dir):
    """Identify a repository's licence from its own licence file.

    Returns (spdx_id, verdict, note):
        verdict "allow"   — permissive or copyleft: Vio may learn from it
                "refuse"  — non-commercial / no-derivatives / all-rights-reserved
                "none"    — no licence file: copyright applies by default, so no
                            permission has been granted
    """
    text = ""
    for name in LICENSE_FILES:
        p = os.path.join(repo_dir, name)
        if os.path.isfile(p):
            try:
                with open(p, encoding="utf-8", errors="ignore") as f:
                    text = f.read(20000)
                break
            except OSError:
                continue
    if not text:
        return (None, "none",
                "the repository has no licence file, so by default all rights are "
                "reserved and no permission to reuse its content has been granted")
    low = " ".join(text.lower().split())
    for spdx, pat in _RESTRICTIVE:
        if re.search(pat, low):
            return (spdx, "refuse",
                    f"its licence ({spdx}) forbids commercial use or derivative works")
    for spdx, pat in _PERMISSIVE:
        if re.search(pat, low):
            return spdx, "allow", f"permissive licence ({spdx})"
    for spdx, pat in _COPYLEFT:
        if re.search(pat, low):
            return (spdx, "allow",
                    f"copyleft licence ({spdx}) — fine for personal, local use; don't "
                    "redistribute what Vio learned from it inside a closed product")
    if re.search(_PROPRIETARY, low):
        return ("Proprietary", "refuse",
                "its licence reserves all rights and grants no permission to reuse")
    return ("unrecognised", "refuse",
            "it has a licence file I couldn't identify, so I can't confirm that reuse "
            "is permitted")


def _allow_unlicensed():
    """Explicit operator override — for your OWN private repos, which often have no
    licence file simply because you never added one."""
    return os.environ.get("VIO_LEARN_UNLICENSED", "").strip() in ("1", "true", "yes")


def _read_doc(path, ext):
    if ext == ".pdf":
        from pdftext import extract_text, looks_readable
        with open(path, "rb") as f:
            text = extract_text(f.read())
        return text if looks_readable(text) else ""
    with open(path, encoding="utf-8", errors="ignore") as f:
        text = f.read()
    if ext in (".md", ".markdown", ".mdx"):
        text = _markdown_to_text(text)
    return text


def fetch_repo_docs(spec):
    """Clone the repo and return (owner, repo, [(source, text), …], skipped_count,
    licence) where licence = {"spdx", "verdict", "note"}.

    Raises ValueError for a bad spec, RuntimeError if git/clone fails, and
    LicenseRefused (a RuntimeError) when the repository's licence does not permit
    reuse — checked BEFORE any document is read."""
    parsed = parse_spec(spec)
    if not parsed:
        raise ValueError("That doesn't look like a GitHub repo. Use owner/repo, e.g. "
                         "hegdepavankumar/Fortigate-Firewall-Complete-Guide")
    owner, repo = parsed
    if not shutil.which("git"):
        raise RuntimeError("git is not installed. Install git, or upload the files with 📄.")

    tmp = tempfile.mkdtemp(prefix="vio_gh_")
    dest = os.path.join(tmp, "repo")
    try:
        try:
            _clone(owner, repo, dest)
        except subprocess.CalledProcessError as e:
            err = (e.stderr or b"").decode("utf-8", "ignore")[-200:]
            raise RuntimeError(f"Couldn't clone {owner}/{repo}. Is it public and spelled "
                               f"right? ({err.strip()})")
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"Cloning {owner}/{repo} timed out — the repo may be very large.")

        spdx, verdict, note = detect_license(dest)
        licence = {"spdx": spdx, "verdict": verdict, "note": note}
        if verdict != "allow" and not _allow_unlicensed():
            raise LicenseRefused(
                f"I didn't learn from {owner}/{repo}: {note}. Nothing from it was stored."
                + ("\n\nIf this is YOUR OWN repository, start Vio with "
                   "VIO_LEARN_UNLICENSED=1 to learn it anyway."
                   if verdict == "none" else ""))

        docs, skipped, total = [], 0, 0
        for root, dirs, files in os.walk(dest):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for fn in sorted(files):
                ext = os.path.splitext(fn)[1].lower()
                path = os.path.join(root, fn)
                if ext not in DOC_EXT:
                    skipped += 1
                    continue
                try:
                    if not (0 < os.path.getsize(path) <= MAX_FILE_BYTES):
                        skipped += 1
                        continue
                    text = _read_doc(path, ext)
                except (OSError, Exception):
                    skipped += 1
                    continue
                if len(text.split()) < 20:              # too little to be useful
                    skipped += 1
                    continue
                rel = os.path.relpath(path, dest)
                docs.append((f"{owner}/{repo}:{rel}", text))
                total += len(text)
                if len(docs) >= MAX_FILES or total >= MAX_TOTAL_BYTES:
                    return owner, repo, docs, skipped, licence
        return owner, repo, docs, skipped, licence
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
