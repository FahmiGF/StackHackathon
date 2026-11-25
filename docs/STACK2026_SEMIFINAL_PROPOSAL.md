# STACK 2026 SEMIFINAL PROPOSAL
**Project Title:** SigapStok — Pattern-Matched Pharmacy Demand Forecasting & Vital-First Budget Ranking  
**Selected Case:** Case 2 — Stronger Communities and Everyday Services  
**Repository:** https://github.com/FahmiGF/StackHackathon

---

## 1. Project and Team Identity
- **Project Title:** SigapStok
- **Team Name:** `[Team Name — Same Identifier as Preliminary Submission]`
- **Selected Case:** **Case 2: Stronger Communities and Everyday Services** (*"How might we make everyday services easier to access and manage for communities and small organizations?"* — addressing manual inventory records and hospital pharmacy procurement workflows)
- **Team Members & Roles:**
  1. **Fahmi (`FahmiGF`) — Backend Data Pipeline, Forecasting & Ranking Lead:** Relational database schema, file upload & column inspection, history persistence, Section 2.4 existing alternatives & Permenkes/VEN analysis, Section 4.4 budget ranking logic, fair comparison simulation co-design, README & Section 7 documentation.
  2. **Member B — Simulation Co-Design & Validation Lead:** Fair comparison protocol design, synthetic RSUD dataset calibration, validation review.
  3. **Member C — Web Frontend & User Interface Lead:** Planned upload/review/one-page ranking dashboard UI and user workflow refinement for Final Day.
  4. **Member D — Pharmacy Domain Liaison & QA (if 4 members):** DOEN/VEN workflow validation, video presentation & deck assembly.

---

## 2. Problem and User Analysis

### 2.1 Problem Context
At **RSUD Kilisuci**, a public regional hospital in Kediri City, monthly drug procurement is calculated using a single consumption formula applied uniformly across all items [1]. Because pharmacy inventory includes routine chronic medications alongside rarely used life-saving drugs, a one-size-fits-all formula causes severe operational distortions:
- **Zero-order stockouts on sporadic life-saving items:** A rarely used emergency drug receives an order quantity of `0` after a quiet month.
- **Over-ordering and drug expiration:** After a spike month, the formula over-orders; compounded by static multipliers without expiry-date (*ED*) capping, excess stock expires on shelves.
- **Blind budget exhaustion:** When monthly funds run short, the current calculation cannot rank drugs by clinical criticality, allowing funds to reach less urgent items first while critical drugs run out.

### 2.2 Intended Users
1. **Primary Users — Pharmacy Warehouse Staff:** Build the monthly purchase plan from Hospital Information System (SIMRS) exports and e-Catalogue price sheets, verify life-saving flags, adjust proposed quantities with documented reasons, and export the plan.
2. **Secondary Users — Hospital Management & Procurement Unit:** Review budget trade-offs and execute item-by-item purchasing on the national electronic catalogue (*e-Katalog LKPP*) [5].
3. **End Beneficiaries — Public Hospital Patients:** Under Indonesia's National Health Insurance (JKN/BPJS), drugs are provided as a bundled service [4] and cash out-of-pocket purchases are not reimbursed [1]; preventing stockouts directly eliminates patient waiting and treatment delays.

### 2.3 Supporting Observations and Evidence
- **Field Interview [1]:** The Head of Pharmacy at RSUD Kilisuci confirmed that current planning adds a fixed allowance (e.g., 10% reserve) to a single month of usage and subtracts physical stock. Drug shortages occur primarily from inaccurate need estimates and secondarily from exhausted budgets. Procurement via e-Katalog is done drug-by-drug, slowing emergency restocking.
- **National Standards & Literature [2][3][6]:** While Indonesian hospital pharmacy standards (*Permenkes RI No. 72/2016*) recognize past consumption as a planning basis [2], a Padang hospital study linked purely consumption-based planning to missed patient growth and expired inventory [3]. Furthermore, a Thai community hospital study demonstrated that no single forecasting method fits all sporadic-demand drugs and emphasized protecting vital items regardless of recent low consumption [6].

### 2.4 Existing Alternatives, Permenkes Standards, and Comparison with VEN
Under **Permenkes RI No. 72/2016** [2], hospital pharmacies use Consumption, Epidemiological, or Combination planning, alongside **ABC** (spend value) and **VEN** (*Vital, Essential, Non-essential*) matrices to trim budgets. However, existing alternatives leave critical operational gaps:

