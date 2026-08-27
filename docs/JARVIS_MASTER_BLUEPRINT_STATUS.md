# JARVIS Master Blueprint Status

Last audited: 2026-08-28 01:30:15 (Asia/Kolkata)

Governing specification: `docs/JARVIS_MASTER_AUTONOMOUS_BLUEPRINT_FOR_CODEX.md`  
Verified SHA-256: `AED7D25B73DD4601EECD74A78EEF7B9492E77DB7123D28BB43E404D10CC7A725`

The repository copy is byte-for-byte identical to the blueprint supplied in `C:\Users\Soura\Downloads`.

## Current verdict

JARVIS is **not blueprint-complete**. The current checkout contains useful control-plane, agent, market-data, options-research, Nautilus-contract and persistent paper-desk foundations, but the full Definition of Done is not satisfied.

The machine-level baseline is also not release-ready:

- Branch: `jarvis-dev/20260827-022645-JARVIS-V6-terminal-x3-cinematic`
- HEAD: `69fbc1f45538981cc0632efb4d43cc1fcfd880a6`
- Working tree: dirty with the current verified repair patch plus an existing local Claude settings file; no release checkpoint has been created
- Declared primary: `.venv\Scripts\python.exe` (Python 3.12.13; application, NumPy and pandas imports verified)
- Declared FYERS data runtime: `.venv-fyers\Scripts\python.exe` (Python 3.12.13; FYERS, NumPy, pandas and adapter imports verified)
- Declared Nautilus runtime: `.venv-nautilus\Scripts\python.exe` (Python 3.12.13; Nautilus 1.231.0, backtest config, `msgspec`, NumPy and pandas worker boundary verified)
- Current services after the clean restart: exactly one listener each for Quant 8787, FYERS read-only bridge 8790, Nautilus 8792, Master 8797 and native voice control 8798
- FYERS runtime state: connected read-only with seven verified NSE/BSE/MCX stream snapshots after the network-enabled restart; broker-order APIs remain disabled
- Full regression: 1170/1170 tests pass using the declared `.venv\Scripts\python.exe`
- Live broker execution: locked; all new trading work remains paper/sandbox only

The machine-readable source of truth is `data/roadmap/jarvis_master_gap_map.json`.

## Immediate failure analysis

### Windows voice compiler lock

Root cause: the older regression compiled repeatedly to the fixed shared path `.jarvis-dev\JarvisVoiceService.test.exe`. A prior test process or file handle could retain that executable, so the next compiler invocation could not overwrite it on Windows.

Current working-tree fix: the compile regression creates a unique `.jarvis-dev\voice-compile-<random>\JarvisVoiceService.test.exe` inside a `TemporaryDirectory`. The production launcher now uses a source-hash-addressed executable under `.jarvis-dev\native-voice-runtime` as well, so a terminating Windows process can never lock the next build target. Two consecutive launcher runs verify compile/start followed by existing-process detection. The real Windows System.Speech compile still runs; the test is not skipped or weakened.

The legacy source-string regressions now verify the stronger behavior: voice calls `executeCommand(...)` directly and preserves `input_mode=voice` plus speech confidence for the server-side uncertainty guard. All focused voice tests and the full suite pass.

The live Windows recognizer advertised an installed entry that failed construction with `No recognizer of the required ID found`, which previously terminated the entire port-8798 service. Native voice now keeps its exclusive loopback control API online, reports `DEGRADED_BROWSER_FALLBACK` and exposes `recognition_available=false` instead of claiming recognition is ready. The launcher and reliability supervisor treat this as a healthy but degraded browser-speech fallback, avoiding restart loops. A compatible Windows speech recognizer still must be installed or repaired before native wake/stop recognition can report READY.

### Declared runtime contract repair

The three blueprint-declared Windows environments no longer trust `python.exe` existence. `omni/runtime_paths.py`, `JARVIS.bat` and `scripts/verify_runtime_contract.py` select and verify real module boundaries. The repaired Python 3.12 Nautilus environment initially exposed stale Python 3.13 NumPy and then `msgspec` binaries when the real research workers ran; the environment was synchronized from the verified pinned Nautilus runtime, and the contract was expanded to import `nautilus_trader.backtest.config`, NumPy and pandas. All 38 real research-kernel/universal/portfolio/walk-forward contract tests and the full 1170-test suite now pass. `omni/loopback_http.py` also supplies a Windows-exclusive threaded loopback server; Quant, FYERS, Nautilus, Master and voice services can no longer silently share one port with stale older processes. A network-enabled clean restart verified one listener on each of 8787/8790/8792/8797/8798.

