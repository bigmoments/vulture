# inventory.md — FASE 1: Inventarisasi entry point

> Entry point = pintu masuk eksekusi. Tanpa daftar ini, fase 2–5 salah arah.
> Script `scripts/entry_points.py` mendeteksi pola umum; yang tak terdeteksi
> didaftarkan manual di sini formatnya.

## Kategori entry point

| Kategori | Contoh | Kenapa penting |
|---|---|---|
| HTTP route | `app.get('/users', ...)`, `Route::post(...)`, `@app.route(...)` | Pintu utama aplikasi web/API |
| Halaman/view | file di `pages/`, `views/`, route frontend | Fitur yang terlihat user |
| Aksi UI | `onClick`, event listener, form submit | Fitur interaktif |
| Cron/job | `cron.schedule(...)`, file crontab, queue worker | Fitur berjalan tanpa user |
| CLI command | `program.command(...)`, `@click.command()`, `bin` di package.json | Fitur via terminal |
| Exported API | `export function`, `module.exports`, `__all__` | Dipakai repo/paket lain |
| Event konektivitas | `addEventListener('online'/'offline')` | Fitur yang jalan saat status jaringan berubah |
| Background sync | service worker `sync` event, `sync.register('tag')` | Sync antrean offline-first |

## Pola per framework/bahasa (yang dikenali script)

**JavaScript/TypeScript** (`.js`, `.ts`, `.mjs`, `.cjs`):
- Express/Hono/Fastify/Koa: `app.get|post|put|patch|delete|all|use('/path', handler)`, `router.*(...)`
- Commander/yargs: `program.command('name')`, `yargs.command('name')`
- Cron: `cron.schedule(...)`, `node-cron`, `setInterval` (catat manual — sering false positive)
- Export: `export function name`, `export const name =`, `module.exports`
- Offline-first: `addEventListener('online'|'offline', ...)`, service worker
  `addEventListener('sync', ...)`, `sync.register('tag')` — rantai sync aplikasi
  offline-first; kelengkapan rantainya diaudit via `references/offline-first.md`

**Python** (`.py`):
- Flask: `@app.route('/path')`, `@bp.route(...)`
- FastAPI/Starlette: `@app.get|post|put|patch|delete('/path')`, `@router.*(...)`
- Django: `path('...', view)` / `re_path(...)` di `urls.py`
- Click: `@click.command()`, `@click.group()`; argparse: `add_parser('name')`, `add_argument`
- Celery/beat: `@app.task`, `@shared_task`, `beat_schedule`

**PHP** (`.php`):
- Laravel: `Route::get|post|put|patch|delete('/path', ...)`
- Symfony: `#[Route('/path')]` (attribute — deteksi sebagian, verifikasi manual)
- WordPress: `add_action(`, `add_shortcode(`, `register_rest_route(`

**Java/Kotlin** (`.java`, `.kt`):
- Spring: `@GetMapping`, `@PostMapping`, `@RequestMapping`, `@Scheduled`, `@EventListener`

**Go** (`.go`):
- `http.HandleFunc(`, `router.GET|POST(`, `mux.HandleFunc(`

**Ruby** (`.rb`):
- Rails: `get|post|put|patch|delete '...'` di `routes.rb`, `rake task`

## Bila framework tak dikenal

1. Cari file konfigurasi routing: `routes.*`, `urls.py`, `*.routes.*`, `api/`.
2. Cari string path URL: grep pola `'\/[a-z-]+'` di direktori source.
3. Cari kata kunci: `schedule`, `command`, `task`, `handler`, `controller`.
4. Daftarkan manual ke `entries.json` dengan format:

```json
{"type": "http-route", "name": "/laporan", "handler": "generateReport",
 "file": "src/laporan.js", "line": 12, "source": "manual"}
```

## Yang sering terlewat (cek manual)

- Webhook endpoint (terdaftar di dashboard provider, bukan di kode).
- Migration/seed script yang dijalankan sekali.
- Event subscriber / message consumer (RabbitMQ, Kafka, Redis pub/sub).
- Background sync yang diregistrasi via Workbox/nama tag dinamis.
- Middleware yang juga berfungsi sebagai fitur (auth, logging boleh diabaikan).
- File `index.*` / `main.*` sebagai entry implisit.
