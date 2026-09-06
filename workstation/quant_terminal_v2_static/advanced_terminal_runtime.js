(()=>{
  let timer=null;
  let activeProfile="adaptive_intraday";
  let activeUniverse="ALL";
  const esc=value=>String(value??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const num=(value,digits=1)=>{const n=Number(value);return Number.isFinite(n)?n.toLocaleString("en-IN",{maximumFractionDigits:digits}):"—"};

  async function json(url,options={}){
    const response=await fetch(url,options);const payload=await response.json();
    if(!response.ok)throw new Error(payload.message||`HTTP ${response.status}`);return payload;
  }

  function style(){
    if(document.getElementById("advancedTerminalStyle"))return;
    const node=document.createElement("style");node.id="advancedTerminalStyle";node.textContent=`
      #jarvisMorningCard{border-color:#2c7655;background:linear-gradient(145deg,#07141c,#0a211b)}
      #jarvisMorningStart{width:100%;min-height:48px;margin-top:9px;border-color:#61e69a;color:#8df6b9;font-weight:800;letter-spacing:.08em}
      #jarvisMorningStart.running{box-shadow:0 0 24px rgba(97,230,154,.18)}
      .advanced-row{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-top:8px}
      .advanced-row small{color:#7e9aa7}.advanced-status{color:#78f2aa;font-size:10px}
      .scanner-results{display:grid;gap:5px;max-height:260px;overflow:auto;margin-top:8px}
      .scanner-result{display:grid;grid-template-columns:1fr auto;gap:4px;border:1px solid #173849;background:#071018;padding:7px;border-radius:5px;cursor:pointer;text-align:left}
      .scanner-result:hover{border-color:#5cdbff}.scanner-result strong{font-size:11px}.scanner-result span{font-size:10px;color:#5cdbff}.scanner-result small{grid-column:1/-1;color:#86a5b2}
      .options-grid{display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-top:8px}.options-grid div{border:1px solid #173849;padding:7px;border-radius:5px;background:#071018}
      .options-grid b{display:block;color:#dff8ff;font-size:11px}.options-grid small{color:#7e9aa7;font-size:9px;line-height:1.4}
      .latency-note{margin-top:8px;border-left:2px solid #ffd166;padding:6px 8px;color:#d8bd6e;font-size:9px;line-height:1.45}
      .mode-row,.universe-row{display:flex;gap:5px;flex-wrap:wrap;margin-top:8px}.mode-row button,.universe-row button{font-size:9px;padding:6px 8px;min-height:0}.mode-row button.active,.universe-row button.active{border-color:#61e69a;color:#8df6b9;background:#0a211b}
      .gate-summary{display:grid;grid-template-columns:repeat(2,1fr);gap:5px;margin-top:8px}.gate-summary div{border:1px solid #173849;padding:6px;background:#071018;border-radius:4px}.gate-summary b{display:block;color:#dff8ff;font-size:10px}.gate-summary small{color:#7e9aa7;font-size:8px}
      .blockers{margin-top:7px;color:#d8bd6e;font-size:9px;line-height:1.5}
    `;document.head.appendChild(node);
  }

  function mount(){
    if(document.getElementById("jarvisMorningCard"))return;
    style();const host=document.querySelector(".intel-panel");if(!host)return;
    const morning=document.createElement("section");morning.className="intel-card";morning.id="jarvisMorningCard";morning.innerHTML=`
      <div class="eyebrow">ONE-CLICK ALL-DAY PAPER PORTFOLIO</div>
      <div class="advanced-row"><b>SCAN → VERIFY → SIZE → SIMULATE → REVIEW</b><span id="morningState" class="advanced-status">READY</span></div>
      <div class="mode-row" id="paperModeRow"><button data-profile="adaptive_intraday" class="active">ADAPTIVE 5m/15m · 0.25×</button><button data-profile="intraday">STRICT MTF 5m/15m/1h</button><button data-profile="paper_exploration">PAPER LEARN · 0.25× RISK</button><button data-profile="1m_only">1m ONLY</button><button data-profile="5m_only">5m ONLY</button><button data-profile="15m_only">15m ONLY</button><button data-profile="swing">SWING</button></div>
      <button id="jarvisMorningStart">START ALL-DAY PAPER TRADING</button>
      <small>50% intraday · 30% swing · 20% long-only investment. Scans Indian indices and constituents, MCX and crypto. Entries use completed bars and fresh-price validation. Real orders remain locked.</small>
      <div id="paperGateSummary" class="gate-summary"><div><b>NO SCAN YET</b><small>PAPER EXECUTION</small></div><div><b>NO REVIEW YET</b><small>BOUNDED LEARNING</small></div></div><div id="paperBlockers" class="blockers"></div>
    `;
    const scanner=document.createElement("section");scanner.className="intel-card";scanner.id="nifty50ScannerCard";scanner.innerHTML=`
      <div class="eyebrow">MULTI-MARKET DISCOVERY RADAR · COMPLETED BARS</div>
      <div class="universe-row" id="scannerUniverseRow"><button data-universe="ALL" class="active">ALL</button><button data-universe="NIFTY50">NIFTY 50</button><button data-universe="BANKNIFTY">BANK NIFTY</button><button data-universe="SENSEX30">SENSEX 30</button><button data-universe="MCX_MAJOR">MCX</button><button data-universe="CRYPTO_MAJOR">CRYPTO</button><button data-universe="GLOBAL_MAJOR">GLOBAL RESEARCH</button></div>
      <div class="advanced-row"><b id="niftyScannerProgress">NOT SCANNED</b><button id="niftyScannerStart">SCAN SELECTED</button></div>
      <div id="niftyScannerResults" class="scanner-results"><p>Run the scan to rank daily breakouts, breakdowns and near-level watches.</p></div>
    `;
    const options=document.createElement("section");options.className="intel-card";options.id="optionsReadinessCard";options.innerHTML=`
      <div class="eyebrow">OPTIONS &amp; LATENCY READINESS</div>
      <div class="options-grid"><div><b id="indiaOptionsState">INDIA OPTIONS · CHECKING</b><small>NIFTY / BANKNIFTY · OI · IV · Greeks</small></div><div><b id="cryptoOptionsState">CRYPTO OPTIONS · CHECKING</b><small>BTC / ETH · Deribit public research</small></div></div>
      <div class="latency-note">TICK DATA CAN ARRIVE IN REAL TIME; STRATEGY ENTRIES ARE EVALUATED ON COMPLETED BARS. THIS IS NOT MILLISECOND/HFT EXECUTION.</div>
    `;
    host.prepend(options);host.prepend(scanner);host.prepend(morning);
    document.getElementById("jarvisMorningStart")?.addEventListener("click",startMorning);
    document.getElementById("niftyScannerStart")?.addEventListener("click",()=>startScan(false));
    document.querySelectorAll("#paperModeRow [data-profile]").forEach(button=>button.addEventListener("click",()=>{activeProfile=button.dataset.profile;document.querySelectorAll("#paperModeRow button").forEach(item=>item.classList.toggle("active",item===button))}));
    document.querySelectorAll("#scannerUniverseRow [data-universe]").forEach(button=>button.addEventListener("click",()=>{activeUniverse=button.dataset.universe;document.querySelectorAll("#scannerUniverseRow button").forEach(item=>item.classList.toggle("active",item===button));renderScanner(window.__jarvisMultiScanner||{})}));
  }

  async function startMorning(){
    const button=document.getElementById("jarvisMorningStart"),state=document.getElementById("morningState"),reply=document.getElementById("commandReply");
    if(button){button.disabled=true;button.textContent="STARTING…"}if(state)state.textContent="STARTING";
    try{const payload=await json("/api/morning/start",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({profile:activeProfile})});if(reply)reply.textContent=payload.speech||"All-day paper portfolio started.";if(state)state.textContent="RUNNING · 50 / 30 / 20";if(button){button.textContent="ALL-DAY PAPER RUNNING";button.classList.add("running")}}
    catch(error){if(state)state.textContent="ERROR";if(reply)reply.textContent=error.message;if(button)button.textContent="RETRY START"}
    finally{if(button)button.disabled=false;refreshScanner()}
  }

  async function startScan(autoEnroll){
    const button=document.getElementById("niftyScannerStart");if(button){button.disabled=true;button.textContent="STARTING"}
    const universes=activeUniverse==="ALL"?["NIFTY50","BANKNIFTY","SENSEX30","INDIA_INDICES","MCX_MAJOR","CRYPTO_MAJOR"]:[activeUniverse];
    try{await json("/api/scanner/multi/start",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({force:true,auto_enroll:Boolean(autoEnroll),profile:activeProfile,universes})});await refreshScanner()}
    catch(error){const reply=document.getElementById("commandReply");if(reply)reply.textContent=error.message}
    finally{if(button){button.disabled=false;button.textContent="SCAN 50"}}
  }

  function renderScanner(payload){
    const progress=document.getElementById("niftyScannerProgress"),host=document.getElementById("niftyScannerResults");if(!progress||!host)return;
    window.__jarvisMultiScanner=payload;progress.textContent=payload.running?`SCANNING ${payload.scanned||0}/${payload.total||0}`:`${payload.candidate_count||0} CANDIDATES · ${payload.scanned||0}/${payload.total||0}`;
    const allRows=Array.isArray(payload.candidates)?payload.candidates:[];const rows=activeUniverse==="ALL"?allRows:allRows.filter(row=>(row.universes||[]).includes(activeUniverse));
    if(!rows.length){host.innerHTML=`<p>${payload.running?"Reading verified daily candles…":"No candidate currently clears the breakout radar."}</p>`;return}
    host.innerHTML=rows.slice(0,18).map(row=>`<button class="scanner-result" data-symbol="${esc(row.symbol)}"><strong>${esc(row.symbol)} · ${esc(row.state||"")}</strong><span>${num(row.score)} SCORE</span><small>${esc((row.universes||[]).join(" / "))} · ${esc(row.direction||"NEUTRAL")} · ${row.auto_paper_eligible?"PAPER ELIGIBLE":"RESEARCH ONLY"} · close ${num(row.close,2)} · vol× ${num(row.volume_ratio,2)}</small></button>`).join("");
    host.querySelectorAll("[data-symbol]").forEach(button=>button.addEventListener("click",()=>{const symbol=button.dataset.symbol;if(typeof window.openSignalChart==="function")window.openSignalChart({symbol,label:symbol,kind:"MARKET",timeframe:activeProfile==="swing"?"1d":["adaptive_intraday","intraday","paper_exploration"].includes(activeProfile)?"5m":activeProfile.replace("_only",""),profile:activeProfile,layout:1})}));
  }

  async function refreshScanner(){try{renderScanner(await json("/api/scanner/multi"))}catch{}}
  async function refreshPaper(){try{const [auto,portfolio,review]=await Promise.all([json("/api/paper/autonomy"),json("/api/paper/portfolio-controller"),json("/api/paper/review")]);const summary=document.getElementById("paperGateSummary"),blockers=document.getElementById("paperBlockers"),state=document.getElementById("morningState");if(state&&portfolio.running)state.textContent="RUNNING · 50 / 30 / 20";if(summary)summary.innerHTML=`<div><b>${auto.positions_opened||0} OPENED · ${auto.scan_cycles||0} CYCLES</b><small>INTRADAY 50% · SWING 30% · INVESTMENT 20%</small></div><div><b>${review.reviewed_trades||0} REVIEWED · ${review.active_policies||0} POLICIES</b><small>RISK CAN ONLY STAY OR TIGHTEN</small></div>`;const entries=Object.entries(auto.last_rejection_counts||{}).sort((a,b)=>b[1]-a[1]).slice(0,5);if(blockers)blockers.textContent=entries.length?`Latest blockers: ${entries.map(([key,count])=>`${key.replaceAll("_"," ")} ${count}`).join(" · ")}`:"No rejection diagnostics yet. No trade is forced without a qualified setup."}catch{}}
  async function refreshOptions(){try{const payload=await json("/api/options/readiness");const india=document.getElementById("indiaOptionsState"),crypto=document.getElementById("cryptoOptionsState");if(india)india.textContent=`INDIA OPTIONS · ${payload.india_index_options?.configured&&payload.india_index_options?.token_saved?"READY":"LOGIN REQUIRED"}`;if(crypto)crypto.textContent="CRYPTO OPTIONS · PUBLIC READY"}catch{}}

  mount();refreshScanner();refreshPaper();refreshOptions();timer=setInterval(()=>{refreshScanner();refreshPaper()},2500);window.addEventListener("beforeunload",()=>{if(timer)clearInterval(timer)});
})();
