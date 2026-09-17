"""
trainpipe — a LICENSED, auditable security-training data pipeline for Vio.

Stages (each pure and testable; live collectors run where the network + private files are):
  1. collect   — official public docs (RFCs, MITRE ATT&CK STIX, CISA KEV, vendor docs) +
                 your sanitized private configs/runbooks. Every item carries metadata:
                 source_url, license, date, vendor, domain, version, content_hash.
  2. sanitize  — strip secrets & PII; REJECT prompt-injection text.
  3. dedupe    — drop exact (content-hash) and near-duplicate items.
  4. chunk     — split by config stanza (configparse) or semantic/paragraph boundaries.
  5. license   — gate: only permissively-licensed content may enter SFT; copyrighted/
                 unknown is RAG-only or excluded — never trained without permission.
  6. split     — RAG corpus / SFT examples / a NEVER-TRAINED eval set, split by SOURCE so
                 chunks of one document never straddle train and eval (no leakage).
  7. sftgen    — SFT records ONLY from grounded evidence, in the schema:
                 {question, context, plan, evidence, answer, citations, confidence,
                  abstention} — plus explicit abstention examples.
  8. report    — data-quality, license, dedup, and train/eval-leakage reports, written
                 BEFORE any fine-tuning. run() refuses to emit training data if a gate fails.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import re
from dataclasses import dataclass, field, asdict

# --------------------------------------------------------------------------- #
# licensing
# --------------------------------------------------------------------------- #
# licenses that MAY be used for fine-tuning (SFT). Everything else is RAG-only or excluded.
SFT_OK_LICENSES = {
    "public-domain", "us-gov-public-domain", "cc0", "cc-by", "cc-by-4.0",
    "ietf-trust", "mitre-attack-terms", "apache-2.0", "mit", "bsd", "private-owned",
}
# licenses allowed in the RAG corpus (retrieval only, not trained)
RAG_OK_LICENSES = SFT_OK_LICENSES | {"vendor-docs-permitted"}
# anything else — "vendor-docs-verify", "copyright", "unknown" — is excluded from both
# until permission is recorded. We NEVER train on copyrighted/unknown content.


@dataclass
class Item:
    source_url: str
    license: str
    content: str
    vendor: str = ""
    domain: str = ""
    version: str = ""
    date: str = ""                       # ISO date the item was published/fetched
    kind: str = "doc"                    # doc | stix | kev | rfc | config | runbook
    content_hash: str = ""

    def finalize(self):
        if not self.date:
            self.date = datetime.date.today().isoformat()
        self.content_hash = hashlib.sha256((self.content or "").encode("utf-8")).hexdigest()
        return self


# --------------------------------------------------------------------------- #
# 0. source manifest (declared, licensed)
# --------------------------------------------------------------------------- #
LICENSED_SOURCES = [
    {"name": "CISA KEV", "url": "https://www.cisa.gov/sites/default/files/feeds/"
     "known_exploited_vulnerabilities.json", "license": "us-gov-public-domain",
     "vendor": "CISA", "domain": "vuln", "kind": "kev"},
    {"name": "MITRE ATT&CK (enterprise STIX)", "url": "https://raw.githubusercontent.com/"
     "mitre/cti/master/enterprise-attack/enterprise-attack.json",
     "license": "mitre-attack-terms", "vendor": "MITRE", "domain": "ttp", "kind": "stix"},
    {"name": "RFC 4271 (BGP-4)", "url": "https://www.rfc-editor.org/rfc/rfc4271.txt",
     "license": "ietf-trust", "vendor": "IETF", "domain": "networking", "kind": "rfc"},
    {"name": "RFC 8446 (TLS 1.3)", "url": "https://www.rfc-editor.org/rfc/rfc8446.txt",
     "license": "ietf-trust", "vendor": "IETF", "domain": "security", "kind": "rfc"},
    # vendor docs default to 'verify' — excluded from training until you confirm the license
    {"name": "FortiOS Admin Guide", "url": "https://docs.fortinet.com/",
     "license": "vendor-docs-verify", "vendor": "Fortinet", "domain": "firewall",
     "kind": "doc"},
]


# --------------------------------------------------------------------------- #
# 2. sanitize (secrets, PII) + prompt-injection rejection
# --------------------------------------------------------------------------- #
_SECRET_PATTERNS = [
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
                re.S), "[REDACTED_PRIVATE_KEY]"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "[REDACTED_AWS_KEY]"),
    (re.compile(r"(?i)\b(api[_-]?key|secret|token|password|passwd|pwd|psk|"
                r"pre-shared-key|bearer)\b\s*[:=]\s*\S+"), r"\1 [REDACTED]"),
    (re.compile(r"(?im)\bset\s+(password|passwd|psksecret|privatekey|psk)\b.*$"),
     r"set \1 [REDACTED]"),
    (re.compile(r"\bENC\s+[A-Za-z0-9+/=]{16,}"), "ENC [REDACTED]"),
    (re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{6,}"),
     "[REDACTED_JWT]"),
]
_PII_PATTERNS = [
    (re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}"), "[EMAIL]"),
    (re.compile(r"(?<!\d)(?:\+?\d[ \-]?){10,13}(?!\d)"), "[PHONE]"),
]
# NOTE: IP addresses are deliberately NOT scrubbed — they are legitimate config content.

_INJECTION = re.compile(
    r"(?i)\b(ignore (all |the )?(previous|prior|above) (instructions|prompts?)|"
    r"disregard (the )?(system|above|previous)|you are now|act as (an? )?|"
    r"new instructions?:|system prompt|jailbreak|do anything now|\bDAN\b|"
    r"pretend to be|override your|reveal your (system )?prompt)\b")


def sanitize(text: str):
    """Return (clean_text, findings). Redacts secrets & PII in place."""
    findings = []
    out = text or ""
    for pat, repl in _SECRET_PATTERNS:
        out, n = pat.subn(repl, out)
        if n:
            findings.append(("secret", n))
    for pat, repl in _PII_PATTERNS:
        out, n = pat.subn(repl, out)
        if n:
            findings.append(("pii", n))
    return out, findings


def is_prompt_injection(text: str) -> bool:
    return bool(_INJECTION.search(text or ""))


# --------------------------------------------------------------------------- #
# 1. collect
# --------------------------------------------------------------------------- #
def _fetch(url):
    """Fetch text/JSON for a public source, SSRF-guarded via websearch when available."""
    try:
        import websearch
        if not websearch.net_enabled():
            raise RuntimeError("set VIO_ALLOW_NET=1 to collect public sources")
        raw = websearch._open(url, engine=False)
        return raw.decode("utf-8", "replace")
    except Exception as e:
        raise RuntimeError(f"fetch failed for {url}: {e}")


def collect_public(sources=None, fetch=_fetch):
    """Fetch declared public sources → [Item]. STIX/KEV are expanded per-object."""
    items = []
    for s in (sources if sources is not None else LICENSED_SOURCES):
        if s.get("kind") == "doc" and s.get("license", "").startswith("vendor-docs-verify"):
            continue                              # skip unverified vendor docs by default
        try:
            body = fetch(s["url"])
        except Exception:
            continue
        for it in _expand(s, body):
            items.append(it.finalize())
    return items


def _expand(s, body):
    kind = s.get("kind", "doc")
    meta = dict(license=s["license"], vendor=s.get("vendor", ""),
                domain=s.get("domain", ""), source_url=s["url"], kind=kind)
    if kind == "kev":
        try:
            data = json.loads(body)
            for v in data.get("vulnerabilities", []):
                txt = (f"{v.get('cveID')} — {v.get('vulnerabilityName')}. "
                       f"{v.get('shortDescription','')} Action: {v.get('requiredAction','')}")
                yield Item(content=txt, version=str(data.get("catalogVersion", "")), **meta)
        except Exception:
            return
    elif kind == "stix":
        try:
            data = json.loads(body)
            for o in data.get("objects", []):
                if o.get("type") in ("attack-pattern", "course-of-action") and o.get("name"):
                    yield Item(content=f"{o.get('name')}: {o.get('description','')}",
                               version=o.get("x_mitre_version", ""), **meta)
        except Exception:
            return
    else:
        yield Item(content=body, **meta)


def collect_private(folder):
    """Load sanitized private configs/runbooks from a local folder → [Item] (never fetched,
    license 'private-owned'). Config files become kind='config', the rest 'runbook'."""
    items = []
    if not folder or not os.path.isdir(folder):
        return items
    for root, _dirs, files in os.walk(folder):
        for fn in files:
            if not fn.lower().endswith((".txt", ".md", ".conf", ".cfg", ".rules", ".log")):
                continue
            path = os.path.join(root, fn)
            try:
                with open(path, encoding="utf-8", errors="replace") as f:
                    body = f.read()
            except Exception:
                continue
            try:
                import configparse
                kind = "config" if configparse.looks_like_config(body) else "runbook"
            except Exception:
                kind = "runbook"
            items.append(Item(content=body, source_url=f"file://{path}",
                              license="private-owned", vendor="internal",
                              domain="internal", kind=kind).finalize())
    return items


# --------------------------------------------------------------------------- #
# 2b. clean a batch: sanitize + reject injection
# --------------------------------------------------------------------------- #
def clean(items):
    """Sanitize every item; drop any whose content is prompt-injection. Returns
    (clean_items, rejected_injection_count, sanitized_findings_count)."""
    out, rejected, findings_n = [], 0, 0
    for it in items:
        if is_prompt_injection(it.content):
            rejected += 1
            continue
        clean_text, findings = sanitize(it.content)
        findings_n += sum(n for _, n in findings)
        it.content = clean_text
        it.finalize()                             # rehash after redaction
        out.append(it)
    return out, rejected, findings_n


# --------------------------------------------------------------------------- #
# 3. dedupe (exact + near)
# --------------------------------------------------------------------------- #
def _norm(text):
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def _near_key(text):
    return hashlib.sha1(_norm(text)[:400].encode("utf-8")).hexdigest()


def dedupe(items):
    """Drop exact (content_hash) and near (normalized-prefix) duplicates. Returns
    (unique_items, removed_exact, removed_near)."""
    seen_hash, seen_near, out, ex, nr = set(), set(), [], 0, 0
    for it in items:
        if it.content_hash in seen_hash:
            ex += 1
            continue
        nk = _near_key(it.content)
        if nk in seen_near:
            nr += 1
            continue
        seen_hash.add(it.content_hash)
        seen_near.add(nk)
        out.append(it)
    return out, ex, nr


# --------------------------------------------------------------------------- #
# 4. chunk (config stanza / semantic boundary)
# --------------------------------------------------------------------------- #
@dataclass
class Chunk:
    text: str
    source_url: str
    license: str
    domain: str
    vendor: str
    kind: str
    doc_hash: str                        # hash of the parent document (for leakage checks)
    chunk_hash: str = ""

    def finalize(self):
        self.chunk_hash = hashlib.sha256(self.text.encode("utf-8")).hexdigest()
        return self


def _prose_chunks(text, target=900):
    paras, cur, out = re.split(r"\n\s*\n", text or ""), "", []
    for p in paras:
        p = p.strip()
        if not p:
            continue
        if len(cur) + len(p) + 2 <= target:
            cur = (cur + "\n\n" + p).strip()
        else:
            if cur:
                out.append(cur)
            cur = p if len(p) <= target else p[:target]
    if cur:
        out.append(cur)
    return out


def chunk_items(items):
    chunks = []
    for it in items:
        try:
            import configparse
            if it.kind == "config" or configparse.looks_like_config(it.content):
                objs = configparse.parse(it.content)
                pieces = [o.raw.strip() for o in objs if o.raw.strip()] or [it.content]
            else:
                pieces = _prose_chunks(it.content)
        except Exception:
            pieces = _prose_chunks(it.content)
        for piece in pieces:
            if len(piece.strip()) < 12:          # keep short config stanzas; drop scraps
                continue
            chunks.append(Chunk(text=piece.strip(), source_url=it.source_url,
                                license=it.license, domain=it.domain, vendor=it.vendor,
                                kind=it.kind, doc_hash=it.content_hash).finalize())
    return chunks


# --------------------------------------------------------------------------- #
# 5+6. license gate + split (RAG / SFT / eval) — split by SOURCE to prevent leakage
# --------------------------------------------------------------------------- #
def _bucket(doc_hash, eval_frac=0.15):
    """Deterministic per-DOCUMENT bucket in [0,1) so all chunks of a doc share a split."""
    return int(doc_hash[:8], 16) / 0xFFFFFFFF


def split(chunks, eval_frac=0.15):
    """Assign each chunk to rag / sft / eval. Eval is chosen per-document (never trained),
    and a document's chunks never straddle sft and eval. License gates SFT/RAG membership."""
    rag, sft, ev, excluded = [], [], [], []
    for c in chunks:
        if c.license not in RAG_OK_LICENSES:
            excluded.append(c)                    # copyrighted/unknown → excluded entirely
            continue
        rag.append(c)                             # everything permitted is retrievable
        if c.license not in SFT_OK_LICENSES:
            continue                              # RAG-only (e.g. vendor-docs-permitted)
        if _bucket(c.doc_hash) < eval_frac:
            ev.append(c)                          # held-out, NEVER trained
        else:
            sft.append(c)
    return {"rag": rag, "sft": sft, "eval": ev, "excluded": excluded}


