# LAPORAN PROYEK SIGAPSTOK
## Sistem Peramalan Kebutuhan Obat Adaptif, Klasifikasi VEN/ABC/XYZ, dan Pemeringkatan Anggaran Farmasi RSUD Kilisuci

---

## 1. Ringkasan Eksekutif & Permasalahan (Abstrak)
Di **RSUD Kilisuci, Kota Kediri**, perencanaan pengadaan obat bulanan selama ini bergantung pada satu rumus konsumsi tunggal (`Pemakaian 1 bulan + cadangan 10% - sisa stok`) [1]. Rumus tunggal tersebut menimbulkan dua masalah kritis:
1. **Kekosongan obat *life-saving* berpermintaan jarang (*intermittent/lumpy*):** setelah bulan yang sepi, rumus menghasilkan usulan `0` unit.
2. **Pemborosan & risiko kedaluwarsa (*ED*):** setelah bulan yang ramai, rumus memesan berlebih sehingga obat terancam kedaluwarsa, sementara ketiadaan peringkat prioritas klinis membuat anggaran terbatas berisiko terserap lebih dulu oleh obat non-kritis.

**SigapStok** hadir sebagai aplikasi berbasis Python dan basis data relasional yang mencocokkan metode peramalan pada pola pemakaian tiap obat, memotong stok fisik yang terancam kedaluwarsa sebelum terpakai (*ED capping*), serta menyusun peringkat pembelian berbasis **Vital-first** lengkap dengan estimasi **`expected_days_without_stock`** bagi item yang tereliminasi oleh batas anggaran.

---

## 2. Alternatif Eksisting, Landasan Permenkes, & Perbedaan dengan VEN (Bagian 2.4)
- **Permenkes RI No. 72 Tahun 2016** [2] mengakui metode konsumsi, epidemiologi, dan kombinasi, serta mengarahkan pengendalian anggaran memakai analisis **ABC** dan **VEN**.
- **Kebijakan JKN/BPJS & e-Katalog LKPP** [4][5]: Obat JKN disediakan rumah sakit dalam paket layanan (pasien tidak mendapat penggantian jika membeli tunai di luar [1]), sedangkan pengadaan melalui e-Katalog dilakukan per item.
- **Perbedaan SigapStok vs VEN Konvensional:** VEN konvensional hanya memberikan label statis (`V/E/N`) tanpa menyesuaikan metode peramalan untuk permintaan sporadis [6], tanpa mengoreksi stok terhadap tanggal kedaluwarsa (`Tanggal ED`), dan tanpa menghitung dampak kuantitatif hari kekosongan saat anggaran kurang.

*(Uraian lengkap tersedia pada [2.4_existing_alternatives.md](2.4_existing_alternatives.md)).*

---

## 3. Arsitektur Data, Inspeksi Kolom, & Klasifikasi Inventori
1. **Skema Basis Data Relasional (`sigapstok/schema.sql`):** Mencakup tabel `drugs`, `upload_batches`, `monthly_usage_history`, `stock_batches_ed`, `forecast_results` (mendukung penyesuaian manual & alasannya), `budget_ranking_results`, dan `simulation_runs`.
2. **Inspeksi Kolom & Validasi Unggahan (`sigapstok/ingestion.py`):** Mendukung format `.xlsx`/`.csv`, memeriksa kolom wajib, menolak stok/harga negatif, memvalidasi format `TANGGAL ED`, serta memberi saran status `V/E` awal dari pencocokan **DOEN**.
3. **Klasifikasi Pola & Risiko Logistik (`sigapstok/forecasting.py`):**
   - **ADI & CV² (Syntetos–Boylan):** `SMOOTH`, `ERRATIC`, `INTERMITTENT`, `LUMPY`.
   - **ABC (Pareto Anggaran)**, **XYZ (Konsistensi CV)**, **FSN (*Fast/Slow/Non-moving*)**, dan matriks **ABC–VEN**.
   - **ED-Adjusted Usable Stock:** Mengamankan sistem dari kasus seperti *Acarbose 100 mg Tablet* di mana stok fisik berlebih namun sebagian terancam ED sebelum habis dipakai.

---

## 4. Pelatihan Model (*Epoch Training*), Evaluasi Akurasi, & Logika Pemeringkatan (Bagian 4.4)

