(()=>{
  const PAPER_RE=/\b(?:paper\s+(?:trading\s+)?(?:portfolio|positions?|p\s*(?:&|and)?\s*l|pnl|risk|exposure)|my\s+paper\s+(?:trading\s+)?positions?|current\s+paper\s+(?:trading\s+)?portfolio|open\s+(?:the\s+)?paper\s+trading|paper\s+trading\s+terminal|(?:start|stop|enable|disable|run|turn\s+on|turn\s+off)\s+(?:autonomous|automatic|auto)\s+paper\s+trading|(?:autonomous|automatic|auto)\s+paper\s+trading\s+(?:status|state))\b/i;
  let refreshTimer=null;
  let resizeObserver=null;
  let latestController=null;
  let decisionMandateFilter="ALL";
  let decisionStateFilter="ALL";

  const MANDATES={
    INTRADAY:{label:"INTRADAY",allocation:"50%",horizon:"5m · 15m",detail:"Independent 5m + 15m breakout lanes with conservative MTF confirmation lane.",startToken:"intraday_only",stopToken:"stop_intraday"},
    SWING:{label:"SWING",allocation:"30%",horizon:"1h · 4h · 1d",detail:"Positional breakout and trend-following paper mandate.",startToken:"swing_only",stopToken:"stop_swing"},
    INVESTMENT:{label:"INVESTMENT",allocation:"20%",horizon:"1d+ · LONG ONLY",detail:"Separate long-only investment paper mandate for confirmed daily structure.",startToken:"investment_only",stopToken:"stop_investment"}
  };

  function money(value){const n=Number(value);return Number.isFinite(n)?n.toLocaleString("en-IN",{maximumFractionDigits:2,minimumFractionDigits:2}):"—"}
  function signed(value){const n=Number(value);return Number.isFinite(n)?`${n>=0?"+":""}${money(n)}`:"—"}
  function esc(value){return String(value??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]))}
  function scoreText(value){if(value===null||value===undefined||value==="")return "—";const n=Number(value);return Number.isFinite(n)?n.toFixed(1):"—"}
  function integer(value){const n=Number(value);return Number.isFinite(n)?Math.max(0,Math.trunc(n)):0}

  function style(){
    if(document.getElementById("paperDeskV81Style"))return;
    const node=document.createElement("style");
    node.id="paperDeskV81Style";
    node.textContent=`
      #paperDeskV4{container-type:inline-size}
      #paperDeskV4 *{box-sizing:border-box}
      #paperDeskV4 .paper-metrics{display:grid;grid-template-columns:1fr 1fr;gap:7px;margin-top:9px}
      #paperDeskV4 .paper-metric{border:1px solid #173849;background:#07131b;border-radius:7px;padding:8px;min-width:0}
      #paperDeskV4 .paper-metric span{display:block;color:#6f94a4;font-size:9px;letter-spacing:.08em}
      #paperDeskV4 .paper-metric b{font-size:13px;color:#d8f4ff;overflow-wrap:anywhere}
      #paperDeskV4 .mandate-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin-top:10px}
      #paperDeskV4.paper-narrow .mandate-grid{grid-template-columns:1fr}
      #paperDeskV4 .mandate-card{border:1px solid #173849;background:linear-gradient(180deg,#081822,#061018);border-radius:9px;padding:10px;min-width:0;overflow:hidden}
      #paperDeskV4 .mandate-head{display:flex;justify-content:space-between;gap:8px;align-items:center;min-width:0}
      #paperDeskV4 .mandate-head b{font-size:11px;letter-spacing:.08em;color:#dff8ff;white-space:nowrap}
      #paperDeskV4 .allocation-badge{flex:0 0 auto;border:1px solid #255367;border-radius:999px;padding:2px 7px;font-size:9px;color:#9ddcf0;background:#0a202b}
      #paperDeskV4 .mandate-state{font-size:10px;margin-top:7px;font-weight:700}
      #paperDeskV4 .mandate-horizon{font-size:10px;color:#9fc8d8;margin-top:4px}
      #paperDeskV4 .mandate-stats{display:grid;grid-template-columns:1fr 1fr;gap:4px 8px;margin-top:8px;font-size:9px;color:#7fa1af;line-height:1.35}
      #paperDeskV4 .mandate-stat{min-width:0;overflow-wrap:anywhere}
      #paperDeskV4 .mandate-stat b{display:block;color:#cbeaf5;font-size:10px;font-weight:600}
      #paperDeskV4 .mandate-actions{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:6px;margin-top:9px;width:100%}
      #paperDeskV4 .mandate-actions button{width:100%;min-width:0;min-height:30px;font-size:9px;padding:4px 5px;overflow:hidden;text-overflow:ellipsis}
      #paperDeskV4 .decision-wrap{border:1px solid #173849;border-radius:8px;background:#061018;margin-top:10px;padding:9px;min-width:0;overflow:hidden}
      #paperDeskV4 .decision-head{display:flex;justify-content:space-between;gap:8px;align-items:flex-start;flex-wrap:wrap}
      #paperDeskV4 .decision-head b{font-size:10px;color:#dff8ff;letter-spacing:.08em}
      #paperDeskV4 .decision-head span{font-size:9px;color:#668b9a;overflow-wrap:anywhere}
      #paperDeskV4 .decision-funnel{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:5px;margin-top:8px}
      #paperDeskV4 .decision-funnel div{border:1px solid #153443;border-radius:6px;background:#07131b;padding:5px;text-align:center;min-width:0}
      #paperDeskV4 .decision-funnel span{display:block;color:#678d9c;font-size:8px;letter-spacing:.05em}
      #paperDeskV4 .decision-funnel b{display:block;color:#d7f3ff;font-size:11px;margin-top:2px}
      #paperDeskV4 .decision-filters{display:flex;gap:5px;flex-wrap:wrap;margin-top:8px}
      #paperDeskV4 .decision-filters button{min-height:24px;padding:3px 7px;font-size:8px;border-radius:999px}
      #paperDeskV4 .decision-filters button.active{border-color:#4ec8f0;color:#dff8ff;background:#0d2a37}
      #paperDeskV4 .decision-list{display:grid;gap:7px;margin-top:8px;max-height:310px;overflow-y:auto;overflow-x:hidden;padding-right:2px;min-width:0}
      #paperDeskV4 .decision-card{border:1px solid #143542;border-radius:7px;background:#07131b;padding:8px;min-width:0;overflow:hidden}
      #paperDeskV4 .decision-card-head{display:flex;justify-content:space-between;gap:8px;align-items:flex-start}
      #paperDeskV4 .decision-card-head strong{font-size:10px;color:#d7f3ff;overflow-wrap:anywhere}
      #paperDeskV4 .decision-card-head em{font-style:normal;font-size:9px;font-weight:700;white-space:nowrap}
      #paperDeskV4 .decision-meta{font-size:8px;color:#6f94a4;margin-top:2px;overflow-wrap:anywhere}
      #paperDeskV4 .decision-scores{display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-top:7px}
      #paperDeskV4 .decision-score{border:1px solid #112d39;border-radius:5px;padding:5px;min-width:0}
      #paperDeskV4 .decision-score span{display:block;color:#668b9a;font-size:8px}
      #paperDeskV4 .decision-score b{display:block;color:#ccebf6;font-size:10px;margin-top:2px}
      #paperDeskV4 .decision-reason{margin-top:7px;font-size:9px;line-height:1.35;color:#8fb0bd;overflow-wrap:anywhere;word-break:break-word}
      #paperDeskV4 .decision-reason b{color:#bfe3ef;font-size:8px;letter-spacing:.05em}
      #paperDeskV4 .decision-next{margin-top:6px;color:#6f94a4;font-size:8px;line-height:1.35;overflow-wrap:anywhere;word-break:break-word}
      #paperDeskV4 .decision-empty{color:#7698a6;font-size:9px;padding:8px 2px}
      #paperDeskV4 .decision-ok{color:#78f2aa}.decision-blocked{color:#ffcc66}
      #paperDeskV4 .paper-controls{display:grid;grid-template-columns:1fr 1fr 1fr;gap:6px;margin-top:9px}
      #paperDeskV4 .paper-controls button{min-width:0;min-height:30px;font-size:9px;padding:4px}
      #paperDeskV4 .paper-position-list{max-height:170px;overflow-y:auto;overflow-x:hidden;margin-top:8px;display:grid;gap:5px;min-width:0}
      #paperDeskV4 .paper-position{border-left:2px solid #5cdbff;background:#071018;padding:6px 7px;font-size:10px;min-width:0;overflow:hidden}
      #paperDeskV4 .paper-position strong{display:flex;justify-content:space-between;gap:6px;color:#dff8ff}
      #paperDeskV4 .paper-position p{margin:3px 0 0;color:#86a5b2;line-height:1.35;overflow-wrap:anywhere}
      #paperDeskV4 .auto-running{color:#78f2aa}.auto-stopped{color:#ffcc66}.auto-partial{color:#72cfff}
      #paperDeskV4.paper-narrow .paper-metrics{grid-template-columns:1fr 1fr}
      #paperDeskV4.paper-narrow .decision-funnel{grid-template-columns:1fr 1fr}
      #paperDeskV4.paper-narrow .paper-controls{grid-template-columns:1fr}
      @container (max-width:520px){#paperDeskV4 .mandate-grid{grid-template-columns:1fr}#paperDeskV4 .decision-funnel{grid-template-columns:1fr 1fr}#paperDeskV4 .paper-controls{grid-template-columns:1fr}}
    `;
    document.head.appendChild(node);
  }

  function mandateMarkup(key,config){
    return `<div class="mandate-card" data-mandate="${key}">
      <div class="mandate-head"><b>${config.label}</b><span class="allocation-badge">${config.allocation}</span></div>
      <div class="mandate-state auto-stopped" id="mandateState${key}">STOPPED</div>
      <div class="mandate-horizon">${config.horizon}</div>
      <div class="mandate-stats" id="mandateStats${key}"><div class="mandate-stat">STATUS<b>Waiting</b></div></div>
      <div class="mandate-actions">
        <button id="mandateStart${key}">START</button>
        <button id="mandateStop${key}">STOP</button>
      </div>
    </div>`;
  }

  function mount(){
    if(document.getElementById("paperDeskV4"))return;
    style();
    const host=document.querySelector(".intel-panel");
    if(!host)return;
    const card=document.createElement("section");
    card.className="intel-card";
    card.id="paperDeskV4";
    card.innerHTML=`
      <div class="eyebrow">JARVIS PAPER PORTFOLIO · V8.1 INDEPENDENT HORIZONS</div>
      <div class="hero-row"><b id="paperDeskEquity">₹100,000.00</b><span id="paperAutoState" class="auto-stopped">ALL STOPPED</span></div>
      <div class="paper-metrics">
        <div class="paper-metric"><span>TOTAL P&amp;L</span><b id="paperDeskPnl">—</b></div>
        <div class="paper-metric"><span>UNREALIZED</span><b id="paperDeskUnrealized">—</b></div>
        <div class="paper-metric"><span>GROSS EXPOSURE</span><b id="paperDeskGross">—</b></div>
        <div class="paper-metric"><span>RISK AT STOPS</span><b id="paperDeskRisk">—</b></div>
      </div>
      <div class="mandate-grid">${Object.entries(MANDATES).map(([key,config])=>mandateMarkup(key,config)).join("")}</div>
      <div class="decision-wrap">
        <div class="decision-head"><b>WHY / WHY NOT TRADE</b><span>DISCOVERY SCORE ≠ EXECUTION SCORE</span></div>
        <div id="paperDecisionFunnel" class="decision-funnel"></div>
        <div class="decision-filters" id="paperMandateFilters">
          <button data-filter="ALL" class="active">ALL</button><button data-filter="INTRADAY">INTRADAY</button><button data-filter="SWING">SWING</button><button data-filter="INVESTMENT">INVESTMENT</button>
        </div>
        <div class="decision-filters" id="paperStateFilters">
          <button data-filter="ALL" class="active">ALL DECISIONS</button><button data-filter="QUALIFIED">QUALIFIED</button><button data-filter="BLOCKED">BLOCKED</button>
        </div>
        <div id="paperDecisionBoard" class="decision-list"><div class="decision-empty">No routed candidates yet.</div></div>
      </div>
      <div class="paper-controls">
        <button id="paperAutoStart">START ALL</button>
        <button id="paperAutoStop">STOP ALL</button>
        <button id="paperDeskRefresh">REFRESH</button>
      </div>
      <div id="paperDeskPositions" class="paper-position-list"><p>No open paper positions.</p></div>
    `;
    const firstCard=host.querySelector(".intel-card");
    if(firstCard&&firstCard.nextSibling)host.insertBefore(card,firstCard.nextSibling);else host.appendChild(card);

    const updateWidth=()=>card.classList.toggle("paper-narrow",card.getBoundingClientRect().width<620);
    updateWidth();
    if(window.ResizeObserver){resizeObserver=new ResizeObserver(updateWidth);resizeObserver.observe(card)}
    else window.addEventListener("resize",updateWidth);

    document.getElementById("paperAutoStart")?.addEventListener("click",startAllDayPaper);
    document.getElementById("paperAutoStop")?.addEventListener("click",stopAllDayPaper);
    document.getElementById("paperDeskRefresh")?.addEventListener("click",refreshAll);
    Object.entries(MANDATES).forEach(([key,config])=>{
      document.getElementById(`mandateStart${key}`)?.addEventListener("click",()=>controlMandate(key,config.startToken,"START"));
      document.getElementById(`mandateStop${key}`)?.addEventListener("click",()=>controlMandate(key,config.stopToken,"STOP"));
    });
    document.querySelectorAll("#paperMandateFilters button").forEach(button=>button.addEventListener("click",()=>{
      decisionMandateFilter=button.dataset.filter||"ALL";
      document.querySelectorAll("#paperMandateFilters button").forEach(item=>item.classList.toggle("active",item===button));
      renderDecisionBoard(latestController);
    }));
    document.querySelectorAll("#paperStateFilters button").forEach(button=>button.addEventListener("click",()=>{
      decisionStateFilter=button.dataset.filter||"ALL";
      document.querySelectorAll("#paperStateFilters button").forEach(item=>item.classList.toggle("active",item===button));
      renderDecisionBoard(latestController);
    }));
  }

  function renderPortfolio(payload){
    if(!payload)return;
    const equity=document.getElementById("paperDeskEquity");
    const pnl=document.getElementById("paperDeskPnl");
    const unrealized=document.getElementById("paperDeskUnrealized");
    const gross=document.getElementById("paperDeskGross");
    const risk=document.getElementById("paperDeskRisk");
    if(equity)equity.textContent=`₹${money(payload.equity)}`;
    if(pnl){pnl.textContent=signed(payload.total_pnl);pnl.style.color=Number(payload.total_pnl)>=0?"#78f2aa":"#ff6f83"}
    if(unrealized){unrealized.textContent=signed(payload.unrealized_pnl);unrealized.style.color=Number(payload.unrealized_pnl)>=0?"#78f2aa":"#ff6f83"}
    if(gross)gross.textContent=money(payload.gross_exposure);
    if(risk)risk.textContent=`${money(payload.risk_at_stops)} · ${Number(payload.risk_percent_of_equity||0).toFixed(2)}%`;
    const list=document.getElementById("paperDeskPositions");
    if(!list)return;
    const positions=Array.isArray(payload.positions)?payload.positions:[];
    if(!positions.length){list.innerHTML="<p>No open paper positions.</p>";return}
    list.innerHTML=positions.map(item=>`<div class="paper-position"><strong><span>${esc(item.symbol)} · ${esc(item.side)}</span><span>${signed(item.unrealized_pnl)}</span></strong><p>qty ${Number(item.quantity||0).toFixed(2)} · entry ${money(item.entry)} · mark ${money(item.mark)}<br>SL ${money(item.stop)} · target ${money(item.target)} · risk ${money(item.risk_at_stop)} · ${esc(item.portfolio_bucket||item.timeframe||"")}</p></div>`).join("");
  }

  function renderMandate(key,status){
    const state=document.getElementById(`mandateState${key}`);
    const stats=document.getElementById(`mandateStats${key}`);
    if(!state||!stats)return;
    const running=Boolean(status?.running);
    state.textContent=running?"RUNNING":"STOPPED";
    state.className=`mandate-state ${running?"auto-running":"auto-stopped"}`;
    const funnel=status?.last_scan_funnel||{};
    const laneNames=status?.lanes?Object.entries(status.lanes).filter(([,value])=>value?.running).map(([name])=>name).join(" / "):"";
    const routed=Array.isArray(status?.universe)?status.universe.length:0;
    const score=status?.min_score===null||status?.min_score===undefined?"—":Number(status.min_score).toFixed(0);
    const rr=status?.min_risk_reward===null||status?.min_risk_reward===undefined?"—":Number(status.min_risk_reward).toFixed(1);
    stats.innerHTML=`
      <div class="mandate-stat">SCORE<b>≥ ${esc(score)}</b></div>
      <div class="mandate-stat">R:R<b>≥ ${esc(rr)}</b></div>
      <div class="mandate-stat">WATCH<b>${routed}</b></div>
      <div class="mandate-stat">SCANNED<b>${integer(funnel.scanned)}</b></div>
      <div class="mandate-stat">QUALIFIED<b>${integer(funnel.qualified)}</b></div>
      <div class="mandate-stat">OPENED<b>${integer(status?.positions_opened??funnel.opened)}</b></div>
      ${laneNames?`<div class="mandate-stat" style="grid-column:1/-1">ACTIVE LANES<b>${esc(laneNames)}</b></div>`:""}`;
  }

  function renderDecisionFunnel(rows){
    const host=document.getElementById("paperDecisionFunnel");if(!host)return;
    const scanned=rows.length;
    const qualified=rows.filter(row=>Boolean(row.qualified)).length;
    const opened=rows.filter(row=>String(row.decision||"").toUpperCase().includes("OPEN")).length;
    const blocked=Math.max(scanned-qualified,0);
    host.innerHTML=`<div><span>SCANNED</span><b>${scanned}</b></div><div><span>QUALIFIED</span><b>${qualified}</b></div><div><span>OPENED</span><b>${opened}</b></div><div><span>BLOCKED</span><b>${blocked}</b></div>`;
  }

  function renderDecisionBoard(controller){
    const host=document.getElementById("paperDecisionBoard");if(!host)return;
    const allRows=Array.isArray(controller?.decision_board)?controller.decision_board:[];
    renderDecisionFunnel(allRows);
    const rows=allRows.filter(row=>{
      const mandate=String(row.mandate||"").toUpperCase();
      const qualified=Boolean(row.qualified);
      if(decisionMandateFilter!=="ALL"&&mandate!==decisionMandateFilter)return false;
      if(decisionStateFilter==="QUALIFIED"&&!qualified)return false;
      if(decisionStateFilter==="BLOCKED"&&qualified)return false;
      return true;
    });
    if(!rows.length){host.innerHTML='<div class="decision-empty">No execution diagnostics match the selected filters.</div>';return}
    host.innerHTML=rows.slice(0,24).map(row=>{
      const lane=row.lane?` · ${row.lane}`:"";
      const decision=String(row.decision||(row.qualified?"QUALIFIED":"BLOCKED")).toUpperCase();
      const reason=row.qualified?"ENTRY GATES PASSED":(row.primary_blocker||row.message||"NO QUALIFIED SETUP");
      const next=row.next_trigger||row.next_confirmation||"Awaiting qualifying completed-bar evidence.";
      return `<div class="decision-card">
        <div class="decision-card-head"><strong>${esc(row.symbol||"UNKNOWN")}</strong><em class="${row.qualified?"decision-ok":"decision-blocked"}">${esc(decision)}</em></div>
        <div class="decision-meta">${esc(row.mandate||"UNROUTED")}${esc(lane)}</div>
        <div class="decision-scores"><div class="decision-score"><span>DISCOVERY</span><b>${scoreText(row.discovery_score)}</b></div><div class="decision-score"><span>EXECUTION</span><b>${scoreText(row.execution_score)}</b></div></div>
        <div class="decision-reason"><b>REASON</b><br>${esc(reason)}</div>
        <div class="decision-next"><b>NEXT</b><br>${esc(next)}</div>
      </div>`;
    }).join("");
  }

  function renderController(controller){
    if(!controller)return;
    latestController=controller;
    const mandates=controller.mandates||{};
    Object.keys(MANDATES).forEach(key=>renderMandate(key,mandates[key]||{}));
    renderDecisionBoard(controller);
    const state=document.getElementById("paperAutoState");
    if(!state)return;
    const active=Object.entries(mandates).filter(([,value])=>value?.running).map(([name])=>name);
    if(!active.length){state.textContent="ALL STOPPED";state.className="auto-stopped"}
    else if(active.length===3){state.textContent="ALL RUNNING";state.className="auto-running"}
    else{state.textContent=active.join(" / ");state.className="auto-partial"}
    const routing=controller.candidate_routing||{};
    state.title=`Active: ${active.join(", ")||"none"} · discovery candidates ${Number(routing.discovery_candidates||0)} · discovery score is separate from execution score`;
  }

  async function fetchJson(url,options){const response=await fetch(url,options);const payload=await response.json();if(!response.ok)throw new Error(payload.message||`HTTP ${response.status}`);return payload}

  async function refreshAll(){
    try{
      const [portfolio,controller]=await Promise.all([fetchJson("/api/paper/portfolio"),fetchJson("/api/paper/portfolio-controller")]);
      renderPortfolio(portfolio);renderController(controller);
    }catch(error){const reply=document.getElementById("commandReply");if(reply)reply.textContent=`Paper desk refresh: ${error.message}`}
  }

  async function controlMandate(key,token,verb){
    const config=MANDATES[key];
    const button=document.getElementById(`mandate${verb==="START"?"Start":"Stop"}${key}`);
    const reply=document.getElementById("commandReply");
    if(button){button.disabled=true;button.textContent=`${verb}ING…`}
    if(reply)reply.textContent=`${verb==="START"?"Starting":"Stopping"} ${config.label.toLowerCase()} paper mandate…`;
    try{
      const controller=await fetchJson("/api/paper/portfolio-controller/start",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({profile:token})});
      renderController(controller);
      if(reply)reply.textContent=`${config.label} paper mandate ${verb==="START"?"started":"stopped"}. Other horizons were not changed. Real execution remains locked.`;
      await refreshAll();
    }catch(error){if(reply)reply.textContent=`${config.label} ${verb} failed: ${error.message}`}
    finally{if(button){button.disabled=false;button.textContent=verb}}
  }

  async function startAllDayPaper(){
    const button=document.getElementById("paperAutoStart");
    const reply=document.getElementById("commandReply");
    if(button){button.disabled=true;button.textContent="STARTING…"}
    if(reply)reply.textContent="Starting all three governed paper mandates and broad discovery…";
    try{
      const payload=await fetchJson("/api/morning/start",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({profile:"adaptive_intraday"})});
      if(reply)reply.textContent=payload.speech||"All paper mandates started.";
      renderController(payload.paper_portfolio_controller);
      await refreshAll();
    }catch(error){if(reply)reply.textContent=`START ALL failed: ${error.message}`}
    finally{if(button){button.disabled=false;button.textContent="START ALL"}}
  }

  async function stopAllDayPaper(){
    const button=document.getElementById("paperAutoStop");
    const reply=document.getElementById("commandReply");
    if(button){button.disabled=true;button.textContent="STOPPING…"}
    try{
      const controller=await fetchJson("/api/paper/portfolio-controller/stop",{method:"POST",headers:{"Content-Type":"application/json"},body:"{}"});
      if(reply)reply.textContent="Intraday, swing and investment paper mandates stopped. Existing paper positions remain visible.";
      renderController(controller);
      await refreshAll();
    }catch(error){if(reply)reply.textContent=`STOP ALL failed: ${error.message}`}
    finally{if(button){button.disabled=false;button.textContent="STOP ALL"}}
  }

  async function sendPaper(text){
    const reply=document.getElementById("commandReply");if(reply)reply.textContent="JARVIS Paper Desk is processing…";
    try{
      const payload=await fetchJson("/api/paper/command",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({text})});
      if(reply)reply.textContent=payload.speech||payload.message||"Paper command processed.";
      if(payload.portfolio)renderPortfolio(payload.portfolio);
      if(payload.paper_portfolio_controller)renderController(payload.paper_portfolio_controller);
      else await refreshAll();
    }catch(error){if(reply)reply.textContent=error.message}
  }

  function intercept(){
    const button=document.getElementById("sendCommand");
    const input=document.getElementById("commandInput");
    if(!button||!input)return;
    button.addEventListener("click",event=>{
      const text=input.value.trim();if(!PAPER_RE.test(text))return;
      event.preventDefault();event.stopImmediatePropagation();sendPaper(text);
    },true);
    input.addEventListener("keydown",event=>{
      if(event.key!=="Enter")return;
      const text=input.value.trim();if(!PAPER_RE.test(text))return;
      event.preventDefault();event.stopImmediatePropagation();sendPaper(text);
    },true);
  }

  mount();intercept();refreshAll();
  refreshTimer=setInterval(refreshAll,2000);
  window.addEventListener("beforeunload",()=>{if(refreshTimer)clearInterval(refreshTimer);if(resizeObserver)resizeObserver.disconnect()});
})();
