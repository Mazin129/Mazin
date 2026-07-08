# Vio starter knowledge base

Clean, well-written knowledge for teaching Vio — plain prose facts (not command
fragments), so Vio gives clean definitions, correct causal reasoning, and a rich
knowledge graph. Each file is one domain:

| File | Domain |
|---|---|
| `networking.md` | VLANs, OSI, TCP/IP, routing (OSPF/BGP), NAT/DNS/DHCP, firewalls, congestion |
| `security.md` | CIA triad, crypto, malware, attacks, vulnerabilities, defenses |
| `computing.md` | hardware, CPU/RAM, operating systems, Linux, the internet, cloud |
| `programming.md` | languages, variables, functions, algorithms, Git, AI basics |
| `science.md` | physics, chemistry, biology |
| `world.md` | geography, astronomy, the human body |

## Teach it all to Vio (one command)

```bash
cd AI-Foundation-Model-Design/mind
python teach_datasets.py
```

That loads every `.md` here into your Vio (~450 clean facts). It ADDS to what Vio
already knows and de-duplicates on re-run. To start fresh first, use **Forget
everything** in the browser (📚 Memory), or delete `knowledge.json` and `graph.json`.

## Or teach one file in the browser

Click **📄 Teach a file** and pick any of these `.md` files.

## After loading, try

```
what is a firewall?
what is encryption?
what causes packet loss?
what happens if a computer overheats?
what is the difference between a hard disk and an ssd?
what is dna?
```

## Style guide (if you write your own)

Vio learns best from clean prose:
- **Definitions:** `A VLAN is a virtual LAN that segments a network.` → gives good
  "what is X" answers and an `is_a` graph edge.
- **Causes:** `Congestion causes packet loss.` → feeds the causal graph and the world
  model (`what happens if congestion occurs?`).
- One idea per sentence. Avoid command syntax, tables, and cross-references — those
  are what make a raw CLI manual answer poorly.