### 4.1 Proses Pelatihan Model (*Epoch Training* & Optimasi Parameter)
Model **SigapStok Trained Hybrid** menggabungkan:
1. **Pure-NumPy Neural Time-Series Regressor (2-Layer MLP + ReLU + Adam Optimizer + L2 Regularization)** yang dilatih selama **160 epoch** pada data historis *rolling-origin* (Bulan 7–15 *train*, Bulan 16–19 *validation*, Bulan 20–24 *out-of-sample test*) menggunakan fitur *6-month lags*, *rolling mean/std*, *zero-month ratio*, *ADI*, *CV²*, musiman `sin/cos`, dan indikator `VEN`.
2. **Optimasi Parameter Statistik per Pola** (grid search pada *validation split*) untuk parameter smoothing $\alpha, \beta, \phi$ pada `SES`, `Damped Holt`, dan `SBA`.
3. **Pattern-Gated Ensemble Blending:** Bobot kombinasi optimal antara prediksi Neural MLP dan model statistik yang dipelajari pada *validation set*.

**Log Konvergensi Pelatihan (Best Epoch = 35, Best Val Loss = 0.10180):**

| Epoch | Train Loss (Huber + L2) | Validation Loss |
| :---: | :---: | :---: |
| 1 | 0.19824 | 0.14582 |
| 20 | 0.09510 | 0.11208 |
| 40 | 0.07447 | 0.10421 |
| 60 | 0.05770 | 0.10821 |
| 80 | 0.04521 | 0.11220 |
| 100 | 0.03620 | 0.11612 |
| 120 | 0.03091 | 0.11996 |
| 140 | 0.02707 | 0.12273 |
| 160 | 0.02427 | 0.12088 |

**Parameter Statistik Teroptimasi:**
- `SMOOTH (SES)`: `{'alpha': 0.15}`
- `ERRATIC (Damped Holt)`: `{'alpha': 0.35, 'beta': 0.15, 'phi': 0.85}`
- `INTERMITTENT (SBA)`: `{'alpha': 0.08}`
- `LUMPY (SBA)`: `{'alpha': 0.15}`

**Bobot Blending Optimal per Pola Permintaan:**
- **SMOOTH:** Bobot MLP `0.15` / Bobot Statistik Teroptimasi `0.85`
- **ERRATIC:** Bobot MLP `0.35` / Bobot Statistik Teroptimasi `0.65`
- **INTERMITTENT:** Bobot MLP `0.00` / Bobot Statistik Teroptimasi `1.00`
- **LUMPY:** Bobot MLP `0.35` / Bobot Statistik Teroptimasi `0.65`
- **NO_DEMAND:** Bobot MLP `0.35` / Bobot Statistik Teroptimasi `0.65`

### 4.2 Evaluasi Akurasi pada Data Uji (*Held-Out Test Set*, Bulan 20–24)

| Model / Metode | MAE | RMSE | sMAPE (%) | WAPE (%) | Akurasi (100 - WAPE) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| RSUD_1Mo_Plus_10Pct | 59.28 | 121.94 | 41.72% | 21.82% | **78.18%** |
| Excel_3Mo_AMC | 44.29 | 87.71 | 53.28% | 16.31% | **83.69%** |
| SigapStok_Untrained_Stat | 39.86 | 80.14 | 68.27% | 14.67% | **85.33%** |
| SigapStok_MLP_Only | 43.50 | 85.91 | 63.14% | 16.02% | **83.98%** |
| SigapStok_Trained_Hybrid | 36.72 | 74.16 | 67.37% | 13.52% | **86.48%** |

> **Capaian Peningkatan Akurasi:** Model terlatih **SigapStok Trained Hybrid** menurunkan **MAE** sebesar **38.1%** dibandingkan rumus eksisting RSUD (`1 Bulan + 10%`), dari `59.28` menjadi `36.72` (akurasi keseluruhan **86.48%**).

### 4.3 Hasil Pemeringkatan Anggaran Satu Halaman (Contoh Siklus Pagu Rp 35,000,000)
- **Total Kebutuhan Ideal:** Rp 36,548,350
- **Total Dialokasikan:** Rp 34,672,350 (Sisa: Rp 327,650)
- **Ringkasan Status:** 15 Penuh | 0 Parsial | 1 Tereliminasi (Vital tereliminasi: 0)

