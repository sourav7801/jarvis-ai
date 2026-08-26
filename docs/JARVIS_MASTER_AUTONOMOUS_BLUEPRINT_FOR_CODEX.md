# JARVIS MASTER AUTONOMOUS BLUEPRINT FOR CODEX

## 1. Mission

Build JARVIS into a local-first AI operating system and quantitative intelligence platform that can reason, plan, use tools, collaborate across specialized agents, remember context, analyze markets deeply, autonomously paper-trade qualified opportunities, manage risk, review mistakes, generate better strategy hypotheses, validate them statistically, and improve through governed promotion.

JARVIS is not a chatbot with indicators. It is an AI control plane over deterministic tools, market-data services, a quant research stack, NautilusTrader infrastructure, a persistent portfolio, and a self-improvement research loop.

Core loop:

`Perception -> Context -> Reasoning -> Planning -> Agent/Tool Execution -> Verification -> Memory -> Evaluation -> Improvement`

Trading loop:

`Verified data -> Structure/features -> Regime -> Strategy ensemble -> Risk -> Paper execution -> Position management -> Exit -> Journal -> Mistake attribution -> Hypothesis -> Backtest -> Walk-forward/OOS -> Champion/Challenger -> Controlled promotion`

Until a future explicitly approved governance milestone, all trading execution must remain PAPER/SANDBOX only and real broker order surfaces must remain absent/locked.

---

## 2. Current repository and operating contract

Repository: `C:\Jarvis`

Primary Python: `C:\Jarvis\.venv\Scripts\python.exe`

Nautilus Python: `C:\Jarvis\.venv-nautilus\Scripts\python.exe`

FYERS data Python: `C:\Jarvis\.venv-fyers\Scripts\python.exe`

Windows 11 / PowerShell.

Current proven major checkpoint before new work:

- Quant V5 Nautilus Core
- proven HEAD: `5bd7b64`
- branch lineage: `jarvis-dev/20260820-011315-JARVIS-Quant-Trading-Intelligence-V5-Nautilus-Core`
- NautilusTrader version contract: `1.231.0`
- ports:
  - 8787 Trading Terminal
  - 8790 FYERS read-only bridge
  - 8792 Nautilus Quant Core
  - 8797 Master JARVIS

Recent V5.4.1 work proved direct-trade routing and paper-desk precedence in targeted tests, but full regression rolled back because the voice compile test could not overwrite `.jarvis-dev\JarvisVoiceService.test.exe` due to a Windows file lock. Fix this as infrastructure, not by skipping the test.

---

## 3. Codex autonomy rules

Codex is the implementation agent. It should act autonomously on routine engineering work.

Rules:

1. Inspect before editing.
2. Prefer architectural fixes over one-off regex/phrase patches.
3. Do not ask for approval for normal refactors, tests, safety branches, commits, pushes, or generated documentation.
4. Stop/ask only for credentials, destructive operations, live broker execution, or protected-core governance exceptions.
5. Never ask the user to paste secrets into chat.
6. Never fabricate live data, candles, options contracts, expiries, OI, IV, Greeks, quotes, or news.
7. Never enable live broker execution.
8. Preserve rollback at all times.
9. Use safety branches.
10. Never use broad destructive cleanup like `git clean -fd`.
11. Remove only temporary files created by the current patch.
12. Terminal/test output is authoritative.
13. Do not mark a milestone installed until required tests pass.
14. Never weaken a valid regression merely to make the suite green.
15. Fix source/environment contracts when tests reveal real incompatibilities.
16. If a failure is a true infrastructure flake, fix the infrastructure and preserve the test.
17. Every release ends with targeted tests, safety tests, full regression, Protected Core import, clean tree, commit and push.

---

## 4. Master JARVIS control plane

Master JARVIS owns:

- natural-language understanding
- intent routing
- planning
- multi-agent orchestration
- tool execution
- desktop/computer control
- missions
- memory
- approvals
- voice
- notifications
- status/health
- failure recovery
- explanations

