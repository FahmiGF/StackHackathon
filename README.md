# SigapStok — Adaptive Pharmacy Demand Forecasting & Budget Ranking

**SigapStok** adalah prototipe sistem perencanaan kebutuhan obat dan pemeringkatan anggaran pengadaan farmasi untuk rumah sakit (studi kasus **RSUD Kilisuci, Kota Kediri**). Aplikasi ini menggantikan rumus pemesanan tunggal berbasis 1 bulan pemakaian dengan peramalan berbasis pola permintaan (*pattern-matched forecasting*), koreksi stok layak pakai berbasis tanggal kedaluwarsa (*ED-capping*), serta pemeringkatan anggaran berorientasi keselamatan pasien (**Vital-first**).

---

## Fitur Utama & Alur Kerja
1. **Unggah & Inspeksi Kolom Otomatis (`sigapstok/ingestion.py`):**
   - Mendukung file ekspor `.xlsx` dan `.csv` untuk data pemakaian/stok fisik/tanggal ED serta daftar harga/DOEN/VEN.
   - Validasi skema kolom otomatis, deteksi nilai negatif/format tanggal ED rusak, serta saran awal status **VEN** berbasis pencocokan **DOEN** untuk dikonfirmasi tim farmasi.
2. **Penyimpanan Riwayat Relasional (`sigapstok/schema.sql`, `sigapstok/db.py`):**
   - Menyimpan master obat, riwayat unggahan (`upload_batches`), deret waktu pemakaian bulanan (`monthly_usage_history`), snapshot stok layak pakai & proyeksi ED (`stock_batches_ed`), hasil peramalan (`forecast_results`), penyesuaian manual beserta alasannya, hingga hasil peringkat anggaran (`budget_ranking_results`).
3. **Klasifikasi Pola Permintaan & Inventori (`sigapstok/forecasting.py`):**
   - **ADI & CV² (Syntetos–Boylan):** Mengklasifikasikan setiap SKU ke dalam pola **Smooth**, **Erratic**, **Intermittent**, atau **Lumpy**.
   - **Metode Peramalan Adaptif:**
     - `SMOOTH` → *Simple Exponential Smoothing (SES)*
     - `ERRATIC` → *Damped Holt's Linear Trend*
     - `INTERMITTENT` / `LUMPY` → **SBA (*Syntetos–Boylan Approximation*)** + *Vital Standby Buffer* agar obat penyelamat nyawa yang jarang dipakai tidak dihitung nol setelah bulan sepi.
   - **Klasifikasi Logistik Multi-Dimensi:** Menghasilkan kelas **ABC** (nilai investasi Pareto), **XYZ** (konsistensi pemakaian), **FSN** (*Fast/Slow/Non-moving*), dan matriks **ABC–VEN**.
   - **ED-Adjusted Usable Stock:** Mengurangi stok fisik dengan porsi obat yang diprediksi akan kedaluwarsa sebelum sempat terpakai.
4. **Pemeringkatan Anggaran & Laporan Satu Halaman (`sigapstok/ranking.py`):**
   - Mengurutkan usulan pembelian berdasarkan **VEN (`V > E > N`) → Sisa Hari Stok (`days_of_supply`) → Efisiensi Matriks `ABC–VEN`**.
   - Memberi status `FULL_ORDER`, `PARTIAL_ORDER`, atau `EXCLUDED_OVER_BUDGET` lengkap dengan estimasi **`expected_days_without_stock`** untuk item yang terpotong anggaran.
5. **Simulasi Perbandingan Adil (`sigapstok/simulation.py`):**
   - Membandingkan **Rumus RSUD Saat Ini** (`1.10 × bulan lalu - stok`), **Spreadsheet 3-Bulan Statis** (`5 × AMC - usable`), dan **SigapStok** di bawah pagu anggaran, permintaan harian, *lead time*, dan aturan FEFO yang identik.

---

