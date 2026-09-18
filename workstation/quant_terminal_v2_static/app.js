const MARKETS=[
  {symbol:"NIFTY",label:"NIFTY 50",kind:"INDIA"},
  {symbol:"BANKNIFTY",label:"BANK NIFTY",kind:"INDIA"},
  {symbol:"SENSEX",label:"SENSEX",kind:"INDIA"},
  {symbol:"CRUDEOIL",label:"CRUDE OIL",kind:"INDIA"},
  {symbol:"GOLD",label:"GOLD",kind:"INDIA"},
  {symbol:"SILVER",label:"SILVER",kind:"INDIA"},
  {symbol:"NATURALGAS",label:"NAT GAS",kind:"INDIA"},
  {symbol:"BTC",label:"BITCOIN",kind:"CRYPTO"},
  {symbol:"ETH",label:"ETHEREUM",kind:"CRYPTO"},
  {symbol:"SOL",label:"SOLANA",kind:"CRYPTO"}
];

const SLOT_DEFAULTS=["NIFTY","BANKNIFTY","CRUDEOIL","BTC","SENSEX","GOLD","ETH","SILVER"];
const $=id=>document.getElementById(id);
let layout=4;
let timeframe="5m";
let analysisProfile="intraday";
let selectedSlot=0;
let selectedSymbol="NIFTY";
let chartSlots=[];
let liveTimer=null;
let providerTimer=null;
let signalTimer=null;
let watchCursor=0;
const indicatorState={ema:true,vwap:true,bb:true,rsi:true};
const RICH_STATE_KEY="jarvis.v16.rich.workspaces";
const CHART_FRAMES=["1m","3m","5m","15m","30m","1h","2h","4h","1d"];
let activeWorkspace="INTRADAY";
let savedWorkspaces={};
try{savedWorkspaces=JSON.parse(localStorage.getItem(RICH_STATE_KEY)||"{}")}catch{}
if(!savedWorkspaces||typeof savedWorkspaces!=="object"||Array.isArray(savedWorkspaces))savedWorkspaces={};
function chartCount(value){return Math.max(1,Math.min(8,Math.trunc(Number(value)||4)))}
function workspaceView(){
  const existing=savedWorkspaces[activeWorkspace];
  if(existing&&typeof existing==="object"&&Array.isArray(existing.slots))return existing;
  return savedWorkspaces[activeWorkspace]={layout:4,focus:0,slots:[]};
}
function slotView(index){
  const view=workspaceView();const stored=view.slots[index]||{};
  const tf=activeWorkspace==="SWING"?"1h":activeWorkspace==="INVESTMENT"?"1d":"5m";
  return view.slots[index]={symbol:String(stored.symbol||SLOT_DEFAULTS[index]||"NIFTY"),timeframe:CHART_FRAMES.includes(stored.timeframe)?stored.timeframe:tf,indicators:{ema:true,vwap:true,bb:true,rsi:true,...stored.indicators},kind:stored.kind||"MARKET",optionChart:stored.optionChart||null};
}
function persistCharts(){
  const view=workspaceView();view.layout=chartCount(layout);view.focus=selectedSlot;
  chartSlots.forEach((s,i)=>{view.slots[i]={symbol:s.symbol,timeframe:s.timeframe,indicators:{...s.indicators},kind:s.kind||"MARKET",optionChart:s.optionChart||null}});
  try{localStorage.setItem(RICH_STATE_KEY,JSON.stringify(savedWorkspaces))}catch{}
}
function focusChart(index){
  const slot=chartSlots[index];if(!slot)return;
  selectedSlot=index;selectedSymbol=slot.symbol;timeframe=slot.timeframe;Object.assign(indicatorState,slot.indicators);
  document.querySelectorAll(".chart-cell").forEach((node,i)=>node.classList.toggle("selected",i===index));
  $("scanSymbol").textContent=marketMeta(selectedSymbol).label;syncControls();buildWatch();persistCharts();
}
async function switchWorkspace(name){
  if(!["INTRADAY","SWING","INVESTMENT","OPTIONS"].includes(name))return;
  persistCharts();activeWorkspace=name;analysisProfile=name==="OPTIONS"?"intraday":name.toLowerCase();
  const view=workspaceView();layout=chartCount(view.layout);selectedSlot=Math.min(Number(view.focus)||0,layout-1);
  chartSlots.forEach(destroySlot);chartSlots=[];
  selectedSymbol=slotView(selectedSlot).symbol;timeframe=slotView(selectedSlot).timeframe;
  syncControls();await mountCharts();window.dispatchEvent(new CustomEvent("jarvis:workspace",{detail:{workspace:name}}));
}
const candleReads=new Map();const candleCache=new Map();let candleActive=0;const candleQueue=[];
async function readCandles(url){
  const cached=candleCache.get(url);if(cached&&Date.now()-cached.at<10000)return cached.payload;
  if(candleReads.has(url))return candleReads.get(url);
  const task=(async()=>{
    if(candleActive>=4)await new Promise(resolve=>candleQueue.push(resolve));else candleActive++;
    try{const payload=await fetchJson(url,{},32000);if(payload.success&&payload.candles?.length){candleCache.set(url,{at:Date.now(),payload});while(candleCache.size>64)candleCache.delete(candleCache.keys().next().value)}return payload}
    finally{const next=candleQueue.shift();if(next)next();else candleActive--;candleReads.delete(url)}
  })();candleReads.set(url,task);return task;
}

