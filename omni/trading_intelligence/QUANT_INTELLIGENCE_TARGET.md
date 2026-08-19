# JARVIS Quant Trading Intelligence — Target Contract

This file is a product/architecture contract for the trading program. It exists so future development does not regress into isolated indicator demos or one-off routing patches.

## Mission

JARVIS Trading Intelligence must evolve into a multi-asset, event-driven, autonomous **paper-trading** research system that can continuously observe markets, evaluate multiple strategy families, manage portfolio risk, explain its decisions, review its mistakes, and improve strategy selection through governed statistical evidence.

It is **not** defined by RSI/VWAP/volume alone and it must never claim that one indicator or one fixed strategy is universally best.

## Core intelligence loop

1. Ingest verified market events and derivative data.
2. Maintain market state incrementally rather than recomputing everything from scratch.
3. Detect market regime and liquidity/volatility conditions.
4. Compute price structure, support/resistance, order-flow proxies, patterns, indicators and derivative features.
5. Run multiple eligible strategy families in parallel.
6. Rank candidates by regime fit, evidence quality, expected value, robustness and portfolio risk.
7. Pass candidates through a deterministic paper-risk gate.
8. Enter/manage/exit synthetic paper positions continuously.
9. Journal every decision, including rejected trades.
10. Attribute outcome to features, strategies, regime and execution assumptions.
11. Update champion/challenger rankings only from statistically meaningful evidence.
12. Generate new strategy candidates in the research sandbox; never promote them directly to autonomous trading without backtest, walk-forward and paper gates.

## Market intelligence capabilities

### Price / structure
- swing highs/lows
- support/resistance zones
- supply/demand zones
- BOS / CHOCH
- fair value gaps / imbalance
- liquidity pools and sweeps
- displacement
- opening range
- previous day/week/month levels
- session highs/lows
- gap analysis
- anchored levels
- market profile / volume profile when data supports it

### Indicator registry
The engine must support a plugin/registry model rather than a hard-coded indicator list. Candidate families include:
- SMA / EMA / WMA / HMA
- VWAP / anchored VWAP
- RSI / Stoch RSI
- MACD
- ADX / DMI
- ATR / realized volatility
- Bollinger Bands / Keltner Channels
- Supertrend
- Donchian Channels
- ROC / momentum
- OBV / MFI / CMF
- volume / relative volume
- pivot families
- Ichimoku
- PSAR
- custom user-defined indicators

A named indicator that is not a verified public standard must be treated as a custom plugin until its exact formula/source is supplied. This includes any future request such as a proprietary "Premium Lock" indicator.

### Pattern engine
- candlestick patterns
- classical chart patterns
- breakout/retest
- range expansion/contraction
- volatility squeeze
- trend continuation/reversal
- multi-timeframe pattern confirmation

### Derivatives / options
- option chain
- OI and change in OI
- volume
- bid/ask and spread
- implied volatility
- IV rank / percentile
- skew and term structure
- Delta / Gamma / Theta / Vega
- PCR
- strike concentration / walls
- expiry/DTE
- liquidity score
- underlying/derivative confirmation
- defined-risk option structures where verified data exists

### Market breadth / cross-market
- NIFTY / BANKNIFTY / SENSEX breadth
- heavyweight confirmation
- sector rotation
- index-vs-components divergence
- commodities / FX / crypto cross-market context where data exists
- correlation and concentration risk

## Strategy families

The strategy layer must be extensible and regime-aware. It should support, test and compare:
- trend following
- momentum
- breakout
- opening-range breakout
- mean reversion
- VWAP reversion / continuation
- volatility expansion / contraction
- FVG / liquidity-sweep structures
- BOS / CHOCH structures
- support/resistance reaction
- relative-strength / breadth
- options-flow / OI / IV strategies
- volatility strategies
- event/news-aware strategies where evidence is timestamped and verified
- ensemble combinations
- research-generated strategy candidates

## Strategy selection

JARVIS must not optimize for win rate alone. Champion/challenger ranking should include:
- expectancy
- profit factor
- Sharpe / Sortino
- max drawdown
- Calmar
- win rate
- payoff ratio
- MAE / MFE
- slippage sensitivity
- transaction-cost sensitivity
- turnover
- regime stability
- walk-forward performance
- out-of-sample performance
- Monte Carlo robustness
- sample size and uncertainty

## Self-improvement / mistake analysis

After each closed paper trade the system should record:
- thesis and strategy votes
- features at entry
- regime
- data source / freshness
- entry/stop/target assumptions
- slippage assumption
- MAE/MFE
- exit reason
- realized R / P&L
- which evidence was useful or misleading
- whether the trade violated any rule

Learning rules:
- do not change a strategy because of one loss
- do not self-edit production code from a trade outcome
- produce research hypotheses from mistakes
- test hypotheses in backtest and walk-forward environments
- promote only through governed champion/challenger gates
- keep full audit history of promotions/demotions

## Autonomous paper trading

The system may continuously scan and execute **synthetic paper trades** when qualified. It must support:
- multiple simultaneous markets
- portfolio-level risk limits
- risk per trade
- gross/net exposure
- stop/target/trailing logic
- duplicate/correlation controls
- daily loss lock
- stale-data rejection
- session / liquidity gates
- persistent positions and P&L
- automatic exits
- alerts and audit journal

## Execution boundary

Until a future explicit governance milestone changes this contract:

- `paper_only = True`
- `live_execution = False`
- FYERS market-data integration is read-only
- no autonomous live broker order client is allowed
- no strategy research result can unlock live trading

## Nautilus role

NautilusTrader is the event-driven research/risk/execution-simulation backbone. JARVIS remains the AI control plane, strategy research/orchestration layer, explanation layer, memory, voice and terminal UI.

Target separation:
- JARVIS: intelligence, strategy synthesis, agents, memory, news, explanation, UI
- Nautilus: event bus, market state, portfolio/risk, deterministic simulation, backtesting, sandbox execution

## Definition of success

The product is not considered "powerful" merely because it displays charts or indicators. The target is reached only when the complete loop works reliably:

**verified event -> feature state -> regime -> strategy ensemble -> risk -> autonomous paper execution -> active management -> exit -> journal -> evaluation -> governed research improvement**
