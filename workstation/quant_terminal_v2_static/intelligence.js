const $=id=>document.getElementById(id);
const params=new URLSearchParams(location.search);
let moduleName=params.get("module")||"adaptive-brain";
let expiryValue=params.get("expiry")||"";

const TITLES={
  "adaptive-brain":"ADAPTIVE QUANT BRAIN",
  "option-chain":"LIVE OPTION CHAIN",
  "oi-iv":"OPEN INTEREST / IMPLIED VOLATILITY",
  "fvg":"FAIR VALUE GAP INTELLIGENCE",
  "liquidity":"LIQUIDITY MAP",
  "order-flow":"ORDER FLOW PROXY",
  "structure":"MARKET STRUCTURE",
  "patterns":"PATTERN ENGINE",
  "heatmaps":"MULTI-MARKET HEATMAPS",
  "portfolio-risk":"PAPER PORTFOLIO RISK",
  "trade-journal":"TRADING JOURNAL",
  "learning":"TRADE LEARNING",
  "strategy-lab":"STRATEGY LAB",
  "self-improvement":"SELF-IMPROVEMENT RESEARCH"
};

const esc=value=>String(value??"").replace(/[&<>"']/g,char=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[char]));
const num=(value,digits=2)=>Number.isFinite(Number(value))?Number(value).toLocaleString(undefined,{maximumFractionDigits:digits}):"—";
const json=value=>esc(JSON.stringify(value??{},null,2));
const arr=value=>Array.isArray(value)?value:[];
const obj=value=>value&&typeof value==="object"&&!Array.isArray(value)?value:{};

function syncQuery(){
  params.set("module",moduleName);
  params.set("symbol",$("symbolSelect").value);
  params.set("universe",$("universeSelect").value);
  params.set("profile",$("profileSelect").value);
  if(expiryValue)params.set("expiry",expiryValue);else params.delete("expiry");
  history.replaceState(null,"",`${location.pathname}?${params}`);
}

function cards(entries){
  return `<div class="cards">${entries.map(([label,value,klass=""])=>`<article class="card"><span class="label">${esc(label)}</span><strong class="value ${klass}">${esc(value)}</strong></article>`).join("")}</div>`;
}

function table(headers,rows){
  if(!rows.length)return `<div class="empty">No verified rows are available for this view yet.</div>`;
  return `<div class="table-wrap"><table><thead><tr>${headers.map(h=>`<th>${esc(h)}</th>`).join("")}</tr></thead><tbody>${rows.join("")}</tbody></table></div>`;
}

function renderOptions(payload){
  const analytics=obj(payload.chain_analytics);
  const chain=arr(payload.chain);
  const maxPain=analytics.max_pain?.strike??analytics.max_pain;
  return cards([
    ["UNDERLYING / SPOT",`${payload.symbol} · ${num(payload.spot)}`],
    ["EXPIRY",payload.expiry?.date||payload.expiry?.expiry||payload.expiry||"NEAREST"],
    ["PCR OI",num(payload.pcr_oi??analytics.pcr_oi,3)],
    ["MAX PAIN",num(maxPain)],
    ["VISIBLE / LISTED",`${chain.length} / ${payload.total_contracts_available??chain.length}`],
    ["GREEKS",payload.greeks_status||"PROVIDER FIELDS"]
  ])+`<div style="margin-top:12px">${table(
    ["TYPE","STRIKE","LTP","BID","ASK","OI","CHG OI","VOLUME","IV","DELTA","GAMMA","THETA","VEGA"],
    chain.map(row=>`<tr>
      <td>${esc(row.option_type)}</td><td>${num(row.strike)}</td><td>${num(row.ltp??row.last_price)}</td>
      <td>${num(row.bid)}</td><td>${num(row.ask)}</td><td>${num(row.open_interest,0)}</td>
      <td>${num(row.change_in_oi,0)}</td><td>${num(row.volume,0)}</td><td>${num(row.iv)}</td>
      <td>${num(row.delta??row.greeks?.delta,3)}</td><td>${num(row.gamma??row.greeks?.gamma,5)}</td>
      <td>${num(row.theta??row.greeks?.theta,3)}</td><td>${num(row.vega??row.greeks?.vega,3)}</td>
    </tr>`)
  )}</div>`;
}

function featureFocus(row,kind){
  if(kind==="fvg")return {fair_value_gaps:row.fair_value_gaps,supply_demand:row.supply_demand};
  if(kind==="liquidity")return {liquidity:row.liquidity,supply_demand:row.supply_demand};
  if(kind==="order-flow")return {order_flow_proxy:row.order_flow_proxy,indicators:row.indicators,structure:row.structure};
  if(kind==="patterns")return {patterns:row.patterns,structure:row.structure};
  return {structure:row.structure,support_resistance:row.support_resistance,patterns:row.patterns};
}

function renderFeatures(payload,kind){
  const rows=arr(payload.timeframes);
  const panels=`<div class="timeframes">${rows.map(row=>`<article class="timeframe">
    <div class="journal-head"><b>${esc(row.timeframe||"TIMEFRAME")}</b><span>${row.fresh===false?"STALE":"VERIFIED"}</span></div>
    <pre>${json(featureFocus(row,kind))}</pre>
  </article>`).join("")}</div>`;
  const decision=obj(payload.decision);
  const summary=cards([
    ["CANDIDATE",decision.candidate_side||"WAIT"],
    ["SCORE",num(decision.score)],
    ["REGIME",decision.regime||"—"],
    ["ALIGNMENT",decision.alignment==null?"—":`${num(decision.alignment,0)}%`],
    ["ENTRY",num(decision.entry)],
    ["STOP / TARGET",`${num(decision.stop)} / ${num(decision.target)}`],
    ["RISK / REWARD",num(decision.risk_reward)]
  ]);
  const caveat=kind==="order-flow"?`<div class="notice">ORDER FLOW PROXY uses completed-bar price, volume, FVG and liquidity-sweep evidence. It does not claim exchange L2/DOM/tick-tape order flow.</div>`:"";
  return caveat+panels+`<div style="margin-top:12px">${summary}</div>`;
}

function renderHeatmap(payload){
  if(!arr(payload.rows).length)return `<div class="empty">${esc(payload.message)}</div>`;
  return `<div class="heatmap">${payload.rows.map(row=>{
    const change=Number(row.percent_change);
    const cls=change>0?"up":change<0?"down":"flat";
    return `<article class="heat ${cls}"><b>${esc(row.symbol)}</b><strong>${num(change)}%</strong><small>${esc(row.state||row.direction||"NO EDGE")} · score ${num(row.score)}</small></article>`;
  }).join("")}</div>`;
}

function renderRisk(payload){
  const p=obj(payload.portfolio);
  return cards([
    ["PAPER EQUITY",num(p.equity)],
    ["TOTAL P&L",num(p.total_pnl),Number(p.total_pnl)>=0?"positive":"negative"],
    ["OPEN POSITIONS",`${p.open_count||0} / ${p.max_open_positions||0}`],
    ["GROSS EXPOSURE",num(p.gross_exposure)],
    ["RISK AT STOPS",`${num(p.risk_at_stops)} · ${num(p.risk_percent_of_equity)}%`],
    ["DRAWDOWN",`${num(p.drawdown)} · ${num(p.drawdown_percent)}%`]
  ])+`<div style="margin-top:12px">${table(
    ["SYMBOL","SIDE","QTY","ENTRY","MARK","STOP","TARGET","P&L"],
    arr(p.positions).map(row=>`<tr>
      <td>${esc(row.symbol)}</td><td>${esc(row.side)}</td><td>${num(row.quantity,6)}</td>
      <td>${num(row.entry??row.entry_price)}</td><td>${num(row.mark??row.mark_price)}</td>
      <td>${num(row.stop??row.stop_price)}</td><td>${num(row.target??row.target_price)}</td>
      <td class="${Number(row.pnl??row.unrealized_pnl)>=0?"positive":"negative"}">${num(row.pnl??row.unrealized_pnl)}</td>
    </tr>`)
  )}</div>`;
}

function snapshotSvg(bars){
  if(!Array.isArray(bars)||bars.length<2)return `<div class="empty">Frozen entry chart snapshot was not captured for this older trade.</div>`;
  const rows=bars.slice(-80);
  const low=Math.min(...rows.map(r=>Number(r.low))),high=Math.max(...rows.map(r=>Number(r.high)));
  const range=Math.max(high-low,.000001),w=800,h=200,step=w/rows.length;
  const candles=rows.map((r,i)=>{
    const x=i*step+step/2,y=v=>10+(high-Number(v))/range*(h-20);
    const open=y(r.open),close=y(r.close),top=Math.min(open,close),height=Math.max(1,Math.abs(open-close));
    const color=Number(r.close)>=Number(r.open)?"#72f2aa":"#ff7187";
    return `<line x1="${x}" y1="${y(r.high)}" x2="${x}" y2="${y(r.low)}" stroke="${color}"/><rect x="${x-step*.28}" y="${top}" width="${Math.max(2,step*.56)}" height="${height}" fill="${color}"/>`;
  }).join("");
  return `<div class="chart-snapshot"><svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none">${candles}</svg></div>`;
}

function renderJournal(payload){
  const trades=arr(payload.closed_positions);
  if(!trades.length)return `<div class="empty">No closed synthetic paper trades are available.</div>`;
  return `<div class="journal-grid">${trades.map(row=>{
    const meta=obj(row.metadata),patterns=arr(meta.chart_patterns),indicators=meta.indicator_snapshot||meta.feature_snapshot?.indicators||{};
    const bars=meta.entry_chart_snapshot?.bars||meta.entry_chart_snapshot||[];
    return `<article class="journal-card">
      <div class="journal-head"><b>${esc(row.symbol)} · ${esc(row.side)} · ${esc(row.timeframe||meta.timeframe||"")}</b>
      <span class="${Number(row.realized_pnl)>=0?"positive":"negative"}">${num(row.realized_pnl)} · ${esc(row.exit_reason||"")}</span></div>
      <p class="journal-reason">${esc(meta.entry_reason||meta.message||"Durable entry rationale was not recorded for this older trade.")}</p>
      <div class="tags">
        <span class="tag">${esc(row.strategy||meta.strategy_id||"STRATEGY UNKNOWN")}</span>
        <span class="tag">score ${num(row.score??meta.score)}</span><span class="tag">entry ${num(row.entry)}</span>
        <span class="tag">SL ${num(row.stop)}</span><span class="tag">target ${num(row.target)}</span>
        <span class="tag">MFE ${num(row.mfe_r)}R</span><span class="tag">MAE ${num(row.mae_r)}R</span>
        ${patterns.map(p=>`<span class="tag">${esc(p.name||p.pattern||p)}</span>`).join("")}
      </div>${snapshotSvg(bars)}
      <details><summary>FULL ENTRY EVIDENCE</summary><pre>${json({votes:meta.votes,decisions:meta.decisions,regime:meta.regime,risk_model:meta.risk_model,exit_policy:meta.exit_policy,indicators,patterns,contradictions:meta.contradictions})}</pre></details>
    </article>`;
  }).join("")}</div>`;
}

function renderAdaptive(payload){
  const d=obj(payload.decision),s=obj(d.structure),i=obj(d.indicators),votes=arr(d.votes);
  const status=String(d.side||"WAIT").toUpperCase();
  return cards([
    ["SIDE",status,status==="LONG"?"positive":status==="SHORT"?"negative":""],
    ["SCORE",num(d.score,1)],
    ["REGIME",d.regime||"—"],
    ["TIMEFRAME",payload.timeframe||d.timeframe||"—"],
    ["ENTRY",num(d.entry)],
    ["STOP",num(d.stop)],
    ["TARGET",num(d.target)],
    ["R:R",num(d.risk_reward)]
  ])+`<div class="split-grid">
    <article class="timeframe"><div class="journal-head"><b>STRUCTURE / LIQUIDITY</b><span>${esc(s.bias||"—")}</span></div><pre>${json(s)}</pre></article>
    <article class="timeframe"><div class="journal-head"><b>INDICATORS</b><span>VERIFIED</span></div><pre>${json(i)}</pre></article>
  </div>
  <div style="margin-top:12px">${table(
    ["STRATEGY","FAMILY","SIDE","SCORE","EVIDENCE"],
    votes.map(v=>`<tr><td>${esc(v.strategy)}</td><td>${esc(v.family)}</td><td>${esc(v.side)}</td><td>${num(v.score,1)}</td><td>${esc(arr(v.evidence).join(" · "))}</td></tr>`)
  )}</div>`;
}

function renderLearning(payload){
  const learning=obj(payload.learning),board=arr(payload.strategy_leaderboard),mistakes=arr(payload.mistakes),recent=arr(learning.recent_outcomes);
  const governance=obj(learning.governance);
  return cards([
    ["RECORDED OUTCOMES",String(recent.length)],
    ["STRATEGIES TRACKED",String(board.length)],
    ["FAMILIES",String(Object.keys(obj(payload.family_weights)).length)],
    ["MIN SAMPLES / WEIGHT",String(governance.minimum_samples_for_weight??12)],
    ["AUTO CODE REWRITE",governance.automatic_strategy_code_rewrite?"ENABLED":"DISABLED"],
    ["LIVE EXECUTION",governance.live_execution?"ENABLED":"LOCKED"]
  ])+`<div class="section-block"><div class="eyebrow">STRATEGY LEADERBOARD</div>${table(
    ["STRATEGY","TRADES","WIN RATE","AVG R","P&L","WEIGHT","WEIGHTING"],
    board.map(r=>`<tr><td>${esc(r.strategy)}</td><td>${num(r.trades,0)}</td><td>${r.win_rate==null?"—":num(r.win_rate*100,1)+"%"}</td><td>${num(r.avg_r,3)}</td><td>${num(r.pnl)}</td><td>${num(r.weight,3)}</td><td>${r.eligible_for_weighting?"ELIGIBLE":"WAITING"}</td></tr>`)
  )}</div>
  <div class="section-block"><div class="eyebrow">MISTAKE HYPOTHESES</div>${table(
    ["HYPOTHESIS","COUNT"],
    mistakes.map(r=>`<tr><td>${esc(r.mistake)}</td><td>${num(r.count,0)}</td></tr>`)
  )}</div>`;
}

function renderStrategyLab(payload){
  const best=obj(payload.best_candidate),candidate=obj(best.candidate),bt=obj(best.backtest),wf=obj(best.walk_forward),rows=arr(payload.candidates);
  return cards([
    ["SYMBOL / TF",`${payload.symbol} · ${payload.timeframe||"—"}`],
    ["BEST CANDIDATE",candidate.name||"NONE"],
    ["STATUS",best.status||"REJECT",best.status==="PAPER_CHALLENGER"?"positive":""],
    ["QUALITY SCORE",num(best.quality_score,2)],
    ["TRADES",num(bt.trades,0)],
    ["EXPECTANCY",`${num(bt.expectancy_r,3)} R`],
    ["PROFIT FACTOR",num(bt.profit_factor,2)],
    ["MAX DRAWDOWN",`${num(bt.max_drawdown_r,2)} R`],
    ["WALK-FORWARD",wf.passed?"PASS":"FAIL",wf.passed?"positive":"negative"]
  ])+`<div class="notice">Research candidates remain paper challengers only. They are not auto-promoted to production or live execution.</div>
  <div class="section-block">${table(
    ["CANDIDATE","FAMILY","REGIME","STATUS","QUALITY","TRADES","EXPECTANCY R","PF","MAX DD R","WALK-FWD"],
    rows.map(r=>{const c=obj(r.candidate),b=obj(r.backtest),w=obj(r.walk_forward);return `<tr>
      <td>${esc(c.name)}</td><td>${esc(c.family)}</td><td>${esc(c.regime)}</td><td>${esc(r.status)}</td>
      <td>${num(r.quality_score,2)}</td><td>${num(b.trades,0)}</td><td>${num(b.expectancy_r,3)}</td>
      <td>${num(b.profit_factor,2)}</td><td>${num(b.max_drawdown_r,2)}</td><td>${w.passed?"PASS":"FAIL"}</td>
    </tr>`})
  )}</div>`;
}

function renderSelfImprovement(payload){
  const s=obj(payload.self_improvement),report=obj(s.last_report),challengers=arr(report.challengers);
  return cards([
    ["STATE",s.running?"RUNNING":"IDLE",s.running?"positive":""],
    ["CYCLES",num(s.cycles,0)],
    ["ERRORS",num(s.errors,0),Number(s.errors)>0?"negative":""],
    ["LAST RUN",s.last_run_at?new Date(s.last_run_at).toLocaleString():"NOT RUN YET"],
    ["INTERVAL",`${num(s.interval_seconds,0)} sec`],
    ["CHALLENGERS",String(challengers.length)]
  ])+`<div class="notice">The coordinator may research and store PAPER_CHALLENGER proposals. Automatic production rewrites and live promotion remain disabled.</div>
  <div class="section-block">${table(
    ["SYMBOL","TIMEFRAME","CANDIDATE","QUALITY","STATUS"],
    challengers.map(r=>`<tr><td>${esc(r.symbol)}</td><td>${esc(r.timeframe)}</td><td>${esc(r.candidate?.name||"—")}</td><td>${num(r.quality_score,2)}</td><td>${esc(r.status)}</td></tr>`)
  )}</div>
  <details class="section-block"><summary>LAST RESEARCH REPORT</summary><pre>${json(report)}</pre></details>`;
}

function render(payload){
  if(!payload.success){
    const login=/FYERS/i.test(payload.message||"")?'<button id="moduleFyersLogin" type="button">OPEN FYERS DAILY LOGIN</button>':"";
    return `<div class="error">${esc(payload.message||"Verified module data is unavailable.")}${login}</div>`;
  }
  if(["option-chain","oi-iv"].includes(moduleName))return renderOptions(payload);
  if(["structure","fvg","liquidity","order-flow","patterns"].includes(moduleName))return renderFeatures(payload,moduleName);
  if(moduleName==="adaptive-brain")return renderAdaptive(payload);
  if(moduleName==="heatmaps")return renderHeatmap(payload);
  if(moduleName==="portfolio-risk")return renderRisk(payload);
  if(moduleName==="trade-journal")return renderJournal(payload);
  if(moduleName==="learning")return renderLearning(payload);
  if(moduleName==="strategy-lab")return renderStrategyLab(payload);
  if(moduleName==="self-improvement")return renderSelfImprovement(payload);
  return `<pre>${json(payload)}</pre>`;
}

function updateExpiryControl(payload){
  const select=$("expirySelect"),isOptions=["option-chain","oi-iv"].includes(moduleName);
  select.hidden=!isOptions;
  if(!isOptions)return;
  const values=Array.isArray(payload.available_expiries)?payload.available_expiries:[];
  const selected=payload.expiry?.date||payload.expiry?.expiry||payload.expiry||expiryValue||"";
  select.replaceChildren(new Option("NEAREST EXPIRY",""),...values.map(value=>new Option(value,value)));
  if(values.includes(String(selected)))select.value=String(selected);else select.value="";
  expiryValue=select.value;
}

async function launchFyersLogin(){
  const button=$("moduleFyersLogin");
  if(button){button.disabled=true;button.textContent="OPENING LOGIN…";}
  try{
    const response=await fetch("/api/fyers/login",{method:"POST",headers:{"Content-Type":"application/json"},body:"{}"});
    const payload=await response.json();
    $("moduleMessage").textContent=payload.message||"FYERS login opened in a local terminal.";
  }catch(error){$("moduleMessage").textContent=error.message;}
}

async function load(){
  syncQuery();
  document.querySelectorAll("[data-module]").forEach(b=>b.classList.toggle("active",b.dataset.module===moduleName));
  $("moduleTitle").textContent=TITLES[moduleName]||moduleName.toUpperCase();
  $("profileState").textContent=`PROFILE: ${$("profileSelect").value.replaceAll("_"," ").toUpperCase()}`;
  $("moduleContent").innerHTML='<div class="loading">Loading verified evidence…</div>';
  const q=new URLSearchParams({
    module:moduleName,
    symbol:$("symbolSelect").value,
    universe:$("universeSelect").value,
    profile:$("profileSelect").value
  });
  if(expiryValue)q.set("expiry",expiryValue);
  try{
    const response=await fetch(`/api/intelligence/module?${q}`);
    const payload=await response.json();
    updateExpiryControl(payload);
    $("moduleMessage").textContent=payload.message||"Module data loaded.";
    $("sourceState").textContent=`SOURCE: ${payload.source||payload.provider||"LOCAL GOVERNED ENGINE"}`;
    $("generatedState").textContent=payload.generated_at?new Date(payload.generated_at).toLocaleString():"CURRENT SNAPSHOT";
    $("moduleContent").innerHTML=render(payload);
    $("moduleFyersLogin")?.addEventListener("click",launchFyersLogin);
  }catch(error){
    $("moduleContent").innerHTML=`<div class="error">${esc(error.message)}</div>`;
  }
}

document.querySelectorAll("[data-module]").forEach(button=>button.addEventListener("click",()=>{moduleName=button.dataset.module;load();}));
$("refreshButton").addEventListener("click",load);
$("symbolSelect").addEventListener("change",()=>{expiryValue="";load();});
$("profileSelect").addEventListener("change",load);
$("universeSelect").addEventListener("change",load);
$("expirySelect").addEventListener("change",event=>{expiryValue=event.target.value;load();});

$("symbolSelect").value=params.get("symbol")||"NIFTY";
$("profileSelect").value=params.get("profile")||"adaptive_intraday";
$("universeSelect").value=params.get("universe")||"NIFTY50";
load();
