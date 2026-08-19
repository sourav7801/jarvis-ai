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
let selectedSlot=0;
let selectedSymbol="NIFTY";
let chartSlots=[];
let liveTimer=null;
let providerTimer=null;
let watchCursor=0;

function marketMeta(symbol){return MARKETS.find(item=>item.symbol===symbol)||{symbol,label:symbol,kind:"INDIA"}}
function fmt(value,digits=2){const n=Number(value);return Number.isFinite(n)?n.toLocaleString("en-IN",{maximumFractionDigits:digits,minimumFractionDigits:digits}):"—"}
function escapeHtml(value){return String(value??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]))}
function secondsFor(tf){return {"1m":60,"3m":180,"5m":300,"15m":900,"30m":1800,"1h":3600,"2h":7200,"4h":14400,"1d":86400}[tf]||300}
function bucketTime(epoch,tf){const size=secondsFor(tf);return Math.floor(Number(epoch)/size)*size}
function currentEpoch(snapshot){const raw=Number(snapshot?.exchange_timestamp);if(Number.isFinite(raw)&&raw>0)return raw>1e12?Math.floor(raw/1000):Math.floor(raw);return Math.floor(Date.now()/1000)}

function buildWatch(){
  const host=$("marketWatch");
  host.innerHTML="";
  MARKETS.forEach(item=>{
    const button=document.createElement("button");
    button.className="market-tile"+(item.symbol===selectedSymbol?" active":"");
    button.dataset.symbol=item.symbol;
    button.innerHTML=`<strong>${item.label}</strong><span class="price" data-watch-price>—</span><small>${item.kind==="CRYPTO"?"PUBLIC CRYPTO":"BROKER DATA"}</small><em data-watch-change>waiting</em>`;
    button.addEventListener("click",()=>selectMarket(item.symbol));
    host.appendChild(button);
  });
}

function updateWatchTile(symbol,snapshot){
  const tile=document.querySelector(`.market-tile[data-symbol="${symbol}"]`);if(!tile)return;
  const price=tile.querySelector("[data-watch-price]");const change=tile.querySelector("[data-watch-change]");
  if(!snapshot||snapshot.ltp==null){price.textContent="—";change.textContent="no live snapshot";return}
  price.textContent=fmt(snapshot.ltp);
  const pct=Number(snapshot.change_percent);const diff=Number(snapshot.change);const sign=diff>0?"+":"";
  change.textContent=(Number.isFinite(diff)?`${sign}${diff.toFixed(2)}`:"")+(Number.isFinite(pct)?` (${pct>0?"+":""}${pct.toFixed(2)}%)`:"");
  change.style.color=diff>0?"#78f2aa":diff<0?"#ff6f83":"#7e9aa7";
}

function selectMarket(symbol){
  selectedSymbol=symbol;
  const meta=marketMeta(symbol);$("scanSymbol").textContent=meta.label;
  document.querySelectorAll(".market-tile").forEach(tile=>tile.classList.toggle("active",tile.dataset.symbol===symbol));
  if(chartSlots[selectedSlot]){
    chartSlots[selectedSlot].symbol=symbol;
    loadSlot(selectedSlot);
  }
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
  if(slot.chart){try{slot.chart.remove()}catch{}slot.chart=null}
}

function mountCharts(){
  const host=$("chartGrid");
  chartSlots.forEach(destroySlot);
  chartSlots=[];
  host.innerHTML="";
  host.className=`chart-grid layout-${layout}`;
  for(let index=0;index<layout;index++){
    const symbol=SLOT_DEFAULTS[index]||"NIFTY";
    const cell=document.createElement("div");cell.className="chart-cell"+(index===selectedSlot?" selected":"");cell.dataset.slot=String(index);
    const head=document.createElement("div");head.className="chart-head";
    head.innerHTML=`<strong>${marketMeta(symbol).label}</strong><span>${timeframe} · LOADING</span>`;
    const chartHost=document.createElement("div");chartHost.className="chart-host";
    const status=document.createElement("div");status.className="chart-status";status.textContent="Loading verified candles…";
    cell.append(head,chartHost,status);host.appendChild(cell);
    cell.addEventListener("click",()=>{selectedSlot=index;selectedSymbol=chartSlots[index].symbol;$("scanSymbol").textContent=marketMeta(selectedSymbol).label;document.querySelectorAll(".chart-cell").forEach((node,i)=>node.classList.toggle("selected",i===selectedSlot));buildWatch()});
    chartSlots.push({index,symbol,cell,head,chartHost,status,chart:null,candles:null,volume:null,data:[],cryptoSocket:null});
    loadSlot(index);
  }
}

function setStatus(slot,text,kind=""){slot.status.textContent=text;slot.status.className="chart-status"+(kind?` ${kind}`:"")}

