# Vio — Tool Integrations

Vio without tools is a textbook. Vio with the right tools is an operator.

The tools below are ranked by *return on integration effort*. Do them in
order. Don't skip ahead — each builds on the last.

---

## Tier 1 — Must have (Week 1)

### 1. RAG over your own notes
- **What**: chunk + embed `NSE6-LAN-Edge/`, `NSE7-Enterprise-FW/`, `Lab/`,
  `Resources/` and any future notes.
- **Stack**: Qdrant (or Chroma) + an embedding model (`bge-m3` for bilingual
  AR/EN, or `text-embedding-3-small` if hosted is ok).
- **Tool surface to Vio**:
  ```json
  {"name":"notes_search","args":{"query":"string","top_k":5,"tag":"optional"}}
  ```
- **Win**: every domain answer cites a file path you wrote.

### 2. Memory (already designed in `MEMORY_ARCHITECTURE.md`)
- Tools: `memory_recall(subject?, tag?, k)`, `memory_write(op_json)`,
  `followups_due(within_days)`.

### 3. Web search
- **Stack**: Brave Search API or SerpAPI. Cache results 24 h to control cost.
- **Tool**: `web_search(query, k=5)` returns title + url + snippet. Vio reads
  full pages via `web_fetch(url)` only when it cites a specific number.

## Tier 2 — High leverage (Weeks 2–4)

### 4. FortiGate read-only API
- Use a dedicated REST API admin with **`prof_admin` read-only** profile,
  trusted-hosts locked to the VPS IP.
- **Tools**:
  ```
  fortigate_status()              # version, HA, license, uptime
  fortigate_routes(vrf?)          # routing table
  fortigate_sessions(filter)      # session table with filter
  fortigate_policies(vdom?)       # firewall policies
  fortigate_log_search(query, time_range)   # via FortiAnalyzer if present
  ```
- **Never** expose write endpoints to Vio without an explicit "apply" gate.

### 5. CVE & advisory feed
- Sources: NVD JSON 2.0 API, FortiGuard PSIRT RSS, Cisco PSIRT openVulnRSS.
- Daily pull, store in `facts` tagged `cve` only when relevant to assets you
  own.
- **Tool**: `advisories_today(vendor?)`.

### 6. Calendar (read + propose-write)
- CalDAV via your provider, or Google Calendar OAuth.
- Tools: `calendar_today()`, `calendar_week()`, `calendar_propose_event(...)`.
- Writes always come back to the principal for confirmation first.

## Tier 3 — Force multiplier (Weeks 5–8)

### 7. Code execution sandbox
- For Vio to write & run Python scripts (log parsing, quick stats, plotting).
- **Stack**: a separate container with no network, mounted read-only on the
  notes directory, writable on `/tmp` only. Kill after 60 s.
- **Tool**: `python_exec(code, timeout_s=30)`.

### 8. Email
- IMAP read for incoming. Compose drafts that the principal sends manually
  until you trust the agent.
- **Tools**: `email_search(query)`, `email_read(id)`, `email_draft(to,
  subject, body)`.

### 9. Messaging notifier
- Signal (via signal-cli) or Telegram bot. **One-way out only**, no
  command-and-control of Vio over public messengers.
- **Tool**: `notify(channel, message)`.

### 10. FortiAnalyzer log query
- If you run FortiAnalyzer, expose a parameterized query tool.
- **Tool**: `faz_query(adom, dataset, time_range, filter)`.

## Tier 4 — Optional, evaluate carefully (Week 9+)

| Tool | When it makes sense | Risk to manage |
|------|---------------------|----------------|
| Browser automation (Playwright) | filling repetitive web forms | wide attack surface; isolate in its own VM |
| GitHub API | tracking your own repos | token scopes minimum needed |
| OS-level shell on the VPS | really last-resort | requires strict allowlist or jailed shell |
| Voice (STT/TTS) | hands-free family briefs | privacy: keep audio on-VPS, don't ship to cloud |

## Tool schema standard

Every tool is described to Vio in the same shape so it can choose correctly:

```json
{
  "name": "fortigate_sessions",
  "description": "Read active firewall sessions, optionally filtered. Read-only.",
  "args": {
    "filter": {
      "type": "object",
      "description": "Optional. Keys: src_ip, dst_ip, proto, dst_port",
      "required": false
    },
    "limit": {"type":"integer","default":100,"max":1000}
  },
  "returns": "array of session objects",
  "destructive": false,
  "rate_limit_per_min": 60
}
```

Set `destructive: true` for anything that writes. Your agent loop reads that
flag and gates the call behind a confirmation step.

## Tool quality bar (test each one)

For every tool you wire in, before you trust it:

1. **Happy path**: it returns sensible data on a normal query.
2. **Empty path**: it returns `[]` not `null` not an error when there's no
   data.
3. **Error path**: it returns a structured error object Vio can read, not a
   stack trace string.
4. **Timeout**: it has one, and it's < 30 s.
5. **Logged**: every call writes `{tool, args_hash, latency_ms, ok}` to
   `/opt/vio/logs/tools.log` for auditability.

## Anti-pattern to avoid

❌ Giving Vio one giant "do_anything" tool that takes a shell command. This
   guts the safety model. Build narrow, well-typed tools instead.

❌ Letting Vio decide what's destructive at run time. The tool definition
   carries `destructive: true|false`. Never the model.

❌ Wiring 30 tools at once. Each new tool is a new failure mode. Add one,
   verify Vio uses it correctly across 10 turns, then add the next.