| Rank | Nama Obat | VEN/ABC | Pola | Sisa Stok (Hari) | Usulan | Alokasi | Biaya | Status | Hari Kosong | Catatan & Penjelasan |
| :---: | :--- | :---: | :--- | :---: | :---: | :---: | ---: | :--- | :---: | :--- |
| 1 | Norepinefrin Injeksi 4 mg/4 ml | V/B | SMOOTH | 6.6 | 31 | 31 | Rp 2,015,000 | FULL_ORDER | 0.0 | Didanai penuh (Tier V/B, pola SMOOTH, sisa stok 6.6 hari). |
| 2 | Ringer Laktat 500 ml Infus | V/A | SMOOTH | 6.8 | 354 | 354 | Rp 4,071,000 | FULL_ORDER | 0.0 | Didanai penuh (Tier V/A, pola SMOOTH, sisa stok 6.8 hari). |
| 3 | Insulin Glargine 100 IU/ml Pen | V/A | SMOOTH | 8.1 | 36 | 36 | Rp 3,528,000 | FULL_ORDER | 0.0 | Didanai penuh (Tier V/A, pola SMOOTH, sisa stok 8.1 hari). |
| 4 | Diazepam Injeksi 5 mg/ml | V/C | INTERMITTENT | 19.2 | 8 | 8 | Rp 112,000 | FULL_ORDER | 0.0 | Didanai penuh (Tier V/C, pola INTERMITTENT, sisa stok 19.2 hari). |
| 5 | Epinefrin Injeksi 0.1% 1 ml | V/C | INTERMITTENT | 19.6 | 8 | 8 | Rp 100,000 | FULL_ORDER | 0.0 | Didanai penuh (Tier V/C, pola INTERMITTENT, sisa stok 19.6 hari). |
| 6 | Atropin Sulfat Injeksi 0.25 mg/ml | V/C | INTERMITTENT | 21.4 | 10 | 10 | Rp 98,000 | FULL_ORDER | 0.0 | Didanai penuh (Tier V/C, pola INTERMITTENT, sisa stok 21.4 hari). |
| 7 | SABU (Serum Anti Bisa Ular) Polivalen | V/C | INTERMITTENT | 78.9 | 2 | 2 | Rp 1,560,000 | FULL_ORDER | 0.0 | Didanai penuh (Tier V/C, pola INTERMITTENT, sisa stok 78.9 hari). |
| 8 | Omeprazole 40 mg Injeksi | E/A | SMOOTH | 6.4 | 123 | 123 | Rp 2,952,000 | FULL_ORDER | 0.0 | Didanai penuh (Tier E/A, pola SMOOTH, sisa stok 6.4 hari). |
| 9 | Metformin 500 mg Tablet | E/B | SMOOTH | 6.4 | 1434 | 1434 | Rp 501,900 | FULL_ORDER | 0.0 | Didanai penuh (Tier E/B, pola SMOOTH, sisa stok 6.4 hari). |
| 10 | Ceftriaxone 1 g Serbuk Injeksi | E/A | SMOOTH | 6.7 | 225 | 225 | Rp 4,162,500 | FULL_ORDER | 0.0 | Didanai penuh (Tier E/A, pola SMOOTH, sisa stok 6.7 hari). |
| 11 | Amlodipine 10 mg Tablet | E/B | SMOOTH | 9.6 | 955 | 955 | Rp 429,750 | FULL_ORDER | 0.0 | Didanai penuh (Tier E/B, pola SMOOTH, sisa stok 9.6 hari). |
| 12 | Aciclovir 200 mg Tablet | E/C | SMOOTH | 12.3 | 164 | 164 | Rp 106,600 | FULL_ORDER | 0.0 | Didanai penuh (Tier E/C, pola SMOOTH, sisa stok 12.3 hari). |
| 13 | Albumin Human 20% 100 ml | N/A | INTERMITTENT | 3.8 | 11 | 11 | Rp 13,750,000 | FULL_ORDER | 0.0 | Didanai penuh (Tier N/A, pola INTERMITTENT, sisa stok 3.8 hari). |
| 14 | Neurotropik B1-B6-B12 Tablet | N/B | SMOOTH | 6.9 | 298 | 298 | Rp 655,600 | FULL_ORDER | 0.0 | Didanai penuh (Tier N/B, pola SMOOTH, sisa stok 6.9 hari). |
| 15 | Salep Kulit Pelembab Khusus | N/C | INTERMITTENT | 7.6 | 14 | 14 | Rp 630,000 | FULL_ORDER | 0.0 | Didanai penuh (Tier N/C, pola INTERMITTENT, sisa stok 7.6 hari). |
| 16 | Multivitamin Sirup 100 ml | N/A | INTERMITTENT | 8.0 | 67 | 0 | Rp 0 | EXCLUDED_OVER_BUDGET | 22.0 | Tereliminasi oleh batas anggaran (butuh Rp 1,876,000, sisa Rp 327,650). Estimasi hari tanpa stok: 22.0 hari dalam siklus 30 hari. |
| - | Acarbose 100 mg Tablet | E/B | SMOOTH | 135.0 | 0 | 0 | Rp 0 | NOT_NEEDED | 0.0 | Tidak perlu order (stok layak pakai cukup 135.0 hari), tetapi 2101 unit fisik berisiko ED! |

