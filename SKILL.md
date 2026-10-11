---
name: vulture
description: >
  Mode burung bangkai: melayang di atas codebase, mencium bangkai fungsi dari
  kejauhan, menukik tepat sasaran. Audit fitur yang language-agnostic:
  inventarisasi entry point, peta relasi fungsi (entry → fungsi → data),
  deteksi dead code & fungsi duplikat, klasifikasi KEEP/MERGE/PRUNE/REVIEW,
  dan laporan prioritas. Untuk JS/TS, PHP, Python, Java, Go, Ruby, dan bahasa
  C-like lainnya. Trigger chat: "vulture", "audit fitur", "fitur apa saja",
  "dead code", "fungsi tidak terpakai", "fungsi mati", "peta fitur",
  "relasi fungsi", "feature audit", "unused functions", "codebase audit",
  "duplikat fungsi".
license: MIT
version: 1.0.0
---

# vulture

Audit fitur aplikasi: jawab tiga pertanyaan — **fungsi apa saja yang ada,
saling berhubungan bagaimana, dan mana yang benar-benar berguna.** Berhenti di
laporan + rekomendasi; eksekusi hapus/gabung selalu keputusan manusia.

## Prinsip kejujuran (baca dulu)

Script di skill ini **heuristik** (pola regex, bukan compiler). Mereka menemukan
**KANDIDAT**, bukan vonis:

- Entry point yang tak terdeteksi (routing dinamis, reflection, magic method)
  membuat fungsi hidup terlihat mati.
- Fungsi "mati" bisa jadi public API/library yang dipakai repo lain.
- Duplikat "identik" bisa jadi disengaja (mis. versi stabil vs eksperimen).

Karena itu selalu ada kategori **REVIEW** untuk yang ambigu, dan laporan tidak
pernah boleh dipakai sebagai perintah hapus otomatis. Manusia memutuskan;
skill ini menyiapkan buktinya.

## Kapan dipakai

- "Aplikasi ini fiturnya apa saja sih?" — codebase warisan tanpa dokumentasi.
- Curiga ada kode mati / fungsi tak terpakai menumpuk.
- Sebelum refactor besar: petakan dulu apa yang boleh disentuh.
- Duplikasi logika di banyak tempat, mau konsolidasi.

JANGAN dipakai untuk: audit performa (pakai app-optimizer), audit keamanan,
analisa bug spesifik.

## Workflow 5 fase

```
FASE 1  inventarisasi entry point   → scripts/entry_points.py  → entries.json
FASE 2  peta relasi                 → scripts/call_graph.py    → graph.json
FASE 3  uji kegunaan                → scripts/dead_code.py     → dead.json
FASE 4  klasifikasi KEEP/MERGE/PRUNE/REVIEW
FASE 5  laporan                     → scripts/audit_report.py  → AUDIT.md
```

**FASE 1 — Inventarisasi entry point.** Entry point = pintu masuk eksekusi:
route HTTP, halaman, aksi UI, cron/job terjadwal, CLI command, exported API.
Jalankan `scripts/entry_points.py <dir> -o entries.json`. Bila framework tak
dikenal polanya, baca `references/inventory.md` lalu daftarkan manual.

**FASE 2 — Peta relasi.** Dari tiap entry point, telusuri fungsi yang dipanggil
dan data yang disentuh (tabel DB, API eksternal, file). Jalankan
`scripts/call_graph.py <dir> -o graph.json`. Detail teknik baca
`references/relations.md`.

**FASE 3 — Uji kegunaan.** Tiap fungsi ditanya tiga hal: (1) ada yang manggil?
(2) ada yang mengakses? (3) kalau dihapus, apa yang rusak? Jalankan
`scripts/dead_code.py --graph graph.json --entries entries.json -o dead.json`.
Fungsi tak terjangkau dari entry point = kandidat PRUNE dengan confidence
level. Cara verifikasi runtime (log, analytics, grep) di
`references/usefulness.md`.

**FASE 4 — Klasifikasi.** Aturan di `references/classification-report.md`:

| Kelas | Arti | Syarat |
|---|---|---|
| KEEP | dipakai, jelas pemiliknya | terjangkau dari entry point |
| MERGE | duplikat / tumpang tindih | badan fungsi identik (dinormalisasi) |
| PRUNE | mati, aman dihapus | tak terjangkau + tak diekspor + confidence high/medium |
| REVIEW | ambigu, butuh manusia | diekspor tapi tak terpanggil, pola dinamis, confidence low |

**FASE 5 — Laporan.** `scripts/audit_report.py --entries entries.json --graph graph.json --dead dead.json -o AUDIT.md`.
Satu dokumen: ringkasan angka, peta fitur, tabel klasifikasi, rekomendasi
prioritas (PRUNE high dulu → MERGE → REVIEW).

## Output Contract

Laporan akhir (`AUDIT.md`) WAJIB memuat:

1. **Ringkasan angka** — total entry point, total fungsi, % terjangkau, kandidat per kelas.
2. **Peta fitur** — tiap entry point → fungsi yang terjangkau (rantai panggilan).
3. **Tabel klasifikasi** — tiap kandidat PRUNE/MERGE/REVIEW: nama, file:baris, alasan, confidence.
4. **Rekomendasi prioritas** — urutan eksekusi yang disarankan + apa yang perlu dikonfirmasi manusia.
5. **Batasan** — apa yang TIDAK bisa dipastikan script (pola dinamis, pemakaian lintas repo).

## Operating Rules

1. **Heuristik = kandidat.** Jangan pernah hapus kode berdasarkan laporan saja; selalu ada langkah konfirmasi manusia.
2. **Entry point dulu.** Tanpa daftar entry point yang benar, semua fase berikutnya salah arah.
3. **REVIEW bukan kegagalan.** Fungsi ambigu masuk REVIEW — itu fitur, bukan bug script.
4. **Mulai dari yang kecil.** Audit satu modul/direktori dulu sebelum seluruh repo.
5. **Catat yang tak terdeteksi.** Framework/pattern yang lolos dari script ditulis di laporan bagian Batasan — jangan diam-diam diabaikan.
6. **Script stdlib only.** `scripts/` hanya boleh memakai Python 3 standard library, executable langsung.