It should not embed strategy calculations directly. Market reasoning should be delegated to trading/quant domain services.

Natural-language operational intents must map to deterministic domain actions whenever possible.

---

## 5. Agent architecture

Maintain specialized agents with capability gates, including:

- Head/Planner Agent
- Trading Agent
- Quant Research Agent
- Risk Agent
- Portfolio Agent
- Options Agent
- Market Structure Agent
- Data Agent
- News/Macro Agent
- Backtest Agent
- Strategy Research Agent
- Strategy Validation Agent
- Mistake/Performance Analyst
- Engineering Agent
- Security Agent
- Coding Agent
- Web Intelligence Agent
- Finance Agent
- Operations Agent
- Product Agent
- Memory Agent
- Voice Agent
- System/Computer Agent

Agents collaborate through explicit capabilities and return one synthesized result rather than conflicting independent answers.

---

## 6. Memory and governed self-improvement

Memory classes:

- conversation
- preferences
- decisions
- projects
- agent findings
- strategy research
- trade journal
- market observations
- failure/incidents
- system health
- performance metrics

JARVIS must never change production strategy logic because of one losing trade.

Improvement process:

1. detect recurring failure patterns
2. classify root cause
3. create a research hypothesis
4. generate a challenger strategy/parameterization
5. backtest
6. validate out-of-sample
7. walk-forward test
8. include fees/slippage
9. robustness/Monte Carlo/bootstrap
10. compare against champion
11. deploy challenger to paper only
12. collect sufficient sample
13. promote only through explicit statistical gates

---

## 7. Market structure intelligence

Build a reusable feature engine supporting:

- swing highs/lows
- HH/HL/LH/LL
- BOS
- CHOCH
- internal/external structure
- trend shifts
- range/consolidation
- breakout / failed breakout / retest
- displacement
- compression / expansion
- gaps/imbalances
- candle anatomy
- wick rejection
- close-location strength
- multi-candle sequences
- previous day/week/session highs/lows
- opening range

All outputs must be deterministic, testable and explainable.

---

## 8. Support/resistance and supply/demand

Support/resistance must not be only rolling min/max.

Rank zones using:

- touches
- recency
- reaction magnitude
- volume
- rejection quality
- time spent
- breakout/retest history
- role reversal
- multi-timeframe confluence
- ATR-normalized distance
- nearby liquidity

Return zone bounds, strength score, timeframe, invalidation, reactions and evidence.

Supply/demand engine should detect:

- rally-base-rally
- drop-base-drop
- rally-base-drop
- drop-base-rally
- fresh vs tested zones
- proximal/distal bounds
- mitigation
- imbalance/displacement
- invalidation
- quality score

---

## 9. Liquidity and structure heuristics

Required:

- equal highs/lows
- liquidity pools
- stop sweeps
- failed auction/rejection
- FVGs
- imbalance
- mitigation
- premium/discount range
- order-block style heuristics
- anchored VWAP
- VWAP bands

Never claim to identify actual institutions from price action. OI, volume and liquidity are activity proxies, not identity.

---

## 10. Chart pattern engine

Programmatic patterns:

- double/triple top/bottom
- head and shoulders / inverse
- triangles
- wedges
- flags
- pennants
- channels
- rectangles
- engulfing
- pin bars
- hammer/shooting star
- inside/outside bars
- morning/evening star
- range expansion
- exhaustion
- failed breakout

Each pattern exposes deterministic definition, quality score, invalidation, target method, context filters and timeframe.

---

## 11. Extensible indicator registry

Do not hardcode a small indicator list into strategies.

Create an `IndicatorPlugin` registry containing:

- name/version
- parameters
- input requirements
- output series
- warmup
- normalization
- timeframe compatibility
- visualization metadata
- tests

Initial library:

