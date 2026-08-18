
const fallbackCharts=[
  {symbol:"NIFTY",label:"NIFTY 50",interval:"5",range:"3M"},
  {symbol:"BANKNIFTY",label:"BANKNIFTY",interval:"5",range:"3M"},
  {symbol:"SENSEX",label:"SENSEX",interval:"5",range:"3M"},
  {symbol:"NIFTY",label:"NIFTY 50",interval:"15",range:"3M"}
];
let state={layout:4,charts:fallbackCharts.map(chart=>({...chart})),selected:0,conversations:{}};
const messageIds=new Map();
let recognition=null;
let listening=false;
let voiceArmed=false;
let voiceMasterMode=false;
let speechInProgress=false;
let voiceRestartTimer=null;
let recognitionContext="master";
let activeContext="master";
let voiceErrorMessage="";
const sendingContexts=new Set();
let chartMountVersion=0;
let currentNewsQuery="India markets NIFTY Sensex";
let newsLoaded=false;
let companyLoaded=false;
let missionLoaded=false;
let webLoaded=false;
let systemLoaded=false;
let paperLoaded=false;
let currentQuantSymbol="BANKNIFTY";
let pendingVoiceCommand=null;
let paperAlertInitialized=false;
const seenPaperOrders=new Set();
const paperSignalStates=new Map();

const tokenParams=new URLSearchParams(window.location.search);
const suppliedToken=tokenParams.get("token");
if(suppliedToken){sessionStorage.setItem("jarvisApiToken",suppliedToken);history.replaceState({},"",window.location.pathname)}
const apiToken=sessionStorage.getItem("jarvisApiToken")||"";

function apiFetch(url,options={}){
  const headers=new Headers(options.headers||{});
  if(apiToken)headers.set("X-Jarvis-Token",apiToken);
  return fetch(url,{...options,headers});
}

async function responseJson(response,fallbackMessage="JARVIS request failed."){
  let payload={};
  try{payload=await response.json()}catch{}
  if(!response.ok){
    const message=response.status===401
      ?"Dashboard authorization expired. Close this tab and launch JARVIS again."
      :(payload.error||fallbackMessage);
    throw new Error(message);
  }
  return payload;
}

function normalizeState(payload){
  if(!payload||typeof payload!=="object"||Array.isArray(payload))throw new Error("Invalid dashboard state.");
  const allowedLayouts=new Set([1,2,3,4,6,8]);
  const layout=allowedLayouts.has(Number(payload.layout))?Number(payload.layout):state.layout;
  const charts=Array.isArray(payload.charts)&&payload.charts.length
    ?payload.charts
    :(Array.isArray(state.charts)&&state.charts.length?state.charts:fallbackCharts);
  return {...state,...payload,layout,charts,conversations:payload.conversations||state.conversations||{}};
}

const $=id=>document.getElementById(id);

function conversationShell(context){
  return document.querySelector(`.conversation[data-chat-context="${context}"]`);
}

function setOmniStatus(label,state="READY"){
  const route=$("omniState");
  const agent=$("omniAgent");
  if(route)route.textContent=label;
  if(agent)agent.textContent=state;
}

function voiceInput(context){
  if(context==="master"&&voiceMasterMode&&$("omniInput"))return $("omniInput");
  return conversationShell(context)?.querySelector("input");
}

function addMessage(context,role,text,id){
  const shell=conversationShell(context);
  if(!shell)return;
  if(!messageIds.has(context))messageIds.set(context,new Set());
  const known=messageIds.get(context);
  if(id!=null&&known.has(id))return;
  if(id!=null)known.add(id);
  const d=document.createElement("div");
  d.className="msg "+role;
  d.innerHTML=`<span class="tag">${role==="assistant"?"JARVIS":"YOU"}</span>${String(text).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]))}`;
  const chat=shell.querySelector(".chat");
  chat.appendChild(d);
  chat.scrollTop=chat.scrollHeight;
}

function speak(text){
  if(!("speechSynthesis" in window))return;
  speechSynthesis.cancel();
  speechInProgress=true;
  setVoiceVisual("speaking","JARVIS SPEAKING");
  if(listening&&recognition){try{recognition.stop()}catch{}}
  const u=new SpeechSynthesisUtterance(text);
  u.lang="en-IN";u.rate=1;u.pitch=.95;
  u.onend=u.onerror=()=>{speechInProgress=false;setVoiceVisual(voiceArmed?"armed":"ready",voiceArmed?"VOICE ARMED":"VOICE READY");scheduleVoiceRestart()};
  speechSynthesis.speak(u);
}

const intervalTimeframes={"1":"1m","2":"2m","3":"3m","5":"5m","10":"10m","15":"15m","20":"20m","30":"30m","60":"1h","120":"2h","240":"4h","D":"1d","W":"1wk"};
const chartSymbolAliases={"NSE:NIFTY":"NIFTY","NSE:BANKNIFTY":"BANKNIFTY","BSE:SENSEX":"SENSEX"};

function candleCountFor(chart){
  const sessions={"1M":22,"2M":44,"3M":66,"6M":132,"12M":264,"24M":528,"60M":1320}[chart.range]||66;
  const interval=String(chart.interval||"5");
  let count;
  if(interval==="D")count=sessions;
  else if(interval==="W")count=Math.ceil(sessions/5);
  else count=Math.ceil(sessions*375/Math.max(Number(interval)||5,1));
  return Math.min(Math.max(count,30),7500);
}

function aggregateCandles(candles,maxPoints){
  if(candles.length<=maxPoints)return candles;
  const size=Math.ceil(candles.length/maxPoints);
  const result=[];
  for(let i=0;i<candles.length;i+=size){
    const group=candles.slice(i,i+size);
    result.push({
      timestamp:group[group.length-1].timestamp,
      open:group[0].open,
      high:Math.max(...group.map(c=>Number(c.high))),
      low:Math.min(...group.map(c=>Number(c.low))),
      close:group[group.length-1].close,
      volume:group.reduce((sum,c)=>sum+(Number(c.volume)||0),0)
    });
  }
  return result;
}

function drawCandles(canvas,input){
  const rect=canvas.getBoundingClientRect();
  const width=Math.max(Math.floor(rect.width),320);
  const height=Math.max(Math.floor(rect.height),230);
  const ratio=Math.max(window.devicePixelRatio||1,1);
  canvas.width=Math.floor(width*ratio);
  canvas.height=Math.floor(height*ratio);
  const ctx=canvas.getContext("2d");
  ctx.scale(ratio,ratio);
  ctx.fillStyle="#070d12";
  ctx.fillRect(0,0,width,height);

  const left=12,right=66,top=12,bottom=48;
  const priceBottom=height-bottom;
  const plotWidth=width-left-right;
  const plotHeight=priceBottom-top;
  const candles=aggregateCandles(input,Math.max(Math.floor(plotWidth/2),30));
  const high=Math.max(...candles.map(c=>Number(c.high)));
  const low=Math.min(...candles.map(c=>Number(c.low)));
  const padding=Math.max((high-low)*.05,high*.0005,1);
  const ceiling=high+padding,floor=low-padding,span=ceiling-floor;
  const y=value=>top+(ceiling-Number(value))/span*plotHeight;

  ctx.font="10px Segoe UI";
  ctx.textAlign="left";
  ctx.lineWidth=1;
  for(let i=0;i<=4;i++){
    const yy=top+plotHeight*i/4;
    const price=ceiling-span*i/4;
    ctx.strokeStyle="rgba(96,220,255,.09)";
    ctx.beginPath();ctx.moveTo(left,yy);ctx.lineTo(width-right,yy);ctx.stroke();
    ctx.fillStyle="#76909c";
    ctx.fillText(price.toLocaleString("en-IN",{maximumFractionDigits:2}),width-right+6,yy+3);
  }

  const step=plotWidth/candles.length;
  const bodyWidth=Math.max(Math.min(step*.68,8),1);
  candles.forEach((c,index)=>{
    const x=left+step*(index+.5);
    const open=y(c.open),close=y(c.close),wickHigh=y(c.high),wickLow=y(c.low);
    const rising=Number(c.close)>=Number(c.open);
    ctx.strokeStyle=rising?"#75f2a7":"#ff7285";
    ctx.fillStyle=ctx.strokeStyle;
    ctx.beginPath();ctx.moveTo(x,wickHigh);ctx.lineTo(x,wickLow);ctx.stroke();
    ctx.fillRect(x-bodyWidth/2,Math.min(open,close),bodyWidth,Math.max(Math.abs(close-open),1));
  });

  const first=new Date(input[0].timestamp);
  const last=new Date(input[input.length-1].timestamp);
  ctx.fillStyle="#76909c";
  ctx.textAlign="left";
  ctx.fillText(first.toLocaleDateString("en-IN",{timeZone:"Asia/Kolkata",day:"2-digit",month:"short",year:"2-digit"}),left,height-17);
  ctx.textAlign="right";
  ctx.fillText(last.toLocaleString("en-IN",{timeZone:"Asia/Kolkata",day:"2-digit",month:"short",hour:"2-digit",minute:"2-digit"}),width-right,height-17);
  const finalClose=Number(input[input.length-1].close);
  ctx.fillStyle="#60dcff";
  ctx.textAlign="right";
  ctx.fillText(finalClose.toLocaleString("en-IN",{minimumFractionDigits:2,maximumFractionDigits:2}),width-right-4,Math.max(y(finalClose)-5,12));
}

