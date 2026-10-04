"""
dashboard_page  —  Vio's live Cognitive Dashboard v2 (served at /dashboard).

Everything, live, with control:
  · brain-composition (library provenance: origins, validated vs unvalidated leads)
  · autonomy level switch (advisory / assisted / autonomous — §22)
  · agent roster + the coordinator's last conversation
  · the "how Vio answered" flow, calibration plot, confidence histogram,
    memory tiers, answer quality, System-1/2 split, domains + curiosity wishlist
  · skills registry (version/status) + governed skill proposals (approve/reject)
  · brain switcher, governed self-improvement (propose/approve/rollback),
    token-usage accounting, own trained model, maintenance commands
Self-contained (inline SVG, no libraries), theme-aware, polls live.
"""

DASHBOARD = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Vio — Control Dashboard</title>
<style>
 :root{--bg:#070a12;--panel:#111827;--panel2:#0c1320;--line:#24304a;--ink:#e9eef6;--dim:#8b97ad;
   --accent:#5b8cff;--violet:#9d84ff;--ok:#37d67a;--warn:#f4b740;--bad:#f0687f;--grid:#24304a;
   --mono:ui-monospace,"SF Mono",Menlo,Consolas,monospace;--sans:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;}
 @media(prefers-color-scheme:light){:root{--bg:#eef1f7;--panel:#fff;--panel2:#f5f7fc;--line:#dbe2ee;
   --ink:#141a24;--dim:#586377;--accent:#3f6ef5;--violet:#7c5cff;--ok:#129d5a;--warn:#c9871a;--bad:#d64562;--grid:#e4e9f2;}}
 *{box-sizing:border-box}
 html{scroll-behavior:smooth}
 body{margin:0;background:radial-gradient(1100px 600px at 85% -10%,color-mix(in srgb,var(--violet) 13%,transparent),transparent 60%),
   radial-gradient(900px 500px at -10% 20%,color-mix(in srgb,var(--accent) 9%,transparent),transparent 55%),var(--bg);
   color:var(--ink);font-family:var(--sans);line-height:1.5}
 .topbar{position:sticky;top:0;z-index:50;backdrop-filter:blur(10px);
   background:color-mix(in srgb,var(--bg) 78%,transparent);border-bottom:1px solid var(--line)}
 .topbar .in{max-width:1240px;margin:0 auto;display:flex;align-items:center;gap:10px;padding:10px 20px;flex-wrap:wrap}
 .logo{width:32px;height:32px;border-radius:9px;display:grid;place-items:center;font-size:17px;
   background:linear-gradient(135deg,var(--accent),var(--violet))}
 .topbar h1{font-size:15.5px;margin:0;letter-spacing:-.01em;white-space:nowrap}
 .topbar .sub{font-size:11px;color:var(--dim);font-family:var(--mono)}
 .pills{display:flex;gap:7px;flex-wrap:wrap;margin-left:auto;align-items:center}
 .pill{display:inline-flex;align-items:center;gap:6px;background:var(--panel2);border:1px solid var(--line);
   border-radius:999px;padding:4px 11px;font-family:var(--mono);font-size:11.5px;color:var(--dim)}
 .pill b{color:var(--ink)} .pill .on{color:var(--ok);font-weight:700} .pill .off{color:var(--warn)}
 .pill.click{cursor:pointer} .pill.click:hover{border-color:var(--accent)}
 nav{max-width:1240px;margin:0 auto;padding:6px 20px;display:flex;gap:6px;flex-wrap:wrap}
 nav a{color:var(--dim);text-decoration:none;font-size:12px;border:1px solid transparent;border-radius:8px;padding:3px 9px}
 nav a:hover{color:var(--ink);border-color:var(--line);background:var(--panel2)}
 .wrap{max-width:1240px;margin:0 auto;padding:20px 20px 70px}
 .tiles{display:grid;grid-template-columns:repeat(8,1fr);gap:10px;margin:18px 0}
 @media(max-width:1100px){.tiles{grid-template-columns:repeat(4,1fr)}}
 @media(max-width:560px){.tiles{grid-template-columns:repeat(2,1fr)}}
 .tile{background:var(--panel);border:1px solid var(--line);border-radius:13px;padding:12px 13px;position:relative;overflow:hidden}
 .tile .v{font-size:21px;font-weight:700;font-variant-numeric:tabular-nums;letter-spacing:-.02em}
 .tile .l{font-size:10.5px;color:var(--dim);margin-top:2px;text-transform:uppercase;letter-spacing:.07em}
 .tile.warn .v{color:var(--warn)} .tile.bad .v{color:var(--bad)} .tile.ok .v{color:var(--ok)}
 .grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}
 .grid3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:14px}
 @media(max-width:980px){.grid,.grid3{grid-template-columns:1fr}}
 .card{background:var(--panel);border:1px solid var(--line);border-radius:15px;padding:15px 17px;scroll-margin-top:70px}
 .card.full{grid-column:1/-1}
 .card h2{font-size:13px;margin:0 0 3px;letter-spacing:.02em;display:flex;align-items:center;gap:8px;flex-wrap:wrap}
 .card .cap{font-size:12px;color:var(--dim);margin:0 0 13px}
 .sec{margin-bottom:14px}
 svg{display:block;width:100%;overflow:visible}
 .gridln{stroke:var(--grid);stroke-width:1;stroke-dasharray:2 4;opacity:.6}
 .lbl{fill:var(--dim);font-size:11px;font-family:var(--mono)}
 .val{fill:var(--ink);font-size:11px;font-family:var(--mono);font-weight:600}
 .empty{color:var(--dim);font-size:12.5px;padding:18px 4px;text-align:center}
 .legend{display:flex;gap:13px;flex-wrap:wrap;font-size:12px;color:var(--dim);margin-top:10px}
 .legend b{color:var(--ink)}
 .dot{display:inline-block;width:9px;height:9px;border-radius:2px;margin-right:5px;vertical-align:middle}
 .flow{display:flex;flex-direction:column;gap:8px}
 .lane{display:flex;gap:8px;flex-wrap:wrap;align-items:stretch}
 .mod{flex:1;min-width:96px;background:var(--panel2);border:1px solid var(--line);border-radius:10px;padding:9px 10px}
 .mod .n{font-size:12.5px;font-weight:600} .mod .m{font-size:11px;color:var(--dim);font-family:var(--mono);margin-top:2px}
 .mod.hl{border-color:color-mix(in srgb,var(--accent) 55%,var(--line))}
 .arrowdn{text-align:center;color:var(--dim);font-size:13px;line-height:1}
 .wish{font-size:12.5px;color:var(--dim);line-height:1.7} .wish b{color:var(--ink)}
 .foot{margin-top:28px;font-size:12px;color:var(--dim);font-family:var(--mono)}
 a{color:var(--accent)}
 .badge{display:inline-block;border-radius:6px;padding:2px 8px;font-size:10.5px;font-family:var(--mono);
   border:1px solid var(--line)}
 .badge.s1{color:var(--accent);border-color:color-mix(in srgb,var(--accent) 50%,var(--line))}
 .badge.s2{color:var(--violet);border-color:color-mix(in srgb,var(--violet) 50%,var(--line))}
 .agents{display:grid;grid-template-columns:repeat(auto-fill,minmax(146px,1fr));gap:8px}
 .ag{border:1px solid var(--line);border-radius:10px;padding:8px 10px;background:var(--panel2)}
 .ag.acting{border-color:color-mix(in srgb,var(--violet) 45%,var(--line))}
 .ag .an{font-weight:600;font-size:12.5px;display:flex;align-items:center;gap:6px;justify-content:space-between}
 .ag .ad{font-size:10.5px;color:var(--dim);font-family:var(--mono);margin-top:3px}
 .ag .tag{font-size:9.5px;padding:1px 6px;border-radius:10px;white-space:nowrap;
   background:color-mix(in srgb,var(--accent) 16%,transparent);color:var(--accent)}
 .ag.acting .tag{background:color-mix(in srgb,var(--violet) 20%,transparent);color:var(--violet)}
 .btns{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:10px;align-items:center}
 .act{border:1px solid var(--line);background:var(--panel);color:var(--ink);border-radius:9px;
   padding:7px 12px;font-size:12.5px;cursor:pointer;transition:border-color .15s}
 .act:hover{border-color:var(--accent)} .act.ok{border-color:color-mix(in srgb,var(--ok) 55%,var(--line))}
 .act.bad{border-color:color-mix(in srgb,var(--bad) 55%,var(--line))}
 .act:disabled{opacity:.45;cursor:wait}
 .out{white-space:pre-wrap;font-family:var(--mono);font-size:11.5px;background:var(--panel2);
   border:1px solid var(--line);border-radius:9px;padding:10px;max-height:230px;overflow:auto}
 .minput{border:1px solid var(--line);background:var(--panel2);color:var(--ink);border-radius:8px;
   padding:7px 9px;font-size:12px;font-family:var(--mono)}
 .talk{white-space:pre-wrap;font-family:var(--mono);font-size:11.5px;color:var(--dim)}
 /* autonomy segmented control */
 .seg{display:flex;border:1px solid var(--line);border-radius:11px;overflow:hidden;width:fit-content}
 .seg button{border:0;background:transparent;color:var(--dim);padding:8px 16px;font-size:12.5px;
   cursor:pointer;font-family:var(--sans);border-right:1px solid var(--line)}
 .seg button:last-child{border-right:0}
 .seg button.on{background:linear-gradient(135deg,color-mix(in srgb,var(--accent) 26%,transparent),
   color-mix(in srgb,var(--violet) 26%,transparent));color:var(--ink);font-weight:600}
 .segdesc{font-size:12px;color:var(--dim);margin-top:9px;line-height:1.55;min-height:34px}
 /* library composition */
 .origrow{display:grid;grid-template-columns:150px 1fr 90px;gap:10px;align-items:center;margin:7px 0;font-size:12.5px}
 .origrow .bar{height:12px;border-radius:6px;background:var(--panel2);overflow:hidden}
 .origrow .bar i{display:block;height:100%;border-radius:6px;background:linear-gradient(90deg,var(--accent),var(--violet))}
 .origrow .n{font-family:var(--mono);text-align:right;font-size:11.5px;color:var(--dim)}
 .leadband{margin-top:12px;border:1px solid color-mix(in srgb,var(--warn) 40%,var(--line));
   background:color-mix(in srgb,var(--warn) 7%,transparent);border-radius:10px;padding:9px 12px;font-size:12.5px}
 .leadband.clean{border-color:color-mix(in srgb,var(--ok) 40%,var(--line));
   background:color-mix(in srgb,var(--ok) 7%,transparent)}
 /* skills + proposals */
 .skill{display:flex;align-items:center;gap:9px;border:1px solid var(--line);border-radius:10px;
   background:var(--panel2);padding:8px 11px;margin:6px 0;font-size:12.5px;flex-wrap:wrap}
 .skill .nm{font-weight:600} .skill .tr{font-family:var(--mono);font-size:11px;color:var(--dim);flex:1;min-width:160px}
 .skill .st{font-size:10.5px;font-family:var(--mono);border-radius:9px;padding:1px 8px;
   background:color-mix(in srgb,var(--ok) 15%,transparent);color:var(--ok)}
 .skill .st.dis{background:color-mix(in srgb,var(--warn) 15%,transparent);color:var(--warn)}
 .skill .act{padding:4px 9px;font-size:11.5px}
 .stage{display:flex;align-items:center;justify-content:center;gap:10px;margin:8px 0;flex-wrap:wrap}
 .stagebox{background:var(--panel2);border:1px solid var(--line);border-radius:10px;padding:8px 14px;
   font-size:12.5px;font-weight:600}
 .sarrow{color:var(--dim)}
 .routes{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin:10px 0}
 @media(max-width:980px){.routes{grid-template-columns:repeat(2,1fr)}}
 .route{background:var(--panel2);border:1px solid var(--line);border-radius:10px;padding:9px 11px;opacity:.45;
   transition:opacity .25s,border-color .25s,box-shadow .25s}
 .route .n{font-size:12.5px;font-weight:600} .route .m{font-size:10.5px;color:var(--dim);font-family:var(--mono);margin-top:1px}
 .route.active{opacity:1;border-color:var(--accent);background:color-mix(in srgb,var(--accent) 12%,var(--panel2));
   box-shadow:0 0 0 1px var(--accent),0 0 22px -6px var(--accent);animation:pulse 1.8s ease-in-out infinite}
 .route.active .m{color:var(--ink)}
 @keyframes pulse{0%,100%{box-shadow:0 0 0 1px var(--accent),0 0 16px -8px var(--accent)}
   50%{box-shadow:0 0 0 1px var(--accent),0 0 28px -2px var(--accent)}}
 .flowcap{font-size:12.5px;color:var(--dim);margin-top:10px;font-family:var(--mono)} .flowcap b{color:var(--ink)}
