# STACK 2026 — Final Phase Report & Product Package
**Project:** SigapStok — Pattern-Matched Pharmacy Demand Forecasting & Vital-First Budget Ranking  
**Case:** Case 2 — Stronger Communities and Everyday Services  
**Repository:** https://github.com/FahmiGF/StackHackathon  

---

## 1. Version History: Starting vs. Final Version
- **Starting Version (Semifinal Cutoff — commit `96a2c5f`):**
  - Python core engine (`sigapstok/`): relational SQLite DB (`schema.sql`), `.xlsx`/`.csv` upload & column inspection (`ingestion.py`), `ADI/CV²` + `SES/Damped Holt/SBA` + `ABC/XYZ/FSN` + ED-usable stock (`forecasting.py`), 250-epoch Hybrid MLP trainer (`trainer.py`), Section 4.4 budget ranker (`ranking.py`), 6-month fair simulation (`simulation.py`), CLI (`main.py`), and 8 unit tests.
- **Final Version Improvements (Final Phase Build):**
  1. **Working Web Application (`web_app.py`):** Built a complete zero-external-framework web dashboard (`http://127.0.0.1:8000`) implementing the end-to-end user flow:
     - Spreadsheet upload (`.xlsx` / `.csv`) + 1-click **Load RSUD Synthetic Demo**
     - Column inspection warnings & DOEN badge display
     - Interactive **VEN confirmation dropdown** (`V / E / N`) per item
     - **Human-in-the-loop quantity override** (`Edit`) with mandatory audit reason persisted to SQLite
     - **Interactive Budget Sensitivity Slider** (`Apply Budget`) updating rankings and `expected_days_without_stock` in real time
     - **One-Page Printable Ranking View** (`window.print()`) and **Procurement CSV Export** (`/api/export_csv`)
     - **On-Demand 6-Month Fair Simulation Panel** (`/api/simulate`)
  2. **Automated Web Integration Test (`tests/test_web_app.py`):** Verifies the live HTTP flow (demo load, manual quantity adjustment with audit trail, and CSV export).
  3. **Presentation Deck (`docs/STACK2026_FINAL_DECK.pdf`):** 13-slide PDF deck formatted for the 10-minute presentation & live demo + 10-minute Q&A.

---

## 2. How to Run the Working Prototype
```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Launch the SigapStok Web Application
python web_app.py
# Open http://127.0.0.1:8000 in your browser

# 3. Run all automated unit & web integration tests
python -m unittest discover -s tests -v
```

---

## 3. Validation Summary (Observed Metrics)
- **250-Epoch Hybrid Forecaster (Held-Out Test Set, Months 30–35):**
  - `RSUD_1Mo_Plus_10Pct`: MAE **73.31** | Accuracy **74.09%**
  - `Excel_3Mo_AMC`: MAE **58.49** | Accuracy **79.33%**
  - `SigapStok_Untrained_Stat`: MAE **53.12** | Accuracy **81.23%**
  - **`SigapStok_Trained_Hybrid`:** MAE **51.26** | Accuracy **81.89%**
- **6-Month Fair Simulation (Budget Rp 30,000,000/month, Identical Demand & FEFO Expiry):**
  - `RSUD_Current_Formula`: **58** Vital Stockout Days | **191** Total Stockout Days | **83.80%** Fill Rate
  - `Static_Excel_3Mo_AMC`: **45** Vital Stockout Days | **170** Total Stockout Days | **87.65%** Fill Rate
  - **`SigapStok_Trained`:** **24** Vital Stockout Days (**-58.6%** vs RSUD) | **110** Total Stockout Days | **88.94%** Fill Rate

---

## 4. Known Limitations & Simulated Data Disclosure
- **Synthetic Data:** All 18 SKUs and 36-month histories are **synthetic data** calibrated to mimic RSUD Kilisuci's Excel exports (including *Acarbose 100 mg*, *Aciclovir 200 mg*, *Spuit 50 ml*) without real patient records.
- **Single-Warehouse v1 Scope:** Covers one pharmacy warehouse and one monthly procurement cycle; multi-warehouse transfers and direct SIMRS API integration are planned next steps.
- **Irreducible Noise on Erratic/Lumpy Items:** Overall WAPE accuracy is bounded at ~81.89% due to ±48% erratic and 2.5× lumpy synthetic variance; `Smooth` routine items are tracked separately in `models/sigapstok_hybrid.json`.

---

## 5. Material AI Assistance Disclosure & Team Contributions
- **AI Assistance:** Antigravity / Gemini AI Coding Assistant assisted with Python module structure, `web_app.py` frontend/API scaffolding, epoch trainer implementation, and documentation formatting. All logic, clinical rules, and test runs were verified by the team.
- **Team Contributions:**
  - `FahmiGF`: Database schema, file upload & column inspection, forecasting & epoch trainer, Section 4.4 budget ranking, Section 2.4 Permenkes/VEN analysis, `web_app.py`, simulation, and documentation.
  - Member B: Fair simulation protocol & validation calibration.
  - Member C / D: UI usability review, domain validation, and pitch deck/video delivery.
