# STACK 2026 — Semifinal Explanatory Video Script (Max 2:00)

**Target Specs (Handbook Page 11):** `<= 2 minutes` | `1080p` | Clear English narration or English subtitles.  
**Rubric Alignment (Handbook Pages 16–17):**
- Team & Context Introduction (`15%`)
- Problem & Solution Explanation (`25%`)
- User Flow / Prototype Showcase (`30%`)
- Progress Honesty & Next Steps (`20%`)
- English & Production Quality (`10%`)

---

## Shot-by-Shot Script (~115 Seconds)

### [0:00 – 0:18] Team & Context Introduction (15%)
* **Visual:** Title card with team name, **Case 2: Stronger Communities and Everyday Services**, and team members on camera / split-screen.
* **Narration:**
  > "Hello judges! We are `[Team Name]`, presenting **SigapStok** for STACK 2026 under **Case 2: Stronger Communities and Everyday Services**. Our team—Fahmi, `[Member B]`, `[Member C]`, and `[Member D]`—is tackling hospital pharmacy inventory planning, inspired by real operational challenges at **RSUD Kilisuci**, a public hospital in Kediri City."

### [0:18 – 0:48] Problem & Solution Explanation (25%)
* **Visual:** Quick diagram contrasting `1.10 × Last Month - Stock` (0 order on quiet months, over-order/expiry on spikes) vs. **SigapStok** (`ADI/CV²` + `ED-Capping` + `Vital-First Ranking`).
* **Narration:**
  > "Currently, RSUD Kilisuci sets every monthly drug order using one uniform formula: one month of usage plus a 10% reserve minus stock. Because of this, rarely used life-saving drugs receive zero orders after a quiet month, while busy months cause over-ordering and drug expiration. And when the budget runs short, the formula cannot prioritize critical medicines, leaving JKN patients waiting. **SigapStok** solves this by matching forecasting methods to each drug's usage pattern, capping usable stock by expiry date, and ranking purchases Vital-first."

### [0:48 – 1:25] User Flow / Prototype Showcase (30%)
* **Visual:** Screen recording of `python web_app.py` (`http://127.0.0.1:8000`) showing:
  1. Clicking **Load RSUD Synthetic Demo** (or uploading `.xlsx` sheets) & DOEN/VEN flags.
  2. Showing *Acarbose 100 mg* flagged for expiry risk (`NOT_NEEDED` order) while *Epinefrin* & *SABU* (intermittent Vital drugs) are protected.
  3. Clicking **Edit** on a proposed quantity and entering a reason.
  4. Moving the **Budget Sensitivity Slider** to `Rp 30,000,000`, showing Vital drugs funded at Ranks 1–7 and excluded non-essential items clearly marked with **`expected_days_without_stock`**, then clicking **Run 6-Month Fair Simulation** (`Vital Stockout Days` dropping from `58` to `24`).
* **Narration:**
  > "Here is our working prototype. Pharmacy staff upload their usage/stock export and price sheet—here loaded with synthetic RSUD-style data. SigapStok inspects columns, flags DOEN essential candidates, and protects intermittent Vital drugs using Syntetos–Boylan (SBA) forecasting while warning about expiring stock like Acarbose. Staff can adjust any quantity with an audit reason, set the monthly budget cap, and instantly see which items are funded and how many days without stock excluded items face—then export a one-page plan for management and e-Catalogue procurement."

### [1:25 – 1:55] Progress Honesty & Next Steps (20%)
* **Visual:** Split slide showing **Completed** (DB, ingestion, 250-epoch Hybrid Forecaster, Section 4.4 ranker, 6-month simulation, 9/9 tests, local Web UI) vs **Synthetic/Planned** (synthetic data disclaimer, pilot calibration with RSUD staff, direct e-Catalogue code mapping).
* **Narration:**
  > "To be transparent about our progress: our relational database, column validator, 250-epoch hybrid forecaster, Vital-first budget ranker, 6-month simulation, and local web prototype are complete and verified by 9 automated tests. Currently, all evaluations use synthetic data mimicking RSUD Kilisuci exports, without patient records. Next, we will calibrate thresholds with the pharmacy team, add multi-sheet Excel export, and prepare direct e-Catalogue item mapping. Thank you!"

---

## Production Checklist Before Exporting Video
- [ ] Resolution **1920×1080 (1080p)**, MP4 format.
- [ ] Total duration **<= 2:00** (aim for `1:50–1:55`).
- [ ] English audio is clear with English burned-in or SRT subtitles.
- [ ] Synthetic data & current progress are stated honestly.