async function loadChart(cell,chart,version){
  const status=cell.querySelector(".chart-status");
  const canvas=cell.querySelector("canvas");
  const symbol=chartSymbolAliases[chart.symbol]||chart.symbol||"NIFTY";
  const timeframe=intervalTimeframes[String(chart.interval||"5")]||"5m";
  const bars=candleCountFor(chart);
  try{
    const params=new URLSearchParams({symbol,timeframe,bars:String(bars)});
    const response=await apiFetch(`/api/candles?${params}`);
    const payload=await response.json();
    if(version!==chartMountVersion||!cell.isConnected)return;
    if(!response.ok||!payload.success||!payload.candles?.length)throw new Error(payload.message||"FYERS candles unavailable");
    drawCandles(canvas,payload.candles);
    status.textContent=`FYERS · ${payload.provider_symbol||symbol} · ${payload.bars} candles · ${chart.range||"3M"}`;
  }catch(error){
    if(version!==chartMountVersion||!cell.isConnected)return;
    status.textContent=error.message||"Unable to load FYERS candles.";
    status.classList.add("error");
  }
}

function mountCharts(){
  const version=++chartMountVersion;
  const host=$("charts");
  host.className=`chart-grid layout${state.layout}`;
  host.innerHTML="";
  const sourceCharts=Array.isArray(state.charts)?state.charts:fallbackCharts;
  const charts=sourceCharts.slice(0,state.layout);

  while(charts.length<state.layout){
    charts.push({symbol:"NIFTY",label:"NIFTY 50",interval:"5",range:"3M"});
  }

  charts.forEach((c,idx)=>{
    const cell=document.createElement("div");
    cell.className="chart-cell";
    const toolbar=document.createElement("div");
    toolbar.className="chart-toolbar";
    const name=document.createElement("strong");
    name.textContent=c.label||c.symbol;
    const meta=document.createElement("span");
    meta.textContent=`${intervalTimeframes[String(c.interval)]||"5m"} · ${c.range||"3M"} · BROKER OHLCV`;
    toolbar.append(name,meta);
    const canvas=document.createElement("canvas");
    canvas.className="fy-chart";
    const status=document.createElement("div");
    status.className="chart-status";
    status.textContent="Loading FYERS candles…";
    cell.append(toolbar,canvas,status);
    host.appendChild(cell);
    loadChart(cell,c,version);
  });
  $("layoutMetric").textContent=state.layout;
}

function formatMarketNumber(value){
  const number=Number(value);
  if(!Number.isFinite(number))return "—";
  return new Intl.NumberFormat("en-IN",{minimumFractionDigits:2,maximumFractionDigits:2}).format(number);
}

function renderMarket(market){
  if(!market)return;
  const stream=market.stream||{};
  const badge=$("marketFeedBadge");
  if(stream.connected){
    badge.textContent="FYERS LIVE DATA · NO LIVE EXECUTION";
  }else if(stream.running){
    badge.textContent="FYERS CONNECTING · NO LIVE EXECUTION";
  }else if(stream.configured){
    badge.textContent="FYERS DATA UNAVAILABLE · NO LIVE EXECUTION";
  }else{
    badge.textContent="FYERS LOGIN REQUIRED · NO LIVE EXECUTION";
  }

  const cards={
    NIFTY:["niftyPrice","niftyChange"],
    BANKNIFTY:["bankniftyPrice","bankniftyChange"],
    SENSEX:["sensexPrice","sensexChange"]
  };
  Object.entries(cards).forEach(([symbol,ids])=>{
    const snapshot=(market.symbols||{})[symbol];
    const price=$(ids[0]);
    const detail=$(ids[1]);
    if(!snapshot||snapshot.ltp==null){
      price.textContent="—";
      detail.textContent=stream.connected?"Awaiting first FYERS tick":"Awaiting FYERS market data";
      detail.className="neutral";
      return;
    }
    price.textContent=formatMarketNumber(snapshot.ltp);
    const change=Number(snapshot.change);
    const percent=Number(snapshot.change_percent);
    const sign=change>0?"+":"";
    detail.textContent=(Number.isFinite(change)?`${sign}${change.toFixed(2)}`:"—")+
      (Number.isFinite(percent)?` (${sign}${percent.toFixed(2)}%)`:"")+
      ` · ${snapshot.snapshot_kind==="QUOTE_SEED"?"QUOTE":"LIVE"}`;
    detail.className=change>0?"positive":change<0?"negative":"neutral";
  });
}

async function refreshMarket(){
  try{
    const response=await apiFetch("/api/market");
    if(!response.ok)return;
    renderMarket(await response.json());
  }catch{}
}

function switchPage(name){
  document.querySelectorAll(".page").forEach(p=>p.classList.remove("active"));
  const page=$(`page-${name}`);
  if(page)page.classList.add("active");
  activeContext={command:"master",system:"system",mission:"mission",web:"web",charts:"charts",quant:"quant",paper:"paper",news:"news",company:"company"}[name]||"master";
  if(voiceArmed&&!voiceMasterMode)recognitionContext=activeContext;
  document.querySelectorAll("[data-page]").forEach(button=>button.classList.toggle("active",button.dataset.page===name));
  if(name==="charts")requestAnimationFrame(mountCharts);
  if(name==="quant")refreshTradingIntelligence(currentQuantSymbol);
  if(name==="paper")refreshPaper();
  if(name==="company"&&!companyLoaded)refreshCompany();
  if(name==="mission"&&!missionLoaded)refreshMission();
  if(name==="web"&&!webLoaded)refreshWeb();
  if(name==="system"&&!systemLoaded)refreshControlPlane();
}

function formatCurrency(value){
  const number=Number(value);
  if(!Number.isFinite(number))return "—";
  return new Intl.NumberFormat("en-IN",{style:"currency",currency:"INR",maximumFractionDigits:2}).format(number);
}

function pnlClass(value){
  const number=Number(value);
  return number>0?"positive":number<0?"negative":"";
}

function emptyPaperRow(message){
  const node=document.createElement("div");
  node.className="paper-empty";
  node.textContent=message;
  return node;
}

function showJarvisAlert(title,message,{speakAlert=false}={}){
  const host=$("jarvisAlerts");
  if(host){
    const alert=document.createElement("div");alert.className="jarvis-alert";
    const heading=document.createElement("b");heading.textContent=title;
    const detail=document.createElement("span");detail.textContent=message;
    alert.append(heading,detail);host.appendChild(alert);
    requestAnimationFrame(()=>alert.classList.add("visible"));
    setTimeout(()=>{alert.classList.remove("visible");setTimeout(()=>alert.remove(),350)},9000);
  }
  if("Notification" in window&&Notification.permission==="granted"){
    try{new Notification(`JARVIS · ${title}`,{body:message,tag:`jarvis-${title}-${message.slice(0,40)}`})}catch{}
  }
  if(speakAlert&&voiceArmed&&!speechInProgress)speak(`${title}. ${message}`);
}

function enablePaperAlerts(){
  $("paperAlertMode").textContent="TRADE ALERTS ARMED";
  showJarvisAlert("TRADE MONITOR ARMED","JARVIS will alert on newly qualified setups and synthetic paper fills.");
  if("Notification" in window&&Notification.permission==="default"){
    Notification.requestPermission().then(permission=>{
      $("paperAlertMode").textContent=permission==="granted"?"DESKTOP ALERTS ARMED":"IN-APP ALERTS ARMED";
    }).catch(()=>{$("paperAlertMode").textContent="IN-APP ALERTS ARMED"});
  }
}

