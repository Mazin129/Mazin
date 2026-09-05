"""
Vio — browser chat (modern, interactive).  Run this, open the URL, and talk to Vio
in your browser (English + العربية). No Ollama, no external model — everything runs
on the local verified reasoning engine + memory + your own trained language model.

    python web.py
    → open http://localhost:8100

Features exposed here:
  • Chat with verified reasoning (math/logic/units/…), retrieval, and generation.
  • 🧠 Deep-solve mode: Vio decomposes hard questions, self-searches, and streams its
    thinking steps live (Server-Sent Events).
  • 🎓 Train: (re)train Vio's own language model on everything it knows — optionally
    folding in the current chat — and see real training stats.
  • 🧩 Skills: teach Vio new reflexes from the browser (pure data, no code, no risk).
  • 📄 Teach from a .txt/.md/.pdf file.

Standard library only (plus the reasoner's sympy/sklearn). Data lives in
mind_memory.json / knowledge.json / skills.json next to this file.
"""

import json
import os
import subprocess
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from reasoner import Mind, KB_FILE
from talk import reply
from agent import SolveAgent
from dashboard_page import DASHBOARD

HERE = os.path.dirname(os.path.abspath(__file__))
PORT = int(os.environ.get("MIND_PORT", "8100"))
MIND = Mind()
_last_activity = time.time()          # for idle-time consolidation (§14 "sleep")
AGENT = SolveAgent(MIND)

# ── one-click "train on ALL data" ───────────────────────────────────────────
# The GUI kicks off the full from-scratch pipeline (train_all.py) as a
# background process so the browser never blocks: the click returns instantly
# and the page polls /api/train_all/status to show live progress. Only one run
# at a time; output is streamed to train_all.log which the status endpoint tails.
TRAIN_LOG = os.path.join(HERE, "train_all.log")
TRAINER = {"proc": None, "started": 0.0, "cmd": ""}


def _trainer_running():
    p = TRAINER["proc"]
    return p is not None and p.poll() is None


def start_train_all(preset="gpu", steps=None):
    """Launch train_all.py in the background. Returns immediately."""
    if _trainer_running():
        return {"ok": False, "running": True,
                "message": "Training is already running — watch the progress below."}
    args = [sys.executable, os.path.join(HERE, "train_all.py"), "--preset", str(preset)]
    if steps:
        args += ["--steps", str(int(steps))]
    try:
        logf = open(TRAIN_LOG, "w", encoding="utf-8")      # fresh log each run
        proc = subprocess.Popen(args, cwd=HERE, stdout=logf, stderr=subprocess.STDOUT,
                                env={**os.environ, "PYTHONUNBUFFERED": "1"})
        logf.close()                                        # child keeps its own handle
    except Exception as e:                                   # pragma: no cover
        return {"ok": False, "running": False,
                "message": f"Could not start training: {e}"}
    TRAINER.update(proc=proc, started=time.time(), cmd=" ".join(args))
    return {"ok": True, "running": True, "message": "Training started on all your data."}


def train_all_status(tail_lines=60):
    running = _trainer_running()
    tail = ""
    try:
        with open(TRAIN_LOG, encoding="utf-8", errors="replace") as f:
            tail = "".join(f.readlines()[-tail_lines:])
    except Exception:
        pass
    p = TRAINER["proc"]
    rc = None if (running or p is None) else p.returncode
    return {"running": running, "returncode": rc, "tail": tail,
            "elapsed": int(time.time() - TRAINER["started"]) if TRAINER["started"] else 0}