## Struktur Proyek
```text
StackHackathon/
├── main.py                              # CLI demo & simulasi perbandingan
├── requirements.txt                     # Dependensi Python (pandas, openpyxl)
├── sigapstok/
│   ├── schema.sql                       # Skema database relasional
│   ├── db.py                            # Layer penyimpanan SQLite & riwayat
│   ├── ingestion.py                     # Unggah file, inspeksi kolom, validasi DOEN/VEN
│   ├── forecasting.py                   # ADI/CV², SES/Holt/SBA, ABC/XYZ/FSN, ED-capping
│   ├── ranking.py                       # Logika pemeringkatan anggaran (Bagian 4.4)
│   ├── synthetic_data.py                # Generator dataset sintetis RSUD Kilisuci
│   └── simulation.py                    # Simulasi perbandingan adil multi-bulan
├── docs/
│   ├── 2.4_existing_alternatives.md     # Kajian Permenkes & perbandingan vs VEN
│   ├── 4.4_budget_ranking_logic.md      # Spesifikasi logika pemeringkatan anggaran
│   └── simulation_fairness.md           # Protokol desain simulasi yang adil
└── tests/
    └── test_sigapstok.py                # Unit & integration tests
```

---

## Instalasi & Cara Menjalankan

```bash
# 1. Instal dependensi
pip install -r requirements.txt

# 2. Jalankan demo end-to-end (buat data sintetis Excel, simpan ke DB, cetak laporan ranking)
python main.py demo --budget 35000000

# 3. Latih model (epoch training + optimasi parameter) dan evaluasi akurasi
python main.py train --epochs 160

# 4. Jalankan simulasi perbandingan adil 6 bulan
python main.py simulate --budget 30000000 --months 6

# 5. Hasilkan Laporan Lengkap (docs/LAPORAN_SIGAPSTOK.md) beserta artefak model terlatih
python main.py report --epochs 160 --months 6

# 6. Jalankan unit tests
python -m unittest discover -s tests -v
```

---

## Bagian 7 · Daftar Referensi & Resource (*References & Resources*)

1. **[1] Wawancara Tim dengan Kepala Instalasi Farmasi RSUD Kilisuci, Kota Kediri** (9–10 November 2026) — dokumentasi alur perencanaan konsumsi bulanan (cadangan 10%), mekanisme pemesanan e-Katalog per item, kendala kekosongan akibat estimasi kebutuhan & keterbatasan anggaran, serta kebijakan layanan obat JKN.
2. **[2] Kementerian Kesehatan Republik Indonesia (2016).** *Peraturan Menteri Kesehatan RI Nomor 72 Tahun 2016 tentang Standar Pelayanan Kefarmasian di Rumah Sakit.* — Landasan metode konsumsi, epidemiologi, kombinasi, serta pengendalian prioritas **ABC** dan **VEN**.
3. **[3] Studi Perencanaan Obat di Rumah Sakit Padang.** — Temuan bahwa perencanaan berbasis konsumsi semata rentan melewatkan lonjakan pasien baru dan berkorelasi dengan terjadinya obat kedaluwarsa.
4. **[4] Regulasi Jaminan Kesehatan Nasional (JKN / BPJS Kesehatan) & Formularium Nasional (FORNAS) / DOEN.** — Kebijakan bahwa obat peserta JKN disediakan dalam paket layanan rumah sakit (tidak mengganti pembelian tunai pasien di luar).
5. **[5] Lembaga Kebijakan Pengadaan Barang/Jasa Pemerintah (LKPP) — e-Katalog Obat.** — Mekanisme pengadaan elektronik pemerintah untuk fasilitas kesehatan publik.
6. **[6] Studi Peramalan Permintaan Obat Sporadis di Rumah Sakit Komunitas Thailand.** — Bukti empiris bahwa tidak ada satu metode forecasting tunggal yang optimal untuk seluruh item farmasi berpermintaan sporadis, dan obat *vital* harus selalu dipastikan ketersediaannya (*Syntetos–Boylan / Croston framework*).
7. **Referensi Metodologi Teknis:**
   - Syntetos, A. A., & Boylan, J. E. (2005). *The accuracy of intermittent demand estimates.* International Journal of Forecasting (klasifikasi **ADI/CV²** dan estimator **SBA**).
   - Kementerian Kesehatan RI — *Daftar Obat Esensial Nasional (DOEN)* sebagai acuan pencocokan zat aktif esensial/vital.