- SMA / EMA / WMA / HMA
- VWAP / Anchored VWAP
- RSI / Stochastic RSI
- MACD
- ADX/DMI
- ATR
- Bollinger Bands
- Keltner
- Supertrend
- Donchian
- Ichimoku
- CCI
- MFI
- ROC
- OBV
- CMF
- relative volume
- volume-profile approximations
- z-score
- realized/historical volatility
- Parkinson volatility
- regression slope
- correlation/beta
- breadth measures
- options/OI-derived features

Proprietary indicators such as Premium Lock must be plugins only after the exact formula, Pine code or algorithm is supplied. Never invent their formula.

---

## 12. Options and derivatives intelligence

India:

- NIFTY
- BANKNIFTY
- SENSEX only after verified BSE mapping
- verified provider contracts only

Crypto:

- BTC
- ETH
- SOL where relevant
- Deribit BTC/ETH options

Required options intelligence:

- chain
- expiry selector
- CE/PE
- spot
- strike map
- OI
- delta OI
- volume
- bid/ask/spread
- IV
- IV history/rank where available
- skew
- term structure
- Greeks
- PCR
- strike concentration / OI walls
- max pain as descriptive only
- expected move
- liquidity quality
- gamma concentration
- premium decay
- directional option candidate selection

Never hand-build stale option symbols. Resolve current contracts/expiries from providers.

No naked option selling. Defined-risk spreads remain PAPER only.

---

## 13. Data architecture

Sources:

- FYERS read-only for India
- Binance for crypto
- Deribit for crypto options
- future providers via adapters

Every market datum carries:

- provider
- provider symbol
- exchange timestamp if available
- received timestamp
- timeframe
- quality flag
- stale flag
- verified status

Unified events:

- trade tick
- quote tick
- bar
- order-book snapshot/delta
- option-chain snapshot
- Greeks update
- OI update
- volatility update
- news/macro event
- provider-health event

No fake data.

---

## 14. NautilusTrader role

Nautilus is infrastructure, not the intelligence layer.

Dedicated service: `127.0.0.1:8792`

Pinned version: `nautilus_trader==1.231.0`

Use Nautilus for:

- event-driven core
- message bus
- market state
- deterministic backtesting
- sandbox/paper execution
- portfolio/order state
- risk primitives
- instrument metadata
- native exchange adapters
- reusable backtest/live semantics where practical

JARVIS still owns AI reasoning, feature engineering, strategy research, learning, explanations, terminal, voice, memory and intent.

Never silently downgrade Nautilus.

---

## 15. Strategy registry and ensemble

Do not search for one universal “best strategy.”

Strategy families:

- trend following
- EMA trend
- momentum
- VWAP momentum
- ORB
- Donchian breakout
- volatility breakout
- mean reversion
- RSI/VWAP reversion
- Bollinger reversion
- z-score reversion
- pullback
- support/resistance reaction
- supply/demand reaction
- FVG continuation
- liquidity sweep reversal
- BOS continuation
- CHOCH reversal
- relative-volume expansion
- compression/expansion
- options momentum
- OI/delta-OI structure
- IV/skew strategies
- directional option selection
- defined-risk spread research

Each strategy exposes:

- id/version
- family
- required features
- entry
- invalidation
- stop
- target
- sizing hint
- regime compatibility
- expected hold
- cost assumptions
- explainable evidence

---

## 16. Regime engine

At least:

- strong trend
- weak trend
- range
- breakout
- high volatility
- low volatility/compression
- abnormal/event-driven
- illiquid/unsafe
- risk-on/risk-off where supported

Regime is per market and timeframe.

Strategy weights depend on market, timeframe, regime, volatility, liquidity, session and instrument type.

---

## 17. Decision engine

Final decisions synthesize:

- structure
- support/resistance
- supply/demand
- chart patterns
- indicators
- volume
- volatility
- multi-timeframe alignment
- options/OI evidence
- breadth/correlation
- regime
- strategy votes
- liquidity
- current portfolio exposure
- stale-data checks

Output:

- WAIT/LONG/SHORT
- score (not fake probability)
- evidence
- contradictions
- entry zone
- invalidation
- stop
- target(s)
- RR
- expected holding horizon
- regime
- contributing strategies
- reasons not to trade
- data quality