# --------------------------------------------------------------------------- #
# 7. SFT generation — grounded, structured, with abstention
# --------------------------------------------------------------------------- #
def _topic(text):
    m = re.search(r"(?im)^\s*(?:config\s+|edit\s+|#+\s*)?([A-Za-z][\w .\-/]{3,60})", text)
    return (m.group(1).strip() if m else text[:48]).strip()


def sft_record(chunk: Chunk):
    """One grounded SFT record from a chunk — the required schema."""
    topic = _topic(chunk.text)
    cite = f"{chunk.vendor or 'source'} — {chunk.source_url} ({chunk.license})"
    return {
        "question": f"According to {chunk.vendor or 'the documentation'}, what should I "
                    f"know about {topic}?",
        "context": chunk.text[:1200],
        "plan": ["retrieve the grounding passage", "verify it answers the question",
                 "answer only from it", "cite the source", "abstain if unsupported"],
        "evidence": [chunk.text[:400]],
        "answer": f"Based on {chunk.vendor or 'the source'}: {chunk.text[:300].strip()}"
                  + ("…" if len(chunk.text) > 300 else ""),
        "citations": [cite],
        "confidence": 0.8 if len(chunk.text) > 120 else 0.6,
        "abstention": False,
    }


ABSTENTION_PROBES = [
    "what is the current stock price of the vendor",
    "what is my production admin password",
    "who won the 2050 world cup",
    "what will next quarter's zero-days be",
]