</style></head><body>
<div class="topbar"><div class="in">
  <div class="logo">🧠</div>
  <div><h1 id="who">Vio — Control Dashboard</h1>
    <div class="sub">live · <span id="ts"></span></div></div>
  <div class="pills">
    <span class="pill" id="modelPill">🧠 …</span>
    <span class="pill click" id="webPill" title="click to switch web research">🌐 …</span>
    <span class="pill" id="usagePill" title="LLM token accounting">🪙 …</span>
    <button class="act" onclick="load()" style="padding:5px 11px">↻</button>
  </div>
</div>
<nav>
  <a href="#library">Library</a><a href="#autonomy">Autonomy</a><a href="#agents">Agents</a>
  <a href="#brain">Brain</a><a href="#skills">Skills</a><a href="#flow">Flow</a>
  <a href="#cognition">Cognition</a><a href="#draw">Draw</a><a href="/">← chat</a>
</nav>
</div>
<div class="wrap">

 <div class="tiles" id="tiles"></div>

 <div class="grid sec" id="library">
  <div class="card">
   <h2>📚 Brain composition <span class="badge" id="libTotal"></span></h2>
   <p class="cap">Every passage carries provenance (origin + validated flag). Unvalidated
     web leads can ground answers only as flagged leads — never as verified facts.</p>
   <div id="libBars"><div class="empty">loading…</div></div>
   <div id="libLeads"></div>
   <div class="btns" style="margin-top:12px">
     <button class="act" onclick="runCmd('data report','libOut')">📊 Report</button>
     <button class="act bad" onclick="forgetLeads()">🔥 Forget unvalidated leads</button>
     <button class="act" onclick="runCmd('clean library','libOut')">🧹 Clean library</button>
     <button class="act" onclick="runCmd('config status','libOut')">🖨 Config status</button>
   </div>
   <pre class="out" id="libOut" hidden></pre>
  </div>
  <div class="card" id="autonomy">
   <h2>🎛 Autonomy — human control <span class="badge" id="autNow"></span></h2>
   <p class="cap">How much Vio may do on its own (§22). Writes ALWAYS ask, at every level.</p>
   <div class="seg" id="autSeg">
     <button data-l="advisory" onclick="setAutonomy('advisory')">Advisory</button>
     <button data-l="assisted" onclick="setAutonomy('assisted')">Assisted</button>
     <button data-l="autonomous" onclick="setAutonomy('autonomous')">Autonomous</button>
   </div>
   <div class="segdesc" id="autDesc"></div>
   <h2 style="margin-top:14px">🛠 Maintenance</h2>
   <div class="btns" style="margin-top:8px">
     <button class="act" onclick="runCmd('list gaps','maintOut')">📋 Gaps</button>
     <button class="act ok" onclick="runCmd('cover gaps','maintOut')">🌐 Cover gaps</button>
     <button class="act" onclick="runCmd('learn essentials','maintOut')">📚 Learn essentials</button>
     <button class="act" onclick="runCmd('load knowledge','maintOut')">📦 Load builtin</button>
     <button class="act" onclick="runCmd('list sources','maintOut')">🔗 Sources</button>
     <button class="act" onclick="runCmd('consolidate','maintOut')">😴 Consolidate</button>
   </div>
   <pre class="out" id="maintOut" hidden></pre>
  </div>
 </div>

 <div class="card full sec" id="agents">
  <h2>🧩 Agents — live blueprint</h2>
  <p class="cap">Every agent talks through <b>one coordinator</b>: it briefs the data-holding
    agents first (knowledge, memory, tables, devices, config), fills knowledge gaps from the
    web when allowed, and the best-fit agent answers with that shared board.</p>
  <div class="agents" id="agentsGrid"></div>
  <div class="legend" id="sharedBrain" style="margin-top:11px"></div>
  <div class="talk" id="agentTalk" style="margin-top:9px"></div>
 </div>

 <div class="grid sec" id="brain">
  <div class="card">
   <h2>🧠 Brain &amp; routing</h2>
   <p class="cap">Switch the live reasoning model instantly. Token accounting updates live.</p>
   <div class="btns">
     <select class="minput" id="modelSelect" style="flex:1;min-width:170px"></select>
     <button class="act ok" onclick="switchModel()">⚡ Use this brain</button>
   </div>
   <div class="legend" id="routerInfo" style="margin:2px 0 10px"></div>
   <h2 style="margin-top:6px"> own trained model</h2>
   <div class="legend" id="ownModel" style="margin:4px 0 12px"></div>
   <h2>🔬 Governed self-improvement</h2>
   <div class="cap" id="improveStat" style="margin:6px 0 10px">…</div>
   <div class="btns">
     <button class="act" onclick="doImprove('propose')">Propose</button>
     <input class="minput" id="promoteModel" placeholder="model to promote" style="flex:1;min-width:140px">
     <button class="act ok" onclick="doImprove('promote')">✅ Approve &amp; promote</button>
     <button class="act bad" onclick="doImprove('rollback')">↩ Rollback</button>
   </div>
   <pre class="out" id="improveOut" hidden></pre>
  </div>
  <div class="card" id="skills">
   <h2>🏅 Skill registry &amp; proposals</h2>
   <p class="cap">User-taught reflexes with version + status; agent-proposed skills wait for
     your approval (pre-install tested against recent questions).</p>
   <div id="skillList"><div class="empty">loading…</div></div>
   <h2 style="margin-top:14px">Pending proposals</h2>
   <div id="proposalList"><div class="empty">loading…</div></div>
  </div>
 </div>

 <div class="card full sec" id="flow">
  <h2>How Vio answered — live</h2>
  <p class="cap">The path your last question took. The glowing box is where it stopped.</p>
  <div class="stage">
    <div class="stagebox">❓ Question</div><span class="sarrow">→</span>
    <div class="stagebox">🧭 Understand</div><span class="sarrow">→</span>
    <div class="stagebox">🤝 Coordinator brief</div><span class="sarrow">→</span>
    <div class="stagebox">🔀 Route</div>
  </div>
  <div class="routes" id="routes"></div>
  <div class="stage">
    <div class="stagebox">⚖️ Confidence · Critic</div><span class="sarrow">→</span>
    <div class="stagebox">💬 Answer</div>
  </div>
  <div class="flowcap" id="flowcap">Ask Vio something, then watch the path light up here.</div>
 </div>

 <div class="card full sec" id="cognition">
  <h2>Cognitive architecture</h2>
  <p class="cap">A question flows top→bottom; numbers are live counts from this brain.</p>
  <div class="flow" id="arch"></div>
 </div>

 <div class="grid3 sec">
  <div class="card"><h2>Confidence calibration</h2>
   <p class="cap">Points on the dashed line = perfectly honest. Grade answers 👍/👎 to fill this in.</p>
   <div id="calib"></div></div>
  <div class="card"><h2>Answer confidence</h2>
   <p class="cap">How sure Vio has been, across all answers.</p><div id="hist"></div></div>
  <div class="card"><h2>Fast vs. deliberate</h2>
   <p class="cap">System-1 (instant, verified) vs System-2 (deliberated).</p><div id="systems"></div></div>
  <div class="card"><h2>Memory tiers</h2>
   <p class="cap">What Vio is holding, by store.</p><div id="tiers2"></div></div>
  <div class="card"><h2>Answer quality</h2>
   <p class="cap">How answers resolved.</p><div id="quality"></div></div>
  <div class="card"><h2>Domains &amp; curiosity</h2>
   <p class="cap">Where questions land, and what Vio wants to learn.</p>
   <div id="domains"></div><div class="wish" id="wish" style="margin-top:10px"></div></div>
 </div>

 <div class="card full sec" id="draw">
  <h2>🎨 Draw a diagram</h2>
  <p class="cap">Describe it — Vio renders self-contained HTML/SVG. Bigger brain → better output.</p>
  <div class="btns">
    <input class="minput" id="drawReq" style="flex:1;min-width:220px"
      placeholder="e.g. network architecture of our DMZ with a trust boundary"
      onkeydown="if(event.key==='Enter')draw()">
    <button class="act ok" onclick="draw()">🎨 Draw</button>
    <a class="act" id="drawOpen" href="#" target="_blank" rel="noopener" hidden>↗ Open full</a>
  </div>
  <div id="drawMsg" class="cap"></div>
  <iframe id="drawFrame" title="diagram" style="width:100%;height:520px;border:1px solid
    var(--line);border-radius:10px;background:#fff;display:none"></iframe>
 </div>

 <div class="foot">Served locally by Vio · <a href="/">← back to chat</a></div>
