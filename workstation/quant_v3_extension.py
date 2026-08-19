from __future__ import annotations

"""Quant V3 integration surface for the professional terminal.

This module is intentionally separate from the V2 HTTP server so V3 can be
installed/rolled back without destabilizing the chart/data foundation.
"""

from typing import Any, Callable

from omni.trading_intelligence.deribit_option_chain_v3 import fetch_deribit_option_chain
from omni.trading_intelligence.fyers_option_chain_v3 import analyze_fyers_options
from omni.trading_intelligence.quant_v3_autopilot import AutopilotConfig, QuantV3Autopilot
from omni.trading_intelligence.quant_v3_strategy_engine import evaluate_strategies, strategy_catalog


CandleLoader = Callable[[str, str, int], dict[str, Any]]
LiveLoader = Callable[[str], dict[str, Any]]


class QuantV3Extension:
    def __init__(self) -> None:
        self._candles: CandleLoader | None = None
        self._live: LiveLoader | None = None
        self.autopilot = QuantV3Autopilot(
            AutopilotConfig(
                local_cycle_seconds=0.25,
                history_refresh_seconds=8.0,
                option_refresh_seconds=10.0,
                risk_per_trade=0.005,
                option_risk_per_trade=0.0025,
                max_daily_loss_pct=0.02,
                max_portfolio_drawdown_pct=0.06,
                max_positions=4,
            )
        )

    def configure(self, *, candle_loader: CandleLoader, live_loader: LiveLoader) -> None:
        self._candles = candle_loader
        self._live = live_loader
        self.autopilot.configure_loaders(
            snapshot_loader=live_loader,
            candle_loader=candle_loader,
            option_loader=self.option_payload,
        )

    @staticmethod
    def normalize_symbol(value: str) -> str:
        text = str(value or "").strip().upper().replace(" ", "")
        aliases = {
            "NIFTY50": "NIFTY",
            "NIFTY": "NIFTY",
            "BANKNIFTY": "BANKNIFTY",
            "SENSEX": "SENSEX",
            "CRUDE": "CRUDEOIL",
            "CRUDEOIL": "CRUDEOIL",
            "GOLD": "GOLD",
            "SILVER": "SILVER",
            "NATGAS": "NATURALGAS",
            "NATURALGAS": "NATURALGAS",
            "BTC": "BTC",
            "BITCOIN": "BTC",
            "ETH": "ETH",
            "ETHEREUM": "ETH",
            "SOL": "SOL",
            "SOLANA": "SOL",
        }
        result = aliases.get(text, text)
        supported = {"NIFTY", "BANKNIFTY", "SENSEX", "CRUDEOIL", "GOLD", "SILVER", "NATURALGAS", "BTC", "ETH", "SOL"}
        if result not in supported:
            raise ValueError(f"Unsupported Quant V3 symbol: {value}")
        return result

    def option_payload(self, symbol: str) -> dict[str, Any] | None:
        canonical = self.normalize_symbol(symbol)
        try:
            if canonical in {"NIFTY", "BANKNIFTY", "SENSEX"}:
                return analyze_fyers_options(canonical, strikecount=12, greeks=True)
            if canonical in {"CRUDEOIL", "GOLD", "SILVER", "NATURALGAS"}:
                # Resolve the active MCX futures contract first. FYERS accepts
                # provider symbols; if the selected contract/segment has no
                # option chain the request fails closed and autopilot falls
                # back to the underlying paper instrument.
                from workstation.paper_market_data import PAPER_MARKET_DATA

                resolved = PAPER_MARKET_DATA.provider_symbol(canonical)
                provider_symbol = str(resolved.get("provider_symbol") or "")
                if not provider_symbol:
                    raise RuntimeError("Could not resolve active MCX contract for option-chain research.")
                result = analyze_fyers_options(provider_symbol, strikecount=10, greeks=True)
                result["friendly_symbol"] = canonical
                return result
            if canonical in {"BTC", "ETH"}:
                return fetch_deribit_option_chain(canonical, strike_window=14)
            return {
                "success": False,
                "symbol": canonical,
                "message": "No verified public option-chain adapter is configured for this market.",
                "paper_only": True,
                "live_execution": False,
            }
        except Exception as exc:
            return {
                "success": False,
                "symbol": canonical,
                "message": f"{type(exc).__name__}: {exc}"[:500],
                "paper_only": True,
                "live_execution": False,
            }

    @staticmethod
    def _option_confirmation(options: dict[str, Any] | None) -> dict[str, Any] | None:
        if not isinstance(options, dict) or not options.get("success"):
            return None
        value = options.get("confirmation")
        return dict(value) if isinstance(value, dict) else None

    def decision_payload(self, symbol: str) -> dict[str, Any]:
        canonical = self.normalize_symbol(symbol)
        if self._candles is None:
            raise RuntimeError("Quant V3 candle loader is not configured.")
        options = self.option_payload(canonical)
        option_confirmation = self._option_confirmation(options)
        evaluations = []
        for timeframe in ("1m", "5m", "15m"):
            payload = self._candles(canonical, timeframe, 320)
            candles = list(payload.get("candles") or ()) if isinstance(payload, dict) else []
            result = evaluate_strategies(
                candles,
                symbol=canonical,
                timeframe=timeframe,
                option_context=option_confirmation,
            )
            if result.get("success"):
                evaluations.append(result)
        if not evaluations:
            return {
                "success": False,
                "symbol": canonical,
                "message": "No verified timeframe has enough data for Quant V3.",
                "options": options,
                "paper_only": True,
                "live_execution": False,
            }
        long_count = sum(item["consensus"] == "LONG" for item in evaluations)
        short_count = sum(item["consensus"] == "SHORT" for item in evaluations)
        if long_count > short_count:
            consensus, agreement = "LONG", long_count / len(evaluations)
        elif short_count > long_count:
            consensus, agreement = "SHORT", short_count / len(evaluations)
        else:
            consensus, agreement = "FLAT", 0.0
        matching = [item for item in evaluations if item["consensus"] == consensus]
        confidence = sum(float(item.get("confidence") or 0.0) for item in matching) / max(len(matching), 1)
        anchor = next((item for item in evaluations if item["timeframe"] == "5m"), evaluations[0])
        total_latency = sum(float(item.get("latency", {}).get("total_ms") or 0.0) for item in evaluations)
        return {
            "success": True,
            "symbol": canonical,
            "consensus": consensus,
            "timeframe_agreement": round(agreement, 4),
            "confidence": round(confidence, 4),
            "regime": anchor.get("regime"),
            "anchor": anchor,
            "evaluations": evaluations,
            "options": options,
            "engine_latency_ms": round(total_latency, 4),
            "latency_scope": "local feature/strategy computation only; excludes broker/network latency",
            "paper_only": True,
            "live_execution": False,
        }

    def strategies_payload(self) -> dict[str, Any]:
        return {
            "success": True,
            "strategies": list(strategy_catalog()),
            "selection": "regime_weighted_ensemble",
            "validation_priority": [
                "out_of_sample_expectancy",
                "profit_factor",
                "max_drawdown",
                "walk_forward_stability",
                "cost_stress",
                "monte_carlo_robustness",
                "win_rate",
            ],
            "universal_best_strategy_claim": False,
            "paper_only": True,
            "live_execution": False,
        }

    def start_autopilot(self, symbols: list[str] | tuple[str, ...] | None = None) -> dict[str, Any]:
        selected = symbols or ["NIFTY", "BANKNIFTY", "SENSEX", "CRUDEOIL", "GOLD", "BTC", "ETH"]
        canonical = [self.normalize_symbol(symbol) for symbol in selected]
        return self.autopilot.start(canonical)

    def status_payload(self) -> dict[str, Any]:
        return {
            "success": True,
            "version": "QUANT_V3_AUTONOMOUS_PAPER",
            "autopilot": self.autopilot.status(),
            "strategies": self.strategies_payload(),
            "options_markets": {
                "india": ["NIFTY", "BANKNIFTY", "SENSEX", "MCX_WHERE_PROVIDER_CHAIN_IS_AVAILABLE"],
                "crypto": ["BTC", "ETH"],
            },
            "hot_path": {
                "source": "read_only_stream_snapshots_plus_local_candle_cache",
                "local_cycle_seconds": self.autopilot.config.local_cycle_seconds,
                "hft_or_colocation_claim": False,
            },
            "paper_only": True,
            "live_execution": False,
            "broker_order": False,
        }


quant_v3_extension = QuantV3Extension()