function processPaperAlerts(paper){
  const orders=Array.isArray(paper?.orders)?paper.orders:[];
  const signals=Array.isArray(paper?.signals)?paper.signals:[];
  if(!paperAlertInitialized){
    orders.forEach(order=>seenPaperOrders.add(order.order_id));
    signals.forEach(signal=>paperSignalStates.set(signal.symbol,`${signal.decision_gate}|${signal.setup}`));
    paperAlertInitialized=true;
    return;
  }
  orders.slice().reverse().forEach(order=>{
    if(!order.order_id||seenPaperOrders.has(order.order_id))return;
    seenPaperOrders.add(order.order_id);
    showJarvisAlert(
      "SYNTHETIC PAPER FILL",
      `${order.side} ${Number(order.quantity).toLocaleString("en-IN")} ${order.symbol} at ${formatMarketNumber(order.price)}. Stop and target are active.`,
      {speakAlert:true}
    );
  });
  signals.forEach(signal=>{
    const next=`${signal.decision_gate}|${signal.setup}`;
    const previous=paperSignalStates.get(signal.symbol);
    paperSignalStates.set(signal.symbol,next);
    if(previous&&previous!==next&&signal.decision_gate==="QUALIFIED"){
      showJarvisAlert(
        "QUALIFIED PAPER SETUP",
        `${signal.symbol} ${String(signal.setup||"").replaceAll("_"," ")} · ${signal.confidence}% alignment · RR ${Number(signal.risk_reward||0).toFixed(2)}.`,
        {speakAlert:true}
      );
    }
  });
}

function renderAutonomy(paper){
  const signals=Array.isArray(paper?.signals)?paper.signals:[];
  const qualified=signals
    .filter(item=>String(item.setup||"").startsWith("PAPER_WATCH")&&Number(item.risk_reward)>=1.8&&item.adaptive_policy?.allowed!==false)
    .sort((a,b)=>(Number(b.confidence)||0)-(Number(a.confidence)||0));
  const learning=paper?.learning||{};
  const reviews=Array.isArray(learning.trade_reviews)?learning.trade_reviews:[];
  const scorecards=Array.isArray(learning.strategy_scorecards)?learning.strategy_scorecards:[];
  const daily=Array.isArray(learning.daily_reviews)?learning.daily_reviews:[];
  $("autoLoopState").textContent=!paper?.market_connected?"WAITING FOR VERIFIED DATA":paper?.autopilot?"AUTONOMOUS PAPER LOOP ARMED":"PAPER LOOP PAUSED";
  const best=qualified[0];
  $("autoBestSetup").textContent=best?`${best.symbol} · ${String(best.setup).replaceAll("_"," ")}`:"NO QUALIFIED SETUP";
  $("autoBestEvidence").textContent=best
    ?`${String(best.strategy||"NO EDGE").replaceAll("_"," ")} · ${best.confidence}% alignment · RR ${Number(best.risk_reward).toFixed(2)} · ${(best.chart_patterns||[]).slice(0,2).join(", ")||"price structure"}`
    :"The engine waits when timeframe, strategy, RR or learning gates fail.";
  const guards=paper?.guardrails||{};
  $("autoRiskState").textContent=`${Number(guards.risk_per_trade_percent||0).toFixed(2)}% RISK · ${paper?.positions?.length||0}/${guards.max_open_positions||6} OPEN`;
  $("autoRiskEvidence").textContent=`Minimum RR ${Number(guards.minimum_risk_reward||1.8).toFixed(1)} · portfolio halt ${guards.portfolio_loss_halt_percent||2}% · every new fill needs a stop and target.`;
  $("autoLearningState").textContent=`${reviews.length} REVIEWED · ${scorecards.length} STRATEGIES`;
  $("autoLearningEvidence").textContent="Losses reduce strategy size; repeated losses trigger a 24-hour strategy cooldown.";
  const today=daily[0];
  $("autoDailyReview").textContent=today?`${today.wins||0}W / ${today.losses||0}L · ${formatCurrency(today.net_pnl)}`:"NO CLOSED TRADES";
  $("autoDailyEvidence").textContent=today?(today.top_review_flags||[]).map(item=>String(item).replaceAll("_"," ")).join(" · ")||today.summary:"The daily review will populate automatically after a paper exit.";

  const feed=$("autoDecisionFeed");feed.replaceChildren();
  const ranked=signals.slice().sort((a,b)=>(Number(b.confidence)||0)-(Number(a.confidence)||0)).slice(0,6);
  if(!ranked.length)feed.appendChild(emptyPaperRow("No multi-asset scan has completed yet."));
  ranked.forEach(signal=>{
    const row=document.createElement("div");row.className="auto-decision-row";
    const symbol=document.createElement("b");symbol.textContent=signal.symbol;
    const decision=document.createElement("span");decision.textContent=String(signal.setup||"WAIT").replaceAll("_"," ");
    const evidence=document.createElement("small");evidence.textContent=`${String(signal.strategy||"NO EDGE").replaceAll("_"," ")} · ${Number(signal.confidence)||0}% · RR ${Number(signal.risk_reward||0).toFixed(1)}`;
    row.append(symbol,decision,evidence);feed.appendChild(row);
  });
  const cards=$("autoScorecards");cards.replaceChildren();
  if(!scorecards.length)cards.appendChild(emptyPaperRow("No reviewed strategy history yet."));
  scorecards.slice(0,6).forEach(card=>{
    const row=document.createElement("div");row.className=`auto-scorecard ${card.status==="COOLING_OFF"?"cooling":""}`;
    const strategy=document.createElement("b");strategy.textContent=String(card.strategy||"UNCLASSIFIED").replaceAll("_"," ");
    const stats=document.createElement("span");stats.textContent=`${card.trades||0} TRADES · ${card.win_rate||0}% WIN · AVG R ${Number(card.average_r||0).toFixed(2)}`;
    const policy=document.createElement("small");policy.textContent=card.status==="COOLING_OFF"?"COOLING OFF":`RISK ×${Number(card.policy?.risk_multiplier||1).toFixed(2)}`;
    row.append(strategy,stats,policy);cards.appendChild(row);
  });
}

