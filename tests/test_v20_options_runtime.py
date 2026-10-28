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


def test_contract_selector_uses_near_atm_proxy_when_delta_missing():
    chain = [
        {
            "symbol": "NSE:TEST-ATM",
            "option_type": "CE",
            "strike": 100,
            "ltp": 10,
            "bid": 9.9,
            "ask": 10.1,
            "volume": 1000,
            "open_interest": 10000,
            "change_in_oi": 500,
        },
        {
            "symbol": "NSE:TEST-WIDE_OTM",
            "option_type": "CE",
            "strike": 110,
            "ltp": 5,
            "bid": 4.0,
            "ask": 6.0,
            "volume": 5000,
            "open_interest": 50000,
            "change_in_oi": 1000,
        },
    ]
    selected = _choose_contract(chain, "CALL", 100)
    assert selected is not None
    assert selected["symbol"] == "NSE:TEST-ATM"
    assert selected["selection_score"] > 0


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



def test_options_agent_tracks_selected_underlying_without_network_io():
    from workstation.v20_options_runtime import V20OptionsAgent

    agent = V20OptionsAgent()
    assert agent.active_config() == ("NIFTY", None, "5m")
    agent.start()
    seen = {}

    def fake_evaluate(symbol, expiry, timeframe):
        seen["config"] = (symbol, expiry, timeframe)
        return {"success": True}

    agent._evaluate_once = fake_evaluate
    result = agent.evaluate("BANKNIFTY", "2026-10-29", "15m")
    assert result["success"] is True
    assert seen["config"] == ("BANKNIFTY", "2026-10-29", "15m")
    assert agent.active_config() == ("BANKNIFTY", "2026-10-29", "15m")


def test_options_agent_can_restart_after_stop():
    from workstation.v20_options_runtime import V20OptionsAgent

    agent = V20OptionsAgent()
    agent.stop()
    assert agent.status()["running"] is False
    agent.start()
    assert agent.status()["running"] is True



def test_overlapping_evaluation_returns_wait_state_without_second_run():
    from workstation.v20_options_runtime import V20OptionsAgent

    agent = V20OptionsAgent()
    agent._evaluation_lock.acquire()
    try:
        result = agent.evaluate("BANKNIFTY")
    finally:
        agent._evaluation_lock.release()
    assert result["success"] is False
    assert result["state"] == "EVALUATING"
    assert result["symbol"] == "BANKNIFTY"
    assert result["live_execution"] is False



def test_stopped_options_agent_cannot_create_a_paper_position():
    from workstation.v20_options_runtime import V20OptionsAgent

    agent = V20OptionsAgent()
    agent.stop()
    result = agent._open_if_running(
        symbol="NSE:TEST",
        side="BUY",
        entry=10.0,
        stop=8.0,
        target=14.0,
        quantity=1,
    )
    assert result == {"success": False, "reason": "OPTIONS_AGENT_STOPPED"}



def test_options_agent_starts_paused_until_explicit_start():
    from workstation.v20_options_runtime import V20OptionsAgent

    agent = V20OptionsAgent()
    assert agent.status()["running"] is False
    agent.start()
    assert agent.status()["running"] is True
