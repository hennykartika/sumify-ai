# Sumify AI: Meeting Summarizer

<p align="center">
  <img src="docs\logo\sumifyai_logo_horizontal.png" alt="Sumify AI" width="420" />
</p>

Aplikasi untuk meringkas hasil rapat dari file audio menggunakan AI. Aplikasi ini mengubah audio menjadi teks (transkripsi), lalu menghasilkan ringkasan dan dokumen PDF.

## Repository Terkait
Project ini merupakan repository untuk aplikasi Android atau tampilan user Sumify AI.

[![Mobile App Repository](https://img.shields.io/badge/Mobile%20App%20Repository-sumify--ai-181717?style=for-the-badge&logo=github)](https://github.com/mkaspulanwar/sumify-ai-fe)

## Tim
| Nama | GitHub |
| --- | --- |
| M. Kaspul Anwar | [![GitHub](https://img.shields.io/badge/mkaspulanwar-181717?style=for-the-badge&logo=github&logoColor=white)](https://github.com/mkaspulanwar) |
| Andri Rahmadani | [![GitHub](https://img.shields.io/badge/AndriRahmadani12-181717?style=for-the-badge&logo=github&logoColor=white)](https://github.com/AndriRahmadani12) |
| Henny Kartika | [![GitHub](https://img.shields.io/badge/hennykartika-181717?style=for-the-badge&logo=github&logoColor=white)](https://github.com/hennykartika) |

## Status Pengembangan

| Bagian | Status |
| --- | --- |
| Upload audio ke storage + catat ke database | Selesai, teruji |
| Ringkasan otomatis dengan LLM | Selesai, teruji |
| Cetak PDF dari ringkasan | Selesai, teruji |
| Presigned URL untuk unduh PDF | Selesai, teruji |
| Transkripsi otomatis (Whisper) | Selesai, teruji |
| Background worker (Celery) | Konfigurasi siap, isi task masih kosong |

Alur lengkap sudah berjalan dari berkas audio sampai PDF tanpa langkah manual. Endpoint `POST /meetings/{id}/transcript` tetap tersedia untuk mengisi transkrip secara manual bila diperlukan, misalnya saat menguji tanpa audio.

Seluruh proses saat ini berjalan sinkron di dalam request. Satu permintaan ringkasan memakan waktu sekitar 30 detik.

## Teknologi Utama

| Package | Fungsi |
| --- | --- |
| `fastapi` | Framework API |
| `uvicorn` | ASGI server |
| `pydantic` / `pydantic-settings` | Validasi schema & config `.env` |
| `sqlalchemy[asyncio]` | ORM database (async) |
| `alembic` | Migrasi database |
| `asyncpg` | Driver PostgreSQL async |
| `miniopy-async` | Klien MinIO / S3 |
| `httpx` | HTTP client async ke penyedia LLM |
| `playwright` | Render HTML menjadi PDF |
| `faster-whisper` | Speech-to-text lokal |
| `celery` + `redis` | Background worker (belum aktif) |
| `structlog` | Logging terstruktur |
| `python-multipart` | Upload file audio |

## Penyedia LLM

Aplikasi memakai endpoint bergaya OpenAI, jadi penyedia bisa ditukar tanpa mengubah kode. Cukup ubah tiga baris di `.env`.

Google Gemini (free tier, tidak butuh kartu kredit):

```
LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
LLM_API_KEY=AIza...
LLM_MODEL=gemini-3-flash-preview
```

DeepSeek:

```
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_API_KEY=sk-...
LLM_MODEL=deepseek-chat
```

Rencana awal memakai Apilogy (`src/core/llm/apilogy.py`), tetapi kredensialnya belum tersedia. Klien yang dipakai sekarang ada di `src/utils/llm.py`.

## Endpoint

| Method | Path | Keterangan |
| --- | --- | --- |
| `POST` | `/api/v1/upload-audio` | Unggah audio, simpan ke storage, buat Meeting |
| `GET` | `/api/v1/templates` | Jenis ringkasan yang tersedia |
| `POST` | `/api/v1/meetings/{id}/transcribe` | Transkripsi otomatis dengan Whisper |
| `POST` | `/api/v1/meetings/{id}/transcript` | Isi transkrip manual |
| `POST` | `/api/v1/meetings/{id}/summarize` | Ringkas transkrip lalu cetak PDF |
| `GET` | `/api/v1/meetings/{id}/pdf` | Unduh PDF hasil ringkasan |
| `GET` | `/api/v1/pdf-templates` | Daftar template PDF |
| `POST` | `/api/v1/meetings/{id}/regenerate-pdf` | Cetak ulang PDF tanpa memanggil LLM |

Dokumentasi interaktif tersedia di `http://localhost:8000/docs`.

## Model Whisper

Ukuran model diatur lewat `.env`. Bawaannya `base` (unduhan ~150 MB, cukup akurat untuk notulen). Untuk laptop yang lebih lemah, ganti ke `tiny`.

```
WHISPER_MODEL=base
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8
```

Unduhan model terjadi sekali saat transkripsi pertama, lalu tersimpan di cache.

## Jenis Ringkasan

| Tipe | Template PDF | Isi |
| --- | --- | --- |
| `simple` | Simple Summary | Ringkasan naratif, poin penting, kata kunci, action items |
| `business` | Business Summary | Ringkasan eksekutif, pokok bahasan, keputusan, langkah lanjutan, tabel PIC |
| `study` | Simple Summary | Rangkuman materi belajar |

## Cara Menjalankan

### Dengan Docker

```bash
docker build -t sumify-ai .
docker run -p 8000:8000 --env-file .env sumify-ai
```

Membutuhkan PostgreSQL, MinIO, dan Redis yang berjalan terpisah.

### Tanpa Docker (untuk laptop dengan sumber daya terbatas)

```bash
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS / Linux

pip install -r requirements.txt
python -m playwright install chromium

cp .env.example .env
```

**Database.** Untuk pengembangan lokal, SQLite sudah cukup:

```bash
pip install aiosqlite
```

lalu di `.env`:

```
DATABASE_URL=sqlite+aiosqlite:///./test.db
```

Untuk PostgreSQL, gunakan `DATABASE_URL` bawaan lalu jalankan `alembic upgrade head`.

**Storage.** Unduh `minio.exe` dari situs MinIO, lalu jalankan di jendela terminal terpisah:

```bash
minio.exe server D:\minio-data --console-address ":9001"
```

Kredensial bawaan `minioadmin` / `minioadmin` sudah cocok dengan `.env.example`. Konsol web ada di `http://localhost:9001`.

**Jalankan server:**

```bash
python main.py
```

Buka `http://localhost:8000/docs`.

## Struktur Folder

```
sumify-ai/
├── main.py                          # Entry point FastAPI
├── requirements.txt
├── Dockerfile
├── .env.example
├── migration/                       # Migrasi Alembic
├── scripts/
│   ├── smoke_test_crud.py           # Uji lapisan CRUD ke database
│   └── test_pdf_dummy.py            # Uji PDF generator dengan data contoh
└── src/
    ├── core/
    │   ├── config/setting.py        # Semua konfigurasi dari .env
    │   ├── database/postgree.py     # Engine & session async
    │   ├── llm/apilogy.py           # Klien Apilogy (tidak dipakai saat ini)
    │   ├── logging/logger.py
    │   └── storage/minio.py         # Klien MinIO tingkat rendah
    ├── models/                      # SQLAlchemy ORM
    ├── prompts/                     # Prompt per jenis ringkasan
    │   ├── prompt_handler.py        # Pemilih prompt
    │   ├── summary_template_a.py    # simple
    │   ├── summary_template_b.py    # business
    │   └── summary_template_c.py    # study
    ├── repositories/                # CRUD per entitas
    ├── router/                      # Endpoint API
    ├── schemas/common.py            # Enum & schema bersama
    ├── services/
    │   ├── pdf_generator/           # HTML -> PDF via Playwright
    │   ├── pdf_templates/           # simple_summary/ & business_summary/
    │   ├── pipeline/main_pipeline.py# Rangkaian ringkasan -> PDF
    │   ├── storage/                 # Abstraksi storage
    │   ├── summary_generator/       # Transkrip -> JSON terstruktur
    │   └── transcriber/             # Whisper (faster-whisper)
    ├── utils/llm.py                 # Klien LLM yang dipakai sekarang
    └── worker/                      # Celery (belum aktif)
```

## Alur Kerja

1. **Upload** — audio masuk ke MinIO, baris `Meeting` dibuat dengan status `uploaded`
2. **Transkripsi** — audio diunduh dari MinIO, diproses Whisper, tersimpan sebagai `Transcription`, status `transcribing`
3. **Ringkasan** — transkrip dikirim ke LLM, hasilnya JSON terstruktur, status `summarizing`
4. **PDF** — konteks dirender ke template HTML lalu dicetak Playwright, status `generating_pdf`
5. **Simpan** — PDF diunggah ke MinIO, `pdf_url` disimpan, status `completed`

Bila salah satu tahap gagal, status meeting menjadi `failed`.

## Pengujian

```bash
python scripts/smoke_test_crud.py    # Lapisan database
python scripts/test_pdf_dummy.py     # PDF generator dengan data contoh
```
