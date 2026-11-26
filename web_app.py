"""SigapStok Web Application: Complete Core User Flow for Hospital Pharmacy Planning."""

from __future__ import annotations

import cgi
import csv
import io
import json
import tempfile
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from sigapstok.db import Database
from sigapstok.forecasting import ForecastItemResult, run_forecast_batch
from sigapstok.ingestion import compute_ed_months_remaining, load_and_inspect_files
from sigapstok.ranking import rank_and_allocate_budget
from sigapstok.simulation import run_fair_comparison_simulation
from sigapstok.synthetic_data import export_synthetic_excel_inputs

APP_DIR = Path(__file__).parent
DATA_DIR = APP_DIR / "output"
MODEL_PATH = APP_DIR / "models" / "sigapstok_hybrid.json"


class AppState:
    """In-memory + SQLite-backed state for the active warehouse planning cycle."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.data_dir = db_path.parent if db_path else DATA_DIR
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db = Database(db_path or (self.data_dir / "sigapstok_web.db"))
        self.batch_id: int | None = None
        self.items: list[dict[str, Any]] = []
        self.forecasts: list[ForecastItemResult] = []
        self.adjustments: dict[int, tuple[float, str]] = {}
        self.warnings: list[str] = []
        self.budget_limit: float = 35_000_000.0
        self.artifact: dict[str, Any] | None = (
            json.loads(MODEL_PATH.read_text(encoding="utf-8")) if MODEL_PATH.exists() else None
        )

    def load_from_files(self, usage_path: Path, price_path: Path, budget_limit: float = 35_000_000.0) -> dict[str, Any]:
        report = load_and_inspect_files(usage_path, price_path)
        self.budget_limit = float(budget_limit)
        self.warnings = report.warnings
        self.adjustments.clear()

        self.batch_id = self.db.create_upload_batch(
            period_label="2026-10",
            budget_limit=self.budget_limit,
            usage_filename=usage_path.name,
            price_filename=price_path.name,
            row_count_usage=len(report.usage_df),
            row_count_price=len(report.price_df),
            warnings=report.warnings,
        )

        merged = report.usage_df.merge(report.price_df, on="name", how="inner")
        items: list[dict[str, Any]] = []
        for _, row in merged.iterrows():
            drug_id = self.db.upsert_drug(
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
                self.db.upsert_usage_history(
                    self.batch_id, drug_id, mc, val, float(row["physical_stock"]), float(row["loan_out_qty"])
                )
            ed_months = compute_ed_months_remaining(row["expiry_date"])
            items.append(
                {
                    "drug_id": drug_id,
                    "name": row["name"],
                    "category": row["category"],
                    "unit": row["unit"],
                    "ven_status": row["ven_status"],
                    "ven_confirmed": bool(row["ven_confirmed"]),
                    "is_doen": bool(row["is_doen"]),
                    "unit_price": float(row["unit_price"]),
                    "history": history,
                    "physical_stock": float(row["physical_stock"]),
                    "ed_months_remaining": ed_months,
                    "loan_out_qty": float(row["loan_out_qty"]),
                    "min_standby_qty": float(row.get("min_standby_qty", 0.0)),
                }
            )

        self.items = items
        self.forecasts = run_forecast_batch(items, trained_artifact=self.artifact)
        for f in self.forecasts:
            self.db.save_forecast_result(self.batch_id, f.__dict__)

        return self.get_dashboard_payload()

    def load_synthetic_demo(self, budget_limit: float = 35_000_000.0) -> dict[str, Any]:
        usage_path, price_path = export_synthetic_excel_inputs(self.data_dir)
        return self.load_from_files(usage_path, price_path, budget_limit=budget_limit)

    def adjust_quantity(self, drug_id: int, new_qty: float, reason: str) -> dict[str, Any]:
        if self.batch_id is None:
            raise ValueError("No active batch loaded.")
        self.adjustments[drug_id] = (max(0.0, float(new_qty)), reason.strip() or "Manual adjustment by pharmacy staff")
        self.db.apply_manual_adjustment(self.batch_id, drug_id, max(0.0, float(new_qty)), reason)
        return self.get_dashboard_payload()

    def update_ven(self, drug_id: int, ven_status: str) -> dict[str, Any]:
        if ven_status not in ("V", "E", "N"):
            raise ValueError("VEN status must be V, E, or N.")
        for it in self.items:
            if it["drug_id"] == drug_id:
                it["ven_status"] = ven_status
                it["ven_confirmed"] = True
                self.db.upsert_drug(
                    name=it["name"],
                    category=it["category"],
                    unit=it["unit"],
                    unit_price=it["unit_price"],
                    ven_status=ven_status,
                    ven_confirmed=True,
                    is_doen=it["is_doen"],
                    min_standby_qty=it["min_standby_qty"],
                )
                break
        self.forecasts = run_forecast_batch(self.items, trained_artifact=self.artifact)
        return self.get_dashboard_payload()

    def get_effective_forecasts(self) -> list[ForecastItemResult]:
        effective: list[ForecastItemResult] = []
        for f in self.forecasts:
            if f.drug_id in self.adjustments:
                adj_qty, _ = self.adjustments[f.drug_id]
                clone = ForecastItemResult(**{**f.__dict__, "proposed_order_qty": adj_qty})
                effective.append(clone)
            else:
                effective.append(f)
        return effective

    def get_dashboard_payload(self, budget_override: float | None = None) -> dict[str, Any]:
        if budget_override is not None:
            self.budget_limit = max(0.0, float(budget_override))
        effective = self.get_effective_forecasts()
        ranked, summary = rank_and_allocate_budget(effective, budget_limit=self.budget_limit)
        if self.batch_id is not None and ranked:
            self.db.save_ranking_results(self.batch_id, [r.__dict__ for r in ranked])

        forecast_map = {f.drug_id: f for f in effective}
        item_map = {it["drug_id"]: it for it in self.items}
        rows = []
        for r in ranked:
            f = forecast_map.get(r.drug_id)
            it = item_map.get(r.drug_id, {})
            adj = self.adjustments.get(r.drug_id)
            rows.append(
                {
                    **r.__dict__,
                    "forecast_method": f.forecast_method if f else "",
                    "forecast_monthly_qty": f.forecast_monthly_qty if f else 0.0,
                    "usable_stock_qty": f.usable_stock_qty if f else 0.0,
                    "physical_stock_qty": f.physical_stock_qty if f else 0.0,
                    "projected_expired_qty": f.projected_expired_qty if f else 0.0,
                    "xyz_class": f.xyz_class if f else "",
                    "fsn_class": f.fsn_class if f else "",
                    "is_doen": it.get("is_doen", False),
                    "ven_confirmed": it.get("ven_confirmed", False),
                    "manual_adjusted": adj is not None,
                    "adjustment_reason": adj[1] if adj else "",
                }
            )
        return {
            "batch_id": self.batch_id,
            "warnings": self.warnings,
            "summary": summary,
            "rows": rows,
            "model_metrics": self.artifact.get("test_metrics") if self.artifact else None,
        }


INDEX_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>SigapStok — RSUD Kilisuci Pharmacy Planning & Budget Ranking</title>
<style>
  :root { --primary: #0f4c81; --accent: #0ea5e9; --vital: #dc2626; --ok: #16a34a; --warn: #d97706; --bg: #f8fafc; }
  body { font-family: 'Segoe UI', system-ui, sans-serif; background: var(--bg); color: #1e293b; margin: 0; padding: 20px; }
  .container { max-width: 1280px; margin: 0 auto; }
  header { display: flex; justify-content: space-between; align-items: center; background: var(--primary); color: #fff; padding: 16px 24px; border-radius: 10px; margin-bottom: 18px; }
  header h1 { margin: 0; font-size: 1.4rem; }
  header p { margin: 4px 0 0; font-size: 0.88rem; opacity: 0.9; }
  .badge { background: rgba(255,255,255,0.18); padding: 4px 10px; border-radius: 20px; font-size: 0.78rem; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 14px; margin-bottom: 18px; }
  .card { background: #fff; border-radius: 10px; padding: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
  .card h3 { margin: 0 0 8px; font-size: 0.85rem; color: #64748b; text-transform: uppercase; letter-spacing: 0.04em; }
  .metric { font-size: 1.45rem; font-weight: 700; color: var(--primary); }
  .controls { display: flex; flex-wrap: wrap; gap: 14px; align-items: flex-end; margin-bottom: 18px; }
  label { display: block; font-size: 0.82rem; font-weight: 600; margin-bottom: 4px; color: #334155; }
  input[type="number"], input[type="file"], input[type="text"], select { padding: 7px 10px; border: 1px solid #cbd5e1; border-radius: 6px; font-size: 0.9rem; }
  button { background: var(--primary); color: #fff; border: none; padding: 9px 16px; border-radius: 6px; cursor: pointer; font-weight: 600; font-size: 0.88rem; }
  button.secondary { background: #475569; }
  button.outline { background: #fff; color: var(--primary); border: 1px solid var(--primary); }
  button:hover { opacity: 0.92; }
  table { width: 100%; border-collapse: collapse; background: #fff; border-radius: 10px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.08); font-size: 0.84rem; }
  th, td { padding: 9px 10px; border-bottom: 1px solid #e2e8f0; text-align: left; }
  th { background: #f1f5f9; color: #0f4c81; font-weight: 600; }
  .pill { padding: 2px 8px; border-radius: 12px; font-weight: 600; font-size: 0.75rem; display: inline-block; }
  .pill-V { background: #fee2e2; color: #b91c1c; }
  .pill-E { background: #dbeafe; color: #1d4ed8; }
  .pill-N { background: #f1f5f9; color: #475569; }
  .st-FULL_ORDER { color: var(--ok); font-weight: 700; }
  .st-PARTIAL_ORDER { color: var(--warn); font-weight: 700; }
  .st-EXCLUDED_OVER_BUDGET { color: var(--vital); font-weight: 700; }
  .warn-box { background: #fef3c7; border-left: 4px solid var(--warn); padding: 10px 14px; border-radius: 6px; margin-bottom: 14px; font-size: 0.85rem; display: none; }
  .tabs { display: flex; gap: 8px; margin-bottom: 14px; }
  @media print { .no-print { display: none !important; } body { padding: 0; background: #fff; } }
</style>
</head>
<body>
<div class="container">
  <header>
    <div>
      <h1>SigapStok — Pharmacy Forecasting & Vital-First Budget Ranking</h1>
      <p>RSUD Kilisuci Planning Prototype (1 Warehouse · 1 Monthly Cycle · Synthetic Demo Data)</p>
    </div>
    <span class="badge">STACK 2026 · Final Phase Prototype</span>
  </header>

  <div class="card no-print" style="margin-bottom: 18px;">
    <div class="controls">
      <div>
        <label>1. Usage & Stock Export (.xlsx/.csv)</label>
        <input type="file" id="usageFile" accept=".xlsx,.csv"/>
      </div>
      <div>
        <label>2. Price & DOEN/VEN Sheet (.xlsx/.csv)</label>
        <input type="file" id="priceFile" accept=".xlsx,.csv"/>
      </div>
      <button onclick="uploadFiles()">Upload & Analyze</button>
      <button class="secondary" onclick="loadDemo()">Load RSUD Synthetic Demo</button>
      <button class="outline" onclick="runSimulation()">Run 6-Month Fair Simulation</button>
      <button class="outline" onclick="window.open('/api/export_csv', '_blank')">Export Procurement CSV</button>
      <button class="outline" onclick="window.print()">Print One-Page Report</button>
    </div>
    <div style="display:flex; align-items:center; gap:14px; margin-top:8px;">
      <label style="margin:0;">Monthly Budget Cap (IDR):</label>
      <input type="range" id="budgetSlider" min="10000000" max="60000000" step="1000000" value="35000000" style="flex:1;" oninput="onBudgetSlide(this.value)"/>
      <input type="number" id="budgetInput" value="35000000" step="500000" style="width:140px;"/>
      <button onclick="applyBudget()">Apply Budget</button>
    </div>
  </div>

  <div id="warnBox" class="warn-box"></div>

  <div class="grid">
    <div class="card"><h3>Budget Limit</h3><div class="metric" id="mBudget">-</div></div>
    <div class="card"><h3>Total Ideal Need</h3><div class="metric" id="mNeed">-</div></div>
    <div class="card"><h3>Allocated Spend</h3><div class="metric" id="mAlloc">-</div></div>
    <div class="card"><h3>Vital Drugs Excluded</h3><div class="metric" id="mVitalExcl">-</div></div>
    <div class="card"><h3>Excluded Items</h3><div class="metric" id="mExcl">-</div></div>
  </div>

  <div id="simBox" class="card" style="margin-bottom:18px; display:none;">
    <h3>6-Month Fair Comparison Simulation (Identical Budget, Demand Stream & FEFO Expiry)</h3>
    <table id="simTable"><thead><tr><th>Strategy</th><th>Vital Stockout Days</th><th>Total Stockout Days</th><th>Expired Units</th><th>Fill Rate</th><th>Vital Budget Share</th></tr></thead><tbody></tbody></table>
  </div>

  <div class="card">
    <h3>One-Page Vital-First Procurement Ranking</h3>
    <table>
      <thead>
        <tr>
          <th>Rank</th><th>Drug Name</th><th>VEN</th><th>Pattern / ABC</th>
          <th>Usable Stock</th><th>Days Supply</th><th>Proposed Qty</th>
          <th>Allocated</th><th>Cost (IDR)</th><th>Status</th><th>Days w/o Stock</th><th>Reason / Override</th>
        </tr>
      </thead>
      <tbody id="rankBody"></tbody>
    </table>
  </div>
</div>

<script>
const fmtIDR = n => 'Rp ' + Math.round(n).toLocaleString('id-ID');

function onBudgetSlide(val) {
  document.getElementById('budgetInput').value = val;
}

async function loadDemo() {
  const b = document.getElementById('budgetInput').value;
  const res = await fetch('/api/demo?budget=' + encodeURIComponent(b), {method: 'POST'});
  renderDashboard(await res.json());
}

async function uploadFiles() {
  const u = document.getElementById('usageFile').files[0];
  const p = document.getElementById('priceFile').files[0];
  if (!u || !p) { alert('Select both usage/stock and price spreadsheets, or click Load RSUD Synthetic Demo.'); return; }
  const fd = new FormData();
  fd.append('usage_file', u);
  fd.append('price_file', p);
  fd.append('budget', document.getElementById('budgetInput').value);
  const res = await fetch('/api/upload', {method: 'POST', body: fd});
  const data = await res.json();
  if (data.error) { alert(data.error); return; }
  renderDashboard(data);
}

async function applyBudget() {
  const b = document.getElementById('budgetInput').value;
  document.getElementById('budgetSlider').value = b;
  const res = await fetch('/api/rank?budget=' + encodeURIComponent(b));
  renderDashboard(await res.json());
}

async function overrideQty(drugId, oldQty) {
  const val = prompt('Enter adjusted order quantity:', oldQty);
  if (val === null) return;
  const reason = prompt('Enter reason for adjustment (recorded in audit trail):', 'Clinical team review');
  const res = await fetch('/api/adjust', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({drug_id: drugId, new_qty: Number(val), reason: reason || ''})
  });
  renderDashboard(await res.json());
}

async function changeVen(drugId, ven) {
  const res = await fetch('/api/ven', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({drug_id: drugId, ven_status: ven})
  });
  renderDashboard(await res.json());
}

async function runSimulation() {
  const b = document.getElementById('budgetInput').value;
  const res = await fetch('/api/simulate?budget=' + encodeURIComponent(b));
  const data = await res.json();
  const tbody = document.querySelector('#simTable tbody');
  tbody.innerHTML = data.results.map(r => `
    <tr>
      <td><strong>${r.strategy_name}</strong></td>
      <td>${r.vital_stockout_days}</td>
      <td>${r.total_stockout_days}</td>
      <td>${r.expired_units}</td>
      <td>${r.fill_rate_pct}%</td>
      <td>${r.vital_budget_share_pct}%</td>
    </tr>
  `).join('');
  document.getElementById('simBox').style.display = 'block';
}

function renderDashboard(data) {
  const s = data.summary;
  document.getElementById('mBudget').textContent = fmtIDR(s.budget_limit);
  document.getElementById('mNeed').textContent = fmtIDR(s.total_requested_cost);
  document.getElementById('mAlloc').textContent = fmtIDR(s.total_allocated_cost);
  document.getElementById('mVitalExcl').textContent = s.vital_excluded;
  document.getElementById('mExcl').textContent = s.excluded_orders;

  const wb = document.getElementById('warnBox');
  if (data.warnings && data.warnings.length > 0) {
    wb.style.display = 'block';
    wb.innerHTML = '<strong>Inspection Notes:</strong> ' + data.warnings.join(' | ');
  } else {
    wb.style.display = 'none';
  }

  const tbody = document.getElementById('rankBody');
  tbody.innerHTML = data.rows.map(r => `
    <tr>
      <td>${r.priority_rank || '-'}</td>
      <td><strong>${r.name}</strong>${r.is_doen ? ' <span class="badge" style="background:#e0f2fe;color:#0369a1;">DOEN</span>' : ''}</td>
      <td>
        <select class="pill pill-${r.ven_status}" onchange="changeVen(${r.drug_id}, this.value)">
          <option value="V" ${r.ven_status==='V'?'selected':''}>V (Vital)</option>
          <option value="E" ${r.ven_status==='E'?'selected':''}>E (Essential)</option>
          <option value="N" ${r.ven_status==='N'?'selected':''}>N (Non-Ess)</option>
        </select>
      </td>
      <td>${r.demand_pattern} / ${r.abc_class}${r.xyz_class}</td>
      <td>${r.usable_stock_qty} ${r.projected_expired_qty > 0 ? '<br><small style="color:#b91c1c;">(' + r.projected_expired_qty + ' ED risk)</small>' : ''}</td>
      <td>${r.days_of_supply} d</td>
      <td>${r.requested_qty} <button class="outline no-print" style="padding:2px 6px;font-size:0.72rem;" onclick="overrideQty(${r.drug_id}, ${r.requested_qty})">Edit</button></td>
      <td>${r.allocated_qty}</td>
      <td>${fmtIDR(r.allocated_cost)}</td>
      <td class="st-${r.allocation_status}">${r.allocation_status}</td>
      <td><strong>${r.expected_days_without_stock} d</strong></td>
      <td><small>${r.explanation_note}${r.manual_adjusted ? ' [Adjusted: ' + r.adjustment_reason + ']' : ''}</small></td>
    </tr>
  `).join('');
}

loadDemo();
</script>
</body>
</html>
"""