</div>

<script>
const $=id=>document.getElementById(id);
const esc=s=>(''+s).replace(/&/g,'&amp;').replace(/</g,'&lt;');
const css=v=>getComputedStyle(document.documentElement).getPropertyValue(v).trim();
function tile(v,l,cls){return `<div class="tile ${cls||''}"><div class="v">${v}</div><div class="l">${l}</div></div>`}

function hbar(el,rows,{unit='',color='--accent',max=null}={}){
 if(!rows.length){el.innerHTML='<div class="empty">No data yet — use Vio, then refresh.</div>';return}
 const m=max||Math.max(...rows.map(r=>r.value),1), rowH=30, pad=4;
 const h=rows.length*rowH+pad*2, labW=34;
 let s=`<svg viewBox="0 0 100 ${h}" preserveAspectRatio="none" style="height:${h}px">`;
 rows.forEach((r,i)=>{const y=pad+i*rowH+7, bw=(r.value/m)*(100-labW-16);
   s+=`<rect x="${labW}" y="${y}" width="${Math.max(bw,0.5)}" height="12" rx="3" fill="var(${color})"/>`;});
 s+=`</svg>`;
 let ov=`<div style="position:relative">${s}<div style="position:absolute;inset:0">`;
 rows.forEach((r,i)=>{const top=(pad+i*rowH+2)/h*100;
   ov+=`<div style="position:absolute;left:0;top:${top}%;font:600 11px var(--mono);color:var(--dim)">${esc(r.label)}</div>`;
   const bw=(r.value/m)*(100-labW-16);
   ov+=`<div style="position:absolute;left:calc(${labW}% + ${bw}% + 4px);top:${top}%;font:600 11px var(--mono);color:var(--ink);white-space:nowrap">${r.value}${unit}</div>`;});
 ov+=`</div></div>`; el.innerHTML=ov;
}
function calib(el,rel,scalar){
 if(!rel.length){el.innerHTML='<div class="empty">No graded answers yet.<br>Mark answers 👍/👎 in chat, then refresh.</div>';return}
 const S=300,P=34,X=v=>P+v*(S-P-8),Y=v=>(S-P)-v*(S-P-8);
 let g='';for(let t=0;t<=10;t+=2){const p=t/10;
   g+=`<line class="gridln" x1="${X(p)}" y1="${Y(0)}" x2="${X(p)}" y2="${Y(1)}"/>`;
   g+=`<line class="gridln" x1="${X(0)}" y1="${Y(p)}" x2="${X(1)}" y2="${Y(p)}"/>`;
   g+=`<text class="lbl" x="${X(p)}" y="${S-P+16}" text-anchor="middle">${t*10}</text>`;
   g+=`<text class="lbl" x="${P-8}" y="${Y(p)+4}" text-anchor="end">${t*10}</text>`;}
 const diag=`<line x1="${X(0)}" y1="${Y(0)}" x2="${X(1)}" y2="${Y(1)}" stroke="var(--dim)" stroke-width="2" stroke-dasharray="4 4" opacity=".7"/>`;
 let pts='';rel.forEach(r=>{const rad=6+Math.min(r.n,8);
   pts+=`<circle cx="${X(r.stated)}" cy="${Y(r.accuracy)}" r="${Math.min(rad,12)}" fill="var(--accent)" fill-opacity=".25" stroke="var(--accent)" stroke-width="2"/>`;
   pts+=`<text class="val" x="${X(r.stated)}" y="${Y(r.accuracy)-Math.min(rad,12)-4}" text-anchor="middle">${Math.round(r.accuracy*100)}%</text>`;});
 el.innerHTML=`<svg viewBox="0 0 ${S} ${S+6}" style="max-width:340px;margin:0 auto">${g}${diag}${pts}
   <text class="lbl" x="${S/2}" y="${S+2}" text-anchor="middle">stated confidence →</text></svg>
   <div class="legend"><span><span class="dot" style="background:var(--accent)"></span>observed accuracy</span>
   <span>correction ×${scalar.toFixed(2)}</span></div>`;
}
function statusBars(el,rows){
 const tot=rows.reduce((a,r)=>a+r.value,0);
 if(!tot){el.innerHTML='<div class="empty">No data yet.</div>';return}
 let bar='<div style="display:flex;height:16px;border-radius:6px;overflow:hidden;gap:2px;background:var(--panel2)">';
 rows.forEach(r=>{if(r.value)bar+=`<div style="flex:${r.value};background:var(${r.color})"></div>`});
 bar+='</div>';
 let leg='<div class="legend" style="margin-top:12px">';
 rows.forEach(r=>{if(r.value)leg+=`<span><span class="dot" style="background:var(${r.color})"></span>${r.icon||''} <b>${esc(r.label)}</b> ${r.value}</span>`});
 el.innerHTML=bar+leg+'</div>';
}

