# Transkrip YouTube

Website kecil untuk mengambil transkrip (subtitle) video YouTube. Backend Flask + youtube-transcript-api, frontend satu file HTML.

## Menjalankan di GitHub Codespaces

1. Buat repo baru di GitHub, lalu upload semua file proyek ini (termasuk folder `.devcontainer`).
2. Klik **Code → Codespaces → Create codespace on main**.
3. Setelah container siap, dependensi terpasang otomatis dan server langsung berjalan di port 5000. Tab browser akan terbuka sendiri.
4. Jika tidak jalan otomatis, buka terminal lalu:

   ```bash
   pip install -r requirements.txt
   python app.py
   ```

   Lalu buka tab **Ports**, klik ikon globe di baris port 5000.

## Fitur

- Menerima tautan `watch`, `youtu.be`, `shorts`, `embed`, dan `live`
- Pilih bahasa transkrip yang tersedia
- Waktu per baris (klik untuk lompat ke momen itu di YouTube)
- Cari kata kunci, salin teks, unduh `.txt` dan `.srt`

## Jika muncul error "YouTube memblokir permintaan"

YouTube sering memblokir IP layanan cloud, termasuk Codespaces. Solusinya pakai proxy (residential/rotating):

```bash
export PROXY_URL="http://user:password@host:port"
python app.py
```

Untuk menyimpannya, tambahkan `PROXY_URL` sebagai **Codespaces secret** di pengaturan GitHub, lalu rebuild codespace.

## Struktur

```
app.py               # API: GET /api/transcript?url=...&lang=...
static/index.html    # Antarmuka
requirements.txt
.devcontainer/       # Konfigurasi Codespaces
```
