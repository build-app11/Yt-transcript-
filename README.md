# Transkrip YouTube (Streamlit)

## Menjalankan di GitHub Codespaces

1. Upload semua file ke repo GitHub (termasuk `.devcontainer` dan `.streamlit`).
2. **Code → Codespaces → Create codespace on main**.
3. Dependensi terpasang otomatis dan Streamlit langsung jalan di port 8501.
   Jika tidak terbuka sendiri, buka tab **Ports** lalu klik ikon globe di baris port 8501.

Manual:

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Jika muncul error "YouTube memblokir permintaan"

YouTube sering memblokir IP layanan cloud, termasuk Codespaces. Pakai proxy:

```bash
export PROXY_URL="http://user:password@host:port"
streamlit run app.py
```

Agar permanen, simpan `PROXY_URL` sebagai **Codespaces secret** di pengaturan GitHub, lalu rebuild codespace.
