# JARVIS Quant Trading Intelligence V3.2 — Options Intelligence

## Current governed coverage

- Crypto option discovery and paper intents: BTC, ETH via public Deribit market data.
- India index option-chain intelligence: NIFTY and BANKNIFTY via FYERS read-only option-chain data.
- Option request parsing: underlying, strike, call/put, expiry intent, paper intent.
- India option evidence: LTP, bid/ask, OI, change in OI, volume, IV, delta, gamma, theta, vega, PCR OI.
- Ambiguous call/put requests never auto-open paper positions.
- Naked short-option paper execution is blocked. Defined-risk spreads are a later governed module.
- Live broker execution remains locked; no place/modify/cancel order surface exists in these modules.

## Next modules

- Exact lot-size validation from current FYERS symbol masters.
- SENSEX/BSE option-chain support after canonical underlying resolution is verified from the daily master.
- Defined-risk spreads and strategy selection.
- Option-chain panel / IV surface / OI heatmap in the 8787 terminal.
- Continuous option monitor missions and synthetic exits.