| Dimension | RSUD Formula (`1 Mo + 10%`) | Static 3-Mo Excel (`5× AMC + ED`) | Conventional VEN (Permenkes) | **SigapStok (Proposed)** |
| :--- | :--- | :--- | :--- | :--- |
| **Forecasting Method** | Single formula for all drugs | Fixed `5× AMC` multiplier across items | Relies on separate manual consumption averages | **Pattern-matched:** `SES` (Smooth), `Damped Holt` (Erratic), **SBA/Croston** (Intermittent/Lumpy) + Epoch-trained Hybrid |
| **Life-Saving Protection** | None (volume-driven only) | None in order priority | Static `V/E/N` tags; drops to 0 if recent usage is 0 | **Vital/DOEN-first** + protected *Minimum Standby Buffer* |
| **Expiry Risk Handling** | Ignored | Partially tracked, yet still recommends orders on high-stock items (e.g., *Acarbose* 1,321 units at ED risk) | Manual shelf audit outside formula | **Automatic ED-Usable Stock Capping** + zero-order guard + ED alerts |
| **Shortfall Transparency** | None | None | Manual cuts (`N -> E`) without impact numbers | **Ranked One-Page Output** with **`expected_days_without_stock`** per excluded item |

---

## 3. Proposed Solution

### 3.1 Value Proposition & Scope Boundaries
**SigapStok** turns raw SIMRS usage/stock exports and price spreadsheets into an auditable, life-saving-first monthly procurement ranking.
- **Explicit Version 1 Scope:** Covers **one pharmacy warehouse** and **one monthly procurement cycle**, operating solely on aggregate item-level usage, stock, expiry, and price spreadsheets **without any patient medical records**.

### 3.2 Core User Flow
1. **Upload & Column Inspection:** Staff upload the usage/stock export and price/DOEN sheet (`.xlsx` / `.csv`). SigapStok validates required columns, flags anomalies, and suggests initial `V/E/N` flags via **DOEN** active-ingredient matching for pharmacy team confirmation.
2. **Pattern-Matched Need Estimation & ED Capping:** Each drug is classified by **ADI** and **CV²** and forecasted using its matched method, while physical stock is capped by remaining shelf life before expiry.
3. **Human-in-the-Loop Adjustment:** Staff inspect system reasoning and can override any proposed quantity with a recorded `adjustment_reason`.
4. **Budget Input & Ranked One-Page Output:** Staff enter the monthly budget ceiling. SigapStok ranks orders **Vital-first**, flags excluded items with **`expected_days_without_stock`**, and generates a one-page summary for management and e-Catalogue procurement.

---

## 4. Technical Design

### 4.1 System Architecture & Planned Stack
- **Implemented Core Engine (Python 3.11 + SQLite):** Modular package (`sigapstok/`) with `ingestion.py`, `db.py` (`schema.sql`), `forecasting.py`, `trainer.py`, `ranking.py`, `simulation.py`, and `synthetic_data.py`.
- **Planned Web Layer (Target for Product Improvement / Final Day):** FastAPI REST endpoints + lightweight web dashboard (HTML/HTMX or React) wrapping the already-working Python core and SQLite/PostgreSQL persistence.

### 4.2 Relational Database & History Storage (`sigapstok/schema.sql`)
Seven normalized tables preserve full auditability: `drugs`, `upload_batches`, `monthly_usage_history` (multi-month time series for ADI/CV²), `stock_batches_ed` (physical vs usable stock and projected expired units), `forecast_results` (including `manual_adjusted_qty` and `adjustment_reason`), `budget_ranking_results`, and `simulation_runs`.

### 4.3 Demand Pattern Classification & Epoch-Trained Hybrid Forecasting
Every SKU is classified using Syntetos–Boylan thresholds (`ADI = 1.32`, `CV² = 0.49`) alongside **ABC** (Pareto spend), **XYZ** (CV variability), and **FSN** (*Fast/Slow/Non-moving*):
- **Smooth** (`ADI < 1.32, CV² < 0.49`): Simple Exponential Smoothing (`SES`)
- **Erratic** (`ADI < 1.32, CV² >= 0.49`): `Damped Holt` Exponential Smoothing
- **Intermittent / Lumpy** (`ADI >= 1.32`): **Syntetos–Boylan Approximation (`SBA`)** + *Vital Standby Buffer*
- **Hybrid Epoch Training (`sigapstok/trainer.py`):** A pure-NumPy 2-Layer MLP (ReLU, Adam optimizer, L2 regularization, Huber loss) trained across **250 epochs** (best validation checkpoint at **Epoch 10**) using 6-month lags, rolling statistics, ADI/CV², seasonality (`sin/cos`), and VEN indicators, blended via validation-learned pattern weights with tuned statistical models.

