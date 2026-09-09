# JARVIS V15.1 — Options Execution Intelligence

V15.1 is a paper-only options-expression layer built strictly on the verified V15 market-reasoning release.

## Authority chain

1. Verified completed-bar market data.
2. V14.1 verified underlying risk geometry.
3. V15 market belief, competing hypotheses, contextual EV and portfolio-adjusted utility.
4. Verified read-only option-chain snapshot.
5. Verified option instrument specification (symbol, lot size, tick size, multiplier).
6. Option-specific contract economics and premium risk plan.
7. PaperTradingDesk as final sizing/accounting/risk authority.

## Long-premium scope

V15.1 supports only paper long-premium expression:

- bullish actionable underlying → call candidates may be evaluated;
- bearish actionable underlying → put candidates may be evaluated;
- a directional underlying view never forces an option trade;
- wide spread, missing executable quote, unverified chain/spec, expired/0-DTE contract, or non-positive option economics can produce `NO_OPTION_TRADE`;
- naked short options are disabled.

## Contract evidence

The engine can use verified bid/ask, LTP, OI, OI change, volume, IV and Greeks already present in the option-chain schema. Missing Greeks remain unavailable. No Greeks, IV, dealer inventory or market prices are fabricated.

Dealer positioning remains `UNAVAILABLE_WITHOUT_VERIFIED_INVENTORY`.

## Premium risk geometry

Entry uses the verified executable ask for a paper long-premium plan. Stop and target are deterministic risk-plan estimates based on premium, uncertainty and liquidity. They are explicitly labelled as risk-plan estimates and are not represented as future market quotes.

The premium geometry must satisfy `0 < stop < entry < target`.

## Instrument accounting

Paper options require verified lot size and tick size. Paper quantity is expressed in lots (`quantity_step=1`) and `contract_multiplier=lot_size`, preserving the existing PaperTradingDesk derivative-accounting contract.

## Safety

- `paper_only=True`
- `live_execution=False`
- `automatic_broker_order=False`
- option-chain providers remain read-only
- no POST/order endpoint is added
- PaperTradingDesk remains final risk authority
- 29 permanent specialists including `critic` remain unchanged
- V8 protected Master remains the runtime identity
