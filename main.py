"""CLI entrypoint for SigapStok forecasting, budget ranking, and fair comparison simulation."""

from __future__ import annotations

import argparse
from pathlib import Path

from sigapstok.db import Database
from sigapstok.forecasting import run_forecast_batch
from sigapstok.ingestion import compute_ed_months_remaining, load_and_inspect_files
from sigapstok.ranking import rank_and_allocate_budget, render_one_page_report
from sigapstok.simulation import run_fair_comparison_simulation
from sigapstok.synthetic_data import export_synthetic_excel_inputs


def cmd_demo(args: argparse.Namespace) -> None:
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    db = Database(out_dir / "sigapstok.db")

    usage_path, price_path = export_synthetic_excel_inputs(out_dir)
    report = load_and_inspect_files(usage_path, price_path)

    batch_id = db.create_upload_batch(
        period_label="2026-10",
        budget_limit=args.budget,
        usage_filename=usage_path.name,
        price_filename=price_path.name,
        row_count_usage=len(report.usage_df),
        row_count_price=len(report.price_df),
        warnings=report.warnings,
    )

    merged = report.usage_df.merge(report.price_df, on="name", how="inner")
    items = []
    for _, row in merged.iterrows():
        drug_id = db.upsert_drug(
            name=row["name"],
            category=row["category"],
            unit=row["unit"],
            unit_price=float(row["unit_price"]),
            ven_status=row["ven_status"],
            ven_confirmed=bool(row["ven_confirmed"]),
            is_doen=bool(row["is_doen"]),
            doen_match_method=row.get("doen_match_method") or None,
            generic_name=row.get("generic_name") or None,
            min_standby_qty=float(row.get("min_standby_qty", 0.0)),
        )
        history = [float(row[mc]) for mc in report.month_columns]
        for mc, val in zip(report.month_columns, history):
            db.upsert_usage_history(batch_id, drug_id, mc, val, float(row["physical_stock"]), float(row["loan_out_qty"]))

        ed_months = compute_ed_months_remaining(row["expiry_date"])
        items.append(
            {
                "drug_id": drug_id,
                "name": row["name"],
                "ven_status": row["ven_status"],
                "unit_price": float(row["unit_price"]),
                "history": history,
                "physical_stock": float(row["physical_stock"]),
                "ed_months_remaining": ed_months,
                "loan_out_qty": float(row["loan_out_qty"]),
                "min_standby_qty": float(row.get("min_standby_qty", 0.0)),
            }
        )

    forecasts = run_forecast_batch(items)
    for f in forecasts:
        db.save_forecast_result(batch_id, f.__dict__)

    ranked, summary = rank_and_allocate_budget(forecasts, budget_limit=args.budget)
    db.save_ranking_results(batch_id, [r.__dict__ for r in ranked])

    md_report = render_one_page_report("Oktober 2026", ranked, summary)
    report_path = out_dir / "one_page_ranking_report.md"
    report_path.write_text(md_report, encoding="utf-8")
    print(md_report)
    print(f"\n[Saved] Database: {out_dir / 'sigapstok.db'} | Report: {report_path}")
    db.close()


def cmd_simulate(args: argparse.Namespace) -> None:
    results = run_fair_comparison_simulation(monthly_budget_cap=args.budget, num_months=args.months)
    print("=== Simulasi Perbandingan Adil (Anggaran & Permintaan Identik) ===")
    print(f"Budget Cap: Rp {args.budget:,.0f}/bulan | Durasi: {args.months} bulan\n")
    for r in results:
        print(
            f"- {r['strategy_name']:22s} | Vital Stockout Days: {r['vital_stockout_days']:3d} | "
            f"Total Stockout Days: {r['total_stockout_days']:3d} | Expired Units: {r['expired_units']:7.1f} | "
            f"Fill Rate: {r['fill_rate_pct']:6.2f}% | Vital Budget Share: {r['vital_budget_share_pct']:5.2f}%"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="SigapStok Pharmacy Forecasting & Budget Ranking CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_demo = sub.add_parser("demo", help="Run synthetic ingestion, forecasting, DB storage, and ranking report")
    p_demo.add_argument("--budget", type=float, default=35_000_000.0, help="Monthly budget cap in IDR")
    p_demo.add_argument("--output-dir", default="output", help="Directory for sample Excel, DB, and report")
    p_demo.set_defaults(func=cmd_demo)

    p_sim = sub.add_parser("simulate", help="Run fair 6-month comparison simulation")
    p_sim.add_argument("--budget", type=float, default=35_000_000.0, help="Monthly budget cap in IDR")
    p_sim.add_argument("--months", type=int, default=6, help="Number of simulated months")
    p_sim.set_defaults(func=cmd_simulate)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
