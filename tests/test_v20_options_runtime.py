from workstation.v20_options_runtime import _choose_contract, _underlying_signal


def test_underlying_signal_waits_for_enough_history():
    result = _underlying_signal([{"close": 100 + i, "high": 101 + i, "low": 99 + i} for i in range(20)])
    assert result["ready"] is False
    assert result["side"] == "WAIT"


def test_underlying_signal_identifies_direction_from_trend():
    candles = []
    for i in range(80):
        close = 100 + i * 0.6
        candles.append({"close": close, "high": close + 1, "low": close - 1})
    result = _underlying_signal(candles)
    assert result["ready"] is True
    assert result["side"] == "CALL"
    assert result["score"] > 0


def test_contract_selector_prefers_liquid_mid_delta_contract():
    chain = [
        {
            "symbol": "NSE:TEST-LOW",
            "option_type": "CE",
            "strike": 100,
            "ltp": 10,
            "bid": 9,
            "ask": 11,
            "delta": 0.50,
            "volume": 1000,
            "open_interest": 10000,
            "change_in_oi": 500,
        },
        {
            "symbol": "NSE:TEST-WIDE",
            "option_type": "CE",
            "strike": 105,
            "ltp": 10,
            "bid": 5,
            "ask": 15,
            "delta": 0.50,
            "volume": 5000,
            "open_interest": 50000,
            "change_in_oi": 1000,
        },
    ]
    selected = _choose_contract(chain, "CALL")
    assert selected is not None
    assert selected["symbol"] == "NSE:TEST-LOW"
    assert selected["selection_score"] > 0
