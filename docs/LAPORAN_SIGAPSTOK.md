# LAPORAN TEKNIS SIGAPSTOK (BAHASA INDONESIA)
## Sistem Peramalan Kebutuhan Obat Adaptif, Klasifikasi VEN/ABC/XYZ, dan Pemeringkatan Anggaran Farmasi RSUD Kilisuci

---

## 1. Ringkasan Eksekutif & Permasalahan
Di **RSUD Kilisuci, Kota Kediri**, perencanaan pengadaan obat bulanan selama ini bergantung pada satu rumus konsumsi tunggal (`Pemakaian 1 bulan + cadangan 10% - sisa stok`) [1]. Pendekatan ini memicu kekosongan pada obat *life-saving* yang jarang dipakai serta kelebihan pesanan/kedaluwarsa pada obat rutin, tanpa peringkat prioritas ketika anggaran menipis.

---

## 2. Pelatihan Model (*Epoch Training*) & Evaluasi Akurasi
Model **SigapStok Trained Hybrid** dilatih selama **200 epoch** (best checkpoint: **Epoch 58**, `best_val_loss = 0.08202`):

| Epoch | Train Loss | Validation Loss |
| :---: | :---: | :---: |
| 1 | 0.29914 | 0.24376 |
| 25 | 0.16496 | 0.09807 |
| 50 | 0.13291 | 0.08294 |
| 75 | 0.11968 | 0.08447 |
| 100 | 0.12034 | 0.08486 |
| 125 | 0.11843 | 0.08550 |
| 150 | 0.11623 | 0.08523 |
| 175 | 0.11491 | 0.08526 |
| 200 | 0.11458 | 0.08532 |

| Model / Metode | MAE | RMSE | sMAPE (%) | WAPE (%) | Akurasi (100 - WAPE) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| RSUD_1Mo_Plus_10Pct | 73.31 | 151.14 | 55.31% | 25.91% | **74.09%** |
| Excel_3Mo_AMC | 58.49 | 119.06 | 57.32% | 20.67% | **79.33%** |
| SigapStok_Untrained_Stat | 53.12 | 110.15 | 68.89% | 18.77% | **81.23%** |
| SigapStok_MLP_Only | 60.89 | 116.16 | 73.09% | 21.51% | **78.49%** |
| SigapStok_Trained_Hybrid | 51.95 | 105.09 | 69.53% | 18.36% | **81.64%** |

> Penurunan **MAE** sebesar **29.1%** dibanding rumus eksisting RSUD (`73.31` → `51.95`).

---

## 3. Hasil Pemeringkatan Anggaran (Pagu Rp 35,000,000)
- **Total Kebutuhan Ideal:** Rp 36,643,700
- **Total Dialokasikan:** Rp 34,507,700 (Sisa: Rp 492,300)