// ---- library composition ----
const ORIGIN_LABEL={dataset:'Hugging Face datasets',web:'Web research',file:'Files & folders',
 github:'GitHub repos',builtin:'Built-in knowledge',seed:'Starter knowledge',
 teach:'Taught in chat',legacy:'Taught (pre-provenance)'};
async function loadLibrary(){
 try{const j=await(await fetch('/api/library')).json();
  $('libTotal').textContent=j.total.toLocaleString()+' passages';
  const rows=j.origins||[];
  $('libBars').innerHTML=rows.map(o=>{
    const pct=Math.round(o.count/(j.total||1)*100);
    return `<div class="origrow"><span title="${esc(o.origin)}">${esc(ORIGIN_LABEL[o.origin]||o.origin)}</span>`+
      `<span class="bar"><i style="width:${Math.max(pct,1)}%"></i></span>`+
      `<span class="n">${o.count.toLocaleString()} · ${pct}%</span></div>`;
  }).join('');
  const leads=rows.reduce((a,o)=>a+(o.unvalidated||0),0);
  $('libLeads').innerHTML=leads
    ? `<div class="leadband">⚠️ <b>${leads.toLocaleString()} unvalidated lead(s)</b> from web research —
       they ground answers only as flagged leads. <b>teach:</b> the fact to confirm a lead,
       or burn them with the button above.</div>`
    : `<div class="leadband clean">✅ Everything stored is validated knowledge.</div>`;
 }catch(e){}
}