async function fetchJson(url,options={},timeoutMs=12000){
  const controller=new AbortController();const timeout=setTimeout(()=>controller.abort(),timeoutMs);
  try{const response=await fetch(url,{...options,signal:controller.signal});const payload=await response.json();if(!response.ok)throw new Error(payload.message||payload.error||`Provider request failed (${response.status})`);return payload}
  catch(error){if(error?.name==="AbortError")throw new Error("Market-data request timed out. Use RELOAD DATA to retry.");throw error}
  finally{clearTimeout(timeout)}
}

function marketMeta(symbol){return MARKETS.find(item=>item.symbol===symbol)||{symbol,label:symbol,kind:"INDIA"}}
function fmt(value,digits=2){const n=Number(value);return Number.isFinite(n)?n.toLocaleString("en-IN",{maximumFractionDigits:digits,minimumFractionDigits:digits}):"—"}
function escapeHtml(value){return String(value??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]))}
function secondsFor(tf){return {"1m":60,"3m":180,"5m":300,"15m":900,"30m":1800,"1h":3600,"2h":7200,"4h":14400,"1d":86400}[tf]||300}
function bucketTime(epoch,tf){const size=secondsFor(tf);return Math.floor(Number(epoch)/size)*size}
function currentEpoch(snapshot){const raw=Number(snapshot?.exchange_timestamp);if(Number.isFinite(raw)&&raw>0)return raw>1e12?Math.floor(raw/1000):Math.floor(raw);return Math.floor(Date.now()/1000)}

function emaSeries(rows,period){
  if(rows.length<period)return[];const alpha=2/(period+1);let value=rows.slice(0,period).reduce((sum,row)=>sum+row.close,0)/period;const result=[{time:rows[period-1].time,value}];
  for(let i=period;i<rows.length;i++){value=alpha*rows[i].close+(1-alpha)*value;result.push({time:rows[i].time,value})}return result;
}
function vwapSeries(rows){let weighted=0,volume=0;const result=[];for(const row of rows){const v=Math.max(0,Number(row.volume||0));weighted+=((row.high+row.low+row.close)/3)*v;volume+=v;if(volume>0)result.push({time:row.time,value:weighted/volume})}return result}
function bollingerSeries(rows,period=20){const upper=[],lower=[];for(let i=period-1;i<rows.length;i++){const sample=rows.slice(i-period+1,i+1).map(row=>row.close);const mean=sample.reduce((a,b)=>a+b,0)/period;const variance=sample.reduce((sum,value)=>sum+((value-mean)**2),0)/period;const sigma=Math.sqrt(variance);upper.push({time:rows[i].time,value:mean+2*sigma});lower.push({time:rows[i].time,value:mean-2*sigma})}return{upper,lower}}
function rsiSeries(rows,period=14){const result=[];for(let i=period;i<rows.length;i++){let gain=0,loss=0;for(let j=i-period+1;j<=i;j++){const change=rows[j].close-rows[j-1].close;if(change>=0)gain+=change;else loss-=change}const avgGain=gain/period,avgLoss=loss/period;const value=avgLoss===0?100:100-(100/(1+(avgGain/avgLoss)));result.push({time:rows[i].time,value})}return result}
function updateIndicators(slot){
  if(!slot?.data?.length||!slot.ema20)return;const bands=bollingerSeries(slot.data);
  slot.ema20.setData(emaSeries(slot.data,20));slot.ema50.setData(emaSeries(slot.data,50));slot.vwap.setData(vwapSeries(slot.data));slot.bbUpper.setData(bands.upper);slot.bbLower.setData(bands.lower);slot.rsi.setData(rsiSeries(slot.data));
  const state=slot.indicators||indicatorState;
  slot.ema20.applyOptions({visible:state.ema});slot.ema50.applyOptions({visible:state.ema});slot.vwap.applyOptions({visible:state.vwap});slot.bbUpper.applyOptions({visible:state.bb});slot.bbLower.applyOptions({visible:state.bb});slot.rsi.applyOptions({visible:state.rsi});
}
function decisionSignal(decision){const side=String(decision?.side||"WAIT").toUpperCase();return side==="LONG"?"BUY":side==="SHORT"?"SELL":"WAIT"}
function clearSignalLines(slot){for(const line of slot?.signalLines||[]){try{slot.candles.removePriceLine(line)}catch{}}if(slot?.signalMarker){try{slot.signalMarker.detach()}catch{}slot.signalMarker=null}if(slot)slot.signalLines=[]}
function applyDecision(slot,decision){
  if(!slot)return;clearSignalLines(slot);slot.decision=decision||null;const signal=decisionSignal(decision);const cls=signal.toLowerCase();slot.signalBadge.textContent=`${signal} · ${Number(decision?.score||0).toFixed(1)}`;slot.signalBadge.className=`chart-signal ${cls}`;
  const pattern=decision?.pattern_confirmation||{};const patternState=String(pattern.state||"NO CONFIRMED PATTERN").replaceAll("_"," ");if(slot.patternState){slot.patternState.textContent=`${patternState} · ${decision?.qualified?"PAPER SETUP QUALIFIED":"MONITORING"}`;slot.patternState.className=`chart-pattern-state ${cls}`}
  if(slot.index===selectedSlot){
    $("liveSignal").textContent=signal;$("liveSignal").className=`signal-badge ${cls}`;$("signalScore").textContent=`${Number(decision?.score||0).toFixed(1)} SCORE`;$("signalRegime").textContent=String(decision?.regime||"NO VERIFIED DECISION").replaceAll("_"," ");
    const votes=Array.isArray(decision?.votes)?decision.votes:[];const blockers=Array.isArray(decision?.blockers)?decision.blockers:[];const evidence=votes.slice(0,4).map(vote=>`${vote.timeframe?`${vote.timeframe} `:""}${String(vote.strategy||"strategy").replaceAll("_"," ")} ${vote.side||"WAIT"}`).join(" · ");$("signalReason").textContent=decision?.message||(blockers.length?blockers.join(" · ").replaceAll("_"," "):(evidence||"Unified 5m / 15m / 1h consensus remains in WAIT."));
  }
  if(!decision?.success||decision.entry==null)return;
  const levels=[[decision.entry,"ENTRY","#5cdbff",1],[decision.stop,"STOP","#ff6f83",2],[decision.target,"TARGET","#78f2aa",2]];for(const [price,title,color,width] of levels){if(Number.isFinite(Number(price)))slot.signalLines.push(slot.candles.createPriceLine({price:Number(price),color,lineWidth:width,lineStyle:LightweightCharts.LineStyle.Dashed,axisLabelVisible:true,title}))}
  if(slot.data?.length&&typeof LightweightCharts.createSeriesMarkers==="function"&&["BUY","SELL"].includes(signal)){
    const last=slot.data[slot.data.length-1];slot.signalMarker=LightweightCharts.createSeriesMarkers(slot.candles,[{time:last.time,position:signal==="BUY"?"belowBar":"aboveBar",shape:signal==="BUY"?"arrowUp":"arrowDown",color:signal==="BUY"?"#78f2aa":"#ff6f83",text:`${signal} · ${patternState}`}]);
  }
}
async function loadDecision(symbol=selectedSymbol){
  try{const decision=await fetchJson(`/api/scan?${new URLSearchParams({symbol,profile:analysisProfile})}`,{},40000);const slot=chartSlots[selectedSlot];if(slot&&slot.symbol===symbol)applyDecision(slot,decision);return decision}catch(error){const decision={success:false,side:"WAIT",score:0,message:error.message};applyDecision(chartSlots[selectedSlot],decision);return decision}
}

