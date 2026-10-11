# Laporan Audit Fitur — toko-contoh (2026-10-11)

> Dihasilkan heuristik (regex), bukan analisa compiler. Semua kandidat
> PRUNE/MERGE butuh verifikasi manusia sebelum dieksekusi.

## Ringkasan

- Entry point: **6** | Fungsi terdeteksi: **20** | Terjangkau: **15** (75%)
- KEEP: **14** | MERGE: **1** grup | PRUNE: **4** kandidat | REVIEW: **0**

## Peta fitur

### `/users` — http-route (`app.js:8`)
Rantai: `listUsers` → `formatUser`, `getAllUsers`

### `/users` — http-route (`app.js:9`)
Rantai: `createUser` → `formatUser`, `saveUser`

### `(anonymous)` — cli (`cli.py:3`)
Rantai: `sync` → `fetch_items`, `save_items`

### `(anonymous)` — cli (`cli.py:9`)
Rantai: `report` → `build_report`, `fetch_items`, `summarize`

### `/products` — http-route (`routes.php:4`)
Rantai: `index` → `fetchProducts`

### `/products` — http-route (`routes.php:5`)
Rantai: `store` → `createProduct`

## Klasifikasi

### PRUNE — confidence high (prioritas hapus)

| Fungsi | Lokasi | Alasan |
|---|---|---|
| `oldReport` | `app.js:31` | tak ada pemanggil sama sekali |
| `unused_helper` | `cli.py:26` | tak ada pemanggil sama sekali |
| `legacyImport` | `routes.php:26` | tak ada pemanggil sama sekali |

### PRUNE — confidence medium (rantai kode mati)

| Fungsi | Lokasi | Alasan |
|---|---|---|
| `formatLegacyRow` | `app.js:35` | hanya dipanggil kode mati: oldReport |

### MERGE — duplikat (verifikasi manual dulu)

| Grup fungsi | Rekomendasi kanonis |
|---|---|
| formatUser (app.js:25), formatUserV2 (app.js:28) | `formatUser` (pemanggil terbanyak) |

### REVIEW — butuh keputusan manusia

_Tidak ada._

## Rekomendasi prioritas

1. **PRUNE high** — risiko terendah. Satu commit per fungsi (mudah revert).
2. **MERGE** — setelah PRUNE, saat peta sudah bersih. Baca kedua badan manual sebelum gabung.
3. **REVIEW** — putuskan satu per satu; lengkapi dengan cek runtime (log/analytics).
4. **Ulangi** fase 2–3 setelah hapus/gabung — rantai mati baru sering muncul.

## Batasan audit

- Deteksi via pola regex: routing dinamis, reflection, magic method, DI container tak terlihat.
- Pemanggilan lintas bahasa (frontend→API) dan lintas repo tak terdeteksi otomatis.
- Fungsi `export` yang tak terpanggil dianggap REVIEW, bukan PRUNE.
- Cek runtime (log 7–30 hari, analytics) belum dilakukan — lakukan sebelum eksekusi PRUNE.