function createSeries(slot,payload){
  if(typeof LightweightCharts==="undefined")throw new Error("Lightweight Charts library did not load.");
  destroySlot(slot);
  slot.chart=LightweightCharts.createChart(slot.chartHost,chartOptions());
  slot.candles=slot.chart.addSeries(LightweightCharts.CandlestickSeries,{upColor:"#61e69a",downColor:"#ff667d",wickUpColor:"#61e69a",wickDownColor:"#ff667d",borderVisible:false,priceLineColor:"#5cdbff",priceLineWidth:1});
  slot.volume=slot.chart.addSeries(LightweightCharts.HistogramSeries,{priceFormat:{type:"volume"},priceScaleId:"",color:"rgba(92,219,255,.28)"});
  slot.volume.priceScale().applyOptions({scaleMargins:{top:.82,bottom:0}});
  slot.data=(payload.candles||[]).map(row=>({time:Number(row.time??row.timestamp),open:Number(row.open),high:Number(row.high),low:Number(row.low),close:Number(row.close),volume:Number(row.volume||0)})).filter(row=>Number.isFinite(row.time)&&Number.isFinite(row.close));
  slot.candles.setData(slot.data.map(({time,open,high,low,close})=>({time,open,high,low,close})));
  slot.volume.setData(slot.data.map(row=>({time:row.time,value:row.volume,color:row.close>=row.open?"rgba(97,230,154,.28)":"rgba(255,102,125,.28)"})));
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
    const response=await fetch(`/api/candles?${params}`);const payload=await response.json();
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
  slot.head.querySelector("span").textContent=`${timeframe} · LIVE ${fmt(price)}`;setStatus(slot,`${marketMeta(slot.symbol).kind==="CRYPTO"?"CRYPTO TICK":"FYERS LIVE"} · ${fmt(price)} · ${new Date().toLocaleTimeString()}`,"live");
  updateWatchTile(slot.symbol,snapshot);
}

async function pollSlotLive(slot){
  if(!slot||!slot.cell.isConnected||marketMeta(slot.symbol).kind==="CRYPTO")return;
  try{const response=await fetch(`/api/live?${new URLSearchParams({symbol:slot.symbol})}`);const payload=await response.json();if(payload.success&&payload.snapshot)applyLivePrice(slot,payload.snapshot)}catch{}
}

function connectCryptoSocket(slot){
  const provider={BTC:"btcusdt",ETH:"ethusdt",SOL:"solusdt"}[slot.symbol];if(!provider)return;
  try{
    const socket=new WebSocket(`wss://stream.binance.com:9443/ws/${provider}@trade`);slot.cryptoSocket=socket;
    socket.onmessage=event=>{try{const trade=JSON.parse(event.data);applyLivePrice(slot,{ltp:Number(trade.p),exchange_timestamp:Math.floor(Number(trade.T)/1000),volume:Number(trade.q)})}catch{}};
    socket.onerror=()=>{setStatus(slot,"Crypto WebSocket unavailable; REST fallback will continue.","error")};
  }catch{}
}

async function refreshProvider(){
  try{
    const response=await fetch("/api/provider");const payload=await response.json();
    const button=$("providerButton");const state=payload.state||"UNKNOWN";button.textContent=`FYERS · ${state.replaceAll("_"," ")}`;button.className="status-pill "+(state==="CONNECTED"?"connected":state==="LOGIN_REQUIRED"?"error":"warn");
    $("providerState").textContent=state.replaceAll("_"," ");
    const error=payload.bridge?.error;$("providerMessage").textContent=state==="CONNECTED"?"Read-only FYERS live stream connected.":error||"FYERS session is not live. Use the local login button if today's token has expired.";
  }catch(error){$("providerState").textContent="UNAVAILABLE";$("providerMessage").textContent=error.message}
}

async function refreshOneWatch(){
  const item=MARKETS[watchCursor%MARKETS.length];watchCursor++;
  try{const response=await fetch(`/api/live?${new URLSearchParams({symbol:item.symbol})}`);const payload=await response.json();if(payload.success&&payload.snapshot)updateWatchTile(item.symbol,payload.snapshot)}catch{}
}