---

## 18. Autonomous paper trading

Universe initially:

- NIFTY
- BANKNIFTY
- SENSEX
- CRUDEOIL
- GOLD
- SILVER
- NATURALGAS
- BTC
- ETH
- SOL

Core timeframes initially: 5m, 15m, 1h.

Two loops:

### Strategy loop
Run on completed bars/meaningful events. Avoid recalculating every strategy on every tick.

### Risk/position loop
Run frequently from live marks.

Responsibilities:

- continuous opportunity scan
- duplicate-exposure prevention
- stale-data rejection
- portfolio risk gate
- live entry-drift validation
- sizing
- stop/target
- trailing framework
- partial-exit framework
- time stop
- regime-change exit
- invalidation exit
- P&L
- MAE/MFE
- journal

When the user says “take trade,” JARVIS must not force a trade. It should enter only if evidence and risk gates qualify; otherwise keep monitoring/arm autonomous paper scanning.

---

## 19. Persistent portfolio/risk engine

Track:

- equity/cash
- realized P&L
- unrealized P&L
- gross exposure
- net exposure
- risk at stops
- per-position risk
- portfolio risk %
- open positions
- asset-class exposure
- direction exposure
- strategy exposure
- correlation clusters
- drawdown
- daily P&L

Risk controls:

- max risk/trade
- max portfolio risk
- max positions
- max symbol exposure
- max correlated exposure
- max gross notional
- daily loss lock
- stale-data lock
- provider-unavailable lock
- malformed-contract lock
- option premium cap
- no naked shorts
- no live order API

---

## 20. Strategy Research Lab

JARVIS may generate new candidate strategies, but never deploy them directly.

Pipeline:

1. hypothesis
2. feature definition
3. strategy spec/DSL
4. compile
5. historical validation
6. backtest
7. fees/slippage
8. walk-forward
9. out-of-sample
10. Monte Carlo/bootstrap
11. regime breakdown
12. sensitivity analysis
13. minimum trade count
14. champion comparison
15. paper challenger
16. shadow validation
17. governed promotion

Metrics:

- expectancy
- profit factor
- max drawdown
- Sharpe
- Sortino
- Calmar
- avg/median R
- win rate
- payoff ratio
- MAE/MFE
- turnover
- exposure
- trade count
- tail losses
- regime-specific performance
- OOS degradation
- parameter stability
- slippage/cost sensitivity

Never optimize only for win rate.

---

## 21. Mistake analyzer

For each paper trade store:

- setup snapshot
- feature state
- structure/regime
- strategy votes
- entry/stop/target
- live mark
- size/risk
- exit
- MAE/MFE
- P&L/R
- data quality
- reasons for entry/exit

Classify errors such as:

- wrong regime
- late/early entry
- stop too tight/wide
- target unrealistic
- weak confluence
- timeframe conflict
- chasing
- liquidity/spread problem
- stale data
- overexposure
- strategy mismatch
- false breakout
- event shock
- provider/data issue
- simulation/execution issue

Aggregate statistically. Do not conclude from one trade.

---

## 22. Champion / Challenger engine

Maintain champions by market/timeframe/regime and challengers with versioned metrics.

Promotion requires:

- minimum sample
- positive expectancy
- acceptable drawdown
- profit-factor threshold
- OOS stability
- walk-forward stability
- cost robustness
- no catastrophic tail behavior
- parameter stability

Adaptive weights must be evidence-driven.

---

## 23. Professional trading terminal

8787 terminal should evolve to include:

- market watch
- multi-chart layouts
- exact option charts
- support/resistance overlays
- supply/demand
- FVG
- BOS/CHOCH
- liquidity sweeps
- VWAP/AVWAP
- indicator overlays
- regime
- strategy evidence
- setup quality
- paper portfolio/P&L/risk
- autonomous status
- options chain
- OI/delta-OI
- IV/skew/Greeks
- heatmaps
- breadth
- correlation
- trade journal
- strategy leaderboard
- champion/challenger
- Nautilus health
- provider health