function renderPaper(paper){
  if(!paper)return;
  paperLoaded=true;
  const account=paper.account||{};
  $("paperFeed").textContent=paper.market_connected?"MULTI-ASSET DATA READY":"MARKET DATA WAITING";
  $("paperMode").textContent=paper.autopilot?"AUTO-START ARMED":"AUTOPILOT PAUSED";
  $("paperMode").classList.toggle("armed",Boolean(paper.autopilot));
  $("paperArm").disabled=Boolean(paper.autopilot);
  $("paperPause").disabled=!paper.autopilot;
  $("paperNotice").textContent=paper.last_error||(
    paper.autopilot
      ?"Automatic scans require aligned timeframes, a strategy score, minimum 1.8 risk/reward, adaptive eligibility, exposure capacity, and a protected synthetic fill."
      :"Autopilot is paused for this session. It auto-arms the next time JARVIS starts unless you pause it again."
  );
  [["paperEquity",account.equity],["paperCash",account.cash],["paperUnrealized",account.unrealized_pnl],["paperRealized",account.realized_pnl]].forEach(([id,value])=>{
    const node=$(id);node.textContent=formatCurrency(value);node.className=id.includes("Unrealized")||id.includes("Realized")?pnlClass(value):"";
  });
  const positions=Array.isArray(paper.positions)?paper.positions:[];
  const universe=Array.isArray(paper.universe)?paper.universe:[];
  const universeHost=$("paperUniverse");universeHost.replaceChildren();
  universe.forEach(asset=>{
    const chip=document.createElement("div");
    const assetClass=String(asset.asset_class||"asset").toLowerCase();
    chip.className=`paper-asset ${assetClass} ${asset.session_open?"open":"closed"}`;
    const symbol=document.createElement("b");symbol.textContent=asset.symbol;
    const session=document.createElement("span");
    session.textContent=`${String(asset.asset_class||"ASSET").toUpperCase()} · SESSION ${asset.session_open?"OPEN":"CLOSED"}`;
    chip.append(symbol,session);universeHost.appendChild(chip);
  });
  $("paperPositionCount").textContent=`${positions.length} OPEN`;
  const positionHost=$("paperPositions");positionHost.replaceChildren();
  if(!positions.length)positionHost.appendChild(emptyPaperRow("No open synthetic positions. Paper Desk is ready without risking real capital."));
  positions.forEach(position=>{
    const row=document.createElement("div");row.className="paper-row";
    const identity=document.createElement("div");
    const symbol=document.createElement("b");symbol.textContent=`${position.symbol} · ${position.asset_class||"ASSET"}`;
    const side=document.createElement("span");side.className=`paper-side${position.side==="SHORT"?" short":""}`;side.textContent=position.side;
    identity.append(symbol,side);
    const quantity=document.createElement("span");quantity.textContent=`QTY ${Number(position.quantity).toLocaleString("en-IN")}`;
    const average=document.createElement("span");average.textContent=`AVG ${formatMarketNumber(position.average_price)} · SL ${formatMarketNumber(position.stop_loss)} · TP ${formatMarketNumber(position.take_profit)}`;
    const mark=document.createElement("span");mark.textContent=`LTP ${formatMarketNumber(position.current_price)}`;
    const pnl=document.createElement("b");pnl.className=pnlClass(position.unrealized_pnl);pnl.textContent=formatCurrency(position.unrealized_pnl);
    const close=document.createElement("button");close.className="paper-close";close.textContent="CLOSE";close.onclick=()=>closePaperPosition(position.symbol);
    row.append(identity,quantity,average,mark,pnl,close);positionHost.appendChild(row);
  });
  const signalHost=$("paperSignals");signalHost.replaceChildren();
  const signals=Array.isArray(paper.signals)?paper.signals:[];
  if(!signals.length)signalHost.appendChild(emptyPaperRow("No signal scan has completed yet."));
  signals.forEach(signal=>{
    const row=document.createElement("div");row.className="paper-row signal";
    const symbol=document.createElement("b");symbol.textContent=signal.symbol;
    const setup=document.createElement("span");setup.textContent=`${String(signal.setup||"NO SETUP").replaceAll("_"," ")} · ${String(signal.strategy||"NO EDGE").replaceAll("_"," ")} · RR ${Number(signal.risk_reward||0).toFixed(1)}`;
    const confidence=document.createElement("b");confidence.textContent=`${Number(signal.confidence)||0}%`;
    const price=document.createElement("span");
    price.textContent=signal.price==null
      ?String(signal.message||"DATA WAITING")
      :`${signal.currency||"INR"} ${formatMarketNumber(signal.price)}`;
    row.append(symbol,setup,confidence,price);signalHost.appendChild(row);
  });
  const activityHost=$("paperActivity");activityHost.replaceChildren();
  const activity=Array.isArray(paper.activity)?paper.activity:[];
  if(!activity.length)activityHost.appendChild(emptyPaperRow("No paper activity yet."));
  activity.slice(0,12).forEach(item=>{
    const row=document.createElement("div");row.className="paper-row activity";
    const time=document.createElement("span");time.textContent=displaySeenDate(item.timestamp);
    const message=document.createElement("b");message.textContent=item.message;
    row.append(time,message);activityHost.appendChild(row);
  });
  const tradeHost=$("paperTrades");tradeHost.replaceChildren();
  const trades=Array.isArray(paper.trades)?paper.trades:[];
  if(!trades.length)tradeHost.appendChild(emptyPaperRow("No synthetic trade has closed yet."));
  trades.slice(0,12).forEach(trade=>{
    const row=document.createElement("div");row.className="paper-row trade";
    const symbol=document.createElement("b");symbol.textContent=`${trade.symbol} · ${trade.side}`;
    const quantity=document.createElement("span");quantity.textContent=`QTY ${trade.quantity}`;
    const exit=document.createElement("span");exit.textContent=`EXIT ${formatMarketNumber(trade.exit_price)}`;
    const pnl=document.createElement("b");pnl.className=pnlClass(trade.net_pnl);pnl.textContent=formatCurrency(trade.net_pnl);
    row.append(symbol,quantity,exit,pnl);tradeHost.appendChild(row);
  });
  const learning=paper.learning||{};
  const reviews=Array.isArray(learning.trade_reviews)?learning.trade_reviews.slice().reverse():[];
  const scorecards=Array.isArray(learning.strategy_scorecards)?learning.strategy_scorecards:[];
  const daily=Array.isArray(learning.daily_reviews)?learning.daily_reviews:[];
  $("paperLearningMode").textContent=String(learning.mode||"POLICY ADAPTATION").replaceAll("_"," ");
  $("paperDailyReview").textContent=daily[0]?`${daily[0].date} · ${daily[0].wins||0}W/${daily[0].losses||0}L · ${formatCurrency(daily[0].net_pnl)}`:"WAITING FOR CLOSED TRADES";
  const reviewHost=$("paperTradeReviews");reviewHost.replaceChildren();
  if(!reviews.length)reviewHost.appendChild(emptyPaperRow("No closed trade has been reviewed yet. Future entries record strategy, patterns, RR, stop and target automatically."));
  reviews.slice(0,8).forEach(review=>{
    const row=document.createElement("div");row.className="learning-row";
    const title=document.createElement("b");title.className=review.outcome==="WIN"?"positive":review.outcome==="LOSS"?"negative":"";title.textContent=`${review.symbol} · ${review.outcome} · R ${review.r_multiple??"—"}`;
    const flags=document.createElement("span");flags.textContent=(review.review_flags||[]).map(item=>String(item).replaceAll("_"," ")).join(" · ")||"PROCESS CHECKS PASSED";
    const lesson=document.createElement("small");lesson.textContent=review.lesson||"Review recorded.";
    row.append(title,flags,lesson);reviewHost.appendChild(row);
  });
  const scoreHost=$("paperScorecards");scoreHost.replaceChildren();
  if(!scorecards.length)scoreHost.appendChild(emptyPaperRow("Strategy performance appears after reviewed paper trades."));
  scorecards.forEach(card=>{
    const row=document.createElement("div");row.className=`learning-row ${card.status==="COOLING_OFF"?"cooling":""}`;
    const title=document.createElement("b");title.textContent=String(card.strategy||"UNCLASSIFIED").replaceAll("_"," ");
    const stats=document.createElement("span");stats.textContent=`${card.trades||0} TRADES · ${card.win_rate||0}% WIN · P&L ${formatCurrency(card.net_pnl)} · AVG R ${Number(card.average_r||0).toFixed(2)}`;
    const policy=document.createElement("small");policy.textContent=card.policy?.reason||card.status||"ELIGIBLE";
    row.append(title,stats,policy);scoreHost.appendChild(row);
  });
  renderAutonomy(paper);
  processPaperAlerts(paper);
}

