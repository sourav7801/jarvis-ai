/* JARVIS V19 — Workspace Architecture / Cockpit */
(()=>{"use strict";
const $=id=>document.getElementById(id);
const KEY="jarvis.v19.workspace.state";
const MODES={
 INTRADAY:{title:"INTRADAY COMMAND",sub:"Session execution · VWAP · OR · momentum · live risk",focus:["Signals","Market Structure","Risk","Execution"],risk:"SESSION"},
 SWING:{title:"SWING RESEARCH",sub:"Multi-session setups · trend · catalysts · position geometry",focus:["Setups","Trend","Catalysts","Risk"],risk:"POSITION"},
 INVESTMENT:{title:"INVESTMENT DESK",sub:"Long-horizon allocation · fundamentals · valuation · portfolio risk",focus:["Portfolio","Fundamentals","Valuation","Watchlist"],risk:"PORTFOLIO"},
 OPTIONS:{title:"OPTIONS INTELLIGENCE",sub:"Chain · OI · IV · Greeks · strategy research",focus:["Chain","Greeks","OI / IV","Strategy"],risk:"DERIVATIVES"}
};
let state={workspace:"INTRADAY",focus:"Signals",provider:null,health:null,options:null,paper:null,started:Date.now()};
try{Object.assign(state,JSON.parse(localStorage.getItem(KEY)||"{}"))}catch{}
function workspace(){return String(window.JARVIS_V17_WORKSPACE_RUNTIME?.workspace||document.querySelector(".workspace-modes button.active")?.dataset.workspace||state.workspace||"INTRADAY").toUpperCase()}
function save(){try{localStorage.setItem(KEY,JSON.stringify({workspace:workspace(),focus:state.focus}))}catch{}}
function esc(v){return String(v??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]))}
function val(v,fallback="—"){return v===null||v===undefined||v===""?fallback:String(v)}
async function json(url){try{const r=await fetch(url,{cache:"no-store"});return await r.json()}catch{return null}}
function chip(label,value,cls=""){return '<div class="v19-chip '+cls+'"><small>'+label+'</small><b>'+esc(value)+'</b></div>'}
function ensure(){
 const ws=document.querySelector(".workspace"),intel=document.querySelector(".intel-panel");if(!ws||!intel)return false;
 if(!$("v19Shellbar")){const bar=document.createElement("section");bar.id="v19Shellbar";bar.className="v19-shellbar";bar.innerHTML='<div class="v19-titleblock"><div class="v19-kicker">JARVIS V19 · WORKSPACE OS</div><div class="v19-title" id="v19Title">INTRADAY COMMAND</div><div class="v19-sub" id="v19Sub"></div></div><div class="v19-statebar" id="v19Statebar"></div><div class="v19-actions"><button data-v19-action="scan">SCAN</button><button data-v19-action="reload">RELOAD</button><button data-v19-action="reset">RESET VIEW</button></div>';ws.querySelector(".workspace-modes")?.after(bar)}
 if(!$("v19Contextbar")){const bar=document.createElement("div");bar.id="v19Contextbar";bar.className="v19-contextbar";ws.querySelector(".v19-shellbar")?.after(bar)}
 if(!$("v19WorkspaceGrid")){const host=document.createElement("div");host.id="v19WorkspaceGrid";host.className="v19-workspace-grid";const grid=$("chartGrid");if(grid){grid.parentNode.insertBefore(host,grid);host.appendChild(grid)}}
 if(!$("v19Rail")){const rail=document.createElement("aside");rail.id="v19Rail";rail.className="v19-rail";intel.insertBefore(rail,intel.firstChild)}
 if(!$("v19Bottom")){const b=document.createElement("div");b.id="v19Bottom";b.className="v19-bottom";b.innerHTML='<div class="v19-bottom-card"><small>WORKSPACE ENGINE</small><b id="v19Engine">BOOTING</b></div><div class="v19-bottom-card"><small>DATA PLANE</small><b id="v19DataPlane">CHECKING</b></div><div class="v19-bottom-card"><small>RISK GATE</small><b id="v19RiskGate">LOCKED</b></div>';const dock=ws.querySelector(".command-dock");dock?.before(b)}
 intel.querySelectorAll(".intel-card").forEach(n=>{if(!n.id.startsWith("v18"))n.style.display="none"});
 return true;
}
function contextHTML(m){
 return '<span class="v19-context-label">DESK CONTEXT</span>'+m.focus.map(x=>'<button class="v19-context-btn '+(x===state.focus?"active":"")+'" data-v19-focus="'+esc(x)+'">'+esc(x)+'</button>').join("");
}
function railHTML(w){
 const base='<div class="v19-rail-card"><div class="eyebrow">'+esc(MODES[w].title)+'</div><div class="v19-rail-title">'+esc(MODES[w].focus.join(" · "))+'</div><div class="v19-rail-note">'+esc(MODES[w].sub)+'</div></div>';
 if(w==="INTRADAY")return base+
 '<div class="v19-rail-card"><div class="eyebrow">SESSION CONTROL</div><div class="v19-metric-grid"><div class="v19-metric"><small>REGIME</small><b id="v19Regime">WAIT</b></div><div class="v19-metric"><small>SIGNAL</small><b id="v19Signal">WAIT</b></div><div class="v19-metric"><small>SCORE</small><b id="v19Score">0.0</b></div><div class="v19-metric"><small>SELECTED</small><b id="v19Selected">NIFTY</b></div></div><div class="v19-status" id="v19DeskStatus">VERIFYING MARKET DATA</div></div>'+
 '<div class="v19-rail-card"><div class="eyebrow">EXECUTION GUARD</div><div class="v19-list"><div><span>Mode</span><b>PAPER</b></div><div><span>Live broker</span><b>LOCKED</b></div><div><span>New entries</span><b id="v19Entries">—</b></div><div><span>Risk gate</span><b>AUTHORITATIVE</b></div></div></div>';
 if(w==="SWING")return base+
 '<div class="v19-rail-card"><div class="eyebrow">SETUP BOARD</div><div class="v19-list"><div><span>Trend</span><b id="v19SwingTrend">WAIT</b></div><div><span>Breakout</span><b id="v19SwingBreakout">WAIT</b></div><div><span>Volume</span><b id="v19SwingVolume">WAIT</b></div><div><span>R:R</span><b id="v19SwingRR">—</b></div></div></div>'+
 '<div class="v19-rail-card"><div class="eyebrow">POSITION PLAN</div><div class="v19-note v19-rail-note">Swing decisions stay separate from session-only signals. Entry, stop, target and catalyst evidence are shown only when verified.</div></div>';
 if(w==="INVESTMENT")return base+
 '<div class="v19-rail-card"><div class="eyebrow">PORTFOLIO STATE</div><div class="v19-metric-grid"><div class="v19-metric"><small>INVESTED</small><b>—</b></div><div class="v19-metric"><small>P&amp;L</small><b>—</b></div><div class="v19-metric"><small>EXPOSURE</small><b>—</b></div><div class="v19-metric"><small>WATCHLIST</small><b id="v19WatchCount">10</b></div></div></div>'+
 '<div class="v19-rail-card"><div class="eyebrow">RESEARCH GATES</div><div class="v19-list"><div><span>Fundamentals</span><b>ON REQUEST</b></div><div><span>Valuation</span><b>ON REQUEST</b></div><div><span>Concentration</span><b>MONITOR</b></div><div><span>Horizon</span><b>POSITIONAL</b></div></div></div>';
 return base+
 '<div class="v19-rail-card"><div class="eyebrow">OPTIONS CONTROL</div><div class="v19-metric-grid"><div class="v19-metric"><small>UNDERLYING</small><b id="v19OptUnderlying">NIFTY</b></div><div class="v19-metric"><small>SPOT</small><b id="v19OptSpot">—</b></div><div class="v19-metric"><small>PCR OI</small><b id="v19OptPCR">—</b></div><div class="v19-metric"><small>MAX PAIN</small><b id="v19OptMaxPain">—</b></div></div><div class="v19-status" id="v19OptStatus">CHAIN ENGINE STARTING</div></div>'+
 '<div class="v19-rail-card"><div class="eyebrow">STRATEGY SAFETY</div><div class="v19-list"><div><span>Execution</span><b>PAPER ONLY</b></div><div><span>Provider</span><b id="v19OptProvider">CHECKING</b></div><div><span>Greeks</span><b>DATA-DRIVEN</b></div><div><span>Risk</span><b>STOP + TARGET</b></div></div></div>'+
 '<div class="v19-rail-card"><div class="eyebrow">WORKSPACE ISOLATION</div><div class="v19-rail-note">Option-chain failures remain inside the Options data lane. Chart hydration is not allowed to depend on the chain request.</div></div>';
}
function paint(){
 if(!ensure())return;
 const w=workspace(),m=MODES[w]||MODES.INTRADAY;
 document.body.classList.toggle("v19-active",true);document.body.classList.toggle("v19-options",w==="OPTIONS");
 $("v19Title").textContent=m.title;$("v19Sub").textContent=m.sub;
 $("v19Contextbar").innerHTML=contextHTML(m);
 $("v19Rail").innerHTML=railHTML(w);
 const active=window.JARVIS_V17_DATA_PLANE?.state?.workspace||w;
 $("v19Engine").textContent=w==="OPTIONS"?"OPTIONS DATA PLANE":w+" WORKSPACE";
 $("v19DataPlane").textContent=(state.provider?.status||"CHECKING")+" · "+(state.health?.status||"UNKNOWN");
 $("v19RiskGate").textContent=state.paper?.running?"PAPER ENGINE RUNNING":"PAPER / LIVE LOCKED";
 $("v19Contextbar").querySelectorAll("[data-v19-focus]").forEach(b=>b.onclick=()=>{state.focus=b.dataset.v19Focus;save();paint()});

}
async function refresh(){
 const w=workspace();
 const snapshot=await json("/api/v19/workspace/state?workspace="+encodeURIComponent(w));
 state.provider=snapshot?.provider||null;state.health=snapshot?.health||null;state.paper=snapshot?.paper||null;state.options=snapshot?.options||null;
 const provider=state.provider,health=state.health,paper=state.paper,options=state.options;
 const p=provider?.status||provider?.state||"UNKNOWN";
 const h=health?.status||"UNKNOWN";
 const chips=$("v19Statebar");if(chips)chips.innerHTML=chip("WORKSPACE",w)+chip("FYERS",p,String(p).toUpperCase().includes("READY")?"ok":String(p).toUpperCase().includes("DEGRADED")?"warn":"bad")+chip("HEALTH",h,String(h).toUpperCase()==="READY"?"ok":"warn")+chip("EXECUTION","PAPER LOCKED","ok");
 if(w==="INTRADAY"){
  const sig=$("liveSignal")?.textContent||"WAIT",reg=$("signalRegime")?.textContent||"WAIT",score=$("signalScore")?.textContent||"0.0";
  $("v19Signal")&&( $("v19Signal").textContent=sig);$("v19Regime")&&($("v19Regime").textContent=reg);$("v19Score")&&($("v19Score").textContent=score);$("v19Selected")&&($("v19Selected").textContent=$("scanSymbol")?.textContent||"NIFTY");$("v19DeskStatus")&&($("v19DeskStatus").textContent=p);
 }
 if(w==="OPTIONS"){
  const o=options||{};const ready=o.success===true||String(o.status||"").toUpperCase()==="READY";
  $("v19OptStatus")&&($("v19OptStatus").textContent=ready?"CHAIN ENGINE READY":"CHAIN ENGINE DEGRADED");
  $("v19OptStatus")?.classList.toggle("ok",ready);$("v19OptStatus")?.classList.toggle("bad",!ready);
  $("v19OptProvider")&&($("v19OptProvider").textContent=ready?"FYERS READY":"FYERS DEGRADED");
 }
}
function actions(){
 document.addEventListener("click",e=>{
  const a=e.target.closest("[data-v19-action]");if(!a)return;
  const action=a.dataset.v19Action;
  if(action==="scan")$("scanButton")?.click();
  if(action==="reload")$("reloadCharts")?.click();
  if(action==="reset"){try{localStorage.removeItem("jarvis.v16.rich.workspaces")}catch{};try{localStorage.removeItem(KEY)}catch{};location.reload()}
 });
}
function observe(){
 const modes=document.querySelector(".workspace-modes");if(modes)new MutationObserver(()=>{save();paint();refresh()}).observe(modes,{subtree:true,attributes:true,attributeFilter:["class"]});
 document.addEventListener("jarvis:workspace",()=>{setTimeout(()=>{save();paint();refresh()},0)});
}
function boot(){if(!ensure())return;paint();actions();observe();refresh();setInterval(()=>{if(!document.hidden)refresh()},15000)}
if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",boot,{once:true});else boot();
})();