from __future__ import annotations

from contextlib import (
    contextmanager,
)

import json
import sqlite3

from pathlib import (
    Path,
)


ROOT = (
    Path(__file__)
    .resolve()
    .parents[2]
)


DEFAULT_DB = (
    ROOT
    / "data"
    / "trading"
    / "derivatives"
    / "history.sqlite3"
)


class DerivativesHistoryStore:

    def __init__(
        self,
        path=None,
    ):

        self.path = Path(
            path
            or DEFAULT_DB
        )


        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )


        self._initialize()


    def _connect(
        self,
    ):

        connection = sqlite3.connect(
            self.path,
            timeout=15,
        )


        connection.row_factory = (
            sqlite3.Row
        )


        connection.execute(
            "PRAGMA foreign_keys=ON"
        )


        connection.execute(
            "PRAGMA busy_timeout=15000"
        )


        return connection


    @contextmanager
    def _db(
        self,
    ):

        connection = self._connect()

        try:

            # sqlite3.Connection context management
            # commits/rolls back but does not itself close
            # the Windows database file handle.
            with connection:

                yield connection

        finally:

            connection.close()


    def _initialize(
        self,
    ):

        with self._db() as db:

            db.execute(
                """
                CREATE TABLE IF NOT EXISTS chain_snapshots (
                    snapshot_id TEXT PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    captured_at TEXT NOT NULL,
                    selected_expiry TEXT,
                    strikecount INTEGER,
                    greeks_requested INTEGER NOT NULL,
                    spot REAL,
                    call_oi INTEGER,
                    put_oi INTEGER,
                    pcr_oi REAL,
                    atm_strike REAL,
                    atm_call_iv REAL,
                    atm_put_iv REAL,
                    atm_iv REAL,
                    atm_skew REAL,
                    expiry_data_json TEXT NOT NULL,
                    raw_response_json TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    sdk_version TEXT
                )
                """
            )


            db.execute(
                """
                CREATE TABLE IF NOT EXISTS option_legs (
                    snapshot_id TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    captured_at TEXT NOT NULL,
                    expiry TEXT,
                    contract_symbol TEXT,
                    fy_token TEXT,
                    option_type TEXT NOT NULL,
                    strike REAL NOT NULL,
                    ltp REAL,
                    ltp_change REAL,
                    ltp_change_pct REAL,
                    bid REAL,
                    ask REAL,
                    oi INTEGER,
                    oi_change INTEGER,
                    oi_change_pct REAL,
                    previous_oi INTEGER,
                    volume INTEGER,
                    delta REAL,
                    gamma REAL,
                    theta REAL,
                    vega REAL,
                    iv REAL,
                    FOREIGN KEY(snapshot_id)
                        REFERENCES chain_snapshots(snapshot_id)
                        ON DELETE CASCADE
                )
                """
            )


            db.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_chain_symbol_time
                ON chain_snapshots(symbol, captured_at)
                """
            )


            db.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_leg_lookup
                ON option_legs(
                    symbol,
                    expiry,
                    strike,
                    option_type,
                    captured_at
                )
                """
            )


    def save(
        self,
        snapshot,
    ):

        snapshot = dict(
            snapshot
        )


        with self._db() as db:

            db.execute(
                """
                INSERT INTO chain_snapshots (
                    snapshot_id,
                    symbol,
                    captured_at,
                    selected_expiry,
                    strikecount,
                    greeks_requested,
                    spot,
                    call_oi,
                    put_oi,
                    pcr_oi,
                    atm_strike,
                    atm_call_iv,
                    atm_put_iv,
                    atm_iv,
                    atm_skew,
                    expiry_data_json,
                    raw_response_json,
                    provider,
                    sdk_version
                )
                VALUES (
                    ?,?,?,?,?,?,?,?,?,?,
                    ?,?,?,?,?,?,?,?,?
                )
                """,
                (
                    snapshot[
                        "snapshot_id"
                    ],

                    snapshot[
                        "symbol"
                    ],

                    snapshot[
                        "captured_at"
                    ],

                    snapshot.get(
                        "selected_expiry"
                    ),

                    snapshot.get(
                        "strikecount"
                    ),

                    int(
                        bool(
                            snapshot.get(
                                "greeks_requested"
                            )
                        )
                    ),

                    snapshot.get(
                        "spot"
                    ),

                    snapshot.get(
                        "call_oi"
                    ),

                    snapshot.get(
                        "put_oi"
                    ),

                    snapshot.get(
                        "pcr_oi"
                    ),

                    snapshot.get(
                        "atm_strike"
                    ),

                    snapshot.get(
                        "atm_call_iv"
                    ),

                    snapshot.get(
                        "atm_put_iv"
                    ),

                    snapshot.get(
                        "atm_iv"
                    ),

                    snapshot.get(
                        "atm_skew"
                    ),

                    json.dumps(
                        snapshot.get(
                            "expiry_data",
                            (),
                        ),
                        default=str,
                    ),

                    json.dumps(
                        snapshot.get(
                            "raw_response",
                            {},
                        ),
                        default=str,
                    ),

                    snapshot.get(
                        "provider",
                        "unknown",
                    ),

                    snapshot.get(
                        "sdk_version"
                    ),
                ),
            )


            for leg in snapshot.get(
                "legs",
                ()
            ):

                db.execute(
                    """
                    INSERT INTO option_legs (
                        snapshot_id,
                        symbol,
                        captured_at,
                        expiry,
                        contract_symbol,
                        fy_token,
                        option_type,
                        strike,
                        ltp,
                        ltp_change,
                        ltp_change_pct,
                        bid,
                        ask,
                        oi,
                        oi_change,
                        oi_change_pct,
                        previous_oi,
                        volume,
                        delta,
                        gamma,
                        theta,
                        vega,
                        iv
                    )
                    VALUES (
                        ?,?,?,?,?,?,?,?,?,?,
                        ?,?,?,?,?,?,?,?,?,?,
                        ?,?,?
                    )
                    """,
                    (
                        snapshot[
                            "snapshot_id"
                        ],

                        snapshot[
                            "symbol"
                        ],

                        snapshot[
                            "captured_at"
                        ],

                        leg.get(
                            "expiry"
                        ),

                        leg.get(
                            "symbol"
                        ),

                        leg.get(
                            "fy_token"
                        ),

                        leg[
                            "option_type"
                        ],

                        leg[
                            "strike"
                        ],

                        leg.get(
                            "ltp"
                        ),

                        leg.get(
                            "ltp_change"
                        ),

                        leg.get(
                            "ltp_change_pct"
                        ),

                        leg.get(
                            "bid"
                        ),

                        leg.get(
                            "ask"
                        ),

                        leg.get(
                            "oi"
                        ),

                        leg.get(
                            "oi_change"
                        ),

                        leg.get(
                            "oi_change_pct"
                        ),

                        leg.get(
                            "previous_oi"
                        ),

                        leg.get(
                            "volume"
                        ),

                        leg.get(
                            "delta"
                        ),

                        leg.get(
                            "gamma"
                        ),

                        leg.get(
                            "theta"
                        ),

                        leg.get(
                            "vega"
                        ),

                        leg.get(
                            "iv"
                        ),
                    ),
                )


        return {
            "success":
                True,

            "snapshot_id":
                snapshot[
                    "snapshot_id"
                ],

            "leg_count":
                len(
                    snapshot.get(
                        "legs",
                        ()
                    )
                ),

            "database":
                str(
                    self.path
                ),

            "research_only":
                True,
        }


    def history(
        self,
        symbol,
        *,
        limit=100,
    ):

        limit = max(
            1,
            min(
                int(
                    limit
                ),
                5000,
            ),
        )


        with self._db() as db:

            rows = db.execute(
                """
                SELECT
                    snapshot_id,
                    symbol,
                    captured_at,
                    selected_expiry,
                    strikecount,
                    greeks_requested,
                    spot,
                    call_oi,
                    put_oi,
                    pcr_oi,
                    atm_strike,
                    atm_call_iv,
                    atm_put_iv,
                    atm_iv,
                    atm_skew,
                    provider,
                    sdk_version
                FROM chain_snapshots
                WHERE symbol = ?
                ORDER BY captured_at DESC
                LIMIT ?
                """,
                (
                    str(
                        symbol
                    ),
                    limit,
                ),
            ).fetchall()


        return tuple(
            dict(
                row
            )

            for row
            in rows
        )


    def leg_history(
        self,
        symbol,
        strike,
        option_type,
        *,
        expiry=None,
        limit=500,
    ):

        option_type = str(
            option_type
        ).upper()


        parameters = [
            str(
                symbol
            ),
            float(
                strike
            ),
            option_type,
        ]


        where = (
            "symbol = ? "
            "AND strike = ? "
            "AND option_type = ?"
        )


        if expiry is not None:

            where += (
                " AND expiry = ?"
            )


            parameters.append(
                str(
                    expiry
                )
            )


        parameters.append(
            max(
                1,
                min(
                    int(
                        limit
                    ),
                    5000,
                ),
            )
        )


        with self._db() as db:

            rows = db.execute(
                f"""
                SELECT *
                FROM option_legs
                WHERE {where}
                ORDER BY captured_at DESC
                LIMIT ?
                """,
                tuple(
                    parameters
                ),
            ).fetchall()


        return tuple(
            dict(
                row
            )

            for row
            in rows
        )


derivatives_history_store = (
    DerivativesHistoryStore()
)
