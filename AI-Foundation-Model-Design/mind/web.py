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
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from reasoner import Mind, KB_FILE
from talk import reply
from agent import SolveAgent

PORT = int(os.environ.get("MIND_PORT", "8100"))
MIND = Mind()
AGENT = SolveAgent(MIND)

PAGE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Vio</title>
<style>
 :root{
   --bg:#0b0e14; --bg2:#0f131c; --panel:#141a26; --panel2:#1a2231; --line:#243044;
   --txt:#e7ecf3; --dim:#93a0b4; --accent:#5b8cff; --accent2:#7c5cff;
   --user:linear-gradient(135deg,#3b6ef5,#6b4dff); --bot:#161d2b;
   --ok:#37d67a; --warn:#f4b740; --radius:16px; --hdr:rgba(20,26,38,.55);
 }
 @media (prefers-color-scheme:light){
   :root{--bg:#eef1f7;--bg2:#e7ecf5;--panel:#ffffff;--panel2:#f2f5fb;--line:#dde3ee;
         --txt:#131722;--dim:#5b6675;--bot:#f1f4fa;--hdr:rgba(255,255,255,.7);}
 }
 *{box-sizing:border-box}
 html,body{height:100%;margin:0}
 body{font-family:'Segoe UI',system-ui,-apple-system,Roboto,Arial,sans-serif;
      background:radial-gradient(1200px 700px at 80% -10%,rgba(124,92,255,.18),transparent 60%),
                 radial-gradient(900px 600px at -10% 110%,rgba(91,140,255,.16),transparent 55%),var(--bg);
      color:var(--txt);display:flex;flex-direction:column}
 header{display:flex;align-items:center;gap:12px;padding:12px 18px;border-bottom:1px solid var(--line);
        backdrop-filter:blur(8px);background:var(--hdr);position:sticky;top:0;z-index:5}
 .logo{width:38px;height:38px;border-radius:12px;display:grid;place-items:center;font-size:20px;
       background:var(--user);box-shadow:0 4px 18px rgba(91,140,255,.45)}
 .brand{font-weight:700;font-size:17px;letter-spacing:.2px}
 .brand small{display:block;font-weight:400;font-size:11px;color:var(--dim)}
 .grow{flex:1}
 .pill{font-size:11px;color:var(--dim);border:1px solid var(--line);padding:5px 10px;border-radius:20px;
       background:var(--panel);white-space:nowrap}
 .pill b{color:var(--accent)}
 .iconbtn{border:1px solid var(--line);background:var(--panel);color:var(--txt);border-radius:10px;
          padding:8px 11px;font-size:13px;cursor:pointer;transition:.15s}
 .iconbtn:hover{border-color:var(--accent);transform:translateY(-1px)}
 main{flex:1;display:flex;flex-direction:column;max-width:900px;width:100%;margin:0 auto;padding:0 14px;min-height:0}
 #log{flex:1;overflow-y:auto;padding:18px 4px;display:flex;flex-direction:column;gap:14px}
 .row{display:flex;gap:10px;align-items:flex-end;max-width:92%}
 .row.me{align-self:flex-end;flex-direction:row-reverse}
 .av{width:30px;height:30px;border-radius:9px;flex:none;display:grid;place-items:center;font-size:15px}
 .av.bot{background:var(--panel2);border:1px solid var(--line)}
 .av.me{background:var(--user)}
 .bubble{padding:11px 14px;border-radius:var(--radius);line-height:1.5;white-space:pre-wrap;
         word-wrap:break-word;overflow-wrap:anywhere;font-size:14.5px;box-shadow:0 2px 12px rgba(0,0,0,.18)}
 .me .bubble{background:var(--user);color:#fff;border-bottom-right-radius:5px}
 .bot .bubble{background:var(--bot);border:1px solid var(--line);border-bottom-left-radius:5px}
 .bubble.rtl{direction:rtl;text-align:right}
 .bubble code{background:rgba(130,150,190,.18);padding:1px 6px;border-radius:6px;font-family:ui-monospace,Consolas,monospace;font-size:13px}
 .bubble pre{background:#0a0d14;border:1px solid var(--line);border-radius:10px;padding:10px 12px;overflow-x:auto;margin:6px 0}
 .bubble pre code{background:none;padding:0}
 .meta{font-size:11px;color:var(--dim);margin-top:6px;display:flex;gap:8px;align-items:center;flex-wrap:wrap}
 .ok{color:var(--ok)}.no{color:var(--warn)}
 .copy{cursor:pointer;opacity:.6}.copy:hover{opacity:1}
 .think{border-left:2px solid var(--accent);padding:6px 0 6px 12px;margin:2px 0 8px;font-size:12.5px;color:var(--dim);
        display:flex;flex-direction:column;gap:3px}
 .think .step{opacity:0;animation:fade .3s forwards}
 @keyframes fade{to{opacity:1}}
 .dots span{display:inline-block;width:6px;height:6px;margin:0 1px;border-radius:50%;background:var(--dim);
            animation:blink 1.2s infinite both}
 .dots span:nth-child(2){animation-delay:.2s}.dots span:nth-child(3){animation-delay:.4s}
 @keyframes blink{0%,80%,100%{opacity:.2}40%{opacity:1}}
 .chips{display:flex;gap:8px;flex-wrap:wrap;padding:4px 0 10px}
 .chip{font-size:12.5px;border:1px solid var(--line);background:var(--panel);color:var(--dim);
       padding:6px 11px;border-radius:20px;cursor:pointer;transition:.15s}
 .chip:hover{border-color:var(--accent);color:var(--txt)}
 .composer{border:1px solid var(--line);background:var(--panel);border-radius:18px;padding:8px;margin:0 0 14px;
           display:flex;flex-direction:column;gap:8px;box-shadow:0 6px 30px rgba(0,0,0,.25)}
 .toolbar{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
 .toggle{display:flex;align-items:center;gap:6px;font-size:12.5px;color:var(--dim);cursor:pointer;user-select:none;
         border:1px solid var(--line);border-radius:20px;padding:5px 10px}
 .toggle.on{color:#fff;background:var(--user);border-color:transparent}
 .inrow{display:flex;gap:8px;align-items:flex-end}
 textarea#inp{flex:1;resize:none;border:0;background:transparent;color:var(--txt);font-size:15px;
              padding:8px 6px;max-height:140px;font-family:inherit;outline:none}
 .send{background:var(--user);border:0;color:#fff;width:42px;height:42px;border-radius:12px;font-size:18px;
       cursor:pointer;flex:none;display:grid;place-items:center;transition:.15s}
 .send:hover{transform:scale(1.06)}
 .send:disabled{opacity:.5;cursor:default;transform:none}
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
<header>
  <div class="logo">🧠</div>
  <div class="brand"><span id="who">Vio</span><small>local · verified · yours</small></div>
  <div class="grow"></div>
  <span class="pill" id="status">model: …</span>
  <button class="iconbtn" onclick="openSkills()">🧩 Skills</button>
  <button class="iconbtn" onclick="train(false)">🎓 Train</button>
  <button class="iconbtn" onclick="openMem()">📚 Memory</button>
</header>
<main>
  <div id="log"></div>
  <div class="chips" id="chips"></div>
  <div class="composer">
    <div class="toolbar">
      <div class="toggle on" id="deepT" onclick="toggleDeep()" title="Vio breaks hard questions apart, self-searches, and shows its thinking">
        <span>🧠</span> Deep solve</div>
      <button class="iconbtn" onclick="document.getElementById('file').click()" title="Teach me from a .txt/.md/.pdf">📄 Teach a file</button>
      <input type="file" id="file" accept=".txt,.md,.text,.csv,.log,.pdf" style="display:none" onchange="upload()">
      <span class="grow"></span>
    </div>
    <div class="inrow">
      <textarea id="inp" rows="1" placeholder="Ask anything, teach a fact, or define a skill… (English / العربية)" autofocus></textarea>
      <button class="send" id="sendBtn" onclick="send()">➤</button>
    </div>
  </div>
</main>

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
function fmt(t){ // minimal, safe markdown: code fences, `inline`, **bold**
 let s=esc(t);
 s=s.replace(/```([\s\S]*?)```/g,(m,c)=>'<pre><code>'+c.replace(/^\n/,'')+'</code></pre>');
 s=s.replace(/`([^`]+)`/g,'<code>$1</code>');
 s=s.replace(/\*\*([^*]+)\*\*/g,'<b>$1</b>');
 return s;
}
const CHIPS=["solve x^2 - 5x + 6 = 0","15% of 200 and 12 factorial","5 km to miles",
 "integrate 1/x","is 97 prime","learn from github owner/repo","teach: The Nile is the longest river."];
function renderChips(){document.getElementById('chips').innerHTML=
 CHIPS.map(c=>`<span class="chip" onclick="chip(this)">${esc(c)}</span>`).join('')}
function chip(e){inp.value=e.textContent;inp.focus();autosize()}
function bubble(who){
 const row=document.createElement('div');row.className='row '+(who==='me'?'me':'bot');
 const av=document.createElement('div');av.className='av '+(who==='me'?'me':'bot');
 av.textContent=who==='me'?'🧑':'🧠';
 const b=document.createElement('div');b.className='bubble';
 row.appendChild(av);row.appendChild(b);log.appendChild(row);
 log.scrollTop=log.scrollHeight;return {row,b};
}
function addUser(t){const {b}=bubble('me');b.classList.toggle('rtl',isAr(t));b.textContent=t;}
function badge(j){const c=(j.confidence!=null)?' · '+Math.round(j.confidence*100)+'% sure':'';
 return (j.verified?'<span class="ok">✓ verified</span>':'<span class="no">… unverified</span>')+' · '+esc(j.how||'')+c;}
function finalize(b,j){
 b.classList.toggle('rtl',isAr(j.answer));
 b.innerHTML=fmt(j.answer);
 const m=document.createElement('div');m.className='meta';
 m.innerHTML=badge(j)+' <span class="copy" title="copy">⧉</span>';
 m.querySelector('.copy').onclick=()=>navigator.clipboard.writeText(j.answer);
 b.appendChild(m);log.scrollTop=log.scrollHeight;
}
function autosize(){inp.style.height='auto';inp.style.height=Math.min(inp.scrollHeight,140)+'px'}
inp.addEventListener('input',autosize);
inp.addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send()}});
function toggleDeep(){deep=!deep;document.getElementById('deepT').classList.toggle('on',deep)}

async function send(){
 const t=inp.value.trim();if(!t||busy)return;
 inp.value='';autosize();addUser(t);busy=true;sendBtn.disabled=true;
 const {b}=bubble('bot');
 if(deep){await solveStream(t,b)} else {await ask(t,b)}
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
 if(/\.pdf$/i.test(f.name)){const buf=new Uint8Array(await f.arrayBuffer());let bin='';
   for(let i=0;i<buf.length;i++)bin+=String.fromCharCode(buf[i]);
   body=JSON.stringify({name:f.name,pdf_b64:btoa(bin)});}
 else{body=JSON.stringify({name:f.name,text:await f.text()});}
 const j=await(await fetch('/api/learn',{method:'POST',headers:{'Content-Type':'application/json'},body})).json();
 finalize(b,{answer:j.answer,how:'learned from file',verified:true});
 document.getElementById('file').value='';loadStatus();
}
async function loadStatus(){
 try{const j=await(await fetch('/api/status')).json();
  if(j.name){document.getElementById('who').textContent=j.name;document.title=j.name;}
  statusEl.innerHTML='model: <b>'+j.vocab+'</b> words · <b>'+j.library+'</b> passages · <b>'+j.skills+'</b> skills · <b>'+(j.memories||0)+'</b> memories';
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
function closeM(id){document.getElementById(id).classList.remove('show')}
async function forget(){await fetch('/api/forget',{method:'POST'});closeM('memM');
 log.innerHTML='';finalize(bubble('bot').b,{answer:'Memory and library cleared.',how:'reset',verified:true});loadStatus();}
document.querySelectorAll('.modal').forEach(m=>m.addEventListener('click',e=>{if(e.target===m)m.classList.remove('show')}));
renderChips();loadStatus();
finalize(bubble('bot').b,{answer:"Hi! I'm Vio — a local assistant that reasons and verifies, never guesses. "+
 "Ask me math, teach me facts, define skills, or flip on 🧠 Deep solve for harder questions. I'm yours.",
 how:'welcome',verified:true});
</script></body></html>"""


MAX_BODY = 32 * 1024 * 1024


def _status():
    st = MIND.thinker.stats()
    return {"name": MIND.name(), "vocab": st["vocab"], "library": len(MIND.lib.docs),
            "contexts": st["contexts"], "skills": len(MIND.skills.skills),
            "memories": len(MIND.episodic.episodes)}


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
        if not self._host_ok():
            self._s(403, "{}"); return
        from urllib.parse import urlparse, parse_qs
        path = urlparse(self.path).path
        if path == "/":
            self._s(200, PAGE, "text/html; charset=utf-8")
        elif path == "/api/status":
            self._s(200, json.dumps(_status(), ensure_ascii=False))
        elif path == "/api/memory":
            lib = json.load(open(KB_FILE, encoding="utf-8")) if os.path.exists(KB_FILE) else []
            self._s(200, json.dumps({"name": MIND.name(), "facts": MIND.mem["facts"],
                                     "library": lib}, ensure_ascii=False))
        elif path == "/api/skills":
            self._s(200, json.dumps({"skills": MIND.skills.list()}, ensure_ascii=False))
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

        elif self.path == "/api/learn":
            name = body.get("name") or "a file"
            text = body.get("text") or ""
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
            msg = MIND.learn_text(text, name)
            self._s(200, json.dumps({"answer": msg}, ensure_ascii=False))

        elif self.path == "/api/train":
            chat = body.get("chat")
            stats = MIND.train_model(extra_text=chat if isinstance(chat, str) else None)
            self._s(200, json.dumps(stats, ensure_ascii=False))

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
            MIND.procedural.solved = MIND.mem["solved"]  # re-point after mem reset
            MIND.wm.clear()
            MIND._retrain()
            self._s(200, "{}")
        else:
            self._s(404, "{}")

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    import threading
    import webbrowser
    url = f"http://localhost:{PORT}"
    print(f"🧠 {MIND.name()} is starting — opening {url} in your browser...")
    print("   Local reasoning + memory + your own trained model. No external model.")
    print("   Keep this window open while you chat; close it to stop Vio.")
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
    except KeyboardInterrupt:
        pass