PAGE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Vio</title>
<style>
 :root{
   --bg:#0a0d13; --panel:#111722; --panel2:#171f2d; --line:#232d40;
   --txt:#e9eef6; --dim:#8b98ad; --accent:#5b8cff; --accent2:#8b6dff;
   --user:linear-gradient(135deg,#3b6ef5,#7b53ff); --bot:#141b28;
   --ok:#3dd882; --warn:#f4b740; --bad:#f0687f; --radius:18px;
   --side:#0d121c; --shadow:0 8px 30px rgba(0,0,0,.35);
 }
 @media (prefers-color-scheme:light){:root:not([data-theme=dark]){
   --bg:#f6f8fc;--panel:#ffffff;--panel2:#f1f4fa;--line:#e2e8f2;--txt:#141a24;--dim:#5c6675;
   --bot:#ffffff;--side:#f0f3f9;--shadow:0 8px 30px rgba(20,30,60,.10);}}
 :root[data-theme=light]{--bg:#f6f8fc;--panel:#fff;--panel2:#f1f4fa;--line:#e2e8f2;--txt:#141a24;
   --dim:#5c6675;--bot:#fff;--side:#f0f3f9;--shadow:0 8px 30px rgba(20,30,60,.10);}
 *{box-sizing:border-box}
 html,body{height:100%;margin:0}
 body{font-family:'Inter','Segoe UI',system-ui,-apple-system,Roboto,Arial,sans-serif;
      background:var(--bg);color:var(--txt);font-size:14.5px}
 .grow{flex:1}
 .app{display:grid;grid-template-columns:262px 1fr;height:100vh;overflow:hidden}
 /* ---- sidebar ---- */
 .side{background:var(--side);border-right:1px solid var(--line);display:flex;flex-direction:column;
       padding:14px 12px;gap:14px;z-index:30;transition:transform .22s}
 .brandrow{display:flex;align-items:center;gap:11px}
 .logo{width:38px;height:38px;border-radius:12px;display:grid;place-items:center;font-size:20px;
       background:var(--user);box-shadow:0 4px 20px rgba(91,110,245,.5)}
 .brand{font-weight:750;font-size:17px;letter-spacing:.2px}
 .brand small{display:block;font-weight:400;font-size:11px;color:var(--dim);letter-spacing:.3px}
 .newchat{margin-top:2px;width:100%;border:1px solid var(--line);background:var(--panel);color:var(--txt);
       border-radius:12px;padding:11px;font-size:14px;font-weight:600;cursor:pointer;transition:.15s}
 .newchat:hover{border-color:var(--accent);background:var(--panel2)}
 .nav{display:flex;flex-direction:column;gap:3px}
 .navbtn{display:flex;align-items:center;gap:11px;text-decoration:none;text-align:left;
       border:0;background:transparent;color:var(--dim);border-radius:10px;padding:10px 11px;
       font-size:14px;cursor:pointer;transition:.13s;font-family:inherit}
 .navbtn span{font-size:16px;width:20px;text-align:center}
 .navbtn:hover{background:var(--panel2);color:var(--txt)}
 .side-foot{margin-top:auto;display:flex;flex-direction:column;gap:9px}
 .brain-card{border:1px solid var(--line);border-radius:12px;padding:9px 11px;font-size:12px;color:var(--dim);
       background:var(--panel);font-family:ui-monospace,Consolas,monospace}
 .brain-card.live{border-color:color-mix(in srgb,var(--ok) 50%,var(--line));color:var(--ok);
       box-shadow:0 0 0 1px color-mix(in srgb,var(--ok) 25%,transparent)}
 .brain-card b{color:inherit}
 .stat{font-size:11.5px;color:var(--dim);padding:0 3px}
 .stat b{color:var(--txt)}
 .theme{position:absolute;top:16px;right:14px;border:1px solid var(--line);background:var(--panel);
       color:var(--txt);width:32px;height:32px;border-radius:9px;cursor:pointer;font-size:14px}
 /* ---- chat area ---- */
 .chatwrap{display:flex;flex-direction:column;min-width:0;height:100vh;position:relative;
       background:radial-gradient(1100px 600px at 85% -15%,rgba(124,100,255,.10),transparent 60%),var(--bg)}
 .topbar{display:none;align-items:center;gap:10px;padding:10px 14px;border-bottom:1px solid var(--line)}
 .ham{border:1px solid var(--line);background:var(--panel);color:var(--txt);border-radius:9px;
       width:36px;height:36px;font-size:16px;cursor:pointer}
 .topname{font-weight:700}
 .brain-mini{font-size:11px;color:var(--dim);font-family:ui-monospace,Consolas,monospace}
 #log{flex:1;overflow-y:auto;padding:26px 18px;display:flex;flex-direction:column;gap:20px;
       max-width:820px;width:100%;margin:0 auto;scroll-behavior:smooth}
 .row{display:flex;gap:12px;align-items:flex-start;animation:rise .32s ease}
 @keyframes rise{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
 .row.me{flex-direction:row-reverse}
 .av{width:32px;height:32px;border-radius:10px;flex:none;display:grid;place-items:center;font-size:16px}
 .av.bot{background:linear-gradient(135deg,#1c2536,#141b28);border:1px solid var(--line)}
 .av.me{background:var(--user)}
 .bubble{padding:13px 16px;border-radius:var(--radius);line-height:1.55;white-space:pre-wrap;
         word-wrap:break-word;overflow-wrap:anywhere;font-size:14.5px;max-width:100%}
 .row.me{align-self:flex-end;max-width:82%}
 .row.bot{align-self:flex-start;max-width:100%;width:100%}
 .row.me .bubble{background:var(--user);color:#fff;border-bottom-right-radius:6px;box-shadow:var(--shadow)}
 .row.bot .bubble{background:var(--bot);border:1px solid var(--line);border-bottom-left-radius:6px;box-shadow:var(--shadow)}
 .bubble.rtl{direction:rtl;text-align:right}
 .row.bot .bubble{white-space:normal}             /* rendered markdown flows as blocks */
 .bubble code{background:rgba(130,150,190,.18);padding:1px 6px;border-radius:6px;font-family:ui-monospace,Consolas,monospace;font-size:13px}
 .bubble pre{position:relative;background:#0a0d14;border:1px solid var(--line);border-radius:10px;padding:12px 12px 10px;overflow-x:auto;margin:8px 0}
 .bubble pre code{background:none;padding:0;font-size:12.5px;line-height:1.5;color:#dbe4f3}  /* always light: pre bg is always dark */
 .bubble pre .cp{position:absolute;top:6px;right:6px;font-size:11px;color:var(--dim);background:var(--panel2);
      border:1px solid var(--line);border-radius:6px;padding:2px 8px;cursor:pointer;opacity:.7}
 .bubble pre .cp:hover{opacity:1;border-color:var(--accent)}
 .bubble h4{font-size:14.5px;margin:12px 0 5px;color:var(--txt);font-weight:700}
 .bubble h4:first-child{margin-top:2px}
 .bubble ol,.bubble ul{margin:5px 0;padding-left:20px}
 .bubble li{margin:3px 0;line-height:1.5}
 .bubble .ln{margin:4px 0;line-height:1.55}
 .bubble .ln:empty{margin:0}
 .bubble .lbl{margin:8px 0 4px;line-height:1.55}
 .bubble .lbl b{color:var(--accent2)}
 .bubble .lbl:first-child{margin-top:0}
 .meta{font-size:11px;color:var(--dim);margin-top:6px;display:flex;gap:8px;align-items:center;flex-wrap:wrap}
 .prov{color:var(--accent2);font-weight:600}
 .ok{color:var(--ok)}.no{color:var(--warn)}
 .copy{cursor:pointer;opacity:.6}.copy:hover{opacity:1}
 .fb{cursor:pointer;opacity:.55;font-size:12px}.fb:hover{opacity:1}
 .think{border-left:2px solid var(--accent);padding:6px 0 6px 12px;margin:2px 0 8px;font-size:12.5px;color:var(--dim);
        display:flex;flex-direction:column;gap:3px}
 .think .step{opacity:0;animation:fade .3s forwards}
 @keyframes fade{to{opacity:1}}
 .dots span{display:inline-block;width:6px;height:6px;margin:0 1px;border-radius:50%;background:var(--dim);
            animation:blink 1.2s infinite both}
 .dots span:nth-child(2){animation-delay:.2s}.dots span:nth-child(3){animation-delay:.4s}
 @keyframes blink{0%,80%,100%{opacity:.2}40%{opacity:1}}
 /* ---- empty / welcome state ---- */
 .empty{margin:auto;text-align:center;max-width:640px;padding:20px;animation:rise .4s ease}
 .hero-logo{width:60px;height:60px;border-radius:18px;display:grid;place-items:center;font-size:30px;
       margin:0 auto 18px;background:var(--user);box-shadow:0 10px 40px rgba(91,110,245,.45)}
 .empty h1{font-size:26px;margin:0 0 8px;letter-spacing:-.01em}
 .empty p{color:var(--dim);font-size:14.5px;margin:0 auto 26px;max-width:460px;line-height:1.55}
 .cards{display:grid;grid-template-columns:1fr 1fr;gap:12px;text-align:left}
 .qcard{border:1px solid var(--line);background:var(--panel);border-radius:14px;padding:14px 15px;
       cursor:pointer;transition:.15s}
 .qcard:hover{border-color:var(--accent);transform:translateY(-2px);box-shadow:var(--shadow)}
 .qcard .qi{font-size:18px;margin-bottom:7px}
 .qcard .qt{font-size:13.5px;font-weight:600;line-height:1.4}
 .qcard .qs{font-size:12px;color:var(--dim);margin-top:3px}
 /* ---- composer ---- */
 .composer-wrap{padding:6px 18px 16px;max-width:820px;width:100%;margin:0 auto}
 .composer{border:1px solid var(--line);background:var(--panel);border-radius:22px;padding:7px 7px 7px 12px;
           display:flex;align-items:flex-end;gap:8px;box-shadow:var(--shadow);transition:border-color .15s}
 .composer:focus-within{border-color:var(--accent)}
 .attach{border:0;background:transparent;color:var(--dim);font-size:18px;cursor:pointer;padding:8px 4px;flex:none;
         align-self:flex-end;line-height:1}
 .attach:hover{color:var(--accent)}
 textarea#inp{flex:1;resize:none;border:0;background:transparent;color:var(--txt);font-size:15px;
              padding:9px 2px;max-height:180px;font-family:inherit;outline:none;line-height:1.5}
 .toggle{flex:none;align-self:flex-end;display:grid;place-items:center;width:38px;height:38px;font-size:16px;
         color:var(--dim);cursor:pointer;user-select:none;border:1px solid var(--line);border-radius:11px;transition:.15s}
 .toggle.on{color:#fff;background:var(--user);border-color:transparent;box-shadow:0 3px 12px rgba(91,110,245,.4)}
 .toggle:hover{border-color:var(--accent)}
 .send{background:var(--user);border:0;color:#fff;width:38px;height:38px;border-radius:11px;font-size:17px;
       cursor:pointer;flex:none;align-self:flex-end;display:grid;place-items:center;transition:.15s}
 .send:hover{transform:scale(1.07)}
 .hint{text-align:center;font-size:11.5px;color:var(--dim);margin-top:9px}
 .send:disabled{opacity:.5;cursor:default;transform:none}
 #log::-webkit-scrollbar{width:10px}
 #log::-webkit-scrollbar-thumb{background:var(--line);border-radius:8px;border:3px solid transparent;background-clip:padding-box}
 .backdrop{position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:25;display:none}
 .backdrop.on{display:block}
 /* ---- responsive: sidebar becomes an off-canvas drawer ---- */
 @media (max-width:820px){
   .app{grid-template-columns:1fr}
   .side{position:fixed;left:0;top:0;bottom:0;width:262px;transform:translateX(-100%);box-shadow:var(--shadow)}
   .side.open{transform:none}
   .topbar{display:flex}
   .theme{position:static}
   #log,.composer-wrap{padding-left:14px;padding-right:14px}
   .cards{grid-template-columns:1fr}
 }
 /* modal */
 .modal{position:fixed;inset:0;background:rgba(4,6,12,.6);display:none;place-items:center;z-index:20;backdrop-filter:blur(3px)}
 .modal.show{display:grid}
 .card{background:var(--panel);border:1px solid var(--line);border-radius:18px;max-width:520px;width:92%;
       max-height:86vh;overflow-y:auto;padding:20px}
 .card h3{margin:0 0 4px}.card p.sub{margin:0 0 14px;color:var(--dim);font-size:13px}
 .card label{font-size:12px;color:var(--dim);display:block;margin:10px 0 4px}
 .card input,.card textarea{width:100%;background:var(--panel2);border:1px solid var(--line);border-radius:10px;
       color:var(--txt);padding:9px 11px;font-size:14px;font-family:inherit}
 .card textarea{resize:vertical;min-height:52px}
 .btn{background:var(--user);border:0;color:#fff;border-radius:10px;padding:9px 16px;font-size:14px;cursor:pointer}
 .btn.ghost{background:var(--panel2);border:1px solid var(--line);color:var(--txt)}
 .btn.danger{background:#7a1f1f}
 .skill{border:1px solid var(--line);border-radius:12px;padding:10px 12px;margin:8px 0;background:var(--panel2)}
 .skill b{font-size:13.5px}.skill .t{font-size:12px;color:var(--dim);margin-top:3px}
 .rowbtns{display:flex;gap:8px;justify-content:flex-end;margin-top:16px}
 .close{float:right;cursor:pointer;color:var(--dim);font-size:20px;line-height:1}
 .memlist{font-size:13px;color:var(--dim);line-height:1.6}
</style></head><body>
<div class="app">
 <aside class="side" id="side">
   <div class="side-top">
     <div class="brandrow">
       <div class="logo">🧠</div>
       <div class="brand"><span id="who">Vio</span><small>local · verified · yours</small></div>
     </div>
     <button class="newchat" onclick="newChat()">＋ New chat</button>
   </div>
   <nav class="nav">
     <button class="navbtn" onclick="openSkills()"><span>🧩</span> Skills</button>
     <button class="navbtn" onclick="train(false)"><span>🎓</span> Train model</button>
     <button class="navbtn" onclick="trainAll()"><span>🚀</span> Train on all data</button>
     <button class="navbtn" onclick="selfImprove()"><span>🔁</span> Self-improve</button>
     <button class="navbtn" onclick="openMem()"><span>📚</span> Memory</button>
     <a class="navbtn" href="/dashboard"><span>📊</span> Brain dashboard</a>
     <button class="navbtn" onclick="document.getElementById('file').click()"><span>📄</span> Teach a file</button>
     <button class="navbtn" onclick="teachFolder()"><span>📁</span> Teach a folder</button>
     <input type="file" id="file" accept=".txt,.md,.text,.csv,.tsv,.log,.pdf,.drawio,.xml,.vsdx,.cfg,.conf,.png,.jpg,.jpeg,.gif,.bmp,.tiff,.webp" hidden onchange="upload()">
   </nav>
   <div class="side-foot">
     <div class="brain-card" id="brain" title="reasoning cortex">🧠 …</div>
     <div class="stat" id="status">…</div>
     <button class="theme" onclick="toggleTheme()" id="themeBtn" title="Toggle light/dark">🌙</button>
   </div>
 </aside>

 <div class="chatwrap">
   <div class="topbar">
     <button class="ham" onclick="document.getElementById('side').classList.toggle('open')">☰</button>
     <div class="topname">Vio</div>
     <span class="grow"></span>
     <div class="brain-mini" id="brainMini"></div>
   </div>
   <div id="log">
     <div class="empty" id="empty">
       <div class="hero-logo">🧠</div>
       <h1>How can I help, <span id="heroName">Mazin</span>?</h1>
       <p>Ask about your stack, reason through a problem, or teach me something. I run on your machine and tell you how sure I am.</p>
       <div class="cards" id="cards"></div>
     </div>
   </div>
   <div class="composer-wrap">
     <div class="composer">
       <button class="attach" onclick="document.getElementById('file').click()" title="Teach a file">📎</button>
       <textarea id="inp" rows="1" placeholder="Message Vio…  (English / العربية)" autofocus></textarea>
       <div class="toggle on" id="deepT" onclick="toggleDeep()" title="Deep solve: break hard questions apart and show the thinking">🧠</div>
       <button class="send" id="sendBtn" onclick="send()">➤</button>
     </div>
     <div class="hint">Vio verifies math &amp; cites your data · answers show how sure it is · everything stays local</div>
   </div>
 </div>
</div>

<div class="modal" id="skillsM">
 <div class="card">
  <span class="close" onclick="closeM('skillsM')">×</span>
  <h3>🧩 Skills</h3>
  <p class="sub">Teach Vio a reflex. Use <code>{name}</code> style slots to capture words.
     Example trigger <code>greet {name}</code>, reply <code>Hello {name}!</code></p>
  <label>Skill name</label><input id="sk_name" placeholder="greet">
  <label>Trigger (what you'll say)</label><input id="sk_trig" placeholder="greet {name}">
  <label>Reply (what Vio answers)</label><textarea id="sk_reply" placeholder="Hello {name}! 👋"></textarea>
  <div class="rowbtns"><button class="btn ghost" onclick="closeM('skillsM')">Close</button>
    <button class="btn" onclick="addSkill()">Add skill</button></div>
  <div id="skillList"></div>
 </div>
</div>

<div class="modal" id="memM">
 <div class="card">
  <span class="close" onclick="closeM('memM')">×</span>
  <h3>📚 What Vio knows</h3>
  <p class="sub">Everything is local and inspectable.</p>
  <div id="memBody" class="memlist"></div>
  <div class="rowbtns">
    <button class="btn ghost" onclick="exportPack()">📦 Export knowledge pack</button>
    <button class="btn ghost" onclick="document.getElementById('packfile').click()">📥 Import pack</button>
    <input type="file" id="packfile" accept=".json" style="display:none" onchange="importPack()">
    <button class="btn ghost" onclick="train(true)">🎓 Train on this chat too</button>
    <button class="btn danger" onclick="forget()">Forget everything</button></div>
 </div>
</div>

<script>
const log=document.getElementById('log'), inp=document.getElementById('inp'),
      statusEl=document.getElementById('status'), sendBtn=document.getElementById('sendBtn');
let deep=true, busy=false;
const isAr=t=>/[؀-ۿ]/.test(t);
const esc=s=>s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
function fmt(t){ // safe markdown: code fences, headings, lists, labels, bold, inline code
 const blocks=[];
 t=t.replace(/```(\w*)\r?\n?([\s\S]*?)```/g,(m,lang,code)=>{
   blocks.push(code.replace(/\s+$/,''));return '\uE000'+(blocks.length-1)+'\uE000';});
 const inl=s=>esc(s).replace(/\*\*([^*]+)\*\*/g,'<b>$1</b>').replace(/`([^`]+)`/g,'<code>$1</code>');
 let html='',list=null;
 const shut=()=>{if(list){html+='</'+list+'>';list=null;}};
 for(const line of t.split('\n')){
   let m=line.match(/^\uE000(\d+)\uE000\s*$/);
   if(m){shut();html+='<pre><span class="cp" onclick="cpCode(this)">copy</span><code>'+esc(blocks[+m[1]])+'</code></pre>';continue;}
   if(m=line.match(/^\s*#{1,6}\s+(.*)/)){shut();html+='<h4>'+inl(m[1])+'</h4>';continue;}
   if(m=line.match(/^\s*\d+[.)]\s+(.*)/)){if(list!=='ol'){shut();html+='<ol>';list='ol';}html+='<li>'+inl(m[1])+'</li>';continue;}
   if(m=line.match(/^\s*[-*•]\s+(.*)/)){if(list!=='ul'){shut();html+='<ul>';list='ul';}html+='<li>'+inl(m[1])+'</li>';continue;}
   if(m=line.match(/^\s*(Understanding|Logic|Approach|Answer|Note|Root cause|Probability|Summary|Recommendation)\s*:\s*(.*)/i)){
     shut();html+='<div class="lbl"><b>'+esc(m[1])+':</b> '+inl(m[2])+'</div>';continue;}
   shut();html+='<div class="ln">'+inl(line)+'</div>';
 }
 shut();return html;
}
function cpCode(el){navigator.clipboard.writeText(el.parentElement.querySelector('code').textContent);
 el.textContent='copied';setTimeout(()=>el.textContent='copy',1200);}
const CARDS=[
 {i:'🛡️',t:'FortiGate',s:'What is a VDOM and when do I use one?',q:'What is a VDOM and when do I use one?'},
 {i:'☁️',t:'AWS security',s:'Security group vs network ACL?',q:'What is the difference between an AWS security group and a network ACL?'},
 {i:'🔒',t:'IPsec VPN',s:'IKE phase 1 vs phase 2',q:'Explain the difference between IKE phase 1 and phase 2.'},
 {i:'🧮',t:'Exact math',s:'solve x² − 5x + 6 = 0',q:'solve x^2 - 5x + 6 = 0'},
];
function renderChips(){const el=document.getElementById('cards');if(!el)return;
 el.innerHTML=CARDS.map((c,i)=>`<div class="qcard" onclick="askCard(${i})">
   <div class="qi">${c.i}</div><div class="qt">${esc(c.t)}</div><div class="qs">${esc(c.s)}</div></div>`).join('');}
function askCard(i){inp.value=CARDS[i].q;send();}
function chip(e){inp.value=e.textContent;inp.focus();autosize()}
function hideEmpty(){const e=document.getElementById('empty');if(e)e.style.display='none';}
function newChat(){[...log.querySelectorAll('.row')].forEach(r=>r.remove());
 const e=document.getElementById('empty');if(e)e.style.display='';inp.focus();
 document.getElementById('side').classList.remove('open');}
function toggleTheme(){const r=document.documentElement;
 const cur=r.getAttribute('data-theme')|| (matchMedia('(prefers-color-scheme:dark)').matches?'dark':'light');
 const next=cur==='dark'?'light':'dark';r.setAttribute('data-theme',next);
 try{localStorage.setItem('vio-theme',next)}catch(e){}
 document.getElementById('themeBtn').textContent=next==='dark'?'🌙':'☀️';}
function bubble(who){hideEmpty();
 const row=document.createElement('div');row.className='row '+(who==='me'?'me':'bot');
 const av=document.createElement('div');av.className='av '+(who==='me'?'me':'bot');
 av.textContent=who==='me'?'🧑':'🧠';
 const b=document.createElement('div');b.className='bubble';
 row.appendChild(av);row.appendChild(b);log.appendChild(row);
 log.scrollTop=log.scrollHeight;return {row,b};
}
function addUser(t){const {b}=bubble('me');b.classList.toggle('rtl',isAr(t));b.textContent=t;}
function badge(j){const c=(j.confidence!=null)?' · '+Math.round(j.confidence*100)+'% sure':'';
 const ag=(j.agent&&j.agent!=='core')?' · <span class="prov">🧩 '+esc(j.agent)+' agent</span>':'';
 return (j.verified?'<span class="ok">✓ verified</span>':'<span class="no">… unverified</span>')+' · '+esc(j.how||'')+c+ag;}
function finalize(b,j){
 b.classList.toggle('rtl',isAr(j.answer));
 b.innerHTML=fmt(j.answer);
 const m=document.createElement('div');m.className='meta';
 const gradable=j.how&&!['feedback','welcome','reset'].includes(j.how);
 m.innerHTML=badge(j)+' <span class="copy" title="copy">⧉</span>'+
   (gradable?' <span class="fb" data-g="1" title="correct">👍</span><span class="fb" data-g="0" title="wrong">👎</span>':'');
 m.querySelector('.copy').onclick=()=>navigator.clipboard.writeText(j.answer);
 m.querySelectorAll('.fb').forEach(el=>el.onclick=async()=>{
   await fetch('/api/feedback',{method:'POST',headers:{'Content-Type':'application/json'},
     body:JSON.stringify({good:el.dataset.g==='1'})});
   el.parentElement.querySelectorAll('.fb').forEach(x=>x.style.opacity=.3);el.style.opacity=1;});
 b.appendChild(m);log.scrollTop=log.scrollHeight;
}
function autosize(){inp.style.height='auto';inp.style.height=Math.min(inp.scrollHeight,140)+'px'}
inp.addEventListener('input',autosize);
inp.addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send()}});
function toggleDeep(){deep=!deep;document.getElementById('deepT').classList.toggle('on',deep)}

async function send(){
 const raw=inp.value.trim();if(!raw||busy)return;
 // A multi-line paste is ONE message by default — a prompt like "Simulate five
 // experts:\nScientist\nEngineer…" must NOT be chopped into separate questions.
 // Only split into separate turns when it's clearly a BATCH of commands (every line
 // is teach:/remember:/skill:), which is the one case where line-by-line is wanted.
 const rawLines=raw.split(/\r?\n/).map(s=>s.trim()).filter(Boolean);
 const isCmd=l=>/^(teach|remember|skill)\s*:/i.test(l);
 const lines=(rawLines.length>1 && rawLines.every(isCmd))?rawLines:[raw];
 inp.value='';autosize();busy=true;sendBtn.disabled=true;
 for(const t of lines){
   addUser(t);
   const {b}=bubble('bot');
   if(deep){await solveStream(t,b)} else {await ask(t,b)}
 }
 busy=false;sendBtn.disabled=false;loadStatus();inp.focus();
}
async function ask(t,b){
 b.innerHTML='<span class="dots"><span></span><span></span><span></span></span>';
 try{
  const j=await(await fetch('/api/ask',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({message:t})})).json();
  finalize(b,j);
 }catch(e){b.textContent='⚠ '+e}
}
function solveStream(t,b){
 return new Promise(resolve=>{
  const think=document.createElement('div');think.className='think';
  b.appendChild(think);
  const dots=document.createElement('div');dots.className='dots';
  dots.innerHTML='<span></span><span></span><span></span>';b.appendChild(dots);
  const es=new EventSource('/api/solve?q='+encodeURIComponent(t));
  es.addEventListener('step',e=>{
    const s=document.createElement('div');s.className='step';s.textContent=e.data;
    think.appendChild(s);log.scrollTop=log.scrollHeight;
  });
  es.addEventListener('final',e=>{
    es.close();dots.remove();
    const j=JSON.parse(e.data);finalize(b,j);resolve();
  });
  es.onerror=()=>{es.close();dots.remove();if(!b.querySelector('.meta'))b.innerHTML+='<div class="meta no">connection interrupted</div>';resolve();};
 });
}
async function upload(){
 const f=document.getElementById('file').files[0];if(!f)return;
 addUser('📄 Teach from '+f.name);const {b}=bubble('bot');
 b.innerHTML='<span class="dots"><span></span><span></span><span></span></span>';
 let body;
 const asB64=async()=>{const buf=new Uint8Array(await f.arrayBuffer());let bin='';
   for(let i=0;i<buf.length;i++)bin+=String.fromCharCode(buf[i]);return btoa(bin);};
 if(/\.pdf$/i.test(f.name)){body=JSON.stringify({name:f.name,pdf_b64:await asB64()});}
 else if(/\.(vsdx|png|jpe?g|gif|bmp|tiff|webp)$/i.test(f.name)){         // Visio / images → binary
   body=JSON.stringify({name:f.name,file_b64:await asB64()});}
 else{body=JSON.stringify({name:f.name,text:await f.text()});}          // text, .drawio/.xml
 const j=await(await fetch('/api/learn',{method:'POST',headers:{'Content-Type':'application/json'},body})).json();
 finalize(b,{answer:j.answer,how:'learned from file',verified:true});
 document.getElementById('file').value='';loadStatus();
}
// Bulk-ingest a whole folder of documents (PDFs, configs, cheat sheets) by path.
async function teachFolder(){
 const path=prompt('Full path to a folder of documents\\n(PDFs, manuals, configs, cheat sheets):');
 if(!path)return;
 document.getElementById('side').classList.remove('open');
 const {b}=bubble('bot');b.innerHTML='<span class="dots"><span></span><span></span><span></span></span>';
 let j;
 try{j=await(await fetch('/api/learn_folder',{method:'POST',headers:{'Content-Type':'application/json'},
   body:JSON.stringify({path})})).json();}catch(e){finalize(b,{answer:'⚠️ Could not reach the server.',how:'error',verified:false});return;}
 let msg;
 if(!j.ok){msg='⚠️ '+(j.answer||('Nothing learned from '+path+'. Put PDFs/text/configs in it and retry.'));}
 else{
   msg='📁 Learned **'+j.passages+'** passages from **'+j.files+'** file(s).';
   if(j.per&&j.per.length)msg+='\\n\\n'+j.per.map(p=>'- '+p[0]+' — '+p[1]).join('\\n');
   if(j.skipped&&j.skipped.length)msg+='\\n\\n**Skipped:**\\n'+j.skipped.map(s=>'- '+s[0]+' — '+s[1]).join('\\n');
 }
 finalize(b,{answer:msg,how:'learned from folder',verified:!!j.ok});
 loadStatus();
}
async function loadStatus(){
 try{const j=await(await fetch('/api/status')).json();
  if(j.name){document.getElementById('who').textContent=j.name;document.title=j.name;}
  const hn=document.getElementById('heroName');if(hn&&j.name)hn.textContent=j.name;
  statusEl.innerHTML='<b>'+j.library+'</b> passages · <b>'+(j.skills||0)+'</b> skills · <b>'+(j.memories||0)+'</b> memories';
  const brain=document.getElementById('brain'), mini=document.getElementById('brainMini');
  if(j.brain){brain.classList.add('live');brain.innerHTML='🧠 reasoning · <b>'+esc(j.brain)+'</b>';
     brain.title='reasoning cortex: '+j.brain+' (understands & reasons)';
     if(mini)mini.textContent='🧠 '+j.brain;}
  else{brain.classList.remove('live');brain.innerHTML='🧠 lexical only — install Ollama';
     brain.title='No local LLM detected — run: ollama pull llama3.1, then restart.';
     if(mini)mini.textContent='';}
 }catch(e){}
}
async function train(withChat){
 const {b}=bubble('bot');b.innerHTML='<span class="dots"><span></span><span></span><span></span></span>';
 let chat=null;
 if(withChat){chat=[...log.querySelectorAll('.row')].map(r=>r.querySelector('.bubble').innerText).join('\n');}
 closeM('memM');
 const j=await(await fetch('/api/train',{method:'POST',headers:{'Content-Type':'application/json'},
   body:JSON.stringify({chat})})).json();
 finalize(b,{answer:'🎓 Trained my language model.\n'+
   `• passages: ${j.library}\n• contexts learned: ${j.contexts}\n• vocabulary: ${j.vocab} words`+
   (j.added?`\n• added ${j.added} new passage(s) from our chat`:''),
   how:'training',verified:true});
 loadStatus();
}
// Governed self-improvement: run the loop up to the approval gate (curate + evaluate),
// then STOP. Vio never trains or promotes itself — promotion is a deliberate step.
async function selfImprove(){
 document.getElementById('side').classList.remove('open');
 const {b}=bubble('bot');
 b.innerHTML='<div class="ln"><b>🔁 Reviewing myself…</b> curating from your feedback and running the '
   +'evaluation gate. I won’t change or promote anything on my own.</div>'
   +'<span class="dots"><span></span><span></span><span></span></span>';
 let j;
 try{j=await(await fetch('/api/improve/propose',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'})).json();}
 catch(e){finalize(b,{answer:'⚠️ Could not reach the server.',how:'error',verified:false});return;}
 if(j.available===false){finalize(b,{answer:'Self-improvement isn’t available in this build.',how:'error',verified:false});return;}
 const ev=j.evaluation||{}, cu=j.curated||{};
 const msg='### 🔁 Self-improvement report\n'
   +`- **Behaviour traces curated:** ${cu.written||0} clean training examples → \`curated_sft.jsonl\`\n`
   +`- **Evaluation gate:** ${ev.passed||0}/${ev.total||0} capabilities passing\n`
   +`- **Live model:** ${j.current_model||'(auto)'}\n`
   +`- **Status:** ${j.status||''}\n\n`
   +`**${j.gate||'Approval required.'}**\n\n`
   +`_Next:_ ${j.next||''}`;
 finalize(b,{answer:msg,how:'self-improvement (gated)',verified:true});
}
// One click → run the FULL from-scratch pipeline (train_all.py) on ALL data,
// in the background, streaming live progress into a chat bubble.
let trainingBubble=null;
async function trainAll(){
 document.getElementById('side').classList.remove('open');
 if(trainingBubble){trainingBubble.scrollIntoView({behavior:'smooth'});return;}
 const r=await(await fetch('/api/train_all',{method:'POST',
   headers:{'Content-Type':'application/json'},body:JSON.stringify({preset:'gpu'})})).json();
 const {b}=bubble('bot');
 if(!r.ok && !r.running){finalize(b,{answer:'⚠️ '+(r.message||'Could not start training.'),how:'training',verified:false});return;}
 b.innerHTML='<div class="ln"><b>🚀 Training on ALL your data…</b> This runs in the background — '
   +'you can keep chatting. It can take a while on a real GPU; feel free to close this window, '
   +'it keeps going.</div><pre><code class="trlog">starting…</code></pre>'
   +'<div class="meta"><span class="fb stoptrain" title="stop training">■ stop</span></div>';
 b.querySelector('.stoptrain').onclick=async()=>{await fetch('/api/train_all/stop',{method:'POST'});};
 trainingBubble=b; pollTrain(b);
}
async function pollTrain(b){
 let s; try{s=await(await fetch('/api/train_all/status')).json();}catch(e){setTimeout(()=>pollTrain(b),3000);return;}
 const el=b.querySelector('.trlog'); if(el) el.textContent=(s.tail||'').trim()||'starting…';
 log.scrollTop=log.scrollHeight;
 if(s.running){setTimeout(()=>pollTrain(b),2500);return;}
 trainingBubble=null;
 const st=b.querySelector('.stoptrain'); if(st) st.remove();
 const done=document.createElement('div');done.className='ln';
 if(s.returncode===0){
   done.innerHTML='<b>✅ Training finished.</b> Vio’s own model is trained on every dataset, skill and RFC.';
 }else if(/No module named .torch.|ModuleNotFoundError/.test(s.tail||'')){
   done.innerHTML='<b>⚠️ PyTorch isn’t installed.</b> Install it once, then click again:<br>'
     +'<code>pip install torch --index-url https://download.pytorch.org/whl/cu121</code>';
 }else{
   done.innerHTML='<b>⚠️ Training stopped'+(s.returncode!=null?' (exit '+s.returncode+')':'')+'.</b> See the log above.';
 }
 b.appendChild(done); loadStatus(); log.scrollTop=log.scrollHeight;
}
// skills modal
async function openSkills(){document.getElementById('skillsM').classList.add('show');loadSkills();}
async function loadSkills(){
 const j=await(await fetch('/api/skills')).json();
 document.getElementById('skillList').innerHTML=(j.skills||[]).map(s=>
  `<div class="skill"><b>${esc(s.name)}</b>
    <div class="t">when: <code>${esc(s.trigger)}</code></div>
    <div class="t">reply: ${esc(s.reply)}</div>
    <div class="rowbtns"><button class="btn danger" onclick="delSkill('${esc(s.name).replace(/'/g,'')}')">Delete</button></div>
   </div>`).join('')||'<p class="sub">No skills yet — add your first above.</p>';
}
async function addSkill(){
 const name=sk_name.value.trim(),trigger=sk_trig.value.trim(),reply=sk_reply.value.trim();
 if(!name||!trigger||!reply)return;
 const j=await(await fetch('/api/skills',{method:'POST',headers:{'Content-Type':'application/json'},
   body:JSON.stringify({name,trigger,reply})})).json();
 if(!j.ok)alert(j.message||'Could not add skill');
 sk_name.value=sk_trig.value=sk_reply.value='';loadSkills();loadStatus();
}
async function delSkill(name){
 await fetch('/api/skills',{method:'DELETE',headers:{'Content-Type':'application/json'},
   body:JSON.stringify({name})});loadSkills();loadStatus();
}
async function openMem(){document.getElementById('memM').classList.add('show');
 const j=await(await fetch('/api/memory')).json();
 document.getElementById('memBody').innerHTML=
  '<b>About you</b><br>'+((j.facts||[]).map(f=>'• '+esc(f)).join('<br>')||'<span class="sub">nothing yet</span>')+
  '<br><br><b>Library ('+(j.library||[]).length+' passages)</b><br>'+
  ((j.library||[]).slice(0,20).map(d=>'• '+esc(d.slice(0,90))).join('<br>')||'<span class="sub">empty</span>');
}
async function exportPack(){
 const j=await(await fetch('/api/pack?domain=all')).json();
 const blob=new Blob([JSON.stringify(j)],{type:'application/json'});
 const a=document.createElement('a');a.href=URL.createObjectURL(blob);
 a.download='vio-knowledge-pack.json';a.click();URL.revokeObjectURL(a.href);
}
async function importPack(){
 const f=document.getElementById('packfile').files[0];if(!f)return;
 let pack;try{pack=JSON.parse(await f.text())}catch(e){alert('Not a valid pack file.');return;}
 const j=await(await fetch('/api/pack/import',{method:'POST',headers:{'Content-Type':'application/json'},
   body:JSON.stringify({pack})})).json();
 document.getElementById('packfile').value='';closeM('memM');
 if(j.ok){const a=j.added;finalize(bubble('bot').b,{answer:`📦 Imported a knowledge pack: `+
   `${a.docs} passages, ${a.edges} relations, ${a.facts} facts, ${a.skills} skills.`,
   how:'pack import',verified:true});loadStatus();}
 else alert(j.message||'Could not import pack');
}
function closeM(id){document.getElementById(id).classList.remove('show')}
async function forget(){await fetch('/api/forget',{method:'POST'});closeM('memM');
 log.innerHTML='';finalize(bubble('bot').b,{answer:'Memory and library cleared.',how:'reset',verified:true});loadStatus();}
document.querySelectorAll('.modal').forEach(m=>m.addEventListener('click',e=>{if(e.target===m)m.classList.remove('show')}));
// apply saved theme
try{const th=localStorage.getItem('vio-theme');
 if(th){document.documentElement.setAttribute('data-theme',th);
   document.getElementById('themeBtn').textContent=th==='dark'?'🌙':'☀️';}}catch(e){}
renderChips();loadStatus();
// If a training run is already going (page was reloaded / reopened), re-attach it.
(async()=>{try{const s=await(await fetch('/api/train_all/status')).json();
  if(s.running){const {b}=bubble('bot');
    b.innerHTML='<div class="ln"><b>🚀 Training on ALL your data…</b> (already in progress)</div>'
      +'<pre><code class="trlog">…</code></pre>'
      +'<div class="meta"><span class="fb stoptrain" title="stop training">■ stop</span></div>';
    b.querySelector('.stoptrain').onclick=async()=>{await fetch('/api/train_all/stop',{method:'POST'});};
    trainingBubble=b; pollTrain(b);}}catch(e){}})();
// the hero empty-state is the welcome — no duplicate bubble needed
</script></body></html>"""


MAX_BODY = 32 * 1024 * 1024


def _status():
    st = MIND.thinker.stats()
    llm = getattr(MIND, "llm", None)
    return {"name": MIND.name(), "vocab": st["vocab"], "library": len(MIND.lib.docs),
            "contexts": st["contexts"], "skills": len(MIND.skills.skills),
            "memories": len(MIND.episodic.episodes), "gaps": len(MIND.curiosity.gaps),
            "brain": (llm.model if (llm and llm.available) else None),
            "semantic": (MIND.lib.sem.backend if getattr(MIND.lib, "sem", None) else None)}


def _idle_consolidator():
    """Background 'sleep' (§14): when Vio has been idle a while, quietly consolidate
    memory. Idle-gated so it never competes with an active request, wrapped so a
    failure can never take the server down. Disable with VIO_NO_SLEEP=1."""
    if os.environ.get("VIO_NO_SLEEP"):
        return
    last_run = 0.0
    while True:
        time.sleep(60)
        idle = time.time() - _last_activity
        if idle > 180 and (time.time() - last_run) > 600:
            try:
                MIND.consolidate()
            except Exception:
                pass
            last_run = time.time()


class H(BaseHTTPRequestHandler):
    def _s(self, code, body, ctype="application/json"):
        b = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code); self.send_header("Content-Type", ctype)
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

    def _host_ok(self):
        host = (self.headers.get("Host") or "").split(":")[0]
        return host in ("localhost", "127.0.0.1", "")

    def _body(self):
        n = int(self.headers.get("Content-Length", 0))
        if n > MAX_BODY:
            return None
        try:
            return json.loads(self.rfile.read(n) or "{}")
        except (ValueError, json.JSONDecodeError):
            return {}

    def do_GET(self):
        global _last_activity
        _last_activity = time.time()
        if not self._host_ok():
            self._s(403, "{}"); return
        from urllib.parse import urlparse, parse_qs
        path = urlparse(self.path).path
        if path == "/":
            self._s(200, PAGE, "text/html; charset=utf-8")
        elif path == "/api/status":
            self._s(200, json.dumps(_status(), ensure_ascii=False))
        elif path == "/dashboard":
            self._s(200, DASHBOARD, "text/html; charset=utf-8")
        elif path == "/api/telemetry":
            self._s(200, json.dumps(MIND.telemetry(), ensure_ascii=False))
        elif path == "/api/train_all/status":
            self._s(200, json.dumps(train_all_status(), ensure_ascii=False))
        elif path == "/api/improve":
            si = getattr(MIND, "si", None)
            self._s(200, json.dumps(si.status() if si else {"available": False},
                                    ensure_ascii=False))
        elif path == "/api/memory":
            lib = json.load(open(KB_FILE, encoding="utf-8")) if os.path.exists(KB_FILE) else []
            self._s(200, json.dumps({"name": MIND.name(), "facts": MIND.mem["facts"],
                                     "library": lib}, ensure_ascii=False))
        elif path == "/api/skills":
            self._s(200, json.dumps({"skills": MIND.skills.list()}, ensure_ascii=False))
        elif path == "/api/pack":                     # export a portable knowledge pack
            import packs
            domain = (parse_qs(urlparse(self.path).query).get("domain", ["all"])[0])
            pack = packs.export_pack(MIND, None if domain == "all" else domain)
            self._s(200, json.dumps(pack, ensure_ascii=False))
        elif path == "/api/solve":
            q = (parse_qs(urlparse(self.path).query).get("q", [""])[0]).strip()
            self._solve_stream(q)
        else:
            self._s(404, "{}")

    def _solve_stream(self, q):
        """Stream the agent's thinking steps as Server-Sent Events, then the final."""
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()

        def sse(event, data):
            try:
                self.wfile.write(f"event: {event}\ndata: {data}\n\n".encode("utf-8"))
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                raise

        try:
            def on_step(text):
                sse("step", text.replace("\n", " "))
            result = AGENT.solve(q, on_step=on_step)
            sse("final", json.dumps(result, ensure_ascii=False))
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as e:
            try:
                sse("final", json.dumps({"answer": f"Something went wrong: {e}",
                                         "how": "error", "verified": False}))
            except Exception:
                pass

    def do_DELETE(self):
        if not self._host_ok():
            self._s(403, "{}"); return
        body = self._body()
        if body is None:
            self._s(413, "{}"); return
        if self.path == "/api/skills":
            ok = MIND.skills.remove(body.get("name", ""))
            self._s(200, json.dumps({"ok": ok}))
        else:
            self._s(404, "{}")

    def do_POST(self):
        global _last_activity
        _last_activity = time.time()
        if not self._host_ok():
            self._s(403, "{}"); return
        body = self._body()
        if body is None:
            self._s(413, '{"answer":"That is too large."}'); return

        if self.path == "/api/ask":
            r = reply(MIND, (body.get("message") or "").strip())
            # talk.py's own fast paths (greeting/identity/time/skills) are deterministic
            r.setdefault("confidence", 0.9 if r.get("verified") else 0.4)
            self._s(200, json.dumps(r, ensure_ascii=False))

        elif self.path == "/api/feedback":
            msg = MIND.feedback(bool(body.get("good")))
            self._s(200, json.dumps({"answer": msg}, ensure_ascii=False))

        elif self.path == "/api/pack/import":
            import packs
            try:
                added = packs.import_pack(MIND, body.get("pack") or {})
                self._s(200, json.dumps({"ok": True, "added": added}, ensure_ascii=False))
            except ValueError as e:
                self._s(200, json.dumps({"ok": False, "message": str(e)}))

        elif self.path == "/api/learn":
            name = body.get("name") or "a file"
            text = body.get("text") or ""
            # a CSV is DATA, not prose — load it as an analyzable table, not memorized text
            if name.lower().endswith((".csv", ".tsv")) and text:
                summary = MIND.load_csv(text, name)
                self._s(200, json.dumps({"answer": summary or
                        f"I couldn't read {name} as a table."}, ensure_ascii=False))
                return
            if body.get("pdf_b64"):
                import base64
                from pdftext import extract_text, looks_readable
                try:
                    text = extract_text(base64.b64decode(body["pdf_b64"]))
                except Exception:
                    text = ""
                if not looks_readable(text):
                    self._s(200, json.dumps({"answer":
                        f"I couldn't read usable text from {name}. It's likely a scanned/image "
                        "PDF (no text layer) or uses fonts I can't decode. Options: install a "
                        "stronger reader (pip install pymupdf) and retry, or open the PDF and "
                        "'Save As → Plain Text (.txt)' and upload that."}, ensure_ascii=False))
                    return
                if len(text.split()) < 60:
                    # readable, but almost no prose — a diagram/architecture PDF whose
                    # content lives in pictures. Learn the little text, but say so plainly
                    # instead of a cheerful "Learned 1 passages" that hides the truth.
                    msg = MIND.learn_text(text, name)
                    self._s(200, json.dumps({"answer": msg +
                        "  ⚠️ Heads-up: this PDF gave me very little text — it looks like a "
                        "diagram, so most of its content is in pictures I can't read. Export it "
                        "from draw.io/Visio as a .drawio/.vsdx file and teach THAT — I read the "
                        "components and connections out of those directly."}, ensure_ascii=False))
                    return
            elif body.get("file_b64"):
                # a binary file (Visio, image) — dispatch by type: diagram → sentences,
                # image → OCR. draw.io .xml comes through as text and is handled below.
                import base64
                from diagrams import file_to_text
                try:
                    raw = base64.b64decode(body["file_b64"])
                except Exception:
                    raw = b""
                text, kind = file_to_text(name, raw)
                if not text:
                    self._s(200, json.dumps({"answer": f"I couldn't read {name}: {kind}."},
                                            ensure_ascii=False))
                    return
            elif name.lower().endswith((".drawio", ".xml")) and text:
                # draw.io source sent as text — pull out components + connections
                from diagrams import drawio_to_text
                dt = drawio_to_text(text.encode("utf-8", "ignore"))
                if dt:
                    text = dt
            msg = MIND.learn_text(text, name)
            self._s(200, json.dumps({"answer": msg}, ensure_ascii=False))

        elif self.path == "/api/learn_folder":
            path = (body.get("path") or "").strip().strip('"')
            res = (MIND.learn_folder(path) if path else
                   {"ok": False, "answer": "No folder path given.", "files": 0,
                    "passages": 0, "skipped": [], "per": []})
            self._s(200, json.dumps(res, ensure_ascii=False))

        elif self.path == "/api/train":
            chat = body.get("chat")
            stats = MIND.train_model(extra_text=chat if isinstance(chat, str) else None)
            self._s(200, json.dumps(stats, ensure_ascii=False))

        elif self.path == "/api/train_all":            # one-click full pipeline
            res = start_train_all(body.get("preset") or "gpu", body.get("steps"))
            self._s(200, json.dumps(res, ensure_ascii=False))

        elif self.path == "/api/train_all/stop":
            p = TRAINER["proc"]
            if p is not None and p.poll() is None:
                p.terminate()
            self._s(200, json.dumps({"ok": True, "running": False}))

        elif self.path == "/api/improve/propose":       # governed loop, up to the gate
            si = getattr(MIND, "si", None)
            self._s(200, json.dumps(si.propose() if si else {"available": False},
                                    ensure_ascii=False))
        elif self.path == "/api/improve/promote":        # requires explicit approval
            si = getattr(MIND, "si", None)
            res = (si.promote(body.get("model", ""), approved=bool(body.get("approved")),
                              note=body.get("note", "")) if si else {"ok": False})
            self._s(200, json.dumps(res, ensure_ascii=False))
        elif self.path == "/api/improve/rollback":
            si = getattr(MIND, "si", None)
            self._s(200, json.dumps(si.rollback() if si else {"ok": False}, ensure_ascii=False))

        elif self.path == "/api/skills":
            ok, msg = MIND.skills.add(body.get("name", ""), body.get("trigger", ""),
                                      body.get("reply", ""))
            self._s(200, json.dumps({"ok": ok, "message": msg}, ensure_ascii=False))

        elif self.path == "/api/forget":
            MIND.mem = {"facts": [], "solved": {}, "identity": {"name": MIND.name()}}
            MIND._save()
            if os.path.exists(KB_FILE):
                os.remove(KB_FILE)
            MIND.lib.docs = []; MIND.lib.vec = None
            MIND.episodic.clear()                       # wipe the autobiographical log too
            MIND.graph.clear()                          # and the knowledge graph
            MIND.curiosity.clear()                      # and the learning wishlist
            MIND.procedural.solved = MIND.mem["solved"]  # re-point after mem reset
            MIND.wm.clear()
            MIND._retrain()
            self._s(200, "{}")
        else:
            self._s(404, "{}")

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    import sys
    import threading
    url = f"http://localhost:{PORT}"
    # --service (or VIO_NO_BROWSER) runs Vio quietly in the background — no browser
    # pop-up — for the always-on autostart. A normal run still opens the browser.
    service = "--service" in sys.argv or os.environ.get("VIO_NO_BROWSER")
    if not service:
        import webbrowser
        print(f"🧠 {MIND.name()} is starting — opening {url} in your browser...")
        print("   Local reasoning + memory + your own trained model.")
        print("   Keep this window open while you chat; close it to stop Vio.")
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    threading.Thread(target=_idle_consolidator, daemon=True).start()   # §14 idle "sleep"
    try:
        ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
    except KeyboardInterrupt:
        pass