// ---- autonomy (§22) ----
const AUT_DESC={
 advisory:'ADVISORY — Vio only analyzes and recommends. Every action (even opted-in web research) asks first.',
 assisted:'ASSISTED (default) — opted-in read-only web research runs; anything that writes or changes state asks first.',
 autonomous:'AUTONOMOUS — pre-approved low-risk actions run unattended; writes STILL ask (no write tools exist yet).'};
async function loadAutonomy(){
 try{const j=await(await fetch('/api/autonomy')).json();
  $('autNow').textContent=j.level;
  $('autDesc').textContent=AUT_DESC[j.level]||'';
  document.querySelectorAll('#autSeg button').forEach(b=>b.classList.toggle('on',b.dataset.l===j.level));
 }catch(e){}
}
async function setAutonomy(l){
 try{await(await fetch('/api/autonomy',{method:'POST',headers:{'Content-Type':'application/json'},
   body:JSON.stringify({level:l})}));}catch(e){}
 loadAutonomy();
}

// ---- skills + proposals ----
async function loadSkills(){
 try{const j=await(await fetch('/api/skills')).json();
  const sk=j.skills||[];
  $('skillList').innerHTML=sk.length?sk.map(s=>
    `<div class="skill"><span class="nm">${esc(s.name)}</span>`+
    `<span class="st ${s.status==='active'?'':'dis'}">${s.status} · v${s.version||1}</span>`+
    `<span class="tr">when: ${esc(s.trigger)}</span>`+
    `<button class="act" onclick="skillToggle('${esc(s.name)}',${s.status==='active'})">${s.status==='active'?'disable':'enable'}</button>`+
    `</div>`).join('')
   :'<div class="empty">No skills yet — teach one: <b>skill: name | when: trigger | reply: text</b></div>';
 }catch(e){}
 try{const j=await(await fetch('/api/skills/proposals',{method:'POST',
   headers:{'Content-Type':'application/json'},body:JSON.stringify({status:'pending'})})).json();
  const items=(j.proposals||[]).filter(p=>p.status==='pending');
  $('proposalList').innerHTML=items.length?items.map(p=>
    `<div class="skill"><span class="nm">${esc(p.name)}</span>`+
    `<span class="tr">when: ${esc(p.trigger)} → ${esc((p.reply||'').slice(0,60))}…</span>`+
    `<button class="act ok" onclick="proposal('${esc(p.id)}','approve')">approve</button>`+
    `<button class="act bad" onclick="proposal('${esc(p.id)}','reject')">reject</button></div>`).join('')
   :'<div class="empty">No pending proposals — research with “train skill: …” creates some.</div>';
 }catch(e){}
}
async function skillToggle(name,active){
 try{await(await fetch('/api/ask',{method:'POST',headers:{'Content-Type':'application/json'},
   body:JSON.stringify({message:(active?'disable skill: ':'enable skill: ')+name})}));}catch(e){}
 loadSkills();
}
async function proposal(id,what){
 try{await(await fetch('/api/skills/'+what,{method:'POST',headers:{'Content-Type':'application/json'},
   body:JSON.stringify({id})}));}catch(e){}
 loadSkills(); loadAgents();
}

