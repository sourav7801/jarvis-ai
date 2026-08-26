"""Covers the partial-exit ladder and trailing target on the paper desk.

Before this framework existed the desk could only move a stop or flatten a
position outright: there was no ``partial``, ``scale_out``, ``tp1`` or
``take_profit`` path anywhere in the paper modules, so a winner either ran to
its fixed target or handed the move back.  These tests pin the two properties
that make banking a partial safe -- exposure only ever falls, and no rupee is
double counted or lost between the banked leg, the portfolio total and the
daily-loss lock -- plus the one-way behaviour of the trailing target.
"""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from workstation.paper_trading_desk import PaperTradingDesk


class PaperPartialExitTests(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.desk = PaperTradingDesk(
            Path(self.temp.name) / "paper.sqlite3",
            starting_equity=100000,
            max_open_positions=4,
            max_total_risk_fraction=0.04,
            max_single_risk_fraction=0.01,
            max_gross_exposure_multiple=2.0,
        )

    def tearDown(self):
        self.temp.cleanup()

    def _open(self, **overrides):
        payload = dict(
            symbol="NIFTY",
            side="LONG",
            entry=100.0,
            stop=98.0,
            target=104.0,
            quantity=30,
            external_id="test:partial",
        )
        payload.update(overrides)
        opened = self.desk.open_position(**payload)
        self.assertTrue(opened["success"], msg=opened)
        return opened

    def test_reduce_position_banks_cash_and_keeps_the_remainder_open(self):
        self._open()

        reduced = self.desk.reduce_position(
            position_id=1,
            exit_price=102.0,
            fraction=1 / 3,
        )

        self.assertTrue(reduced["success"], msg=reduced)
        self.assertEqual(reduced["reason"], "PAPER_POSITION_REDUCED")
        self.assertFalse(reduced["live_execution"])
        self.assertTrue(reduced["paper_only"])
        self.assertAlmostEqual(reduced["quantity"], 10.0)
        self.assertAlmostEqual(reduced["remaining_quantity"], 20.0)
        self.assertAlmostEqual(reduced["pnl"], 20.0)

        snap = self.desk.snapshot(mark_loader=lambda _symbol: 102.0)
        self.assertEqual(snap["open_count"], 1)
        # Exposure fell with the quantity, and the banked leg is already cash.
        self.assertAlmostEqual(snap["unrealized_pnl"], 40.0)
        self.assertAlmostEqual(snap["realized_pnl"], 20.0)

    def test_banked_and_final_legs_sum_exactly_once(self):
        self._open()
        self.desk.reduce_position(position_id=1, exit_price=102.0, fraction=1 / 3)

        closed = self.desk.close_position(
            position_id=1,
            exit_price=103.0,
            reason="TEST_EXIT",
        )

        self.assertTrue(closed["success"], msg=closed)
        # 10 units banked at +2 and 20 units closed at +3.
        self.assertAlmostEqual(closed["realized_pnl"], 80.0)
        final = self.desk.snapshot()
        self.assertEqual(final["open_count"], 0)
        self.assertAlmostEqual(final["realized_pnl"], 80.0)

    def test_scale_out_below_quantity_step_is_refused(self):
        self._open(quantity=1, external_id="test:dust")

        reduced = self.desk.reduce_position(
            position_id=1,
            exit_price=102.0,
            fraction=0.1,
        )

        self.assertFalse(reduced["success"])
        self.assertEqual(reduced["reason"], "SCALE_OUT_BELOW_QUANTITY_STEP")
        self.assertEqual(self.desk.snapshot()["open_count"], 1)

    def test_invalid_fraction_is_refused(self):
        self._open()

        for fraction in (0.0, 1.0, -0.5, 1.5):
            reduced = self.desk.reduce_position(
                position_id=1,
                exit_price=102.0,
                fraction=fraction,
            )
            self.assertFalse(reduced["success"], msg=fraction)
            self.assertEqual(reduced["reason"], "INVALID_FRACTION")

    def test_ladder_fires_each_rung_once(self):
        self._open(
            metadata={
                "initial_risk": 2.0,
                "exit_policy": {
                    "breakeven_at_r": 0.75,
                    "trailing_at_r": 5.0,
                    "scale_out": [
                        {"at_r": 1.0, "fraction": 0.34},
                        {"at_r": 2.0, "fraction": 0.50},
                    ],
                },
            }
        )

        # +2.0 on a 2.0 risk is exactly 1R: only the first rung is eligible.
        self.desk.manage_positions({"NIFTY": 102.0})
        after_first = self.desk.snapshot(mark_loader=lambda _symbol: 102.0)
        self.assertEqual(after_first["open_count"], 1)
        self.assertAlmostEqual(after_first["realized_pnl"], 20.0)

        # Re-marking at the same level must not bank the same rung again.
        self.desk.manage_positions({"NIFTY": 102.0})
        self.assertAlmostEqual(
            self.desk.snapshot(mark_loader=lambda _symbol: 102.0)["realized_pnl"],
            20.0,
        )

        # 2R releases the second rung.
        self.desk.manage_positions({"NIFTY": 104.0})
        after_second = self.desk.snapshot(mark_loader=lambda _symbol: 104.0)
        self.assertEqual(after_second["open_count"], 1)
        self.assertGreater(after_second["realized_pnl"], 20.0)

    def test_trailing_target_extends_only_when_the_stop_protects_the_trade(self):
        self._open(
            metadata={
                "initial_risk": 2.0,
                "exit_policy": {
                    "breakeven_at_r": 0.75,
                    "trailing_at_r": 1.0,
                    "trailing_distance_r": 0.5,
                    "trailing_target_r": 1.0,
                },
            }
        )

        # Price trades through the 104 target with the stop already ratcheted
        # past breakeven, so the objective is pushed out instead of harvested.
        self.desk.manage_positions({"NIFTY": 104.0})

        snap = self.desk.snapshot(mark_loader=lambda _symbol: 104.0)
        self.assertEqual(snap["open_count"], 1, msg="runner was capped at the fixed target")
        position = snap["positions"][0]
        self.assertGreater(float(position["target"]), 104.0)
        self.assertGreaterEqual(float(position["stop"]), 100.0)

    def test_daily_loss_lock_attributes_each_leg_to_its_own_day(self):
        self._open()
        self.desk.reduce_position(position_id=1, exit_price=102.0, fraction=1 / 3)

        today = self.desk.snapshot()["daily_realized_pnl"]
        self.assertAlmostEqual(today, 20.0)

        # Backdate the banked leg by a day; it must leave today's figure.
        yesterday = (
            datetime.now(timezone.utc) - timedelta(days=1)
        ).isoformat()
        with self.desk._connection() as conn:  # noqa: SLF001 - storage assertion
            import json

            row = conn.execute(
                "SELECT metadata_json FROM paper_positions WHERE id=1"
            ).fetchone()
            metadata = json.loads(row["metadata_json"])
            metadata["scale_outs"][0]["at"] = yesterday
            conn.execute(
                "UPDATE paper_positions SET metadata_json=? WHERE id=1",
                (json.dumps(metadata, default=str, sort_keys=True),),
            )

        self.assertAlmostEqual(self.desk.snapshot()["daily_realized_pnl"], 0.0)
        # The lifetime total still carries the banked leg.
        self.assertAlmostEqual(self.desk.snapshot()["realized_pnl"], 20.0)

    def test_no_live_order_surface_in_the_partial_exit_path(self):
        source = Path("workstation/paper_trading_desk.py").read_text(encoding="utf-8")

        for token in ("place_order(", "modify_order(", "cancel_order("):
            self.assertNotIn(token, source)


if __name__ == "__main__":
    unittest.main()
