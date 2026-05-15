# Vio — Long-term Memory

> Load this skill whenever you need to **recall** what you've stored
> about Mazin (his network, his family, his work, his preferences) or
> **store** something new that should outlive this session.

---

## Where memory lives

Single SQLite file:

```
/data/.openclaw/workspace/vio-memory/memory.db
```

If the file does not exist yet, **create it on first use**:

```bash
mkdir -p /data/.openclaw/workspace/vio-memory
sqlite3 /data/.openclaw/workspace/vio-memory/memory.db <<'SQL'
CREATE TABLE IF NOT EXISTS facts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  subject   TEXT NOT NULL,
  predicate TEXT NOT NULL,
  object    TEXT NOT NULL,
  tags      TEXT NOT NULL,
  confidence REAL NOT NULL DEFAULT 0.8,
  superseded_by INTEGER,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  expires_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_facts_subject ON facts(subject);
CREATE INDEX IF NOT EXISTS idx_facts_tags ON facts(tags);
CREATE INDEX IF NOT EXISTS idx_facts_active ON facts(superseded_by) WHERE superseded_by IS NULL;

CREATE TABLE IF NOT EXISTS followups (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  description TEXT NOT NULL,
  due_at TEXT,
  done_at TEXT,
  priority INTEGER NOT NULL DEFAULT 3,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_followups_open ON followups(done_at, due_at);
SQL
chmod 600 /data/.openclaw/workspace/vio-memory/memory.db
```

## Reading before answering

At the start of every non-trivial turn, recall what's relevant:

```bash
# By tag (most common path)
sqlite3 -separator '|' /data/.openclaw/workspace/vio-memory/memory.db \
  "SELECT id, subject, predicate, object, confidence
   FROM facts
   WHERE superseded_by IS NULL
     AND tags LIKE '%TAG%'
   ORDER BY created_at DESC LIMIT 25;"

# By keyword in the object field
sqlite3 -separator '|' /data/.openclaw/workspace/vio-memory/memory.db \
  "SELECT id, subject, predicate, object
   FROM facts
   WHERE superseded_by IS NULL
     AND object LIKE '%KEYWORD%'
   ORDER BY created_at DESC LIMIT 25;"

# Open follow-ups due this week
sqlite3 -separator '|' /data/.openclaw/workspace/vio-memory/memory.db \
  "SELECT id, priority, description, due_at
   FROM followups
   WHERE done_at IS NULL
     AND (due_at IS NULL OR due_at <= datetime('now','+7 days'))
   ORDER BY priority, due_at LIMIT 10;"
```

Inject what you find into your reasoning silently. Only mention it to
Mazin if he asks "what do you know about X" or if the recall is the
reason you're recommending something.

## Writing memory

A **good fact** looks like (subject, predicate, object):

✅ `('Mazin', 'studies', 'NSE7 Enterprise FW')` tags=`study,work`
✅ `('home_network', 'mgmt_subnet', '10.10.17.0/24')` tags=`network`
✅ `('Mazin', 'prefers_language', 'ar')` tags=`preference`
✅ `('bill:internet', 'due_day', '12')` tags=`family,bill`

A **bad fact** (don't write these):

❌ `('Mazin','said','hi')` — noise
❌ `('Mazin','ip','82.x.x.x')` — PII, stale within hours
❌ `('child:<name>','condition','asthma')` — medical, child PII

Write with:

```bash
sqlite3 /data/.openclaw/workspace/vio-memory/memory.db \
  "INSERT INTO facts (subject, predicate, object, tags, confidence)
   VALUES ('SUBJECT','PREDICATE','OBJECT','TAG1,TAG2',0.9);"
```

**Supersede** an old fact rather than deleting it:

```bash
sqlite3 /data/.openclaw/workspace/vio-memory/memory.db <<'SQL'
INSERT INTO facts (subject, predicate, object, tags, confidence)
  VALUES ('SUBJECT','PREDICATE','NEW_OBJECT','TAG1,TAG2',0.9);
UPDATE facts SET superseded_by = last_insert_rowid()
  WHERE id = OLD_ID_HERE;
SQL
```

## Follow-ups

Add a follow-up when Mazin says "remind me", "next week", "ask me again
later", or when you make a promise:

```bash
sqlite3 /data/.openclaw/workspace/vio-memory/memory.db \
  "INSERT INTO followups (description, due_at, priority)
   VALUES ('DESCRIPTION', datetime('now','+N days'), PRIORITY);"
```

Priority: 1 (now) … 5 (someday).

Close one:
```bash
sqlite3 /data/.openclaw/workspace/vio-memory/memory.db \
  "UPDATE followups SET done_at = datetime('now') WHERE id = ID;"
```

## Never store

- Passwords, MFA codes, full card numbers, government IDs.
- Plaintext private keys.
- Exact home address.
- Child medical diagnoses.
- API keys or service tokens — those go in environment variables, not
  here.

## Weekly hygiene (run every Friday)

```bash
sqlite3 /data/.openclaw/workspace/vio-memory/memory.db <<'SQL'
-- Mark low-confidence aging facts for review
UPDATE facts SET expires_at = datetime('now','+7 days')
WHERE confidence < 0.5
  AND created_at < datetime('now','-60 days')
  AND expires_at IS NULL;

-- Hard-delete what expired
DELETE FROM facts WHERE expires_at IS NOT NULL
  AND expires_at < datetime('now');

-- Compact superseded chains older than 30 days
DELETE FROM facts WHERE superseded_by IS NOT NULL
  AND created_at < datetime('now','-30 days');
SQL
```

## Tag taxonomy (use these, don't invent new ones casually)

```
network                      home/work network facts
network,fortigate            FortiGate-specific
network,fortiswitch
network,fortiap
study,fortinet,nse6          NSE6 study
study,fortinet,nse7          NSE7 study
study,weakness               topic missed twice
family                       family-scoped
family,spouse / family,child:<name> / family,parent:<name>
family,bill / family,appointment / family,travel
work                         employer/customer matters
preference                   Mazin's stated likes/dislikes
incident                     SOC/incident notes
followup                     points to a followups row
```