`JARVIS_SERVICE_HEALTH_V1` now normalizes Master, Quant, FYERS, Nautilus and native voice health responses with service/version identity, READY/DEGRADED status, start/response timestamps, uptime, last success/error timing, dependency states and explicit paper-only/live-execution safety. This provides the contract required by the next owned-process recovery milestone.

### Canonical market data and venue sessions

`workstation/market_data_contract.py` now defines one provider-neutral `MarketDatum` contract with provider, provider symbol, exchange and received timestamps, timeframe, quality, stale, verified and freshness-basis fields. It also enumerates the complete blueprint market-event family and supplies a fail-closed venue service for NSE, BSE, MCX, continuous crypto and ungoverned global research feeds. `workstation/paper_market_data.py` emits this contract for successful quote/history paths and routes Paper session decisions through the shared service. A versioned 2026 exchange-calendar snapshot now cites official NSE, BSE and MCX sources, represents full and partial-session holidays, refuses pending Muhurat timings and fails closed outside its verified year. Remaining work is to automate reviewed calendar refreshes and migrate Deribit, option-chain, order-book, news and remaining legacy adapters.

The event family now has validated `MarketEventEnvelope` payload contracts and a bounded, failure-isolated `MarketEventBus`. Paper quote and completed-bar paths are real publishers and expose acceptance diagnostics. Invalid OHLC, option-chain and provider-health shapes fail before publication. Order-book, options/OI/volatility, news/provider-health and Nautilus publisher adapters remain incomplete.

### Unified feature and indicator foundation

Milestone B now has a reusable foundation rather than terminal-specific helper functions. `workstation/indicator_registry.py` defines the blueprint's 30 initial deterministic indicator plugins with versioned metadata, warmup, inputs, outputs and strict validation. `workstation/unified_feature_engine.py` adds explainable market structure, ranked support/resistance, supply/demand heuristics, liquidity/FVG evidence, candle/volatility state and prior session ranges. Context-dependent indicators fail closed unless their benchmark, breadth or options inputs are supplied. `quant_terminal_v2` now attaches this snapshot only to verified completed candles. Ten dedicated regressions and the full repository suite pass.

`workstation/multi_timeframe_feature_store.py` now retains only verified, fresh, completed-bar feature snapshots with provider/data-quality provenance, a deterministic payload hash, symbol/timeframe/bar/version deduplication and bounded per-series retention. Quant evidence writes to this store without weakening signal gates. The Windows regression verifies that every SQLite connection closes before temporary cleanup.

### Quant Ensemble V2 and specialist windows

Every active ensemble vote now resolves through `StrategyRegistry` and carries strategy version, required features, compatible regimes, regime weight, evidence and the paper-only execution boundary. Decisions include explicit opposing-vote contradictions and reasons not to trade; the multi-timeframe terminal preserves this graph per selected timeframe. New paper entries fail closed when the directional vote lacks a regime-compatible supporter or when registered strategy votes conflict. Entry risk now uses an explainable hybrid stop: nearby validated price structure plus an ATR buffer when structure is between 0.75R and 2.0R away, otherwise a 1.25 ATR fallback; position sizing is derived from that stop distance. The remaining ensemble gap is cross-market options/breadth/correlation/microstructure evidence, not strategy identity or traceability.

The V3 command API previously dropped the specialist `raw` payload and the browser only updated Master transcript. The API now preserves the safe payload. Route-owned browser rendering places Web/Research/News results and citation links in Web Intelligence, and Paper/Portfolio/Autonomy results in Paper Execution Desk. Remaining Mission/Evidence/System renderers keep Milestone I partial.

### Options Desk V2 foundation

`workstation/options_chain_analytics.py` now supplies one provider-neutral contract for descriptive chain analytics. The FYERS India adapter returns normalized contracts plus PCR, delta OI inputs, OI walls, descriptive max pain, ATM-straddle expected move, 25-delta skew when Greeks exist, expiry term structure, gamma concentration and explicit liquidity coverage. Missing OI, IV or Greeks are never inferred.