| Rank | Nama Obat | VEN/ABC | Pola | Sisa Stok (Hari) | Usulan | Alokasi | Biaya | Status | Hari Kosong | Catatan |
| :---: | :--- | :---: | :--- | :---: | :---: | :---: | ---: | :--- | :---: | :--- |
| 1 | Norepinefrin Injeksi 4 mg/4 ml | V/A | SMOOTH | 6.4 | 31 | 31 | Rp 2,015,000 | FULL_ORDER | 0.0 | Didanai penuh (Tier V/A, pola SMOOTH, sisa stok 6.4 hari). |
| 2 | Ringer Laktat 500 ml Infus | V/A | SMOOTH | 6.9 | 347 | 347 | Rp 3,990,500 | FULL_ORDER | 0.0 | Didanai penuh (Tier V/A, pola SMOOTH, sisa stok 6.9 hari). |
| 3 | Insulin Glargine 100 IU/ml Pen | V/A | SMOOTH | 8.3 | 35 | 35 | Rp 3,430,000 | FULL_ORDER | 0.0 | Didanai penuh (Tier V/A, pola SMOOTH, sisa stok 8.3 hari). |
| 4 | Epinefrin Injeksi 0.1% 1 ml | V/C | INTERMITTENT | 18.8 | 9 | 9 | Rp 112,500 | FULL_ORDER | 0.0 | Didanai penuh (Tier V/C, pola INTERMITTENT, sisa stok 18.8 hari). |
| 5 | Atropin Sulfat Injeksi 0.25 mg/ml | V/C | INTERMITTENT | 25.3 | 9 | 9 | Rp 88,200 | FULL_ORDER | 0.0 | Didanai penuh (Tier V/C, pola INTERMITTENT, sisa stok 25.3 hari). |
| 6 | Diazepam Injeksi 5 mg/ml | V/C | INTERMITTENT | 29.9 | 6 | 6 | Rp 84,000 | FULL_ORDER | 0.0 | Didanai penuh (Tier V/C, pola INTERMITTENT, sisa stok 29.9 hari). |
| 7 | SABU (Serum Anti Bisa Ular) Polivalen | V/C | INTERMITTENT | 65.2 | 3 | 3 | Rp 2,340,000 | FULL_ORDER | 0.0 | Didanai penuh (Tier V/C, pola INTERMITTENT, sisa stok 65.2 hari). |
| 8 | Omeprazole 40 mg Injeksi | E/A | SMOOTH | 6.6 | 118 | 118 | Rp 2,832,000 | FULL_ORDER | 0.0 | Didanai penuh (Tier E/A, pola SMOOTH, sisa stok 6.6 hari). |
| 9 | Ceftriaxone 1 g Serbuk Injeksi | E/A | SMOOTH | 6.6 | 227 | 227 | Rp 4,199,500 | FULL_ORDER | 0.0 | Didanai penuh (Tier E/A, pola SMOOTH, sisa stok 6.6 hari). |
| 10 | Metformin 500 mg Tablet | E/B | SMOOTH | 6.7 | 1350 | 1350 | Rp 472,500 | FULL_ORDER | 0.0 | Didanai penuh (Tier E/B, pola SMOOTH, sisa stok 6.7 hari). |
| 11 | Amlodipine 10 mg Tablet | E/B | SMOOTH | 10.0 | 904 | 904 | Rp 406,800 | FULL_ORDER | 0.0 | Didanai penuh (Tier E/B, pola SMOOTH, sisa stok 10.0 hari). |
| 12 | Aciclovir 200 mg Tablet | E/C | SMOOTH | 11.2 | 178 | 178 | Rp 115,700 | FULL_ORDER | 0.0 | Didanai penuh (Tier E/C, pola SMOOTH, sisa stok 11.2 hari). |
| 13 | Albumin Human 20% 100 ml | N/A | INTERMITTENT | 3.9 | 11 | 11 | Rp 13,750,000 | FULL_ORDER | 0.0 | Didanai penuh (Tier N/A, pola INTERMITTENT, sisa stok 3.9 hari). |
| 14 | Neurotropik B1-B6-B12 Tablet | N/B | SMOOTH | 6.7 | 305 | 305 | Rp 671,000 | FULL_ORDER | 0.0 | Didanai penuh (Tier N/B, pola SMOOTH, sisa stok 6.7 hari). |
| 15 | Salep Kulit Pelembab Khusus | N/C | INTERMITTENT | 9.1 | 12 | 0 | Rp 0 | EXCLUDED_OVER_BUDGET | 20.9 | Tereliminasi oleh batas anggaran (butuh Rp 540,000, sisa Rp 492,300). Estimasi hari tanpa stok: 20.9 hari dalam siklus 30 hari. |
| 16 | Multivitamin Sirup 100 ml | N/B | INTERMITTENT | 9.6 | 57 | 0 | Rp 0 | EXCLUDED_OVER_BUDGET | 20.4 | Tereliminasi oleh batas anggaran (butuh Rp 1,596,000, sisa Rp 492,300). Estimasi hari tanpa stok: 20.4 hari dalam siklus 30 hari. |
| - | Acarbose 100 mg Tablet | E/B | SMOOTH | 135.0 | 0 | 0 | Rp 0 | NOT_NEEDED | 0.0 | Tidak perlu order (stok layak pakai cukup 135.0 hari), tetapi 2233 unit fisik berisiko ED! |

---

## 4. Hasil Simulasi Perbandingan Adil (6 Bulan, Pagu Rp 30,000,000/Bulan)
| Strategi | Vital Stockout Days | Total Stockout Days | Expired Units | Nilai Kerugian ED | Fill Rate (%) | Porsi Anggaran Vital (%) |
| :--- | :---: | :---: | :---: | ---: | :---: | :---: |
| RSUD_Current_Formula | 58 | 191 | 0.0 | Rp 0 | 83.80% | 43.19% |
| Static_Excel_3Mo_AMC | 45 | 170 | 0.0 | Rp 0 | 87.65% | 44.84% |
| SigapStok | 26 | 112 | 0.0 | Rp 0 | 88.40% | 38.95% |
| SigapStok_Trained | 23 | 111 | 0.0 | Rp 0 | 88.91% | 39.09% |
