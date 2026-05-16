---
name: vio-designs
description: Handle Mazin's work network design documents (HLD/LLD PDFs, Visio/drawio diagrams). When Mazin uploads a design doc, extract structured facts (devices, subnets, VLANs, policies, services) and store them as ontology entities tagged with the project. The source document NEVER stays on the server — only extracted facts. Use ontology skill for structured storage. Load when Mazin uploads a PDF/image of a design, or asks about a past customer project.
---

# Vio Designs — Work Project Knowledge

Vio's long-term memory for Mazin's customer network designs. Source documents
stay on Mazin's PC. Only **extracted, structured facts** are kept here, so the
designs themselves never leak.

## Privacy rules (non-negotiable)

- **Never copy** the original PDF/image to the VPS storage beyond temporary
  processing. Delete after extraction.
- **Never store customer real names** unless Mazin explicitly authorizes —
  use placeholders like `customer-A`, `bank-1`, `ministry-2`.
- **Never store credentials, license keys, admin passwords, or SNMP
  community strings** even if they appear in the doc.
- **Public IPs / WAN addresses** — store only if Mazin says OK. Otherwise
  store as `wan-public-1`, `isp-1-ip` placeholders.

## Workflow when Mazin uploads a new design

### 1. Identify and confirm

> Mazin, I see an HLD/LLD document. Which project is this for?
> Give me a short project key (e.g. `bank-A`, `gov-1`, `home-lab`).

Wait for the project key before extracting.

### 2. Extract source content

| Source | Tool | Command |
|--------|------|---------|
| PDF | `pdftotext` | `pdftotext input.pdf -` |
| Image (Visio/drawio export) | Vision (Claude) | Read the diagram directly |
| Markdown / text | Direct read | — |

If `pdftotext` is missing, install: `brew install poppler` (inside container).

### 3. Create the Project entity (via ontology skill)

```bash
python3 /data/.openclaw/skills/ontology/scripts/ontology.py create \
  --type Project \
  --props '{"name":"<project-key>","status":"active","domain":"network","sensitivity":"customer"}'
```

Save the returned `id` — every entity below links to it.

### 4. Extract entities (one entity per network element)

| Network element | Ontology type | Properties to capture |
|-----------------|---------------|----------------------|
| FortiGate / Firewall | `Device` | name, vendor=Fortinet, model, role=firewall, mgmt_ip, ha_role |
| FortiSwitch | `Device` | name, model, role=switch, mgmt_ip, uplink |
| FortiAP | `Device` | name, model, role=ap, ssid_list, controller |
| Server | `Device` | name, role=server, os, mgmt_ip |
| VLAN / Subnet | `Subnet` | vlan_id, cidr, purpose, gateway |
| Service (DNS, NTP, SMTP) | `Service` | service_type, address, used_by |
| Policy | `Policy` | name, src_zone, dst_zone, src_addr, dst_addr, action |
| WAN link | `Service` | service_type=wan, isp, bandwidth |
| Site / Location | `Location` | name, address (only if Mazin says OK) |

For each entity, create then relate to project:

```bash
ID=$(python3 .../ontology.py create --type Device --props '{...}' | jq -r '.id')
python3 .../ontology.py relate --from "$ID" --rel "belongs_to" --to "<project-id>"
```

### 5. Summarize and confirm

After extraction, show Mazin a structured summary:

```
Project: customer-A
Devices: 2x FortiGate 100F (HA), 4x FortiSwitch 248D, 8x FortiAP 231F
Subnets: 4 VLANs — Mgmt 10.0.0.0/24, Users 10.10.0.0/22, IoT 10.20.0.0/24, Guest 10.30.0.0/24
Policies: 18 — captured
Services: 2 ISPs (Etisalat + STC), AD/DNS server, Syslog
```

Ask Mazin to confirm or correct before committing.

## Workflow when Mazin asks about a past project

### IMPORTANT: always cd to the workspace first

The ontology script enforces path safety — it rejects paths outside the
current working directory. **Always `cd /data/.openclaw/workspace`** before
running any ontology query, and use the relative graph path
`memory/ontology/graph.jsonl`.

### Lookup commands

```bash
cd /data/.openclaw/workspace

# All projects
python3 /data/.openclaw/skills/ontology/scripts/ontology.py list \
  --type Project --graph memory/ontology/graph.jsonl

# All entities linked to a project (find project id first, then query)
PROJ_ID=$(python3 /data/.openclaw/skills/ontology/scripts/ontology.py query \
  --type Project --where '{"name":"EALZ"}' --graph memory/ontology/graph.jsonl \
  | python3 -c "import json,sys; print(json.load(sys.stdin)[0]['id'])")

python3 /data/.openclaw/skills/ontology/scripts/ontology.py related \
  --id "$PROJ_ID" --rel belongs_to --dir incoming \
  --graph memory/ontology/graph.jsonl

# All FortiGate devices across all projects
python3 /data/.openclaw/skills/ontology/scripts/ontology.py query \
  --type Device --where '{"vendor":"Fortinet"}' \
  --graph memory/ontology/graph.jsonl
```

### Useful queries Mazin will ask

| Question | Query |
|----------|-------|
| "What FortiGate did I use for customer-A?" | Device where role=firewall, project=customer-A |
| "Which projects used FortiAP 231F?" | Device where model=FortiAP-231F |
| "What's the mgmt subnet for bank-1?" | Subnet where project=bank-1, purpose=management |
| "How many sites did I do this year?" | Project where status=active, count |

## Drawio / Visio diagrams

If Mazin sends a `.drawio` XML, you can grep for shapes:

```bash
grep -oP 'value="[^"]+"' design.drawio | sort -u
```

This pulls out every label — devices, subnets, links. Then build entities from there.

For exported PNGs/SVGs, use vision (Claude can see the diagram and read labels).

## Source document handling

After extraction:

1. Confirm with Mazin: "I've extracted N entities. Should I delete the source?"
2. If yes: `rm /data/.openclaw/media/inbound/<file>` — confirm deletion.
3. If no: tell Mazin where the file is and the deletion is on him.

## Memory hygiene

When a project ends (Mazin says "we finished customer-A"):

```bash
python3 .../ontology.py update --id <project-id> --props '{"status":"completed","completed":"<date>"}'
```

Keep entities for reference, mark project complete. Don't delete — Mazin may need to reference past work for new ones.