Every signal should expose WHY and invalidation.

---

## 24. Voice and desktop reliability

Voice must be non-blocking and deterministic.

Requirements:

- listening/wake state
- STT/TTS
- typo/speech repair
- domain routing
- no duplicate execution
- no stale BUSY locks
- explicit service lifecycle
- safe process ownership checks

Fix the current Windows regression around `.jarvis-dev\JarvisVoiceService.test.exe` by eliminating a fixed shared test executable target. Use a unique temp/GUID/timestamped output path, explicit process cleanup and `finally` cleanup. Retry only genuine Windows sharing violations if safe. Never skip the compile test.

---

## 25. Natural-language trading contract

Must support deterministically:

Terminal:
- open trading terminal
- open paper trading
- open paper trading terminal

Portfolio:
- my paper trading position
- show paper portfolio
- show P&L and exposure

Autonomous:
- start autonomous paper trading
- stop autonomous paper trading
- autonomous paper trading status

Universe:
- scan all supported markets
- find best setups
- rank current setups

Direct paper action:
- take trade in bitcoin
- paper trade BTC
- take a paper trade in Nifty
- execute the qualified Bitcoin setup
- monitor BTC and enter when valid

Semantics:
- direct actions never bypass risk
- no qualified setup -> monitor/arm, do not force
- duplicate position -> reject duplicate
- stale/unverified data -> reject
- split/typo market words repaired conservatively
- unknown instrument -> context guard
- plain EXECUTE without resolvable context -> deterministic context-required response
- portfolio/desk/autonomy intents always take precedence over generic trade-action phrases

---

## 26. Engineering reliability

Every service should expose health/status/metrics/version/last-error/uptime/safety state where practical.

Windows reliability:

- check process ownership
- terminate only JARVIS-owned processes
- check port ownership
- unique temporary build paths
- clean shutdown
- no orphan processes
- explicit logs
- no broad cleanup

Logging should include timestamps, command/mission id, agent/service id, provider, error category and timing.

---

## 27. Test policy

Every milestone runs:

1. compile touched Python
2. JS syntax if applicable
3. exact user-command contract tests
4. subsystem unit tests
5. integration tests
6. trading safety tests
7. regressions for every previously fixed bug
8. full test suite
9. Protected Core import
10. clean git status

Permanent regressions must cover:

- open paper trading
- portfolio
- autonomous mode
- universe scan
- take trade in bitcoin
- split typo `bitcoi n`
- EXECUTE context guard
- option chart commands
- V4/V5 compatibility
- Nautilus 1.231.0
- FYERS read-only safety
- no live order surface
- voice compile
- Windows file-lock resilience

---

## 28. Release process

For each release:

1. inspect current branch/HEAD
2. require clean tree
3. stop only JARVIS-owned runtimes
4. fetch verified source branch
5. verify expected source SHA/capability contract
6. create timestamped safety branch
7. integrate
8. allowlist changed files
9. `git diff --check`
10. compile
11. exact-command tests
12. targeted regressions
13. safety scan
14. full regression
15. Protected Core
16. commit
17. push
18. start JARVIS
19. print success banner

On failure restore exact original branch/HEAD and remove only current patch temp files.

---

## 29. Autonomous implementation roadmap

### Milestone A — Stability and deterministic command router
- fix voice compile file-lock flake without weakening test
- finish direct paper trade routing
- preserve paper-desk precedence
- context-aware EXECUTE
- robust speech typo repair
- eliminate legacy CRUDE fallback for trading intents
- remove duplicate messages
- command context/state

### Milestone B — Unified Feature/Structure Engine
- structure
- support/resistance
- supply/demand
- patterns
- FVG
- BOS/CHOCH
- liquidity
- indicator registry
- multi-timeframe feature store

### Milestone C — Quant Ensemble V2
- regime v2
- strategy registry
- strategy weighting
- contradiction engine
- evidence graph
- setup-quality filters