async function paperRequest(path,body={}){
  const response=await apiFetch(path,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
  const payload=await responseJson(response,"Paper Desk request failed.");
  renderPaper(payload.state||payload);
  return payload;
}

async function refreshPaper(){
  try{
    const response=await apiFetch("/api/paper");
    renderPaper(await responseJson(response,"Unable to load Paper Desk."));
  }catch(error){$("paperNotice").textContent=error.message||"Paper Desk is unavailable."}
}

async function closePaperPosition(symbol){
  if(!window.confirm(`Close the synthetic ${symbol} paper position?`))return;
  try{await paperRequest("/api/paper/close",{symbol})}catch(error){$("paperNotice").textContent=error.message}
}

function renderControlPlane(control){
  if(!control)return;
  systemLoaded=true;
  const summary=control.summary||{};
  const runtime=control.runtime||{};
  $("systemAgentReady").textContent=`${summary.agents_ready??0}/${summary.agents_total??0}`;
  $("systemAgentDetail").textContent=(summary.agents_degraded||0)?`${summary.agents_degraded} require review`:"All registered entrypoints found";
  $("systemToolCount").textContent=summary.tools_total??0;
  $("systemToolDetail").textContent=Object.entries(summary.tool_policies||{}).map(([key,value])=>`${value} ${titleCase(key)}`).join(" · ")||"No tools registered";
  $("systemPosture").textContent=control.status||"UNKNOWN";
  $("systemNetwork").textContent=`${runtime.loopback_only?"LOOPBACK":"NETWORK"} · ${runtime.authenticated_api?"AUTHENTICATED":"UNAUTHENTICATED"}`;
  $("systemExecution").textContent=runtime.live_trading||"LOCKED";
  const generated=new Date(control.generated_at||"");
  $("systemGenerated").textContent=Number.isNaN(generated.getTime())?"CURRENT":generated.toLocaleTimeString("en-IN",{timeZone:"Asia/Kolkata",hour:"2-digit",minute:"2-digit",second:"2-digit"});
  $("agentCatalogState").textContent=control.status||"UNKNOWN";

  const boundary=$("runtimeBoundary");boundary.replaceChildren();
  [
    ["ARCHITECTURE",runtime.architecture],
    ["OPERATOR MODEL",runtime.operator_model],
    ["API HOST",runtime.workstation_host],
    ["MARKET DATA",`${runtime.market_data_provider||"UNAVAILABLE"} · ${runtime.market_data_connected?"CONNECTED":"NOT CONNECTED"}`],
    ["MODEL ACTIONS",runtime.model_actions],
    ["TELEMETRY",runtime.telemetry_available?"AVAILABLE":"OPTIONAL / UNAVAILABLE"]
  ].forEach(([label,value])=>{
    const row=document.createElement("div");row.className="boundary-row";
    const key=document.createElement("span");key.textContent=label;
    const detail=document.createElement("b");detail.textContent=titleCase(value||"UNKNOWN");
    row.append(key,detail);boundary.appendChild(row);
  });

  const guardrails=$("systemGuardrails");guardrails.replaceChildren();
  (control.guardrails||[]).forEach((text,index)=>{
    const row=document.createElement("div");row.className="guardrail-row";
    const number=document.createElement("b");number.textContent=String(index+1).padStart(2,"0");
    const detail=document.createElement("span");detail.textContent=text;
    row.append(number,detail);guardrails.appendChild(row);
  });

  const catalog=$("agentCatalog");catalog.replaceChildren();
  (control.agents||[]).forEach(agent=>{
    const card=document.createElement("article");card.className=`agent-manifest ${String(agent.status||"").toLowerCase()}`;
    const head=document.createElement("div");head.className="agent-manifest-head";
    const title=document.createElement("b");title.textContent=agent.label||agent.name;
    const status=document.createElement("span");status.textContent=agent.status;
    head.append(title,status);
    const authority=document.createElement("div");authority.className="agent-authority";authority.textContent=`${titleCase(agent.authority)} · ${titleCase(agent.isolation)}`;
    const diagnostic=document.createElement("p");diagnostic.textContent=agent.diagnostic;
    const capabilities=document.createElement("div");capabilities.className="agent-capabilities";
    (agent.capabilities||[]).forEach(capability=>{const chip=document.createElement("i");chip.textContent=capability;capabilities.appendChild(chip)});
    card.append(head,authority,diagnostic,capabilities);catalog.appendChild(card);
  });

  const toolHost=$("toolAuthority");toolHost.replaceChildren();
  (control.tools||[]).forEach(tool=>{
    const row=document.createElement("div");row.className="tool-row";
    const identity=document.createElement("div");
    const name=document.createElement("b");name.textContent=tool.name;
    const description=document.createElement("span");description.textContent=tool.description;
    identity.append(name,description);
    const policy=document.createElement("div");policy.className=`tool-policy ${String(tool.risk||"").toLowerCase()}`;
    const risk=document.createElement("b");risk.textContent=tool.risk;
    const state=document.createElement("span");state.textContent=titleCase(tool.policy);
    policy.append(risk,state);row.append(identity,policy);toolHost.appendChild(row);
  });

  const traceHost=$("systemTrace");traceHost.replaceChildren();
  if(!(control.trace||[]).length)traceHost.textContent="No audit metadata has been recorded yet.";
  (control.trace||[]).slice(0,30).forEach(event=>{
    const row=document.createElement("div");row.className="trace-row";
    const status=document.createElement("i");status.className=String(event.status||"").toLowerCase();
    const content=document.createElement("div");
    const name=document.createElement("b");name.textContent=`${event.category} · ${event.name}`;
    const detail=document.createElement("span");detail.textContent=`${event.status} · ${displaySeenDate(event.timestamp)}`;
    content.append(name,detail);row.append(status,content);traceHost.appendChild(row);
  });

  const mission=control.missions||{};
  const missionHost=$("systemMission");missionHost.replaceChildren();
  [
    ["MISSIONS",mission.mission_count??0],
    ["ACTIVE",mission.active_title||"NONE"],
    ["STATUS",titleCase(mission.active_status||"READY")],
    ["TASKS",mission.task_count??0],
    ["APPROVAL LOCKS",mission.approval_locks??0],
    ["CRITIC",titleCase(mission.critic_verdict||"WAITING")]
  ].forEach(([label,value])=>{
    const card=document.createElement("div");
    const key=document.createElement("span");key.textContent=label;
    const detail=document.createElement("b");detail.textContent=value;
    card.append(key,detail);missionHost.appendChild(card);
  });
}

async function refreshControlPlane(){
  try{
    const response=await apiFetch("/api/control-plane");
    if(!response.ok)return;
    renderControlPlane(await response.json());
  }catch{}
}

function renderTradingIntelligence(payload){
  if(!payload?.success){
    $("quantRegime").textContent="DATA UNAVAILABLE";
    $("quantExplanation").textContent=payload?.message||"FYERS timeframe data is unavailable.";
    $("quantSetup").textContent="NO SETUP";
    $("quantConfidence").textContent="—";
    $("quantStrategy").textContent="NO EDGE";
    $("quantPatterns").textContent="NO CONFIRMATION";
    $("quantTradePlan").textContent="— / — / —";
    $("quantRiskReward").textContent="—";
    $("quantTimeframes").textContent=(payload?.errors||[]).map(item=>`${item.timeframe}: ${item.error}`).join(" · ")||"No timeframe evidence.";
    return;
  }
  $("quantRegime").textContent=`${payload.symbol} · ${payload.regime}`;
  $("quantExplanation").textContent=payload.explanation;
  $("quantSetup").textContent=payload.setup.replaceAll("_"," ");
  $("quantConfidence").textContent=`${payload.confidence}%`;
  $("quantBar").style.width=`${Math.max(0,Math.min(Number(payload.momentum)||0,100))}%`;
  $("quantSupport").textContent=formatMarketNumber(payload.support);
  $("quantResistance").textContent=formatMarketNumber(payload.resistance);
  $("quantAtr").textContent=`ATR ${formatMarketNumber(payload.atr14)} · Momentum ${payload.momentum}/100`;
  $("quantMode").textContent=payload.mode.replaceAll("_"," ");
  $("quantStrategy").textContent=`${String(payload.strategy||"NO EDGE").replaceAll("_"," ")} · SCORE ${Number(payload.strategy_score||0).toFixed(1)}`;
  $("quantPatterns").textContent=(payload.chart_patterns||[]).slice(0,4).map(item=>String(item).replaceAll("_"," ")).join(" · ")||"NO CONFIRMED PATTERN";
  $("quantTradePlan").textContent=`${formatMarketNumber(payload.entry)} / ${formatMarketNumber(payload.stop_loss)} / ${formatMarketNumber(payload.take_profit)}`;
  $("quantRiskReward").textContent=Number(payload.risk_reward)>0?`${Number(payload.risk_reward).toFixed(2)} R · ${payload.decision_gate||"WAIT"}`:"NO VALIDATED RR";
  $("quantRisk").textContent=[...(payload.decision_reasons||[]),payload.risk_notice].filter(Boolean).join(" · ");
  const host=$("quantTimeframes");
  host.replaceChildren();
  payload.timeframes.forEach(item=>{
    const card=document.createElement("div");card.className="tf-card";
    const head=document.createElement("div");head.className="tf-head";
    const tf=document.createElement("b");tf.textContent=item.timeframe;
    const regime=document.createElement("span");regime.textContent=item.regime.replaceAll("_"," ");
    head.append(tf,regime);
    const values=document.createElement("div");values.className="tf-values";
    [["PRICE",formatMarketNumber(item.price)],["RSI 14",item.rsi14],["EMA 20",formatMarketNumber(item.ema20)],["EMA 50",formatMarketNumber(item.ema50)],["ATR %",`${item.atr_percent}%`],["VOLUME",`${item.volume_ratio}×`],["STRATEGY",String(item.strategy||"NO EDGE").replaceAll("_"," ")],["PATTERN",(item.chart_patterns||[]).slice(0,1).join(" ").replaceAll("_"," ")||"NONE"]].forEach(([label,value])=>{
      const span=document.createElement("span");span.textContent=`${label} `;
      const strong=document.createElement("b");strong.textContent=value;span.appendChild(strong);values.appendChild(span);
    });
    card.append(head,values);host.appendChild(card);
  });
}

async function refreshTradingIntelligence(symbol=currentQuantSymbol){
  currentQuantSymbol=String(symbol||"BANKNIFTY").toUpperCase();
  document.querySelectorAll("[data-quant-symbol]").forEach(button=>button.classList.toggle("active",button.dataset.quantSymbol===currentQuantSymbol));
  $("quantRegime").textContent=`${currentQuantSymbol} · LOADING`;
  $("quantExplanation").textContent="Reading 5m, 15m, and 1h FYERS broker candles…";
  try{
    const response=await apiFetch(`/api/trading/intelligence?symbol=${encodeURIComponent(currentQuantSymbol)}`);
    const payload=await response.json();
    renderTradingIntelligence(payload);
  }catch(error){renderTradingIntelligence({success:false,message:"Trading intelligence service is unavailable."})}
}

function renderCompany(company){
  if(!company)return;
  companyLoaded=true;
  $("companyAgentCount").textContent=company.agent_count||0;
  $("agentMetric").textContent=(state.agents?.length)||company.agent_count||0;
  const departmentHost=$("departmentMesh");
  departmentHost.replaceChildren();
  (company.agents||[]).forEach(agent=>{
    const card=document.createElement("div");card.className="department-card";
    const name=document.createElement("b");name.textContent=agent.name;
    const mission=document.createElement("span");mission.textContent=agent.mission;
    card.append(name,mission);departmentHost.appendChild(card);
  });
  const plan=company.latest_plan;
  if(!plan)return;
  $("companyTitle").textContent=plan.company_name;
  $("companyMission").textContent=plan.venture_thesis?.mission||plan.idea;
  $("companyTaskCount").textContent=plan.tasks?.length||0;
  $("companyGateCount").textContent=(plan.tasks||[]).filter(task=>task.approval_required).length;
  $("companyArtifactCount").textContent=plan.artifacts?.length||0;
  const roadmap=$("companyRoadmap");roadmap.replaceChildren();
  (plan.roadmap||[]).forEach(phase=>{
    const card=document.createElement("div");card.className="roadmap-phase";
    const title=document.createElement("b");title.textContent=phase.horizon;
    const goal=document.createElement("p");goal.textContent=phase.goal;
    const tasks=document.createElement("span");tasks.textContent=(phase.tasks||[]).join(" · ");
    card.append(title,goal,tasks);roadmap.appendChild(card);
  });
  const taskHost=$("companyTasks");taskHost.replaceChildren();
  (plan.tasks||[]).forEach(task=>{
    const card=document.createElement("div");card.className=`mission-task${task.approval_required?" locked":""}`;
    const head=document.createElement("div");head.className="mission-task-head";
    const title=document.createElement("b");title.textContent=`${task.id} · ${task.title}`;
    const status=document.createElement("span");status.textContent=task.approval_required?"LOCKED · APPROVAL":"PLANNED";
    head.append(title,status);
    const body=document.createElement("p");body.textContent=`${task.department} — ${task.deliverable}`;
    card.append(head,body);taskHost.appendChild(card);
  });
}

async function refreshCompany(){
  try{
    const response=await apiFetch("/api/company");
    if(!response.ok)return;
    renderCompany(await response.json());
  }catch{}
}

function titleCase(value){
  return String(value||"").replaceAll("_"," ").replace(/\b\w/g,character=>character.toUpperCase()).replace("Data Ai","Data & AI");
}

function renderMission(missionControl){
  if(!missionControl)return;
  missionLoaded=true;
  const mission=missionControl.latest_mission;
  if(!mission)return;
  $("missionTitle").textContent=mission.title||"Active mission";
  $("missionObjective").textContent=mission.objective||"No objective supplied.";
  $("missionStatus").textContent=titleCase(mission.status);
  $("missionConfidence").textContent=`${mission.critic?.confidence??"—"}%`;
  $("missionAgentCount").textContent=(mission.selected_agents||[]).length;
  $("missionTaskCount").textContent=(mission.tasks||[]).length;
  $("missionArtifactCount").textContent=(mission.artifacts||[]).length;
  $("missionLockCount").textContent=(mission.approval_locks||[]).length;

  const outputByAgent=new Map((mission.specialist_outputs||[]).map(item=>[item.agent,item]));
  const specialistHost=$("missionSpecialists");specialistHost.replaceChildren();
  (mission.selected_agents||[]).forEach(agentName=>{
    const output=outputByAgent.get(agentName)||{};
    const card=document.createElement("div");card.className=`specialist-node${output.success===false?" failed":""}`;
    const name=document.createElement("b");name.textContent=titleCase(agentName);
    const status=document.createElement("span");status.textContent=output.success===false?"FAILED SAFE":"COMPLETE";
    const detail=document.createElement("small");detail.textContent=String(output.message||"Contribution recorded.").slice(0,240);
    card.append(name,status,detail);specialistHost.appendChild(card);
  });

  const critic=mission.critic||{};
  $("missionCritic").textContent=titleCase(critic.verdict||"Waiting");
  const checksHost=$("missionChecks");checksHost.replaceChildren();
  Object.entries(critic.checks||{}).forEach(([check,passed])=>{
    const row=document.createElement("div");row.className=`critic-check${passed?"":" review"}`;
    const label=document.createElement("span");label.textContent=titleCase(check);
    const result=document.createElement("b");result.textContent=passed?"PASS":"REVIEW";
    row.append(label,result);checksHost.appendChild(row);
  });

  const taskHost=$("missionTasks");taskHost.replaceChildren();
  (mission.tasks||[]).forEach(task=>{
    const status=String(task.status||"");
    const className=task.approval_required?" locked":status.includes("FAILED")?" failed":status.includes("REVIEW")?" review":"";
    const card=document.createElement("div");card.className=`graph-node${className}`;
    const head=document.createElement("div");head.className="graph-head";
    const title=document.createElement("b");title.textContent=`${task.id} · ${task.title}`;
    const stateLabel=document.createElement("span");stateLabel.textContent=titleCase(status);
    head.append(title,stateLabel);
    const detail=document.createElement("p");detail.textContent=`${task.owner} — ${task.detail}`;
    const dependencies=document.createElement("div");dependencies.className="graph-deps";
    dependencies.textContent=`DEPENDS ON · ${(task.depends_on||[]).join(" + ")||"ROOT"}`;
    card.append(head,detail,dependencies);taskHost.appendChild(card);
  });

  const artifactHost=$("missionArtifacts");artifactHost.replaceChildren();
  (mission.artifacts||[]).forEach(artifact=>{
    const row=document.createElement("div");row.className="artifact-row";
    const name=document.createElement("b");name.textContent=artifact.name;
    const path=document.createElement("span");path.textContent=artifact.path;
    row.append(name,path);artifactHost.appendChild(row);
  });

  const lockHost=$("missionLocks");lockHost.replaceChildren();
  (mission.approval_locks||[]).forEach(lock=>{
    const row=document.createElement("div");row.className="lock-row";
    const action=document.createElement("b");action.textContent=lock.action;
    const reason=document.createElement("span");reason.textContent=lock.reason;
    row.append(action,reason);lockHost.appendChild(row);
  });
}

async function refreshMission(){
  try{
    const response=await apiFetch("/api/missions");
    if(!response.ok)return;
    renderMission(await response.json());
  }catch{}
}

function renderWeb(webState){
  if(!webState)return;
  webLoaded=true;
  const result=webState.latest||webState;
  if(!result?.query)return;
  $("webQuery").textContent=result.query;
  $("webSourceCount").textContent=`${(result.sources||[]).length} SOURCES`;
  $("webProvider").textContent=(result.providers||[]).join(" + ")||"NO PROVIDER";
  $("webNotice").textContent=result.notice||"Research completed with bounded public sources.";
  const answerPanel=$("webAnswerPanel");
  const answer=$("webAnswer");
  if(answerPanel&&answer){
    answerPanel.hidden=!result.answer;
    answer.textContent=result.answer||"";
  }

  const sourceHost=$("webSources");sourceHost.replaceChildren();
  if(!(result.sources||[]).length){
    sourceHost.textContent="No public source could be retrieved for this request.";
  }
  (result.sources||[]).forEach((source,index)=>{
    const row=document.createElement("article");row.className="web-source";
    const number=document.createElement("div");number.className="web-source-number";number.textContent=String(index+1).padStart(2,"0");
    const content=document.createElement("div");
    const link=document.createElement("a");link.href=source.url;link.target="_blank";link.rel="noopener noreferrer";link.textContent=source.title||source.url;
    const excerpt=document.createElement("p");excerpt.textContent=source.excerpt||"Source discovered; no readable excerpt was returned.";
    const meta=document.createElement("div");meta.className="web-source-meta";
    const provider=document.createElement("b");provider.textContent=source.provider||"PUBLIC WEB";
    const status=document.createElement("span");status.textContent=titleCase(source.read_status||"SOURCE");
    const time=document.createElement("span");time.textContent=displaySeenDate(source.retrieved_at||"");
    meta.append(provider,status,time);content.append(link,excerpt,meta);row.append(number,content);sourceHost.appendChild(row);
  });

  const diagnostics=$("webDiagnostics");diagnostics.replaceChildren();
  [
    ["MODE",titleCase(result.mode||"UNKNOWN"),false],
    ["AUTO ROUTE",result.mode==="OFFICIAL_RANKING"?"OFFICIAL RANKING → NIRF":"MASTER → WEB INTELLIGENCE",false],
    ["SEARCH COVERAGE",result.broad_search_configured?"BRAVE SEARCH":"FIRECRAWL KEYLESS",false],
    ["PROVIDERS",(result.providers||[]).join(" · ")||"NONE",false],
    ...((result.errors||[]).map(error=>["ACCESS LIMIT",error,true]))
  ].forEach(([label,value,isError])=>{
    const row=document.createElement("div");row.className=`web-diagnostic-row${isError?" error":""}`;
    const heading=document.createElement("b");heading.textContent=label;
    const detail=document.createElement("span");detail.textContent=value;
    row.append(heading,detail);diagnostics.appendChild(row);
  });
}

async function refreshWeb(){
  try{
    const response=await apiFetch("/api/web");
    if(!response.ok)return;
    renderWeb(await response.json());
  }catch{}
}

function displaySeenDate(value){
  const raw=String(value||"");
  const match=raw.match(/^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})/);
  const date=match
    ?new Date(`${match[1]}-${match[2]}-${match[3]}T${match[4]}:${match[5]}:00Z`)
    :new Date(raw);
  if(Number.isNaN(date.getTime()))return raw;
  return date.toLocaleString("en-IN",{timeZone:"Asia/Kolkata",day:"2-digit",month:"short",hour:"2-digit",minute:"2-digit"});
}

