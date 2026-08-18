# OMNI-JARVIS Blueprint Alignment

This document distinguishes implemented capabilities from target-state ideas.
It is intentionally conservative: a prototype or placeholder is not marked as
production-ready.

| Blueprint domain | Current alignment | Canonical implementation | Principal gap |
|---|---|---|---|
| Global orchestrator | Durable bounded workers plus manager-owned missions | `main.py`, `omni/mission_control.py`, `omni/`, `agents/head_agent.py` | Distributed workers and external queue |
| Dynamic model router | Local provider foundation | profile router and Ollama adapter in `omni/` | Calibrated quality metrics and optional cloud plugins |
| Specialized agents | 22 bounded agents registered | `omni/agent_registry.py`, `agents/company_department_agent.py`, `agents/` | Add selected external connectors and deeper domain evaluations |
| Company operating system | Governed local foundation | `omni/company_os.py`, Company OS workstation page | External legal, banking, CRM, and deployment actions remain approval-gated integrations |
| Computer control | Early | `tools/computer.py` | Cross-platform adapters and visual verification |
| Web intelligence | Governed public-web search/read foundation | `agents/web_intelligence_agent.py`, `omni/web_research.py`, Web Intelligence page | Optional authorized interactive-browser adapter and premium indexes |
| Research agent | Provenance foundation | `omni/web_research.py`, `agents/research_agent.py` | Credibility calibration and academic connectors |
| Coding agent | Early | `agents/coding_agent.py` | AST index, isolated test loop, patch governance |
| Trading engine | Read-only FYERS plus multi-timeframe intelligence | `workstation/trading_intelligence.py`, `trading/research/`, `agents/trading_core/`, `agents/fyers_*` | Additional licensed providers, walk-forward suite, audited paper reconciliation |
| Universal memory | Hybrid foundation | JSON compatibility, Chroma, SQLite FTS/episodic audit, semantic fusion interface | Production embedding adapter and retention policy |
| Mission Control | Governed local foundation | `omni/mission_control.py`, Mission Control workstation page | Background queue, resumable long-running remote jobs, and approved connector execution |
| 3D dashboard | Voice-first 3D master, mission graph, and department mesh | `workstation/app.py`, V7 static UI | Streaming execution traces and interactive approval controls |
| Runtime control plane | Authenticated System Core with static agent manifests, tool policy, runtime posture, mission health, and secret-free audit trace | `omni/control_plane.py`, `/api/control-plane`, System Core page | Interactive approval decisions, remote worker health, and production metrics export |
| Safety and verification | Governed foundation | schemas, capabilities, one-time approvals, SQLite audit, subprocess boundary | Interactive approval UI and OS/container isolation |

## Architectural invariants

1. Live trading remains disabled until an independently reviewed execution
   service, broker reconciliation, circuit breakers, and explicit human
   authorization exist.
2. HIGH and CRITICAL actions fail closed.
3. Agents do not bypass the tool registry or validation layer for state-changing
   operations.
4. Generated output, credentials, tokens, vector stores, and runtime state do
   not belong in source control.
5. Every new capability requires deterministic tests and observable outcomes.
6. “Autonomous company” means local planning, drafting, building, and testing;
   it never implies silent authority to incorporate, spend, contact people,
   sign, publish, hire, deploy sensitive systems, or move funds.

## Delivery sequence

### Phase 1 — Stabilize the foundation

- Declare canonical files and preserve old generations as historical material.
- Rebuild the broken virtual environment from reproducible metadata.
- Establish Git, CI, smoke tests, configuration, risk policy, and audit events.
- Connect existing department routes, including trading.

### Phase 2 — Durable orchestration and memory

- Introduce typed task, plan, step, result, and event contracts.
- Persist task DAG state and support bounded retries and cancellation.
- Add SQLite episodic/audit storage and combine lexical and vector retrieval.
- Add provider-neutral model routing with latency and quality telemetry.

### Phase 3 — Governed execution services

- Move filesystem, browser, coding, and research operations behind isolated
  adapters with explicit capabilities.
- Add preconditions and postconditions to every state-changing operation.
- Introduce an interactive approval service for HIGH-risk operations.

### Phase 4 — Unified workstation

- Replace competing workstation versions with one API and frontend.
- Stream task, agent, model, memory, system, and market telemetry.
- Integrate voice and permission prompts without hiding execution status.

### Phase 5 — Trading research hardening

- Normalize live and historical market data with provenance and timestamps.
- Add deterministic replay, slippage, fees, walk-forward validation, and paper
  reconciliation.
- Implement portfolio-wide exposure limits and kill switches in simulation.
- Keep live execution outside scope until an explicit separate review.

### Phase 6 — Company OS and voice-first master surface

- Register specialist strategy, product, engineering, data/AI, design,
  security, legal/compliance, finance, operations, marketing, sales, customer
  success, people, and quality/risk agents.
- Turn a spoken idea into a durable venture thesis, 30/60/90 roadmap,
  dependency-aware task graph, and local operating packet.
- Show consequential tasks as locked approval gates.
- Add one-click always-listening wake-word voice routing across separate tabs.
- Upgrade Quant Lab to explain actual 5m/15m/1h FYERS evidence.

### Phase 7 — Multi-agent Mission Control

- Route explicit outcomes through one manager that owns the final packet.
- Select relevant specialists and execute their bounded local analysis concurrently.
- Apply a separate critic for workflow coverage and visible degradation.
- Persist the task graph, audit trace, specialist outputs, execution plan, and
  approval register as a local mission workspace.
- Keep external communications, spending, accounts, legal actions, production
  deployment, live trading, and movement of funds locked for fresh approval.

### Phase 8 — Universal Operator and Web Intelligence

- Add a generalist operator that turns explicit end-to-end outcomes into
  supervised Mission Control runs.
- Add keyless public discovery plus optional sanctioned broad web search.
- Read explicit public URLs with SSRF protection, redirect revalidation,
  bounded extraction, checksums, provenance, and citations.
- Keep authentication, CAPTCHAs, private networks, paywalls, and restricted
  interactive actions outside silent automation.

## Excluded claims

CAPTCHA bypass, stealth/fingerprint evasion, unauthorized restricted-site
scraping, and unrestricted dark-web access are not implementation goals. Browser
and research capabilities must comply with authorization, site rules, privacy,
and applicable law.