function buildWatch(){
  const host=$("marketWatch");
  host.innerHTML="";
  MARKETS.forEach(item=>{
    const button=document.createElement("button");
    button.className=`market-tile asset-${String(item.kind||"market").toLowerCase().replaceAll("_","-")}`+(item.symbol===selectedSymbol?" active":"");
    button.dataset.symbol=item.symbol;
    const feed=item.kind==="CRYPTO"?"PUBLIC CRYPTO":String(item.kind).includes("GLOBAL")?"PUBLIC DELAYED":"BROKER DATA";button.innerHTML=`<strong>${item.label}</strong><span class="price" data-watch-price>—</span><small>${feed}</small><em data-watch-change>waiting</em>`;
    button.addEventListener("click",()=>selectMarket(item.symbol));
    host.appendChild(button);
  });
}

function updateWatchTile(symbol,snapshot,meta={}){
  const tile=document.querySelector(`.market-tile[data-symbol="${symbol}"]`);if(!tile)return;
  const price=tile.querySelector("[data-watch-price]");const change=tile.querySelector("[data-watch-change]");
  tile.classList.toggle("degraded",Boolean(meta.degraded||meta.stale));tile.classList.remove("data-error");
  if(!snapshot||snapshot.ltp==null){
    const hasLastVerified=tile.dataset.lastVerified==="1"&&price.textContent!=="—";
    if(hasLastVerified){
      change.textContent=(meta.message||"refresh delayed")+" · LAST VERIFIED";
      change.style.color="#d4a84c";
      tile.classList.add("degraded");
      return;
    }
    price.textContent="—";change.textContent=meta.message||"no verified snapshot";tile.classList.add("data-error");return
  }
  price.textContent=fmt(snapshot.ltp);tile.dataset.lastVerified="1";
  const pct=Number(snapshot.change_percent);const diff=Number(snapshot.change);const sign=diff>0?"+":"";
  const feedState=String(meta.statusLabel||(meta.stale?"STALE":meta.snapshotKind==="REST_QUOTE_FALLBACK"?"REST":meta.degraded?"DEGRADED":"")).toUpperCase();
  change.textContent=(Number.isFinite(diff)?`${sign}${diff.toFixed(2)}`:"")+(Number.isFinite(pct)?` (${pct>0?"+":""}${pct.toFixed(2)}%)`:"")+(feedState?` · ${feedState}`:"");
  change.style.color=meta.stale?"#d4a84c":diff>0?"#78f2aa":diff<0?"#ff6f83":"#7e9aa7";
}

function selectMarket(symbol){
  selectedSymbol=symbol;
  const meta=marketMeta(symbol);$("scanSymbol").textContent=meta.label;
  document.querySelectorAll(".market-tile").forEach(tile=>tile.classList.toggle("active",tile.dataset.symbol===symbol));
  if(chartSlots[selectedSlot]){
    chartSlots[selectedSlot].symbol=symbol;
    chartSlots[selectedSlot].data=[];destroySlot(chartSlots[selectedSlot]);persistCharts();
    return loadSlot(selectedSlot).then(()=>scanSelected());
  }
  return Promise.resolve();
}

