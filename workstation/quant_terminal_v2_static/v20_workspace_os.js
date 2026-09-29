/* JARVIS V20 — Full Workspace Operating System */
(()=>{"use strict";
if(window.__JARVIS_V20_OS__)return;window.__JARVIS_V20_OS__=true;
const $=id=>document.getElementById(id), esc=v=>String(v??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const num=(v,d=2)=>{const n=Number(v);return Number.isFinite(n)?n.toLocaleString("en-IN",{maximumFractionDigits:d,minimumFractionDigits:d}):"—"};
const state={workspace:"INTRADAY",option:{underlying:"NIFTY",expiry:"",range:12,view:"PRICE",rows:[],spot:null,pcr:null,analytics:{},expiries:[],legs:[],runtime:null,loading:false}};
const U=[["NIFTY","NIFTY 50"],["BANKNIFTY","BANK NIFTY"],["SENSEX","SENSEX"]];
let optionSeq=0,optionAbort=null,optionRuntimeTimer=null,optionChartTimer=null;
const optionCharts={underlying:null,contract:null};

async function getJSON(url,timeout=8000){
 const c=new AbortController(),t=setTimeout(()=>c.abort(),timeout);
 try{const r=await fetch(url,{cache:"no-store",signal:c.signal});const p=await r.json().catch(()=>({}));return {ok:r.ok,p};}
 catch(e){return {ok:false,p:{success:false,message:e.name==="AbortError"?"Request timed out":e.message}}}finally{clearTimeout(t)}
}
function activeWorkspace(){return String(document.querySelector(".workspace-modes button.active")?.dataset.workspace||state.workspace||"INTRADAY").toUpperCase()}
function hideLegacy(){/* V20 is an orchestration layer. Proven V17/V18/V19 surfaces stay visible and authoritative. */}
function ensure(){
 const w=document.querySelector(".workspace");if(!w)return null;
 let root=$("v20WorkspaceOS");
 if(!root){root=document.createElement("section");root.id="v20WorkspaceOS";const modes=w.querySelector(".workspace-modes");if(modes)modes.after(root);else w.appendChild(root)}
 hideLegacy();return root
}
function chip(label,value,kind=""){return '<div class="v20-chip '+kind+'"><small>'+label+'</small><b>'+esc(value)+'</b></div>'}
function header(w){
 const titles={INTRADAY:["INTRADAY COMMAND","Session execution · VWAP · OR · momentum · risk"],SWING:["SWING RESEARCH","Multi-session setups · trend · catalysts · position geometry"],INVESTMENT:["INVESTMENT DESK","Portfolio · fundamentals · valuation · allocation · thesis"],OPTIONS:["OPTIONS INTELLIGENCE","Dedicated derivatives desk · chain · Greeks · OI / IV · paper strategy"]};
 const t=titles[w]||titles.INTRADAY;
 return '<div class="v20-head"><div class="v20-brand"><div class="v20-kicker">JARVIS V20 · WORKSPACE OS</div><div class="v20-title">'+t[0]+'</div><div class="v20-sub">'+t[1]+'</div></div><div class="v20-status" id="v20Status">'+chip("WORKSPACE",w)+chip("FYERS","CHECKING","warn")+chip("HEALTH","CHECKING","warn")+chip("EXECUTION","PAPER LOCKED","ok")+'</div><div class="v20-actions"><button data-v20="refresh">REFRESH</button><button data-v20="reset">RESET</button></div></div>'
}
function contexts(w){
 const map={INTRADAY:["Signals","Market Structure","Risk","Execution"],SWING:["Setups","Trend","Catalysts","Risk"],INVESTMENT:["Portfolio","Fundamentals","Valuation","Watchlist"],OPTIONS:["Chain","Greeks","OI / IV","Strategy"]};
 return '<div class="v20-context"><span class="v20-muted">DESK</span>'+map[w].map((x,i)=>'<button class="'+(i===0?"active":"")+'">'+x+'</button>').join("")+'</div>'
}

const V20_MARKETS=[
 ["NIFTY","NIFTY 50"],["BANKNIFTY","BANK NIFTY"],["SENSEX","SENSEX"],
 ["CRUDEOIL","CRUDE OIL"],["GOLD","GOLD"],["SILVER","SILVER"],
 ["NATURALGAS","NAT GAS"],["BTC","BITCOIN"],["ETH","ETHEREUM"],["SOL","SOLANA"]
];
const V20_TFS=["1m","3m","5m","15m","30m","1h","2h","4h","1d"];
const v20ChartState={layout:4,slots:[],generation:0,active:false,loading:false};
function v20ChartCount(v){return Math.max(1,Math.min(8,Math.trunc(Number(v)||4)))}
function v20ChartDefaults(workspace){
 const tf=workspace==="SWING"?"1h":workspace==="INVESTMENT"?"1d":"5m";
 return ["NIFTY","BANKNIFTY","SENSEX","CRUDEOIL","GOLD","BTC","ETH","SILVER"].map((symbol,i)=>({symbol,timeframe:tf}));
}
function v20ChartGrid(){
 const slots=v20ChartDefaults(state.workspace);
 while(v20ChartState.slots.length<v20ChartState.layout)v20ChartState.slots.push({...slots[v20ChartState.slots.length]});
 v20ChartState.slots=v20ChartState.slots.slice(0,v20ChartState.layout);
 return '<div class="v20-chart-toolbar"><div class="v20-chart-toolbar-group"><span>CHARTS</span>'+[1,2,3,4,5,6,7,8].map(n=>'<button class="v20-chart-layout '+(n===v20ChartState.layout?"active":"")+'" data-v20-layout="'+n+'">'+n+'</button>').join('')+'</div><div class="v20-chart-toolbar-group"><span>TIMEFRAME</span>'+["1m","5m","15m","1h","4h","1d"].map(tf=>'<button class="v20-chart-tf" data-v20-tf="'+tf+'">'+tf+'</button>').join('')+'</div><button class="v20-btn v20-chart-refresh" data-v20="charts-refresh">RELOAD DATA</button></div>'+
 '<div id="v20ChartGrid" class="v20-chart-grid layout-'+v20ChartState.layout+'">'+v20ChartState.slots.map((s,i)=>'<div class="v20-chart-card" data-v20-chart="'+i+'"><div class="v20-chart-head"><div><b>'+esc((V20_MARKETS.find(x=>x[0]===s.symbol)||["",s.symbol])[1])+'</b><span>'+s.timeframe+' · QUEUED</span></div><select data-v20-chart-symbol="'+i+'">'+V20_MARKETS.map(x=>'<option value="'+x[0]+'" '+(x[0]===s.symbol?"selected":"")+'>'+x[1]+'</option>').join('')+'</select></div><div class="v20-chart-host" id="v20ChartHost'+i+'"></div><div class="v20-chart-foot"><span data-v20-chart-status="'+i+'">Waiting for verified candles…</span><span>ENTRY · STOP · TARGET · PAPER</span></div></div>').join('')+'</div>';
}
function v20ChartOptions(){
 return {autoSize:true,layout:{background:{type:"solid",color:"#040b10"},textColor:"#8eabb7",fontFamily:"Arial"},grid:{vertLines:{color:"rgba(75,140,166,.08)"},horzLines:{color:"rgba(75,140,166,.08)"}},rightPriceScale:{borderColor:"#173849"},timeScale:{borderColor:"#173849",timeVisible:true,secondsVisible:false,rightOffset:5,barSpacing:7},crosshair:{mode:LightweightCharts.CrosshairMode.Normal}};
}
function v20ApplyRiskLines(chart,series){
 try{
  const data=series.data?series.data():null;
 }catch{}
}
async function v20FetchCandles(slot,index,generation){
 const status=document.querySelector('[data-v20-chart-status="'+index+'"]'),host=document.getElementById("v20ChartHost"+index);
 if(!host)return;
 if(generation!==v20ChartState.generation)return;
 if(typeof LightweightCharts==="undefined"){if(status)status.textContent="Chart library unavailable";return}
 if(status)status.textContent="Loading "+slot.symbol+" "+slot.timeframe+"…";
 const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),22000);
 try{
  const q=new URLSearchParams({symbol:slot.symbol,timeframe:slot.timeframe,bars:"500",display:"1"});
  const r=await fetch("/api/candles?"+q,{cache:"no-store",signal:controller.signal});
  const p=await r.json().catch(()=>({}));
  if(generation!==v20ChartState.generation)return;
  if(!r.ok||p.success!==true||!Array.isArray(p.candles)||!p.candles.length)throw new Error(p.message||p.reason||"Verified candles unavailable");
  host.innerHTML="";
  const chart=LightweightCharts.createChart(host,v20ChartOptions());
  const candles=chart.addSeries(LightweightCharts.CandlestickSeries,{upColor:"#61e69a",downColor:"#ff667d",wickUpColor:"#61e69a",wickDownColor:"#ff667d",borderVisible:false});
  const rows=p.candles.map(x=>({time:Number(x.time??x.timestamp),open:Number(x.open),high:Number(x.high),low:Number(x.low),close:Number(x.close)})).filter(x=>[x.time,x.open,x.high,x.low,x.close].every(Number.isFinite)).sort((a,b)=>a.time-b.time);
  candles.setData(rows);
  const ema=chart.addSeries(LightweightCharts.LineSeries,{color:"#5cdbff",lineWidth:1,priceLineVisible:false,lastValueVisible:false});
  const period=20,alpha=2/(period+1);let value=rows.slice(0,period).reduce((a,x)=>a+x.close,0)/period;const emaRows=rows.length>=period?[{time:rows[period-1].time,value}]:[];
  for(let j=period;j<rows.length;j++){value=alpha*rows[j].close+(1-alpha)*value;emaRows.push({time:rows[j].time,value})}
  ema.setData(emaRows);
  chart.timeScale().fitContent();
  v20ChartState.slots[index]={...slot,chart,candles,rows};
  if(status)status.textContent=(p.source||"FYERS")+" · "+rows.length+" bars · "+(p.data_quality||"VERIFIED");
  setTimeout(()=>{try{chart.resize(host.clientWidth,host.clientHeight);chart.timeScale().fitContent()}catch{}},0);
 }catch(e){
  if(status)status.textContent=(e.name==="AbortError"?"Timed out":(e.message||"Market data unavailable"))+" · existing workspace remains usable";
 }finally{clearTimeout(timer)}
}
async function v20LoadCharts(){
 const grid=document.getElementById("v20ChartGrid");if(!grid)return;
 v20ChartState.generation+=1;const generation=v20ChartState.generation;
 for(const slot of v20ChartState.slots){if(slot.chart){try{slot.chart.remove()}catch{};delete slot.chart}}
 v20ChartState.active=true;
 const order=v20ChartState.slots.map((_,i)=>i);
 for(let i=0;i<order.length;i+=2){
  if(generation!==v20ChartState.generation)return;
  await Promise.allSettled(order.slice(i,i+2).map(idx=>v20FetchCandles(v20ChartState.slots[idx],idx,generation)));
 }
}
function v20BindCharts(){
 document.querySelectorAll("[data-v20-layout]").forEach(b=>b.onclick=()=>{v20ChartState.layout=v20ChartCount(b.dataset.v20Layout);render()});
 document.querySelectorAll("[data-v20-tf]").forEach(b=>b.onclick=()=>{const tf=b.dataset.v20Tf;const idx=Math.max(0,Number(document.querySelector(".v20-chart-card.active")?.dataset.v20Chart||0));if(v20ChartState.slots[idx])v20ChartState.slots[idx].timeframe=tf;render()});
 document.querySelectorAll("[data-v20-chart-symbol]").forEach(s=>s.onchange=()=>{const i=Number(s.dataset.v20ChartSymbol);if(v20ChartState.slots[i])v20ChartState.slots[i].symbol=s.value;render()});
}

function canonicalControls(){
 const layouts=[1,2,3,4,5,6,7,8].map(n=>'<button data-v20-canonical="layout" data-layout="'+n+'">'+n+'</button>').join('');
 const tfs=["1m","5m","15m","1h","1d"].map(tf=>'<button data-v20-canonical="tf" data-timeframe="'+tf+'">'+tf+'</button>').join('');
 return '<div class="v20-panel v20-canonical-controls"><div class="v20-panel-head"><div><div class="v20-panel-title">CANONICAL V16 / V17 TRADING SURFACE</div><div class="v20-muted">V20 orchestrates the proven chart, intelligence, paper-desk and risk engines below. No duplicate trading engine is created here.</div></div><div class="v20-actions"><button data-v20-canonical="fit">FIT</button><button data-v20-canonical="reload">RELOAD</button></div></div><div class="v20-canonical-layout"><span>CHARTS</span>'+layouts+'<span>TF</span>'+tfs+'</div></div>';
}

function intraday(){
 return '<div class="v20-body"><div class="v20-main">'+canonicalControls()+'</div><aside class="v20-rail"><div class="v20-panel"><div class="v20-panel-title">V20 INTEGRATION</div><div class="v20-list"><div><span>Chart engine</span><b>V16 CANONICAL</b></div><div><span>Intelligence</span><b>V17 RUNTIME</b></div><div><span>Paper Desk</span><b>AUTHORITATIVE</b></div><div><span>Execution</span><b>LOCKED</b></div></div></div><div class="v20-panel"><div class="v20-panel-title">MARKETS</div><div class="v20-list"><div><span>NIFTY 50</span><b>ROUTED</b></div><div><span>BANK NIFTY</span><b>ROUTED</b></div><div><span>SENSEX</span><b>ROUTED</b></div><div><span>CRUDE OIL</span><b>ROUTED</b></div><div><span>GOLD</span><b>ROUTED</b></div><div><span>BITCOIN</span><b>ROUTED</b></div></div></div></aside></div>'
}
function swing(){
 return '<div class="v20-body"><div class="v20-main">'+canonicalControls()+'</div><aside class="v20-rail"><div class="v20-panel"><div class="v20-panel-title">SWING ROUTING</div><div class="v20-list"><div><span>Trend engine</span><b>V17 / CANONICAL</b></div><div><span>Setups</span><b>CANONICAL</b></div><div><span>Risk geometry</span><b>CANONICAL</b></div><div><span>Execution</span><b>PAPER LOCKED</b></div></div></div></aside></div>'
}

function investment(){
 return '<div class="v20-invest"><div class="v20-invest-main"><div class="v20-panel"><div class="v20-panel-head"><div><div class="v20-panel-title">PORTFOLIO CONTROL</div><div class="v20-muted">Investment workspace is independent from Intraday and Options execution logic.</div></div><button class="v20-btn" style="width:auto" data-v20="research">RESEARCH</button></div><div class="v20-grid4" style="margin-top:6px"><div class="v20-metric"><small>INVESTED</small><b>—</b></div><div class="v20-metric"><small>PORTFOLIO P&amp;L</small><b>—</b></div><div class="v20-metric"><small>EXPOSURE</small><b>—</b></div><div class="v20-metric"><small>WATCHLIST</small><b>—</b></div></div></div><div class="v20-research-grid"><div class="v20-research-card"><b>Fundamentals</b><p>Revenue · EBITDA · EPS · ROE · ROCE · debt · FCF · growth.</p></div><div class="v20-research-card"><b>Valuation</b><p>P/E · EV/EBITDA · P/B · PEG · FCF yield · historical ranges.</p></div><div class="v20-research-card"><b>Thesis</b><p>Bull · base · bear · catalysts · invalidation · time horizon.</p></div><div class="v20-research-card"><b>Allocation</b><p>Position sizing · concentration · sector exposure · cash buffer.</p></div><div class="v20-research-card"><b>Watchlist</b><p>Candidate → researching → thesis ready → monitored.</p></div><div class="v20-research-card"><b>Risk</b><p>Drawdown · concentration · correlation · thesis-break monitoring.</p></div></div></div><aside class="v20-invest-side"><div class="v20-panel"><div class="v20-panel-title">RESEARCH GATES</div><div class="v20-list"><div><span>Fundamentals</span><b>READY WHEN DATA CONNECTS</b></div><div><span>Valuation</span><b>READY WHEN DATA CONNECTS</b></div><div><span>Thesis</span><b>RESEARCH</b></div><div><span>Execution</span><b>PAPER / LOCKED</b></div></div></div><div class="v20-panel"><div class="v20-panel-title">NO SIGNAL BLEED</div><div class="v20-note">Intraday signals, option-chain legs and short-horizon triggers do not automatically become Investment decisions.</div></div></aside></div>'
}
function optionShell(){
 return '<div class="v20-options"><aside class="v20-options-left"><div class="v20-panel"><div class="v20-panel-title">UNDERLYING</div><select id="v20OptUnderlying" class="v20-select">'+U.map(x=>'<option value="'+x[0]+'">'+x[1]+'</option>').join("")+'</select><div class="v20-panel-title" style="margin-top:9px">EXPIRY</div><select id="v20OptExpiry" class="v20-select"><option value="">NEAREST EXPIRY</option></select><div class="v20-panel-title" style="margin-top:9px">STRIKE WINDOW</div><select id="v20OptRange" class="v20-select"><option value="8">±8 STRIKES</option><option value="12" selected>±12 STRIKES</option><option value="20">±20 STRIKES</option></select><button class="v20-btn primary" id="v20OptRefresh" style="margin-top:7px">REFRESH ENGINE</button></div><div class="v20-panel"><div class="v20-panel-title">LIVE DECISION</div><div id="v20DecisionState" class="v20-auto-state">WAITING FOR VERIFIED MARKET DATA…</div><div id="v20DecisionReason" class="v20-note" style="margin-top:6px">The Options Agent evaluates the underlying, chain, liquidity and risk gates independently.</div></div><div class="v20-panel"><div class="v20-panel-title">CHAIN ANALYTICS</div><div class="v20-list"><div><span>Spot</span><b id="v20Spot">—</b></div><div><span>PCR OI</span><b id="v20PCR">—</b></div><div><span>Call wall</span><b id="v20CallWall">—</b></div><div><span>Put wall</span><b id="v20PutWall">—</b></div><div><span>Max pain</span><b id="v20MaxPain">—</b></div></div></div><div class="v20-panel"><div class="v20-panel-title">DATA LANE</div><div id="v20OptState" class="v20-note">Dedicated Options Agent · port 8796 · paper only.</div></div></aside><main class="v20-options-center"><div class="v20-panel v20-options-command"><div class="v20-panel-head"><div><div class="v20-panel-title">AUTONOMOUS OPTIONS COMMAND</div><div class="v20-muted">Live underlying structure + selected contract price action. The agent chooses the contract; JARVIS records only synthetic paper positions.</div></div><div class="v20-auto-badge">AUTO PAPER · LIVE ORDERS LOCKED</div></div><div class="v20-grid4" id="v20DecisionMetrics"></div></div><div class="v20-options-charts"><div class="v20-panel v20-option-chart-panel"><div class="v20-panel-head"><div><div class="v20-panel-title">UNDERLYING · LIVE 5M</div><div class="v20-muted" id="v20UnderlyingChartMeta">Waiting…</div></div></div><div id="v20OptionUnderlyingChart" class="v20-option-chart"></div></div><div class="v20-panel v20-option-chart-panel"><div class="v20-panel-head"><div><div class="v20-panel-title">SELECTED OPTION · LIVE 5M</div><div class="v20-muted" id="v20ContractChartMeta">Agent has not selected a contract.</div></div></div><div id="v20OptionContractChart" class="v20-option-chart"></div></div></div><div class="v20-panel"><div class="v20-panel-head"><div><div class="v20-panel-title">OPTION CHAIN · V20</div><div class="v20-muted">Calls / strikes / puts with OI, IV and Greeks. ATM and the agent-selected contract are highlighted.</div></div><div class="v20-tabs">'+["PRICE","GREEKS","STRADDLE"].map(x=>'<button class="v20-btn '+(x==="PRICE"?"active":"")+'" data-v20-opt-view="'+x+'">'+x+'</button>').join("")+'</div></div></div><div id="v20OptSummary" class="v20-grid4"></div><div class="v20-chain"><table><thead id="v20OptHead"></thead><tbody id="v20OptRows"></tbody></table></div></main><aside class="v20-options-right"><div class="v20-panel"><div class="v20-panel-title">AUTONOMOUS CONTRACT</div><div id="v20SelectedContract" class="v20-selected-contract"><b>WAITING</b><span>No verified contract selected.</span></div></div><div class="v20-panel"><div class="v20-panel-title">PAPER POSITION</div><div id="v20PaperPosition" class="v20-note">No autonomous paper position is currently reported.</div></div><div class="v20-panel"><div class="v20-panel-title">DECISION GATES</div><div id="v20DecisionGates" class="v20-gates"></div></div><div class="v20-panel"><div class="v20-panel-title">STRATEGY LAB</div><div class="v20-note">The existing strategy lab, Greeks, OI/IV, journal and learning surfaces remain available. This desk adds a continuous contract-selection lane rather than replacing them.</div><div id="v20Legs" class="v20-legs" style="margin-top:6px"></div><button class="v20-btn primary" id="v20AddLeg" style="margin-top:6px">ADD ATM LEG</button><div id="v20Payoff" class="v20-note" style="margin-top:7px"></div></div></aside></div>'
}
function stopOptionRuntime(){
 if(optionRuntimeTimer){clearInterval(optionRuntimeTimer);optionRuntimeTimer=null}
 if(optionChartTimer){clearInterval(optionChartTimer);optionChartTimer=null}
 optionSeq+=1;if(optionAbort){try{optionAbort.abort()}catch{};optionAbort=null}
 for(const key of ["underlying","contract"]){if(optionCharts[key]){try{optionCharts[key].remove()}catch{};optionCharts[key]=null}}
}
function chartOptions(){
 return {autoSize:true,layout:{background:{type:"solid",color:"#040b10"},textColor:"#8eabb7",fontFamily:"Arial"},grid:{vertLines:{color:"rgba(75,140,166,.08)"},horzLines:{color:"rgba(75,140,166,.08)"}},rightPriceScale:{borderColor:"#173849"},timeScale:{borderColor:"#173849",timeVisible:true,secondsVisible:false,rightOffset:6,barSpacing:7},crosshair:{mode:LightweightCharts.CrosshairMode.Normal}};
}
function renderLiveChart(hostId,key,candles,title){
 const host=$(hostId);if(!host||typeof LightweightCharts==="undefined")return;
 const rows=(candles||[]).map(x=>({time:Number(x.time??x.timestamp),open:Number(x.open),high:Number(x.high),low:Number(x.low),close:Number(x.close)})).filter(x=>[x.time,x.open,x.high,x.low,x.close].every(Number.isFinite)).sort((a,b)=>a.time-b.time);
 if(rows.length<2)return;
 if(optionCharts[key]){try{optionCharts[key].remove()}catch{}}
 host.innerHTML="";
 const chart=LightweightCharts.createChart(host,chartOptions());
 const series=chart.addSeries(LightweightCharts.CandlestickSeries,{upColor:"#61e69a",downColor:"#ff667d",wickUpColor:"#61e69a",wickDownColor:"#ff667d",borderVisible:false});
 series.setData(rows);
 const ema=chart.addSeries(LightweightCharts.LineSeries,{color:"#5cdbff",lineWidth:1,priceLineVisible:false,lastValueVisible:false});
 const period=20,alpha=2/(period+1);let value=rows.slice(0,period).reduce((a,x)=>a+x.close,0)/Math.max(1,Math.min(period,rows.length));const emaRows=rows.length>=period?[{time:rows[period-1].time,value}]:[];
 for(let j=period;j<rows.length;j++){value=alpha*rows[j].close+(1-alpha)*value;emaRows.push({time:rows[j].time,value})}
 if(emaRows.length)ema.setData(emaRows);
 chart.timeScale().fitContent();optionCharts[key]=chart;
 setTimeout(()=>{try{chart.resize(host.clientWidth,host.clientHeight);chart.timeScale().fitContent()}catch{}},0);
}
async function refreshSelectedOptionChart(){
 const selected=state.option.runtime?.selected_contract;if(!selected?.symbol)return;
 const q=new URLSearchParams({provider:"FYERS",instrument:selected.symbol,timeframe:"5m",bars:"180"});
 try{
  const r=await getJSON("/api/option-candles?"+q,9000);if(!r.ok||r.p?.success!==true)return;
  renderLiveChart("v20OptionContractChart","contract",r.p.candles||[],"Selected option");
  const meta=$("v20ContractChartMeta");if(meta)meta.textContent=selected.symbol+" · "+(selected.option_type||"OPTION")+" · "+(r.p.data_quality||"VERIFIED");
 }catch{}
}
async function loadOptionRuntime(){
 const id=++optionSeq;state.option.loading=true;
 const u=state.option.underlying,e=state.option.expiry;
 const q=new URLSearchParams({symbol:u,timeframe:"5m"});if(e)q.set("expiry",e);
 const box=$("v20OptState");if(box)box.textContent="Options Agent evaluating "+u+"…";
 try{
  const r=await getJSON("/api/v20/options/runtime?"+q,6500);
  if(id!==optionSeq)return;
  const p=r.p||{};
  if(!r.ok||p.success!==true)throw new Error(p.message||"Options Agent unavailable");
  state.option.runtime=p;
  state.option.rows=Array.isArray(p.chain)?p.chain:[];state.option.spot=Number.isFinite(Number(p.spot))?Number(p.spot):null;state.option.pcr=Number.isFinite(Number(p.chain_analytics?.pcr_oi))?Number(p.chain_analytics.pcr_oi):Number.isFinite(Number(p.pcr_oi))?Number(p.pcr_oi):null;state.option.analytics=p.chain_analytics||{};state.option.expiries=Array.isArray(p.available_expiries)?p.available_expiries:[];
  const sel=$("v20OptExpiry");if(sel){const expiryValue=typeof p.expiry==="string"?p.expiry:(p.expiry?.date||e||"");sel.innerHTML='<option value="">NEAREST EXPIRY</option>'+state.option.expiries.map(x=>'<option value="'+esc(x)+'">'+esc(x)+'</option>').join("");sel.value=state.option.expiry||expiryValue}
  if(box)box.textContent="OPTIONS AGENT · "+(p.state||"RUNNING")+" · "+(p.data_quality?.chain||"FYERS") ;
  const sig=p.underlying_signal||{},contract=p.selected_contract||{};
  const decision=$("v20DecisionState");if(decision)decision.textContent=(sig.side||"WAIT")+" · "+num(p.composite_score,1)+" / 100";
  const reason=$("v20DecisionReason");if(reason)reason.textContent=(p.blockers||[]).length?"BLOCKED · "+p.blockers.join(" · "):"All configured entry gates passed. Paper engine may open a synthetic position.";
  const metrics=$("v20DecisionMetrics");if(metrics)metrics.innerHTML=[["UNDERLYING",sig.side||"WAIT"],["TREND SCORE",num(sig.score,2)],["RSI",num(sig.rsi,1)],["CONTRACT SCORE",num(contract.selection_score,1)]].map(x=>'<div class="v20-metric"><small>'+x[0]+'</small><b>'+esc(x[1])+'</b></div>').join("");
  const sc=$("v20SelectedContract");if(sc)sc.innerHTML=contract.symbol?'<b>'+esc(contract.option_type||"OPTION")+" "+num(contract.strike,0)+'</b><span>'+esc(contract.symbol)+' · Δ '+num(contract.delta,3)+' · IV '+num(contract.iv,1)+' · OI '+num(contract.open_interest,0)+'</span>':'<b>WAITING</b><span>No verified contract selected.</span>';
  const pp=$("v20PaperPosition");const positions=Array.isArray(p.positions)?p.positions:[];if(pp)pp.innerHTML=p.paper_trade?.success?'<b>PAPER ENTRY OPENED</b><br>'+esc(p.paper_trade.symbol||contract.symbol||"OPTION")+" · entry "+num(p.paper_trade.entry)+" · stop "+num(p.paper_trade.stop)+" · target "+num(p.paper_trade.target):positions.length?positions.map(x=>esc(x.symbol)+" · "+esc(x.side)+" · mark "+num(x.mark)).join("<br>"):"No autonomous paper position is currently reported.";
  const gates=$("v20DecisionGates");if(gates)gates.innerHTML=(p.blockers||[]).length?(p.blockers||[]).map(x=>'<span class="v20-gate bad">'+esc(x)+'</span>').join(""):'<span class="v20-gate ok">VERIFIED DATA</span><span class="v20-gate ok">DIRECTIONAL EDGE</span><span class="v20-gate ok">LIQUID CONTRACT</span><span class="v20-gate ok">RISK ADMISSION</span>';
  renderOptions();
  renderLiveChart("v20OptionUnderlyingChart","underlying",p.underlying_candles||[],"Underlying");
  const um=$("v20UnderlyingChartMeta");if(um)um.textContent=u+" · "+(p.timeframe||"5m")+" · "+((p.underlying_candles||[]).length)+" bars";
  await refreshSelectedOptionChart();
 }catch(err){
  if(id!==optionSeq)return;
  if(box)box.textContent="OPTIONS AGENT DEGRADED · "+(err.message||"request failed");
  const decision=$("v20DecisionState");if(decision)decision.textContent="WAIT · DATA LANE";
  const reason=$("v20DecisionReason");if(reason)reason.textContent="No synthetic trade is opened without verified chain and candle evidence.";
 }finally{if(id===optionSeq)state.option.loading=false}
}
function pairRows(){
 const m=new Map();for(const r of state.option.rows||[]){const k=Number(r.strike),t=String(r.option_type||"").toUpperCase();if(!Number.isFinite(k)||!["CE","PE"].includes(t))continue;if(!m.has(k))m.set(k,{strike:k,CE:null,PE:null});m.get(k)[t]=r}
 let a=[...m.values()].sort((x,y)=>x.strike-y.strike);if(state.option.spot==null)return a;
 let ai=0,md=Infinity;a.forEach((p,i)=>{const d=Math.abs(p.strike-state.option.spot);if(d<md){md=d;ai=i}});return a.slice(Math.max(0,ai-state.option.range),Math.min(a.length,ai+state.option.range+1))
}
function optionHeaders(){
 const v=state.option.view;
 if(v==="GREEKS")return "<tr><th>CE IV</th><th>CE Δ</th><th>CE Γ</th><th>CE Θ</th><th>STRIKE</th><th>PE Θ</th><th>PE Γ</th><th>PE Δ</th><th>PE IV</th></tr>";
 if(v==="STRADDLE")return "<tr><th>CE OI</th><th>CE LTP</th><th>CE IV</th><th>STRIKE</th><th>PE IV</th><th>PE LTP</th><th>PE OI</th><th>STRADDLE</th></tr>";
 return "<tr><th>CE LTP</th><th>CE BID</th><th>CE ASK</th><th>CE OI</th><th>CE ΔOI</th><th>STRIKE</th><th>PE ΔOI</th><th>PE OI</th><th>PE BID</th><th>PE ASK</th><th>PE LTP</th></tr>"
}
function renderOptions(){
 const ps=pairRows(),a=state.option.analytics||{},h=$("v20OptHead"),b=$("v20OptRows");if(!h||!b)return;h.innerHTML=optionHeaders();
 const atm=state.option.spot!=null&&ps.length?ps.reduce((x,y)=>Math.abs(y.strike-state.option.spot)<Math.abs(x.strike-state.option.spot)?y:x,ps[0]).strike:null;
 if(!ps.length){b.innerHTML='<tr><td colspan="11"><div class="v20-empty"><b>NO VERIFIED OPTION CHAIN</b>'+esc(state.option.loading?"Waiting for FYERS chain response.": "FYERS chain is unavailable or degraded. The workspace remains usable.")+'</div></td></tr>'}
 else b.innerHTML=ps.map(p=>{const ce=p.CE||{},pe=p.PE||{},c=Number(ce.ltp),q=Number(pe.ltp),cl=p.strike===atm?"atm":"";
 if(state.option.view==="GREEKS")return '<tr class="'+cl+'"><td>'+num(ce.iv)+'</td><td>'+num(ce.delta,3)+'</td><td>'+num(ce.gamma,4)+'</td><td>'+num(ce.theta,3)+'</td><td class="v20-strike">'+num(p.strike,0)+'</td><td>'+num(pe.theta,3)+'</td><td>'+num(pe.gamma,4)+'</td><td>'+num(pe.delta,3)+'</td><td>'+num(pe.iv)+'</td></tr>';
 if(state.option.view==="STRADDLE")return '<tr class="'+cl+'"><td>'+num(ce.open_interest,0)+'</td><td>'+num(c)+'</td><td>'+num(ce.iv)+'</td><td class="v20-strike">'+num(p.strike,0)+'</td><td>'+num(pe.iv)+'</td><td>'+num(q)+'</td><td>'+num(pe.open_interest,0)+'</td><td>'+num((Number.isFinite(c)?c:0)+(Number.isFinite(q)?q:0))+'</td></tr>';
 return '<tr class="'+cl+'"><td class="v20-ce">'+num(ce.ltp)+'</td><td>'+num(ce.bid)+'</td><td>'+num(ce.ask)+'</td><td>'+num(ce.open_interest,0)+'</td><td>'+num(ce.change_in_oi,0)+'</td><td class="v20-strike">'+num(p.strike,0)+'</td><td>'+num(pe.change_in_oi,0)+'</td><td>'+num(pe.open_interest,0)+'</td><td>'+num(pe.bid)+'</td><td>'+num(pe.ask)+'</td><td class="v20-pe">'+num(pe.ltp)+'</td></tr>'}).join("");
 $("v20OptSummary").innerHTML=[["SPOT",num(state.option.spot)],["PCR OI",num(state.option.pcr)],["CALL WALL",num(a.call_oi_wall?.strike,0)],["PUT WALL",num(a.put_oi_wall?.strike,0)]].map(x=>'<div class="v20-metric"><small>'+x[0]+'</small><b>'+esc(x[1])+'</b></div>').join("");
 $("v20Spot").textContent=num(state.option.spot);$("v20PCR").textContent=num(state.option.pcr);$("v20CallWall").textContent=num(a.call_oi_wall?.strike,0);$("v20PutWall").textContent=num(a.put_oi_wall?.strike,0);$("v20MaxPain").textContent=num(a.max_pain?.strike,0);$("v20RightExpiry").textContent=state.option.expiry||"NEAREST";$("v20RightStrikes").textContent=String(ps.length);$("v20RightProvider").textContent=state.option.rows.length?"FYERS READY":"DEGRADED";renderLegs()
}
function renderLegs(){
 const host=$("v20Legs"),pay=$("v20Payoff");if(!host||!pay)return;
 host.innerHTML=state.option.legs.length?state.option.legs.map((l,i)=>'<div class="v20-leg"><span class="'+(l.type==="CE"?"v20-ce":"v20-pe")+'">'+l.type+'</span><span>'+l.action+" "+num(l.strike,0)+" @ "+num(l.premium)+'</span><button data-leg="'+i+'">×</button></div>').join(""):'<div class="v20-note">No legs. Add an ATM CE/PE scenario.</div>';
 host.querySelectorAll("[data-leg]").forEach(b=>b.onclick=()=>{state.option.legs.splice(Number(b.dataset.leg),1);renderLegs()});
 if(!state.option.legs.length){pay.textContent="Strategy lab idle.";return}
 const spot=state.option.spot||state.option.legs[0].strike;
 const payoff=x=>state.option.legs.reduce((v,l)=>{const intrinsic=l.type==="CE"?Math.max(0,x-l.strike):Math.max(0,l.strike-x);return v+(l.action==="BUY"?intrinsic-l.premium:l.premium-intrinsic)},0);
 const p0=payoff(spot);pay.innerHTML="Spot P/L: <b>"+num(p0)+"</b><br>−2% / +2%: "+num(payoff(spot*.98))+" / "+num(payoff(spot*1.02))+"<br><span class='v20-note'>Per unit approximation; lot size, fees and slippage excluded.</span>"
}
function addLeg(){
 const ps=pairRows();if(!ps.length)return;const p=ps.reduce((x,y)=>Math.abs(y.strike-(state.option.spot||y.strike))<Math.abs(x.strike-(state.option.spot||x.strike))?y:x,ps[0]);
 const raw=window.prompt("BUY CE, SELL CE, BUY PE or SELL PE","BUY CE");if(!raw)return;const m=String(raw).toUpperCase().match(/^(BUY|SELL)\s+(CE|PE)$/);if(!m||!p[m[2]])return;
 state.option.legs.push({action:m[1],type:m[2],strike:p.strike,premium:Number(p[m[2]].ltp)||0});renderLegs()
}
function bindOptions(){
 $("v20OptUnderlying").value=state.option.underlying;
 $("v20OptUnderlying").onchange=e=>{state.option.underlying=e.target.value;state.option.expiry="";state.option.legs=[];loadOptionRuntime()};
 $("v20OptExpiry").onchange=e=>{state.option.expiry=e.target.value;loadOptionRuntime()};
 $("v20OptRange").onchange=e=>{state.option.range=Number(e.target.value)||12;renderOptions()};
 $("v20OptRefresh").onclick=loadOptionRuntime;
 $("v20AddLeg").onclick=addLeg;
 document.querySelectorAll("[data-v20-opt-view]").forEach(b=>b.onclick=()=>{state.option.view=b.dataset.v20OptView;document.querySelectorAll("[data-v20-opt-view]").forEach(x=>x.classList.toggle("active",x===b));renderOptions()});
 stopOptionRuntime();
 loadOptionRuntime();
 optionRuntimeTimer=setInterval(()=>{if(!document.hidden&&activeWorkspace()==="OPTIONS")loadOptionRuntime()},5000);
 optionChartTimer=setInterval(()=>{if(!document.hidden&&activeWorkspace()==="OPTIONS")refreshSelectedOptionChart()},5000);
}
async function telemetry(){
 const w=activeWorkspace(),a=await getJSON("/api/v19/workspace/state?workspace="+encodeURIComponent(w),5000),b=await getJSON("/api/provider",5000);
 const p=a.p?.provider||b.p||{},h=a.p?.health||null;const fy=String(p.state||p.status||"UNKNOWN").toUpperCase();const hs=String(h?.status||"").toUpperCase()||((fy==="CONNECTED"||fy==="READY")?"READY":fy==="RECONNECTING"?"RECONNECTING":"DEGRADED");
 const box=$("v20Status");if(box)box.innerHTML=chip("WORKSPACE",w)+chip("FYERS",fy,fy==="CONNECTED"||fy==="READY"?"ok":fy==="RECONNECTING"?"warn":"bad")+chip("HEALTH",hs,hs==="READY"?"ok":"warn")+chip("EXECUTION","PAPER LOCKED","ok");
 $("v20RailProvider")&&($("v20RailProvider").textContent=fy);$("v20RightProvider")&&($("v20RightProvider").textContent=fy)
}

async function globalState() {
 const names=["INTRADAY","SWING","INVESTMENT"];
 const results=await Promise.all(names.map(async name=>{
   const r=await getJSON("/api/v16/trading/workspace-state?workspace="+encodeURIComponent(name),7000);
   return {name,p:r.p||{}};
 }));
 const journal=await getJSON("/api/v20/journal?limit=40",7000);
 const scanner=await getJSON("/api/scanner/multi",7000);
 const options=await getJSON("/api/v20/options/health",4000);
 return {workspaces:results,journal:journal.p||{},scanner:scanner.p||{},options:options.p||{}};
}
function money(v){
 const n=Number(v);return Number.isFinite(n)?n.toLocaleString("en-IN",{style:"currency",currency:"INR",maximumFractionDigits:0}):"—";
}
function age(iso){
 if(!iso)return "—";const t=Date.parse(iso);if(!Number.isFinite(t))return "—";
 const s=Math.max(0,Date.now()-t)/1000;if(s<60)return Math.round(s)+"s";
 if(s<3600)return Math.floor(s/60)+"m";
 if(s<86400)return Math.floor(s/3600)+"h";
 return Math.floor(s/86400)+"d";
}
function globalStyle(){
 if($("v20GlobalStyle"))return;
 const s=document.createElement("style");s.id="v20GlobalStyle";
 s.textContent=".v20-global{display:grid;gap:7px;margin:7px 0}.v20-global *{box-sizing:border-box}.v20-global-head{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:8px;align-items:center;border:1px solid #24566a;background:linear-gradient(90deg,#071a23,#07121a);padding:9px;border-radius:7px}.v20-global-kicker{font-size:8px;letter-spacing:.12em;color:#58d9ff}.v20-global-title{font-size:16px;font-weight:900;color:#e9fbff;margin-top:2px}.v20-global-sub{font-size:8px;color:#87aebb;margin-top:3px}.v20-global-actions{display:flex;gap:5px;flex-wrap:wrap;justify-content:flex-end}.v20-global-actions button{min-height:30px;border:1px solid #2a6175;background:#071923;color:#dff8ff;border-radius:5px;padding:6px 10px;font-size:8px;font-weight:800;cursor:pointer}.v20-global-actions button.start{border-color:#2f8c61;color:#8af2b3;background:#09251b}.v20-global-actions button.stop{border-color:#7b3949;color:#ff9aaa;background:#281015}.v20-global-strip{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:5px}.v20-global-card,.v20-global-panel{border:1px solid #174354;background:#07151d;border-radius:6px;padding:7px}.v20-global-card small{display:block;font-size:6px;color:#6d96a5;letter-spacing:.08em}.v20-global-card b{display:block;font-size:11px;color:#e4f8ff;margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.v20-global-card span{display:block;font-size:7px;color:#82a7b6;margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.v20-global-card.ok b{color:#80f0ad}.v20-global-card.warn b{color:#ffd166}.v20-global-panel .head{display:flex;justify-content:space-between;align-items:center;gap:6px;margin-bottom:5px}.v20-global-panel .title{font-size:9px;font-weight:900;letter-spacing:.08em;color:#9bd3e5}.v20-global-panel .hint{font-size:7px;color:#638c9c}.v20-global-table{width:100%;border-collapse:collapse;font-size:7px}.v20-global-table th{position:sticky;top:0;background:#0a1c25;color:#74aabe;padding:6px;text-align:left}.v20-global-table td{padding:6px;border-top:1px solid #12313e;color:#c9e4ec;white-space:nowrap;vertical-align:top}.v20-global-table td.note{white-space:normal;max-width:360px}.v20-global-grid{display:grid;grid-template-columns:1.25fr 1fr;gap:7px}.v20-global-status{font-size:8px;border-left:2px solid #ffd166;background:#08171e;padding:6px;color:#d9c477}.v20-global-status.ok{border-color:#49d68f;color:#93efbd}.v20-global-status.bad{border-color:#ff6f83;color:#ff9aaa}@media(max-width:1200px){.v20-global-strip{grid-template-columns:repeat(3,minmax(0,1fr))}.v20-global-grid{grid-template-columns:1fr}}@media(max-width:700px){.v20-global-strip{grid-template-columns:repeat(2,minmax(0,1fr))}.v20-global-head{grid-template-columns:1fr}.v20-global-actions{justify-content:flex-start}}";
 document.head.appendChild(s);
}
function globalDeck(workspace){
 globalStyle();
 return '<section id="v20Global" class="v20-global">'+
 '<div class="v20-global-head"><div><div class="v20-global-kicker">JARVIS V20 · GLOBAL CONTROL PLANE</div><div class="v20-global-title">FULL WORKSPACE COMMAND CENTER</div><div class="v20-global-sub">V20 orchestrates the canonical V17/V18/V19 runtime. One control can arm or pause Intraday, Swing, Investment and the dedicated Options Agent without replacing their proven surfaces.</div></div><div class="v20-global-actions"><button class="start" data-v20-global="start">START JARVIS TRADING</button><button class="stop" data-v20-global="stop">STOP NEW ENTRIES</button><button data-v20-global="scan">SCAN ALL MARKETS</button><button data-v20-global="refresh">REFRESH</button></div></div>'+
 '<div id="v20GlobalStatus" class="v20-global-status">Reading canonical workspace, scanner and journal state…</div>'+
 '<div id="v20GlobalStrip" class="v20-global-strip"></div>'+
 '<div class="v20-global-grid"><div class="v20-global-panel"><div class="head"><span class="title">OVERALL MARKET SCANNER</span><span class="hint">GLOBAL · NOT SELECTED-MARKET ONLY</span></div><div id="v20GlobalScanner"></div></div><div class="v20-global-panel"><div class="head"><span class="title">CAPITAL + POSITION GOVERNANCE</span><span class="hint">NO DAILY TOP-UP</span></div><div id="v20GlobalPositions"></div></div></div>'+
 '<div class="v20-global-panel"><div class="head"><span class="title">TRADE JOURNAL + AUTOMATIC REVIEW</span><span class="hint">ENTRY → EXECUTION → MANAGEMENT → CLOSE → LEARNING</span></div><div id="v20GlobalJournal"></div></div>'+
 '</section>';
}
function renderGlobal(data){
 const strip=$("v20GlobalStrip"),scanner=$("v20GlobalScanner"),positions=$("v20GlobalPositions"),journal=$("v20GlobalJournal"),status=$("v20GlobalStatus");
 if(!strip)return;
 const ws=data.workspaces||[];
 let totalAvail=0,totalCommitted=0,totalRisk=0,totalPnl=0,openCount=0;
 const allPositions=[];
 for(const item of ws){
  const p=item.p||{},cap=p.capital||{};
  totalAvail+=Number(cap.available_capital)||0; totalCommitted+=Number(cap.committed_capital)||0; totalRisk+=Number(cap.open_risk)||0; totalPnl+=Number(cap.equity||0)-Number(cap.starting_capital||0);
  for(const pos of (p.positions||[])) allPositions.push({...pos,workspace:item.name});
 }
 openCount=allPositions.length;
 strip.innerHTML=ws.map(item=>{const p=item.p||{},cap=p.capital||{};const running=String(p.session?.entry_session||"PAUSED").toUpperCase()==="RUNNING";return '<div class="v20-global-card '+(running?"ok":"")+"'><small>"+esc(item.name)+"</small><b>"+(running?"RUNNING":"PAUSED")+"</b><span>"+money(cap.available_capital)+" available · "+money(cap.open_risk)+" risk</span></div>'}).join("")+
 '<div class="v20-global-card"><small>OPTIONS AGENT</small><b>'+esc(String(data.options?.running===true?"RUNNING":"READY/WAIT"))+'</b><span>paper-only · live locked</span></div>'+
 '<div class="v20-global-card ok"><small>GLOBAL AVAILABLE</small><b>'+money(totalAvail)+'</b><span>new entries use current workspace cash</span></div>';
 status.className="v20-global-status "+((data.options?.success!==false)?"ok":"bad");
 status.textContent="WORKSPACE "+workspace+" · "+openCount+" open position"+(openCount===1?"":"s")+" · "+money(totalRisk)+" open risk · "+money(totalCommitted)+" committed · "+money(totalPnl)+" net equity change";
 const scan=data.scanner||{}, rows=Array.isArray(scan.candidates)?scan.candidates:[], scoped=rows.slice(0,18);
 scanner.innerHTML=(scan.running?'<div class="v20-global-status">Scanning '+(scan.scanned||0)+' / '+(scan.total||0)+' across '+((scan.selected_universes||[]).join(" · ")||"all configured universes")+'</div>':'')+
 '<table class="v20-global-table"><thead><tr><th>SYMBOL</th><th>DIRECTION</th><th>SCORE</th><th>UNIVERSE</th><th>STATUS</th><th>DATA</th></tr></thead><tbody>'+
 (scoped.length?scoped.map(r=>'<tr><td><b>'+esc(r.symbol)+'</b></td><td>'+esc(r.direction||"WAIT")+'</td><td>'+esc(r.score??"—")+'</td><td>'+esc((r.universes||[]).join(" / "))+'</td><td>'+esc(r.auto_paper_eligible?"PAPER WATCH":"RESEARCH")+'</td><td class="note">'+esc(r.message||r.state||"—")+'</td></tr>').join(""):'<tr><td colspan="6">No global scanner results yet. Use SCAN ALL MARKETS.</td></tr>')+
 '</tbody></table>';
 const posRows=allPositions.slice(0,24);
 positions.innerHTML='<table class="v20-global-table"><thead><tr><th>WORKSPACE</th><th>SYMBOL</th><th>ENTRY</th><th>MARK</th><th>P&amp;L</th><th>AGE</th></tr></thead><tbody>'+
 (posRows.length?posRows.map(p=>'<tr><td>'+esc(p.workspace)+'</td><td><b>'+esc(p.symbol)+'</b><br>'+esc(p.side||"")+'</td><td>'+esc(p.entry??"—")+'</td><td>'+esc(p.mark??"—")+'</td><td>'+money(p.unrealized_pnl)+'</td><td>'+age(p.opened_at)+'</td></tr>').join(""):'<tr><td colspan="6">No open positions. Workspace scanners remain separate; existing positions stay monitored when entries are paused.</td></tr>')+
 '</tbody></table>';
 const jr=Array.isArray(data.journal?.rows)?data.journal.rows:[];
 journal.innerHTML='<table class="v20-global-table"><thead><tr><th>TRADE</th><th>WORKSPACE</th><th>ENTRY / EXECUTION</th><th>CLOSE</th><th>RESULT</th><th>AUTOMATIC REVIEW</th></tr></thead><tbody>'+
 (jr.length?jr.slice(0,24).map(r=>{const review=r.learning_review||{};const outcome=review.outcome||("OPEN"===String(r.status).toUpperCase()?"OPEN":"—");const mistakes=Array.isArray(review.mistake_hypotheses)?review.mistake_hypotheses.join(", "):"";const note=r.journal||{};return '<tr><td><b>'+esc(r.trade_id||("#"+r.position_id))+'</b><br>'+esc(r.symbol)+' '+esc(r.side)+'</td><td>'+esc(r.workspace)+'</td><td>'+esc(r.decision_at||"—")+'<br>'+esc(r.execution_at||r.opened_at||"—")+'</td><td>'+esc(r.closed_at||"OPEN")+'<br>'+esc(r.exit_execution_at||"—")+'</td><td>'+esc(outcome)+' · '+money(r.realized_pnl)+'<br>MAE '+esc(r.mae_r??"—")+'R · MFE '+esc(r.mfe_r??"—")+'R</td><td class="note">'+esc(review.status||"PENDING")+" · "+esc(review.reason||note.exit_note||note.entry_note||"Lifecycle tracked; automatic review runs at close.")+(mistakes?"<br>Hypotheses: "+esc(mistakes):"")+'</td></tr>'}).join(""):'<tr><td colspan="6">No paper journal records returned.</td></tr>')+
 '</tbody></table>';
}
async function refreshGlobal(){
 const box=$("v20GlobalStatus");try{const data=await globalState();renderGlobal(data);window.__JARVIS_V20_GLOBAL_STATE__=data;return data}catch(e){if(box){box.className="v20-global-status bad";box.textContent="Global control-plane read degraded · "+(e.message||e);}}return null;
}
async function v20GlobalControl(action){
 const state=await getJSON("/api/v16/trading/workspace-state?workspace=INTRADAY",7000);
 const token=state.p?.csrf_token;
 if(!token){$("v20GlobalStatus").textContent="LOCAL SESSION TOKEN REQUIRED · refresh this terminal";return}
 try{
  const response=await fetch("/api/v20/control",{method:"POST",headers:{"Content-Type":"application/json","X-Jarvis-Token":String(token)},body:JSON.stringify({action}),cache:"no-store"});
  const payload=await response.json().catch(()=>({}));
  if(!response.ok||payload.success!==true)throw new Error(payload.message||payload.reason||("HTTP "+response.status));
  $("v20GlobalStatus").className="v20-global-status ok";$("v20GlobalStatus").textContent=payload.message||("Global "+action+" complete.");
  await refreshGlobal();
 }catch(e){$("v20GlobalStatus").className="v20-global-status bad";$("v20GlobalStatus").textContent="Global control failed · "+(e.message||e);}
}
async function scanAllMarkets(){
 const payload={force:true,auto_enroll:false,profile:"intraday",universes:["NIFTY50","BANKNIFTY","SENSEX30","INDIA_INDICES","MCX_MAJOR","CRYPTO_MAJOR","GLOBAL_MAJOR"]};
 try{
  const response=await fetch("/api/scanner/multi/start",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload),cache:"no-store"});
  const data=await response.json().catch(()=>({}));if(!response.ok||data.success!==true)throw new Error(data.message||data.reason||("HTTP "+response.status));
  $("v20GlobalStatus").className="v20-global-status ok";$("v20GlobalStatus").textContent="GLOBAL SCANNER STARTED · all configured market universes requested.";
  setTimeout(refreshGlobal,300);
 }catch(e){$("v20GlobalStatus").className="v20-global-status bad";$("v20GlobalStatus").textContent="Global scanner failed · "+(e.message||e);}
}
function render(){
 globalStyle();
 const root=ensure();if(!root)return;
 const w=activeWorkspace();state.workspace=w;
 root.innerHTML=globalDeck(w);
 hideLegacy();
 refreshGlobal();
 if(w!=="OPTIONS")stopOptionRuntime();
 window.scrollTo?.(0,0);
}
function wire(){
 window.addEventListener("jarvis:workspace",()=>render());
 document.addEventListener("click",e=>{
   const a=e.target.closest("[data-v20-global]");
   if(a){
     const action=a.dataset.v20Global;
     if(action==="start")v20GlobalControl("start");
     if(action==="stop")v20GlobalControl("stop");
     if(action==="scan")scanAllMarkets();
     if(action==="refresh")refreshGlobal();
   }
 });
}
function boot(){wire();render();setInterval(()=>{if(!document.hidden){const w=activeWorkspace();if(w!==state.workspace)render();else refreshGlobal()}},5000)}
if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",boot,{once:true});else boot();
})();