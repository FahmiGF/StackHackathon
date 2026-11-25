"""Synthetic dataset generator mimicking RSUD Kilisuci pharmacy exports."""

from __future__ import annotations

import random
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd


def build_synthetic_rsud_skus(seed: int = 42) -> list[dict]:
    """
    Create 18 representative pharmacy SKUs covering Smooth, Erratic, Intermittent, and Lumpy patterns,
    including real-world examples from RSUD Kilisuci (Acarbose 100 mg, Aciclovir 200 mg, Spuit 50 ml)
    and Vital life-saving drugs.
    """
    rng = random.Random(seed)
    skus = [
        # Vital + Intermittent / Lumpy (rare life-saving drugs that fail under 1-month formula)
        {"name": "Epinefrin Injeksi 0.1% 1 ml", "category": "Farmasi - Obat - Injeksi", "unit": "Ampul", "ven": "V", "is_doen": True, "price": 12500, "pattern": "INTERMITTENT", "base": 6, "p_nonzero": 0.45, "stock": 2, "ed_days": 420, "standby": 10},
        {"name": "Atropin Sulfat Injeksi 0.25 mg/ml", "category": "Farmasi - Obat - Injeksi", "unit": "Ampul", "ven": "V", "is_doen": True, "price": 9800, "pattern": "INTERMITTENT", "base": 8, "p_nonzero": 0.40, "stock": 3, "ed_days": 380, "standby": 12},
        {"name": "SABU (Serum Anti Bisa Ular) Polivalen", "category": "Farmasi - Obat - Serum", "unit": "Vial", "ven": "V", "is_doen": True, "price": 780000, "pattern": "LUMPY", "base": 2, "p_nonzero": 0.25, "stock": 1, "ed_days": 300, "standby": 3},
        {"name": "Diazepam Injeksi 5 mg/ml", "category": "Farmasi - Obat - Injeksi", "unit": "Ampul", "ven": "V", "is_doen": True, "price": 14000, "pattern": "INTERMITTENT", "base": 10, "p_nonzero": 0.50, "stock": 4, "ed_days": 450, "standby": 10},
        {"name": "Insulin Glargine 100 IU/ml Pen", "category": "Farmasi - Obat - Injeksi", "unit": "Pen", "ven": "V", "is_doen": True, "price": 98000, "pattern": "SMOOTH", "base": 45, "p_nonzero": 1.0, "stock": 12, "ed_days": 240, "standby": 20},
        {"name": "Norepinefrin Injeksi 4 mg/4 ml", "category": "Farmasi - Obat - Injeksi", "unit": "Ampul", "ven": "V", "is_doen": True, "price": 65000, "pattern": "ERRATIC", "base": 22, "p_nonzero": 0.90, "stock": 5, "ed_days": 330, "standby": 15},

        # Essential (DOEN-matched & hospital routine)
        {"name": "Aciclovir 200 mg Tablet", "category": "Farmasi - Obat - Tablet", "unit": "Tablet", "ven": "E", "is_doen": True, "price": 650, "pattern": "ERRATIC", "base": 180, "p_nonzero": 0.90, "stock": 60, "ed_days": 400, "standby": 0},
        {"name": "Acarbose 100 mg Tablet", "category": "Farmasi - Obat - Tablet", "unit": "Tablet", "ven": "E", "is_doen": False, "price": 1850, "pattern": "SMOOTH", "base": 520, "p_nonzero": 1.0, "stock": 4446, "ed_days": 180, "standby": 0},
        {"name": "Alat Suntik Sekali Pakai 50 ml (Cath Tip)", "category": "Farmasi - Alkes - Alkes & BMHP", "unit": "Pcs", "ven": "E", "is_doen": False, "price": 8500, "pattern": "SMOOTH", "base": 15, "p_nonzero": 1.0, "stock": 57, "ed_days": 540, "standby": 0},
        {"name": "Amlodipine 10 mg Tablet", "category": "Farmasi - Obat - Tablet", "unit": "Tablet", "ven": "E", "is_doen": True, "price": 450, "pattern": "SMOOTH", "base": 1200, "p_nonzero": 1.0, "stock": 400, "ed_days": 500, "standby": 0},
        {"name": "Metformin 500 mg Tablet", "category": "Farmasi - Obat - Tablet", "unit": "Tablet", "ven": "E", "is_doen": True, "price": 350, "pattern": "SMOOTH", "base": 1600, "p_nonzero": 1.0, "stock": 350, "ed_days": 480, "standby": 0},
        {"name": "Ceftriaxone 1 g Serbuk Injeksi", "category": "Farmasi - Obat - Injeksi", "unit": "Vial", "ven": "E", "is_doen": True, "price": 18500, "pattern": "ERRATIC", "base": 190, "p_nonzero": 1.0, "stock": 45, "ed_days": 365, "standby": 0},
        {"name": "Omeprazole 40 mg Injeksi", "category": "Farmasi - Obat - Injeksi", "unit": "Vial", "ven": "E", "is_doen": True, "price": 24000, "pattern": "SMOOTH", "base": 140, "p_nonzero": 1.0, "stock": 30, "ed_days": 410, "standby": 0},
        {"name": "Ringer Laktat 500 ml Infus", "category": "Farmasi - Cairan - Infus", "unit": "Botol", "ven": "V", "is_doen": True, "price": 11500, "pattern": "SMOOTH", "base": 420, "p_nonzero": 1.0, "stock": 90, "ed_days": 520, "standby": 100},

        # Non-essential (expensive or supportive items that drain budget if unranked)
        {"name": "Albumin Human 20% 100 ml", "category": "Farmasi - Obat - Injeksi", "unit": "Botol", "ven": "N", "is_doen": False, "price": 1250000, "pattern": "LUMPY", "base": 8, "p_nonzero": 0.45, "stock": 1, "ed_days": 270, "standby": 0},
        {"name": "Multivitamin Sirup 100 ml", "category": "Farmasi - Obat - Sirup", "unit": "Botol", "ven": "N", "is_doen": False, "price": 28000, "pattern": "ERRATIC", "base": 85, "p_nonzero": 0.85, "stock": 15, "ed_days": 350, "standby": 0},
        {"name": "Neurotropik B1-B6-B12 Tablet", "category": "Farmasi - Obat - Tablet", "unit": "Tablet", "ven": "N", "is_doen": False, "price": 2200, "pattern": "SMOOTH", "base": 340, "p_nonzero": 1.0, "stock": 80, "ed_days": 420, "standby": 0},
        {"name": "Salep Kulit Pelembab Khusus", "category": "Farmasi - Obat - Topikal", "unit": "Tube", "ven": "N", "is_doen": False, "price": 45000, "pattern": "INTERMITTENT", "base": 18, "p_nonzero": 0.50, "stock": 3, "ed_days": 300, "standby": 0},
    ]

    for s in skus:
        history: list[int] = []
        for m in range(12):
            if rng.random() > s["p_nonzero"]:
                history.append(0)
                continue
            if s["pattern"] == "SMOOTH":
                val = int(max(1, round(rng.gauss(s["base"], s["base"] * 0.12))))
            elif s["pattern"] == "ERRATIC":
                val = int(max(1, round(rng.gauss(s["base"], s["base"] * 0.55))))
            elif s["pattern"] == "INTERMITTENT":
                val = int(max(1, round(rng.gauss(s["base"], s["base"] * 0.18))))
            else:  # LUMPY
                val = int(max(1, round(s["base"] * rng.uniform(0.4, 2.8))))
            history.append(val)
        # Ensure last month of rare Vital drug can be 0 to demonstrate failure of 1-month formula
        if s["ven"] == "V" and s["pattern"] in ("INTERMITTENT", "LUMPY"):
            history[-1] = 0
            history[-2] = max(1, s["base"])
        s["history_12m"] = history
    return skus


