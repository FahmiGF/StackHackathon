# LAPORAN TEKNIS SIGAPSTOK (BAHASA INDONESIA)
## Sistem Peramalan Kebutuhan Obat Adaptif, Klasifikasi VEN/ABC/XYZ, dan Pemeringkatan Anggaran Farmasi RSUD Kilisuci

---

## 1. Ringkasan Eksekutif & Permasalahan
Di **RSUD Kilisuci, Kota Kediri**, perencanaan pengadaan obat bulanan selama ini bergantung pada satu rumus konsumsi tunggal (`Pemakaian 1 bulan + cadangan 10% - sisa stok`) [1]. Pendekatan ini memicu kekosongan pada obat *life-saving* yang jarang dipakai serta kelebihan pesanan/kedaluwarsa pada obat rutin, tanpa peringkat prioritas ketika anggaran menipis.

---

## 2. Pelatihan Model (*Epoch Training*) & Evaluasi Akurasi
Model **SigapStok Trained Hybrid** dilatih selama **250 epoch** (best checkpoint: **Epoch 10**, `best_val_loss = 0.08222`):

| Epoch | Train Loss | Validation Loss |
| :---: | :---: | :---: |
| 1 | 0.27638 | 0.21060 |
| 50 | 0.11575 | 0.08579 |
| 100 | 0.10182 | 0.09159 |
| 150 | 0.08750 | 0.09360 |
| 200 | 0.09379 | 0.09376 |
| 250 | 0.08858 | 0.09415 |

| Model / Metode | MAE | RMSE | sMAPE (%) | WAPE (%) | Akurasi (100 - WAPE) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| RSUD_1Mo_Plus_10Pct | 73.31 | 151.14 | 55.31% | 25.91% | **74.09%** |
| Excel_3Mo_AMC | 58.49 | 119.06 | 57.32% | 20.67% | **79.33%** |
| SigapStok_Untrained_Stat | 53.12 | 110.15 | 68.89% | 18.77% | **81.23%** |
| SigapStok_MLP_Only | 68.20 | 128.77 | 67.44% | 24.10% | **75.90%** |
| SigapStok_Trained_Hybrid | 51.26 | 100.13 | 69.98% | 18.11% | **81.89%** |

> Penurunan **MAE** sebesar **30.1%** dibanding rumus eksisting RSUD (`73.31` → `51.26`).

---

## 3. Hasil Pemeringkatan Anggaran (Pagu Rp 35,000,000)
- **Total Kebutuhan Ideal:** Rp 37,766,050
- **Total Dialokasikan:** Rp 34,910,650 (Sisa: Rp 89,350)