function chartOptions(){return {
  autoSize:true,
  attributionLogo:true,
  layout:{background:{type:"solid",color:"#060d12"},textColor:"#86a5b2",fontFamily:"Segoe UI, Arial"},
  grid:{vertLines:{color:"rgba(75,140,166,.08)"},horzLines:{color:"rgba(75,140,166,.08)"}},
  rightPriceScale:{borderColor:"#173849"},
  timeScale:{borderColor:"#173849",timeVisible:true,secondsVisible:false,rightOffset:5,barSpacing:7},
  crosshair:{mode:LightweightCharts.CrosshairMode.Normal,vertLine:{color:"rgba(92,219,255,.28)",labelBackgroundColor:"#16485d"},horzLine:{color:"rgba(92,219,255,.28)",labelBackgroundColor:"#16485d"}},
  handleScroll:{mouseWheel:true,pressedMouseMove:true,horzTouchDrag:true,vertTouchDrag:false},
  handleScale:{axisPressedMouseMove:true,mouseWheel:true,pinch:true}
}}

function centerChart(slot){
  if(!slot?.chart)return;
  const scale=slot.chart.timeScale();
  scale.fitContent();
  // Keep enough forward space for live candles, entry/SL/target labels and
  // active pattern annotations instead of pinning the latest candle to edge.
  window.requestAnimationFrame(()=>scale.scrollToPosition(12,false));
}

function destroySlot(slot){
  if(!slot)return;
  if(slot.cryptoSocket){try{slot.cryptoSocket.close()}catch{}slot.cryptoSocket=null}
  if(slot.cryptoTimer){clearTimeout(slot.cryptoTimer);slot.cryptoTimer=null}
  slot.pendingCrypto=null;
  if(slot.chart){try{slot.chart.remove()}catch{}slot.chart=null}
}

function mountCharts(){
  const host=$("chartGrid");
  chartSlots.forEach(destroySlot);
  chartSlots=[];
  host.innerHTML="";
  host.className=`chart-grid layout-${layout}`;
  const loads=[];
  for(let index=0;index<layout;index++){
    const config=slotView(index);const symbol=config.symbol;
    const cell=document.createElement("div");cell.className="chart-cell"+(index===selectedSlot?" selected":"");cell.dataset.slot=String(index);
    const head=document.createElement("div");head.className="chart-head";
    head.innerHTML=`<strong>${marketMeta(symbol).label}</strong><span>${timeframe} · LOADING</span>`;
    const controls=document.createElement("div");controls.className="chart-controls";
    controls.innerHTML=`<select data-chart-symbol aria-label="Chart ${index+1} symbol">${[...new Set([...MARKETS.map(m=>m.symbol),symbol])].map(s=>`<option ${s===symbol?"selected":""}>${escapeHtml(s)}</option>`).join("")}</select><select data-chart-timeframe aria-label="Chart ${index+1} timeframe">${CHART_FRAMES.map(tf=>`<option ${tf===config.timeframe?"selected":""}>${tf}</option>`).join("")}</select><button data-chart-fit title="Fit chart">FIT</button>`;
    controls.addEventListener("click",event=>event.stopPropagation());
    controls.querySelector("[data-chart-symbol]").addEventListener("change",event=>{focusChart(index);selectMarket(event.target.value)});
    controls.querySelector("[data-chart-timeframe]").addEventListener("change",event=>{focusChart(index);setChartTimeframe(index,event.target.value)});
    controls.querySelector("[data-chart-fit]").addEventListener("click",()=>centerChart(chartSlots[index]));
    const chartHost=document.createElement("div");chartHost.className="chart-host";
    const signalBadge=document.createElement("div");signalBadge.className="chart-signal wait";signalBadge.textContent="WAIT · 0.0";
    const patternState=document.createElement("div");patternState.className="chart-pattern-state wait";patternState.textContent="PATTERN ENGINE · WAITING";
    const status=document.createElement("div");status.className="chart-status";status.textContent="Loading verified candles…";
    cell.append(head,controls,chartHost,signalBadge,patternState,status);host.appendChild(cell);
    cell.addEventListener("click",()=>{if(selectedSlot===index)return;focusChart(index);if(chartSlots[index].decision)applyDecision(chartSlots[index],chartSlots[index].decision);scanSelected()});
    chartSlots.push({...config,index,symbol,cell,head,chartHost,signalBadge,patternState,status,chart:null,candles:null,volume:null,ema20:null,ema50:null,vwap:null,bbUpper:null,bbLower:null,rsi:null,signalLines:[],signalMarker:null,decision:null,data:[],cryptoSocket:null,cryptoTimer:null,pendingCrypto:null});
    loads.push(loadSlot(index));
  }
  focusChart(Math.min(selectedSlot,layout-1));return Promise.allSettled(loads);
}

function setChartTimeframe(index,tf){
  const slot=chartSlots[index];if(!slot||!CHART_FRAMES.includes(tf))return;
  slot.timeframe=tf;slot.data=[];destroySlot(slot);focusChart(index);persistCharts();
  slot.cell.querySelector("[data-chart-timeframe]").value=tf;return loadSlot(index);
}

function setStatus(slot,text,kind=""){slot.status.textContent=text;slot.status.className="chart-status"+(kind?` ${kind}`:"")}