def export_synthetic_excel_inputs(
    out_dir: str | Path,
    reference_date: datetime | None = None,
    seed: int = 42,
) -> tuple[Path, Path]:
    """Generate sample usage_stock.xlsx and price_ven.xlsx files for testing upload & column inspection."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    ref = reference_date or datetime(2026, 10, 12)
    skus = build_synthetic_rsud_skus(seed=seed)

    month_labels = [
        (ref - timedelta(days=30 * (12 - i))).strftime("%Y-%m")
        for i in range(12)
    ]

    usage_rows = []
    price_rows = []
    for s in skus:
        ed_date = (ref + timedelta(days=s["ed_days"])).strftime("%Y-%m-%d")
        u_row = {
            "NAMA": s["name"],
            "KATEGORI": s["category"],
            "SATUAN": s["unit"],
            "STOK FISIK": s["stock"],
            "TANGGAL ED": ed_date,
            "PEMINJAMAN KE FASKES LAIN": 0,
        }
        for lbl, val in zip(month_labels, s["history_12m"]):
            u_row[lbl] = val
        usage_rows.append(u_row)

        price_rows.append(
            {
                "NAMA": s["name"],
                "HARGA SATUAN": s["price"],
                "STATUS VEN": s["ven"],
                "HASIL PENCOCOKAN DOEN": "YA - tercantum di DOEN" if s["is_doen"] else "TIDAK",
                "STOK STANDBY MINIMAL": s["standby"],
            }
        )

    usage_path = out / "sample_usage_stock.xlsx"
    price_path = out / "sample_price_ven.xlsx"
    pd.DataFrame(usage_rows).to_excel(usage_path, index=False)
    pd.DataFrame(price_rows).to_excel(price_path, index=False)
    return usage_path, price_path
