"""Fair comparison simulation between Current RSUD Formula, Static 3-Month Excel, and SigapStok."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

from sigapstok.forecasting import ForecastItemResult, run_forecast_batch
from sigapstok.ranking import rank_and_allocate_budget
from sigapstok.synthetic_data import build_synthetic_rsud_skus


@dataclass
class BatchLot:
    qty: float
    expiry_day: int


def _generate_daily_demand_stream(skus: list[dict], num_months: int = 6, seed: int = 123) -> dict[str, list[int]]:
    """Generate an identical day-by-day demand realization used fairly across all strategies."""
    rng = random.Random(seed)
    total_days = num_months * 30
    stream: dict[str, list[int]] = {}
    for s in skus:
        daily_vals = [0] * total_days
        for m in range(num_months):
            if rng.random() > s["p_nonzero"]:
                continue
            if s["pattern"] == "SMOOTH":
                monthly_qty = max(1, int(round(rng.gauss(s["base"], s["base"] * 0.15))))
            elif s["pattern"] == "ERRATIC":
                monthly_qty = max(1, int(round(rng.gauss(s["base"], s["base"] * 0.55))))
            elif s["pattern"] == "INTERMITTENT":
                monthly_qty = max(1, int(round(rng.gauss(s["base"], s["base"] * 0.20))))
            else:
                monthly_qty = max(1, int(round(s["base"] * rng.uniform(0.5, 2.5))))

            # Distribute monthly demand across active days in the month
            n_events = 1 if s["pattern"] in ("INTERMITTENT", "LUMPY") else min(20, monthly_qty)
            for _ in range(n_events):
                day = m * 30 + rng.randint(0, 29)
                daily_vals[day] += max(1, monthly_qty // n_events)
        stream[s["name"]] = daily_vals
    return stream


def _simulate_strategy(
    strategy_name: str,
    skus: list[dict],
    demand_stream: dict[str, list[int]],
    monthly_budget_cap: float,
    num_months: int = 6,
    lead_time_days: int = 7,
    trained_artifact: dict | None = None,
) -> dict:
    """Run one inventory strategy over identical demand stream, budget cap, lead time, and FEFO expiry."""
    total_days = num_months * 30
    # Initialize identical stock lots & rolling 12-month history
    lots: dict[str, list[BatchLot]] = {}
    histories: dict[str, list[int]] = {}
    pending_deliveries: dict[int, list[tuple[str, float, int]]] = {}

    for s in skus:
        lots[s["name"]] = [BatchLot(qty=float(s["stock"]), expiry_day=int(s["ed_days"]))]
        histories[s["name"]] = list(s["history_12m"])

    vital_stockout_days = 0
    total_stockout_days = 0
    expired_units = 0.0
    expired_value = 0.0
    total_demand_units = 0.0
    fulfilled_units = 0.0
    total_spend_all = 0.0
    total_spend_vital = 0.0
    current_month_usage = {s["name"]: 0 for s in skus}

    sku_by_name = {s["name"]: s for s in skus}

    for day in range(total_days):
        # 1. Receive deliveries arriving today
        if day in pending_deliveries:
            for name, qty, ed_day in pending_deliveries[day]:
                if qty > 0:
                    lots[name].append(BatchLot(qty=qty, expiry_day=ed_day))
                    lots[name].sort(key=lambda b: b.expiry_day)

        # 2. Discard expired lots (FEFO check at start of day)
        for name, item_lots in lots.items():
            still_valid: list[BatchLot] = []
            for lot in item_lots:
                if lot.expiry_day <= day and lot.qty > 0:
                    expired_units += lot.qty
                    expired_value += lot.qty * sku_by_name[name]["price"]
                elif lot.qty > 0:
                    still_valid.append(lot)
            lots[name] = still_valid

        # 3. Monthly ordering cycle at day 0, 30, 60...
        if day % 30 == 0:
            if day > 0:
                for name in current_month_usage:
                    histories[name].append(current_month_usage[name])
                    current_month_usage[name] = 0

            orders_to_place: dict[str, float] = {}

            if strategy_name == "RSUD_Current_Formula":
                # 1 month usage + 10% reserve - stock; naive allocation by highest last month cost
                candidates = []
                for s in skus:
                    name = s["name"]
                    phys = sum(b.qty for b in lots[name])
                    last_m = histories[name][-1]
                    req = max(0.0, math.ceil(1.10 * last_m - phys))
                    if req > 0:
                        candidates.append((last_m * s["price"], name, req, s["price"]))
                candidates.sort(reverse=True)  # Unranked by criticality
                rem = monthly_budget_cap
                for _, name, req, price in candidates:
                    if req * price <= rem:
                        orders_to_place[name] = req
                        rem -= req * price

            elif strategy_name == "Static_Excel_3Mo_AMC":
                # 5x AMC (3 months) - usable stock; naive order by alphabetical/list order
                rem = monthly_budget_cap
                for s in skus:
                    name = s["name"]
                    amc_3m = sum(histories[name][-3:]) / 3.0
                    phys = sum(b.qty for b in lots[name])
                    # ED-capped usable using earliest batch expiry
                    next_ed_months = max(0.0, (lots[name][0].expiry_day - day) / 30.0) if lots[name] else 12.0
                    usable = min(phys, amc_3m * next_ed_months)
                    req = max(0.0, math.ceil(5.0 * amc_3m - usable))
                    cost = req * s["price"]
                    if req > 0 and cost <= rem:
                        orders_to_place[name] = req
                        rem -= cost

            elif strategy_name in ("SigapStok", "SigapStok_Trained"):
                batch_items = []
                for idx, s in enumerate(skus, start=1):
                    name = s["name"]
                    phys = sum(b.qty for b in lots[name])
                    next_ed_months = ((lots[name][0].expiry_day - day) / 30.0) if lots[name] else None
                    batch_items.append(
                        {
                            "drug_id": idx,
                            "name": name,
                            "ven_status": s["ven"],
                            "unit_price": s["price"],
                            "history": histories[name][-12:],
                            "physical_stock": phys,
                            "ed_months_remaining": next_ed_months,
                            "min_standby_qty": s["standby"],
                        }
                    )
                art = trained_artifact if strategy_name == "SigapStok_Trained" else None
                month_idx = 12 + (day // 30)
                forecasts: list[ForecastItemResult] = run_forecast_batch(
                    batch_items,
                    lead_time_days=lead_time_days,
                    trained_artifact=art,
                    target_month_idx=month_idx,
                )
                ranked, _ = rank_and_allocate_budget(forecasts, budget_limit=monthly_budget_cap)
                for r in ranked:
                    if r.allocated_qty > 0:
                        orders_to_place[r.name] = r.allocated_qty

            # Schedule deliveries after lead_time_days
            arrival_day = day + lead_time_days
            pending_deliveries.setdefault(arrival_day, [])
            for name, qty in orders_to_place.items():
                cost = qty * sku_by_name[name]["price"]
                total_spend_all += cost
                if sku_by_name[name]["ven"] == "V":
                    total_spend_vital += cost
                pending_deliveries[arrival_day].append((name, qty, arrival_day + 450))

        # 4. Fulfill daily demand using FEFO
        for s in skus:
            name = s["name"]
            req = demand_stream[name][day]
            if req <= 0:
                continue
            total_demand_units += req
            avail = sum(b.qty for b in lots[name])
            if avail < req:
                total_stockout_days += 1
                if s["ven"] == "V":
                    vital_stockout_days += 1
            served = min(req, avail)
            fulfilled_units += served
            current_month_usage[name] += int(served)

            rem_to_take = served
            for lot in lots[name]:
                if rem_to_take <= 0:
                    break
                take = min(lot.qty, rem_to_take)
                lot.qty -= take
                rem_to_take -= take

    fill_rate = (fulfilled_units / total_demand_units * 100.0) if total_demand_units > 0 else 100.0
    vital_share = (total_spend_vital / total_spend_all * 100.0) if total_spend_all > 0 else 0.0

    return {
        "strategy_name": strategy_name,
        "vital_stockout_days": vital_stockout_days,
        "total_stockout_days": total_stockout_days,
        "expired_units": round(expired_units, 1),
        "expired_value_idr": round(expired_value, 0),
        "fill_rate_pct": round(fill_rate, 2),
        "vital_budget_share_pct": round(vital_share, 2),
    }


def run_fair_comparison_simulation(
    monthly_budget_cap: float = 35_000_000.0,
    num_months: int = 6,
    seed: int = 42,
    trained_artifact: dict | None = None,
) -> list[dict]:
    """Compare RSUD formula, Static Excel 3-mo AMC, SigapStok Stat, and SigapStok Trained under identical constraints."""
    skus = build_synthetic_rsud_skus(seed=seed)
    demand_stream = _generate_daily_demand_stream(skus, num_months=num_months, seed=seed + 100)
    strategies = ["RSUD_Current_Formula", "Static_Excel_3Mo_AMC", "SigapStok"]
    if trained_artifact is not None:
        strategies.append("SigapStok_Trained")
    return [
        _simulate_strategy(
            strategy_name=st,
            skus=skus,
            demand_stream=demand_stream,
            monthly_budget_cap=monthly_budget_cap,
            num_months=num_months,
            trained_artifact=trained_artifact,
        )
        for st in strategies
    ]