### 4.4 Budget Ranking Logic
For items with net order $Q_{\text{order}, i} = \max(0, (\hat{D}_i + SS_i) - S_{\text{usable}, i}) > 0$:
1. **Runway & Stockout Risk:** $\text{DoS}_i = S_{\text{usable}, i} / (\hat{D}_i / 30)$ and $\text{ExpectedDaysWithoutStock}_i = \max(0, 30 - \text{DoS}_i)$.
2. **Lexicographic Priority Key:** `(1) VEN Tier (V > E > N)` $\rightarrow$ `(2) Lowest Days of Supply` $\rightarrow$ `(3) ABC-VEN Matrix (AV..CN) & Days-Saved-per-Rupiah`.
3. **Constrained Allocation:** Iterates rank-by-rank under `budget_limit`, assigning `FULL_ORDER`, `PARTIAL_ORDER` (for divisible V/E items), or `EXCLUDED_OVER_BUDGET` with transparent explanation notes and `expected_days_without_stock`.

### 4.5 Data Sources & Honest Simulation Labeling
All evaluation datasets in this repository are **synthetic datasets** (`sigapstok/synthetic_data.py`) calibrated to mimic RSUD Kilisuci's actual spreadsheet structure (e.g., *Acarbose 100 mg*, *Aciclovir 200 mg*, *Spuit 50 ml*, DOEN synonym matching, and 18 multi-pattern hospital SKUs). No confidential patient data is used.

---

## 5. Development Plan & Progress Honesty

### 5.1 Competition Milestones
- **10 Nov 2026 (Completed):** Preliminary Abstract & Twibbon Submission.
- **30 Nov 2026 (Current — Semifinal):** Working Core Backend/Forecasting/DB/Simulation + Detailed Proposal + 2-Minute Video.
- **7–16 Dec 2026 (Product Improvement):** Build Web UI (upload form, editable forecast review table, one-page printable ranking view), pharmacy team review of synthetic data, end-to-end API wiring.
- **19 Dec 2026 (Final Day Build Session):** Execute 3 substantive Final Day tasks: (1) Multi-sheet `.xlsx` export of the one-page e-Catalogue procurement sheet, (2) Interactive budget sensitivity slider ("what-if" comparison), and (3) Audit-log history comparison UI across monthly cycles.

### 5.2 Honest Status: Completed vs. Unfinished Functionality
| Component | Current Status | Verification |
| :--- | :--- | :--- |
| Relational DB schema & history storage | **Completed** | Tested in `tests/test_sigapstok.py` |
| `.xlsx`/`.csv` upload, column inspection & DOEN/VEN check | **Completed** | Tested with invalid & DOEN inputs |
| Pattern classification (`ADI/CV²`, `ABC/XYZ/FSN`) & ED capping | **Completed** | Tested against *Acarbose* ED edge case |
| Epoch-trained Hybrid Forecaster (`160` epochs) & Budget Ranker | **Completed** | Benchmarked on held-out test split |
| Fair 6-month comparison simulation | **Completed** | Executed across 4 strategies |
| Interactive Web UI (FastAPI + Frontend Upload/Review Screens) | **Planned (Not Yet Built)** | Scheduled for Product Improvement (7–16 Dec) |

---

## 6. Validation and Impact

### 6.1 Epoch Training & Held-Out Forecast Accuracy (Months 20–24, Synthetic Benchmark)
**Training Convergence:** Initial Train Loss `0.19824` (Epoch 1) $\rightarrow$ `0.02427` (Epoch 160); Best Validation Loss **`0.08222`** at **Epoch 10**.

| Model / Method | MAE | RMSE | WAPE (%) | Accuracy (`100 - WAPE`) |
| :--- | :---: | :---: | :---: | :---: |
| `RSUD_1Mo_Plus_10Pct` *(Current Formula)* | 73.31 | 151.14 | 25.91% | 74.09% |
| `Excel_3Mo_AMC` *(Static 3-Mo Average)* | 58.49 | 119.06 | 20.67% | 79.33% |
| `SigapStok_Untrained_Stat` *(Fixed Params)* | 53.12 | 110.15 | 18.77% | 81.23% |
| **`SigapStok_Trained_Hybrid` *(Epoch-Tuned)*** | **51.26** | **100.13** | **18.11%** | **81.89%** |

- **Result:** `30.1%` MAE reduction compared to RSUD's current 1-month formula.

### 6.2 Fair 6-Month Comparison Simulation (Identical Budget Rp 30,000,000/mo, FEFO, 7-Day Lead Time)
| Strategy | Vital Stockout Days | Total Stockout Days | Expired Units | Fill Rate (%) | Vital Budget Share (%) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `RSUD_Current_Formula` | 58 | 191 | 0.0 | 83.80% | 43.19% |
| `Static_Excel_3Mo_AMC` | 45 | 170 | 0.0 | 87.65% | 44.84% |
| `SigapStok` *(Untrained Stat)* | 26 | 112 | 0.0 | 88.40% | 38.95% |
| **`SigapStok_Trained` *(Hybrid)*** | **24** | **110** | **0.0** | **88.94%** | **38.87%** |

- **Sample Ranked Output (Budget Cap Rp 35,000,000, Vital Excluded = 0):**

