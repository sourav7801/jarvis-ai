# JARVIS V16 — Unified Autonomous Workstation + Quant Operating System

Status: **DEVELOPMENT BLUEPRINT — NOT VERIFIED / NOT A RELEASE**  
Verified parent: `JARVIS V15` at `51f5923d5d5af755537f3cf8b75e167feac113cf`

This document is the canonical target for V16. V16 is not another trading overlay.
It is the convergence release that turns the existing JARVIS intelligence,
missions, tools, memory, browser, computer-use and quant subsystems into one
coherent operating system.

## 1. Non-negotiable safety boundaries

The following boundaries are permanent and are release blockers if violated:

- Paper trading only.
- `live_execution = false`.
- `automatic_broker_order = false`.
- No broker place/modify/cancel/submit-order surface is added.
- Consequential external actions require an approval gate.
- Automatic production-strategy rewrite/deployment remains disabled.
- Exactly 29 permanent specialists, including the permanent `critic` specialist.
- System planes/services do not become permanent agents.
- No fabricated market data, dealer inventory, Greeks, instrument specs or prices.
- Dealer positioning is unavailable unless genuine dealer inventory is verified.
- Stale, missing or invalid required market data blocks new automatic entries.
- `INVALID_RISK_LEVELS` remains a hard blocker when valid geometry cannot be built.
- The protected V8 Master identity and verified V15 trading lineage are preserved.
- Unknown processes are never killed; recovery acts only on proven JARVIS-owned processes.

## 2. Product definition

JARVIS V16 is a personal AI operating system with a professional quant trading
subsystem. The user expresses an outcome; JARVIS determines the required tools,
agents, files, websites, applications, data sources and verification steps.

```text
USER
  |
  v
UNIVERSAL JARVIS INPUT (text / files / voice later)
  |
  v
HEAD / INTENT + MISSION PLANNER
  |
  +---- Research / Web / Browser
  +---- Files / Documents / Artifacts
  +---- Coding / Git / Computer
  +---- Company / Finance / Operations
  +---- Trading / Quant / Options
  |
  v
CANONICAL TOOL CONTRACT + APPROVAL GATE
  |
  v
EXECUTE -> OBSERVE -> VERIFY
  |
  v
ARTIFACT / ACTION / PAPER TRADE / ANSWER
  |
  v
MEMORY + AUDIT + PROJECT + MISSION STATE
```

The user should not need to know which agent or module to start.

## 3. Existing capabilities that V16 reuses

V16 must consolidate rather than rebuild working foundations. Existing verified
or mature components include:

- 29-agent registry and deterministic routing.
- Mission, mission queue/worker and persistent goal/task graph.
- Approval, action engine and audit infrastructure.
- Browser automation and governed web research.
- Computer operator / desktop automation components.
- Model provider/router and local Ollama support.
- Hybrid memory and project/workspace orchestration components.
- Coding/Git/GitHub tooling.
- Gmail/Calendar/Contacts integrations where configured.
- V14.1 risk geometry.
- V15 contextual market reasoning and portfolio-adjusted utility.
- Paper Desk, journal, Strategy Lab and portfolio controller.
- Distinct INTRADAY / SWING / INVESTMENT paper mandates.
- Option-chain analytics and read-only provider contracts.

A working capability must not be replaced with a placeholder merely to simplify
V16.

## 4. Canonical navigation and visual design

The final Master shell is intentionally simple:

```text
JARVIS

HOME

WORK
  Chat
  Research
  Files
  Office
  Coding

TRADING
  Intraday
  Swing
  Investment
  Options
  Strategy Lab
  Journal

COMPANY
  Command Center
  Projects
  Finance
  Product
  Operations

AUTOMATION
  Missions
  Scheduled Tasks
  Approvals

SYSTEM
  Memory
  Connections
  Agents
  Diagnostics
  Settings
```

The Home view is not a telemetry wall. It contains one primary input, file drop,
recent work, running missions and a compact system-health strip. Deep diagnostics
remain accessible but do not crowd normal work.

### Design rules

- Dark professional workstation aesthetic; avoid decorative clutter.
- Central content gets the largest area.
- One authoritative state per concept; no contradictory legacy panels.
- Progressive disclosure: advanced diagnostics expand on demand.
- Trading uses chart-first layouts.
- Status colors are semantic and accessible: healthy, warning, blocked, risk.
- Every blocking state includes a human-readable reason and next system action.
- Long-running operations never freeze navigation or chart interaction.

## 5. Universal managed Files service

V16 introduces a user-facing managed file system instead of arbitrary agent
filesystem access.

