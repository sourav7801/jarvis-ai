from workstation.v17_autonomous_options import (
    OPTION_EXECUTION_CAPABILITIES,
    SAFETY,
    option_execution_capability,
)


def test_v17_verified_india_index_options_are_auto_paper_capable():
    for underlying in ("NIFTY", "BANKNIFTY", "SENSEX"):
        capability = option_execution_capability(underlying)
        assert capability["auto_paper"] is True
        assert capability["paper_only"] is True
        assert capability["live_execution"] is False
        assert capability["automatic_broker_order"] is False
        assert capability["live_orders_locked"] is True


def test_v17_unverified_option_venues_fail_closed():
    for underlying in ("MCX_OPTIONS", "CRYPTO_OPTIONS", "UNKNOWN"):
        capability = option_execution_capability(underlying)
        assert capability["auto_paper"] is False
        assert capability["live_execution"] is False
        assert capability["automatic_broker_order"] is False
        assert capability["live_orders_locked"] is True
        assert capability.get("reason")


def test_v17_has_no_forced_trade_quota():
    assert SAFETY["forced_trade_quota"] is False
    assert all(
        "auto_paper" in capability
        for capability in OPTION_EXECUTION_CAPABILITIES.values()
    )
