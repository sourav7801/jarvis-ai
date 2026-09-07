(()=>{
  "use strict";
  const $=id=>document.getElementById(id);
  const esc=v=>String(v??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const num=(v,d=1)=>Number.isFinite(Number(v))?Number(v).toLocaleString(undefined,{maximumFractionDigits:d}):"—";
  async function api(url,options={}){const r=await fetch(url,options);let p={};try{p=await r.json()}catch{}if(!r.ok||p.success===false)throw new Error(p.message||p.error||`HTTP ${r.status}`);return p}
  function activate(id,title,msg){document.querySelectorAll(".nav button").forEach(b=>b.classList.remove("active"));$(id)?.classList.add("active");$("sectionKicker").textContent="V11 COGNITIVE EXECUTION";$("sectionTitle").textContent=title;$("sectionMessage").textContent=msg;$("content").innerHTML='<div class="loading">Refreshing governed V11 state…</div>';}
  function cards(rows){return `<div class="v10-grid">${rows.map(([a,b,k=""])=>`<article class="v10-card"><span>${esc(a)}</span><b class="${k}">${esc(b)}</b></article>`).join("")}</div>`}
  function badge(v,k=""){return `<span class="v10-badge ${k}">${esc(v)}</span>`}
  function installStyle(){if($("v11ExecutionStyle"))return;const s=document.createElement("style");s.id="v11ExecutionStyle";s.textContent=`.v11-state{font-weight:700;letter-spacing:.04em}.v11-qualified{color:#75efae}.v11-blocked{color:#ffc271}.v11-locked{color:#ff7e87}.v11-route{color:#8fd7ff}.v11-scoreline{display:flex;gap:12px;flex-wrap:wrap;margin:5px 0;color:#9fc3d2;font-size:10px}.v11-reasons{margin:6px 0 0;padding-left:18px;color:#ffc271;font-size:10px}.v11-row-head{display:flex;justify-content:space-between;gap:10px;align-items:flex-start}.v11-row-head h3{margin:0}.v11-mini{font-size:9px;color:#6f95a6}.v11-form{display:grid;grid-template-columns:minmax(220px,1fr) auto auto;gap:8px}.v11-form input{background:#06111a;color:#dff8ff;border:1px solid #21485c;border-radius:7px;padding:9px}@media(max-width:800px){.v11-form{grid-template-columns:1fr}}`;document.head.appendChild(s)}

  async function executionMeshView(){
    activate("executionMeshNav","GOVERNED EXECUTION MESH","One evidence-first packet above the 29 permanent agents. Local reversible steps may be planned; consequential external actions require approval; live broker execution remains locked.");
    try{
      const p=await api("/api/execution-mesh"),last=p.last_plan||{};
      $("content").innerHTML=cards([
        ["SYSTEM PLANE",p.system_plane?"YES":"NO",p.system_plane?"v10-ok":"v10-warn"],
        ["PLANS",num(p.plans||0,0)],
        ["LAST STATE",last.state||"NO PLAN",last.state==="READY"?"v10-ok":"v10-warn"],
        ["LIVE EXECUTION",p.live_execution?"ENABLED":"LOCKED","v10-bad"]
      ])+`<section class="section"><div class="section-head"><h2>Build governed execution packet</h2><small>Queueing adds a supervised local mission only after the existing autonomy/critic path allows it. It does not auto-start consequential execution.</small></div><div class="v11-form"><input id="v11Objective" placeholder="e.g. inspect market decision flow and prepare a governed repair plan"><button id="v11Plan">BUILD PACKET</button><button id="v11Queue">PACKET + QUEUE MISSION</button></div><div id="v11PlanResult" class="empty">No V11 packet requested yet.</div></section><section class="section"><div class="section-head"><h2>Last execution packet</h2></div>${last.created_at?`<article class="v10-row"><div class="v11-row-head"><h3>${esc(last.domain||"GENERAL")} · ${esc(last.state||"—")}</h3>${badge(last.external_actions||"APPROVAL_GATED")}</div><div class="v11-scoreline"><span>local steps ${num((last.local_governed_steps||[]).length,0)}</span><span>approval steps ${num((last.approval_required_steps||[]).length,0)}</span><span>locked steps ${num((last.locked_steps||[]).length,0)}</span></div><pre>${esc(JSON.stringify({critic:last.critic,steps:last.steps,domain_surface:last.domain_surface,safety:{paper_only:last.paper_only,live_execution:last.live_execution,automatic_broker_order:last.automatic_broker_order}},null,2))}</pre></article>`:'<div class="empty">No execution packet has run in this process yet.</div>'}</section>`;
      const submit=async enqueue=>{const q=$("v11Objective")?.value?.trim();if(!q)return;const host=$("v11PlanResult");host.className="loading";host.textContent="Building evidence-first execution packet…";try{const x=await api("/api/execution-mesh/plan",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({objective:q,enqueue_mission:enqueue})});host.className="";host.innerHTML=`<pre>${esc(JSON.stringify(x,null,2))}</pre>`}catch(e){host.className="error";host.textContent=e.message}};
      $("v11Plan")?.addEventListener("click",()=>submit(false));$("v11Queue")?.addEventListener("click",()=>submit(true));
    }catch(e){$("content").innerHTML=`<div class="error">${esc(e.message)}</div>`}
  }

  function stateClass(state){if(state==="EXECUTION_QUALIFIED")return "v11-qualified";if(String(state).includes("LOCK"))return "v11-locked";if(String(state).includes("BLOCK")||String(state).includes("STOPPED"))return "v11-blocked";return "v11-route"}
  async function tradingDecisionView(){
    activate("tradingDecisionNav","TRADE DECISION MESH","Discovery score, horizon routing, completed-bar execution score and exact blockers are shown separately so a 70–72 discovery score can never be mistaken for entry authority.");
    try{
      const p=await api("/api/trading-decision-mesh"),f=p.funnel||{},rows=p.rows||[];
      $("content").innerHTML=cards([
        ["DISCOVERY",num(f.scanner_candidates||0,0)],
        ["EXECUTION OBS",num(f.execution_observations||0,0)],
        ["QUALIFIED",num(f.execution_qualified||0,0),"v10-ok"],
        ["10M DERIVED",p.derived_10m?.installed?"ACTIVE":"NOT INSTALLED",p.derived_10m?.installed?"v10-ok":"v10-warn"]
      ])+`<section class="section"><div class="section-head"><h2>Explain one symbol</h2><small>Returns the current route, execution lane and exact WHY NOT TRADE blockers from recent governed scans.</small></div><div class="v11-form"><input id="v11Symbol" placeholder="e.g. CIPLA"><button id="v11Explain">EXPLAIN</button><span></span></div><div id="v11ExplainResult" class="empty">Select a symbol to inspect.</div></section><section class="section"><div class="section-head"><h2>Decision board</h2><small>Qualified means the execution scan passed; downstream re-entry/adaptive/risk controls can still prevent a paper position.</small></div><div class="v10-list">${rows.length?rows.map(r=>`<article class="v10-row"><div class="v11-row-head"><h3>${esc(r.symbol)} · <span class="v11-state ${stateClass(r.state)}">${esc(r.state)}</span></h3><div>${(r.route_targets||[]).map(x=>badge(x)).join("")}</div></div><div class="v11-scoreline"><span>discovery ${r.discovery_score==null?"—":num(r.discovery_score,1)}</span><span>execution ${r.execution_score==null?"—":num(r.execution_score,1)}</span><span>${esc(r.execution_mandate||"—")} ${esc(r.execution_lane||"")}</span><span>${esc(r.discovery_state||"—")}</span></div>${(r.why_not_trade||[]).length?`<ul class="v11-reasons">${r.why_not_trade.map(x=>`<li>${esc(x)}</li>`).join("")}</ul>`:'<div class="v11-mini">No current blocker in the decision board.</div>'}</article>`).join(""):'<div class="empty">No recent discovery/execution evidence.</div>'}</div></section><section class="section"><div class="section-head"><h2>Score contract</h2></div><pre>${esc(JSON.stringify(p.score_contract||{},null,2))}</pre></section>`;
      $("v11Explain")?.addEventListener("click",async()=>{const s=$("v11Symbol")?.value?.trim();if(!s)return;const host=$("v11ExplainResult");host.className="loading";host.textContent="Reading recent execution evidence…";try{const x=await api(`/api/trading-decision/explain?symbol=${encodeURIComponent(s)}`);host.className="";host.innerHTML=`<pre>${esc(JSON.stringify(x,null,2))}</pre>`}catch(e){host.className="error";host.textContent=e.message}});
    }catch(e){$("content").innerHTML=`<div class="error">${esc(e.message)}</div>`}
  }

  async function derived10mView(){
    activate("derived10mNav","10M COMPLETED-BAR BRIDGE","10-minute research/paper candles are derived only from two contiguous completed 5-minute provider bars. Missing or forming bars are never synthesized.");
    try{
      const [d,r]=await Promise.all([api("/api/derived-timeframe"),api("/api/discovery-routing")]);
      $("content").innerHTML=cards([
        ["INSTALLED",d.installed?"YES":"NO",d.installed?"v10-ok":"v10-warn"],
        ["SOURCE",d.source_timeframe||"5m"],
        ["COMPLETED ONLY",d.completed_bars_only?"YES":"NO",d.completed_bars_only?"v10-ok":"v10-bad"],
        ["LIVE EXECUTION",d.live_execution?"ENABLED":"LOCKED","v10-bad"]
      ])+`<section class="section"><div class="section-head"><h2>Derived timeframe provenance</h2></div><pre>${esc(JSON.stringify(d,null,2))}</pre></section><section class="section"><div class="section-head"><h2>Discovery routing convergence</h2><small>Scanner auto-enrollment is redirected to the portfolio horizon controller, preventing the old intraday-only path and duplicate router scans.</small></div><pre>${esc(JSON.stringify(r,null,2))}</pre></section>`;
    }catch(e){$("content").innerHTML=`<div class="error">${esc(e.message)}</div>`}
  }

  function bind(){[["executionMeshNav",executionMeshView],["tradingDecisionNav",tradingDecisionView],["derived10mNav",derived10mView]].forEach(([id,fn])=>$(id)?.addEventListener("click",fn));}
  installStyle();bind();
})();
