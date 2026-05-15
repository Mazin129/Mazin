# Vio — Long-term Memory (Node.js)

> Load this skill whenever you need to **recall** what you know about
> Mazin (network, family, work, preferences) or **store** something new
> that should survive across sessions.

---

## Memory file location

```
/data/.openclaw/workspace/vio-memory/memory.json
```

Node.js 24 is always available. Use it for all memory operations — no
other tools required.

---

## Read memory before answering

At the start of every non-trivial turn, check what's relevant:

### Read all active facts

```bash
node -e "
const fs=require('fs');
const p='/data/.openclaw/workspace/vio-memory/memory.json';
try {
  const m=JSON.parse(fs.readFileSync(p,'utf8'));
  const active=m.facts.filter(f=>!f.supersededBy);
  console.log(JSON.stringify(active,null,2));
} catch(e) { console.log('memory empty'); }
"
```

### Read facts filtered by tag

```bash
node -e "
const fs=require('fs');
const p='/data/.openclaw/workspace/vio-memory/memory.json';
try {
  const m=JSON.parse(fs.readFileSync(p,'utf8'));
  m.facts
    .filter(f=>!f.supersededBy && f.tags.includes('TAG'))
    .forEach(f=>console.log(f.subject, '|', f.predicate, '|', f.object));
} catch(e) { console.log('nothing found'); }
"
```

Replace `TAG` with one of: `network`, `family`, `study`, `work`,
`preference`, `incident`.

### Read open follow-ups

```bash
node -e "
const fs=require('fs');
const p='/data/.openclaw/workspace/vio-memory/memory.json';
try {
  const m=JSON.parse(fs.readFileSync(p,'utf8'));
  const open=m.followups.filter(f=>!f.doneAt);
  open.forEach(f=>console.log('[P'+f.priority+']',f.description,'due:',f.dueAt||'anytime'));
} catch(e) { console.log('no followups'); }
"
```

---

## Write a new fact

Use this when Mazin states a new fact, makes a decision, or expresses a
preference. Replace the SUBJECT/PREDICATE/OBJECT/TAGS values:

```bash
node -e "
const fs=require('fs');
const p='/data/.openclaw/workspace/vio-memory/memory.json';
let m={facts:[],followups:[]};
try{m=JSON.parse(fs.readFileSync(p,'utf8'))}catch(e){}
const fact={
  id: Date.now(),
  subject: 'SUBJECT',
  predicate: 'PREDICATE',
  object: 'OBJECT',
  tags: 'TAG1,TAG2',
  confidence: 0.9,
  created: new Date().toISOString()
};
m.facts.push(fact);
fs.writeFileSync(p,JSON.stringify(m,null,2));
console.log('saved:', fact.subject, fact.predicate, fact.object);
"
```

Good fact examples:

| subject | predicate | object | tags |
|---------|-----------|--------|------|
| `home_network` | `mgmt_subnet` | `192.168.100.0/24` | `network` |
| `Mazin` | `studies` | `NSE7 Enterprise FW` | `study,work` |
| `Mazin` | `prefers_language` | `ar` | `preference` |
| `bill:internet` | `due_day` | `12` | `family,bill` |

Bad facts — do NOT write these:
- Passwords, MFA codes, full card numbers, government IDs
- Exact home address
- Child medical diagnoses
- API keys or tokens

## Update (supersede) an existing fact

When a fact changes (e.g. subnet changes), supersede the old one:

```bash
node -e "
const fs=require('fs');
const p='/data/.openclaw/workspace/vio-memory/memory.json';
let m=JSON.parse(fs.readFileSync(p,'utf8'));
const newFact={
  id: Date.now(),
  subject: 'SUBJECT',
  predicate: 'PREDICATE',
  object: 'NEW_OBJECT',
  tags: 'TAGS',
  confidence: 0.9,
  created: new Date().toISOString()
};
const old=m.facts.find(f=>!f.supersededBy && f.subject==='SUBJECT' && f.predicate==='PREDICATE');
if(old) old.supersededBy=newFact.id;
m.facts.push(newFact);
fs.writeFileSync(p,JSON.stringify(m,null,2));
console.log('updated:', newFact.object);
"
```

## Add a follow-up

When Mazin says "remind me", "ask me later", or you make a promise:

```bash
node -e "
const fs=require('fs');
const p='/data/.openclaw/workspace/vio-memory/memory.json';
let m=JSON.parse(fs.readFileSync(p,'utf8'));
m.followups.push({
  id: Date.now(),
  description: 'DESCRIPTION',
  dueAt: 'YYYY-MM-DD',
  priority: 3,
  created: new Date().toISOString()
});
fs.writeFileSync(p,JSON.stringify(m,null,2));
console.log('followup added');
"
```

Priority: 1=urgent, 3=normal, 5=someday.

## Close a follow-up

```bash
node -e "
const fs=require('fs');
const p='/data/.openclaw/workspace/vio-memory/memory.json';
let m=JSON.parse(fs.readFileSync(p,'utf8'));
const f=m.followups.find(f=>f.id===FOLLOWUP_ID);
if(f) f.doneAt=new Date().toISOString();
fs.writeFileSync(p,JSON.stringify(m,null,2));
console.log('closed');
"
```

## Tag taxonomy

```
network                      home/work network facts
network,fortigate
study,fortinet,nse6
study,fortinet,nse7
study,weakness               topic missed twice
family
family,child:<name>
family,bill
family,appointment
family,travel
work
preference
incident
```

## Weekly hygiene (run every Friday)

```bash
node -e "
const fs=require('fs');
const p='/data/.openclaw/workspace/vio-memory/memory.json';
let m=JSON.parse(fs.readFileSync(p,'utf8'));
const cutoff=new Date(Date.now()-30*24*60*60*1000).toISOString();
// Remove superseded facts older than 30 days
m.facts=m.facts.filter(f=>!(f.supersededBy && f.created<cutoff));
// Remove completed followups older than 30 days
m.followups=m.followups.filter(f=>!(f.doneAt && f.doneAt<cutoff));
fs.writeFileSync(p,JSON.stringify(m,null,2));
console.log('cleaned. facts:',m.facts.length,'followups:',m.followups.length);
"
```
