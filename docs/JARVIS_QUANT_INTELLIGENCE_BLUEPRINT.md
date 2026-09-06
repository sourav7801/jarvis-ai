# JARVIS Quant Intelligence Blueprint

## Mission

JARVIS is not an indicator dashboard. It is an AI control plane for a governed, event-driven quantitative research and autonomous paper-trading system.

The target closed loop is:

`verified market event -> feature state -> market regime -> strategy ensemble -> portfolio risk -> paper execution -> active management -> exit -> journal -> mistake analysis -> research hypothesis -> backtest/walk-forward -> challenger -> governed promotion`

Live broker execution remains locked until a separate, explicit production-governance milestone is completed.

## Core architecture

### 1. JARVIS AI control plane

Owns natural-language intent, voice, agents, memory, missions, explanations, research orchestration, alerts and user interaction.

### 2. Nautilus Quant Core

Owns deterministic event processing, backtest/sandbox infrastructure, portfolio/risk primitives and future exchange-adapter execution semantics. It runs as a dedicated local process.

### 3. Verified market data

- FYERS: India read-only market data and options data.
- Binance: crypto public/native market data.
- Deribit: crypto options/futures/Greeks/IV/order-book data.
- No fabricated current prices, candles, contracts, expiries or option strikes.

### 4. Adaptive Quant Brain

The brain maintains a multi-factor market state rather than relying on one indicator. Initial production-research features include:

- EMA 9/20/50/200
- RSI
- ATR
- VWAP
- MACD
- Bollinger Bands
- Stochastic
- Rate of Change
- ADX proxy
- Relative volume
- swing highs/lows
- support and resistance
- bullish/bearish market structure
- break of structure (BOS)
- change of character (CHOCH)
- fair value gaps (FVG)
- liquidity sweeps/reclaims
- candlestick patterns
- multi-timeframe confluence
- market regime

Custom/proprietary indicators are supported through the Indicator Plugin Registry. JARVIS must never invent the formula for a proprietary indicator such as Premium Lock. The exact formula, Pine source, executable definition or documented logic must be supplied and verified before registration.

## Strategy universe

JARVIS can combine and research multiple strategy families rather than hard-coding one 'best' strategy:

- trend following
- momentum
- VWAP continuation/pullback
- opening-range breakout
- Donchian/breakout
- mean reversion
- Bollinger/RSI extremes
- volatility expansion
- FVG/imbalance
- liquidity sweep/reclaim
- BOS/CHOCH structure
- volume expansion
- options-flow / OI / IV / skew / Greeks research

Strategy selection is regime-aware. A strategy may receive more weight in one market state and less in another.

## Continuous paper execution

The autonomous paper engine scans the governed universe continuously and independently marks open risk more frequently than it recomputes completed-bar strategy decisions.

Supported governed universe currently includes:

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

Direct user requests such as 'take trade in Bitcoin' are objectives, not forced entries. JARVIS must only open a synthetic paper position if the current Quant/risk gates qualify. Otherwise it arms continuous monitoring and waits for a valid setup.

## Learning and mistake analysis

Every closed paper position is converted into an auditable learning outcome containing symbol, side, regime, strategy votes, score, initial risk, exit reason, P&L and R multiple.

The learning engine maintains bounded reliability priors by strategy family and strategy name. Key governance rules:

- one loss cannot rewrite strategy code;
- family weights remain 1.0 until a minimum sample exists;
- learned weights are bounded to a narrow range;
- mistake labels are hypotheses, not truths;
- all learning remains paper/research only;
- automatic production-code rewriting is disabled.

Initial mistake hypotheses include:

- low initial risk/reward
- marginal signal score
- missing regime context
- high strategy disagreement
- stop-hit concentration
- missing stop/target context

## Strategy synthesis and research lab

JARVIS may synthesize candidate strategies from verified feature combinations. Candidate strategies are not deployed because they look good on one chart.

Required research path:

1. define a candidate rule set;
2. backtest using next-bar entries to avoid obvious look-ahead;
3. include fees and slippage assumptions;
4. use pessimistic same-bar stop/target resolution;
5. measure expectancy, profit factor, win rate, average R, net R and max drawdown;
6. run sequential walk-forward folds;
7. reject unstable candidates;
8. allow only robust candidates to become paper challengers;
9. compare challenger performance with the current champion over additional paper samples;
10. require explicit governance before any production promotion.

No universal 'world best strategy' is assumed. Strategy quality is conditional on regime, instrument, timeframe, liquidity, costs and sample stability.

## Options intelligence target

The options desk should evolve toward:

- verified contract resolution
- expiry selection
- strike selection
- call/put OI
- change in OI
- volume
- bid/ask/spread
- IV
- delta/gamma/theta/vega
- skew
- put/call ratios
- OI walls and strike concentration
- underlying + option synchronized charting
- paper-only defined-risk execution

Naked short-option execution remains blocked unless a separate defined-risk framework is explicitly implemented and validated.

## Future chart intelligence

The terminal should render the Adaptive Quant Brain state directly on charts:

- support/resistance zones
- swing labels
- BOS/CHOCH
- FVG rectangles
- liquidity sweeps
- VWAP/EMA overlays
- regime
- selected strategy votes
- entry/stop/target
- active paper position
- P&L and risk
- strategy evidence panel
- learning state / challenger state

## Evaluation metrics

JARVIS must judge strategies with multiple metrics, not win rate alone:

- expectancy
- profit factor
- average R
- payoff ratio
- max drawdown
- MAE/MFE when available
- transaction-cost sensitivity
- regime stability
- walk-forward performance
- out-of-sample performance
- Monte Carlo robustness (future milestone)
- sample size

## Safety and execution boundary

Current target is autonomous paper/shadow trading. The system may continuously analyze, select, enter, manage and exit synthetic positions. It must not expose live broker order placement, modification, cancellation or synchronization APIs in the paper/research modules.

A future live milestone must be separate, explicit, auditable, broker-specific and protected by portfolio-level hard limits and user governance.
