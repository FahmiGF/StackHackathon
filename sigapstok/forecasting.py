"""Adaptive demand pattern classification, forecasting, ABC/XYZ/FSN, and ED usable-stock logic."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional


@dataclass
class ForecastItemResult:
    drug_id: int
    name: str
    ven_status: str
    unit_price: float
    lookback_months: int
    adi: float
    cv2: float
    demand_pattern: str
    abc_class: str
    xyz_class: str
    fsn_class: str
    abc_ven_matrix: str
    forecast_method: str
    forecast_monthly_qty: float
    safety_stock_qty: float
    target_stock_qty: float
    physical_stock_qty: float
    usable_stock_qty: float
    projected_expired_qty: float
    proposed_order_qty: float
    days_of_supply: float
    expected_days_without_stock: float


def compute_adi_cv2(history: list[float]) -> tuple[float, float]:
    """Compute Average Demand Interval (ADI) and Squared Coefficient of Variation (CV^2)."""
    if not history:
        return float("inf"), 0.0
    non_zero = [x for x in history if x > 0]
    if not non_zero:
        return float(len(history)), 0.0
    adi = len(history) / len(non_zero)
    mean_nz = sum(non_zero) / len(non_zero)
    if mean_nz <= 0 or len(non_zero) < 2:
        return round(adi, 4), 0.0
    variance = sum((x - mean_nz) ** 2 for x in non_zero) / len(non_zero)
    cv2 = variance / (mean_nz ** 2)
    return round(adi, 4), round(cv2, 4)


def classify_demand_pattern(history: list[float]) -> tuple[str, float, float]:
    """Classify demand using Syntetos-Boylan thresholds (ADI=1.32, CV^2=0.49)."""
    non_zero = [x for x in history if x > 0]
    if not non_zero:
        return "NO_DEMAND", float(len(history) or 1), 0.0
    adi, cv2 = compute_adi_cv2(history)
    if adi < 1.32 and cv2 < 0.49:
        return "SMOOTH", adi, cv2
    if adi < 1.32 and cv2 >= 0.49:
        return "ERRATIC", adi, cv2
    if adi >= 1.32 and cv2 < 0.49:
        return "INTERMITTENT", adi, cv2
    return "LUMPY", adi, cv2


def classify_xyz(history: list[float]) -> str:
    """Classify usage consistency via Coefficient of Variation across all periods."""
    if not history:
        return "Z"
    mean_all = sum(history) / len(history)
    if mean_all <= 0:
        return "Z"
    std_all = math.sqrt(sum((x - mean_all) ** 2 for x in history) / len(history))
    cv = std_all / mean_all
    if cv < 0.5:
        return "X"
    if cv < 1.0:
        return "Y"
    return "Z"


def classify_fsn(history: list[float], adi: float) -> str:
    """Classify turnover velocity into FAST, SLOW, or NON_MOVING."""
    if not history or sum(history) <= 0:
        return "NON_MOVING"
    recent = history[-3:] if len(history) >= 3 else history
    if sum(recent) <= 0 and adi >= 3.0:
        return "NON_MOVING"
    if adi <= 1.5:
        return "FAST"
    return "SLOW"


def forecast_ses(history: list[float], alpha: float = 0.35) -> float:
    """Simple Exponential Smoothing for Smooth demand."""
    if not history:
        return 0.0
    level = history[0]
    for val in history[1:]:
        level = alpha * val + (1.0 - alpha) * level
    return max(0.0, level)


def forecast_damped_holt(history: list[float], alpha: float = 0.35, beta: float = 0.15, phi: float = 0.85) -> float:
    """Damped Holt's Linear Trend for Erratic demand without over-reacting to spikes."""
    if not history:
        return 0.0
    if len(history) == 1:
        return max(0.0, history[0])
    level = history[0]
    trend = history[1] - history[0]
    for val in history[1:]:
        prev_level = level
        level = alpha * val + (1.0 - alpha) * (level + phi * trend)
        trend = beta * (level - prev_level) + (1.0 - beta) * phi * trend
    return max(0.0, level + phi * trend)


