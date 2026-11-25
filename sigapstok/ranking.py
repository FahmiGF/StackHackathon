"""Section 4.4 Budget Ranking Logic & One-Page Report Generation for SigapStok."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable

from sigapstok.forecasting import ForecastItemResult

VEN_PRIORITY_WEIGHT = {"V": 0, "E": 1, "N": 2}
ABC_MATRIX_WEIGHT = {
    "AV": 0, "BV": 1, "CV": 2,
    "AE": 3, "BE": 4, "CE": 5,
    "AN": 6, "BN": 7, "CN": 8,
}


@dataclass
class RankedBudgetRow:
    drug_id: int
    name: str
    priority_rank: int
    ven_status: str
    abc_class: str
    demand_pattern: str
    days_of_supply: float
    expected_days_without_stock: float
    requested_qty: float
    allocated_qty: float
    unit_price: float
    allocated_cost: float
    allocation_status: str
    explanation_note: str


def rank_and_allocate_budget(
    forecasts: Iterable[ForecastItemResult],
    budget_limit: float,
    cycle_days: int = 30,
) -> tuple[list[RankedBudgetRow], dict]:
    """
    Rank order candidates with life-saving (Vital) drugs first, then lowest days_of_supply,
    then cost-effectiveness (days saved per Rupiah). Mark excluded items with expected
    days without stock and transparent explanations.
    """
    need_order = [f for f in forecasts if f.proposed_order_qty > 0]
    no_order = [f for f in forecasts if f.proposed_order_qty <= 0]

    def sort_key(f: ForecastItemResult) -> tuple:
        order_cost = max(1.0, f.proposed_order_qty * f.unit_price)
        days_saved_per_million = (f.expected_days_without_stock / order_cost) * 1_000_000.0
        return (
            VEN_PRIORITY_WEIGHT.get(f.ven_status, 2),
            round(f.days_of_supply, 1),
            ABC_MATRIX_WEIGHT.get(f.abc_ven_matrix, 8),
            -days_saved_per_million,
            f.name,
        )

    ordered_candidates = sorted(need_order, key=sort_key)

    remaining_budget = float(budget_limit)
    ranked_rows: list[RankedBudgetRow] = []
    total_requested_cost = 0.0
    total_allocated_cost = 0.0

    for rank_idx, f in enumerate(ordered_candidates, start=1):
        req_qty = math.ceil(f.proposed_order_qty)
        req_cost = req_qty * f.unit_price
        total_requested_cost += req_cost

        if req_cost <= remaining_budget + 1e-6:
            alloc_qty = float(req_qty)
            alloc_cost = round(req_cost, 2)
            remaining_budget = max(0.0, remaining_budget - alloc_cost)
            total_allocated_cost += alloc_cost
            status = "FULL_ORDER"
            days_without = 0.0
            note = (
                f"Didanai penuh (Tier {f.ven_status}/{f.abc_class}, pola {f.demand_pattern}, "
                f"sisa stok {f.days_of_supply:.1f} hari)."
            )
        elif remaining_budget >= f.unit_price > 0 and f.ven_status in ("V", "E"):
            alloc_qty = float(int(remaining_budget // f.unit_price))
            alloc_cost = round(alloc_qty * f.unit_price, 2)
            remaining_budget = max(0.0, remaining_budget - alloc_cost)
            total_allocated_cost += alloc_cost
            status = "PARTIAL_ORDER"
            funded_ratio = alloc_qty / req_qty if req_qty > 0 else 0.0
            days_without = round(f.expected_days_without_stock * (1.0 - funded_ratio), 1)
            note = (
                f"Didanai parsial ({int(alloc_qty)}/{req_qty} unit) karena sisa anggaran terbatas; "
                f"estimasi kekosongan turun menjadi {days_without:.1f} hari."
            )
        else:
            alloc_qty = 0.0
            alloc_cost = 0.0
            status = "EXCLUDED_OVER_BUDGET"
            days_without = f.expected_days_without_stock
            note = (
                f"Tereliminasi oleh batas anggaran (butuh Rp {req_cost:,.0f}, sisa Rp {remaining_budget:,.0f}). "
                f"Estimasi hari tanpa stok: {days_without:.1f} hari dalam siklus {cycle_days} hari."
            )

        if f.projected_expired_qty > 0:
            note += f" [Peringatan ED: {f.projected_expired_qty:.0f} unit fisik berisiko kedaluwarsa sebelum terpakai]."

        ranked_rows.append(
            RankedBudgetRow(
                drug_id=f.drug_id,
                name=f.name,
                priority_rank=rank_idx,
                ven_status=f.ven_status,
                abc_class=f.abc_class,
                demand_pattern=f.demand_pattern,
                days_of_supply=f.days_of_supply,
                expected_days_without_stock=days_without,
                requested_qty=float(req_qty),
                allocated_qty=alloc_qty,
                unit_price=f.unit_price,
                allocated_cost=alloc_cost,
                allocation_status=status,
                explanation_note=note,
            )
        )

    # Append items not needing an order at the bottom with rank 0
    for f in sorted(no_order, key=lambda x: x.name):
        ed_note = (
            f"Stok layak pakai cukup ({f.days_of_supply:.1f} hari)."
            if f.projected_expired_qty <= 0
            else f"Tidak perlu order (stok layak pakai cukup {f.days_of_supply:.1f} hari), "
                 f"tetapi {f.projected_expired_qty:.0f} unit fisik berisiko ED!"
        )
        ranked_rows.append(
            RankedBudgetRow(
                drug_id=f.drug_id,
                name=f.name,
                priority_rank=0,
                ven_status=f.ven_status,
                abc_class=f.abc_class,
                demand_pattern=f.demand_pattern,
                days_of_supply=f.days_of_supply,
                expected_days_without_stock=0.0,
                requested_qty=0.0,
                allocated_qty=0.0,
                unit_price=f.unit_price,
                allocated_cost=0.0,
                allocation_status="NOT_NEEDED",
                explanation_note=ed_note,
            )
        )

    summary = {
        "budget_limit": round(budget_limit, 2),
        "total_requested_cost": round(total_requested_cost, 2),
        "total_allocated_cost": round(total_allocated_cost, 2),
        "remaining_budget": round(remaining_budget, 2),
        "full_orders": sum(1 for r in ranked_rows if r.allocation_status == "FULL_ORDER"),
        "partial_orders": sum(1 for r in ranked_rows if r.allocation_status == "PARTIAL_ORDER"),
        "excluded_orders": sum(1 for r in ranked_rows if r.allocation_status == "EXCLUDED_OVER_BUDGET"),
        "vital_excluded": sum(
            1 for r in ranked_rows if r.allocation_status == "EXCLUDED_OVER_BUDGET" and r.ven_status == "V"
        ),
    }
    return ranked_rows, summary


def render_one_page_report(
    period_label: str,
    ranked_rows: list[RankedBudgetRow],
    summary: dict,
) -> str:
    """Render a one-page management and procurement summary in Markdown."""
    lines = [
        f"# SigapStok — Rencana Pengadaan & Pemeringkatan Anggaran ({period_label})",
        "",
        "## Ringkasan Anggaran",
        f"- **Batas Anggaran:** Rp {summary['budget_limit']:,.0f}",
        f"- **Total Kebutuhan Ideal:** Rp {summary['total_requested_cost']:,.0f}",
        f"- **Total Dialokasikan:** Rp {summary['total_allocated_cost']:,.0f} (Sisa: Rp {summary['remaining_budget']:,.0f})",
        f"- **Status:** {summary['full_orders']} Penuh | {summary['partial_orders']} Parsial | {summary['excluded_orders']} Tereliminasi (Vital tereliminasi: {summary['vital_excluded']})",
        "",
        "## Daftar Peringkat Pengadaan (Prioritas Vital-First)",
        "| Rank | Nama Obat | VEN/ABC | Pola | Sisa Stok (Hari) | Usulan | Alokasi | Biaya (Rp) | Status | Hari Kosong | Catatan |",
        "| :---: | :--- | :---: | :--- | :---: | :---: | :---: | ---: | :--- | :---: | :--- |",
    ]
    for r in ranked_rows:
        if r.allocation_status == "NOT_NEEDED" and "risiko ED" not in r.explanation_note:
            continue
        rank_str = str(r.priority_rank) if r.priority_rank > 0 else "-"
        lines.append(
            f"| {rank_str} | {r.name} | {r.ven_status}/{r.abc_class} | {r.demand_pattern} | "
            f"{r.days_of_supply:.1f} | {r.requested_qty:.0f} | {r.allocated_qty:.0f} | "
            f"{r.allocated_cost:,.0f} | {r.allocation_status} | {r.expected_days_without_stock:.1f} | {r.explanation_note} |"
        )
    return "\n".join(lines)