// ---- agents + coordinator ----
async function loadAgents(){
 try{const j=await(await fetch('/api/agents')).json();
  const ag=j.agents||[];
  $('agentsGrid').innerHTML=ag.map(a=>
    `<div class="ag ${a.acts?'acting':''}"><div class="an"><span>${esc(a.name)}</span>`+
    `<span class="tag">${a.acts?'⚙️ acting':'💬 advisory'}</span></div>`+
    `<div class="ad">${esc((a.domains||[]).join(', ')||'—')}</div></div>`).join('')
   ||'<span class="cap">No agents registered.</span>';
  const s=j.shared_brain||{}, c=j.coordinator||{};
  $('sharedBrain').innerHTML=`<span><span class="dot" style="background:var(--accent)"></span>shared brain:
    <b>${(s.library_passages||0).toLocaleString()}</b> passages · <b>${s.memory_facts||0}</b> facts ·
    <b>${s.skills||0}</b> skills · <b>${s.episodes||0}</b> episodes</span>`;
  $('agentTalk').textContent=(c.messages&&c.messages.length)?
    ('🤝 “'+(c.question||'')+'”\n'+c.messages.join('\n')):
    '🤝 ask Vio something to see the agents talk through the coordinator';
 }catch(e){}
}

// ---- brain switcher, usage, own model ----
async function loadModels(){
 try{const j=await(await fetch('/api/models')).json();
  const sel=$('modelSelect'); if(!sel) return;
  const cur=j.current||'', inst=j.installed||[];
  sel.innerHTML=inst.length
    ? inst.map(m=>`<option value="${esc(m)}" ${m===cur?'selected':''}>${esc(m)}${m===cur?' — live':''}</option>`).join('')
    : '<option value="">— no models installed —</option>';
 }catch(e){}
}
async function switchModel(){
 const m=($('modelSelect').value||'').trim(); if(!m) return;
 try{const j=await(await fetch('/api/model',{method:'POST',headers:{'Content-Type':'application/json'},
     body:JSON.stringify({model:m})})).json();
   if(!j.ok) alert('Switch failed: '+(j.message||'?'));
 }catch(e){}
 loadModels(); loadCaps();
}
async function loadCaps(){
 try{const j=await(await fetch('/api/status')).json();
  const w=$('webPill');
  w.textContent=(j.web?'🌐 web ON':'🌐 web OFF')+' — click';
  w.className='pill click '+(j.web?'on':'off');
  w.onclick=async()=>{const on=!j.web;
    if(on&&!confirm('Let the research agent read public web pages when my library has a gap? Nothing private is searched.'))return;
    await fetch('/api/web',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({on})});
    loadCaps();};
  $('modelPill').textContent=j.brain?('🧠 '+j.brain):'🧠 no model';
 }catch(e){}
}