Required input formats:

- PDF, DOCX, XLSX/XLS, CSV, PPTX.
- TXT, Markdown, JSON, XML, HTML.
- JPG/PNG/WEBP/GIF.
- ZIP.
- Python, JavaScript/TypeScript, SQL, PowerShell and common source/log files.

Every uploaded file receives:

- stable `file_id`.
- original filename and verified extension/MIME metadata.
- SHA-256 identity.
- size and timestamps.
- workspace/project binding.
- parser status.
- bounded extracted text where supported.
- managed storage path unavailable to ordinary planner prompts.

The UI must support drag/drop, browse, list, search, preview, attach-to-project and
"Ask JARVIS" actions.

No OCR is silently performed; image OCR/vision is a separate explicit capability.

## 6. Artifact / Office engine

The Artifact Service must create and reopen-verify outputs before returning
success.

Supported deliverables:

- XLSX / CSV.
- DOCX.
- PPTX.
- PDF.
- Markdown / text / JSON.

### Spreadsheet requirements

The spreadsheet engine eventually supports:

- Create and edit workbooks.
- Multiple sheets.
- Formulas.
- Formatting and tables.
- Conditional formatting.
- Filters and freeze panes.
- Data validation and named ranges.
- Charts.
- Pivot-style summaries where supported.
- Data cleaning, joins, lookups and transformations.
- Financial models, scenarios and sensitivity analysis.
- Dashboard sheets.
- Reopen verification of formulas/sheets/charts structure.

The final acceptance test is not "an XLSX file exists". JARVIS must reopen the
workbook and validate the requested sheets, formulas and structural artifacts.

## 7. Internet and Browser architecture

There are three levels:

1. **Search** — find public sources and return metadata.
2. **Research** — open multiple sources, extract evidence, cross-check and cite.
3. **Browser automation** — navigate JavaScript-heavy sites, click, type, upload,
   download and inspect rendered pages.

Preferred execution hierarchy:

```text
DIRECT API
  -> native tool/CLI
  -> governed HTTP
  -> browser automation
  -> GUI computer control (last resort)
```

Public reads may run automatically. Sending, submitting, purchasing, publishing
or other consequential external effects are approval gated.

## 8. Canonical tool protocol

All V16 capabilities expose one serializable contract:

```text
name
capability
risk class
input schema
output schema
timeout
idempotency
approval requirement
source/tags
```

Tool families include:

- `file.*`
- `artifact.*`
- `web.*`
- `browser.*`
- `computer.*`
- `spreadsheet.*`
- `document.*`
- `slides.*`
- `pdf.*`
- `code.*`
- `git.*`
- `email.*`
- `calendar.*`
- `workspace.*`
- `memory.*`
- `automation.*`
- `market.*`
- `trading.*`
- `system.*`

A model does not receive secrets or raw Python callables. It receives tool
metadata and governed execution handles.

## 9. Missions and persistent execution

Complex work becomes a persistent mission instead of one giant chat call.

Canonical states:

- PLANNED
- READY
- RUNNING
- WAITING_TOOL
- WAITING_DATA
- WAITING_APPROVAL
- BLOCKED
- VERIFYING
- COMPLETED
- FAILED
- CANCELLED

Mission checkpoints persist. Restart recovery reconciles state and resumes only
idempotent/safe work. Consequential steps cannot be replayed without appropriate
approval/idempotency evidence.

Projects bind chat context, files, missions, artifacts, decisions and memory.

## 10. Verification plane

Every important workflow uses:

```text
PLAN -> EXECUTE -> OBSERVE -> VERIFY
```

Examples:

- XLSX: create -> reopen -> inspect sheets/formulas -> verified.
- Research: claim -> source -> cross-check -> citation.
- Coding: branch -> edit -> compile/test -> diff review.
- Trading: opportunity -> risk -> paper execution -> portfolio/journal reconcile.

No success is reported only because a subprocess returned zero.

## 11. Data platform and provider governance

Agents must not independently hit FYERS or other providers.

Target architecture:

```text
FYERS / CRYPTO / OTHER READ-ONLY DATA SOURCES
              |
              v
       MARKET DATA GATEWAY
       - provider governor
       - request queue
       - rate budget
       - deduplication
       - completed-bar cache
       - instrument mapping
       - timestamp/session validation
       - health state
              |
              v
          DATA BUS
        /     |      \
     Chart  Strategy  Options
```

Provider states must remain distinct:

- READY
- RATE_LIMITED
- LOGIN_REQUIRED
- TOKEN_INVALID
- PERMISSION_REQUIRED
- CREDENTIAL_MISMATCH
- REQUEST_REJECTED
- STALE
- NO_DATA
- PROVIDER_ERROR

