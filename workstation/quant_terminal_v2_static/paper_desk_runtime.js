(()=>{
  const PAPER_RE=/\b(?:paper\s+(?:trading\s+)?(?:portfolio|positions?|p\s*(?:&|and)?\s*l|pnl|risk|exposure)|my\s+paper\s+(?:trading\s+)?positions?|current\s+paper\s+(?:trading\s+)?portfolio|open\s+(?:the\s+)?paper\s+trading|paper\s+trading\s+terminal|(?:start|stop|enable|disable|run|turn\s+on|turn\s+off)\s+(?:autonomous|automatic|auto)\s+paper\s+trading|(?:autonomous|automatic|auto)\s+paper\s+trading\s+(?:status|state))\b/i;
  let refreshTimer=null;

  const MANDATES={
    INTRADAY:{label:"INTRADAY",allocation:"50%",horizon:"5m / 15m",detail:"Independent 5m + 15m breakout lanes with conservative MTF confirmation lane.",startToken:"intraday_only",stopToken:"stop_intraday"},
    SWING:{label:"SWING",allocation:"30%",horizon:"1h / 4h / 1d",detail:"Positional breakout and trend-following paper mandate.",startToken:"swing_only",stopToken:"stop_swing"},
    INVESTMENT:{label:"INVESTMENT",allocation:"20%",horizon:"1d+ · LONG ONLY",detail:"Separate long-only investment paper mandate for confirmed daily structure.",startToken:"investment_only",stopToken:"stop_investment"}
  };

  function money(value){const n=Number(value);return Number.isFinite(n)?n.toLocaleString("en-IN",{maximumFractionDigits:2,minimumFractionDigits:2}):"—"}
  function signed(value){const n=Number(value);return Number.isFinite(n)?`${n>=0?"+":""}${money(n)}`:"—"}
  function esc(value){return String(value??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]))}

  function style(){
    if(document.getElementById("paperDeskV81Style"))return;
    const node=document.createElement("style");
    node.id="paperDeskV81Style";
    node.textContent=`
      #paperDeskV4 .paper-metrics{display:grid;grid-template-columns:1fr 1fr;gap:7px;margin-top:9px}
      #paperDeskV4 .paper-metric{border:1px solid #173849;background:#07131b;border-radius:6px;padding:7px}
      #paperDeskV4 .paper-metric span{display:block;color:#6f94a4;font-size:9px;letter-spacing:.08em}
      #paperDeskV4 .paper-metric b{font-size:13px;color:#d8f4ff}
      #paperDeskV4 .mandate-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin-top:10px}
      #paperDeskV4 .mandate-card{border:1px solid #173849;background:linear-gradient(180deg,#081822,#061018);border-radius:8px;padding:9px;min-width:0}
      #paperDeskV4 .mandate-head{display:flex;justify-content:space-between;gap:6px;align-items:center}
      #paperDeskV4 .mandate-head b{font-size:11px;letter-spacing:.08em;color:#dff8ff}
      #paperDeskV4 .mandate-head span{font-size:9px;color:#6f94a4}
      #paperDeskV4 .mandate-state{font-size:10px;margin-top:5px}
      #paperDeskV4 .mandate-horizon{font-size:10px;color:#9fc8d8;margin-top:4px}
      #paperDeskV4 .mandate-detail{font-size:9px;color:#688b9a;line-height:1.35;min-height:36px;margin-top:5px}
      #paperDeskV4 .mandate-stats{font-size:9px;color:#7fa1af;line-height:1.4;margin-top:6px;min-height:39px}
      #paperDeskV4 .mandate-actions{display:grid;grid-template-columns:1fr 1fr;gap:5px;margin-top:8px}
      #paperDeskV4 .mandate-actions button{min-height:28px;font-size:9px}
      #paperDeskV4 .decision-wrap{border:1px solid #173849;border-radius:7px;background:#061018;margin-top:9px;padding:8px}
      #paperDeskV4 .decision-head{display:flex;justify-content:space-between;gap:8px;align-items:center}
      #paperDeskV4 .decision-head b{font-size:10px;color:#dff8ff;letter-spacing:.08em}
      #paperDeskV4 .decision-head span{font-size:9px;color:#668b9a}
      #paperDeskV4 .decision-list{display:grid;gap:4px;margin-top:7px;max-height:190px;overflow:auto}
      #paperDeskV4 .decision-row{display:grid;grid-template-columns:1.15fr .8fr .7fr .7fr 2fr;gap:6px;align-items:center;border-top:1px solid #112b38;padding:5px 2px;font-size:9px;color:#8eb3c2}
      #paperDeskV4 .decision-row strong{color:#d7f3ff}.decision-ok{color:#78f2aa}.decision-blocked{color:#ffcc66}
      #paperDeskV4 .paper-controls{display:grid;grid-template-columns:1fr 1fr 1fr;gap:6px;margin-top:9px}
      #paperDeskV4 .paper-controls button{min-height:30px;font-size:10px}
      #paperDeskV4 .paper-position-list{max-height:170px;overflow:auto;margin-top:8px;display:grid;gap:5px}
      #paperDeskV4 .paper-position{border-left:2px solid #5cdbff;background:#071018;padding:6px 7px;font-size:10px}
      #paperDeskV4 .paper-position strong{display:flex;justify-content:space-between;color:#dff8ff}
      #paperDeskV4 .paper-position p{margin:3px 0 0;color:#86a5b2;line-height:1.35}
      #paperDeskV4 .auto-running{color:#78f2aa}.auto-stopped{color:#ffcc66}.auto-partial{color:#72cfff}
      @media(max-width:1050px){#paperDeskV4 .mandate-grid{grid-template-columns:1fr}#paperDeskV4 .decision-row{grid-template-columns:1fr 1fr 1fr}#paperDeskV4 .decision-row span:last-child{grid-column:1/-1}}
    `;
    document.head.appendChild(node);
  }

  function mandateMarkup(key,config){
    return `<div class="mandate-card" data-mandate="${key}">
      <div class="mandate-head"><b>${config.label}</b><span>${config.allocation} PAPER RISK</span></div>
      <div class="mandate-state auto-stopped" id="mandateState${key}">STOPPED</div>
      <div class="mandate-horizon">${config.horizon}</div>
      <div class="mandate-detail">${config.detail}</div>
      <div class="mandate-stats" id="mandateStats${key}">Waiting for mandate telemetry.</div>
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
        <div id="paperDecisionBoard" class="decision-list"><div class="decision-row"><span>No routed candidates yet.</span></div></div>
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

    document.getElementById("paperAutoStart")?.addEventListener("click",startAllDayPaper);
    document.getElementById("paperAutoStop")?.addEventListener("click",stopAllDayPaper);
    document.getElementById("paperDeskRefresh")?.addEventListener("click",refreshAll);
    Object.entries(MANDATES).forEach(([key,config])=>{
      document.getElementById(`mandateStart${key}`)?.addEventListener("click",()=>controlMandate(key,config.startToken,"START"));
      document.getElementById(`mandateStop${key}`)?.addEventListener("click",()=>controlMandate(key,config.stopToken,"STOP"));
    });
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
    const laneNames=status?.lanes?Object.entries(status.lanes).filter(([,value])=>value?.running).map(([name])=>name).join("/"):"";
    const routed=status?.universe?.length||0;
    stats.innerHTML=`score ≥ ${Number(status?.min_score||0).toFixed(0)} · R:R ≥ ${Number(status?.min_risk_reward||0).toFixed(1)}<br>scanned ${Number(funnel.scanned||0)} · qualified ${Number(funnel.qualified||0)} · opened ${Number(status?.positions_opened||0)}${laneNames?`<br>lanes ${esc(laneNames)}`:""}${routed?` · watch ${routed}`:""}`;
  }

  function renderDecisionBoard(controller){
    const host=document.getElementById("paperDecisionBoard");if(!host)return;
    const rows=Array.isArray(controller?.decision_board)?controller.decision_board:[];
    if(!rows.length){host.innerHTML='<div class="decision-row"><span>No routed execution diagnostics yet.</span></div>';return}
    host.innerHTML=rows.slice(0,18).map(row=>{
      const discovery=Number(row.discovery_score);
      const execution=Number(row.execution_score);
      const discoveryText=Number.isFinite(discovery)?discovery.toFixed(1):"—";
      const executionText=Number.isFinite(execution)?execution.toFixed(1):"—";
      const lane=row.lane?`/${row.lane}`:"";
      const blocker=row.qualified?"ENTRY GATES PASSED":(row.primary_blocker||row.message||"NO QUALIFIED SETUP");
      return `<div class="decision-row"><strong>${esc(row.symbol)}</strong><span>${esc(row.mandate||"")}${esc(lane)}</span><span>D ${discoveryText}</span><span>E ${executionText}</span><span class="${row.qualified?"decision-ok":"decision-blocked"}">${esc(row.decision||"BLOCKED")} · ${esc(blocker)}</span></div>`;
    }).join("");
  }

  function renderController(controller){
    if(!controller)return;
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
  window.addEventListener("beforeunload",()=>{if(refreshTimer)clearInterval(refreshTimer)});
})();
