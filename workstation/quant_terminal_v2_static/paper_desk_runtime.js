(()=>{
  const PAPER_RE=/\b(?:paper\s+(?:trading\s+)?(?:portfolio|positions?|p\s*(?:&|and)?\s*l|pnl|risk|exposure)|my\s+paper\s+(?:trading\s+)?positions?|current\s+paper\s+(?:trading\s+)?portfolio|open\s+(?:the\s+)?paper\s+trading|paper\s+trading\s+terminal|(?:start|stop|enable|disable|run|turn\s+on|turn\s+off)\s+(?:autonomous|automatic|auto)\s+paper\s+trading|(?:autonomous|automatic|auto)\s+paper\s+trading\s+(?:status|state))\b/i;
  let refreshTimer=null;

  function money(value){const n=Number(value);return Number.isFinite(n)?n.toLocaleString("en-IN",{maximumFractionDigits:2,minimumFractionDigits:2}):"—"}
  function signed(value){const n=Number(value);return Number.isFinite(n)?`${n>=0?"+":""}${money(n)}`:"—"}
  function esc(value){return String(value??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]))}

  function style(){
    if(document.getElementById("paperDeskV4Style"))return;
    const node=document.createElement("style");
    node.id="paperDeskV4Style";
    node.textContent=`
      #paperDeskV4 .paper-metrics{display:grid;grid-template-columns:1fr 1fr;gap:7px;margin-top:9px}
      #paperDeskV4 .paper-metric{border:1px solid #173849;background:#07131b;border-radius:6px;padding:7px}
      #paperDeskV4 .paper-metric span{display:block;color:#6f94a4;font-size:9px;letter-spacing:.08em}
      #paperDeskV4 .paper-metric b{font-size:13px;color:#d8f4ff}
      #paperDeskV4 .paper-controls{display:grid;grid-template-columns:1fr 1fr 1fr;gap:6px;margin-top:8px}
      #paperDeskV4 .paper-controls button{min-height:30px;font-size:10px}
      #paperDeskV4 .paper-position-list{max-height:170px;overflow:auto;margin-top:8px;display:grid;gap:5px}
      #paperDeskV4 .paper-position{border-left:2px solid #5cdbff;background:#071018;padding:6px 7px;font-size:10px}
      #paperDeskV4 .paper-position strong{display:flex;justify-content:space-between;color:#dff8ff}
      #paperDeskV4 .paper-position p{margin:3px 0 0;color:#86a5b2;line-height:1.35}
      #paperDeskV4 .auto-running{color:#78f2aa}.auto-stopped{color:#ffcc66}
    `;
    document.head.appendChild(node);
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
      <div class="eyebrow">AUTONOMOUS PAPER DESK · V4</div>
      <div class="hero-row"><b id="paperDeskEquity">₹100,000.00</b><span id="paperAutoState" class="auto-stopped">STOPPED</span></div>
      <div class="paper-metrics">
        <div class="paper-metric"><span>TOTAL P&amp;L</span><b id="paperDeskPnl">—</b></div>
        <div class="paper-metric"><span>UNREALIZED</span><b id="paperDeskUnrealized">—</b></div>
        <div class="paper-metric"><span>GROSS EXPOSURE</span><b id="paperDeskGross">—</b></div>
        <div class="paper-metric"><span>RISK AT STOPS</span><b id="paperDeskRisk">—</b></div>
      </div>
      <div class="paper-controls">
        <button id="paperAutoStart">AUTO ON</button>
        <button id="paperAutoStop">AUTO OFF</button>
        <button id="paperDeskRefresh">REFRESH</button>
      </div>
      <div id="paperDeskPositions" class="paper-position-list"><p>No open paper positions.</p></div>
    `;
    const firstCard=host.querySelector(".intel-card");
    if(firstCard&&firstCard.nextSibling)host.insertBefore(card,firstCard.nextSibling);else host.appendChild(card);

    document.getElementById("paperAutoStart")?.addEventListener("click",()=>sendPaper("start autonomous paper trading"));
    document.getElementById("paperAutoStop")?.addEventListener("click",()=>sendPaper("stop autonomous paper trading"));
    document.getElementById("paperDeskRefresh")?.addEventListener("click",refreshAll);
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
    list.innerHTML=positions.map(item=>`<div class="paper-position"><strong><span>${esc(item.symbol)} · ${esc(item.side)}</span><span>${signed(item.unrealized_pnl)}</span></strong><p>qty ${Number(item.quantity||0).toFixed(2)} · entry ${money(item.entry)} · mark ${money(item.mark)}<br>SL ${money(item.stop)} · target ${money(item.target)} · risk ${money(item.risk_at_stop)}</p></div>`).join("");
  }

  function renderAuto(payload){
    const state=document.getElementById("paperAutoState");if(!state)return;
    const running=Boolean(payload?.running);
    state.textContent=running?"RUNNING":"STOPPED";
    state.className=running?"auto-running":"auto-stopped";
    state.title=`Scans ${payload?.scan_cycles||0} · Opens ${payload?.positions_opened||0} · Closes ${payload?.positions_closed||0}`;
  }

  async function fetchJson(url,options){const response=await fetch(url,options);const payload=await response.json();if(!response.ok)throw new Error(payload.message||`HTTP ${response.status}`);return payload}

  async function refreshAll(){
    try{
      const [portfolio,auto]=await Promise.all([fetchJson("/api/paper/portfolio"),fetchJson("/api/paper/autonomy")]);
      renderPortfolio(portfolio);renderAuto(auto);
    }catch(error){const reply=document.getElementById("commandReply");if(reply)reply.textContent=`Paper desk refresh: ${error.message}`}
  }

  async function sendPaper(text){
    const reply=document.getElementById("commandReply");if(reply)reply.textContent="JARVIS Paper Desk is processing…";
    try{
      const payload=await fetchJson("/api/paper/command",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({text})});
      if(reply)reply.textContent=payload.speech||payload.message||"Paper command processed.";
      if(payload.portfolio)renderPortfolio(payload.portfolio);
      if(payload.autonomy)renderAuto(payload.autonomy);
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
