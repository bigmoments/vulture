# classification-report.md — FASE 4 & 5: Klasifikasi dan laporan

## Kriteria klasifikasi

### KEEP — dipakai, jelas
- Terjangkau dari ≥1 entry point, atau
- Ada bukti akses runtime (log/analytics hit), atau
- Diekspor sebagai public API dengan konsumen diketahui.
- Aksi: tidak diapa-apakan. Dokumentasikan pemilik/tujuannya bila belum ada.

### MERGE — duplikat / tumpang tindih
- Badan fungsi identik setelah normalisasi (whitespace + komentar dibuang),
  atau
- Nama mirip + logika sama (mis. `formatUser` vs `formatUserV2`) — diverifikasi
  baca manual, bukan cuma hash.
- Aksi: pilih satu sebagai kanonis, alihkan pemanggil, hapus sisanya.
  Prioritaskan yang: (a) dipakai di lebih banyak tempat menang, (b) namanya
  lebih jelas, (c) test-nya lebih lengkap.
- Hati-hati: duplikat yang disengaja (versi stabil vs eksperimen, fallback)
  dipindah ke REVIEW dengan catatan alasannya.

### PRUNE — mati, aman dihapus
- Syarat kumulatif: tak terjangkau dari entry point **DAN** tak diekspor
  **DAN** tak ada bukti akses runtime **DAN** confidence high/medium.
- Aksi: hapus + hapus test yang hanya menguji fungsi itu. Satu commit per fungsi
  (mudah revert).
- Jangan hapus dalam batch besar sekaligus — maksimal beberapa fungsi per
  commit agar rollback surgical.

### REVIEW — ambigu, butuh manusia
- Diekspor tapi tak terpanggil di repo ini (mungkin dipakai repo lain).
- Confidence low dari script.
- Pola dinamis: magic method, reflection, registrasi via config/loop.
- Handler entry point yang definisinya tak ketemu di codebase.
- Kode musiman (dipakai berkala, bukan harian).
- Aksi: manusia memutuskan KEEP/PRUNE dalam N hari, atau tulis alasan KEEP.

## Format laporan (dihasilkan scripts/audit_report.py)

```markdown
# Laporan Audit Fitur — <nama proyek> (<tanggal>)

## Ringkasan
- Entry point: N | Fungsi terdeteksi: M | Terjangkau: X (Y%)
- KEEP: ... | MERGE: ... grup | PRUNE: ... kandidat | REVIEW: ...

## Peta fitur
### <entry point> — <tipe>
Rantai: handler → fungsi… → data (tabel/API)
...

## Klasifikasi
### PRUNE (confidence high)
| Fungsi | Lokasi | Alasan |
...
### PRUNE (confidence medium)
...
### MERGE (duplikat)
| Grup | Fungsi-fungsi | Rekomendasi kanonis |
...
### REVIEW
| Fungsi | Lokasi | Kenapa ambigu | Butuh apa |
...

## Rekomendasi prioritas
1. PRUNE high — risiko terendah, dampak kebersihan tertinggi.
2. MERGE — setelah PRUNE (peta lebih sederhana).
3. REVIEW — putuskan satu per satu bersama pemilik kode.
4. Jangan kerjakan PRUNE medium sebelum high selesai diverifikasi.

## Batasan audit
- Pola yang tak terdeteksi script: ...
- Area yang belum dicek runtime: ...
```

## Prioritas eksekusi — aturan umum

1. **PRUNE high dulu**: hapus yang pasti mati. Menang cepat, risiko minimal.
2. **MERGE**: gabungkan duplikat saat peta sudah bersih dari kode mati.
3. **REVIEW**: butuh manusia + mungkin data runtime tambahan. Jangan dipaksa.
4. **Ulangi**: setelah hapus/gabung, jalankan ulang fase 2–3 — rantai mati baru
   sering muncul (fungsi yang tadinya "hidup" karena dipanggil kode mati).
5. **Berhenti saat cukup**: target bukan 0 kandidat, tapi "setiap fungsi yang
   tersisa jelas pemilik dan gunanya".