def forecast_sba(history: list[float], alpha: float = 0.15) -> float:
    """Syntetos-Boylan Approximation (bias-corrected Croston) for Intermittent / Lumpy demand."""
    if not history or sum(history) <= 0:
        return 0.0
    first_nz = next((i for i, v in enumerate(history) if v > 0), None)
    if first_nz is None:
        return 0.0

    z_hat = history[first_nz]
    p_hat = float(first_nz + 1)
    q = 1
    for val in history[first_nz + 1:]:
        if val > 0:
            z_hat = alpha * val + (1.0 - alpha) * z_hat
            p_hat = alpha * q + (1.0 - alpha) * p_hat
            q = 1
        else:
            q += 1
    if p_hat <= 0:
        return 0.0
    return max(0.0, (1.0 - alpha / 2.0) * (z_hat / p_hat))


def compute_pattern_matched_forecast(
    history: list[float],
    ven_status: str,
    min_standby_qty: float = 0.0,
    lead_time_days: float = 10.0,
) -> tuple[str, str, float, float, float, float]:
    """
    Select forecasting algorithm matched to demand pattern and compute safety stock.

    Returns:
        (pattern, method_name, forecast_monthly_qty, safety_stock_qty, adi, cv2)
    """
    pattern, adi, cv2 = classify_demand_pattern(history)
    lead_months = max(0.1, lead_time_days / 30.0)

    if pattern == "SMOOTH":
        method = "SES (Simple Exponential Smoothing)"
        forecast_qty = forecast_ses(history)
        z_score = 1.65 if ven_status == "V" else (1.28 if ven_status == "E" else 0.84)
    elif pattern == "ERRATIC":
        method = "Damped Holt Exponential Smoothing"
        forecast_qty = forecast_damped_holt(history)
        z_score = 1.96 if ven_status == "V" else (1.65 if ven_status == "E" else 1.04)
    elif pattern in ("INTERMITTENT", "LUMPY"):
        method = "SBA (Syntetos-Boylan Approximation)"
        forecast_qty = forecast_sba(history)
        z_score = 1.96 if ven_status == "V" else (1.44 if ven_status == "E" else 0.84)
    else:
        method = "Zero-Demand Guard"
        forecast_qty = 0.0
        z_score = 0.0

    mean_h = sum(history) / len(history) if history else 0.0
    std_h = math.sqrt(sum((x - mean_h) ** 2 for x in history) / len(history)) if len(history) > 1 else 0.0
    safety_stock = z_score * std_h * math.sqrt(lead_months)

    # Protect Vital life-saving drugs even if recent consumption was 0 or sporadic
    if ven_status == "V":
        non_zero = [x for x in history if x > 0]
        typical_event = (sum(non_zero) / len(non_zero)) if non_zero else 0.0
        vital_floor = max(min_standby_qty, typical_event)
        if forecast_qty + safety_stock < vital_floor:
            safety_stock = max(safety_stock, vital_floor - forecast_qty)
            method = f"{method} + Vital Standby Buffer"

    return pattern, method, round(forecast_qty, 2), round(safety_stock, 2), adi, cv2


def compute_ed_usable_stock(
    physical_stock: float,
    monthly_forecast: float,
    ed_months_remaining: Optional[float],
    loan_out_qty: float = 0.0,
) -> tuple[float, float]:
    """
    Calculate usable stock before expiry date (ED capping) minus loaned-out stock.
    Prevents overestimating stock when a large portion will expire before it can be consumed.
    """
    if ed_months_remaining is None:
        consumable_before_ed = physical_stock
    else:
        # Allow consuming at least standby/emergency rate if monthly_forecast is near zero
        effective_monthly_rate = max(monthly_forecast, 0.0)
        consumable_before_ed = min(physical_stock, effective_monthly_rate * max(0.0, ed_months_remaining))

    usable = max(0.0, consumable_before_ed - max(0.0, loan_out_qty))
    projected_expired = max(0.0, physical_stock - consumable_before_ed)
    return round(usable, 2), round(projected_expired, 2)


def assign_abc_classes(annual_values: dict[int, float]) -> dict[int, str]:
    """Assign ABC Pareto classes (A: top 80% spend, B: next 15%, C: bottom 5%)."""
    total_val = sum(annual_values.values())
    if total_val <= 0:
        return {k: "C" for k in annual_values}

    sorted_items = sorted(annual_values.items(), key=lambda kv: kv[1], reverse=True)
    cum = 0.0
    classes: dict[int, str] = {}
    for drug_id, val in sorted_items:
        share_before = cum / total_val
        cum += val
        if share_before < 0.80:
            classes[drug_id] = "A"
        elif share_before < 0.95:
            classes[drug_id] = "B"
        else:
            classes[drug_id] = "C"
    return classes


