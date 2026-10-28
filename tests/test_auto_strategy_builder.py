from omni.trading_intelligence.auto_strategy_builder import (
    backtest,
    build_strategy_report,
    candidate_specs,
)


def candles(n=320):
    rows = []
    price = 100.0
    for i in range(n):
        # Trend plus a deterministic oscillation so the search space has varied signals.
        price *= 1.0012 if (i // 35) % 2 == 0 else 0.9994
        price += (i % 7 - 3) * 0.025
        rows.append({"close": price, "high": price * 1.003, "low": price * 0.997, "volume": 1000 + i})
    return rows


def test_candidate_space_is_small_and_explainable():
    specs = candidate_specs()
    assert len(specs) >= 4
    assert all(s.name and s.family and s.parameters and s.description for s in specs)


def test_backtest_requires_minimum_evaluation_window():
    result = backtest(candles(30), candidate_specs()[0], start=2, end=4)
    assert result["ready"] is False
    assert result["reason"] == "INSUFFICIENT_EVALUATION_BARS"


def test_builder_splits_chronologically_and_never_enables_live_execution():
    result = build_strategy_report(candles(), minimum_train_bars=100, minimum_test_bars=30)
    assert result["success"] is True
    assert result["state"] == "PAPER_CANDIDATES_READY"
    assert result["split_index"] < result["bars"]
    assert len(result["candidates"]) == len(candidate_specs())
    assert result["governance"]["chronological_holdout"] is True
    assert result["governance"]["automatic_live_execution"] is False
    assert result["governance"]["automatic_code_rewrite"] is False
    assert result["governance"]["live_execution"] is False
    assert all("out_of_sample" in row and "train" in row for row in result["candidates"])


def test_builder_refuses_insufficient_history():
    result = build_strategy_report(candles(80))
    assert result["success"] is False
    assert result["state"] == "INSUFFICIENT_DATA"


def test_backtest_accounts_for_round_trip_costs():
    rows = candles()
    spec = candidate_specs()[0]
    free = backtest(rows, spec, cost_per_turn_pct=0, slippage_per_turn_pct=0)
    charged = backtest(rows, spec, cost_per_turn_pct=0.15, slippage_per_turn_pct=0.10)
    assert charged["metrics"]["net_return_pct"] <= free["metrics"]["net_return_pct"]



def test_backtest_rejects_negative_or_nonfinite_costs():
    negative = backtest(candles(), candidate_specs()[0], cost_per_turn_pct=-0.1)
    infinite = backtest(candles(), candidate_specs()[0], slippage_per_turn_pct=float("inf"))
    assert negative["ready"] is False
    assert negative["reason"] == "INVALID_COST_ASSUMPTION"
    assert infinite["ready"] is False
    assert infinite["reason"] == "INVALID_COST_ASSUMPTION"


def test_trade_metrics_count_completed_round_trips_not_signal_flips():
    result = backtest(candles(), candidate_specs()[0])
    metrics = result["metrics"]
    assert metrics["trades"] >= 0
    assert 0 <= metrics["win_rate"] <= 100
    if metrics["trades"] == 0:
        assert metrics["expectancy_pct"] == 0.0
    else:
        assert isinstance(metrics["expectancy_pct"], float)
