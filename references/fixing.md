# fixing.md — FASE 6 (opsional): Perbaikan rantai yang putus

> Fase ini **HANYA** jalan bila user eksplisit meminta ("perbaiki", "fix",
> "sambungkan", "benerin"). Tanpa permintaan eksplisit, vulture berhenti di
> laporan (fase 5). Ini bukan sekadar aturan skill — eksekusi yang mengubah
> keadaan wajib konfirmasi (aturan global).

## Prinsip (perpanjangan prinsip kejujuran)

- **Usulan ≠ vonis.** Agent mengusulkan diff; manusia menyetujui **tiap diff**,
  satu per satu. Tidak ada batch approval.
- **Jangan mengarang logika bisnis.** Bila cara penyambungan ambigu (kapan
  dipanggil? argumen apa? bagaimana error handling-nya?), tulis pilihannya dan
  **tanya user** — jangan menebak.
- **Sambungan ditambahkan, perilaku tidak diubah.** Fungsi yang KEEP/hidup tidak
  boleh diubah perilakunya demi "menyambung".

## Sinyal "seharusnya berkaitan"

Fungsi A dan B dinilai seharusnya terhubung bila ada ≥2 sinyal:

- **Nama/domain sama** — `saveImageBase64` ↔ `uploadToCloudinary` (sama-sama soal gambar).
- **Aliran data cocok** — output A = input yang dibutuhkan B.
- **Menyentuh hal yang sama** — tabel/data, SDK, atau config yang sama
  (tabel `images`, `CLOUDINARY_URL`).
- **Jejak niat** — komentar/TODO ("TODO: upload when online"), docs, atau
  antrean outbox yang tak pernah dikonsumsi (produsen tanpa konsumen).
- **Struktur rantai** — laporan fase 5 menandai "rantai putus" di antara keduanya.

Satu sinyal saja = belum cukup, tulis sebagai hipotesis dan konfirmasi ke user.

## Jenis perbaikan

### A. Penyambungan rantai (wiring)

Kasus: fungsi integrasi ada tapi tak terhubung (kasus klasik: SDK terpasang,
fungsi upload ada, tapi tak pernah dipanggil).
1. Tentukan titik sambung dari sinyal di atas.
2. Tulis **diff minimal**: panggil fungsi di titik yang tepat + error handling
   + penanda status (mis. `synced: true` hanya setelah konfirmasi server).
3. Tunjukkan diff ke user + jelaskan: apa yang diubah, kenapa di titik itu,
   dan apa yang masih harus diverifikasi manusia.
4. Setelah disetujui dan diterapkan → verifikasi (di bawah).

### B. Eksekusi PRUNE / MERGE yang disetujui

Hapus/gabung sesuai laporan fase 5. Satu aksi = satu commit (mudah revert).
Jangan gabungkan banyak PRUNE dalam satu commit.

## Yang TIDAK boleh dilakukan

- Mengubah perilaku fungsi KEEP demi menyambung rantai.
- Menghapus/menggabung kode hanya berdasarkan usulan, tanpa persetujuan eksplisit.
- Mengklaim "sudah berfungsi" tanpa bukti re-audit + uji runtime.
- Memasang dependency/config/secret baru tanpa persetujuan.
- Menebak strategi resolusi konflik / logika bisnis yang ambigu.

## Verifikasi perbaikan (wajib, bukan opsional)

1. **Re-audit (fase 2–3).** Fungsi yang diperbaiki harus berpindah
   PRUNE → KEEP (terjangkau dari entry point) dan temuan "rantai putus"-nya
   hilang dari laporan. Bila masih PRUNE → sambungan salah tempat atau tak
   terdeteksi pola. Perbaiki, jangan abaikan.
2. **Uji runtime.** Buktikan **ujung rantai**: data benar-benar sampai di
   cloud/tujuan (bukan cuma "request terkirim"). Untuk offline-first, jalankan
   4 uji di `references/offline-first.md`.
3. **Test suite** (bila ada). Jalankan test terkait, pastikan hijau.

Ketiga langkah ini adalah definisi "sudah bekerja dengan baik" — bukan perasaan.

## Mode interaktif (`scripts/interactive.py`)

Alternatif eksekusi mekanis tanpa agent: wizard CLI yang menjalankan fase 1–3
otomatis lalu menuntun user per temuan. PRUNE dihapus dengan preview +
konfirmasi (backup di `vulture-removed.bak.md`); keputusan MERGE/REVIEW/dep
dicatat di `vulture-decisions.json`; rantai putus bisa dipilih "sambungkan"
→ masuk `FIX-QUEUE.md` untuk dikerjakan agent (wiring butuh penilaian kode,
tidak dikerjakan script). Setelah penghapusan, re-audit jalan otomatis.