def run_forecast_batch(
    items: list[dict],
    lead_time_days: float = 10.0,
    cycle_days: int = 30,
) -> list[ForecastItemResult]:
    """
    Execute full pattern-matched forecasting, ABC/XYZ/FSN/VEN classification,
    and ED-usable stock subtraction for all items in a batch.
    """
    preliminary: list[dict] = []
    annual_values: dict[int, float] = {}

    for item in items:
        drug_id = int(item["drug_id"])
        history: list[float] = [float(x) for x in item["history"]]
        ven = item["ven_status"]
        unit_price = float(item["unit_price"])
        min_standby = float(item.get("min_standby_qty", 0.0))

        pattern, method, forecast_qty, safety_stock, adi, cv2 = compute_pattern_matched_forecast(
            history=history,
            ven_status=ven,
            min_standby_qty=min_standby,
            lead_time_days=lead_time_days,
        )
        xyz = classify_xyz(history)
        fsn = classify_fsn(history, adi)

        usable_stock, projected_expired = compute_ed_usable_stock(
            physical_stock=float(item["physical_stock"]),
            monthly_forecast=forecast_qty,
            ed_months_remaining=item.get("ed_months_remaining"),
            loan_out_qty=float(item.get("loan_out_qty", 0.0)),
        )

        target_stock = round(forecast_qty + safety_stock, 2)
        proposed_order = max(0.0, round(target_stock - usable_stock, 2))
        if item.get("is_divisible", True) is False:
            proposed_order = float(math.ceil(proposed_order))

        daily_rate = forecast_qty / float(cycle_days)
        if daily_rate > 0:
            days_of_supply = round(usable_stock / daily_rate, 1)
        elif ven == "V" and usable_stock < target_stock:
            days_of_supply = 0.0
        else:
            days_of_supply = float(cycle_days)

        expected_stockout_days = round(max(0.0, float(cycle_days) - days_of_supply), 1)
        annual_values[drug_id] = forecast_qty * 12.0 * unit_price

        preliminary.append(
            {
                "drug_id": drug_id,
                "name": item["name"],
                "ven_status": ven,
                "unit_price": unit_price,
                "lookback_months": len(history),
                "adi": adi,
                "cv2": cv2,
                "demand_pattern": pattern,
                "xyz_class": xyz,
                "fsn_class": fsn,
                "forecast_method": method,
                "forecast_monthly_qty": forecast_qty,
                "safety_stock_qty": safety_stock,
                "target_stock_qty": target_stock,
                "physical_stock_qty": float(item["physical_stock"]),
                "usable_stock_qty": usable_stock,
                "projected_expired_qty": projected_expired,
                "proposed_order_qty": proposed_order,
                "days_of_supply": days_of_supply,
                "expected_days_without_stock": expected_stockout_days,
            }
        )

    abc_map = assign_abc_classes(annual_values)
    results: list[ForecastItemResult] = []
    for p in preliminary:
        abc = abc_map[p["drug_id"]]
        results.append(
            ForecastItemResult(
                drug_id=p["drug_id"],
                name=p["name"],
                ven_status=p["ven_status"],
                unit_price=p["unit_price"],
                lookback_months=p["lookback_months"],
                adi=p["adi"],
                cv2=p["cv2"],
                demand_pattern=p["demand_pattern"],
                abc_class=abc,
                xyz_class=p["xyz_class"],
                fsn_class=p["fsn_class"],
                abc_ven_matrix=f"{abc}{p['ven_status']}",
                forecast_method=p["forecast_method"],
                forecast_monthly_qty=p["forecast_monthly_qty"],
                safety_stock_qty=p["safety_stock_qty"],
                target_stock_qty=p["target_stock_qty"],
                physical_stock_qty=p["physical_stock_qty"],
                usable_stock_qty=p["usable_stock_qty"],
                projected_expired_qty=p["projected_expired_qty"],
                proposed_order_qty=p["proposed_order_qty"],
                days_of_supply=p["days_of_supply"],
                expected_days_without_stock=p["expected_days_without_stock"],
            )
        )
    return results