`workstation/defined_risk_options_paper_desk.py` adds a persistent atomic multi-leg paper book for exact same-expiry bull-call and bear-put debit verticals. Conservative buy-ask/sell-bid fills, complete Greeks/OI/volume, relative-spread liquidity, verified multiplier/currency, maximum-loss sizing, idempotency and a spread-count cap are mandatory; naked shorts cannot enter. `workstation/options_paper_autonomy.py` opens a spread only from fresh verified chain evidence, an open session and a contradiction-free underlying score of at least 80, otherwise recording the blocker. The spread desk now accepts only fresh verified marks, computes conservative close value, enforces bounded loss/profit exits and settles expiry only from an exact official settlement certificate. The Paper workspace renders both legs, maximum loss and options-autonomy telemetry. Provider polling, SENSEX verification, IV history/rank and morning-workflow wiring remain Milestone D gaps.

### Running paper workflow and exits

The most recent live workflow evidence completed all 71 discovery instruments across NIFTY50, BANKNIFTY, SENSEX30, India indices, MCX and crypto with zero scanner errors and produced 11 eligible daily watch candidates. Autonomy enrolled a bounded 21-symbol universe, but opened no new position in five observed cycles because none cleared the stricter intraday alignment, score, range, risk-level and session gates; it did not force a trade. One previously persisted paper position remained. Paper exits treat adverse stop gaps conservatively, fill resting targets at the target reference, support risk-reducing breakeven/trailing plus explicit time stops, and refuse stale or unverified marks. Partial scale-outs now quantize the exit amount itself, reject reductions below the authoritative quantity step and extend the protected runner target after the first target is filled instead of immediately flattening the remainder. Signal-reversal, regime and session-close policies remain.

### FYERS watchlist degradation and service ownership

The Quant watchlist blank state had two concrete causes: a disconnected FYERS socket could leave cached snapshots looking connected, and the fixed Indian instruments did not use the already-available read-only REST quote fallback. `quant_terminal_v2` now distinguishes CONNECTED from DEGRADED, rejects old stream snapshots as live, uses FYERS REST quotes for fixed and dynamic Indian instruments, labels fallback/stale provenance explicitly and hydrates every watch tile immediately instead of silently swallowing one request at a time. This changes data visibility only; live orders remain disabled. The same repair adds exclusive Windows loopback binding to every JARVIS service so a new process fails visibly instead of coexisting with stale listeners. A network-enabled clean restart proved one listener per active port and restored seven verified FYERS NSE/BSE/MCX stream snapshots with no bridge error.

Paper instrument accounting now fails closed for derivatives without an authoritative contract specification. MCX lot size, contract multiplier and tick size come from FYERS' public symbol master; crypto price and quantity grids come from Binance public exchange metadata. Synthetic P&L, exposure and stop risk use the verified contract multiplier and INR valuation multiplier. Fees and slippage remain zero only with an explicit `UNCONFIGURED` label; they are applied only when a named `ExecutionCostConfig` is supplied, so JARVIS does not invent venue charges.

The persistent desk now owns portfolio-level entry governance rather than trusting individual callers. It stores peak equity durably and enforces daily-loss, maximum-drawdown, symbol, asset-class, strategy, direction, configured correlation-cluster, gross-notional, stop-risk and position-count limits. Every valid mark updates MAE/MFE in valuation currency and R; closed trades retain those excursions and the exit reason. Autonomous desk rejections are counted in scanner telemetry. The live migrated account reports paper-only/live-execution-false, daily P&L about –₹777 against a ₹2,000 lock, 0.78% drawdown and no current entry lock. Statistical correlation remains explicitly `UNCONFIGURED` until a verified rolling-returns service supplies clusters.

### Paper Portfolio workspace

The V3 Paper window is no longer a static command placeholder. `/api/paper-portfolio` returns the persistent SQLite portfolio, closed-trade journal, event log and autonomy telemetry. Natural-language loss-review requests are routed to this durable desk before generic Quant routing and summarize IST today/yesterday results, exit reasons, regime compatibility, opposing votes, MAE/MFE and trailing activation from the exact displayed trades. The spatial browser workspace renders equity, P&L, gross exposure, stop risk, open positions, closed trades, contract/currency/cost provenance, scanner blockers and stale-mark diagnostics. A persisted 3D depth toggle adds perspective, a horizon grid and pointer-responsive window depth with reduced-motion support; “4D/5D” is not presented as a false web-platform capability. Live execution remains locked. Mission, Apps, Evidence and System workspaces still require the same route-owned depth before Milestone I can be called complete.

