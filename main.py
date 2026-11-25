"""CLI entrypoint for SigapStok forecasting, training, budget ranking, simulation, and reporting."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from sigapstok.db import Database
from sigapstok.forecasting import run_forecast_batch
from sigapstok.ingestion import compute_ed_months_remaining, load_and_inspect_files
from sigapstok.ranking import rank_and_allocate_budget, render_one_page_report
from sigapstok.report_builder import build_full_laporan, build_stack2026_proposal_md, markdown_to_a4_html
from sigapstok.simulation import run_fair_comparison_simulation
from sigapstok.synthetic_data import export_synthetic_excel_inputs
from sigapstok.trainer import train_and_evaluate_models


def _prepare_demo_items(out_dir: Path, budget: float, db: Database) -> tuple[int, list[dict]]:
    usage_path, price_path = export_synthetic_excel_inputs(out_dir)
    report = load_and_inspect_files(usage_path, price_path)

    batch_id = db.create_upload_batch(
        period_label="2026-10",
        budget_limit=budget,
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
    return batch_id, items


def cmd_demo(args: argparse.Namespace) -> None:
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    db = Database(out_dir / "sigapstok.db")

    artifact = None
    model_path = Path(args.model_path)
    if model_path.exists():
        artifact = json.loads(model_path.read_text(encoding="utf-8"))

    batch_id, items = _prepare_demo_items(out_dir, args.budget, db)
    forecasts = run_forecast_batch(items, trained_artifact=artifact)
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


def cmd_train(args: argparse.Namespace) -> None:
    artifact_path = Path(args.model_path)
    summary = train_and_evaluate_models(epochs=args.epochs, save_artifact_path=artifact_path)
    print(f"=== Epoch Training Complete ({summary.epochs} epochs, best epoch: {summary.best_epoch}) ===")
    for e in summary.epoch_history:
        print(f"Epoch {e['epoch']:3d} | train_loss: {e['train_loss']:.5f} | val_loss: {e['val_loss']:.5f}")
    print("\n=== Held-Out Test Set Accuracy (Months 20-24) ===")
    for name, m in summary.test_metrics.items():
        print(
            f"- {name:26s} | MAE: {m['MAE']:6.2f} | RMSE: {m['RMSE']:6.2f} | "
            f"sMAPE: {m['sMAPE_pct']:5.2f}% | Accuracy: {m['Accuracy_pct']:5.2f}%"
        )
    print(f"\n[Saved Model Artifact] {artifact_path}")


def cmd_simulate(args: argparse.Namespace) -> None:
    artifact = None
    model_path = Path(args.model_path)
    if model_path.exists():
        artifact = json.loads(model_path.read_text(encoding="utf-8"))

    results = run_fair_comparison_simulation(
        monthly_budget_cap=args.budget,
        num_months=args.months,
        trained_artifact=artifact,
    )
    print("=== Simulasi Perbandingan Adil (Anggaran & Permintaan Identik) ===")
    print(f"Budget Cap: Rp {args.budget:,.0f}/bulan | Durasi: {args.months} bulan\n")
    for r in results:
        print(
            f"- {r['strategy_name']:22s} | Vital Stockout Days: {r['vital_stockout_days']:3d} | "
            f"Total Stockout Days: {r['total_stockout_days']:3d} | Expired Units: {r['expired_units']:7.1f} | "
            f"Fill Rate: {r['fill_rate_pct']:6.2f}% | Vital Budget Share: {r['vital_budget_share_pct']:5.2f}%"
        )


def cmd_report(args: argparse.Namespace) -> None:
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    model_path = Path(args.model_path)

    # 1. Train & save model artifact (fallback to in-memory if file is locked)
    try:
        training = train_and_evaluate_models(epochs=args.epochs, save_artifact_path=model_path)
    except PermissionError:
        training = train_and_evaluate_models(epochs=args.epochs, save_artifact_path=None)
    artifact = json.loads(model_path.read_text(encoding="utf-8")) if model_path.exists() else None

    # 2. Run ranking demo with trained model
    db = Database(out_dir / "sigapstok.db")
    batch_id, items = _prepare_demo_items(out_dir, args.demo_budget, db)
    forecasts = run_forecast_batch(items, trained_artifact=artifact)
    for f in forecasts:
        db.save_forecast_result(batch_id, f.__dict__)
    ranked, budget_summary = rank_and_allocate_budget(forecasts, budget_limit=args.demo_budget)
    db.save_ranking_results(batch_id, [r.__dict__ for r in ranked])

    # 3. Run fair simulation across all 4 strategies
    sim_results = run_fair_comparison_simulation(
        monthly_budget_cap=args.sim_budget,
        num_months=args.months,
        trained_artifact=artifact,
    )
    for sr in sim_results:
        db.save_simulation_run("Laporan_6Mo_Comparison", args.months, args.sim_budget, sr)
    db.close()

    # 4. Generate complete Laporan Markdown + STACK 2026 Semifinal Proposal (MD & A4 HTML)
    laporan_text = build_full_laporan(
        training=training,
        sim_results=sim_results,
        ranked_rows=ranked,
        budget_summary=budget_summary,
        budget_cap_sim=args.sim_budget,
        sim_months=args.months,
    )
    laporan_path = Path(args.laporan_path)
    laporan_path.parent.mkdir(parents=True, exist_ok=True)
    laporan_path.write_text(laporan_text, encoding="utf-8")

    proposal_md = build_stack2026_proposal_md(
        training=training,
        sim_results=sim_results,
        ranked_rows=ranked,
        budget_summary=budget_summary,
        budget_cap_sim=args.sim_budget,
        sim_months=args.months,
    )
    proposal_md_path = laporan_path.parent / "STACK2026_SEMIFINAL_PROPOSAL.md"
    proposal_html_path = laporan_path.parent / "STACK2026_SEMIFINAL_PROPOSAL.html"
    proposal_md_path.write_text(proposal_md, encoding="utf-8")
    proposal_html_path.write_text(markdown_to_a4_html(proposal_md), encoding="utf-8")

    print(f"[Generated Laporan]  {laporan_path}")
    print(f"[Generated Proposal] {proposal_md_path}")
    print(f"[Generated A4 HTML]  {proposal_html_path}")
    print(f"[Saved Model]        {model_path}")
    print("\n--- Test Set Accuracy Summary ---")
    for name, m in training.test_metrics.items():
        print(f"  {name:26s} -> MAE: {m['MAE']:6.2f} | Accuracy: {m['Accuracy_pct']:5.2f}%")
    print("\n--- Simulation Summary ---")
    for r in sim_results:
        print(
            f"  {r['strategy_name']:22s} -> Vital Stockout: {r['vital_stockout_days']:3d}d | "
            f"Total Stockout: {r['total_stockout_days']:3d}d | Fill Rate: {r['fill_rate_pct']:6.2f}%"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="SigapStok Pharmacy Forecasting, Training & Budget Ranking CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_demo = sub.add_parser("demo", help="Run synthetic ingestion, forecasting, DB storage, and ranking report")
    p_demo.add_argument("--budget", type=float, default=35_000_000.0)
    p_demo.add_argument("--output-dir", default="output")
    p_demo.add_argument("--model-path", default="models/sigapstok_hybrid.json")
    p_demo.set_defaults(func=cmd_demo)

    p_train = sub.add_parser("train", help="Run epoch training and evaluate held-out forecast accuracy")
    p_train.add_argument("--epochs", type=int, default=160)
    p_train.add_argument("--model-path", default="models/sigapstok_hybrid.json")
    p_train.set_defaults(func=cmd_train)

    p_sim = sub.add_parser("simulate", help="Run fair 6-month comparison simulation")
    p_sim.add_argument("--budget", type=float, default=30_000_000.0)
    p_sim.add_argument("--months", type=int, default=6)
    p_sim.add_argument("--model-path", default="models/sigapstok_hybrid.json")
    p_sim.set_defaults(func=cmd_simulate)

    p_rep = sub.add_parser("report", help="Train model, run simulation, and write full LAPORAN_SIGAPSTOK.md")
    p_rep.add_argument("--epochs", type=int, default=160)
    p_rep.add_argument("--demo-budget", type=float, default=35_000_000.0)
    p_rep.add_argument("--sim-budget", type=float, default=30_000_000.0)
    p_rep.add_argument("--months", type=int, default=6)
    p_rep.add_argument("--output-dir", default="output")
    p_rep.add_argument("--model-path", default="models/sigapstok_hybrid.json")
    p_rep.add_argument("--laporan-path", default="docs/LAPORAN_SIGAPSTOK.md")
    p_rep.set_defaults(func=cmd_report)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
