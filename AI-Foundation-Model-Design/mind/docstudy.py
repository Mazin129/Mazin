"""
docstudy — what "learning a document" actually means, made checkable.

Storing passages is not learning. When a file is taught, Vio now:

  1. reports what it really read (words, passages, how many were new);
  2. SELF-TESTS retrieval: for a spread of passages it builds a question from their most
     distinctive words and checks the library brings that document back — so "you can
     ask me about it" is a measured claim, not a slogan;
  3. pulls out the structure (rules, steps, definitions) deterministically;
  4. STUDIES it with the local model in the background — notes per part, then one
     digest (what it is about, key points, options and trade-offs, recommendations,
     questions it answers). The digest is stored as study notes in the library, so later
     answers draw on the understanding, not only on raw fragments.

Records live in DATA_DIR/documents.json. Nothing leaves the machine.
"""
from __future__ import annotations

import json
import os
import re
import threading
import time

_STOP = set("""the a an and or of to in on for with by from at as is are was were be been
this that these those it its into than then there their they which who whom what when
where why how not no yes can will would should could may might must shall also such
other more most some any each all both per via over under between within without about
""".split())


def _words(text):
    return [w for w in re.findall(r"[A-Za-z][A-Za-z0-9_.-]{3,}", text or "")
            if w.lower() not in _STOP]


def _name_tokens(name):
    """File-name words: 'Flynas-Crayon_Azure.pdf' → {flynas, crayon, azure}."""
    return {w for w in re.findall(r"[a-z0-9]+", (name or "").lower())
            if len(w) > 2 and w not in _STOP and w not in ("pdf", "docx", "txt", "file")}


class DocStore:
    """Per-document learning records: stats, self-test result, structure, study notes."""

    def __init__(self, data_dir):
        self.path = os.path.join(data_dir, "documents.json")
        self._lock = threading.Lock()
        try:
            with open(self.path, encoding="utf-8") as f:
                self.docs = json.load(f)
        except Exception:
            self.docs = {}

    def _save(self):
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.docs, f, ensure_ascii=False, indent=1)
        except Exception:
            pass

    def put(self, source, **fields):
        with self._lock:
            rec = self.docs.setdefault(source, {"source": source})
            rec.update(fields)
            rec["updated"] = time.time()
            self._save()
            return dict(rec)

    def get(self, source):
        return self.docs.get(source)

    def find(self, name=""):
        """The record whose name best matches `name`; the most recent when empty."""
        recs = sorted(self.docs.values(), key=lambda r: r.get("learned", 0))
        if not recs:
            return None
        if not name.strip():
            return recs[-1]
        want = _name_tokens(name)
        best, score = None, 0
        for r in recs:
            have = _name_tokens(r["source"])
            s = len(want & have)
            if s > score or (s == score and s and r is recs[-1]):
                best, score = r, s
        return best


# --------------------------------------------------------------------------- #
# 2. retrieval self-test
# --------------------------------------------------------------------------- #
def self_test(lib, chunks, n=5):
    """Can the library find this document again from a question about it?

    For up to `n` passages spread through the document, the query is that passage's
    most distinctive words (rarest in the whole library). A test passes when one of the
    top-3 results is a passage of this document. Returns (passed, total, misses)."""
    chunks = [c for c in chunks if len(_words(c)) >= 6]
    if not chunks:
        return 0, 0, []
    step = max(1, len(chunks) // n)
    picks = chunks[::step][:n]
    mine = {c.strip() for c in chunks}
    idf = {}
    try:
        idf = {t: lib.vec.idf_[i] for t, i in lib.vec.vocabulary_.items()}
    except Exception:
        pass
    passed, misses = 0, []
    for c in picks:
        ws = list(dict.fromkeys(w.lower() for w in _words(c)))
        ws.sort(key=lambda w: -idf.get(w, len(w) / 3.0))
        q = " ".join(ws[:6])
        try:
            hits = lib.search(q, k=3)
        except Exception:
            hits = []
        if any((d or "").strip() in mine for d, _ in hits):
            passed += 1
        else:
            misses.append(q)
    return passed, len(picks), misses


# --------------------------------------------------------------------------- #
# 4. study with the local model
# --------------------------------------------------------------------------- #
PART_SYSTEM = ("You are studying a technical document to understand it deeply. Write "
               "compact study notes on the part you are given: the key points, concrete "
               "facts and numbers, options compared and their trade-offs, decisions and "
               "recommendations, and any rules or steps. Only what the text says.")

DIGEST_SYSTEM = ("You have studied a document part by part. From your notes, write what "
                 "you now understand, in this shape:\n"
                 "**What it is about** — two sentences.\n"
                 "**Key points** — the most important facts, bullet list.\n"
                 "**Options and trade-offs** — what is compared and how they differ "
                 "(skip if nothing is compared).\n"
                 "**Recommendation / decision** — what the document concludes or advises.\n"
                 "**Questions it answers** — three questions someone could now ask.\n"
                 "Be specific to THIS document; never add facts that are not in the notes.")


def _parts(text, size=5000, cap=6):
    paras = re.split(r"\n\s*\n", text or "")
    parts, cur = [], ""
    for p in paras:
        if len(cur) + len(p) > size and cur:
            parts.append(cur)
            cur = ""
        cur += p + "\n\n"
    if cur.strip():
        parts.append(cur)
    # a single huge paragraph (PDF text often has no blank lines): hard-split it
    out = []
    for p in parts:
        out += [p[i:i + size] for i in range(0, len(p), size)] or [p]
    if len(out) > cap:                    # spread the budget over the whole document
        step = len(out) / cap
        out = [out[int(i * step)] for i in range(cap)]
    return out


def study(llm, text, source):
    """Notes per part, then one digest. Returns (digest, note) or (None, reason)."""
    if llm is None or not getattr(llm, "available", False):
        return None, "no local model running — start Ollama to let me study documents"
    cap = int(os.environ.get("VIO_STUDY_PARTS", "6"))
    total_chars = len(text or "")
    parts = _parts(text, cap=cap)
    notes = []
    for i, p in enumerate(parts, 1):
        out = llm.generate(f"Document: {source}\nPart {i} of {len(parts)}:\n\n{p}",
                           system=PART_SYSTEM, temperature=0.2, max_tokens=700,
                           personal=False)
        if out:
            notes.append(f"[Part {i}]\n{out}")
    if not notes:
        return None, f"the model produced no notes ({getattr(llm, 'last_error', '')})"
    digest = llm.generate(f"Document: {source}\n\nYour notes:\n\n" + "\n\n".join(notes),
                          system=DIGEST_SYSTEM, temperature=0.2, max_tokens=1200,
                          think=True, personal=False)
    if not digest:
        digest = "\n\n".join(notes)
    studied = sum(len(p) for p in parts)
    cover = min(100, round(100 * studied / max(1, total_chars)))
    return digest, f"studied {len(parts)} part(s), about {cover}% of the text"
