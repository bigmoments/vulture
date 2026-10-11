# relations.md — FASE 2: Peta relasi

> Dari tiap entry point: fungsi apa dipanggil → data apa disentuh.
> Script `scripts/call_graph.py` membangun call graph kasar via regex
> (definisi fungsi + pemanggilan). Ini heuristik — baca batasannya.

## Cara kerja script

1. **Definisi fungsi** dideteksi per bahasa (C-like):
   - JS/TS: `function name(`, `const name = (...) =>`, `const name = async function(`
   - Python: `def name(` (termasuk method — `def method(self)`)
   - PHP: `function name(` (bukan anonymous `function (`)
   - Java/C#: `<modifier> <ReturnType> name(`
   - Go: `func name(` / `func (r Type) name(`
   - Ruby: `def name`
2. **Badan fungsi** = baris dari definisi sampai definisi berikutnya di file yang
   sama (aproksimasi; cukup untuk file terstruktur normal).
3. **Pemanggilan** = pola `nama(` di dalam badan, dikurangi keyword bahasa
   (`if`, `for`, `while`, `return`, `new`, ...).
4. Tiap node menyimpan `body_hash` (badan dinormalisasi: whitespace dibuang,
   komentar baris dibuang) untuk deteksi duplikat di fase 4.

## Jejak data (ditambahkan manual / via grep)

Call graph menjawab "siapa manggil siapa". Untuk "data apa disentuh",
lengkapi dengan grep terarah per entry point:

| Jejak | Pola grep | Arti |
|---|---|---|
| Query SQL | `SELECT\|INSERT\|UPDATE\|DELETE` (string literal) | Tabel yang dibaca/ditulis |
| ORM | `\.find\|\.create\|\.save\|\.destroy\|Model\.query\|db\.` | Model/tabel via ORM |
| HTTP keluar | `fetch(\|axios\.\|http\.get\|requests\.` | API eksternal disentuh |
| File | `readFile\|writeFile\|open(\|fopen` | File disentuh |
| Cache/queue | `redis\|cache\.\|queue\.\|dispatch(` | Infra disentuh |

Catat temuan ke peta fitur: `entry → [fungsi...] → [tabel/API/file]`.

## Batasan heuristik (tulis di laporan)

- **Dynamic dispatch** tak terlihat: `$obj->$method()`, `getattr(obj, name)()`,
  `this[methodName]()`, reflection, dependency injection container.
- **Callback/event**: fungsi yang didaftarkan sebagai callback tapi tak pernah
  "dipanggil" secara tekstual (event listener, promise chain terpisah file).
- **Magic method**: `__call`, `__get` (PHP), `__getattr__` (Python), proxy JS.
- **Lintas bahasa**: frontend JS memanggil API backend — hubungkan manual via
  pencocokan path URL (fase 1) dengan `fetch('/path')` di frontend.
- **Monorepo/paket**: pemakaian lintas paket tak terlihat — cek `package.json`
  / `composer.json` / `requirements` dependensi internal.

Aturan praktis: bila ragu apakah suatu pola terdeteksi, grep manual nama
fungsinya di seluruh repo. Satu grep 5 detik mengalahkan asumsi.
