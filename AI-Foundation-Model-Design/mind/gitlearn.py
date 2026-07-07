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
    """Clone the repo and return (owner, repo, [(source, text), …], skipped_count).
    Raises ValueError for a bad spec and RuntimeError if git/clone fails."""
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
                    return owner, repo, docs, skipped
        return owner, repo, docs, skipped
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
