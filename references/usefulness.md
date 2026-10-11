# usefulness.md — FASE 3: Uji kegunaan

> Tiap fungsi ditanya tiga hal:
> 1. **Ada yang manggil?** — terlihat di call graph (fase 2).
> 2. **Ada yang mengakses?** — bukti runtime: log, analytics, traffic.
> 3. **Kalau dihapus, apa yang rusak?** — gabungan 1 + 2 + akal sehat.

## Yang bisa dijawab script

`scripts/dead_code.py` menjawab pertanyaan #1 secara mekanis: fungsi yang tak
terjangkau dari entry point mana pun = kandidat PRUNE, dengan confidence:

| Confidence | Arti | Contoh |
|---|---|---|
| `high` | Tak ada pemanggil sama sekali, tak diekspor | `function oldReport()` yatim |
| `medium` | Pemanggilnya ada tapi semuanya juga mati | rantai kode mati |
| `low` → REVIEW | Diekspor / namanya konvensi khusus | public API, `main`, `handler` |

Pertanyaan #2 dan #3 **tidak bisa** dijawab script — butuh bukti runtime.

## Cara cek runtime (pilih yang tersedia)

**Log aplikasi.** Cari nama fungsi/handler/route di log 7–30 hari terakhir.
Tidak muncul sekali pun = sinyal kuat tak dipakai. Perintah pola:

```bash
grep -r "oldReport\|/laporan-lama" /var/log/app/ --include="*.log" | wc -l
```

**Access log / analytics.** Untuk HTTP route: hitung hit per path. Route dengan
0 hit dalam 30 hari = kandidat PRUNE (konfirmasi dulu bukan webhook musiman).

```bash
awk '{print $7}' /var/log/nginx/access.log | sort | uniq -c | sort -rn | head -30
```

**Frontend → backend.** Untuk API: grep path di codebase frontend. Tak ada
`fetch('/path')` / pemakaian di manapun = tak ada konsumen yang diketahui.

```bash
grep -rn "fetch('/api/laporan-lama'\|\"/api/laporan-lama\"" frontend/src/
```

**DB query log.** Fungsi yang diklaim "tak dipakai" tapi tabelnya masih
ditulis = ada penulis lain (job, trigger, aplikasi lain). Cek sebelum hapus.

**Fitur flag / config.** Fungsi di balik flag yang mati (`if (false)`,
`FEATURE_X=false`) = mati secara efektif walau terpanggil.

## Menjawab "kalau dihapus, apa yang rusak?"

1. Kumpulkan daftar pemanggil (dari graph) + bukti akses (dari runtime).
2. Keduanya kosong → kemungkinan besar aman, tapi tetap REVIEW bila diekspor.
3. Ada salah satu → KEEP, atau cari tahu dulu siapa pemakainya.
4. Tulis jawabannya di laporan per kandidat — "tidak ada pemanggil, 0 hit
   30 hari" jauh lebih meyakinkan daripada "kayaknya nggak dipakai".

## Jebakan umum

- **Kode musiman**: laporan tahunan, webhook langka — 0 hit 30 hari belum tentu mati.
- **Dipakai repo lain**: util yang diimpor proyek lain (cek package registry / grep monorepo).
- **Test memanggilnya**: fungsi yang hanya dipakai test = kandidat PRUNE juga (bersama test-nya).
- **Dinamis**: route/handler yang diregistrasi via loop config — script tak melihatnya, grep manual polanya.