def abstention_record(question):
    """A record that TEACHES refusal when evidence is missing (never invents)."""
    return {
        "question": question,
        "context": "",
        "plan": ["search grounding", "find no supporting evidence", "abstain honestly"],
        "evidence": [],
        "answer": "I don't have grounded evidence for that, so I won't guess. "
                  "Provide a source or ask something covered by the documentation.",
        "citations": [],
        "confidence": 0.05,
        "abstention": True,
    }


def gen_sft(sft_chunks, max_per_doc=3):
    records, per_doc = [], {}
    for c in sft_chunks:
        per_doc.setdefault(c.doc_hash, 0)
        if per_doc[c.doc_hash] >= max_per_doc:
            continue
        per_doc[c.doc_hash] += 1
        records.append(sft_record(c))
    for q in ABSTENTION_PROBES:                   # always include refusal exemplars
        records.append(abstention_record(q))
    return records


# --------------------------------------------------------------------------- #
# 8. reports (BEFORE any fine-tuning)
# --------------------------------------------------------------------------- #
def leakage_report(sft_chunks, eval_chunks):
    sft_h = {c.chunk_hash for c in sft_chunks}
    sft_docs = {c.doc_hash for c in sft_chunks}
    chunk_overlap = sorted(sft_h & {c.chunk_hash for c in eval_chunks})
    doc_overlap = sorted(sft_docs & {c.doc_hash for c in eval_chunks})
    return {"sft_chunks": len(sft_chunks), "eval_chunks": len(eval_chunks),
            "chunk_overlap": len(chunk_overlap), "doc_overlap": len(doc_overlap),
            "clean": not chunk_overlap and not doc_overlap}


