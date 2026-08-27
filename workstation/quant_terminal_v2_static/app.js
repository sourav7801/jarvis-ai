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

async function fetchJson(url,options={},timeoutMs=12000){
  const controller=new AbortController();const timeout=setTimeout(()=>controller.abort(),timeoutMs);
  try{const response=await fetch(url,{...options,signal:controller.signal});if(!response.ok)throw new Error(`HTTP ${response.status}`);return await response.json()}
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
function vwapSeries(rows){let weighted=0,volume=0;return rows.map(row=>{const v=Math.max(0,Number(row.volume||0));weighted+=((row.high+row.low+row.close)/3)*v;volume+=v;return{time:row.time,value:volume>0?weighted/volume:row.close}})}
function bollingerSeries(rows,period=20){const upper=[],lower=[];for(let i=period-1;i<rows.length;i++){const sample=rows.slice(i-period+1,i+1).map(row=>row.close);const mean=sample.reduce((a,b)=>a+b,0)/period;const variance=sample.reduce((sum,value)=>sum+((value-mean)**2),0)/period;const sigma=Math.sqrt(variance);upper.push({time:rows[i].time,value:mean+2*sigma});lower.push({time:rows[i].time,value:mean-2*sigma})}return{upper,lower}}
function rsiSeries(rows,period=14){const result=[];for(let i=period;i<rows.length;i++){let gain=0,loss=0;for(let j=i-period+1;j<=i;j++){const change=rows[j].close-rows[j-1].close;if(change>=0)gain+=change;else loss-=change}const avgGain=gain/period,avgLoss=loss/period;const value=avgLoss===0?100:100-(100/(1+(avgGain/avgLoss)));result.push({time:rows[i].time,value})}return result}
function updateIndicators(slot){
  if(!slot?.data?.length||!slot.ema20)return;const bands=bollingerSeries(slot.data);
  slot.ema20.setData(emaSeries(slot.data,20));slot.ema50.setData(emaSeries(slot.data,50));slot.vwap.setData(vwapSeries(slot.data));slot.bbUpper.setData(bands.upper);slot.bbLower.setData(bands.lower);slot.rsi.setData(rsiSeries(slot.data));
  slot.ema20.applyOptions({visible:indicatorState.ema});slot.ema50.applyOptions({visible:indicatorState.ema});slot.vwap.applyOptions({visible:indicatorState.vwap});slot.bbUpper.applyOptions({visible:indicatorState.bb});slot.bbLower.applyOptions({visible:indicatorState.bb});slot.rsi.applyOptions({visible:indicatorState.rsi});
}
function decisionSignal(decision){const side=String(decision?.side||"WAIT").toUpperCase();return side==="LONG"?"BUY":side==="SHORT"?"SELL":"WAIT"}
function clearSignalLines(slot){for(const line of slot?.signalLines||[]){try{slot.candles.removePriceLine(line)}catch{}}if(slot)slot.signalLines=[]}
function applyDecision(slot,decision){
  if(!slot)return;clearSignalLines(slot);slot.decision=decision||null;const signal=decisionSignal(decision);const cls=signal.toLowerCase();slot.signalBadge.textContent=`${signal} · ${Number(decision?.score||0).toFixed(1)}`;slot.signalBadge.className=`chart-signal ${cls}`;
  if(slot.index===selectedSlot){
    $("liveSignal").textContent=signal;$("liveSignal").className=`signal-badge ${cls}`;$("signalScore").textContent=`${Number(decision?.score||0).toFixed(1)} SCORE`;$("signalRegime").textContent=String(decision?.regime||"NO VERIFIED DECISION").replaceAll("_"," ");
    const votes=Array.isArray(decision?.votes)?decision.votes:[];const blockers=Array.isArray(decision?.blockers)?decision.blockers:[];const evidence=votes.slice(0,4).map(vote=>`${vote.timeframe?`${vote.timeframe} `:""}${String(vote.strategy||"strategy").replaceAll("_"," ")} ${vote.side||"WAIT"}`).join(" · ");$("signalReason").textContent=decision?.message||(blockers.length?blockers.join(" · ").replaceAll("_"," "):(evidence||"Unified 5m / 15m / 1h consensus remains in WAIT."));
  }
  if(!decision?.success||decision.entry==null)return;
  const levels=[[decision.entry,"ENTRY","#5cdbff",1],[decision.stop,"STOP","#ff6f83",2],[decision.target,"TARGET","#78f2aa",2]];for(const [price,title,color,width] of levels){if(Number.isFinite(Number(price)))slot.signalLines.push(slot.candles.createPriceLine({price:Number(price),color,lineWidth:width,lineStyle:LightweightCharts.LineStyle.Dashed,axisLabelVisible:true,title}))}
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
  tile.classList.toggle("degraded",Boolean(meta.degraded));tile.classList.remove("data-error");
  if(!snapshot||snapshot.ltp==null){price.textContent="—";change.textContent=meta.message||"no verified snapshot";tile.classList.add("data-error");return}
  price.textContent=fmt(snapshot.ltp);
  const pct=Number(snapshot.change_percent);const diff=Number(snapshot.change);const sign=diff>0?"+":"";
  change.textContent=(Number.isFinite(diff)?`${sign}${diff.toFixed(2)}`:"")+(Number.isFinite(pct)?` (${pct>0?"+":""}${pct.toFixed(2)}%)`:"")+(meta.degraded?" · REST":"");
  change.style.color=diff>0?"#78f2aa":diff<0?"#ff6f83":"#7e9aa7";
}

function selectMarket(symbol){
  selectedSymbol=symbol;
  const meta=marketMeta(symbol);$("scanSymbol").textContent=meta.label;
  document.querySelectorAll(".market-tile").forEach(tile=>tile.classList.toggle("active",tile.dataset.symbol===symbol));
  if(chartSlots[selectedSlot]){
    chartSlots[selectedSlot].symbol=symbol;
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
    const symbol=index===0?selectedSymbol:(SLOT_DEFAULTS[index]||"NIFTY");
    const cell=document.createElement("div");cell.className="chart-cell"+(index===selectedSlot?" selected":"");cell.dataset.slot=String(index);
    const head=document.createElement("div");head.className="chart-head";
    head.innerHTML=`<strong>${marketMeta(symbol).label}</strong><span>${timeframe} · LOADING</span>`;
    const chartHost=document.createElement("div");chartHost.className="chart-host";
    const signalBadge=document.createElement("div");signalBadge.className="chart-signal wait";signalBadge.textContent="WAIT · 0.0";
    const status=document.createElement("div");status.className="chart-status";status.textContent="Loading verified candles…";
    cell.append(head,chartHost,signalBadge,status);host.appendChild(cell);
    cell.addEventListener("click",()=>{selectedSlot=index;selectedSymbol=chartSlots[index].symbol;$("scanSymbol").textContent=marketMeta(selectedSymbol).label;document.querySelectorAll(".chart-cell").forEach((node,i)=>node.classList.toggle("selected",i===selectedSlot));buildWatch();if(chartSlots[index].decision)applyDecision(chartSlots[index],chartSlots[index].decision);scanSelected()});
    chartSlots.push({index,symbol,cell,head,chartHost,signalBadge,status,chart:null,candles:null,volume:null,ema20:null,ema50:null,vwap:null,bbUpper:null,bbLower:null,rsi:null,signalLines:[],decision:null,data:[],cryptoSocket:null,cryptoTimer:null,pendingCrypto:null});
    loads.push(loadSlot(index));
  }
  return Promise.allSettled(loads);
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
  slot.data=(payload.candles||[]).map(row=>({time:Number(row.time??row.timestamp),open:Number(row.open),high:Number(row.high),low:Number(row.low),close:Number(row.close),volume:Number(row.volume||0)})).filter(row=>Number.isFinite(row.time)&&Number.isFinite(row.close));
  slot.candles.setData(slot.data.map(({time,open,high,low,close})=>({time,open,high,low,close})));
  slot.volume.setData(slot.data.map(row=>({time:row.time,value:row.volume,color:row.close>=row.open?"rgba(97,230,154,.28)":"rgba(255,102,125,.28)"})));
  updateIndicators(slot);
  slot.chart.timeScale().fitContent();
}

async function loadSlot(index){
  const slot=chartSlots[index];if(!slot)return;
  if(slot.cryptoSocket){try{slot.cryptoSocket.close()}catch{}slot.cryptoSocket=null}
  const symbol=slot.symbol;const meta=marketMeta(symbol);
  slot.head.querySelector("strong").textContent=meta.label;slot.head.querySelector("span").textContent=`${timeframe} · LOADING`;
  setStatus(slot,`Loading ${meta.label} ${timeframe} candles…`);
  try{
    const params=new URLSearchParams({symbol,timeframe,bars:"700"});
    const payload=await fetchJson(`/api/candles?${params}`,{},32000);
    if(!payload.success||!payload.candles?.length)throw new Error(payload.message||"Verified candles unavailable.");
    createSeries(slot,payload);
    slot.head.querySelector("span").textContent=`${timeframe} · ${payload.source}`;
    setStatus(slot,`${payload.source} · ${payload.provider_symbol} · ${payload.bars} bars · ${payload.data_quality}`,"live");
    if(meta.kind==="CRYPTO")connectCryptoSocket(slot);else pollSlotLive(slot);
  }catch(error){
    setStatus(slot,error.message||"Market data unavailable.","error");
    slot.head.querySelector("span").textContent=`${timeframe} · DATA UNAVAILABLE`;
  }
}

function applyLivePrice(slot,snapshot){
  if(!slot?.candles||!snapshot||snapshot.ltp==null)return;
  const price=Number(snapshot.ltp);if(!Number.isFinite(price))return;
  const now=bucketTime(currentEpoch(snapshot),timeframe);const last=slot.data[slot.data.length-1];
  let candle;
  if(last&&Number(last.time)===now){
    candle={...last,high:Math.max(Number(last.high),price),low:Math.min(Number(last.low),price),close:price};
    if(snapshot.volume!=null&&Number.isFinite(Number(snapshot.volume)))candle.volume=Number(snapshot.volume);
    slot.data[slot.data.length-1]=candle;
  }else{
    const open=last?Number(last.close):price;candle={time:now,open,high:Math.max(open,price),low:Math.min(open,price),close:price,volume:Number(snapshot.volume||0)};slot.data.push(candle);
  }
  slot.candles.update({time:candle.time,open:candle.open,high:candle.high,low:candle.low,close:candle.close});
  slot.volume.update({time:candle.time,value:candle.volume||0,color:candle.close>=candle.open?"rgba(97,230,154,.28)":"rgba(255,102,125,.28)"});
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
  try{const payload=await fetchJson(`/api/live?${new URLSearchParams({symbol:item.symbol})}`,{},6000);if(payload.success&&payload.snapshot)updateWatchTile(item.symbol,payload.snapshot,{degraded:Boolean(payload.stream_degraded||payload.stale)});else updateWatchTile(item.symbol,null,{message:payload.message||"data unavailable"})}catch(error){updateWatchTile(item.symbol,null,{message:error.message})}
}

async function refreshAllWatch(){
  await Promise.allSettled(MARKETS.map(async item=>{
    try{const payload=await fetchJson(`/api/live?${new URLSearchParams({symbol:item.symbol})}`,{},10000);if(payload.success&&payload.snapshot)updateWatchTile(item.symbol,payload.snapshot,{degraded:Boolean(payload.stream_degraded||payload.stale)});else updateWatchTile(item.symbol,null,{message:payload.message||"data unavailable"})}catch(error){updateWatchTile(item.symbol,null,{message:error.message})}
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
    if(result.chart){await openSignalChart(result.chart,result.decision)}
    else if(result.action==="set_layout"&&Number(result.layout)){layout=[1,2,4,6,8].includes(Number(result.layout))?Number(result.layout):layout;selectedSlot=0;syncControls();await mountCharts()}
    else if(result.action==="open_quant"&&result.symbol){await openSignalChart({symbol:result.symbol,timeframe,layout:1},result.decision)}
  }catch(error){$("commandReply").textContent=error.message}
}

function syncControls(){document.querySelectorAll("[data-layout]").forEach(button=>button.classList.toggle("active",Number(button.dataset.layout)===layout));document.querySelectorAll("[data-timeframe]").forEach(button=>button.classList.toggle("active",button.dataset.timeframe===timeframe));document.querySelectorAll("[data-indicator]").forEach(button=>button.classList.toggle("active",Boolean(indicatorState[button.dataset.indicator])))}

function bindControls(){
  document.querySelectorAll("[data-layout]").forEach(button=>button.addEventListener("click",()=>{layout=Number(button.dataset.layout);selectedSlot=0;syncControls();mountCharts()}));
  document.querySelectorAll("[data-timeframe]").forEach(button=>button.addEventListener("click",async()=>{timeframe=button.dataset.timeframe;analysisProfile=timeframe==="1d"?"swing":"intraday";syncControls();await Promise.allSettled(chartSlots.map((_,i)=>loadSlot(i)));scanSelected()}));
  document.querySelectorAll("[data-indicator]").forEach(button=>button.addEventListener("click",()=>{const key=button.dataset.indicator;indicatorState[key]=!indicatorState[key];syncControls();chartSlots.forEach(updateIndicators)}));
  $("fitButton").addEventListener("click",()=>chartSlots.forEach(slot=>slot.chart?.timeScale().fitContent()));
  $("reloadCharts").addEventListener("click",()=>chartSlots.forEach((_,i)=>loadSlot(i)));
  $("scanButton").addEventListener("click",scanSelected);
  $("sendCommand").addEventListener("click",sendCommand);$("commandInput").addEventListener("keydown",event=>{if(event.key==="Enter")sendCommand()});
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
  const params=new URLSearchParams(window.location.search);const raw=String(params.get("symbol")||"").toUpperCase().replaceAll(" ","");let found=MARKETS.find(item=>item.symbol===raw||item.label.toUpperCase().replaceAll(" ","")===raw);if(!found&&raw){found={symbol:raw,label:raw,kind:"INDIA_EQUITY"};MARKETS.push(found)}if(found)selectedSymbol=found.symbol;const tf=params.get("timeframe");if(tf&&["1m","3m","5m","15m","30m","1h","2h","4h","1d"].includes(tf))timeframe=tf;analysisProfile=params.get("profile")||(timeframe==="1d"?"swing":"intraday");if(params.get("analyze")==="1")layout=1;
  buildWatch();bindControls();syncControls();const watchHydration=refreshAllWatch();await mountCharts();refreshProvider();startTimers();await watchHydration;if(params.get("analyze")==="1")await scanSelected();
}
bootstrap();
