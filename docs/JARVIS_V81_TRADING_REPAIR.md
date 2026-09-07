# JARVIS V8.1 Trading Decision + Execution Repair

Base checkpoint: `94be6ba06dce7154254c7edc90f43ce4e46a3678` (verified V8).

## Why this release exists

Live paper telemetry showed a structurally unhealthy funnel: hundreds of valid scans but zero qualified and zero opened positions. The broad discovery scanner could display 70–72 scores while the paper executor recomputed a different horizon-specific score, and daily discovery candidates were being enrolled only into the intraday singleton rather than the swing mandate.

V8.1 repairs the architecture without enabling real broker execution and without simply lowering global thresholds.

## Independent horizon controls

The Paper Desk now exposes three separate paper mandates:

- **INTRADAY — 50% risk budget**
  - conservative adaptive 5m/15m MTF lane;
  - independent 5m confirmed-breakout lane;
  - independent 15m confirmed-breakout lane;
  - each lane still requires completed-bar evidence, valid risk levels, R:R, fresh/session-qualified data and portfolio-risk approval.
- **SWING — 30% risk budget**
  - 1h / 4h / 1d execution consensus;
  - long and short paper positions permitted when qualified.
- **INVESTMENT — 20% risk budget**
  - daily/long-horizon mandate;
  - long-only;
  - higher evidence and R:R requirements remain intact.

Each mandate has separate START and STOP controls. `START ALL` and `STOP ALL` remain for compatibility.

## Candidate horizon routing

`CandidateHorizonRouter` observes completed broad discovery scans and routes eligible candidates to the three mandate watchlists. Discovery never has entry authority.

The contract is explicit:

`DISCOVERY SCORE != EXECUTION SCORE`

- Discovery score ranks completed-bar opportunities.
- Execution score is recomputed inside the selected horizon.
- A discovery candidate can therefore remain blocked by the horizon-specific execution engine.

Daily bullish confirmed breakout candidates can be enrolled into Investment; eligible daily candidates are also enrolled into Swing; the top bounded candidate set is sent to the fast intraday lanes.

## Why / Why Not Trade board

The portfolio-controller status now combines discovery routing with each mandate's latest execution rows and exposes a `decision_board` containing:

- symbol;
- mandate;
- intraday lane when applicable;
- discovery score;
- execution score;
- candidate side;
- qualified / blocked decision;
- session status;
- blocker list and primary blocker;
- human-readable message.

The Paper Desk renders this as **WHY / WHY NOT TRADE** so a score can no longer appear to silently disappear inside the execution funnel.

## Scan-load repair

The broad daily scanner no longer needs to expand the expensive adaptive MTF singleton with every discovery result. Newly discovered symbols go to bounded 5m and 15m fast lanes while the conservative MTF lane keeps the compact canonical universe. This reduces duplicated 5m/15m computation and should materially shorten the previous 50–70 second scan cycles; runtime telemetry still determines the actual improvement.

## Safety invariants

V8.1 remains paper/research only:

- `paper_only=True`
- `live_execution=False`
- no broker order API added
- no automatic production strategy rewrite
- Investment remains long-only
- existing stop/target, R:R, freshness/session, adaptive-policy and portfolio-risk gates remain downstream of discovery

## Verification

Use `install-jarvis-v81-trading-repair.ps1`.

The installer:

1. requires a clean `C:\Jarvis` working tree;
2. creates a timestamped rollback branch;
3. verifies descent from the exact verified V8 checkpoint;
4. compiles V8.1 Python modules;
5. checks Paper Desk JavaScript with Node when available;
6. enforces the independent-horizon source contract;
7. runs V8.1 + trading + V8 targeted regression;
8. runs the entire JARVIS regression suite by default;
9. rechecks Protected Core, 29-agent contract and paper-only safety;
10. launches the existing V8 runtime supervisor and verifies Master, Quant, Completion and the V8.1 Paper Desk marker;
11. rolls back to the exact previous branch/HEAD on failure.
