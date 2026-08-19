# JARVIS Quant Firm Engine V3

Paper/research-only autonomous multi-strategy trading intelligence.

## Strategy families

- EMA trend following
- VWAP momentum
- Donchian breakout
- Opening-range breakout proxy
- RSI/VWAP mean reversion
- Z-score mean reversion
- ATR stretch mean reversion
- Fair value gap / three-candle imbalance
- Liquidity sweep detection
- Relative-volume expansion

## Regime routing

The engine does not assume one strategy is universally best. It classifies the current environment as trending, range-bound, high-volatility, or insufficient-data, then changes family weights. Trend/momentum/breakout votes receive more weight in trending regimes. Mean-reversion/structure votes receive more weight in range regimes. Breakout/structure receives more weight in high-volatility regimes.

## Autonomous paper layer

A validated ensemble decision can create a synthetic paper intent after portfolio risk checks. The paper coordinator enforces maximum open positions, a daily loss lock, position sizing from stop distance, and a minimum strategy score. The module contains no broker order method and always reports live_execution=false.

## Options research

The engine includes a generic liquid near-ATM directional option selector. It can consume normalized option-chain rows with strike, option type, bid, ask, LTP, volume, OI, IV and Greeks when those fields are available. Provider-specific adapters remain separate so unavailable data is never fabricated.

## Research / promotion principle

No strategy is promoted because of a headline win-rate claim. Candidate strategies should be compared using expectancy, payoff ratio, profit factor, drawdown, turnover, slippage sensitivity, out-of-sample performance, walk-forward results, and regime stability. Champion/challenger promotion should be based on validated risk-adjusted results rather than raw win rate.