| Rank | Nama Obat | VEN/ABC | Pola | Sisa Stok (Hari) | Usulan | Alokasi | Biaya | Status | Hari Kosong | Catatan |
| :---: | :--- | :---: | :--- | :---: | :---: | :---: | ---: | :--- | :---: | :--- |
| 1 | Norepinefrin Injeksi 4 mg/4 ml | V/A | SMOOTH | 6.3 | 32 | 32 | Rp 2,080,000 | FULL_ORDER | 0.0 | Didanai penuh (Tier V/A, pola SMOOTH, sisa stok 6.3 hari). |
| 2 | Ringer Laktat 500 ml Infus | V/A | SMOOTH | 7.4 | 325 | 325 | Rp 3,737,500 | FULL_ORDER | 0.0 | Didanai penuh (Tier V/A, pola SMOOTH, sisa stok 7.4 hari). |
| 3 | Insulin Glargine 100 IU/ml Pen | V/A | SMOOTH | 8.3 | 35 | 35 | Rp 3,430,000 | FULL_ORDER | 0.0 | Didanai penuh (Tier V/A, pola SMOOTH, sisa stok 8.3 hari). |
| 4 | Epinefrin Injeksi 0.1% 1 ml | V/C | INTERMITTENT | 18.8 | 9 | 9 | Rp 112,500 | FULL_ORDER | 0.0 | Didanai penuh (Tier V/C, pola INTERMITTENT, sisa stok 18.8 hari). |
| 5 | Atropin Sulfat Injeksi 0.25 mg/ml | V/C | INTERMITTENT | 25.3 | 9 | 9 | Rp 88,200 | FULL_ORDER | 0.0 | Didanai penuh (Tier V/C, pola INTERMITTENT, sisa stok 25.3 hari). |
| 6 | Diazepam Injeksi 5 mg/ml | V/C | INTERMITTENT | 29.9 | 6 | 6 | Rp 84,000 | FULL_ORDER | 0.0 | Didanai penuh (Tier V/C, pola INTERMITTENT, sisa stok 29.9 hari). |
| 7 | SABU (Serum Anti Bisa Ular) Polivalen | V/C | INTERMITTENT | 65.2 | 3 | 3 | Rp 2,340,000 | FULL_ORDER | 0.0 | Didanai penuh (Tier V/C, pola INTERMITTENT, sisa stok 65.2 hari). |
| 8 | Ceftriaxone 1 g Serbuk Injeksi | E/A | SMOOTH | 5.2 | 283 | 283 | Rp 5,235,500 | FULL_ORDER | 0.0 | Didanai penuh (Tier E/A, pola SMOOTH, sisa stok 5.2 hari). |
| 9 | Omeprazole 40 mg Injeksi | E/A | SMOOTH | 6.4 | 124 | 124 | Rp 2,976,000 | FULL_ORDER | 0.0 | Didanai penuh (Tier E/A, pola SMOOTH, sisa stok 6.4 hari). |
| 10 | Metformin 500 mg Tablet | E/B | SMOOTH | 6.4 | 1433 | 1433 | Rp 501,550 | FULL_ORDER | 0.0 | Didanai penuh (Tier E/B, pola SMOOTH, sisa stok 6.4 hari). |
| 11 | Aciclovir 200 mg Tablet | E/C | SMOOTH | 8.4 | 231 | 231 | Rp 150,150 | FULL_ORDER | 0.0 | Didanai penuh (Tier E/C, pola SMOOTH, sisa stok 8.4 hari). |
| 12 | Amlodipine 10 mg Tablet | E/B | SMOOTH | 9.7 | 945 | 945 | Rp 425,250 | FULL_ORDER | 0.0 | Didanai penuh (Tier E/B, pola SMOOTH, sisa stok 9.7 hari). |
| 13 | Albumin Human 20% 100 ml | N/A | INTERMITTENT | 3.9 | 11 | 11 | Rp 13,750,000 | FULL_ORDER | 0.0 | Didanai penuh (Tier N/A, pola INTERMITTENT, sisa stok 3.9 hari). |
| 14 | Neurotropik B1-B6-B12 Tablet | N/B | SMOOTH | 6.3 | 327 | 0 | Rp 0 | EXCLUDED_OVER_BUDGET | 23.7 | Tereliminasi oleh batas anggaran (butuh Rp 719,400, sisa Rp 89,350). Estimasi hari tanpa stok: 23.7 hari dalam siklus 30 hari. |
| 15 | Salep Kulit Pelembab Khusus | N/C | INTERMITTENT | 9.1 | 12 | 0 | Rp 0 | EXCLUDED_OVER_BUDGET | 20.9 | Tereliminasi oleh batas anggaran (butuh Rp 540,000, sisa Rp 89,350). Estimasi hari tanpa stok: 20.9 hari dalam siklus 30 hari. |
| 16 | Multivitamin Sirup 100 ml | N/B | INTERMITTENT | 9.6 | 57 | 0 | Rp 0 | EXCLUDED_OVER_BUDGET | 20.4 | Tereliminasi oleh batas anggaran (butuh Rp 1,596,000, sisa Rp 89,350). Estimasi hari tanpa stok: 20.4 hari dalam siklus 30 hari. |
| - | Acarbose 100 mg Tablet | E/B | SMOOTH | 135.0 | 0 | 0 | Rp 0 | NOT_NEEDED | 0.0 | Tidak perlu order (stok layak pakai cukup 135.0 hari), tetapi 2171 unit fisik berisiko ED! |

---

## 4. Hasil Simulasi Perbandingan Adil (6 Bulan, Pagu Rp 30,000,000/Bulan)
| Strategi | Vital Stockout Days | Total Stockout Days | Expired Units | Nilai Kerugian ED | Fill Rate (%) | Porsi Anggaran Vital (%) |
| :--- | :---: | :---: | :---: | ---: | :---: | :---: |
| RSUD_Current_Formula | 58 | 191 | 0.0 | Rp 0 | 83.80% | 43.19% |
| Static_Excel_3Mo_AMC | 45 | 170 | 0.0 | Rp 0 | 87.65% | 44.84% |
| SigapStok | 26 | 112 | 0.0 | Rp 0 | 88.40% | 38.95% |
| SigapStok_Trained | 24 | 110 | 0.0 | Rp 0 | 88.94% | 38.87% |