A FYERS HTTP/provider 429 is a rate-limit state, not an expired-token guess.
Backoff is bounded and shared across isolated workers. Recent completed-history
cache may be served only within explicitly valid freshness limits and is never
synthetic market data.

## 12. Trading workspaces

V16 preserves three distinct paper ledgers:

### Intraday

- Live market scanning.
- 5m / 10m / 15m and adaptive intraday reasoning.
- Active setups.
- Execution and position management.
- Session risk and daily performance.
- Options expression when enabled and verified.

### Swing

- 1h / 4h / daily multi-day setups.
- Overnight paper positions.
- Swing strategy state.
- Alerts and trade-management plans.
- Independent allocation/risk ledger.

### Investment

- Daily+ research.
- LONG ONLY automatic paper mandate.
- Portfolio holdings/allocation.
- Thesis and valuation state.
- Independent investment allocation ledger.

Default top-level allocation remains configurable around 50/30/20, but capital
must have one canonical reservation/commitment ledger so no rupee is counted or
committed twice.

## 13. Professional quant terminal UI

The chart is the center of the trading experience. Surround it with watchlist,
active setups, positions, risk and compact reasoning.

For every proposed/executed trade display:

- Entry.
- Stop/invalidation.
- Targets.
- Quantity/lot size.
- Capital allocated.
- Capital at risk.
- Risk/reward.
- EV/utility evidence.
- Main blockers/warnings.

### Chart overlays

Long:

- target/profit zone above entry: green shaded area.
- stop/loss zone below entry: red shaded area.

Short:

- stop/loss zone above entry: red shaded area.
- target/profit zone below entry: green shaded area.

Proposed setup uses dashed/semi-transparent graphics. Executed paper position uses
solid/stronger graphics. Entry/exit markers and journal records derive from the
same canonical Paper Desk state; the frontend never invents levels.

## 14. Automatic intraday paper workflow

One session action starts the complete loop:

```text
VALID MARKET DATA
  -> DISCOVERY
  -> STRATEGY EVIDENCE
  -> MARKET BELIEF
  -> RISK GEOMETRY
  -> CONTEXTUAL EV
  -> PORTFOLIO UTILITY
  -> CAPITAL / RISK SIZE
  -> PAPER DESK
  -> POSITION MANAGER
  -> EXIT
  -> JOURNAL
  -> CAUSAL REVIEW / LEARNING
```

Strategies are features/voters, not independent order engines. Multiple strategy
signals for the same opportunity converge into one canonical opportunity and one
Paper Desk action, preventing duplicate/conflicting orders.

If no trade is eligible, JARVIS stays idle and exposes the exact reason.

## 15. Dynamic capital and risk

Confidence is not treated as a proven win probability.

Position risk derives from:

```text
base risk
x expected-value quality
x evidence/data quality
x regime fit
x historical calibration
x liquidity
x volatility
x correlation/concentration factor
x portfolio/workspace capacity
```

Then hard caps apply:

- risk per trade.
- total open risk.
- daily loss.
- simultaneous positions.
- symbol/sector concentration.
- workspace allocation.
- verified quantity/lot/tick constraints.
- margin/cash requirements.
- fees/spread/slippage assumptions.

The UI explains the sizing waterfall. Capital allocated and capital at risk are
separate quantities.

## 16. Options intelligence

Options are a first-class expression layer but remain read-only-data + paper
execution.

```text
UNDERLYING V15/V16 BELIEF
  -> verified option chain
  -> expiry selection
  -> strike selection
  -> bid/ask + liquidity
  -> OI / OI change / volume
  -> IV / verified Greeks where available
  -> option-specific economics
  -> premium risk plan
  -> verified instrument lot/tick
  -> PAPER LONG-PREMIUM POSITION
```

A bullish/bearish underlying view never forces an option trade. Poor spread,
unverified specs, invalid/expired contracts, adverse theta/IV economics or
non-positive option EV can result in `NO_OPTION_TRADE`.

Naked option selling remains disabled. Dealer positioning remains unavailable
without verified dealer inventory.

## 17. Strategy Lab and learning

Strategy Lab retains:

- historical backtests.
- parameter sweeps.
- walk-forward/out-of-sample tests.
- regime breakdowns.
- Monte Carlo where supported.
- expectancy / R distribution / drawdown / Sharpe / Sortino / profit factor.

Governance states:

- RESEARCH
- CANDIDATE
- APPROVED_PAPER
- CHAMPION_PAPER