function createSeries(slot,payload){
  if(typeof LightweightCharts==="undefined")throw new Error("Lightweight Charts library did not load.");
  destroySlot(slot);
  slot.chart=LightweightCharts.createChart(slot.chartHost,chartOptions());
  slot.candles=slot.chart.addSeries(LightweightCharts.CandlestickSeries,{upColor:"#61e69a",downColor:"#ff667d",wickUpColor:"#61e69a",wickDownColor:"#ff667d",borderVisible:false,priceLineColor:"#5cdbff",priceLineWidth:1});
  slot.volume=slot.chart.addSeries(LightweightCharts.HistogramSeries,{priceFormat:{type:"volume"},priceScaleId:"",color:"rgba(92,219,255,.28)"});
  slot.ema20=slot.chart.addSeries(LightweightCharts.LineSeries,{color:"#5cdbff",lineWidth:2,priceLineVisible:false,lastValueVisible:false});
  slot.ema50=slot.chart.addSeries(LightweightCharts.LineSeries,{color:"#ffd166",lineWidth:2,priceLineVisible:false,lastValueVisible:false});
  slot.vwap=slot.chart.addSeries(LightweightCharts.LineSeries,{color:"#d57aff",lineWidth:2,lineStyle:LightweightCharts.LineStyle.Dotted,priceLineVisible:false,lastValueVisible:false});
  slot.bbUpper=slot.chart.addSeries(LightweightCharts.LineSeries,{color:"rgba(126,154,167,.72)",lineWidth:1,priceLineVisible:false,lastValueVisible:false});
  slot.bbLower=slot.chart.addSeries(LightweightCharts.LineSeries,{color:"rgba(126,154,167,.72)",lineWidth:1,priceLineVisible:false,lastValueVisible:false});
  slot.rsi=slot.chart.addSeries(LightweightCharts.LineSeries,{color:"#78f2aa",lineWidth:2,priceFormat:{type:"price",precision:1,minMove:.1},priceLineVisible:false,lastValueVisible:true},1);
  slot.rsi.priceScale().applyOptions({autoScale:true,scaleMargins:{top:.1,bottom:.1}});slot.rsi.createPriceLine({price:70,color:"rgba(255,111,131,.45)",lineWidth:1,lineStyle:LightweightCharts.LineStyle.Dotted,axisLabelVisible:false});slot.rsi.createPriceLine({price:30,color:"rgba(120,242,170,.45)",lineWidth:1,lineStyle:LightweightCharts.LineStyle.Dotted,axisLabelVisible:false});
  slot.volume.priceScale().applyOptions({scaleMargins:{top:.82,bottom:0}});
  slot.data=(payload.candles||[]).filter(row=>[row.time??row.timestamp,row.open,row.high,row.low,row.close].every(v=>v!=null&&Number.isFinite(Number(v)))).map(row=>({time:Number(row.time??row.timestamp),open:Number(row.open),high:Number(row.high),low:Number(row.low),close:Number(row.close),volume:row.volume==null?null:Number(row.volume)})).filter(row=>row.high>=Math.max(row.open,row.close)&&row.low<=Math.min(row.open,row.close)).sort((a,b)=>a.time-b.time);
  slot.data=slot.data.filter((row,i,rows)=>i===rows.length-1||rows[i+1].time!==row.time);
  slot.candles.setData(slot.data.map(({time,open,high,low,close})=>({time,open,high,low,close})));
  slot.volume.setData(slot.data.filter(row=>row.volume!=null&&Number.isFinite(row.volume)).map(row=>({time:row.time,value:row.volume,color:row.close>=row.open?"rgba(97,230,154,.28)":"rgba(255,102,125,.28)"})));
  updateIndicators(slot);
  centerChart(slot);
}

async function loadSlot(index){
  const slot=chartSlots[index];if(!slot)return;
  const timeframe=slot.timeframe;const version=slot.loadVersion=(slot.loadVersion||0)+1;
  if(slot.cryptoSocket){try{slot.cryptoSocket.close()}catch{}slot.cryptoSocket=null}
  const symbol=slot.symbol;const meta=marketMeta(symbol);
  slot.head.querySelector("strong").textContent=meta.label;slot.head.querySelector("span").textContent=`${timeframe} · LOADING`;
  setStatus(slot,`Loading ${meta.label} ${timeframe} candles…`);
  try{
    const params=new URLSearchParams({symbol,timeframe,bars:"700"});
    const payload=await readCandles(`/api/candles?${params}`);
    if(chartSlots[index]!==slot||slot.loadVersion!==version||slot.symbol!==symbol||slot.timeframe!==timeframe)return;
    if(!payload.success||!payload.candles?.length)throw new Error(payload.message||"Verified candles unavailable.");
    createSeries(slot,payload);
    slot.head.querySelector("span").textContent=`${timeframe} · ${payload.source}`;
    setStatus(slot,`${payload.source} · ${payload.provider_symbol} · ${payload.bars} bars · ${payload.data_quality}`,"live");
    if(meta.kind==="CRYPTO")connectCryptoSocket(slot);else pollSlotLive(slot);
  }catch(error){
    if(chartSlots[index]!==slot||slot.loadVersion!==version)return;
    setStatus(slot,`${slot.data.length?"LAST VERIFIED HISTORY RETAINED · ":""}${error.message||"Market data unavailable."}`,"error");
    slot.head.querySelector("span").textContent=`${timeframe} · DATA UNAVAILABLE`;
  }
}

