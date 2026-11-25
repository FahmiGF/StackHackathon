# LAPORAN TEKNIS SIGAPSTOK (BAHASA INDONESIA)
## Sistem Peramalan Kebutuhan Obat Adaptif, Klasifikasi VEN/ABC/XYZ, dan Pemeringkatan Anggaran Farmasi RSUD Kilisuci

---

## 1. Ringkasan Eksekutif & Permasalahan
Di **RSUD Kilisuci, Kota Kediri**, perencanaan pengadaan obat bulanan selama ini bergantung pada satu rumus konsumsi tunggal (`Pemakaian 1 bulan + cadangan 10% - sisa stok`) [1]. Pendekatan ini memicu kekosongan pada obat *life-saving* yang jarang dipakai serta kelebihan pesanan/kedaluwarsa pada obat rutin, tanpa peringkat prioritas ketika anggaran menipis.

---

## 2. Pelatihan Model (*Epoch Training*) & Evaluasi Akurasi
Model **SigapStok Trained Hybrid** dilatih selama **160 epoch** (best checkpoint: **Epoch 35**, `best_val_loss = 0.10180`):

| Epoch | Train Loss | Validation Loss |
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

| Model / Metode | MAE | RMSE | sMAPE (%) | WAPE (%) | Akurasi (100 - WAPE) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| RSUD_1Mo_Plus_10Pct | 59.28 | 121.94 | 41.72% | 21.82% | **78.18%** |
| Excel_3Mo_AMC | 44.29 | 87.71 | 53.28% | 16.31% | **83.69%** |
| SigapStok_Untrained_Stat | 39.86 | 80.14 | 68.27% | 14.67% | **85.33%** |
| SigapStok_MLP_Only | 43.50 | 85.91 | 63.14% | 16.02% | **83.98%** |
| SigapStok_Trained_Hybrid | 36.72 | 74.16 | 67.37% | 13.52% | **86.48%** |

> Penurunan **MAE** sebesar **38.1%** dibanding rumus eksisting RSUD (`59.28` → `36.72`).

---

## 3. Hasil Pemeringkatan Anggaran (Pagu Rp 35,000,000)
- **Total Kebutuhan Ideal:** Rp 36,548,350
- **Total Dialokasikan:** Rp 34,672,350 (Sisa: Rp 327,650)

| Rank | Nama Obat | VEN/ABC | Pola | Sisa Stok (Hari) | Usulan | Alokasi | Biaya | Status | Hari Kosong | Catatan |
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

## 4. Hasil Simulasi Perbandingan Adil (6 Bulan, Pagu Rp 30,000,000/Bulan)
| Strategi | Vital Stockout Days | Total Stockout Days | Expired Units | Nilai Kerugian ED | Fill Rate (%) | Porsi Anggaran Vital (%) |
| :--- | :---: | :---: | :---: | ---: | :---: | :---: |
| RSUD_Current_Formula | 58 | 191 | 0.0 | Rp 0 | 83.80% | 43.19% |
| Static_Excel_3Mo_AMC | 45 | 170 | 0.0 | Rp 0 | 87.65% | 44.84% |
| SigapStok | 26 | 112 | 0.0 | Rp 0 | 88.40% | 38.95% |
| SigapStok_Trained | 23 | 108 | 0.0 | Rp 0 | 89.43% | 39.43% |
