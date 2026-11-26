"""Database persistence and history management for SigapStok."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable, Optional

SCHEMA_PATH = Path(__file__).parent / "schema.sql"


class Database:
    """SQLite database manager storing drugs, usage history, forecasts, and rankings."""

    def __init__(self, db_path: str | Path = "sigapstok.db") -> None:
        self.db_path = Path(db_path)
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.init_schema()

    def init_schema(self) -> None:
        schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
        self.conn.executescript(schema_sql)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def upsert_drug(
        self,
        name: str,
        category: str,
        unit: str,
        unit_price: float,
        ven_status: str = "E",
        ven_confirmed: bool = False,
        is_doen: bool = False,
        doen_match_method: Optional[str] = None,
        generic_name: Optional[str] = None,
        min_standby_qty: float = 0.0,
    ) -> int:
        cur = self.conn.cursor()
        cur.execute("SELECT id FROM drugs WHERE name = ?", (name,))
        row = cur.fetchone()
        if row:
            drug_id = int(row["id"])
            cur.execute(
                """
                UPDATE drugs
                SET category = ?, unit = ?, unit_price = ?, ven_status = ?,
                    ven_confirmed = ?, is_doen = ?, doen_match_method = COALESCE(?, doen_match_method),
                    generic_name = COALESCE(?, generic_name), min_standby_qty = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    category,
                    unit,
                    unit_price,
                    ven_status,
                    int(ven_confirmed),
                    int(is_doen),
                    doen_match_method,
                    generic_name,
                    min_standby_qty,
                    drug_id,
                ),
            )
            self.conn.commit()
            return drug_id

        cur.execute(
            """
            INSERT INTO drugs (
                name, generic_name, category, unit, ven_status, ven_confirmed,
                is_doen, doen_match_method, unit_price, min_standby_qty
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                name,
                generic_name,
                category,
                unit,
                ven_status,
                int(ven_confirmed),
                int(is_doen),
                doen_match_method,
                unit_price,
                min_standby_qty,
            ),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def create_upload_batch(
        self,
        period_label: str,
        budget_limit: float,
        usage_filename: str,
        price_filename: str,
        row_count_usage: int,
        row_count_price: int,
        warnings: list[str],
    ) -> int:
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO upload_batches (
                period_label, budget_limit, usage_filename, price_filename,
                row_count_usage, row_count_price, validation_warnings
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                period_label,
                budget_limit,
                usage_filename,
                price_filename,
                row_count_usage,
                row_count_price,
                json.dumps(warnings, ensure_ascii=False),
            ),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def upsert_usage_history(
        self,
        batch_id: int,
        drug_id: int,
        period_month: str,
        qty_used: float,
        stock_end: float = 0.0,
        loan_out_qty: float = 0.0,
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO monthly_usage_history (batch_id, drug_id, period_month, qty_used, stock_end, loan_out_qty)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(drug_id, period_month) DO UPDATE SET
                batch_id = excluded.batch_id,
                qty_used = excluded.qty_used,
                stock_end = excluded.stock_end,
                loan_out_qty = excluded.loan_out_qty
            """,
            (batch_id, drug_id, period_month, qty_used, stock_end, loan_out_qty),
        )
        self.conn.commit()

    def get_usage_series(self, drug_id: int) -> list[float]:
        rows = self.conn.execute(
            "SELECT qty_used FROM monthly_usage_history WHERE drug_id = ? ORDER BY period_month ASC",
            (drug_id,),
        ).fetchall()
        return [float(r["qty_used"]) for r in rows]

    def save_stock_ed_snapshot(
        self,
        batch_id: int,
        drug_id: int,
        physical_stock: float,
        expiry_date: Optional[str],
        ed_months_remaining: Optional[float],
        usable_stock: float,
        projected_expired_qty: float,
        loan_out_qty: float = 0.0,
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO stock_batches_ed (
                batch_id, drug_id, physical_stock, expiry_date, ed_months_remaining,
                usable_stock, projected_expired_qty, loan_out_qty
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                batch_id,
                drug_id,
                physical_stock,
                expiry_date,
                ed_months_remaining,
                usable_stock,
                projected_expired_qty,
                loan_out_qty,
            ),
        )
        self.conn.commit()

    def save_forecast_result(self, batch_id: int, record: dict[str, Any]) -> None:
        self.conn.execute(
            """
            INSERT INTO forecast_results (
                batch_id, drug_id, lookback_months, adi, cv2, demand_pattern,
                abc_class, xyz_class, fsn_class, abc_ven_matrix, forecast_method,
                forecast_monthly_qty, safety_stock_qty, target_stock_qty,
                usable_stock_qty, proposed_order_qty, manual_adjusted_qty, adjustment_reason
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                batch_id,
                record["drug_id"],
                record["lookback_months"],
                record["adi"],
                record["cv2"],
                record["demand_pattern"],
                record["abc_class"],
                record["xyz_class"],
                record["fsn_class"],
                record["abc_ven_matrix"],
                record["forecast_method"],
                record["forecast_monthly_qty"],
                record["safety_stock_qty"],
                record["target_stock_qty"],
                record["usable_stock_qty"],
                record["proposed_order_qty"],
                record.get("manual_adjusted_qty"),
                record.get("adjustment_reason"),
            ),
        )
        self.conn.commit()

    def save_ranking_results(self, batch_id: int, rows: Iterable[dict[str, Any]]) -> None:
        for r in rows:
            self.conn.execute(
                """
                INSERT INTO budget_ranking_results (
                    batch_id, drug_id, priority_rank, ven_status, abc_class,
                    days_of_supply, expected_days_without_stock, requested_qty,
                    allocated_qty, allocated_cost, allocation_status, explanation_note
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    batch_id,
                    r["drug_id"],
                    r["priority_rank"],
                    r["ven_status"],
                    r["abc_class"],
                    r["days_of_supply"],
                    r["expected_days_without_stock"],
                    r["requested_qty"],
                    r["allocated_qty"],
                    r["allocated_cost"],
                    r["allocation_status"],
                    r["explanation_note"],
                ),
            )
        self.conn.commit()

    def save_simulation_run(self, run_label: str, num_months: int, budget_cap: float, metrics: dict[str, Any]) -> None:
        self.conn.execute(
            """
            INSERT INTO simulation_runs (
                run_label, num_months, monthly_budget_cap, strategy_name,
                vital_stockout_days, total_stockout_days, expired_units,
                expired_value_idr, fill_rate_pct, vital_budget_share_pct
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_label,
                num_months,
                budget_cap,
                metrics["strategy_name"],
                metrics["vital_stockout_days"],
                metrics["total_stockout_days"],
                metrics["expired_units"],
                metrics["expired_value_idr"],
                metrics["fill_rate_pct"],
                metrics["vital_budget_share_pct"],
            ),
        )
        self.conn.commit()

    def apply_manual_adjustment(self, batch_id: int, drug_id: int, new_qty: float, reason: str) -> None:
        """Allow pharmacy staff to adjust a proposed order quantity with a recorded reason."""
        self.conn.execute(
            """
            UPDATE forecast_results
            SET manual_adjusted_qty = ?, adjustment_reason = ?
            WHERE batch_id = ? AND drug_id = ?
            """,
            (new_qty, reason, batch_id, drug_id),
        )
        self.conn.commit()
