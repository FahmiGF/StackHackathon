# STACK 2026 — Final Day Pitching & Live Demo Script (10 Min Pitch + 10 Min Q&A)

**Deck:** [STACK2026_FINAL_DECK.pdf](STACK2026_FINAL_DECK.pdf) (`13` pages: 1 cover + 12 content slides)  
**Live App:** `python web_app.py` → `http://127.0.0.1:8000`  

---

## Part 1: Presentation & Live Demo Timing (10 Minutes)

| Time | Slide(s) | Speaker Focus |
| :--- | :--- | :--- |
| **0:00 – 1:00** | Cover + Slide 1–2 | Introduce team, Case 2, and RSUD Kilisuci problem (`1 mo + 10% - stock` failure on sporadic life-saving drugs & expiry). |
| **1:00 – 2:30** | Slide 3–4 | Explain Permenkes 72/2016, why conventional VEN alone is not enough, and our v1 scope (1 warehouse, 1 cycle, no PII). |
| **2:30 – 5:30** | **LIVE DEMO** (`web_app.py`) | 1. Show synthetic RSUD upload / **Load Demo**.<br>2. Point out DOEN badge & **Acarbose** ED warning (`0` order).<br>3. Edit 1 quantity with an audit reason.<br>4. Drag Budget Slider to `Rp 30M` → show Vital Ranks 1–7 funded & `expected_days_without_stock` on excluded items.<br>5. Click **Run 6-Month Fair Simulation** & show **Export CSV**. |
| **5:30 – 7:30** | Slide 5–8 | Walk through SQLite 7-table architecture, `ADI/CV²` + `SBA` + 250-epoch Hybrid MLP, ED capping, and Section 4.4 lexicographic priority key. |
| **7:30 – 9:00** | Slide 9–10 | Present validation: MAE `73.31 → 51.26`, Vital Stockout Days `58d → 24d` (`-58.6%`), and Final Day web/test milestones. |
| **9:00 – 10:00** | Slide 11–12 | State honest limitations (synthetic data, erratic variance), AI disclosure, and next steps (RSUD pilot & e-Catalogue mapping). |

---

## Part 2: Anticipated Judge Q&A (10 Minutes)

1. **Q: Why not use a single deep learning model for all drugs?**
   - *A:* Consistent with the Thai community hospital study [6], sporadic (*intermittent/lumpy*) drugs have too many zero months for standard regression/LSTM. That is why we classify every SKU by `ADI` and `CV²`, use **SBA (Syntetos–Boylan Approximation)** + a *Vital Standby Buffer* for sporadic items, and blend with our regularized 250-epoch MLP using validation-learned pattern weights.

2. **Q: How did you fix overfitting in your epoch training?**
   - *A:* Initially on 24 months with `hidden_dim=24`, `train_loss` dropped to `0.024` while `val_loss` rose after Epoch 35. We expanded rolling-origin history to 36 months, reduced `hidden_dim`, added **Dropout**, **L2 weight decay**, **Cosine LR annealing**, and **lag-12 seasonal features**, stabilizing `val_loss` around `0.086–0.094` across 250 epochs.

3. **Q: Why is overall accuracy ~81.89% instead of >95%?**
   - *A:* Our synthetic benchmark deliberately injects realistic ±48% erratic variance and 0.4×–2.5× lumpy spikes. Because random noise is irreducible (*Bayes error*), we also track `Smooth_Accuracy_pct` separately for routine items and prove operational impact via **Vital Stockout Days (`-58.6%`)**.

4. **Q: How does SigapStok differ from standard VEN in Permenkes 72/2016?**
   - *A:* Standard VEN is a static manual tag (`V/E/N`). SigapStok integrates **DOEN-assisted VEN flagging**, **pattern-matched forecasting**, **ED-usable stock capping**, and **quantified `expected_days_without_stock`** whenever budget cuts occur.

5. **Q: Is any real hospital or patient data exposed in the repo?**
   - *A:* No. Zero patient records are used, and all demonstrations use synthetic data (`sigapstok/synthetic_data.py`) calibrated to public/anonymized RSUD spreadsheet structures.
