/* JARVIS V20 — Full Workspace Operating System */
(()=>{"use strict";
if(window.__JARVIS_V20_OS__)return;window.__JARVIS_V20_OS__=true;
const $=id=>document.getElementById(id), esc=v=>String(v??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const num=(v,d=2)=>{const n=Number(v);return Number.isFinite(n)?n.toLocaleString("en-IN",{maximumFractionDigits:d,minimumFractionDigits:d}):"—"};
const state={workspace:"INTRADAY",option:{underlying:"NIFTY",expiry:"",range:12,view:"PRICE",rows:[],spot:null,pcr:null,analytics:{},expiries:[],legs:[],loading:false}};
const U=[["NIFTY","NIFTY 50"],["BANKNIFTY","BANK NIFTY"],["SENSEX","SENSEX"]];
let optionSeq=0,optionAbort=null;

async function getJSON(url,timeout=8000){
 const c=new AbortController(),t=setTimeout(()=>c.abort(),timeout);
 try{const r=await fetch(url,{cache:"no-store",signal:c.signal});const p=await r.json().catch(()=>({}));return {ok:r.ok,p};}
 catch(e){return {ok:false,p:{success:false,message:e.name==="AbortError"?"Request timed out":e.message}}}finally{clearTimeout(t)}
}
function activeWorkspace(){return String(document.querySelector(".workspace-modes button.active")?.dataset.workspace||state.workspace||"INTRADAY").toUpperCase()}
function hideLegacy(){document.querySelectorAll(".v19-shellbar,.v19-contextbar,#v19Bottom,#v19Rail,#v18OptionsWorkbench").forEach(n=>n.style.display="none");document.querySelectorAll(".intel-panel>.intel-card").forEach(n=>{if(n.id.startsWith("v19"))n.style.display="none"})}
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
 return '<div class="v20-options"><aside class="v20-options-left"><div class="v20-panel"><div class="v20-panel-title">UNDERLYING</div><select id="v20OptUnderlying" class="v20-select">'+U.map(x=>'<option value="'+x[0]+'">'+x[1]+'</option>').join("")+'</select><div class="v20-panel-title" style="margin-top:9px">EXPIRY</div><select id="v20OptExpiry" class="v20-select"><option value="">NEAREST EXPIRY</option></select><div class="v20-panel-title" style="margin-top:9px">STRIKE WINDOW</div><select id="v20OptRange" class="v20-select"><option value="8">±8 STRIKES</option><option value="12" selected>±12 STRIKES</option><option value="20">±20 STRIKES</option></select><button class="v20-btn primary" id="v20OptRefresh" style="margin-top:7px">REFRESH CHAIN</button></div><div class="v20-panel"><div class="v20-panel-title">CHAIN ANALYTICS</div><div class="v20-list"><div><span>Spot</span><b id="v20Spot">—</b></div><div><span>PCR OI</span><b id="v20PCR">—</b></div><div><span>Call wall</span><b id="v20CallWall">—</b></div><div><span>Put wall</span><b id="v20PutWall">—</b></div><div><span>Max pain</span><b id="v20MaxPain">—</b></div></div></div><div class="v20-panel"><div class="v20-panel-title">DATA LANE</div><div id="v20OptState" class="v20-note">Waiting for isolated Options data lane.</div></div></aside><main class="v20-options-center"><div class="v20-panel"><div class="v20-panel-head"><div><div class="v20-panel-title">OPTION CHAIN · V20</div><div class="v20-muted">Calls / strikes / puts with OI, IV and Greeks. This is not the legacy chart panel.</div></div><div class="v20-tabs">'+["PRICE","GREEKS","STRADDLE"].map(x=>'<button class="v20-btn '+(x==="PRICE"?"active":"")+'" data-v20-opt-view="'+x+'">'+x+'</button>').join("")+'</div></div></div><div id="v20OptSummary" class="v20-grid4"></div><div class="v20-chain"><table><thead id="v20OptHead"></thead><tbody id="v20OptRows"></tbody></table></div></main><aside class="v20-options-right"><div class="v20-panel"><div class="v20-panel-title">PAPER STRATEGY LAB</div><div class="v20-note">Research/simulation only. No broker order is sent.</div><div id="v20Legs" class="v20-legs" style="margin-top:6px"></div><button class="v20-btn primary" id="v20AddLeg" style="margin-top:6px">ADD ATM LEG</button><div id="v20Payoff" class="v20-note" style="margin-top:7px"></div></div><div class="v20-panel"><div class="v20-panel-title">POSITION INTELLIGENCE</div><div class="v20-list"><div><span>Expiry</span><b id="v20RightExpiry">—</b></div><div><span>Strikes loaded</span><b id="v20RightStrikes">—</b></div><div><span>Provider</span><b id="v20RightProvider">CHECKING</b></div><div><span>Execution</span><b>PAPER LOCKED</b></div></div></div><div class="v20-panel"><div class="v20-panel-title">ISOLATION</div><div class="v20-note">Option requests have their own backend lane. Chart hydration is independent and can continue when the chain provider is degraded.</div></div></aside></div>'
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
async function loadOptions(){
 const id=++optionSeq;if(optionAbort)optionAbort.abort();optionAbort=new AbortController();state.option.loading=true;
 const u=state.option.underlying,e=state.option.expiry;
 $("v20OptState").textContent="Loading isolated FYERS chain for "+u+"…";
 try{
  const q=new URLSearchParams({workspace:"OPTIONS",symbol:u,module:"option-chain"});if(e)q.set("expiry",e);
  const c=optionAbort;const timer=setTimeout(()=>c.abort(),12000);const r=await fetch("/api/v17/options/chain?"+q,{cache:"no-store",signal:c.signal});clearTimeout(timer);const p=await r.json().catch(()=>({}));
  if(id!==optionSeq)return;if(!r.ok||p.success!==true)throw new Error(p.message||p.reason||"Options chain request failed");
  state.option.rows=Array.isArray(p.chain)?p.chain:[];state.option.spot=Number.isFinite(Number(p.spot))?Number(p.spot):null;state.option.pcr=Number.isFinite(Number(p.pcr_oi))?Number(p.pcr_oi):null;state.option.analytics=p.chain_analytics||{};state.option.expiries=Array.isArray(p.available_expiries)?p.available_expiries:[];
  const sel=$("v20OptExpiry");sel.innerHTML='<option value="">NEAREST EXPIRY</option>'+state.option.expiries.map(x=>'<option value="'+esc(x)+'">'+esc(x)+'</option>').join("");sel.value=state.option.expiry;
  $("v20OptState").textContent="FYERS VERIFIED · "+state.option.rows.length+" contracts · "+(state.option.expiry||"nearest expiry");renderOptions()
 }catch(err){if(id!==optionSeq)return;if(err.name==="AbortError")return;state.option.rows=[];state.option.analytics={};$("v20OptState").textContent="OPTIONS DEGRADED · "+(err.message||"request failed");renderOptions()
 }finally{if(id===optionSeq){state.option.loading=false}}
}
function bindOptions(){
 $("v20OptUnderlying").value=state.option.underlying;$("v20OptUnderlying").onchange=e=>{state.option.underlying=e.target.value;state.option.expiry="";state.option.legs=[];loadOptions()};
 $("v20OptExpiry").onchange=e=>{state.option.expiry=e.target.value;loadOptions()};$("v20OptRange").onchange=e=>{state.option.range=Number(e.target.value)||12;renderOptions()};$("v20OptRefresh").onclick=loadOptions;$("v20AddLeg").onclick=addLeg;
 document.querySelectorAll("[data-v20-opt-view]").forEach(b=>b.onclick=()=>{state.option.view=b.dataset.v20OptView;document.querySelectorAll("[data-v20-opt-view]").forEach(x=>x.classList.toggle("active",x===b));renderOptions()});
 loadOptions()
}
async function telemetry(){
 const w=activeWorkspace(),a=await getJSON("/api/v19/workspace/state?workspace="+encodeURIComponent(w),5000),b=await getJSON("/api/provider",5000);
 const p=a.p?.provider||b.p||{},h=a.p?.health||null;const fy=String(p.state||p.status||"UNKNOWN").toUpperCase();const hs=String(h?.status||"").toUpperCase()||((fy==="CONNECTED"||fy==="READY")?"READY":fy==="RECONNECTING"?"RECONNECTING":"DEGRADED");
 const box=$("v20Status");if(box)box.innerHTML=chip("WORKSPACE",w)+chip("FYERS",fy,fy==="CONNECTED"||fy==="READY"?"ok":fy==="RECONNECTING"?"warn":"bad")+chip("HEALTH",hs,hs==="READY"?"ok":"warn")+chip("EXECUTION","PAPER LOCKED","ok");
 $("v20RailProvider")&&($("v20RailProvider").textContent=fy);$("v20RightProvider")&&($("v20RightProvider").textContent=fy)
}
function render(){
 const root=ensure();if(!root)return;const w=activeWorkspace();state.workspace=w;document.body.classList.toggle("v20-active",true);document.body.classList.toggle("v20-options-active",w==="OPTIONS");document.body.classList.toggle("v20-investment-active",w==="INVESTMENT");
 root.innerHTML=header(w)+contexts(w)+(w==="OPTIONS"?optionShell():w==="INVESTMENT"?investment():w==="SWING"?swing():intraday());
 if(w==="OPTIONS")bindOptions();
 
 telemetry()
}
function wire(){
 document.querySelectorAll(".workspace-modes [data-workspace]").forEach(b=>b.addEventListener("click",()=>setTimeout(render,40)));
 document.addEventListener("click",e=>{
   const b=e.target.closest("[data-v20]");
   if(b){const a=b.dataset.v20;if(a==="refresh")telemetry();if(a==="scan")$("scanButton")?.click();if(a==="reset"){state.option.legs=[];state.option.rows=[];render()}}
   const c=e.target.closest("[data-v20-canonical]");
   if(c){const a=c.dataset.v20Canonical;if(a==="fit")$("fitButton")?.click();if(a==="reload")$("reloadCharts")?.click();if(a==="layout")document.querySelector('[data-layout="'+c.dataset.layout+'"]')?.click();if(a==="tf")document.querySelector('[data-timeframe="'+c.dataset.timeframe+'"]')?.click();}
 });
}
function boot(){render();wire();setInterval(()=>{if(!document.hidden){const w=activeWorkspace();if(w!==state.workspace)render();else telemetry()}},10000)}
if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",boot,{once:true});else boot();
})();