### Company Builder and venture research operating system

Company OS now converts a spoken idea into a durable supervised venture workspace rather than a generic chat answer. It creates a venture thesis, 18-task dependency graph, local four-page website prototype, brand and social/video draft library, approval register, hypothesis/falsification ledger, obstacle register and 30/90-day plus year-1/year-4/year-5 decision gates. `omni/venture_evidence_engine.py` runs eight domain research tracks plus a global opportunity-radar query, preserves URLs/provider/read status, labels retrieved text separately from search/discovery leads and records coverage gaps instead of inventing conclusions.

The visible 16-department mesh is also connected to real bounded execution. `omni/company_department_coordinator.py` dispatches every department through the canonical governed `AgentRegistry`, isolates individual failures, persists JSON/Markdown specialist packets and updates the Company workboard only to `LOCAL_BRIEF_READY`. It does not claim accounts, posts, outreach, contracts, filings, hiring, deployment, spending or production work occurred. Those actions require a connected sandbox/service and explicit review of the exact action. Live trading remains disabled.

`omni/company_action_queue.py` now creates durable, tamper-evident deployment, social, video and outreach packets. Approval is bound to the exact payload hash, unconfigured destinations and secret-bearing fields fail closed, revocation is durable, and even an approved packet can only yield a sandbox execution envelope—this module contains no external executor. `omni/opportunity_radar_scheduler.py` persists restart-safe due times for evidence refreshes. Every venture also receives machine-readable and human-readable executive reports separating prepared local work, required physical/professional work and actions that have not occurred.

The Master service was restarted and live-verified: HTTP 200, Company Builder markup present, `/api/company-os` reported 16 supervised agents, `external_actions=EXPLICIT_APPROVAL_REQUIRED`, and `live_trading=DISABLED`. Browser-level visual automation remains a test gap because the desktop browser plugin could not initialize its trusted service dependency; HTTP/API and rendering source contracts passed.

### Deterministic direct paper routing

The direct command router exists at `workstation/paper_trade_action_router.py` and currently proves:

- `take trade in bitcoin` routes to the Quant/Paper path
- split speech typo `bitcoi n` resolves conservatively to BTC
- plain `EXECUTE` returns a deterministic context-required response
- `open paper trading` remains Paper Desk navigation
- portfolio/P&L/risk queries remain Paper Desk requests
- an existing position blocks duplicate exposure
- no qualified setup arms monitoring rather than forcing a trade
- a qualified setup can open only a synthetic Paper Desk position

The deterministic direct-routing contract is now **PRESENT**. Exact 1m/5m/15m profiles are propagated through `requested_trading_profile`, `scan_payload` and `PaperAutonomyEngine`; autonomous fills also reuse the direct router's live-entry drift check. Broader position-management and market-microstructure gates remain Milestone E work rather than defects in the direct command contract.

### Why autonomous paper trading may show no position

The current strict gates can legitimately yield zero entries. A start command does not mean “force a trade.” A paper position should open only when verified data, market session, completed-bar evidence, strategy score, risk/reward, freshness, duplicate exposure and portfolio risk all qualify.

The loss-review command no longer falls through to an unrelated chart action: both V3.1 and legacy Master routers open Paper Desk and use the same persistent portfolio evidence. The autonomy engine also starts on boot in some configurations, so pressing Start again may produce no new work. Clearer already-running feedback remains a workflow gap; it does not justify bypassing entry gates.

Autonomy now exposes the latest scan latency, scanned/data-ok/session-open/qualified/opened funnel, provider failure counts, rejection histogram and normalized per-symbol blockers. The Paper workspace renders those fields alongside entry locks and mark-safety rejections, so an empty portfolio can be explained without weakening the entry gates. `paper_scan_history.sqlite3` adds bounded durable cycle/row evidence with profile, timeframes, providers and paper-only invariants. Bounded historical rates, latency, provider failures and blocker aggregation now feed a per-cycle data-health trend visualization in Paper Desk.

Automatic paper re-entry now uses versioned profile-specific cooldowns after a position closes: 2 minutes for 1m, 10 for 5m, 30 for 15m/intraday, 120 for 1h and one day for swing. The gate is scoped to symbol, strategy and profile, emits `REENTRY_COOLDOWN_ACTIVE`, remains visible in Paper telemetry, and does not restore the former one-trade-per-day defect.