function applyLivePrice(slot,snapshot){
  if(!slot?.candles||!snapshot||snapshot.ltp==null)return;
  const price=Number(snapshot.ltp);if(!Number.isFinite(price))return;
  const stamp=Number(snapshot.exchange_timestamp);if(!Number.isFinite(stamp)||stamp<=0)return;
  const epoch=stamp>1e12?stamp/1000:stamp;if(Math.abs(Date.now()/1000-epoch)>30)return;
  const timeframe=slot.timeframe;const now=bucketTime(epoch,timeframe);const last=slot.data[slot.data.length-1];if(last&&now<last.time)return;
  let candle;
  if(last&&Number(last.time)===now){
    candle={...last,high:Math.max(Number(last.high),price),low:Math.min(Number(last.low),price),close:price};
    slot.data[slot.data.length-1]=candle;
  }else{
    candle={time:now,open:price,high:price,low:price,close:price,volume:null};slot.data.push(candle);
  }
  slot.candles.update({time:candle.time,open:candle.open,high:candle.high,low:candle.low,close:candle.close});
  if(candle.volume!=null)slot.volume.update({time:candle.time,value:candle.volume,color:candle.close>=candle.open?"rgba(97,230,154,.28)":"rgba(255,102,125,.28)"});
  updateIndicators(slot);
  slot.head.querySelector("span").textContent=`${timeframe} · LIVE ${fmt(price)}`;setStatus(slot,`${marketMeta(slot.symbol).kind==="CRYPTO"?"CRYPTO TICK":"FYERS LIVE"} · ${fmt(price)} · ${new Date().toLocaleTimeString()}`,"live");
  updateWatchTile(slot.symbol,snapshot);
}

async function pollSlotLive(slot){
  if(!slot||!slot.cell.isConnected||marketMeta(slot.symbol).kind==="CRYPTO")return;
  try{const payload=await fetchJson(`/api/live?${new URLSearchParams({symbol:slot.symbol})}`,{},6000);if(payload.success&&payload.snapshot)applyLivePrice(slot,payload.snapshot)}catch{}
}

function connectCryptoSocket(slot){
  const provider={BTC:"btcusdt",ETH:"ethusdt",SOL:"solusdt"}[slot.symbol];if(!provider)return;
  try{
    const socket=new WebSocket(`wss://stream.binance.com:9443/ws/${provider}@trade`);slot.cryptoSocket=socket;
    // BTC can emit dozens of trades per second. Rendering every tick used to
    // starve the browser main thread and made the terminal look permanently
    // stuck on LOADING even though the candle API was healthy. Keep the newest
    // tick and render at a bounded two updates per second.
    socket.onmessage=event=>{try{const trade=JSON.parse(event.data);slot.pendingCrypto={ltp:Number(trade.p),exchange_timestamp:Math.floor(Number(trade.T)/1000),volume:Number(trade.q)};if(!slot.cryptoTimer)slot.cryptoTimer=setTimeout(()=>{slot.cryptoTimer=null;const latest=slot.pendingCrypto;slot.pendingCrypto=null;if(latest&&slot.cell.isConnected)applyLivePrice(slot,latest)},500)}catch{}};
    socket.onerror=()=>{setStatus(slot,"Crypto WebSocket unavailable; REST fallback will continue.","error")};
  }catch{}
}

async function refreshProvider(){
  try{
    const payload=await fetchJson("/api/provider",{},6000);
    const button=$("providerButton");const state=payload.state||"UNKNOWN";button.textContent=`FYERS · ${state.replaceAll("_"," ")}`;button.className="status-pill "+(state==="CONNECTED"?"connected":state==="LOGIN_REQUIRED"?"error":"warn");
    $("providerState").textContent=state.replaceAll("_"," ");
    const error=payload.bridge?.error;$("providerMessage").textContent=state==="CONNECTED"?"Read-only FYERS live stream connected.":state==="DEGRADED"?`FYERS REST fallback active while the live stream reconnects${error?`: ${error}`:"."}`:error||"FYERS session is not live. Use the local login button if today's token has expired.";
  }catch(error){$("providerState").textContent="UNAVAILABLE";$("providerMessage").textContent=error.message}
}

async function refreshOneWatch(){
  const item=MARKETS[watchCursor%MARKETS.length];watchCursor++;
  try{const payload=await fetchJson(`/api/live?${new URLSearchParams({symbol:item.symbol})}`,{},6000);if(payload.success&&payload.snapshot)updateWatchTile(item.symbol,payload.snapshot,{degraded:Boolean(payload.stream_degraded||payload.stale),stale:Boolean(payload.stale),snapshotKind:payload.snapshot_kind,statusLabel:payload.market_closed?"CLOSED":payload.stale?"STALE":payload.snapshot_kind==="REST_QUOTE_FALLBACK"?"REST":payload.stream_degraded?"DEGRADED":"",message:payload.message});else updateWatchTile(item.symbol,null,{message:payload.message||"data unavailable"})}catch(error){updateWatchTile(item.symbol,null,{message:error.message,degraded:true})}
}

async function refreshAllWatch(){
  await Promise.allSettled(MARKETS.map(async item=>{
    try{const payload=await fetchJson(`/api/live?${new URLSearchParams({symbol:item.symbol})}`,{},10000);if(payload.success&&payload.snapshot)updateWatchTile(item.symbol,payload.snapshot,{degraded:Boolean(payload.stream_degraded||payload.stale),stale:Boolean(payload.stale),snapshotKind:payload.snapshot_kind,statusLabel:payload.market_closed?"CLOSED":payload.stale?"STALE":payload.snapshot_kind==="REST_QUOTE_FALLBACK"?"REST":payload.stream_degraded?"DEGRADED":"",message:payload.message});else updateWatchTile(item.symbol,null,{message:payload.message||"data unavailable"})}catch(error){updateWatchTile(item.symbol,null,{message:error.message,degraded:true})}
  }));
}

