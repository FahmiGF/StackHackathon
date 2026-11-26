# SigapStok — Pattern-Matched Pharmacy Demand Forecasting & Vital-First Budget Ranking

**STACK 2026 (GDGoC ITB) — Case 2: Stronger Communities and Everyday Services**

**SigapStok** is a Python-based decision-support prototype designed for **RSUD Kilisuci (Kediri City)**. It replaces uniform consumption ordering (`1 month + 10% - stock`) with pattern-matched statistical & epoch-trained hybrid forecasting, expiry-date (*ED*) usable-stock capping, and a transparent **Vital-first** budget ranking engine that quantifies `expected_days_without_stock` for excluded items.

---

## 1. Current Scope, Version & Honest Progress Status
- **Current Version:** `1.0.0` (Final Phase Build: Working Web App, Forecasting Engine, Epoch Trainer, DB, Simulation & Presentation Deck)
- **Completed Features:**
  - Interactive **Web Application** (`web_app.py` at `http://127.0.0.1:8000`) supporting `.xlsx`/`.csv` upload, 1-click RSUD demo load, VEN confirmation, manual quantity overrides with audit reasons, interactive budget slider, printable one-page ranking, and CSV export.
  - `.xlsx` / `.csv` spreadsheet upload & column schema validation (`sigapstok/ingestion.py`) with DOEN-assisted VEN suggestions.
  - SQLite relational schema & full history persistence (`sigapstok/schema.sql`, `sigapstok/db.py`).
  - Syntetos–Boylan (`ADI/CV²`) pattern classification + `SES`, `Damped Holt`, `SBA` + **160-epoch Hybrid MLP** (`sigapstok/forecasting.py`, `sigapstok/trainer.py`).
  - `ABC`, `XYZ`, `FSN`, `ABC–VEN` classification and ED-adjusted usable stock capping.
  - Vital-first budget ranking engine & one-page report generator (`sigapstok/ranking.py`).
  - Fair 6-month comparison simulation under identical budget, demand, lead time, and FEFO expiry rules (`sigapstok/simulation.py`).
- **Simulated Functionality:**
  - All evaluations currently use **synthetic multi-month datasets** (`sigapstok/synthetic_data.py`) mimicking RSUD Kilisuci exports without patient records.
- **Run the Web Application:**
  ```bash
  python web_app.py
  # Open http://127.0.0.1:8000
  ```

---

## 2. Setup, Dependencies & Supported Environment
- **Supported Environment:** Python `3.11+` (tested on Python `3.11.9`, Windows 11).
- **Dependencies:** `numpy`, `pandas`, `openpyxl`, plus Python standard library (`sqlite3`, `unittest`).

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run 160-epoch model training & held-out accuracy evaluation
python main.py train --epochs 160

# 3. Run synthetic end-to-end ingestion, DB storage & one-page ranking demo
python main.py demo --budget 35000000

# 4. Run 6-month fair comparison simulation across all strategies
python main.py simulate --budget 30000000 --months 6

# 5. Generate STACK 2026 Semifinal Proposal (MD + A4 HTML) & Technical Report
python main.py report --epochs 160 --months 6

# 6. Run automated test suite (8/8 tests)
python -m unittest discover -s tests -v
```

---

## 3. Repository Structure
```text
StackHackathon/
├── main.py                                 # CLI: demo, train, simulate, report
├── requirements.txt                        # Python dependencies
├── models/
│   └── sigapstok_hybrid.json               # Saved epoch-trained MLP & tuned stat weights
├── sigapstok/
│   ├── schema.sql                          # Relational SQLite schema
│   ├── db.py                               # History & batch persistence layer
│   ├── ingestion.py                        # File upload, column validation, DOEN/VEN check
│   ├── forecasting.py                      # ADI/CV², SES/Holt/SBA, ABC/XYZ/FSN, ED-capping
│   ├── trainer.py                          # 160-epoch NumPy MLP + parameter tuning
│   ├── ranking.py                          # Section 4.4 Vital-first budget ranking logic
│   ├── synthetic_data.py                   # Synthetic RSUD Kilisuci dataset generator
│   ├── simulation.py                       # Fair 6-month FEFO comparison simulation
│   └── report_builder.py                   # STACK 2026 Proposal & Laporan builder
├── docs/
│   ├── STACK2026_SEMIFINAL_PROPOSAL.md     # English Semifinal Proposal (STACK 2026 format)
│   ├── STACK2026_SEMIFINAL_PROPOSAL.pdf    # Print-ready A4 PDF (max 10 content pages)
│   ├── LAPORAN_SIGAPSTOK.md                # Technical summary report (Indonesian)
│   ├── 2.4_existing_alternatives.md        # Permenkes 72/2016 & SigapStok vs VEN analysis
│   ├── 4.4_budget_ranking_logic.md         # Budget ranking specification
│   └── simulation_fairness.md              # Fair comparison agreement
└── tests/
    └── test_sigapstok.py                   # Unit & integration test suite
```

---

## 4. Third-Party Resources & Material AI Assistance Disclosure
- **Third-Party Libraries:** `numpy`, `pandas`, `openpyxl`, Python standard library (`sqlite3`, `unittest`).
- **Material AI Assistance Disclosure (Per STACK 2026 Handbook Rules):**
  - **Tool Used:** Antigravity / Gemini AI Coding Assistant.
  - **Role:** Assisted in structuring the modular Python codebase, implementing the pure-NumPy MLP epoch trainer and FEFO simulation harness, drafting documentation/proposal structure, and verifying automated tests. All domain rules (Permenkes/VEN/DOEN), mathematical formulations, simulation fairness criteria, and code outputs were reviewed, executed, and validated by the team.

---

## 5. Section 7 — References & Resources
1. **[1]** Team interview with the Head of Pharmacy, RSUD Kilisuci, Kediri City, 9–10 November 2026.
2. **[2]** Ministry of Health RI (2016). *Permenkes RI No. 72 Tahun 2016 on Hospital Pharmacy Service Standards.*
3. **[3]** Padang Hospital Drug Planning Study on consumption-based forecasting limitations and expired inventory.
4. **[4]** National Health Insurance (*JKN / BPJS Kesehatan*) drug service rules & DOEN / FORNAS.
5. **[5]** LKPP Electronic Catalogue (*e-Katalog Obat*) public procurement portal.
6. **[6]** Thai Community Hospital Study on sporadic-demand forecasting and vital drug availability.
7. **[7]** Syntetos, A. A., & Boylan, J. E. (2005). *The accuracy of intermittent demand estimates.* International Journal of Forecasting.
