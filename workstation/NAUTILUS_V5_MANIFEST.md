# JARVIS Quant Trading Intelligence V5 — Nautilus Core

## Purpose

V5 introduces an isolated NautilusTrader service as the deterministic research/risk/execution-simulation backbone beneath JARVIS.

## Process architecture

- `8797` — JARVIS OS / Master control plane
- `8787` — JARVIS Quant Trading Intelligence terminal
- `8790` — FYERS read-only data bridge
- `8792` — Nautilus Quant Core

The Nautilus process is isolated because the live-node architecture owns global runtime state and should not be mixed into the Master JARVIS process.

## V5 foundation capabilities

- isolated `.venv-nautilus`
- official NautilusTrader binary package
- Rust-native backtest/risk/execution engine availability checks
- dedicated local quant-core service
- adapter availability checks for Binance, Deribit and Sandbox
- market-event ingestion endpoint with sequence IDs and local ingest latency metrics
- backtest-engine self-test endpoint
- JARVIS client for status/event publishing
- deterministic all-supported-markets command route
- terminal status badge
- existing Quant Firm V4 portfolio/paper desk preserved
- live broker execution remains disabled

## Safety boundary

The V5 core exposes no JARVIS broker-order route. FYERS remains read-only. The Nautilus service is started in paper/sandbox architecture mode only.

## Next V5 layer

After the core installation is proven on the workstation:

1. Binance native data adapter -> Nautilus event stream.
2. Deribit native data/option adapter -> Nautilus event stream.
3. FYERS custom read-only `InstrumentProvider` and `DataClient`.
4. Nautilus Sandbox execution venue for autonomous paper fills.
5. Strategy actors and regime/ensemble controller.
6. Parquet catalog and BacktestNode walk-forward research.
7. Portfolio/risk state synchronization into the 8787 terminal.
8. Order-book, quote-tick and trade-tick strategies.
9. Champion/challenger strategy promotion based on out-of-sample metrics.

Live broker execution is not part of this milestone.