async function scanSelected(){
  const symbol=selectedSymbol;$("scanRegime").textContent="SCANNING";$("scanBias").textContent="WORKING";$("scanAlignment").textContent="—";$("setupState").textContent="WAITING";$("evidenceList").innerHTML="<p>Loading verified 5m / 15m / 1h evidence…</p>";
  try{
    const response=await fetch(`/api/scan?${new URLSearchParams({symbol})}`);const payload=await response.json();
    $("scanRegime").textContent=payload.regime||"UNAVAILABLE";$("scanBias").textContent=payload.bias||"NO BIAS";$("scanAlignment").textContent=`${Number(payload.alignment||0)}% ALIGN`;
    const setup=payload.setup;$("setupState").textContent=setup?`${setup.side} · ${setup.status}`:"NO QUALIFIED SETUP";$("entryRef").textContent=setup?fmt(setup.entry_reference):"—";$("stopRef").textContent=setup?fmt(setup.stop_reference):"—";$("targetRef").textContent=setup?fmt(setup.target_reference):"—";$("rrRef").textContent=setup?`${setup.risk_reward_reference}:1`:"—";
    const evidence=Array.isArray(payload.evidence)?payload.evidence:[];$("evidenceList").innerHTML=evidence.map(row=>{if(!row.available)return `<div class="evidence-row"><div class="topline"><b>${escapeHtml(row.timeframe)}</b><span>NO DATA</span></div><p>${escapeHtml(row.message||"")}</p></div>`;const cls=row.trend==="BULLISH"?"bull":row.trend==="BEARISH"?"bear":"";return `<div class="evidence-row ${cls}"><div class="topline"><b>${escapeHtml(row.timeframe)} · ${escapeHtml(row.trend)}</b><span>${escapeHtml(row.source||"")}</span></div><p>Close ${fmt(row.close)} · EMA20 ${fmt(row.ema20)} · EMA50 ${fmt(row.ema50)} · RSI ${fmt(row.rsi14,1)} · ATR ${fmt(row.atr14)} · Vol× ${row.volume_ratio==null?"—":fmt(row.volume_ratio,2)}</p></div>`}).join("")||"<p>No timeframe evidence.</p>";
    $("commandReply").textContent=payload.message||"Scan complete.";
  }catch(error){$("scanRegime").textContent="DATA ERROR";$("scanBias").textContent="NO SCAN";$("evidenceList").innerHTML=`<p>${escapeHtml(error.message)}</p>`}
}

async function sendCommand(){
  const input=$("commandInput");const text=input.value.trim();if(!text)return;$("commandReply").textContent="JARVIS is routing the trading command…";
  try{
    const response=await fetch("/api/agent",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({text})});const result=await response.json();$("commandReply").textContent=result.speech||result.message||"Command processed.";
    if(result.action==="set_layout"&&Number(result.layout)){layout=[1,2,4,6,8].includes(Number(result.layout))?Number(result.layout):layout;selectedSlot=0;syncControls();mountCharts()}
    if(result.action==="set_chart"&&result.chart){const raw=String(result.chart.label||result.chart.symbol||"").toUpperCase().replaceAll(" ","");const found=MARKETS.find(item=>item.symbol===raw||item.label.toUpperCase().replaceAll(" ","")===raw);if(found)selectMarket(found.symbol)}
    if(result.action==="open_quant"&&result.symbol){const raw=String(result.symbol).toUpperCase().replaceAll(" ","");const found=MARKETS.find(item=>item.symbol===raw||item.label.toUpperCase().replaceAll(" ","")===raw);if(found){selectMarket(found.symbol);scanSelected()}}
  }catch(error){$("commandReply").textContent=error.message}
}

function syncControls(){document.querySelectorAll("[data-layout]").forEach(button=>button.classList.toggle("active",Number(button.dataset.layout)===layout));document.querySelectorAll("[data-timeframe]").forEach(button=>button.classList.toggle("active",button.dataset.timeframe===timeframe))}

function bindControls(){
  document.querySelectorAll("[data-layout]").forEach(button=>button.addEventListener("click",()=>{layout=Number(button.dataset.layout);selectedSlot=0;syncControls();mountCharts()}));
  document.querySelectorAll("[data-timeframe]").forEach(button=>button.addEventListener("click",()=>{timeframe=button.dataset.timeframe;syncControls();chartSlots.forEach((_,i)=>loadSlot(i))}));
  $("fitButton").addEventListener("click",()=>chartSlots.forEach(slot=>slot.chart?.timeScale().fitContent()));
  $("reloadCharts").addEventListener("click",()=>chartSlots.forEach((_,i)=>loadSlot(i)));
  $("scanButton").addEventListener("click",scanSelected);
  $("sendCommand").addEventListener("click",sendCommand);$("commandInput").addEventListener("keydown",event=>{if(event.key==="Enter")sendCommand()});
  $("loginButton").addEventListener("click",async()=>{try{const response=await fetch("/api/fyers/login",{method:"POST",headers:{"Content-Type":"application/json"},body:"{}"});const payload=await response.json();$("providerMessage").textContent=payload.message||"FYERS login launched."}catch(error){$("providerMessage").textContent=error.message}});
  $("restartButton").addEventListener("click",async()=>{try{await fetch("/api/market/restart",{method:"POST",headers:{"Content-Type":"application/json"},body:"{}"});setTimeout(refreshProvider,700);chartSlots.forEach((_,i)=>loadSlot(i))}catch(error){$("providerMessage").textContent=error.message}});
  $("providerButton").addEventListener("click",()=>$("providerState").scrollIntoView({behavior:"smooth",block:"center"}));
}

function startTimers(){
  if(liveTimer)clearInterval(liveTimer);liveTimer=setInterval(()=>{chartSlots.forEach(slot=>{if(marketMeta(slot.symbol).kind==="INDIA")pollSlotLive(slot)});refreshOneWatch()},1200);
  if(providerTimer)clearInterval(providerTimer);providerTimer=setInterval(refreshProvider,5000);
}

buildWatch();bindControls();syncControls();mountCharts();refreshProvider();startTimers();
