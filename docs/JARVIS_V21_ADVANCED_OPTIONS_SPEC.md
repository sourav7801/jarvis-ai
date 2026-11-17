# Jarvis V21 — Advanced Options Workspace

**Status:** Final product scope / implementation baseline  
**Base:** `jarvis-dev/20260923-v20-agent-mesh`  
**Branch:** `jarvis-v21-advanced-options`

## Product decision

V21 is the final planned options-focused release line for the current Jarvis trading terminal. It consolidates existing V15.1/V16/V17/V20 options capabilities rather than introducing another parallel options engine.

V21 is an advanced **research, analysis, and paper-trading** workspace. Live order placement remains disabled until separate broker/API, exchange, regulatory, security, and operational approval.

## Scope

### Supported instruments
- NIFTY and BANKNIFTY options.
- SENSEX options where the connected provider supplies complete, validated chain and contract metadata.
- Index futures/options analytics supported by the existing data adapters.
- No broad stocks/commodities scanner expansion in this release.

### User workflow
1. Select underlying and expiry.
2. Load a timestamped option chain with provider and freshness status.
3. Review underlying trend, market regime, VWAP, volatility and key levels.
4. Inspect chain liquidity, bid/ask spread, volume, OI, OI change, IV and Greeks where available.
5. Compare eligible contracts and defined-risk strategies.
6. Review entry zone, invalidation, stop logic, target logic, max loss, breakeven, payoff and estimated costs.
7. Send an approved candidate to the canonical paper desk.
8. Review fills, P&L, risk, and journal entry.

The system must display **NO TRADE** when data, liquidity, contract metadata, risk, or signal confirmation is insufficient.

## Architecture and authority

| Concern | V21 authority |
|---|---|
| Market data | Existing provider adapters; preserve FYERS integration and verify any Groww adapter independently |
| Chain normalization | Existing option-chain provider/schema, with one canonical normalized contract model |
| Decision analysis | Consolidated V15.1/V16 options intelligence |
| V20 Options Agent | Research/orchestration and explanation only; not an independent order authority |
| Contract selection | Canonical selector with expiry, liquidity, spread, Greeks and contract validation |
| Strategy analysis | Long CE/PE and defined-risk debit spreads initially |
| Paper execution | One canonical paper execution desk |
| Risk | Independent deterministic risk gate; AI cannot override it |
| UI | Existing Options workspace and charts; preserve other workspaces |
| Live execution | Disabled by default and guarded server-side |

Do not delete legacy modules merely because they are not the selected authority. First map callers and tests; retain compatibility wrappers where needed and remove duplicates only after migration tests pass.

## Mandatory analytical requirements

- Timestamp and identify every market-data source.
- Reject stale, incomplete, crossed, malformed or mismatched chain data.
- Validate expiry, strike, option type, lot size, tick size and underlying mapping against the current instrument master.
- Display missing Greeks/IV as unavailable; never fabricate them.
- Include brokerage, statutory charges, spread and slippage assumptions in paper P&L.
- Prevent look-ahead, duplicate signals and duplicate paper orders.
- Use option-specific risk/payoff calculations; do not use arbitrary fixed percentage stop/target geometry as the authoritative risk model.
- Distinguish theoretical payoff from achievable execution and liquidity.
- Require explicit confirmation before creating a paper position.
- Keep signal rationale and risk calculations auditable.

## Risk policy

Initial defaults are conservative research guardrails, not promises of maximum loss:
- Paper mode only.
- One active paper position per underlying by default.
- No averaging down or martingale.
- No new paper entry when feed is stale or risk state is unavailable.
- Enforce max-loss, daily-loss, position-count, quantity and exposure limits in a deterministic backend service.
- Kill switch blocks new entries immediately and records an audit event.
- Simulated stops are not guaranteed fills; model gaps and slippage.

Live trading must remain unavailable unless a later, separately reviewed change explicitly enables it after broker API permissions, exchange algo requirements, authentication, order controls, monitoring, and compliance checks are completed.

## V21 implementation work packages

1. **Baseline and inventory**
   - Freeze V20 base SHA and record current branch.
   - Map options UI -> HTTP routes -> runtime -> providers -> paper desk.
   - Capture CI status and current failing tests before modifications.
2. **Canonical data and chain**
   - Normalize contracts and chain snapshots.
   - Add freshness, completeness, symbol/expiry and liquidity validation.
3. **Decision consolidation**
   - Route all option candidates through the selected V15.1/V16 decision authority.
   - Restrict V20 agent to explanation/orchestration.
   - Remove the fixed 28% stop / 45% target auto-entry behavior as an authoritative decision rule.
4. **Risk-aware strategy analysis**
   - Validate long CE/PE and defined-risk debit spreads.
   - Calculate payoff, breakeven, max loss, costs, spread and quantity.
5. **Paper execution**
   - Use one paper desk and explicit user confirmation.
   - Persist order lifecycle, fills, positions, P&L and journal.
6. **Options UI integration**
   - Preserve chain, charts, strategy analysis, readiness, journal and existing workspaces.
   - Show data health, candidate rationale, risk and NO TRADE reasons.
7. **Regression and release**
   - Repair options-specific regressions.
   - Run targeted tests, full test suite, JS syntax checks and end-to-end paper flow.
   - Publish exact pass/fail counts and known limitations.

## Acceptance gates

- No stale or invalid chain can generate an actionable candidate.
- No AI-generated decision can bypass deterministic risk controls.
- No automatic paper position opens without explicit user confirmation.
- All displayed contract metadata comes from validated source data.
- Paper P&L includes configured costs and execution assumptions.
- Restart/reconnect recovers paper state without duplicate positions.
- Existing Intraday, Swing, Investment, Options, chart and journal workspaces pass regression tests.
- All changed Python modules compile; relevant JavaScript passes syntax checks.
- Options-focused tests pass; full-suite failures are reported rather than hidden.
- Live order routes remain blocked in backend configuration and tests.

## Out of scope

- New multi-market stocks/commodities scanner.
- A new standalone application or replacement UI.
- A new independent options agent that can place trades.
- Live automated trading.
- Claims of profitability or guaranteed stop-loss execution.

## Release definition

V21 is ready for a **research and paper-trading release** only after all acceptance gates are evidenced. A branch or specification commit is not a completed implementation or a passing release. The final release note must list the tested commit SHA, commands run, pass/fail counts, data providers verified, and any remaining limitations.