| Rank | Drug Name | VEN/ABC | Pattern | DoS | Req | Alloc | Cost | Status | Days Without Stock |
| :---: | :--- | :---: | :--- | :---: | :---: | :---: | ---: | :--- | :---: |
| 1 | Norepinefrin Injeksi 4 mg/4 ml | V/A | SMOOTH | 6.3 d | 32 | 32 | Rp 2,080,000 | FULL_ORDER | 0.0 d |
| 2 | Ringer Laktat 500 ml Infus | V/A | SMOOTH | 7.4 d | 325 | 325 | Rp 3,737,500 | FULL_ORDER | 0.0 d |
| 4 | Epinefrin Injeksi 0.1% 1 ml | V/C | INTERMITTENT | 18.8 d | 9 | 9 | Rp 112,500 | FULL_ORDER | 0.0 d |
| 8 | Ceftriaxone 1 g Serbuk Injeksi | E/A | SMOOTH | 5.2 d | 283 | 283 | Rp 5,235,500 | FULL_ORDER | 0.0 d |
| 13 | Albumin Human 20% 100 ml | N/A | INTERMITTENT | 3.9 d | 11 | 11 | Rp 13,750,000 | FULL_ORDER | 0.0 d |
| 14 | Neurotropik B1-B6-B12 Tablet | N/B | SMOOTH | 6.3 d | 327 | 0 | Rp 0 | EXCLUDED_OVER_BUDGET | 23.7 d |
| 15 | Salep Kulit Pelembab Khusus | N/C | INTERMITTENT | 9.1 d | 12 | 0 | Rp 0 | EXCLUDED_OVER_BUDGET | 20.9 d |
| 16 | Multivitamin Sirup 100 ml | N/B | INTERMITTENT | 9.6 d | 57 | 0 | Rp 0 | EXCLUDED_OVER_BUDGET | 20.4 d |

### 6.3 Automated Software Tests
All **8 unit & integration tests** (`python -m unittest discover -s tests -v`) pass in `0.189s` covering schema validation, DOEN flagging, SBA intermittent stability, ED capping, budget ranking, SQLite history, simulation comparison, and epoch-loss convergence.

### 6.4 Risks, Privacy, and Sustainability
- **Key Risks & Mitigations:** Synthetic demand distributions may differ from real seasonal outbreaks — mitigated by pharmacy team calibration review and manual quantity overrides (`adjustment_reason`). Unconfirmed DOEN-suggested VEN tags require pharmacist sign-off before locking.
- **Privacy:** Strictly zero patient identifiers or clinical records; all processing uses aggregate item counts and local credentials stay outside version control.
- **Sustainability:** Built on open-source Python and standard SIMRS Excel exports, requiring zero proprietary license fees for public hospitals.

---

## 7. References and Declaration

### 7.1 Third-Party Resources
- **Python Standard Library (`sqlite3`, `unittest`, `argparse`, `json`, `math`)** — relational persistence, testing, and CLI.
- **NumPy (`>=2.0`)** — vectorized neural network training (Adam/Huber) and statistical metrics.
- **Pandas & OpenPyXL** — `.xlsx`/`.csv` spreadsheet ingestion and column schema validation.

### 7.2 Material AI Assistance Disclosure (Per STACK 2026 Rules)
- **Tool Used:** Antigravity / Gemini AI Coding Assistant.
- **Role & Scope:** Assisted with structuring modular Python architecture, drafting the pure-NumPy MLP training loop and simulation harness, formatting documentation/proposal drafts, and verifying automated unit tests. All mathematical design choices, clinical VEN/DOEN rules, fairness constraints, and repository outputs were reviewed, executed, and verified by the team.

### 7.3 References
1. **[1]** Team interview with the Head of Pharmacy, RSUD Kilisuci, Kediri City, 9–10 November 2026.
2. **[2]** Ministry of Health of the Republic of Indonesia (2016). *Permenkes RI No. 72 Tahun 2016 on Hospital Pharmacy Service Standards.*
3. **[3]** Padang Hospital Drug Planning Study linking consumption-only planning to missed patient growth and expired drugs.
4. **[4]** National Health Insurance (*JKN / BPJS Kesehatan*) drug benefit regulations & National Essential Medicines List (*DOEN / FORNAS*).
5. **[5]** Indonesian National Public Procurement Agency (*LKPP*) — Electronic Catalogue (*e-Katalog*).
6. **[6]** Thai Community Hospital Study on sporadic demand forecasting and vital drug availability.
7. **[7]** Syntetos, A. A., & Boylan, J. E. (2005). *The accuracy of intermittent demand estimates.* International Journal of Forecasting.

### 7.4 Declaration of Originality
*(Attach the signed Declaration of Originality downloaded from `s.id/DeclarationOfOriginalitySTACK2026` as the final appendix page when exporting to PDF for submission.)*
