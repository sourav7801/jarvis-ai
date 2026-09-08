# JARVIS V13 — Adaptive Intelligence Operating System

V13 builds on the verified V12 adaptive expected-value paper engine. It does not restore fixed score gates. V12 remains the base market-evidence policy; V13 adds context-conditioned closed-paper outcomes, uncertainty-aware decisions, completed-bar portfolio correlation, bounded decision forensics, verified options-volatility synthesis, continuous top-N discovery routing, constraint-aware fractional paper sizing and a governed strategy lifecycle.

## Decision pipeline

`VERIFIED DATA -> CONTINUOUS DISCOVERY -> V12 EVIDENCE EV -> CONTEXTUAL PAPER OUTCOMES -> UNCERTAINTY -> PORTFOLIO CORRELATION -> PRIMARY / PROBE / WAIT -> CONSTRAINT-AWARE SIZE -> PAPER DESK RISK`

Legacy score, alignment and static R:R values remain diagnostics only. A low legacy score may still produce a positive-EV paper decision. Stale data, invalid levels, unavailable accounting/valuation data, session constraints and final Paper Desk risk controls remain hard boundaries.

## Contextual outcome memory

V13 derives bounded cohorts only from durable closed Paper Desk trades. It uses realized R and context fields such as symbol, timeframe, regime, side, adaptive action and setup. Small samples are shrunk toward neutral priors. Missing history remains missing; no synthetic performance record is created.

## Dynamic portfolio correlation

Correlation uses aligned returns from actual completed candles. At least 30 aligned observations are required. Missing data produces `UNKNOWN`, not a fabricated coefficient. High same-direction correlation can only reduce the contextual risk multiplier. The Paper Desk remains the final exposure/risk authority.

## Constraint-aware fractional paper sizing

The inherited Paper Desk originally calculated automatic quantity with floor division before applying the verified instrument quantity step. For fractional assets this could convert a valid BTC/crypto quantity below one whole coin into zero, causing `POSITION_SIZE_ZERO` and leaving an otherwise executable setup in watching mode.

V13 fixes this at the runtime bridge without weakening any risk limit. Automatic sizing now:

`RISK BUDGET / PER-UNIT RISK -> FRACTIONAL RAW QUANTITY -> PORTFOLIO/Bucket/Exposure CAPS -> VERIFIED QUANTITY STEP -> PAPER DESK FINAL VALIDATION`

The planner also downsizes to remaining total-risk, bucket-risk, gross-exposure, bucket-exposure, symbol, asset-class, strategy, direction and configured correlation-cluster capacity instead of requesting an oversized quantity and then rejecting the entire opportunity. Explicit quantities keep the protected Paper Desk behavior. Risk constraints can only reduce size; they are never relaxed.

## Decision forensics

A bounded local evidence ledger records high-information decisions with the V12 base action/EV, V13 action/EV, confidence, contextual posterior, correlation state, hard blockers, soft evidence and changes since the previous observation. Sensitive fields are redacted.

## Discovery

The V13 runtime bridge replaces fixed discovery-score candidate gating with bounded continuous top-N routing of verified directional discoveries. Discovery still has no execution authority; each Intraday, Swing and Investment engine independently evaluates the opportunity.

## Options volatility

V13 composes the existing read-only option-chain and derivatives-history stack. It exposes IV rank/percentile when verified history exists, skew, term structure, PCR, OI changes, expected move when ATM premiums are present, liquidity and unusual activity. OI is never treated as verified dealer inventory. Dealer positioning/gamma is unavailable unless real dealer inventory exists.

## Strategy governance

Persistent lifecycle:

`RESEARCH_CANDIDATE -> VALIDATED -> CHALLENGER -> PAPER_SHADOW -> REVIEW -> CHAMPION`

`CHAMPION` is paper/research-only and requires explicit operator approval. Automatic production promotion, automatic live promotion and production strategy rewrite remain disabled.

## Runtime

- Master: protected V8 Unified Intelligence HTTP/UI identity on `127.0.0.1:8797`, with `/api/v13/paper-authority` proving the process-local V13 bridge.
- Quant: `127.0.0.1:8787`, contextual paper intelligence with 5m/10m/15m/MTF Intraday plus Swing and Investment. The V13 paper overlay shows the top execution blocker and whether positions have actually opened.
- Completion: `127.0.0.1:8799`, V13 intelligence surfaces.
- Nautilus: preserved supervised research/backtest service.

## Safety

- Permanent specialist agents: 29, including the legacy `critic` specialist.
- V13 components are system planes, not additional permanent agents.
- `paper_only=True`
- `live_execution=False`
- `automatic_broker_order=False`
- automatic production strategy rewrite disabled
- external consequential actions approval-gated
- no live broker order API added
- no fabricated market/derivatives/correlation/history data
- automatic sizing never increases requested risk or bypasses Paper Desk limits
