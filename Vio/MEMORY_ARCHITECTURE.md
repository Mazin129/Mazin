# Vio — Memory Architecture

Without memory, Vio is just a chatbot. With memory, Vio becomes *your* agent.

This document specifies a memory system you can stand up on a Hostinger VPS in
under an hour, and grow from there.

---

## Three layers of memory

| Layer | Lifetime | Storage | What goes in |
|-------|----------|---------|--------------|
| **Working** | one turn | LLM context window | the current question + injected context |
| **Episodic** | days–weeks | SQLite `conversations` table | full turn-by-turn chat history |
| **Semantic** | forever | SQLite `facts` table + vector index | distilled facts, preferences, decisions |

Working memory is automatic. Episodic is a log. Semantic is what makes Vio feel
like it *knows you*.

---

## Schema (SQLite, paste this into `schema.sql`)

```sql
-- Conversation log
CREATE TABLE IF NOT EXISTS conversations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT NOT NULL,
  role TEXT NOT NULL CHECK (role IN ('user','assistant','tool','system')),
  content TEXT NOT NULL,
  tokens INTEGER,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_conv_session ON conversations(session_id, created_at);

-- Distilled facts (the long-term memory)
CREATE TABLE IF NOT EXISTS facts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  subject TEXT NOT NULL,           -- e.g. "Mazin", "home_network", "kid:Lina"
  predicate TEXT NOT NULL,         -- e.g. "prefers", "has_ip", "studies"
  object TEXT NOT NULL,            -- the value
  tags TEXT NOT NULL,              -- comma-separated: network,family,study
  confidence REAL NOT NULL DEFAULT 0.8,  -- 0.0–1.0
  source_session TEXT,             -- which session produced this
  superseded_by INTEGER,           -- FK to a newer fact that replaced this one
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  expires_at TEXT                  -- NULL = never
);
CREATE INDEX IF NOT EXISTS idx_facts_subject ON facts(subject);
CREATE INDEX IF NOT EXISTS idx_facts_tags ON facts(tags);
CREATE INDEX IF NOT EXISTS idx_facts_active ON facts(superseded_by) WHERE superseded_by IS NULL;

-- Open follow-ups (things Vio promised to come back to)
CREATE TABLE IF NOT EXISTS followups (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  description TEXT NOT NULL,
  due_at TEXT,
  done_at TEXT,
  priority INTEGER NOT NULL DEFAULT 3,  -- 1=now, 5=someday
  related_facts TEXT,                   -- comma-separated fact IDs
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_followups_open ON followups(done_at, due_at);

-- Vector index for semantic search over facts.
-- If you can't run sqlite-vss, store embeddings in a separate Qdrant/Chroma
-- collection and keep `facts.id` as the foreign key.
CREATE TABLE IF NOT EXISTS fact_embeddings (
  fact_id INTEGER PRIMARY KEY REFERENCES facts(id),
  embedding BLOB NOT NULL,   -- float32[768] or [1024], depending on model
  model TEXT NOT NULL
);
```

## Read path (every user turn)

```
1. Embed the user message → query vector.
2. Top-k (k=8) semantic search over fact_embeddings WHERE superseded_by IS NULL.
3. SELECT * FROM followups WHERE done_at IS NULL AND
     (due_at IS NULL OR due_at <= datetime('now', '+7 days'))
   ORDER BY priority, due_at LIMIT 5.
4. Pull the last 10 messages of the current session_id from conversations.
5. Compose a CONTEXT block and inject it BEFORE the user turn:

   <vio-memory>
     facts:
       - {subject} {predicate} {object}   (confidence={c}, tags={tags})
       ...
     open_followups:
       - [P{priority}] {description}  due {due_at}
       ...
   </vio-memory>
```

## Write path (after the assistant response)

A small classifier (a second, cheap LLM call) inspects the just-finished turn
and decides what to persist. Prompt:

```
Given this conversation turn, output a JSON list of memory operations.
Allowed ops:
  {"op":"add_fact","subject":..., "predicate":..., "object":..., "tags":[...], "confidence":0.0-1.0}
  {"op":"supersede","old_id":N,"new":{...}}
  {"op":"add_followup","description":..., "due_at":..., "priority":1-5}
  {"op":"complete_followup","id":N}
Only emit ops for genuinely new or changed information. Output [] if nothing.
NEVER store: passwords, MFA codes, full card numbers, gov IDs, plaintext
private keys, child medical details, exact home address.
```

Then apply the ops in a transaction.

## What goes into a *good* fact

✅ Good:
- `subject=Mazin, predicate=studies, object=NSE7 Enterprise FW, tags=study,work`
- `subject=home_network, predicate=mgmt_subnet, object=10.10.17.0/24, tags=network`
- `subject=Mazin, predicate=prefers_language, object=ar, tags=preference`

❌ Bad:
- `subject=Mazin, predicate=said, object="hi"` — noise
- `subject=Mazin, predicate=ip, object=82.x.x.x` — PII, and stale within hours

## Hygiene (run weekly via cron)

```sql
-- 1. Mark low-confidence facts older than 60 days for review
UPDATE facts SET expires_at = datetime('now', '+7 days')
WHERE confidence < 0.5 AND created_at < datetime('now', '-60 days')
  AND expires_at IS NULL;

-- 2. Hard-delete expired facts
DELETE FROM facts WHERE expires_at IS NOT NULL AND expires_at < datetime('now');

-- 3. Compact superseded chains older than 30 days
DELETE FROM facts WHERE superseded_by IS NOT NULL
  AND created_at < datetime('now','-30 days');
```

## Privacy at rest

- VPS disk should be **encrypted** (LUKS on the volume, or at minimum a
  dedicated `/var/lib/vio` mount with `chmod 700`).
- SQLite file owned by `vio:vio`, mode `0600`.
- Daily encrypted backup (`age` or `gpg`) pushed to a separate object store.
  Never commit the DB or backups to git.

## Why this design

- **Triple-store facts** (subject/predicate/object) makes facts easy to update
  and reason about, instead of a fragile blob of "notes."
- **Supersession** beats deletion: you can audit why a fact changed.
- **Tags** let you do quick filtered recall ("show me everything tagged `family`
  before our trip on Friday").
- **Vector + structured** together: vectors find the *relevant* facts, the
  structured fields let you filter and update them deterministically.