async function scanSelected(){
  const symbol=selectedSymbol;const frames=analysisProfile==="swing"?"1h / 4h / 1d":"5m / 15m / 1h";$("scanRegime").textContent="SCANNING";$("scanBias").textContent="WORKING";$("scanAlignment").textContent="—";$("setupState").textContent="WAITING";$("evidenceList").innerHTML=`<p>Loading verified ${frames} evidence…</p>`;
  try{
    const payload=await fetchJson(`/api/scan?${new URLSearchParams({symbol,profile:analysisProfile})}`,{},40000);const decision=payload;
    $("scanRegime").textContent=payload.regime||"UNAVAILABLE";$("scanBias").textContent=payload.qualified?(payload.bias||"QUALIFIED"):`WAIT · ${payload.bias||"NO BIAS"}`;$("scanAlignment").textContent=`${Number(payload.alignment||0)}% ALIGN`;
    const setup=payload.setup;$("setupState").textContent=setup?`${setup.side} · ${setup.status}`:"NO QUALIFIED SETUP";$("entryRef").textContent=setup?fmt(setup.entry_reference):"—";$("stopRef").textContent=setup?fmt(setup.stop_reference):"—";$("targetRef").textContent=setup?fmt(setup.target_reference):"—";$("rrRef").textContent=setup?`${setup.risk_reward_reference}:1`:"—";
    const evidence=Array.isArray(payload.evidence)?payload.evidence:[];$("evidenceList").innerHTML=evidence.map(row=>{if(!row.available)return `<div class="evidence-row"><div class="topline"><b>${escapeHtml(row.timeframe)}</b><span>NO DATA</span></div><p>${escapeHtml(row.message||"")}</p></div>`;const cls=row.trend==="BULLISH"?"bull":row.trend==="BEARISH"?"bear":"";const d=row.decision||{};const pattern=row.patterns||{};return `<div class="evidence-row ${cls}"><div class="topline"><b>${escapeHtml(row.timeframe)} · ${escapeHtml(row.trend)}</b><span>${escapeHtml(d.side||"WAIT")} ${Number(d.score||0).toFixed(1)}</span></div><p>Close ${fmt(row.close)} · EMA20 ${fmt(row.ema20)} · EMA50 ${fmt(row.ema50)} · RSI ${fmt(row.rsi14,1)} · ATR ${fmt(row.atr14)} · Vol× ${row.volume_ratio==null?"—":fmt(row.volume_ratio,2)}<br>Pattern: ${escapeHtml(pattern.state||"NO EDGE")} · structure ${escapeHtml(pattern.structure||"—")} · level ${fmt(pattern.breakout_level)}</p></div>`}).join("")||"<p>No timeframe evidence.</p>";
    const slot=chartSlots[selectedSlot];if(slot&&slot.symbol===symbol)applyDecision(slot,decision);
    $("commandReply").textContent=payload.message||"Scan complete.";
  }catch(error){$("scanRegime").textContent="DATA ERROR";$("scanBias").textContent="NO SCAN";$("evidenceList").innerHTML=`<p>${escapeHtml(error.message)}</p>`;applyDecision(chartSlots[selectedSlot],{success:false,side:"WAIT",score:0,message:error.message})}
}

async function openSignalChart(chart,decision=null){
  const raw=String(chart?.symbol||chart?.label||"").toUpperCase().replaceAll(" ","");let found=MARKETS.find(item=>item.symbol===raw||item.label.toUpperCase().replaceAll(" ","")===raw);if(!found&&raw){found={symbol:raw,label:String(chart?.label||raw),kind:String(chart?.kind||"INDIA_EQUITY")};MARKETS.push(found)}if(!found)return false;
  selectedSymbol=found.symbol;selectedSlot=0;layout=[1,2,4,6,8].includes(Number(chart?.layout))?Number(chart.layout):1;const requested=String(chart?.timeframe||timeframe);if(["1m","3m","5m","15m","30m","1h","2h","4h","1d"].includes(requested))timeframe=requested;analysisProfile=String(decision?.profile||chart?.profile||(timeframe==="1d"?"swing":"intraday"));buildWatch();syncControls();await mountCharts();if(decision)applyDecision(chartSlots[0],decision);await scanSelected();return true;
}

async function sendCommand(){
  const input=$("commandInput");const text=input.value.trim();if(!text)return;$("commandReply").textContent="JARVIS is routing the trading command…";
  try{
    const result=await fetchJson("/api/agent",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({text})},45000);$("commandReply").textContent=result.speech||result.message||"Command processed.";
    if(result.action==="open_master_chat"){
      const handoff=String(result.text||text).slice(0,1000);
      window.open(`http://127.0.0.1:8797/?workspace=chat&command=${encodeURIComponent(handoff)}`,"_blank","noopener");
    }
    else if(result.chart){await openSignalChart(result.chart,result.decision)}
    else if(result.action==="set_layout"&&Number(result.layout)){layout=[1,2,4,6,8].includes(Number(result.layout))?Number(result.layout):layout;selectedSlot=0;syncControls();await mountCharts()}
    else if(result.action==="open_quant"&&result.symbol){await openSignalChart({symbol:result.symbol,timeframe,layout:1},result.decision)}
  }catch(error){$("commandReply").textContent=error.message}
}