Learning may update empirical statistics, calibration and bounded priors. It may
recommend strategy changes, but may not automatically rewrite/deploy production
or live strategies.

## 18. Performance and resource architecture

Long-lived services are bounded:

- Core/control plane.
- Market-data service.
- Quant workers.
- Artifact workers.
- Browser service.
- Model workers.

No unbounded process spawning. Heavy backtests and artifact jobs run off the UI
thread. Shared indicator calculations are cached by symbol + timeframe + completed
candle timestamp.

Priority under load:

1. Existing position/risk management.
2. Market data.
3. Paper execution.
4. UI responsiveness.
5. Direct user command.
6. Research/artifacts.
7. Background learning.

## 19. Reliability and health

V16 must recover from:

- provider 429/disconnect.
- internet loss.
- model outage.
- browser crash.
- worker crash.
- UI reload.
- Windows sleep/restart.
- duplicate launcher attempts.

Persistent state includes missions, paper positions, journal, allocations,
provider health, approvals and project/file metadata.

Health Center exposes real state without crowding normal UI:

```text
Core          HEALTHY
Market Data   HEALTHY / RATE_LIMITED / ...
Paper Desk    HEALTHY
Browser       HEALTHY
Models        provider state
Memory        HEALTHY
Mission Queue active/waiting
```

## 20. V16 internal delivery milestones

V16 remains one development branch and one final release candidate.

### A — Core OS convergence

- Canonical tool contract.
- Existing action/approval/audit adaptation.
- Mission and workspace bindings.
- Health/recovery hardening.

### B — Universal Workstation

- Managed file upload/index/search.
- Files UI.
- Verified artifact engine.
- Office/Coding/Browser/Computer tool registration.
- Project workspace UI.

### C — Data Platform

- Shared market-data gateway.
- FYERS governor/cache/provider states.
- Crypto/read-only provider integration.
- Instrument master and shared computation cache.

### D — Quant Terminal

- Intraday/Swing/Investment UX separation.
- Canonical capital ledgers.
- Chart overlays.
- Complete automatic paper loop.
- Options execution-intelligence migration.

### E — Intelligence convergence

- V15 beliefs/hypotheses/utility.
- Strategy ensemble.
- causal review/journal learning.
- Strategy Lab governance.

### F — Product completion

- Home/navigation cleanup.
- Connections/settings.
- Automation/schedules.
- Voice integration against the same universal command path.
- Installer/migration/docs.
- Full cross-generation and end-to-end acceptance suite.

## 21. Final acceptance gates

V16 is not complete until all of the following have reproducible proof.

### Universal workstation

- Upload PDF -> searchable/previewable -> summarize path available.
- Upload XLSX -> inspect/edit -> valid verified XLSX output.
- Instruction -> create verified XLSX.
- Instruction -> create verified DOCX/PPTX/PDF.
- Public web search/research -> cited output.
- Browser task -> controlled completion.
- File search -> correct managed file.
- Coding task -> safety branch/edit/test/diff.
- Mission -> restart -> safe resume.

### Trading

- Provider connect/data quality validation.
- Scan -> valid setup -> risk geometry -> positive EV/utility.
- Dynamic size -> Paper Desk acceptance.
- Chart overlay matches canonical position.
- Position management -> exit.
- Journal and portfolio reconcile exactly.
- Options path can select or correctly reject a verified contract.

### Failure scenarios

- FYERS 429.
- stale/missing data.
- provider disconnect.
- model unavailable.
- duplicate launcher.
- worker crash.
- invalid risk levels.
- insufficient capital.
- unverified instrument spec.
- restart with open paper position.
- consequential action without approval.

### Regression and safety

- Entire historical test suite passes.
- V16 targeted tests pass.
- protected-core verification passes.
- exactly 29 agents including `critic`.
- no live broker order API surface.
- no fabricated market data.
- clean working tree after verification.
- Windows runtime HTTP/UI acceptance checks pass.

## 22. Completion experience

The intended daily workflow is:

1. Run `JARVIS.bat` once.
2. Master opens and shows compact system health.
3. Ask JARVIS for ordinary work, upload files or open a project.
4. Open Intraday/Swing/Investment/Options only when needed.
5. Start a paper session once; scanning, reasoning, sizing, paper execution,
   management and journal operate automatically.
6. Continue unrelated research/office/coding work while trading services run in
   bounded background workers.

The user should interact with outcomes, not plumbing.

---

**Release rule:** Until the final installer, full regression and Windows runtime
checks pass, V16 remains a development candidate and V15 stays the recovery floor.
