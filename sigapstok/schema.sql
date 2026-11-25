-- SigapStok Relational Schema (SQLite / PostgreSQL compatible concepts)
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS drugs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    drug_code TEXT UNIQUE,
    name TEXT NOT NULL UNIQUE,
    generic_name TEXT,
    category TEXT NOT NULL DEFAULT 'Uncategorized',
    unit TEXT NOT NULL DEFAULT 'Unit',
    ven_status TEXT NOT NULL DEFAULT 'E' CHECK (ven_status IN ('V', 'E', 'N')),
    ven_confirmed INTEGER NOT NULL DEFAULT 0,
    is_doen INTEGER NOT NULL DEFAULT 0,
    doen_match_method TEXT,
    unit_price REAL NOT NULL CHECK (unit_price >= 0),
    is_divisible INTEGER NOT NULL DEFAULT 1,
    min_standby_qty REAL NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS upload_batches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    period_label TEXT NOT NULL,
    budget_limit REAL NOT NULL CHECK (budget_limit >= 0),
    usage_filename TEXT NOT NULL,
    price_filename TEXT NOT NULL,
    row_count_usage INTEGER NOT NULL DEFAULT 0,
    row_count_price INTEGER NOT NULL DEFAULT 0,
    validation_warnings TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS monthly_usage_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id INTEGER REFERENCES upload_batches(id) ON DELETE CASCADE,
    drug_id INTEGER NOT NULL REFERENCES drugs(id) ON DELETE CASCADE,
    period_month TEXT NOT NULL, -- YYYY-MM
    qty_used REAL NOT NULL CHECK (qty_used >= 0),
    stock_end REAL NOT NULL DEFAULT 0 CHECK (stock_end >= 0),
    loan_out_qty REAL NOT NULL DEFAULT 0 CHECK (loan_out_qty >= 0),
    UNIQUE (drug_id, period_month)
);

CREATE TABLE IF NOT EXISTS stock_batches_ed (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id INTEGER NOT NULL REFERENCES upload_batches(id) ON DELETE CASCADE,
    drug_id INTEGER NOT NULL REFERENCES drugs(id) ON DELETE CASCADE,
    physical_stock REAL NOT NULL CHECK (physical_stock >= 0),
    expiry_date TEXT, -- YYYY-MM-DD
    ed_months_remaining REAL,
    usable_stock REAL NOT NULL CHECK (usable_stock >= 0),
    projected_expired_qty REAL NOT NULL DEFAULT 0 CHECK (projected_expired_qty >= 0),
    loan_out_qty REAL NOT NULL DEFAULT 0 CHECK (loan_out_qty >= 0)
);

CREATE TABLE IF NOT EXISTS forecast_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id INTEGER NOT NULL REFERENCES upload_batches(id) ON DELETE CASCADE,
    drug_id INTEGER NOT NULL REFERENCES drugs(id) ON DELETE CASCADE,
    lookback_months INTEGER NOT NULL,
    adi REAL NOT NULL,
    cv2 REAL NOT NULL,
    demand_pattern TEXT NOT NULL CHECK (demand_pattern IN ('SMOOTH', 'ERRATIC', 'INTERMITTENT', 'LUMPY', 'NO_DEMAND')),
    abc_class TEXT NOT NULL CHECK (abc_class IN ('A', 'B', 'C')),
    xyz_class TEXT NOT NULL CHECK (xyz_class IN ('X', 'Y', 'Z')),
    fsn_class TEXT NOT NULL CHECK (fsn_class IN ('FAST', 'SLOW', 'NON_MOVING')),
    abc_ven_matrix TEXT NOT NULL,
    forecast_method TEXT NOT NULL,
    forecast_monthly_qty REAL NOT NULL CHECK (forecast_monthly_qty >= 0),
    safety_stock_qty REAL NOT NULL CHECK (safety_stock_qty >= 0),
    target_stock_qty REAL NOT NULL CHECK (target_stock_qty >= 0),
    usable_stock_qty REAL NOT NULL CHECK (usable_stock_qty >= 0),
    proposed_order_qty REAL NOT NULL CHECK (proposed_order_qty >= 0),
    manual_adjusted_qty REAL,
    adjustment_reason TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS budget_ranking_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id INTEGER NOT NULL REFERENCES upload_batches(id) ON DELETE CASCADE,
    drug_id INTEGER NOT NULL REFERENCES drugs(id) ON DELETE CASCADE,
    priority_rank INTEGER NOT NULL,
    ven_status TEXT NOT NULL,
    abc_class TEXT NOT NULL,
    days_of_supply REAL NOT NULL,
    expected_days_without_stock REAL NOT NULL,
    requested_qty REAL NOT NULL,
    allocated_qty REAL NOT NULL,
    allocated_cost REAL NOT NULL,
    allocation_status TEXT NOT NULL CHECK (allocation_status IN ('FULL_ORDER', 'PARTIAL_ORDER', 'EXCLUDED_OVER_BUDGET', 'NOT_NEEDED')),
    explanation_note TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS simulation_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_label TEXT NOT NULL,
    num_months INTEGER NOT NULL,
    monthly_budget_cap REAL NOT NULL,
    strategy_name TEXT NOT NULL,
    vital_stockout_days INTEGER NOT NULL,
    total_stockout_days INTEGER NOT NULL,
    expired_units REAL NOT NULL,
    expired_value_idr REAL NOT NULL,
    fill_rate_pct REAL NOT NULL,
    vital_budget_share_pct REAL NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
