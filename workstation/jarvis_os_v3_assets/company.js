(() => {
  "use strict";
  const TOKEN=window.JARVIS_TOKEN;
  const $=id=>document.getElementById(id);
  const text=(id,value,fallback="—")=>{const node=$(id);if(node)node.textContent=String(value??fallback)};
  const clean=value=>String(value??"").replaceAll("_"," ");
  const SpeechRecognition=window.SpeechRecognition||window.webkitSpeechRecognition;
  const TYPED_COMMAND={input_mode: "typed"};
  const VOICE_COMMAND={input_mode: "voice"};
  let recognition=null;

  async function api(path,options={}){
    const response=await fetch(path,{...options,cache:"no-store",headers:{...(options.headers||{}),"X-Jarvis-Token":TOKEN,"Content-Type":"application/json"}});
    const payload=await response.json();
    if(!response.ok)throw new Error(payload.error||payload.response||`HTTP ${response.status}`);
    return payload;
  }

  function row(title,detail,status="READY",locked=false){
    const node=document.createElement("div");node.className="row";
    const heading=document.createElement("strong");heading.textContent=String(title||"ITEM");
    const body=document.createElement("div");const paragraph=document.createElement("p");paragraph.textContent=String(detail||"No detail recorded.");body.append(heading,paragraph);
    const badge=document.createElement("span");badge.className=`pill${locked?" lock":""}`;badge.textContent=clean(status);
    node.append(body,badge);return node;
  }

  function replaceBoard(id,nodes,empty){
    const board=$(id);if(!board)return;
    if(nodes.length){board.replaceChildren(...nodes);return}
    const node=document.createElement("div");node.className="empty";node.textContent=empty;board.replaceChildren(node);
  }

  function render(state){
    const plan=state.latest_plan||{};const autopilot=plan.autopilot||{};
    const tasks=Array.isArray(plan.tasks)?plan.tasks:[];
    const program=plan.research_program||{};
    const tracks=Array.isArray(program.research_tracks)?program.research_tracks:[];
    const horizons=Array.isArray(program.horizons)?program.horizons:[];
    const artifacts=Array.isArray(plan.artifacts)?plan.artifacts:[];
    const queuedActions=state.external_action_queue?.actions;
    const actions=Array.isArray(queuedActions)
      ? queuedActions
      : (Array.isArray(plan.external_actions)?plan.external_actions:[]);
    const runs=Array.isArray(state.autopilot_runs)?state.autopilot_runs:[];

    text("ventureName",plan.company_name||"NO ACTIVE VENTURE");
    text("ventureIdea",plan.idea||"Describe a startup idea to create a supervised local venture workspace.");
    text("departmentCount",state.agent_count||0);text("artifactCount",artifacts.length);text("trackCount",tracks.length);text("approvalCount",actions.length);
    text("ventureStatus",plan.status||"WAITING FOR IDEA");text("researchStatus",autopilot.research||"NOT STARTED");
    text("departmentStatus",autopilot.department_workboard||"NOT STARTED");text("publishingStatus",autopilot.publishing||"APPROVAL REQUIRED");

    replaceBoard("departmentBoard",tasks.map(item=>row(`${item.id} · ${item.department}`,`${item.title} — ${item.deliverable}`,item.status,item.approval_required)),"No department tasks yet.");
    replaceBoard("researchTracks",tracks.map(item=>{
      const questions=Array.isArray(item.questions)?item.questions.join(" "):String(item.questions||"");
      return row(`${item.id} · ${item.title}`,questions||item.deliverable||"Evidence question pending.",item.owner||"RESEARCH",Boolean(item.approval_required));
    }),"No research tracks yet.");
    replaceBoard("roadmapBoard",horizons.map(item=>row(`${item.horizon||"HORIZON"} · ${item.gate||"DECISION GATE"}`,item.outcome||item.goal||"Evidence gate pending.","UNVERIFIED")),"No long-horizon gates yet.");
    replaceBoard("artifactBoard",artifacts.slice(0,40).map(item=>row(item.name||"LOCAL ARTIFACT",item.path||"Local path unavailable.","LOCAL FILE")),"No local artifacts yet.");
    replaceBoard("approvalBoard",actions.map(item=>row(`${item.department||"DEPARTMENT"} · ${item.action_type||"ACTION"}`,`${item.connector||"connector"} → ${item.destination||"UNCONFIGURED"}; executed=${Boolean(item.executed)}`,item.status||"REVIEW REQUIRED",true)),"No external action drafts. Nothing has executed.");
    replaceBoard("activityBoard",runs.slice(0,20).map(item=>row(item.kind||item.action||"BACKGROUND RUN",item.completed_at||item.started_at||item.message||"No timestamp recorded.",item.status||"RECORDED")),"No background company run has completed yet.");

    const truth=[];
    const addTruth=(label,value)=>{const node=document.createElement("div");node.className="truth";const strong=document.createElement("b");strong.textContent=`${label}: `;node.append(strong,document.createTextNode(String(value||"NOT RECORDED")));truth.push(node)};
    addTruth("CURRENT LOCAL STATE",autopilot.status||plan.status||"WAITING");
    addTruth("RESEARCH TRUTH",autopilot.message||program.truth_policy||"Claims require cited evidence and review.");
    addTruth("CONNECTORS",Object.entries(autopilot.connectors||{}).map(([key,value])=>`${key}=${value}`).join(" · ")||"NOT CONNECTED");
    addTruth("BOUNDARY","JARVIS may research, plan, draft, code and test locally. Publishing, outreach, accounts, spending, contracts, filings and regulated decisions remain approval-gated.");
    replaceBoard("executiveBoard",truth,"No executive status yet.");
  }

  async function refresh(){
    text("ventureStatus","REFRESHING");
    try{render(await api("/api/company-os"))}catch(error){text("ventureStatus","DEGRADED");text("commandResult",error.message)}
  }

  async function execute(inputMode="typed",speechConfidence=null){
    const input=$("companyCommand");const command=String(input.value||"").trim();if(!command)return;
    text("commandResult","JARVIS is routing the supervised company mission…");$("executeCompany").disabled=true;
    try{
      const result=await api("/api/command",{
        method: "POST",
        body: JSON.stringify({
          ...(inputMode==="voice"?VOICE_COMMAND:TYPED_COMMAND),
          text: command,
          speech_confidence: speechConfidence,
          source: "company_terminal"
        })
      });
      text("commandResult",result.response||"Company mission processed.");input.value="";await refresh();
    }catch(error){text("commandResult",error.message)}finally{$("executeCompany").disabled=false}
  }

  async function refreshVoiceStatus(){
    try{
      const status=await api("/api/voice/owner-status");
      text("companyVoiceState",`VOICE · ${clean(status.mode||"DICTATION ONLY")}`);
      $("companyListen").disabled=!SpeechRecognition;
      $("companyListen").title=status.detail||"Browser dictation does not verify speaker identity.";
    }catch(error){
      text("companyVoiceState","VOICE · DEGRADED");
      $("companyListen").disabled=true;
    }
  }

  function listen(){
    if(!SpeechRecognition){
      text("commandResult","Voice dictation is unavailable in this browser. Type the company mission instead.");
      return;
    }
    if(recognition){recognition.abort();recognition=null;return}
    recognition=new SpeechRecognition();
    recognition.lang="en-IN";
    recognition.interimResults=false;
    recognition.maxAlternatives=1;
    text("companyVoiceState","VOICE · LISTENING");
    recognition.onresult=event=>{
      const result=event.results?.[0]?.[0];
      const transcript=String(result?.transcript||"").trim();
      if(transcript){$("companyCommand").value=transcript;execute("voice",Number(result.confidence)||null)}
    };
    recognition.onerror=event=>text("commandResult",`Voice dictation failed: ${event.error||"unknown error"}. Type the mission instead.`);
    recognition.onend=()=>{recognition=null;refreshVoiceStatus()};
    recognition.start();
  }

  $("refreshCompany").addEventListener("click",refresh);
  $("executeCompany").addEventListener("click",()=>execute("typed"));
  $("companyListen").addEventListener("click",listen);
  $("companyCommand").addEventListener("keydown",event=>{if(event.key==="Enter")execute("typed")});
  $("masterChat").addEventListener("click",()=>window.open("/?workspace=chat","_blank","noopener"));
  refresh();refreshVoiceStatus();window.setInterval(refresh,15000);
})();
