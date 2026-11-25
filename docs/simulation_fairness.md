# Desain Simulasi Perbandingan yang Adil (*Fair Comparison Agreement*)

Dokumen ini mendefinisikan protokol keadilan (*fairness protocol*) untuk membandingkan kinerja **Rumus Eksisting RSUD**, **Spreadsheet 3-Bulan Statis**, dan **SigapStok**.

## Prinsip Keadilan (*Controlled Variables*)
Agar perbandingan objektif dan bebas bias, seluruh metode diuji pada kondisi identik berikut:
1. **Stream Permintaan Harian Identik:** Realisasi pemakaian harian selama 6 bulan (180 hari) dibangkitkan satu kali menggunakan *fixed random seed*, lalu disuplai secara identik ke semua strategi.
2. **Anggaran Bulanan Identik (`monthly_budget_cap`):** Setiap metode dibatasi oleh pagu anggaran yang sama persis di setiap siklus 30 hari (misal Rp 30.000.000 – Rp 35.000.000/bulan untuk skenario anggaran terbatas).
3. **Lead Time & Aturan Kedaluwarsa (FEFO) Identik:** Seluruh pengiriman tiba setelah *lead time* yang sama ($L = 7$ hari) dan pengeluaran harian selalu mengonsumsi batch terdekat ED (*First Expired, First Out*).
4. **Stok Awal & Histori 12 Bulan Identik:** Seluruh strategi memulai Hari-0 dengan lot stok fisik dan tanggal ED yang sama persis.

## Variabel yang Diukur (*Comparison Metrics*)
1. **Vital Drug Stockout Days:** Jumlah hari kejadian kekurangan stok pada obat kategori **Vital (`V`)** *(indikator keselamatan pasien utama)*.
2. **Total Stockout Days:** Total hari kekurangan stok seluruh SKU.
3. **Expired Units & Expired Value (IDR):** Total unit/nilai obat yang melewati tanggal ED di gudang akibat *over-ordering*.
4. **Fill Rate (%):** Rasio total unit permintaan pasien yang berhasil dilayani tepat waktu terhadap total permintaan.
5. **Vital Budget Share (%):** Persentase anggaran yang berhasil diamankan untuk obat-obatan Vital.