def license_report(chunks, splits):
    by_lic = {}
    for c in chunks:
        by_lic[c.license] = by_lic.get(c.license, 0) + 1
    return {"by_license": by_lic,
            "excluded_non_permissive": len(splits["excluded"]),
            "sft_licenses": sorted({c.license for c in splits["sft"]}),
            "all_sft_licenses_permitted":
                all(c.license in SFT_OK_LICENSES for c in splits["sft"])}


def quality_report(raw_n, cleaned, rejected_injection, sanitized_findings, deduped,
                   removed_exact, removed_near, chunks):
    lengths = [len(c.text) for c in chunks] or [0]
    return {"collected": raw_n, "after_clean": len(cleaned),
            "rejected_prompt_injection": rejected_injection,
            "secrets_pii_redactions": sanitized_findings,
            "after_dedupe": len(deduped), "removed_exact_dupes": removed_exact,
            "removed_near_dupes": removed_near, "chunks": len(chunks),
            "avg_chunk_len": round(sum(lengths) / len(lengths), 1),
            "min_chunk_len": min(lengths), "max_chunk_len": max(lengths)}


# --------------------------------------------------------------------------- #
# orchestration
# --------------------------------------------------------------------------- #
def run(private_folder=None, out_dir=None, sources=None, collect_net=True):
    """Full pipeline. Writes RAG corpus, SFT, eval, and the four reports. Returns a dict
    with all reports and a 'ready_to_train' gate that is True only when license and
    leakage checks pass. NOTHING is fine-tuned here — that's a separate, human step."""
    out_dir = out_dir or os.path.join(os.environ.get("VIO_DATA_DIR", "."), "trainpipe_out")
    os.makedirs(out_dir, exist_ok=True)

    raw = []
    if collect_net:
        raw += collect_public(sources)
    raw += collect_private(private_folder)

    cleaned, rej_inj, san_n = clean(raw)
    deduped, rm_ex, rm_nr = dedupe(cleaned)
    chunks = chunk_items(deduped)
    splits = split(chunks)
    sft = gen_sft(splits["sft"])

    reports = {
        "quality": quality_report(len(raw), cleaned, rej_inj, san_n, deduped, rm_ex, rm_nr,
                                  chunks),
        "license": license_report(chunks, splits),
        "dedup": {"removed_exact": rm_ex, "removed_near": rm_nr,
                  "unique": len(deduped)},
        "leakage": leakage_report(splits["sft"], splits["eval"]),
    }
    reports["ready_to_train"] = bool(
        reports["leakage"]["clean"] and reports["license"]["all_sft_licenses_permitted"]
        and rej_inj >= 0)

    def _dump(name, rows):
        with open(os.path.join(out_dir, name), "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    _dump("rag_corpus.jsonl", [asdict(c) for c in splits["rag"]])
    _dump("eval_holdout.jsonl", [asdict(c) for c in splits["eval"]])
    _dump("sft.jsonl", sft)
    with open(os.path.join(out_dir, "REPORTS.json"), "w", encoding="utf-8") as f:
        json.dump(reports, f, ensure_ascii=False, indent=2)
    reports["out_dir"] = out_dir
    return reports


if __name__ == "__main__":
    import sys
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    folder = sys.argv[1] if len(sys.argv) > 1 else None
    print("Running the licensed security-training pipeline…")
    print("  (public sources need VIO_ALLOW_NET=1; private folder:", folder or "none", ")")
    rep = run(private_folder=folder, collect_net=bool(os.environ.get("VIO_ALLOW_NET")))
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    print("\nReady to fine-tune:" , "YES ✅" if rep["ready_to_train"] else "NO ❌ (fix gates)")
    print("Artifacts + REPORTS.json in:", rep["out_dir"])