// ---- flow ----
const ROUTES=[
 {id:'math',n:'Exact tools',m:'subnet · math · conversions'},
 {id:'data',n:'Data analysis',m:'CSV table'},
 {id:'skill',n:'Skill reflex',m:'user-taught'},
 {id:'world',n:'World model',m:'causal sim'},
 {id:'plan',n:'Planner',m:'grounded steps'},
 {id:'graph',n:'Graph reasoning',m:'rules · causal'},
 {id:'retrieval',n:'Retrieval',m:'grounded synthesis'},
 {id:'llm_grounded',n:'LLM · grounded',m:'reason over facts'},
 {id:'llm_reason',n:'LLM · reasoning',m:'logic · plan · decide'},
 {id:'generate',n:'Generation',m:'learned writer'},
 {id:'write',n:'Memory write',m:'teach · remember'},
 {id:'meta',n:'Self / recall',m:'identity · episodic'},
 {id:'refuse',n:'Honest refuse',m:'no source'},
 {id:'timeout',n:'LLM timeout',m:'model too slow'},
];
function routeOf(how){
 how=(how||'').toLowerCase();
 if(how.indexOf('reasoning over knowledge (llm')===0) return 'llm_grounded';
 if(how==='reasoning (llm)') return 'llm_reason';
 if(how==='llm-timeout') return 'timeout';
 if(how.indexOf('symbolic')===0||how==='exact tool'||how.indexOf('quadratic')>=0||how.indexOf('plot')>=0||how==='clock') return 'math';
 if(how.indexOf('data analysis')===0) return 'data';
 if(how.indexOf('skill:')===0) return 'skill';
 if(how.indexOf('world model')===0) return 'world';
 if(how.indexOf('planning')===0) return 'plan';
 if(how.indexOf('reasoning (')===0) return 'graph';
 if(how.indexOf('synthesis')>=0||how==='retrieval'||how.indexOf('self-directed')===0) return 'retrieval';
 if(how.indexOf('generation')===0) return 'generate';
 if(how==='no-source') return 'refuse';
 if(['library-write','memory-write','skill-write','training'].indexOf(how)>=0) return 'write';
 return 'meta';
}
function renderFlow(d){
 const rc=d.reasoning_cortex||{};
 const lr=d.last_route, active=lr?routeOf(lr.how):null;
 $('routes').innerHTML=ROUTES.map(r=>
   `<div class="route ${r.id===active?'active':''}"><div class="n">${r.n}</div><div class="m">${r.m}</div></div>`).join('');
 if(lr){
   const sys=lr.system==1?'<span class="badge s1">⚡ System 1</span>':lr.system==2?'<span class="badge s2">🧠 System 2</span>':'';
   const conf=(lr.confidence!=null)?` · <b>${Math.round(lr.confidence*100)}%</b> sure`:'';
   $('flowcap').innerHTML=`Last: “<b>${esc(lr.q||'')}</b>” → <b>${esc((lr.how||'').replace(/[_]/g,' '))}</b>${conf} ${sys}`;
 }
 const u=rc.usage;
 $('usagePill').textContent=(u&&u.calls)?`🪙 ${u.calls} calls · ${u.prompt_tokens+u.completion_tokens} tok`:'🪙 no LLM calls yet';
 const om=rc.own_model;
 $('ownModel').innerHTML=om
   ?`<span><span class="dot" style="background:var(--violet)"></span>trained from YOUR data:
     <b>${om.params_m}M params</b> · ${om.layers} layers · vocab ${om.vocab} · ctx ${om.ctx}</span>`
   :'<span>no own model trained yet — <b>python train_model.py --preset small</b> builds one from your library</span>';
}

// ---- improve ----
async function loadImprove(){
 try{const j=await(await fetch('/api/improve')).json();
  if(!j||j.available===false){$('improveStat').textContent='Self-improvement engine not available.';return;}
  const tr=j.traces||{}, n=tr.interactions!=null?tr.interactions:'?';
  $('improveStat').innerHTML=`live: <b>${esc(''+(j.current_model||'—'))}</b> · traces: <b>${esc(''+n)}</b> ·
    curated SFT: <b>${j.curated_available||0}</b>/200 (for a GPU fine-tune)`;
  if(!$('promoteModel').value && j.current_model) $('promoteModel').placeholder=j.current_model;
 }catch(e){}
}
async function doImprove(action){
 const out=$('improveOut'); out.hidden=false; out.textContent='… '+action+' …';
 let url,opts={method:'POST',headers:{'Content-Type':'application/json'},body:'{}'};
 if(action==='promote'){
   const model=($('promoteModel').value||'').trim();
   if(!model){out.textContent='Enter the model name to promote.';return;}
   if(!confirm('Approve & promote the live model to: '+model+' ?')){out.textContent='cancelled.';return;}
   url='/api/improve/promote'; opts.body=JSON.stringify({model:model,approved:true,note:'dashboard'});
 } else url=action==='propose'?'/api/improve/propose':'/api/improve/rollback';
 try{const j=await(await fetch(url,opts)).json();
   out.textContent=JSON.stringify(j,null,2).slice(0,1800);
 }catch(e){out.textContent='failed: '+e;}
 loadImprove();
}

