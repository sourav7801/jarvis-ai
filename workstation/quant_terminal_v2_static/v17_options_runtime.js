(() => {
"use strict";
if (!window.JARVIS_V17_RUNTIME || window.__JARVIS_V17_OPTIONS_RUNTIME__) return;
window.__JARVIS_V17_OPTIONS_RUNTIME__ = true;

const $ = id => document.getElementById(id);
const UNDERLYINGS = [["NIFTY","NIFTY 50"],["BANKNIFTY","BANK NIFTY"],["SENSEX","SENSEX"]];
let underlying = "NIFTY";
let expiry = "";
let request = null;
let serial = 0;
let refreshTimer = null;

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, function(c) {
    return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c];
  });
}
function fmt(value, digits) {
  const n = Number(value);
  if (!Number.isFinite(n)) return "—";
  return n.toLocaleString("en-IN",{maximumFractionDigits:digits ?? 2,minimumFractionDigits:digits ?? 2});
}
function ensurePanel() {
  let node = $("v17OptionsWorkspace");
  if (node) return node;
  const host = document.querySelector(".workspace");
  const grid = $("chartGrid");
  if (!host || !grid) return null;
  const style = document.createElement("style");
  style.id = "v17OptionsStyle";
  style.textContent =
    "#v17OptionsWorkspace{border:1px solid #24586d;background:#06141b;border-radius:7px;margin:0 0 8px;padding:10px}" +
    "#v17OptionsWorkspace .ohead{font-size:12px;color:#dff8ff;letter-spacing:.08em}" +
    "#v17OptionsWorkspace .osub{margin-top:4px;color:#779aaa;font-size:8px}" +
    "#v17OptionsWorkspace .ocontrols{display:grid;grid-template-columns:160px 160px auto;gap:6px;margin:9px 0}" +
    "#v17OptionsWorkspace select,#v17OptionsWorkspace button{min-height:32px;background:#071923;border:1px solid #28576a;color:#dff7ff;border-radius:5px;padding:5px 8px;font-size:8px}" +
    "#v17OptionsWorkspace button{cursor:pointer}.primary{border-color:#2d8a61!important;color:#85f1b4!important}" +
    "#v17OptionsWorkspace button:disabled{opacity:.4}.ostatus{padding:7px;border-left:2px solid #ffd166;background:#091820;color:#d8c37e;font-size:8px}" +
    "#v17OptionsWorkspace .ok{border-color:#46d78d;color:#91efb9}.error{border-color:#ff667d;color:#ff9aaa}" +
    "#v17OptionsWorkspace .ostats{display:grid;grid-template-columns:repeat(5,1fr);gap:4px;margin:7px 0}" +
    "#v17OptionsWorkspace .ostats div{border:1px solid #163e4e;background:#06131a;padding:6px}.ostats small{display:block;color:#688d9b;font-size:6px}.ostats b{font-size:9px;color:#dff8ff}" +
    "#v17OptionsWorkspace .otable{max-height:430px;overflow:auto;border:1px solid #163d4c}" +
    "#v17OptionsWorkspace table{width:100%;border-collapse:collapse;font-size:7px}#v17OptionsWorkspace th{position:sticky;top:0;background:#0a1b24;color:#7fb6c8;padding:6px;text-align:right}#v17OptionsWorkspace th:first-child,#v17OptionsWorkspace td:first-child{text-align:left}#v17OptionsWorkspace td{padding:5px;border-top:1px solid #102d39;text-align:right;color:#cce9f2}.ce{color:#8be8b2}.pe{color:#ff91a3}";
  document.head.appendChild(style);
  node = document.createElement("section");
  node.id = "v17OptionsWorkspace";
  node.hidden = true;
  node.innerHTML =
    '<div class="ohead">JARVIS V17 · OPTIONS WORKSPACE</div>' +
    '<div class="osub">Dedicated isolated option-chain lane. Provider failures stay inside this workspace.</div>' +
    '<div class="ocontrols"><select id="v17OptUnderlying">' +
    UNDERLYINGS.map(function(x){ return '<option value="' + x[0] + '">' + x[1] + '</option>'; }).join("") +
    '</select><select id="v17OptExpiry"><option value="">NEAREST</option></select>' +
    '<button id="v17OptReload" class="primary" type="button">LOAD OPTION CHAIN</button></div>' +
    '<div id="v17OptStatus" class="ostatus">Ready.</div><div id="v17OptStats" class="ostats"></div>' +
    '<div class="otable"><table><thead><tr><th>TYPE</th><th>STRIKE</th><th>LTP</th><th>BID</th><th>ASK</th><th>VOL</th><th>OI</th><th>ΔOI</th><th>IV</th><th>DELTA</th><th>GAMMA</th><th>THETA</th><th>VEGA</th></tr></thead><tbody id="v17OptRows"></tbody></table></div>';
  host.insertBefore(node, grid);
  $("v17OptUnderlying").addEventListener("change", function(e){ underlying=String(e.target.value).toUpperCase(); expiry=""; $("v17OptExpiry").innerHTML='<option value="">NEAREST</option>'; loadChain(); });
  $("v17OptExpiry").addEventListener("change", function(e){ expiry=String(e.target.value||""); loadChain(); });
  $("v17OptReload").addEventListener("click", loadChain);
  return node;
}
function render(payload) {
  const status=$("v17OptStatus"), rowsNode=$("v17OptRows"), stats=$("v17OptStats");
  const rows=Array.isArray(payload && payload.chain) ? payload.chain : [];
  if(status){
    status.className="ostatus " + (payload && payload.success && rows.length ? "ok" : "error");
    status.textContent=(payload && payload.message) || (rows.length ? "Loaded " + rows.length + " contracts." : "No verified contracts returned.");
  }
  if(stats){
    const a=(payload && payload.chain_analytics) || {};
    const cells=[["SPOT",fmt(payload && payload.spot)],["PCR OI",fmt(payload && (payload.pcr_oi ?? a.pcr_oi))],["CALL WALL",fmt(a.call_oi_wall && a.call_oi_wall.strike,0)],["PUT WALL",fmt(a.put_oi_wall && a.put_oi_wall.strike,0)],["MAX PAIN",fmt(a.max_pain && a.max_pain.strike,0)]];
    stats.innerHTML=cells.map(function(x){return "<div><small>"+x[0]+"</small><b>"+esc(x[1])+"</b></div>";}).join("");
  }
  if(rowsNode){
    rowsNode.innerHTML=rows.map(function(r){
      const t=String(r && r.option_type || "—").toUpperCase();
      const cls=t==="CE"?"ce":t==="PE"?"pe":"";
      return "<tr><td class=\"" + cls + "\">" + esc(t) + "</td><td>" + esc(fmt(r && r.strike,0)) + "</td><td>" + esc(fmt(r && r.ltp)) +
        "</td><td>" + esc(fmt(r && r.bid)) + "</td><td>" + esc(fmt(r && r.ask)) + "</td><td>" + esc(fmt(r && r.volume,0)) +
        "</td><td>" + esc(fmt(r && r.open_interest,0)) + "</td><td>" + esc(fmt(r && r.change_in_oi,0)) +
        "</td><td>" + esc(fmt(r && r.iv)) + "</td><td>" + esc(fmt(r && r.delta,3)) + "</td><td>" + esc(fmt(r && r.gamma,4)) +
        "</td><td>" + esc(fmt(r && r.theta,3)) + "</td><td>" + esc(fmt(r && r.vega,3)) + "</td></tr>";
    }).join("");
  }
  const exp=$("v17OptExpiry"), list=Array.isArray(payload && payload.available_expiries)?payload.available_expiries:[];
  if(exp){ exp.innerHTML='<option value="">NEAREST</option>'+list.map(function(v){return '<option value="'+esc(v)+'">'+esc(v)+'</option>';}).join(""); if(expiry && list.includes(expiry)) exp.value=expiry; }
}
async function loadChain(){
  const node=ensurePanel();
  if(!node || node.hidden) return;
  const ticket=++serial;
  if(request) request.abort();
  request=new AbortController();
  const status=$("v17OptStatus"), button=$("v17OptReload");
  status.className="ostatus";
  status.textContent="Loading " + underlying + " option chain…";
  button.disabled=true;
  try{
    const qs=new URLSearchParams({workspace:"OPTIONS",symbol:underlying,module:"option-chain"});
    if(expiry) qs.set("expiry",expiry);
    const res=await fetch("/api/v17/options/chain?"+qs.toString(),{cache:"no-store",signal:request.signal});
    const payload=await res.json().catch(function(){return {};});
    if(ticket!==serial) return;
    if(!res.ok || payload.success!==true) throw new Error(payload.message || payload.reason || ("HTTP "+res.status));
    render(payload);
  }catch(error){
    if(ticket!==serial || error.name==="AbortError") return;
    render({success:false,message:error.message || "Option chain request failed.",chain:[]});
  }finally{
    if(ticket===serial){ request=null; button.disabled=false; }
  }
}
function visibility(){
  const node=ensurePanel();
  if(!node) return;
  const active=String(document.querySelector(".workspace-modes button.active")?.dataset.workspace || "").toUpperCase()==="OPTIONS";
  node.hidden=!active;
  if(active && !$("v17OptRows")?.children.length && !request) loadChain();
}
function boot(){
  ensurePanel();
  visibility();
  document.addEventListener("jarvis:workspace",visibility);
  document.querySelector(".workspace-modes")?.addEventListener("click",function(){setTimeout(visibility,0);});
  refreshTimer=setInterval(function(){
    const active=String(document.querySelector(".workspace-modes button.active")?.dataset.workspace || "").toUpperCase()==="OPTIONS";
    if(active && !document.hidden && !request) loadChain();
  },30000);
  window.addEventListener("beforeunload",function(){clearInterval(refreshTimer);if(request)request.abort();},{once:true});
}
if(document.readyState==="loading") document.addEventListener("DOMContentLoaded",boot,{once:true}); else boot();
})();