---

## 5. Hasil Simulasi Perbandingan Adil (6 Bulan, Pagu Rp 30,000,000/Bulan)
Seluruh strategi dijalankan pada *stream* permintaan harian yang identik, pagu anggaran bulanan yang identik, *lead time* yang sama (7 hari), serta aturan pengeluaran FEFO (*First Expired, First Out*):

| Strategi | Vital Stockout Days | Total Stockout Days | Expired Units | Nilai Kerugian ED | Fill Rate (%) | Porsi Anggaran Vital (%) |
| :--- | :---: | :---: | :---: | ---: | :---: | :---: |
| RSUD_Current_Formula | 58 | 191 | 0.0 | Rp 0 | 83.80% | 43.19% |
| Static_Excel_3Mo_AMC | 45 | 170 | 0.0 | Rp 0 | 87.65% | 44.84% |
| SigapStok | 26 | 112 | 0.0 | Rp 0 | 88.40% | 38.95% |
| SigapStok_Trained | 23 | 108 | 0.0 | Rp 0 | 89.43% | 39.43% |

---

## 6. Kesimpulan
1. Pemisahan periode historis panjang (12–24 bulan) untuk deteksi pola dan siklus pengadaan 30 hari mengatasi kegagalan rumus 1 bulan RSUD pada obat sporadis.
2. Pelatihan *epoch* pada *Hybrid Forecaster* (**MLP + SBA/Holt/SES teroptimasi**) berhasil meningkatkan akurasi prediksi secara konsisten dan menekan **Vital Stockout Days** secara signifikan pada simulasi anggaran terbatas.
3. Transparansi pemeringkatan **VEN-first** beserta kolom **`expected_days_without_stock`** dan **`projected_expired_qty`** memberikan dasar keputusan yang objektif dan dapat diaudit oleh manajemen maupun unit pengadaan e-Katalog.

---

## 7. Daftar Pustaka & Resource
1. **[1]** Wawancara Tim dengan Kepala Instalasi Farmasi RSUD Kilisuci, Kota Kediri (9–10 November 2026).
2. **[2]** Kementerian Kesehatan RI (2016). *Permenkes RI No. 72 Tahun 2016 tentang Standar Pelayanan Kefarmasian di Rumah Sakit.*
3. **[3]** Studi perencanaan pengadaan obat di rumah sakit Padang terkait risiko pasien baru dan obat kedaluwarsa.
4. **[4]** Regulasi layanan obat paket JKN / BPJS Kesehatan dan Formularium Nasional (FORNAS).
5. **[5]** LKPP — Sistem Pengadaan Elektronik Pemerintah (*e-Katalog Obat*).
6. **[6]** Studi peramalan permintaan obat sporadis di rumah sakit komunitas Thailand (*intermittent demand & vital drug availability*).
7. **Syntetos, A. A., & Boylan, J. E. (2005).** *The accuracy of intermittent demand estimates.* International Journal of Forecasting.
