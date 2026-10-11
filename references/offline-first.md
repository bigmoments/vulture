# offline-first.md — Audit kelengkapan fitur offline-first

> Dibaca bila aplikasi (atau sebagian fiturnya) offline-first / local-first.
> Tujuan: memastikan fitur **tetap bekerja, tidak kehilangan data, dan tetap
> tersinkron dengan cloud saat dibutuhkan** — bukan sekadar "ada kode sync".

## Rantai lengkap yang sehat

```
tulis/aksi → simpan lokal (durable) → masuk antrean outbox
    → sync saat online → konfirmasi server → bersihkan antrean
```

Rantai putus di titik mana pun = risiko kehilangan data atau data tak pernah
sampai cloud. Kasus klasik: gambar disimpan base64 secara lokal, SDK/fungsi
upload cloud terpasang, tapi **tak ada yang memicu sync** — rantai putus di
tengah, data menumpuk lokal selamanya.

## Kebutuhan yang dicek saat audit

1. **Tulis lokal dulu.** UI merefleksikan state lokal segera, tidak menunggu network.
   Aksi tidak boleh gagal total hanya karena offline.
2. **Penyimpanan durable.** Data tersimpan di media yang selamat dari tutup app:
   IndexedDB / SQLite / file lokal — bukan variabel di memori.
3. **Antrean outbox.** Mutasi saat offline dicatat sebagai antrean eksplisit
   (bukan ditimpa, bukan dibuang diam-diam).
4. **Pemicu sync jelas.** Minimal satu dari: event `online`, saat app dibuka,
   background sync / periodik. Script mendeteksi pola umum (`addEventListener('online')`,
   service worker `sync`); sisanya verifikasi manual.
5. **Retry dengan backoff.** Sync gagal → antrean dipertahankan, coba lagi dengan
   jeda membesar. Antrean TIDAK boleh dihapus sebelum server konfirmasi.
6. **Konfirmasi & cleanup.** Antrean dibersihkan hanya setelah ada konfirmasi
   dari sisi cloud — bukan setelah "request terkirim".
7. **Strategi konflik.** Bila data bisa diubah di dua tempat (lokal + cloud),
   harus ada strategi eksplisit: last-write-wins, merge manual, atau tolak
   duplikat. Minimal didokumentasikan — jangan diam.
8. **Status transparan ke user.** User bisa bedakan "tersimpan lokal, menunggu
   sync" vs "sudah di cloud". Jangan tampilkan seolah sudah aman padahal belum.

## Pola yang dicurigai (temuan audit)

| Pola | Risiko |
|---|---|
| SDK/config/fungsi upload cloud ada, tapi tak ada pemicu sync | Rantai putus — data tak pernah sampai cloud |
| Antrean dibersihkan sebelum konfirmasi server | Data hilang saat sync gagal di tengah jalan |
| Sync hanya dipicu dari satu layar tertentu | Data menumpuk bila user tak membuka layar itu |
| Semua tulis langsung ke network tanpa fallback lokal | Bukan offline-first — jangan diklaim begitu |
| Tak ada retry / backoff | Satu kegagalan network = data hangus |

## Optimasi yang sehat (YAGNI)

- **Jangan sync semuanya.** Prioritaskan antrean: data kritis (transaksi, foto user)
  dulu, yang bisa dihitung ulang belakangan.
- **Batch & kompresi.** Gabungkan beberapa item antrean per request; kompres
  payload besar (gambar) sebelum upload — hemat baterai & kuota.
- **Idempotency key.** Tiap item antrean punya ID unik; server menolak duplikat.
  Ini yang mencegah data ganda saat retry.
- **Jangan polling agresif.** Sync saat event (online/app-start), bukan tiap detik.
- **Batasi ukuran antrean lokal.** Ada batas + kebijakan saat penuh (peringatkan user,
  jangan hapus diam-diam).

## Verifikasi runtime (wajib sebelum vonis "sehat")

1. Matikan network → lakukan aksi → **tutup app** → buka lagi → data masih ada?
2. Nyalakan network → antrean terkirim? Verifikasi **di sisi cloud**, bukan cuma "request 200".
3. Matikan network **di tengah sync** → tidak ada data ganda & tidak ada yang hilang?
4. Cek log 7–30 hari: ada item antrean yang umurnya tua (tak pernah tersync)?

## Batasan

- Kelengkapan rantai butuh baca kode + uji manual; script hanya menandai kandidat
  (fungsi sync mati, entry `online` tak ada, dependency upload tak terpakai).
- Desain resolusi konflik & skema sync butuh review arsitektur, bukan grep.
- Klaim "offline-first" di marketing/docs harus dibuktikan dengan 4 uji di atas.