def make_handler(state: AppState) -> type[BaseHTTPRequestHandler]:
    class SigapStokHandler(BaseHTTPRequestHandler):
        def _send_json(self, payload: Any, status: int = 200) -> None:
            raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/":
                body = INDEX_HTML.encode("utf-8")
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            if parsed.path == "/api/health":
                self._send_json({"status": "ok", "batch_id": state.batch_id})
                return

            if parsed.path == "/api/rank":
                qs = dict(p.split("=", 1) for p in parsed.query.split("&") if "=" in p)
                budget = float(qs["budget"]) if "budget" in qs else None
                self._send_json(state.get_dashboard_payload(budget_override=budget))
                return

            if parsed.path == "/api/simulate":
                qs = dict(p.split("=", 1) for p in parsed.query.split("&") if "=" in p)
                budget = float(qs.get("budget", state.budget_limit))
                results = run_fair_comparison_simulation(
                    monthly_budget_cap=budget, num_months=6, trained_artifact=state.artifact
                )
                self._send_json({"results": results})
                return

            if parsed.path == "/api/export_csv":
                data = state.get_dashboard_payload()
                buf = io.StringIO()
                writer = csv.writer(buf)
                writer.writerow(["Rank", "Drug Name", "VEN", "ABC", "Pattern", "Requested", "Allocated", "Cost IDR", "Status", "Expected Days Without Stock", "Note"])
                for r in data["rows"]:
                    writer.writerow([
                        r["priority_rank"], r["name"], r["ven_status"], r["abc_class"],
                        r["demand_pattern"], r["requested_qty"], r["allocated_qty"],
                        r["allocated_cost"], r["allocation_status"], r["expected_days_without_stock"],
                        r["explanation_note"],
                    ])
                raw = buf.getvalue().encode("utf-8")
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/csv; charset=utf-8")
                self.send_header("Content-Disposition", "attachment; filename=sigapstok_ranking.csv")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
                return

            self.send_error(HTTPStatus.NOT_FOUND)

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            try:
                if parsed.path == "/api/demo":
                    qs = dict(p.split("=", 1) for p in parsed.query.split("&") if "=" in p)
                    budget = float(qs.get("budget", state.budget_limit))
                    self._send_json(state.load_synthetic_demo(budget_limit=budget))
                    return

                if parsed.path == "/api/upload":
                    form = cgi.FieldStorage(
                        fp=self.rfile,
                        headers=self.headers,
                        environ={"REQUEST_METHOD": "POST", "CONTENT_TYPE": self.headers.get("Content-Type", "")},
                    )
                    u_item = form["usage_file"]
                    p_item = form["price_file"]
                    budget = float(form.getvalue("budget", str(state.budget_limit)))
                    with tempfile.TemporaryDirectory() as tmp:
                        u_path = Path(tmp) / Path(u_item.filename or "usage.xlsx").name
                        p_path = Path(tmp) / Path(p_item.filename or "price.xlsx").name
                        u_path.write_bytes(u_item.file.read())
                        p_path.write_bytes(p_item.file.read())
                        payload = state.load_from_files(u_path, p_path, budget_limit=budget)
                    self._send_json(payload)
                    return

                length = int(self.headers.get("Content-Length", "0"))
                body = json.loads(self.rfile.read(length).decode("utf-8")) if length > 0 else {}

                if parsed.path == "/api/adjust":
                    self._send_json(state.adjust_quantity(int(body["drug_id"]), float(body["new_qty"]), str(body.get("reason", ""))))
                    return

                if parsed.path == "/api/ven":
                    self._send_json(state.update_ven(int(body["drug_id"]), str(body["ven_status"])))
                    return

                self.send_error(HTTPStatus.NOT_FOUND)
            except Exception as exc:
                self._send_json({"error": str(exc)}, status=400)

        def log_message(self, format: str, *args: Any) -> None:
            return

    return SigapStokHandler


def run_server(host: str = "127.0.0.1", port: int = 8000) -> None:
    state = AppState()
    server = ThreadingHTTPServer((host, port), make_handler(state))
    print(f"SigapStok Web App running at http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run_server()