function openIntelligenceModule(moduleName){
  const params=new URLSearchParams({module:String(moduleName||""),symbol:selectedSymbol,profile:"intraday"});
  const defaultUniverse={NIFTY:"NIFTY50",BANKNIFTY:"BANKNIFTY",SENSEX:"SENSEX30",BTC:"CRYPTO_MAJOR",ETH:"CRYPTO_MAJOR",SOL:"CRYPTO_MAJOR",CRUDEOIL:"MCX_MAJOR",GOLD:"MCX_MAJOR",SILVER:"MCX_MAJOR",NATURALGAS:"MCX_MAJOR"}[selectedSymbol];
  if(defaultUniverse)params.set("universe",defaultUniverse);
  window.open(`/intelligence.html?${params.toString()}`,"_blank","noopener");
}

function syncControls(){document.querySelectorAll("[data-workspace]").forEach(button=>button.classList.toggle("active",button.dataset.workspace===activeWorkspace));document.querySelectorAll("[data-layout]").forEach(button=>button.classList.toggle("active",Number(button.dataset.layout)===layout));document.querySelectorAll("[data-timeframe]").forEach(button=>button.classList.toggle("active",button.dataset.timeframe===timeframe));document.querySelectorAll("[data-indicator]").forEach(button=>button.classList.toggle("active",Boolean(indicatorState[button.dataset.indicator])))}

function bindControls(){
  document.querySelectorAll("[data-workspace]").forEach(button=>button.addEventListener("click",()=>switchWorkspace(button.dataset.workspace)));
  document.querySelectorAll("[data-layout]").forEach(button=>button.addEventListener("click",()=>{persistCharts();layout=chartCount(button.dataset.layout);selectedSlot=Math.min(selectedSlot,layout-1);syncControls();mountCharts()}));
  document.querySelectorAll("[data-timeframe]").forEach(button=>button.addEventListener("click",()=>setChartTimeframe(selectedSlot,button.dataset.timeframe)));
  document.querySelectorAll("[data-indicator]").forEach(button=>button.addEventListener("click",()=>{const key=button.dataset.indicator;indicatorState[key]=!indicatorState[key];const slot=chartSlots[selectedSlot];if(slot){slot.indicators[key]=indicatorState[key];updateIndicators(slot)}syncControls();persistCharts()}));
  $("fitButton").addEventListener("click",()=>chartSlots.forEach(centerChart));
  $("reloadCharts").addEventListener("click",()=>chartSlots.forEach((_,i)=>loadSlot(i)));
  $("scanButton").addEventListener("click",scanSelected);
  $("sendCommand").addEventListener("click",sendCommand);$("commandInput").addEventListener("keydown",event=>{if(event.key==="Enter")sendCommand()});
  document.querySelectorAll("[data-module]").forEach(button=>button.addEventListener("click",()=>openIntelligenceModule(button.dataset.module)));
  $("loginButton").addEventListener("click",async()=>{try{const payload=await fetchJson("/api/fyers/login",{method:"POST",headers:{"Content-Type":"application/json"},body:"{}"},15000);$("providerMessage").textContent=payload.message||"FYERS login launched."}catch(error){$("providerMessage").textContent=error.message}});
  $("restartButton").addEventListener("click",async()=>{try{await fetchJson("/api/market/restart",{method:"POST",headers:{"Content-Type":"application/json"},body:"{}"},15000);setTimeout(refreshProvider,700);chartSlots.forEach((_,i)=>loadSlot(i))}catch(error){$("providerMessage").textContent=error.message}});
  $("providerButton").addEventListener("click",()=>$("providerState").scrollIntoView({behavior:"smooth",block:"center"}));
}

function startTimers(){
  if(liveTimer)clearInterval(liveTimer);liveTimer=setInterval(()=>{chartSlots.forEach(slot=>{if(String(marketMeta(slot.symbol).kind).startsWith("INDIA"))pollSlotLive(slot)});refreshOneWatch()},1200);
  if(providerTimer)clearInterval(providerTimer);providerTimer=setInterval(refreshProvider,5000);
  if(signalTimer)clearInterval(signalTimer);signalTimer=setInterval(()=>loadDecision(selectedSymbol),30000);
}

async function bootstrap(){
  const view=workspaceView();layout=chartCount(view.layout);selectedSlot=Math.max(0,Math.min(Number(view.focus)||0,layout-1));selectedSymbol=slotView(selectedSlot).symbol;timeframe=slotView(selectedSlot).timeframe;
  const params=new URLSearchParams(window.location.search);const raw=String(params.get("symbol")||"").toUpperCase().replaceAll(" ","");let found=MARKETS.find(item=>item.symbol===raw||item.label.toUpperCase().replaceAll(" ","")===raw);if(!found&&raw){found={symbol:raw,label:raw,kind:"INDIA_EQUITY"};MARKETS.push(found)}if(found)selectedSymbol=found.symbol;const tf=params.get("timeframe");if(tf&&["1m","3m","5m","15m","30m","1h","2h","4h","1d"].includes(tf))timeframe=tf;analysisProfile=params.get("profile")||(timeframe==="1d"?"swing":"intraday");if(params.get("analyze")==="1")layout=1;
  if(found||tf){view.slots[selectedSlot]={...slotView(selectedSlot),symbol:selectedSymbol,timeframe}};
  buildWatch();bindControls();syncControls();const watchHydration=refreshAllWatch();await mountCharts();refreshProvider();startTimers();await watchHydration;if(params.get("analyze")==="1")await scanSelected();
}
bootstrap();