function renderNews(payload){
  const host=$("headlines");
  host.replaceChildren();
  $("newsQuery").textContent=`QUERY · ${payload.query||currentNewsQuery} · FRESH ${String(payload.timespan||"3d").toUpperCase()}`;
  if(!payload.success||!payload.articles?.length){
    const empty=document.createElement("div");
    empty.className="news-empty";
    empty.textContent=payload.message||"No matching headlines were found.";
    host.appendChild(empty);
    return;
  }
  payload.articles.forEach((article,index)=>{
    const row=document.createElement("article");
    row.className="news-item";
    const number=document.createElement("span");
    number.className="news-number";
    number.textContent=String(index+1).padStart(2,"0");
    const content=document.createElement("div");
    const link=document.createElement("a");
    link.href=article.url;
    link.target="_blank";
    link.rel="noopener noreferrer";
    link.textContent=article.title;
    const meta=document.createElement("div");
    meta.className="news-meta";
    meta.textContent=[article.domain,article.source_country,displaySeenDate(article.seen_date)].filter(Boolean).join(" · ");
    content.append(link,meta);
    const read=document.createElement("button");
    read.className="news-read";
    read.textContent="READ";
    read.onclick=()=>requestNewsBriefing(index+1,1);
    row.append(number,content,read);
    host.appendChild(row);
  });
  const filtered=Number(payload.stale_filtered)||0;
  $("impactText").textContent=`Showing ${payload.count} source headlines for “${payload.query}” inside the ${payload.timespan||"3d"} freshness window${filtered?`; ${filtered} stale result${filtered===1?" was":"s were"} removed`:""}. Treat headline relevance as research context; verify the linked report before drawing a market or trading conclusion.`;
}