## Status by roadmap milestone

| Milestone | Status | Evidence-backed summary |
|---|---|---|
| A — Stability/router | PRESENT (checkpoint blocked) | Voice content-addressed build fix and truthful degraded runtime, direct routing, exact timeframe policy, precedence, declared runtime contracts, exclusive loopback ownership, uniform service health contracts, focused safety gates and 1170 full regressions pass. The working tree is not checkpoint-ready. |
| B — Feature/structure | PARTIAL | A unified feature engine, ranked zones, liquidity heuristics and 30-plugin IndicatorRegistry are installed and tested. Persistent feature storage and broader cross-asset calibration remain. |
| C — Quant Ensemble V2 | PARTIAL | Every active vote is versioned and registry-backed with evidence/contradiction graphs and reasons-not-to-trade. Options, breadth, correlation and microstructure evidence remain. |
| D — Options Desk V2 | PARTIAL | India/Deribit research adapters, provider-neutral analytics, an atomic defined-risk spread book, lifecycle marks/expiry settlement and a governed chain-to-paper decision bridge exist. Provider polling, SENSEX verification, IV history/rank and workflow scheduling remain. |
| E — Autonomous Portfolio | PARTIAL | Persistent SQLite desk, exact timeframe policy, all-market scan/enrollment, live-entry validation, stale-mark certificates, verified contract accounting, daily/drawdown/concentration locks, MAE/MFE journal and bounded advanced exits exist. Evidence-derived correlations, options risk, remaining exits and venue scheduling are incomplete. |
| F — Nautilus integration | PRESENT | Pinned 1.231.0 service is live on 8792 and reports READY with paper-only/live-execution-false invariants. |
| G — Strategy Research Lab | PARTIAL | Mutation/crossover research candidates, backtest, edge validation, chronological OOS, walk-forward, sensitivity, cost stress, Monte Carlo and regime robustness foundations exist; no unified DSL-to-governed-promotion pipeline. No component guarantees win rate. |
| H — Mistake/self-improvement | PARTIAL | The current Paper Desk reviewer performs durable today/yesterday evidence review and only tightens bounded cohort policy; a research-only champion/challenger comparator exists. It cannot self-promote or rewrite production strategy. Sufficient statistically meaningful closed-trade evidence remains. |
| I — Professional UI | PARTIAL | Claude's V6 Terminal X/X2/X3 commits add a substantial cinematic visual layer to Master JARVIS, and Quant now has a spectral multicolour venue/state treatment plus immediate watch hydration. Web Intelligence receives route-owned results; Paper Execution has a live portfolio/journal/telemetry workspace; Company OS has a supervised venture/research/department workspace. The V6 JavaScript/CSS is currently additive and unusually large, so it still needs component refactoring and browser interaction coverage. Mission/apps/evidence/system renderers and several professional desks remain. |
| J — Shadow-live governance | MISSING | Requires completed paper milestones, sufficient evidence and explicit future approval. |

## Highest-priority dependency order

1. Finish the canonical market datum and venue/session contracts; verified Paper instrument accounting now exists.
2. Extend the existing versioned strategies/evidence graphs with breadth, correlation, options and microstructure evidence; the persistent multi-timeframe feature store is now installed.
3. Finish evidence-derived correlation lifecycle, options portfolio controls, remaining exit policies and venue scheduling; daily/drawdown/concentration gates and MAE/MFE are now implemented.
4. Connect FYERS/Deribit chain polling to the defined-risk options engine and finish spread expiry/mark/exit management.
5. Complete research, champion/challenger and professional UI workflows.

## Safety boundary

Real broker execution is out of scope and remains locked. No milestone in this program may request, print or persist secrets in reports. No result may fabricate candles, quotes, contracts, expiries, OI, IV, Greeks, prices or news. A paper command never overrides evidence or risk gates.

## Release gate

No checkpoint will be described as verified until all of the following are true for the allowlisted release patch:

1. touched Python compiles
2. touched JavaScript parses
3. exact user-command contracts pass
4. targeted and integration tests pass
5. trading safety tests pass
6. full regression passes
7. Protected Core import passes
8. `git diff --check` passes
9. repository release state is clean or the checkpoint cleanly isolates and preserves all pre-existing user changes
10. commit and push both succeed