### Milestone D — Options Desk V2
- normalized India/crypto chains
- OI/delta-OI
- IV/skew/Greeks
- PCR/OI walls
- exact option chart
- option selection
- defined-risk paper spreads

### Milestone E — Autonomous Portfolio Manager
- event-driven scans
- portfolio-aware entries
- active exits/trailing/time stops
- correlation risk
- daily risk locks
- alerts/journal

### Milestone F — Deeper Nautilus integration
- native Binance
- native Deribit
- FYERS custom data adapter
- sandbox execution
- strategy-event adapters
- portfolio/risk synchronization

### Milestone G — Strategy Research Lab
- strategy DSL
- generated hypotheses
- BacktestNode/BacktestEngine workflows
- walk-forward/OOS
- Monte Carlo
- sensitivity/cost modeling
- strategy registry

### Milestone H — Mistake Analyzer and Self-Improvement
- trade attribution
- recurring failure detection
- hypothesis creation
- champion/challenger
- adaptive weights
- weekly learning report

### Milestone I — Professional Intelligence UI
- overlays
- heatmaps
- options desk
- portfolio risk desk
- research results
- strategy leaderboard
- explanation explorer
- learning history

### Milestone J — Shadow-live governance
Only after sufficient paper evidence and explicit approval:
- live data + shadow decisions
- zero real orders
- compare simulated vs market
- slippage/reliability analysis
- incident-free period

Real live execution is a separate future milestone.

---

## 30. Definition of done

JARVIS is not “done” because charts load, indicators display, Nautilus runs, or one paper trade opens.

Target capability is reached only when JARVIS can:

1. continuously observe verified markets
2. understand structure/context
3. use an extensible feature/indicator library
4. select strategies by regime
5. explain evidence and contradictions
6. manage portfolio risk
7. autonomously paper-trade qualified opportunities
8. actively manage positions
9. journal every decision
10. analyze recurring mistakes
11. generate strategy hypotheses
12. robustly backtest/validate them
13. compare champion/challenger
14. improve through governed evidence
15. remain auditable/reversible
16. recover cleanly from service/data failures
17. maintain strict paper/live boundaries

---

## 31. Codex autonomous execution instruction

Codex: execute this blueprint as a multi-milestone engineering program, not one giant unsafe patch.

First perform a complete repository audit and create:

- `data/roadmap/jarvis_master_gap_map.json`
- `docs/JARVIS_MASTER_BLUEPRINT_STATUS.md`

For every capability assign one status:

- PRESENT
- PARTIAL
- MISSING
- BROKEN
- BLOCKED

Record evidence files/functions, existing tests, missing tests, dependencies, milestone and status.

Then implement milestones autonomously. Do not repeatedly ask the user for routine permission.

After every milestone:

- run exact command contracts
- run targeted tests
- run safety tests
- run full regression
- fix failures
- verify Protected Core
- commit/push verified checkpoint
- update the gap map
- update the status document

Do not proceed to a dependent milestone while foundational data/safety contracts are broken.

### Immediate tasks

1. Fix the Windows voice compile file-lock regression without skipping/weaking it.
2. Finish V5.4.1 direct paper-trade routing while preserving V4 Paper Desk/portfolio/autonomy behavior.
3. Run and pass the full regression suite.
4. Establish a verified checkpoint.
5. Build the Unified Feature/Structure Engine.
6. Migrate strategy logic onto the feature and strategy registries.
7. Continue automatically through the roadmap.

Primary engineering principle:

> Build reusable domain capabilities, not one-off responses to individual phrases.

Primary trading principle:

> JARVIS trades only when verified evidence, regime fit, strategy edge and portfolio risk justify a paper position.

Primary learning principle:

> JARVIS improves by generating hypotheses, validating them statistically and promoting robust challengers—not by impulsively rewriting production rules after a loss.

Primary safety principle:

> Until explicitly changed in a future governed milestone, all execution is PAPER/SANDBOX only and all real broker order surfaces remain absent/locked.
