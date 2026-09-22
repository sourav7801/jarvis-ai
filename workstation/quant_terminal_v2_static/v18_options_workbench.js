(() => {
"use strict";
if (!window.JARVIS_V17_RUNTIME || window.__JARVIS_V18_OPTIONS_WORKBENCH__) return;
window.__JARVIS_V18_OPTIONS_WORKBENCH__ = true;

var $ = function(id){ return document.getElementById(id); };
var U = [["NIFTY","NIFTY 50"],["BANKNIFTY","BANK NIFTY"],["SENSEX","SENSEX"]];
var S = {underlying:"NIFTY",expiry:"",view:"PRICE",range:12,rows:[],spot:null,analytics:{},expiries:[],legs:[],loading:false};
var aborter=null, seq=0, timer=null;

function esc(v){return String(v==null?"":v).replace(/[&<>"']/g,function(c){return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c];});}
function n(v,d){var x=Number(v);return Number.isFinite(x)?x.toLocaleString("en-IN",{maximumFractionDigits:d==null?2:d,minimumFractionDigits:d==null?2:d}):"—";}
function rn(v){var x=Number(v);return Number.isFinite(x)?x:null;}
function px(r){var b=rn(r&&r.bid),a=rn(r&&r.ask),l=rn(r&&r.ltp);return b!=null&&a!=null&&a>=b?(b+a)/2:l;}

function style(){
 if($("v18OptionsStyle"))return;
 var s=document.createElement("style");s.id="v18OptionsStyle";
 s.textContent=[
 "#v18OptionsWorkbench{display:none;flex:1;min-height:0;min-width:0;overflow:hidden;flex-direction:column;background:#041017;border:1px solid #174457;border-radius:8px;padding:8px;color:#cfeaf2}"+
 "#v18OptionsWorkbench .h{flex:0 0 auto}",
 "#v18WorkspaceRail{display:none;flex:1;overflow:auto;background:linear-gradient(180deg,#081821,#061118);border-color:#24566a!important}#v18WorkspaceRail .v18-rail-title{font-size:20px;font-weight:800;color:#e9fbff;margin-top:8px}#v18WorkspaceRail .v18-rail-sub{font-size:8px;color:#6d96a5;line-height:1.45;margin-top:4px}#v18WorkspaceRail .v18-rail-status{margin-top:10px;padding:6px;border:1px solid #765b2c;color:#e7c76e;font-size:8px;border-radius:5px}#v18WorkspaceRail .v18-rail-status.ok{border-color:#246d4b;color:#78f2aa}#v18WorkspaceRail .v18-rail-status.bad{border-color:#713243;color:#ff8a9d}#v18WorkspaceRail .v18-rail-grid{display:grid;grid-template-columns:1fr 1fr;gap:5px;margin:9px 0 12px}#v18WorkspaceRail .v18-rail-grid>div{border:1px solid #173b4a;background:#06131a;padding:7px;border-radius:5px}#v18WorkspaceRail .v18-rail-grid small{display:block;color:#628b99;font-size:7px}#v18WorkspaceRail .v18-rail-grid b{display:block;color:#e2f7fb;font-size:12px;margin-top:3px}#v18WorkspaceRail .bt{margin-top:9px;font-size:7px;color:#77a8b7;letter-spacing:.1em}#v18WorkspaceRail .v18-rail-note{margin-top:4px;border:1px solid #153746;background:#06131a;padding:7px;color:#9cb9c4;font-size:8px;line-height:1.5;border-radius:5px}.intel-panel.v18-rail-mode > .intel-card:not(#v18WorkspaceRail){display:none!important}",
 "#v18OptionsWorkbench .h{display:flex;justify-content:space-between;gap:8px}#v18OptionsWorkbench .t{font-size:12px;letter-spacing:.12em;color:#e7fbff;font-weight:700}#v18OptionsWorkbench .sub{font-size:7px;color:#6d9baa;margin-top:3px}",
 "#v18OptionsWorkbench .controls{display:flex;align-items:center;gap:5px;margin:8px 0;flex:0 0 auto;min-height:29px;flex-wrap:nowrap}#v18OptionsWorkbench .controls select{width:145px;flex:0 0 145px}#v18OptionsWorkbench .controls select:nth-child(3){width:105px;flex-basis:105px}#v18OptionsWorkbench .controls>.primary{width:120px;flex:0 0 120px}#v18OptionsWorkbench .tabs{margin-left:auto;flex:0 0 auto}
 "#v18OptionsWorkbench select,#v18OptionsWorkbench button{min-height:29px;background:#061821;border:1px solid #24566a;color:#d9f4fa;border-radius:4px;padding:5px 7px;font-size:8px}",
 "#v18OptionsWorkbench button{cursor:pointer}#v18OptionsWorkbench .active{border-color:#4fc5e8!important;background:#0a2a36!important}#v18OptionsWorkbench .primary{border-color:#37a66f!important;color:#8af0b4!important}",
 "#v18OptionsWorkbench .tabs{display:flex;gap:4px}#v18OptionsWorkbench .status{padding:6px 8px;border-left:2px solid #e2b84d;background:#08171e;color:#d8bd75;font-size:8px;margin-bottom:6px}#v18OptionsWorkbench .status.ok{border-color:#43d58e;color:#8feeb9}#v18OptionsWorkbench .status.err{border-color:#ff667d;color:#ff9aa9}",
 "#v18OptionsWorkbench .summary{display:grid;grid-template-columns:repeat(7,minmax(70px,1fr));gap:4px;margin-bottom:7px}#v18OptionsWorkbench .card{border:1px solid #153b49;background:#06141b;padding:6px}#v18OptionsWorkbench .card small{display:block;color:#628b99;font-size:6px}#v18OptionsWorkbench .card b{display:block;margin-top:3px;color:#e2f7fb;font-size:10px}",
 "#v18OptionsWorkbench .main{display:grid;grid-template-columns:minmax(0,1fr) 270px;gap:7px;flex:1;min-height:0}#v18OptionsWorkbench .chain{min-width:0;min-height:0;border:1px solid #153d4b;overflow:auto}#v18OptionsWorkbench .chain table{width:100%;border-collapse:collapse;font-size:7px}#v18OptionsWorkbench .chain th{position:sticky;top:0;background:#0a1c25;color:#7fb8ca;padding:7px 5px;text-align:right}#v18OptionsWorkbench .chain th:first-child,#v18OptionsWorkbench .chain td:first-child{text-align:left}#v18OptionsWorkbench .chain td{padding:6px 5px;border-top:1px solid #0e2b36;text-align:right;white-space:nowrap}#v18OptionsWorkbench .chain tr:hover{background:#0b222c}#v18OptionsWorkbench .chain tr.atm{background:#102b30;box-shadow:inset 2px 0 #45d39a}#v18OptionsWorkbench .ce{color:#8cecb6}#v18OptionsWorkbench .pe{color:#ff9baa}#v18OptionsWorkbench .strike{font-weight:700;color:#f0f8fa}",
 "#v18OptionsWorkbench .side{display:flex;flex-direction:column;gap:6px;min-width:0;min-height:0;overflow:auto}#v18OptionsWorkbench .empty{padding:28px;text-align:center;color:#6f96a5;font-size:9px;line-height:1.6}#v18OptionsWorkbench .empty b{display:block;color:#d8eef5;font-size:11px;margin-bottom:5px}#v18OptionsWorkbench .box{border:1px solid #153d4b;background:#06141b;padding:7px}#v18OptionsWorkbench .bt{font-size:7px;color:#77a8b7;letter-spacing:.1em;margin-bottom:6px}#v18OptionsWorkbench .leg{display:grid;grid-template-columns:35px 1fr auto;gap:4px;align-items:center;margin:3px 0;font-size:7px}#v18OptionsWorkbench .leg button{min-height:22px;padding:2px 6px}#v18OptionsWorkbench .note{font-size:6px;color:#5f8998;line-height:1.5}",
 "@media(max-width:1100px){#v18OptionsWorkbench .main{grid-template-columns:1fr;overflow:auto}#v18OptionsWorkbench .side{display:grid!important;grid-template-columns:1fr 1fr}#v18OptionsWorkbench .summary{grid-template-columns:repeat(4,1fr)!important}}",
 "@media(max-width:800px){#v18OptionsWorkbench .controls{flex-wrap:wrap}#v18OptionsWorkbench .controls select,#v18OptionsWorkbench .controls>.primary{flex:1 1 140px;width:auto}#v18OptionsWorkbench .tabs{margin-left:0}#v18OptionsWorkbench .summary{grid-template-columns:repeat(2,1fr)!important}#v18OptionsWorkbench .side{display:block!important}}"
 ].join("");
 document.head.appendChild(s);
}

function mount(){
 style();
 var host=$("v18OptionsWorkbench"); if(host)return host;
 var w=document.querySelector(".workspace"),g=$("chartGrid"); if(!w||!g)return null;
 host=document.createElement("section");host.id="v18OptionsWorkbench";
 host.innerHTML=[
 '<div class="h"><div><div class="t">JARVIS V18 · OPTIONS INTELLIGENCE WORKBENCH</div><div class="sub">Dedicated option data plane · chain analytics · Greeks · OI structure · straddle view · paper strategy laboratory</div></div><div id="v18Provider" class="card">FYERS · CHECKING</div></div>',
 '<div class="controls"><select id="v18Underlying"></select><select id="v18Expiry"><option value="">NEAREST EXPIRY</option></select><select id="v18Range"><option value="8">±8 STRIKES</option><option value="12" selected>±12 STRIKES</option><option value="20">±20 STRIKES</option></select><button id="v18Refresh" class="primary">REFRESH CHAIN</button><div class="tabs"><button data-view="PRICE" class="active">PRICE</button><button data-view="GREEKS">GREEKS</button><button data-view="STRADDLE">STRADDLE</button></div></div>',
 '<div id="v18Status" class="status">Ready. Option requests are isolated from chart hydration and execution.</div><div id="v18Summary" class="summary"></div>',
 '<div class="main"><div class="chain"><table><thead id="v18Head"></thead><tbody id="v18Rows"></tbody></table></div><div class="side">',
 '<div class="box"><div class="bt">PAPER STRATEGY LAB</div><div id="v18Legs"></div><button id="v18Add" class="primary" style="width:100%;margin-top:5px">+ ADD ATM LEG</button><div id="v18Payoff" class="note"></div></div>',
 '<div class="box"><div class="bt">CHAIN STRUCTURE</div><div id="v18Structure" class="note">Waiting for verified chain.</div></div>',
 '<div class="box"><div class="bt">DATA / SAFETY</div><div class="note">Read-only FYERS data. Paper/research only. No broker order endpoint is called by this workbench. A provider timeout degrades only this pane.</div></div>',
 '</div></div>'].join("");
 w.insertBefore(host,g);
 var intel=document.querySelector(".intel-panel");
 if(intel&&!$("v18WorkspaceRail")){
   var rail=document.createElement("section");rail.id="v18WorkspaceRail";rail.className="intel-card";intel.insertBefore(rail,intel.firstChild);
 }
 U.forEach(function(x){var o=document.createElement("option");o.value=x[0];o.textContent=x[1];$("v18Underlying").appendChild(o);});
 $("v18Underlying").onchange=function(){S.underlying=this.value;S.expiry="";S.legs=[];load();};
 $("v18Expiry").onchange=function(){S.expiry=this.value;load();};
 $("v18Range").onchange=function(){S.range=Number(this.value)||12;render();};
 $("v18Refresh").onclick=load;
 host.querySelectorAll("[data-view]").forEach(function(b){b.onclick=function(){S.view=this.dataset.view;host.querySelectorAll("[data-view]").forEach(function(x){x.classList.toggle("active",x===b);});render();};});
 $("v18Add").onclick=addATM;
 return host;
}

function pairs(){
 var m=new Map(),rows=S.rows||[];
 rows.forEach(function(r){var t=String(r&&r.option_type||"").toUpperCase(),k=rn(r&&r.strike);if(!k||!(t==="CE"||t==="PE"))return;if(!m.has(k))m.set(k,{strike:k,CE:null,PE:null});m.get(k)[t]=r;});
 var all=Array.from(m.values()).sort(function(a,b){return a.strike-b.strike;});
 if(S.spot==null)return all;
 var ai=0,md=Infinity;all.forEach(function(p,i){var d=Math.abs(p.strike-S.spot);if(d<md){md=d;ai=i;}});
 return all.slice(Math.max(0,ai-S.range),Math.min(all.length,ai+S.range+1));
}

function render(){
 var ps=pairs(),h=$("v18Head"),body=$("v18Rows");if(!h||!body)return;
 if(!ps.length){
   h.innerHTML="<tr><th>CE</th><th>BID</th><th>ASK</th><th>OI</th><th>ΔOI</th><th>STRIKE</th><th>ΔOI</th><th>OI</th><th>BID</th><th>ASK</th><th>PE</th></tr>";
   body.innerHTML="<tr><td colspan=\"11\"><div class=\"empty\"><b>OPTION CHAIN DATA UNAVAILABLE</b>Waiting for a verified FYERS chain. The Options workspace remains isolated; chart hydration is not blocked.</div></td></tr>";
 }
 var a=S.analytics||{},atm=null;
 if(ps.length&&S.spot!=null)atm=ps.reduce(function(x,y){return Math.abs(y.strike-S.spot)<Math.abs(x.strike-S.spot)?y:x;},ps[0]).strike;
 if(S.view==="GREEKS")h.innerHTML="<tr><th>CE IV</th><th>CE Δ</th><th>CE Γ</th><th>CE Θ</th><th>STRIKE</th><th>PE Θ</th><th>PE Γ</th><th>PE Δ</th><th>PE IV</th></tr>";
 else if(S.view==="STRADDLE")h.innerHTML="<tr><th>CE OI</th><th>CE LTP</th><th>CE IV</th><th>STRIKE</th><th>PE IV</th><th>PE LTP</th><th>PE OI</th><th>STRADDLE</th></tr>";
 else h.innerHTML="<tr><th>CE LTP</th><th>CE BID</th><th>CE ASK</th><th>CE OI</th><th>CE ΔOI</th><th>STRIKE</th><th>PE ΔOI</th><th>PE OI</th><th>PE BID</th><th>PE ASK</th><th>PE LTP</th></tr>";
 if(ps.length) body.innerHTML=ps.map(function(p){
   var ce=p.CE||{},pe=p.PE||{},c=px(ce),q=px(pe),cls=p.strike===atm?"atm":"";
   if(S.view==="GREEKS")return '<tr class="'+cls+'"><td>'+n(ce.iv)+'</td><td>'+n(ce.delta,3)+'</td><td>'+n(ce.gamma,4)+'</td><td>'+n(ce.theta,3)+'</td><td class="strike">'+n(p.strike,0)+'</td><td>'+n(pe.theta,3)+'</td><td>'+n(pe.gamma,4)+'</td><td>'+n(pe.delta,3)+'</td><td>'+n(pe.iv)+'</td></tr>';
   if(S.view==="STRADDLE")return '<tr class="'+cls+'"><td>'+n(ce.open_interest,0)+'</td><td>'+n(c)+'</td><td>'+n(ce.iv)+'</td><td class="strike">'+n(p.strike,0)+'</td><td>'+n(pe.iv)+'</td><td>'+n(q)+'</td><td>'+n(pe.open_interest,0)+'</td><td>'+n((c||0)+(q||0))+'</td></tr>';
   return '<tr class="'+cls+'"><td class="ce">'+n(ce.ltp)+'</td><td>'+n(ce.bid)+'</td><td>'+n(ce.ask)+'</td><td>'+n(ce.open_interest,0)+'</td><td>'+n(ce.change_in_oi,0)+'</td><td class="strike">'+n(p.strike,0)+'</td><td>'+n(pe.change_in_oi,0)+'</td><td>'+n(pe.open_interest,0)+'</td><td>'+n(pe.bid)+'</td><td>'+n(pe.ask)+'</td><td class="pe">'+n(pe.ltp)+'</td></tr>';
 }).join("");
 if(!ps.length) body.innerHTML="<tr><td colspan=\"11\"><div class=\"empty\"><b>NO VERIFIED STRIKES</b>Select an expiry or refresh the chain after FYERS data becomes ready.</div></td></tr>";
 $("v18Summary").innerHTML=[["SPOT",n(S.spot)],["PCR OI",n(S.pcr)],["CALL WALL",n(a&&a.call_oi_wall&&a.call_oi_wall.strike,0)],["PUT WALL",n(a&&a.put_oi_wall&&a.put_oi_wall.strike,0)],["MAX PAIN",n(a&&a.max_pain&&a.max_pain.strike,0)],["EXPIRY",S.expiry||"NEAREST"],["STRIKES",ps.length]].map(function(x){return '<div class="card"><small>'+x[0]+'</small><b>'+esc(x[1])+'</b></div>';}).join("");
 var call=ps.slice().sort(function(x,y){return (rn(y.CE&&y.CE.open_interest)||0)-(rn(x.CE&&x.CE.open_interest)||0);})[0],put=ps.slice().sort(function(x,y){return (rn(y.PE&&y.PE.open_interest)||0)-(rn(x.PE&&x.PE.open_interest)||0);})[0];
 $("v18Structure").innerHTML="Call wall: <b>"+n(a&&a.call_oi_wall&&a.call_oi_wall.strike,0)+"</b><br>Put wall: <b>"+n(a&&a.put_oi_wall&&a.put_oi_wall.strike,0)+"</b><br>Max pain: <b>"+n(a&&a.max_pain&&a.max_pain.strike,0)+"</b><br>Highest CE OI: "+n(call&&call.strike,0)+"<br>Highest PE OI: "+n(put&&put.strike,0);
 renderLegs();
 updateWorkspaceRail();
}

function renderWorkspaceRail(){
 var host=$("v18WorkspaceRail");if(!host)return;
 var active=String(document.querySelector(".workspace-modes button.active")?.dataset.workspace||"INTRADAY").toUpperCase();
 var intel=document.querySelector(".intel-panel");
 if(active==="INTRADAY"){
   host.style.display="none";
   if(intel)intel.classList.remove("v18-rail-mode");
   return;
 }
   if(intel)intel.classList.add("v18-rail-mode");
   host.style.display="block";
   if(active==="OPTIONS"){
     var a=S.analytics||{};
     host.innerHTML="<div class='eyebrow'>OPTIONS INTELLIGENCE</div>"+
       "<div class='v18-rail-title'>"+esc(S.underlying||"NIFTY")+"</div>"+
       "<div class='v18-rail-sub'>Dedicated option decision rail · paper / research only</div>"+
       "<div class='v18-rail-status "+(S.loading?"wait":(S.rows.length?"ok":"bad"))+"'>"+(S.loading?"LOADING CHAIN":(S.rows.length?"FYERS VERIFIED":"FYERS DEGRADED"))+"</div>"+
       "<div class='v18-rail-grid'>"+
       "<div><small>SPOT</small><b>"+n(S.spot)+"</b></div><div><small>PCR OI</small><b>"+n(S.pcr,2)+"</b></div>"+
       "<div><small>CALL WALL</small><b>"+n(a.call_oi_wall&&a.call_oi_wall.strike,0)+"</b></div><div><small>PUT WALL</small><b>"+n(a.put_oi_wall&&a.put_oi_wall.strike,0)+"</b></div>"+
       "<div><small>MAX PAIN</small><b>"+n(a.max_pain&&a.max_pain.strike,0)+"</b></div><div><small>EXPIRY</small><b>"+esc(S.expiry||"NEAREST")+"</b></div>"+
       "</div>"+
       "<div class='bt'>PAPER STRATEGY</div><div class='v18-rail-note'>"+(S.legs.length?S.legs.map(function(l){return esc(l.action+" "+l.type+" "+n(l.strike,0));}).join("<br>"):"No active paper legs.")+"</div>"+
       "<div class='bt'>CHAIN STATE</div><div class='v18-rail-note'>"+(S.rows.length?(S.rows.length+" contracts loaded · "+(pairs().length)+" strikes in view."):"No verified chain loaded.")+"</div>"+
       "<div class='bt'>SAFETY</div><div class='v18-rail-note'>Provider failures stay inside the Options lane. No broker order endpoint is used here.</div>";
   }else if(active==="SWING"){
     host.innerHTML="<div class='eyebrow'>SWING INTELLIGENCE</div><div class='v18-rail-title'>SETUP CONTROL</div><div class='v18-rail-sub'>Medium-horizon market structure and position planning</div>"+
       "<div class='bt'>FOCUS</div><div class='v18-rail-note'>Trend · breakout · volume · relative strength · catalyst awareness</div>"+
       "<div class='bt'>RISK GEOMETRY</div><div class='v18-rail-grid'><div><small>ENTRY</small><b>—</b></div><div><small>STOP</small><b>—</b></div><div><small>TARGET</small><b>—</b></div><div><small>R:R</small><b>—</b></div></div>"+
       "<div class='bt'>WORKSPACE RULE</div><div class='v18-rail-note'>Swing evidence is kept separate from intraday execution signals.</div>";
   }else{
     host.innerHTML="<div class='eyebrow'>INVESTMENT INTELLIGENCE</div><div class='v18-rail-title'>PORTFOLIO CONTROL</div><div class='v18-rail-sub'>Long-horizon allocation and fundamental research</div>"+
       "<div class='bt'>FOCUS</div><div class='v18-rail-note'>Allocation · valuation · growth · quality · concentration · catalysts</div>"+
       "<div class='bt'>PORTFOLIO STATE</div><div class='v18-rail-grid'><div><small>INVESTED</small><b>—</b></div><div><small>P&L</small><b>—</b></div><div><small>EXPOSURE</small><b>—</b></div><div><small>WATCHLIST</small><b>—</b></div></div>"+
       "<div class='bt'>WORKSPACE RULE</div><div class='v18-rail-note'>Investment research does not inherit intraday entry or option-chain signals.</div>";
   }
}
function updateWorkspaceRail(){renderWorkspaceRail();}
function addATM(){
 var ps=pairs();if(!ps.length)return;
 var p=ps.reduce(function(x,y){return Math.abs(y.strike-(S.spot||y.strike))<Math.abs(x.strike-(S.spot||x.strike))?y:x;},ps[0]);
 var type=window.prompt("Enter BUY CE, SELL CE, BUY PE, or SELL PE","BUY CE");if(!type)return;
 var m=String(type).toUpperCase().match(/^(BUY|SELL)\\s+(CE|PE)$/);if(!m||!p[m[2]])return;
 S.legs.push({action:m[1],type:m[2],strike:p.strike,premium:px(p[m[2]])});renderLegs();
}

function renderLegs(){
 var host=$("v18Legs"),pay=$("v18Payoff");if(!host||!pay)return;
 host.innerHTML=S.legs.length?S.legs.map(function(l,i){return '<div class="leg"><span class="'+(l.type==="CE"?"ce":"pe")+'">'+l.type+'</span><span>'+l.action+' '+n(l.strike,0)+' @ '+n(l.premium)+'</span><button data-leg="'+i+'">×</button></div>';}).join(""):'<div class="note">No paper legs. Add the ATM leg to begin scenario analysis.</div>';
 host.querySelectorAll("[data-leg]").forEach(function(b){b.onclick=function(){S.legs.splice(Number(this.dataset.leg),1);renderLegs();};});
 if(!S.legs.length){pay.textContent="Strategy lab idle.";return;}
 var net=S.legs.reduce(function(x,l){return x+(l.action==="BUY"?-1:1)*(l.premium||0);},0),spot=S.spot||S.legs[0].strike;
 function payoff(x){return S.legs.reduce(function(v,l){var iv=l.type==="CE"?Math.max(0,x-l.strike):Math.max(0,l.strike-x);return v+(l.action==="BUY"?iv-(l.premium||0):(l.premium||0)-iv);},0);}
 pay.innerHTML="Net premium/unit: <b>"+n(net)+"</b><br>Spot P/L: <b>"+n(payoff(spot))+"</b><br>±2% P/L: "+n(payoff(spot*.98))+" / "+n(payoff(spot*1.02))+"<br><span class='note'>Research approximation per unit; lot size, fees and slippage excluded.</span>";
}

async function load(){
 mount();var ticket=++seq;if(aborter)aborter.abort();aborter=new AbortController();S.loading=true;
 $("v18Status").className="status";$("v18Status").textContent="Loading verified "+S.underlying+" option chain…";$("v18Refresh").disabled=true;
 try{
  var q=new URLSearchParams({workspace:"OPTIONS",symbol:S.underlying,module:"option-chain"});if(S.expiry)q.set("expiry",S.expiry);
  var r=await fetch("/api/v17/options/chain?"+q.toString(),{cache:"no-store",signal:aborter.signal}),p=await r.json().catch(function(){return {};});
  if(ticket!==seq)return;if(!r.ok||p.success!==true)throw new Error(p.message||p.reason||("HTTP "+r.status));
  S.rows=Array.isArray(p.chain)?p.chain:[];S.spot=rn(p.spot);S.analytics=p.chain_analytics||{};S.pcr=rn(p.pcr_oi);S.expiries=Array.isArray(p.available_expiries)?p.available_expiries:[];
  var e=$("v18Expiry");e.innerHTML='<option value="">NEAREST EXPIRY</option>'+S.expiries.map(function(x){return '<option value="'+esc(x)+'">'+esc(x)+'</option>';}).join("");e.value=S.expiry;
  $("v18Provider").innerHTML="FYERS · VERIFIED";$("v18Status").className="status ok";$("v18Status").textContent="Verified "+S.underlying+" chain · "+S.rows.length+" contracts · "+(S.expiry||"nearest expiry");
  render();
 }catch(err){
  if(ticket!==seq||err.name==="AbortError")return;S.rows=[];S.analytics={};$("v18Provider").innerHTML="FYERS · DEGRADED";$("v18Status").className="status err";$("v18Status").textContent="Options plane isolated: "+(err.message||"data request failed");render();
 }finally{if(ticket===seq){S.loading=false;$("v18Refresh").disabled=false;}}
}

function visible(){
 var h=mount();if(!h)return;var active=String(document.querySelector(".workspace-modes button.active")?.dataset.workspace||"").toUpperCase()==="OPTIONS";
 h.style.display=active?"flex":"none";var g=$("chartGrid");if(g)g.style.display=active?"none":"grid";
 var tb=document.querySelector(".workspace-toolbar");if(tb)tb.style.display=active?"none":"flex";
 var old=$("v17OptionsWorkspace");if(old)old.style.display="none";
 if(active&&!S.rows.length&&!S.loading)load();
}
function boot(){mount();visible();document.addEventListener("jarvis:workspace",function(){visible();renderWorkspaceRail();});document.querySelector(".workspace-modes")?.addEventListener("click",function(){setTimeout(visible,0);});timer=setInterval(function(){var a=String(document.querySelector(".workspace-modes button.active")?.dataset.workspace||"").toUpperCase()==="OPTIONS";if(a&&!document.hidden&&!S.loading)load();},45000);window.addEventListener("beforeunload",function(){clearInterval(timer);if(aborter)aborter.abort();},{once:true});}
if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",boot,{once:true});else boot();
})();