async function requestNewsBriefing(index=null,limit=5){
  try{
    const response=await apiFetch("/api/news/briefing",{
      method:"POST",
      headers:{"Content-Type":"application/json"},
      body:JSON.stringify({index,limit,chat_context:"news"})
    });
    const payload=await responseJson(response,"News briefing request failed.");
    if(payload.messages)payload.messages.forEach(message=>addMessage("news",message.role,message.text,message.id));
    if(payload.speech)speak(payload.speech);
    return payload;
  }catch(error){
    addMessage("news","assistant","The spoken news briefing is temporarily unavailable.");
    return null;
  }
}

async function refreshNews(query=currentNewsQuery,limit=10,autoBrief=false,timespan="3d"){
  currentNewsQuery=String(query||currentNewsQuery).trim()||"India markets NIFTY Sensex";
  $("headlines").textContent=`Loading current source headlines for “${currentNewsQuery}”…`;
  $("newsQuery").textContent=`QUERY · ${currentNewsQuery}`;
  try{
    const params=new URLSearchParams({q:currentNewsQuery,limit:String(limit),timespan:String(timespan||"3d")});
    const response=await apiFetch(`/api/news?${params}`);
    const payload=await response.json();
    if(!response.ok)throw new Error(payload.error||"News request failed.");
    renderNews(payload);
    newsLoaded=true;
    if(autoBrief&&payload.success)await requestNewsBriefing(null,Math.min(limit,10));
  }catch(error){
    renderNews({success:false,query:currentNewsQuery,message:error.message||"Market-news retrieval is unavailable.",articles:[]});
  }
}

async function agent(text,context=activeContext,metadata={}){
  text=(text||"").trim();
  if(!text||sendingContexts.has(context))return;
  if(/\b(?:ping|notify|alert|monitor|watch)\b|\bwhen(?:ever)?\b.{0,50}\b(?:trade|setup|signal|entry)\b/i.test(text))enablePaperAlerts();
  sendingContexts.add(context);
  setOmniStatus("MASTER IS ROUTING",context.toUpperCase());
  document.body.classList.add("command-active");
  setVoiceVisual("processing","PROCESSING COMMAND");
  try{
    const requestBody={text,context};
    if(Number.isFinite(Number(metadata.speechConfidence)))requestBody.speech_confidence=Number(metadata.speechConfidence);
    if(context==="quant")requestBody.active_symbol=currentQuantSymbol;
    const r=await apiFetch("/api/agent",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(requestBody)});
    const d=await responseJson(r,"JARVIS command request failed.");
    const routedAgent={open_news:"NEWS AGENT",open_system:"SYSTEM CORE",open_quant:"QUANT AGENT",open_paper:"PAPER AGENT",open_company:"COMPANY OS",open_mission:"MISSION CONTROL",open_web:"WEB INTELLIGENCE",set_chart:"CHART AGENT",set_layout:"CHART AGENT"}[d.action]||"MASTER JARVIS";
    setOmniStatus(`AUTO-ROUTED · ${routedAgent}`,"DONE");
    const responseContext=d.context||context;
    if(d.messages)d.messages.forEach(m=>addMessage(responseContext,m.role,m.text,m.id));
    if(d.routed_context&&d.routed_messages)d.routed_messages.forEach(m=>addMessage(d.routed_context,m.role,m.text,m.id));
    if(d.state){
      state=normalizeState(d.state);
      mountCharts();
    }
    if(d.action==="open_news"){
      switchPage("news");
      refreshNews(d.query||currentNewsQuery,d.limit||10,Boolean(d.auto_brief),d.timespan||"3d");
    }else if(d.action==="open_system"){
      if(d.control_plane)renderControlPlane(d.control_plane);
      switchPage("system");
    }else if(d.action==="open_quant"){
      currentQuantSymbol=d.symbol||currentQuantSymbol;
      if(d.trading_intelligence)renderTradingIntelligence(d.trading_intelligence);
      if(d.paper)renderPaper(d.paper);
      if(d.notification_requested)enablePaperAlerts();
      switchPage("quant");
    }else if(d.action==="open_paper"){
      if(d.paper)renderPaper(d.paper);
      switchPage("paper");
    }else if(d.action==="open_company"){
      if(d.company)renderCompany(d.company);
      switchPage("company");
    }else if(d.action==="open_mission"){
      if(d.mission_control)renderMission(d.mission_control);
      switchPage("mission");
    }else if(d.action==="open_web"){
      if(d.web_intelligence)renderWeb(d.web_intelligence);
      else renderWeb(d);
      switchPage("web");
    }else if(d.action==="set_chart"||d.action==="set_layout"){
      switchPage("charts");
    }
    if(d.speech){
      speak(d.speech);
    }
  }catch(e){
    setOmniStatus("MASTER AUTO-ROUTE","CHECK DIAGNOSTICS");
    addMessage(context,"assistant",e.message||"The JARVIS command service is unavailable.");
  }finally{
    sendingContexts.delete(context);
    setTimeout(()=>document.body.classList.remove("command-active"),500);
    if(!speechInProgress){setVoiceVisual(voiceArmed?"armed":"ready",voiceArmed?"VOICE ARMED":"VOICE READY");scheduleVoiceRestart()}
  }
}

function setVoiceVisual(mode,label){
  document.body.classList.toggle("voice-listening",mode==="listening");
  document.body.classList.toggle("voice-speaking",mode==="speaking");
  const stateLabel=$("voiceState");
  const coreLabel=$("coreState");
  if(stateLabel)stateLabel.textContent=label;
  if(coreLabel)coreLabel.textContent=label;
}

function setVoiceArmed(value,context=activeContext,masterMode=false){
  voiceArmed=Boolean(value);
  voiceMasterMode=voiceArmed&&Boolean(masterMode);
  recognitionContext=context;
  document.body.classList.toggle("voice-armed",voiceArmed);
  document.querySelectorAll('[data-chat-action="listen"]').forEach(button=>button.textContent=voiceArmed&&button.closest(".conversation")?.dataset.chatContext===recognitionContext?"LISTENING":"LISTEN");
  const omniVoice=$("omniVoice");
  if(omniVoice){omniVoice.classList.toggle("active",voiceArmed&&voiceMasterMode);omniVoice.textContent=voiceArmed&&voiceMasterMode?"●":"J"}
  if(!recognition)return;
  if(!voiceArmed){
    pendingVoiceCommand=null;
    clearTimeout(voiceRestartTimer);
    try{recognition.stop()}catch{}
    setVoiceVisual("ready","VOICE READY");
  }else if(!listening&&!speechInProgress){
    setVoiceVisual("armed",`MIC ARMED · ${recognitionContext.toUpperCase()}`);
    try{recognition.start()}catch{}
  }
}

