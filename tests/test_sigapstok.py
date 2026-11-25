"""Unit and integration tests for SigapStok ingestion, forecasting, ranking, and simulation."""

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from sigapstok.db import Database
from sigapstok.forecasting import (
    classify_demand_pattern,
    compute_ed_usable_stock,
    forecast_sba,
    run_forecast_batch,
)
from sigapstok.ingestion import ColumnValidationError, validate_price_ven_df, validate_usage_stock_df
from sigapstok.ranking import rank_and_allocate_budget
from sigapstok.simulation import run_fair_comparison_simulation
from sigapstok.trainer import train_and_evaluate_models


class TestSigapStok(unittest.TestCase):
    def test_column_validation_rejects_missing_required(self) -> None:
        bad_df = pd.DataFrame({"KATEGORI": ["Obat"], "SATUAN": ["Tab"]})
        with self.assertRaises(ColumnValidationError):
            validate_usage_stock_df(bad_df)

    def test_column_validation_and_doen_suggestion(self) -> None:
        usage_df = pd.DataFrame(
            {
                "NAMA": ["Aciclovir 200 mg Tablet"],
                "KATEGORI": ["Farmasi - Obat - Tablet"],
                "SATUAN": ["Tablet"],
                "STOK FISIK": [60],
                "2026-07": [180],
                "2026-08": [200],
                "2026-09": [190],
            }
        )
        price_df = pd.DataFrame(
            {
                "Nama obat dari daftar Anda": ["Aciclovir 200 mg Tablet"],
                "HARGA SATUAN": [650],
                "Hasil pencocokan DOEN": ["YA - zat aktif tercantum di DOEN"],
            }
        )
        u_clean, months, _ = validate_usage_stock_df(usage_df)
        p_clean, w2 = validate_price_ven_df(price_df)
        self.assertEqual(len(months), 3)
        self.assertEqual(p_clean.loc[0, "ven_status"], "E")
        self.assertTrue(bool(p_clean.loc[0, "is_doen"]))
        self.assertTrue(len(w2) > 0)

    def test_sba_intermittent_vital_does_not_drop_to_zero(self) -> None:
        # Rare life-saving drug with 0 usage in the latest month
        history = [6, 0, 0, 5, 0, 0, 6, 0, 0, 5, 0, 0]
        pattern, adi, _ = classify_demand_pattern(history)
        self.assertEqual(pattern, "INTERMITTENT")
        self.assertGreaterEqual(adi, 1.32)
        sba_est = forecast_sba(history)
        self.assertGreater(sba_est, 1.0)

    def test_ed_usable_stock_caps_expiring_excess(self) -> None:
        # Mimics Acarbose 100 mg: 4446 stock, ~520.8/mo, 6 months to ED -> 3124.8 usable, 1321.2 expired
        usable, expired = compute_ed_usable_stock(
            physical_stock=4446.0,
            monthly_forecast=520.8,
            ed_months_remaining=6.0,
        )
        self.assertAlmostEqual(usable, 3124.8, places=1)
        self.assertAlmostEqual(expired, 1321.2, places=1)

    def test_budget_ranking_prioritizes_vital_and_reports_excluded_days(self) -> None:
        items = [
            {
                "drug_id": 1,
                "name": "Epinefrin Vital",
                "ven_status": "V",
                "unit_price": 10000,
                "history": [5, 0, 5, 0, 5, 0],
                "physical_stock": 0,
                "ed_months_remaining": 12.0,
                "min_standby_qty": 5,
            },
            {
                "drug_id": 2,
                "name": "Suplemen Non-Esensial",
                "ven_status": "N",
                "unit_price": 50000,
                "history": [20, 20, 20, 20, 20, 20],
                "physical_stock": 0,
                "ed_months_remaining": 12.0,
                "min_standby_qty": 0,
            },
        ]
        forecasts = run_forecast_batch(items)
        # Tight budget enough only for Vital drug
        ranked, summary = rank_and_allocate_budget(forecasts, budget_limit=150_000)
        self.assertEqual(ranked[0].name, "Epinefrin Vital")
        self.assertEqual(ranked[0].allocation_status, "FULL_ORDER")
        self.assertEqual(ranked[1].name, "Suplemen Non-Esensial")
        self.assertEqual(ranked[1].allocation_status, "EXCLUDED_OVER_BUDGET")
        self.assertGreater(ranked[1].expected_days_without_stock, 0)
        self.assertEqual(summary["vital_excluded"], 0)

    def test_database_history_storage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Database(Path(tmp) / "test.db")
            drug_id = db.upsert_drug("Parasetamol 500 mg", "Tablet", "Tablet", 250.0, "E", True, True)
            batch_id = db.create_upload_batch("2026-10", 10_000_000, "u.xlsx", "p.xlsx", 1, 1, [])
            db.upsert_usage_history(batch_id, drug_id, "2026-08", 500.0)
            db.upsert_usage_history(batch_id, drug_id, "2026-09", 620.0)
            series = db.get_usage_series(drug_id)
            self.assertEqual(series, [500.0, 620.0])
            db.close()

    def test_fair_simulation_outperforms_baseline_on_vital_stockout(self) -> None:
        results = run_fair_comparison_simulation(monthly_budget_cap=30_000_000.0, num_months=6, seed=42)
        by_name = {r["strategy_name"]: r for r in results}
        self.assertLessEqual(
            by_name["SigapStok"]["vital_stockout_days"],
            by_name["RSUD_Current_Formula"]["vital_stockout_days"],
        )

    def test_epoch_training_reduces_loss_and_beats_baseline_mae(self) -> None:
        summary = train_and_evaluate_models(epochs=100, seed=42)
        self.assertLess(summary.final_train_loss, summary.epoch_history[0]["train_loss"])
        hybrid_mae = summary.test_metrics["SigapStok_Trained_Hybrid"]["MAE"]
        rsud_mae = summary.test_metrics["RSUD_1Mo_Plus_10Pct"]["MAE"]
        self.assertLess(hybrid_mae, rsud_mae)


if __name__ == "__main__":
    unittest.main()
