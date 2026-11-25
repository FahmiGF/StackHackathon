"""Spreadsheet upload, column inspection, and normalization for RSUD Kilisuci exports."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd


class ColumnValidationError(ValueError):
    """Raised when an uploaded CSV/XLSX file misses required columns or contains invalid types."""


USAGE_COLUMN_ALIASES: dict[str, list[str]] = {
    "name": ["nama", "nama obat", "nama_obat", "name", "item_name"],
    "category": ["kategori", "category", "jenis"],
    "unit": ["satuan", "unit", "uom"],
    "physical_stock": ["stok fisik", "stok_fisik", "physical_stock", "sisa stok", "stok"],
    "expiry_date": ["tanggal ed", "tanggal_ed", "ed", "expiry_date", "expired_date"],
    "loan_out": ["peminjaman ke faskes lain", "pinjaman", "loan_out", "loan_out_qty"],
}

PRICE_COLUMN_ALIASES: dict[str, list[str]] = {
    "name": ["nama", "nama obat", "nama obat dari daftar anda", "nama_obat", "name"],
    "unit_price": ["harga", "harga satuan", "harga_satuan", "unit_price", "price"],
    "ven_status": ["ven", "status ven", "status_ven", "ven_status", "kritis"],
    "doen_match": ["hasil pencocokan doen", "doen", "is_doen", "doen_match"],
    "generic_name": ["nama generik/item doen yang cocok", "generic_name", "zat aktif"],
    "doen_method": ["metode pencocokan", "doen_match_method"],
    "min_standby_qty": ["stok standby minimal", "min_standby_qty", "standby_min"],
}


@dataclass
class IngestionReport:
    usage_df: pd.DataFrame
    price_df: pd.DataFrame
    month_columns: list[str]
    warnings: list[str]


def _normalize_header(col: object) -> str:
    text = str(col).strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text


def _load_table(path: str | Path) -> pd.DataFrame:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"File tidak ditemukan: {p}")
    suffix = p.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(p)
    if suffix in (".xlsx", ".xls"):
        return pd.read_excel(p)
    raise ColumnValidationError(f"Format file tidak didukung ({suffix}). Gunakan .csv atau .xlsx.")


def _find_matching_column(columns: list[str], aliases: list[str]) -> Optional[str]:
    norm_map = {_normalize_header(c): c for c in columns}
    for alias in aliases:
        if alias in norm_map:
            return norm_map[alias]
    for norm_col, orig_col in norm_map.items():
        for alias in aliases:
            if norm_col.startswith(alias):
                return orig_col
    return None


def _detect_month_columns(columns: list[str]) -> list[str]:
    """Find monthly consumption columns such as '2026-07', 'usage_2026_07', or 'm01'..'m12'."""
    month_cols: list[str] = []
    pattern = re.compile(r"^(?:\d{4}[-_/]\d{2}|usage_\d{4}[-_]\d{2}|m\d{1,2}|bulan_\d{1,2})$", re.IGNORECASE)
    for c in columns:
        norm = _normalize_header(c).replace(" ", "_")
        if pattern.match(norm):
            month_cols.append(c)
    return month_cols


def validate_usage_stock_df(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str], list[str]]:
    """Inspect and normalize the usage + physical stock + expiry export."""
    warnings: list[str] = []
    cols = list(df.columns)

    name_col = _find_matching_column(cols, USAGE_COLUMN_ALIASES["name"])
    stock_col = _find_matching_column(cols, USAGE_COLUMN_ALIASES["physical_stock"])
    if not name_col or not stock_col:
        missing = []
        if not name_col:
            missing.append("NAMA / nama_obat")
        if not stock_col:
            missing.append("STOK FISIK / physical_stock")
        raise ColumnValidationError(f"Kolom wajib tidak ditemukan pada file pemakaian: {', '.join(missing)}")

    month_cols = _detect_month_columns(cols)
    if not month_cols:
        total_col = _find_matching_column(cols, ["total keluar", "total_keluar", "pemakaian", "usage"])
        if not total_col:
            raise ColumnValidationError(
                "Tidak ditemukan kolom deret pemakaian bulanan (mis. 2026-07..2026-09) maupun 'TOTAL KELUAR'."
            )
        warnings.append(
            f"Hanya ditemukan kolom agregat '{total_col}'. Untuk hasil klasifikasi ADI/CV² akurat, unggah histori per bulan (YYYY-MM)."
        )
        month_cols = [total_col]

    cat_col = _find_matching_column(cols, USAGE_COLUMN_ALIASES["category"])
    unit_col = _find_matching_column(cols, USAGE_COLUMN_ALIASES["unit"])
    ed_col = _find_matching_column(cols, USAGE_COLUMN_ALIASES["expiry_date"])
    loan_col = _find_matching_column(cols, USAGE_COLUMN_ALIASES["loan_out"])

    out = pd.DataFrame()
    out["name"] = df[name_col].astype(str).str.strip()
    out = out[out["name"].ne("") & out["name"].ne("nan")].copy()
    out["category"] = df.loc[out.index, cat_col].fillna("Uncategorized").astype(str).str.strip() if cat_col else "Uncategorized"
    out["unit"] = df.loc[out.index, unit_col].fillna("Unit").astype(str).str.strip() if unit_col else "Unit"

    out["physical_stock"] = pd.to_numeric(df.loc[out.index, stock_col], errors="coerce").fillna(0.0)
    if (out["physical_stock"] < 0).any():
        bad = out.loc[out["physical_stock"] < 0, "name"].tolist()
        raise ColumnValidationError(f"Nilai stok fisik negatif ditemukan pada item: {bad}")

    out["loan_out_qty"] = (
        pd.to_numeric(df.loc[out.index, loan_col], errors="coerce").fillna(0.0).clip(lower=0.0)
        if loan_col
        else 0.0
    )

    if ed_col:
        parsed_ed = pd.to_datetime(df.loc[out.index, ed_col], errors="coerce")
        out["expiry_date"] = parsed_ed.dt.strftime("%Y-%m-%d").where(parsed_ed.notna(), None)
        missing_ed = int(parsed_ed.isna().sum())
        if missing_ed > 0:
            warnings.append(f"{missing_ed} item tidak memiliki format Tanggal ED valid; diasumsikan aman >12 bulan.")
    else:
        out["expiry_date"] = None
        warnings.append("Kolom TANGGAL ED tidak ada; stok fisik dianggap layak pakai seluruhnya.")

    normalized_month_cols: list[str] = []
    for idx, mc in enumerate(month_cols, start=1):
        norm_name = f"m_{idx:02d}" if not re.match(r"^\d{4}[-_]\d{2}$", _normalize_header(mc)) else _normalize_header(mc).replace("_", "-")
        vals = pd.to_numeric(df.loc[out.index, mc], errors="coerce").fillna(0.0).clip(lower=0.0)
        out[norm_name] = vals
        normalized_month_cols.append(norm_name)

    if out["name"].duplicated().any():
        dups = out.loc[out["name"].duplicated(), "name"].unique().tolist()
        warnings.append(f"Terdapat nama obat duplikat yang digabungkan/diperbarui: {dups[:5]}")
        out = out.drop_duplicates(subset=["name"], keep="last").reset_index(drop=True)

    return out.reset_index(drop=True), normalized_month_cols, warnings


def validate_price_ven_df(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Inspect and normalize the price + DOEN + VEN classification spreadsheet."""
    warnings: list[str] = []
    cols = list(df.columns)

    name_col = _find_matching_column(cols, PRICE_COLUMN_ALIASES["name"])
    price_col = _find_matching_column(cols, PRICE_COLUMN_ALIASES["unit_price"])
    if not name_col or not price_col:
        missing = []
        if not name_col:
            missing.append("NAMA / nama_obat")
        if not price_col:
            missing.append("HARGA / unit_price")
        raise ColumnValidationError(f"Kolom wajib tidak ditemukan pada file harga: {', '.join(missing)}")

    ven_col = _find_matching_column(cols, PRICE_COLUMN_ALIASES["ven_status"])
    doen_col = _find_matching_column(cols, PRICE_COLUMN_ALIASES["doen_match"])
    generic_col = _find_matching_column(cols, PRICE_COLUMN_ALIASES["generic_name"])
    method_col = _find_matching_column(cols, PRICE_COLUMN_ALIASES["doen_method"])
    standby_col = _find_matching_column(cols, PRICE_COLUMN_ALIASES["min_standby_qty"])

    out = pd.DataFrame()
    out["name"] = df[name_col].astype(str).str.strip()
    out = out[out["name"].ne("") & out["name"].ne("nan")].copy()

    out["unit_price"] = pd.to_numeric(df.loc[out.index, price_col], errors="coerce")
    if out["unit_price"].isna().any() or (out["unit_price"] < 0).any():
        bad = out.loc[out["unit_price"].isna() | (out["unit_price"] < 0), "name"].tolist()
        raise ColumnValidationError(f"Harga tidak valid atau negatif pada item: {bad[:5]}")

    if doen_col:
        doen_raw = df.loc[out.index, doen_col].fillna("").astype(str).str.upper()
        out["is_doen"] = doen_raw.str.contains("YA|TRUE|1|YES")
    else:
        out["is_doen"] = False

    if ven_col:
        ven_raw = df.loc[out.index, ven_col].fillna("").astype(str).str.strip().str.upper()
        out["ven_status"] = ven_raw.where(ven_raw.isin(["V", "E", "N"]), other="")
        out["ven_confirmed"] = out["ven_status"].isin(["V", "E", "N"])
        # Auto-suggest E for DOEN items lacking manual VEN tag, N otherwise
        mask_empty = ~out["ven_confirmed"]
        if mask_empty.any():
            out.loc[mask_empty & out["is_doen"], "ven_status"] = "E"
            out.loc[mask_empty & (~out["is_doen"]), "ven_status"] = "N"
            warnings.append(
                f"{int(mask_empty.sum())} item belum memiliki tag VEN eksplisit; diberi saran otomatis berbasis DOEN (perlu konfirmasi tim farmasi)."
            )
    else:
        out["ven_confirmed"] = False
        out["ven_status"] = out["is_doen"].map(lambda x: "E" if x else "N")
        warnings.append("Kolom VEN tidak ada; sistem memberi flag awal dari pencocokan DOEN untuk dikonfirmasi tim farmasi.")

    out["generic_name"] = df.loc[out.index, generic_col].fillna("").astype(str).str.strip() if generic_col else ""
    out["doen_match_method"] = df.loc[out.index, method_col].fillna("").astype(str).str.strip() if method_col else ""
    out["min_standby_qty"] = (
        pd.to_numeric(df.loc[out.index, standby_col], errors="coerce").fillna(0.0).clip(lower=0.0)
        if standby_col
        else 0.0
    )

    return out.drop_duplicates(subset=["name"], keep="last").reset_index(drop=True), warnings


def load_and_inspect_files(usage_path: str | Path, price_path: str | Path) -> IngestionReport:
    """Load both spreadsheets, inspect columns, and report warnings."""
    raw_usage = _load_table(usage_path)
    raw_price = _load_table(price_path)
    usage_df, month_cols, w1 = validate_usage_stock_df(raw_usage)
    price_df, w2 = validate_price_ven_df(raw_price)
    return IngestionReport(
        usage_df=usage_df,
        price_df=price_df,
        month_columns=month_cols,
        warnings=w1 + w2,
    )


def compute_ed_months_remaining(expiry_date: Optional[str], reference_date: Optional[datetime] = None) -> Optional[float]:
    """Compute remaining months until Expiry Date relative to reference_date."""
    if not expiry_date:
        return None
    ref = reference_date or datetime.now()
    ed = datetime.strptime(expiry_date, "%Y-%m-%d")
    days = (ed - ref).days
    return max(0.0, round(days / 30.0, 2))