function scheduleVoiceRestart(){
  clearTimeout(voiceRestartTimer);
  if(!voiceArmed||speechInProgress||listening||!recognition||sendingContexts.size)return;
  voiceRestartTimer=setTimeout(()=>{if(voiceArmed&&!listening&&!speechInProgress&&!sendingContexts.size){try{recognition.start()}catch{}}},450);
}

function setupVoice(){
  const SR=window.SpeechRecognition||window.webkitSpeechRecognition;
  if(!SR){setVoiceVisual("ready","VOICE TEXT MODE");return}
  recognition=new SR();
  recognition.lang="en-IN";
  recognition.continuous=false;
  recognition.interimResults=true;
  recognition.onstart=()=>{voiceErrorMessage="";listening=true;setVoiceVisual("listening",`LISTENING · ${recognitionContext.toUpperCase()}`)};
  recognition.onend=()=>{
    listening=false;
    if(voiceErrorMessage){setVoiceVisual("error",voiceErrorMessage);voiceErrorMessage="";return}
    if(pendingVoiceCommand?.text){
      const pending=pendingVoiceCommand;pendingVoiceCommand=null;
      setVoiceVisual("processing","PROCESSING VOICE COMMAND");
      agent(pending.text,pending.context,{speechConfidence:pending.confidence});
      return;
    }
    setVoiceVisual(voiceArmed?"armed":"ready",voiceArmed?"LISTENING RESTART":"VOICE READY");scheduleVoiceRestart();
  };
  recognition.onerror=event=>{
    const messages={"not-allowed":"MICROPHONE PERMISSION DENIED","service-not-allowed":"VOICE SERVICE BLOCKED","audio-capture":"NO MICROPHONE FOUND","network":"VOICE NETWORK ERROR","no-speech":"NO SPEECH HEARD"};
    voiceErrorMessage=messages[event.error]||`VOICE ERROR · ${String(event.error||"UNKNOWN").toUpperCase()}`;
    setVoiceArmed(false);
    setVoiceVisual("error",voiceErrorMessage);
  };
  recognition.onresult=e=>{
    let finalText="",interimText="";
    let finalConfidence=null,interimConfidence=null;
    for(let i=e.resultIndex;i<e.results.length;i++){
      if(e.results[i].isFinal){finalText+=e.results[i][0].transcript+" ";finalConfidence=e.results[i][0].confidence}
      else{interimText+=e.results[i][0].transcript+" ";interimConfidence=e.results[i][0].confidence}
    }
    const input=voiceInput(recognitionContext);
    if(interimText.trim()){
      const interimCommand=interimText.trim().replace(/^jarvis[\s,:-]*/i,"").trim();
      if(input)input.value=interimCommand;
      if(interimCommand)pendingVoiceCommand={text:interimCommand,context:recognitionContext,confidence:interimConfidence};
    }
    finalText=finalText.trim();
    if(!finalText)return;
    const cmd=finalText.replace(/^jarvis[\s,:-]*/i,"").trim();
    if(input)input.value=cmd;
    pendingVoiceCommand=null;
    if(cmd)agent(cmd,recognitionContext,{speechConfidence:finalConfidence});
  };
}

document.querySelectorAll(".conversation[data-chat-context]").forEach(shell=>{
  const context=shell.dataset.chatContext;
  const input=shell.querySelector("input");
  const send=shell.querySelector('[data-chat-action="send"]');
  const listenButton=shell.querySelector('[data-chat-action="listen"]');
  const stopButton=shell.querySelector('[data-chat-action="stop"]');
  send.onclick=()=>{const value=input.value;input.value="";agent(value,context)};
  input.addEventListener("keydown",event=>{if(event.key==="Enter")send.click()});
  listenButton.onclick=async()=>{
    if(!recognition){setVoiceVisual("error","VOICE NOT SUPPORTED");return}
    if(voiceArmed){setVoiceArmed(false,context);return}
    try{
      if(navigator.mediaDevices?.getUserMedia){
        const stream=await navigator.mediaDevices.getUserMedia({audio:true});
        stream.getTracks().forEach(track=>track.stop());
      }
      setVoiceArmed(true,context,false);
    }catch{setVoiceVisual("error","MICROPHONE PERMISSION REQUIRED")}
  };
  stopButton.onclick=()=>{window.speechSynthesis?.cancel();speechInProgress=false;setVoiceArmed(false,context)};
});

$("omniSend").onclick=()=>{const input=$("omniInput");const value=input.value;input.value="";agent(value,"master")};
$("omniInput").addEventListener("keydown",event=>{if(event.key==="Enter")$("omniSend").click()});
$("omniVoice").onclick=async()=>{
  if(!recognition){setVoiceVisual("error","VOICE NOT SUPPORTED");return}
  if(voiceArmed&&voiceMasterMode){setVoiceArmed(false,"master");return}
  if(voiceArmed)setVoiceArmed(false,recognitionContext);
  try{
    if(navigator.mediaDevices?.getUserMedia){
      const stream=await navigator.mediaDevices.getUserMedia({audio:true});
      stream.getTracks().forEach(track=>track.stop());
    }
    setVoiceArmed(true,"master",true);
    setOmniStatus("CONTINUOUS MASTER VOICE","LISTENING");
  }catch{setVoiceVisual("error","MICROPHONE PERMISSION REQUIRED")}
};

document.querySelectorAll("[data-page]").forEach(b=>{
  b.onclick=()=>{
    switchPage(b.dataset.page);
    if(b.dataset.page==="news"&&!newsLoaded)refreshNews();
  }
});

document.querySelectorAll("[data-quant-symbol]").forEach(button=>{
  button.onclick=()=>refreshTradingIntelligence(button.dataset.quantSymbol);
});

document.querySelectorAll("[data-layout]").forEach(b=>{
  b.onclick=()=>{
    state.layout=parseInt(b.dataset.layout,10);
    mountCharts();
  }
});

$("newsRefresh").onclick=()=>refreshNews();
$("newsRead").onclick=()=>requestNewsBriefing(null,5);
$("systemRefresh").onclick=()=>refreshControlPlane();
$("paperRefresh").onclick=()=>refreshPaper();
$("paperArm").onclick=async()=>{try{await paperRequest("/api/paper/control",{enabled:true})}catch(error){$("paperNotice").textContent=error.message}};
$("paperPause").onclick=async()=>{try{await paperRequest("/api/paper/control",{enabled:false})}catch(error){$("paperNotice").textContent=error.message}};
$("paperScan").onclick=async()=>{try{await paperRequest("/api/paper/scan")}catch(error){$("paperNotice").textContent=error.message}};
$("paperFlatten").onclick=async()=>{if(!window.confirm("Close every synthetic paper position? No live order will be sent."))return;try{await paperRequest("/api/paper/close",{all:true})}catch(error){$("paperNotice").textContent=error.message}};

apiFetch("/api/state").then(r=>responseJson(r,"Unable to load dashboard state.")).then(s=>{
  state=normalizeState(s);
  mountCharts();
  renderMarket(s.market);
  renderCompany(s.company);
  renderMission(s.mission_control);
  renderWeb(s.web_intelligence);
  renderControlPlane(s.control_plane);
  renderPaper(s.paper);
  Object.entries(s.conversations||{}).forEach(([context,messages])=>{
    messages.forEach(message=>addMessage(context,message.role,message.text,message.id));
  });
}).catch(error=>{
  state=normalizeState(state);
  mountCharts();
  addMessage("master","assistant",error.message||"Unable to connect to the JARVIS service. Relaunch the dashboard.");
});

setInterval(refreshMarket,2500);
setInterval(()=>{
  if(($("page-paper").classList.contains("active")||$("page-command").classList.contains("active"))&&document.visibilityState==="visible")refreshPaper();
},5000);
setInterval(()=>{
  if($("page-system").classList.contains("active")&&document.visibilityState==="visible")refreshControlPlane();
},15000);
setInterval(()=>{
  if($("page-charts").classList.contains("active")&&document.visibilityState==="visible")mountCharts();
},60000);

setupVoice();

document.addEventListener("visibilitychange",()=>{if(document.visibilityState==="visible")mountCharts()});