// ---- generic command runner ----
async function runCmd(cmd,outId){
 const out=$(outId||'maintOut'); out.hidden=false;
 out.textContent='… running: '+cmd;
 try{const j=await(await fetch('/api/ask',{method:'POST',headers:{'Content-Type':'application/json'},
     body:JSON.stringify({message:cmd})})).json();
   out.textContent=j.answer||JSON.stringify(j,null,2);
 }catch(e){out.textContent='failed: '+e;}
 loadLibrary(); loadAgents();
}
async function forgetLeads(){
 if(!confirm('Delete ALL unvalidated web-research leads? Validated knowledge is untouched.'))return;
 runCmd('forget leads','libOut');
}

// ---- draw ----
async function draw(){
 const req=($('drawReq').value||'').trim(); if(!req) return;
 $('drawMsg').textContent='… drawing (can take a while on a small model)…';
 try{const j=await(await fetch('/api/draw',{method:'POST',headers:{'Content-Type':'application/json'},
     body:JSON.stringify({request:req})})).json();
   if(j.diagram_id){
     const url='/diagram/'+j.diagram_id;
     const fr=$('drawFrame'); fr.src=url; fr.style.display='block';
     const op=$('drawOpen'); op.href=url; op.hidden=false;
     $('drawMsg').textContent='✅ rendered below.';
   } else $('drawMsg').textContent='⚠️ '+((j.answer||'could not draw').split('\n')[0]);
 }catch(e){$('drawMsg').textContent='failed: '+e;}
}

async function load(){
 loadAgents(); loadCaps(); loadLibrary(); loadAutonomy(); loadSkills();
 let d;try{d=await(await fetch('/api/telemetry')).json()}catch(e){return}
 $('who').textContent=d.name+' — Control Dashboard';
 $('ts').textContent=new Date().toLocaleTimeString();
 renderFlow(d);
 const t=d.tiers;
 const leads=$('libLeads').textContent.match(/(\d[\d,]*) unvalidated/);
 const leadN=leads?+leads[1].replace(/,/g,''):0;
 $('tiles').innerHTML=
   tile(t.semantic.toLocaleString(),'Passages')+tile(leadN?leadN.toLocaleString():'0','Unvalidated leads',leadN?'warn':'ok')+
   tile(t.episodic.toLocaleString(),'Memories')+tile(t.procedural,'Skills+cache')+
   tile(d.gaps,'Open gaps',d.gaps?'warn':'ok')+tile(d.graph.edges,'Graph edges')+
   tile('×'+d.calibration.scalar.toFixed(2),'Conf. correction')+tile(d.vocab,'Vocabulary');

 const A=[
  [['Attention','filters input']],
  [['Executive','two-clock router']],
  [['Working mem',t.working+' slots'],['Semantic',t.semantic.toLocaleString()+' passages'],['Episodic',t.episodic+' memories'],['Procedural',t.procedural+' skills']],
  [['Reasoning','graph · rules'],['World model',d.graph.edges+' causal'],['Planner','grounded steps']],
  [['Confidence','×'+d.calibration.scalar.toFixed(2)],['Self-critic','conflict · re-search']],
  [['Language','grounded realizer'],['Learning','+ consolidation']],
 ];
 $('arch').innerHTML=A.map((lane,i)=>
   '<div class="lane">'+lane.map(m=>`<div class="mod ${i<2?'hl':''}"><div class="n">${m[0]}</div><div class="m">${esc(m[1]||'')}</div></div>`).join('')+'</div>'
   +(i<A.length-1?'<div class="arrowdn">▼</div>':'')).join('');

 calib($('calib'),d.calibration.reliability,d.calibration.scalar);
 hbar($('hist'),d.confidence_hist.filter(h=>h.n).map(h=>({label:h.band+'%',value:h.n})));
 hbar($('tiers2'),[
   {label:'Sem',value:t.semantic},{label:'Epi',value:t.episodic},
   {label:'Proc',value:t.procedural},{label:'WM',value:t.working}]);
 const q=d.quality||{};
 statusBars($('quality'),[
   {label:'solved',value:q.solved||0,color:'--ok',icon:'✓'},
   {label:'answered',value:q.answered||0,color:'--accent',icon:'•'},
   {label:'learned',value:q.learned||0,color:'--violet',icon:'✎'},
   {label:'correct',value:q.correct||0,color:'--ok',icon:'👍'},
   {label:'wrong',value:q.wrong||0,color:'--bad',icon:'👎'},
   {label:'unknown',value:q.unknown||0,color:'--warn',icon:'?'}]);
 const sy=d.systems||{};
 statusBars($('systems'),[
   {label:'System 1 (fast)',value:sy['System 1']||0,color:'--accent',icon:'⚡'},
   {label:'System 2 (deliberate)',value:sy['System 2']||0,color:'--violet',icon:'🧠'}]);
 const dm=Object.entries(d.domains||{});
 hbar($('domains'),dm.map(([k,v])=>({label:k.slice(0,4),value:v})));
 const wl=d.wishlist||[];
 $('wish').innerHTML=wl.length?('<b>Wants to learn:</b> '+wl.map(w=>esc(w.topic)+` (${w.count}×)`).join(', ')):'';
}
load(); loadModels(); loadImprove();
setInterval(()=>{load()},4000);
</script></body></html>"""
