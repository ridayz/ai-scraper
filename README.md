# AI API Scraper & Benchmark

| | |
| --- | --- |
| **Status** | `done` |
| **Created** | 2026-11-07 |

## Purpose

Auto-discover free AI APIs from the internet, benchmark them (alive + speed), and rank the smartest ones. Each entry shows: AI model name, endpoint, API key type, benchmark score, and context window.

## How to Run

```bash
# install deps
/tmp/proxy_venv/bin/pip install fastapi uvicorn httpx==0.28.1 aiosqlite python-multipart jinja2

# run server (port 9100 — no conflict)
cd projects/ai-scraper
/tmp/proxy_venv/bin/python -m uvicorn src.server:app --host 0.0.0.0 --port 9100

# dashboard: http://localhost:9100
```

## Features

- **Auto-discover**: Fetches 460+ models live dari OpenRouter API setiap 5 menit
- **Smart scoring**: Setiap model dapat skor kecerdasan dari benchmark publik (MMLU, HumanEval, dll) + context window + modality
- **Filter 🧠 Smart Free**: Klik tab ini untuk lihat hanya model gratis + pintar
- **Continuous scan**: Cek alive tiap 60 detik, mati langsung di-delist & cari pengganti
- **Benchmark speed**: Ukur response time real setiap endpoint
- **SQLite storage**: Data persisten, tidak hilang saat restart
- **Auto-refresh UI**: Dashboard otomatis update tiap 10 detik

## Integrasi OpenCode (free + smart)

`localhost:9100` hanya katalog (`GET /api/smart-free`), bukan endpoint
inference — tidak ada `POST /v1/chat/completions`, jadi tidak bisa jadi
`baseURL` OpenCode. Inference tetap ke upstream (OpenRouter).

Config proyek ada di `.opencode/opencode.jsonc` (provider `openrouter` bawaan,
alias 15 model `isSmart=1` + `alive=1` dari `ai_apis.db` dengan `modelID` upstream,
urut tercepat). Default: `openrouter/nemotron-3-5-lightning-free`
→ `nvidia/nemotron-3.5-lightning:free`.

Kredensial disimpan via integrasi OpenCode (bukan plaintext di repo):
key OpenRouter terdaftar sebagai `OpenRouter` (stored). `/models` untuk pilih.
Detail seed: `src/data.py`, scoring: `src/database.py#insert_new`,
import: `src/scanner.py#fetch_openrouter_models`.
