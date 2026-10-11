#!/usr/bin/env python3
"""audit_report.py — gabungkan temuan jadi laporan Markdown.

Usage:
    audit_report.py --entries entries.json --graph graph.json --dead dead.json
                    [--deps deps.json] [--project NAME] -o AUDIT.md

Klasifikasi:
  KEEP   — terjangkau dari entry point.
  MERGE  — badan fungsi identik (body_hash sama), diverifikasi manual.
  PRUNE  — kandidat dead_code confidence high/medium.
  REVIEW — confidence low + missing handlers + pola ambigu.

Duplikat "identik" bisa disengaja — laporan menandainya untuk verifikasi
manusia, bukan perintah hapus. (Prinsip kejujuran: SKILL.md)
"""
import argparse
import datetime
import json
import os
import re
from collections import defaultdict

# Heuristik nama fungsi yang biasanya ujung integrasi (pola, bukan vonis).
# Selalu dilaporkan sebagai kandidat + sinyal pendukung, bukan fakta mati.
INTEGRATION_HINTS = ("upload", "sync", "push", "pull", "send", "notify",
                     "webhook", "publish", "subscribe", "payment", "charge",
                     "export", "backup", "migrate", "queue", "enqueue",
                     "dispatch", "deliver", "transmit", "replicate",
                     "download", "share", "invite", "sms", "email", "mail",
                     "invoice", "billing", "oauth", "sso")

ENV_RX = re.compile(
    r"process\.env\.([A-Z][A-Z0-9_]*)"
    r"|os\.environ(?:\.get)?\(\s*['\"`]([^'\"`]+)['\"`]"
    r"|getenv\(\s*['\"`]([^'\"`]+)['\"`]"
    r"|\benv\(\s*['\"`]([^'\"`]+)['\"`]"
)


def load(p):
    with open(p) as f:
        return json.load(f)


def reachable_map(graph, roots):
    calls = defaultdict(set)
    for e in graph["edges"]:
        calls[e["from"]].add(e["to"])
    seen, stack = set(), list(roots)
    while stack:
        cur = stack.pop()
        if cur in seen:
            continue
        seen.add(cur)
        stack.extend(calls.get(cur, ()))
    return seen


def main():
    ap = argparse.ArgumentParser(description="Susun laporan audit Markdown")
    ap.add_argument("--entries", required=True)
    ap.add_argument("--graph", required=True)
    ap.add_argument("--dead", required=True)
    ap.add_argument("--deps", default=None,
                    help="deps.json dari unused_deps.py (opsional)")
    ap.add_argument("--project", default="proyek")
    ap.add_argument("-o", "--output", required=True)
    args = ap.parse_args()

    entries = load(args.entries)
    graph = load(args.graph)
    dead = load(args.dead)
    deps_data = load(args.deps) if args.deps else {"deps": []}
    today = datetime.date.today().isoformat()

    nodes = graph["nodes"]
    by_name = defaultdict(list)
    for n in nodes:
        by_name[n["name"]].append(n)
    callers_of = defaultdict(set)
    for e in graph["edges"]:
        callers_of[e["to"]].add(e["from"])

    roots = set(dead["stats"]["roots"])
    reach = reachable_map(graph, roots)

    # --- duplikat: body_hash sama, >1 fungsi ---
    dup_groups = defaultdict(list)
    for n in nodes:
        if n.get("body_hash"):
            dup_groups[n["body_hash"]].append(n)
    dup_groups = {h: g for h, g in dup_groups.items() if len(g) > 1}
    dup_names = {n["name"] for g in dup_groups.values() for n in g}

    # --- klasifikasi ---
    keep, prune_h, prune_m, review = [], [], [], []
    dead_by_name = {c["name"]: c for c in dead["candidates"]}
    for n in nodes:
        name = n["name"]
        if name in dup_names:
            continue  # dibahas di MERGE
        c = dead_by_name.get(name)
        if c is None:
            keep.append(n)
        elif c["confidence"] == "high":
            prune_h.append(c)
        elif c["confidence"] == "medium":
            prune_m.append(c)
        else:
            review.append(c)

    # rekomendasi kanonis per grup duplikat: pemanggil terbanyak menang
    merge_rows = []
    for h, g in sorted(dup_groups.items(),
                       key=lambda kv: kv[1][0]["file"]):
        ranked = sorted(g, key=lambda n: (-len(callers_of[n["name"]]), n["name"]))
        canon = ranked[0]["name"]
        members = ", ".join(f"{n['name']} ({n['file']}:{n['line']})" for n in g)
        merge_rows.append((members, canon))

    # --- temuan integrasi: dependency & rantai putus ---
    # Catatan: sinyal config/env dibaca dari file source, jadi paling akurat
    # bila script dijalankan dari root proyek yang diaudit.
    file_cache = {}

    def file_text(rel):
        if rel not in file_cache:
            try:
                with open(rel, encoding="utf-8", errors="replace") as f:
                    file_cache[rel] = f.read()
            except OSError:
                file_cache[rel] = ""
        return file_cache[rel]

    def env_keys_in(text):
        keys = set()
        for m in ENV_RX.finditer(text):
            for grp in m.groups():
                if grp:
                    keys.add(grp)
        return sorted(keys)

    keep_names = {n["name"] for n in keep}
    file_status = {}  # rel -> live | dead | unknown
    for n in nodes:
        if n["name"] in keep_names:
            file_status[n["file"]] = "live"
        elif file_status.get(n["file"]) is None:
            file_status[n["file"]] = "dead"

    dep_importers = {d["name"]: d.get("imported_in", [])
                     for d in deps_data["deps"]}
    unused_deps = [d for d in deps_data["deps"] if not d["imported"]]
    dead_only_deps = []
    for d in deps_data["deps"]:
        if not d["imported"]:
            continue
        files = d.get("imported_in", [])
        # hanya flag bila SEMUA file pengimpor jelas mati;
        # file tanpa fungsi terdeteksi (config) = unknown -> jangan flag
        if files and all(file_status.get(f) == "dead" for f in files):
            dead_only_deps.append(d)

    broken = []  # (candidate, sinyal)
    for c in prune_h + prune_m:
        lname = c["name"].lower()
        hint = next((h for h in INTEGRATION_HINTS if h in lname), None)
        text = file_text(c["file"])
        sdks = [dn for dn, fs in dep_importers.items() if c["file"] in fs]
        keys = env_keys_in(text)
        if hint or sdks:
            signals = []
            if hint:
                signals.append(f"nama fungsi mengandung '{hint}'")
            if sdks:
                signals.append("memakai SDK: " + ", ".join(f"`{s}`" for s in sdks))
            if keys:
                shown = ", ".join(f"`{k}`" for k in keys[:8])
                more = f" (+{len(keys)-8})" if len(keys) > 8 else ""
                signals.append(f"config terkait: {shown}{more}")
            broken.append((c, "; ".join(signals)))

    L = []
    A = L.append
    A(f"# Laporan Audit Fitur — {args.project} ({today})")
    A("")
    A("> Dihasilkan heuristik (regex), bukan analisa compiler. Semua kandidat")
    A("> PRUNE/MERGE butuh verifikasi manusia sebelum dieksekusi.")
    A("")
    A("## Ringkasan")
    A("")
    A(f"- Entry point: **{len(entries)}** | Fungsi terdeteksi: **{len(nodes)}** | "
      f"Terjangkau: **{len(reach)}** ({len(reach)*100//max(len(nodes),1)}%)")
    A(f"- KEEP: **{len(keep)}** | MERGE: **{len(dup_groups)}** grup | "
      f"PRUNE: **{len(prune_h)+len(prune_m)}** kandidat | "
      f"REVIEW: **{len(review)+len(dead['missing_handlers'])}**")
    A("")
    A("## Peta fitur")
    A("")
    for e in entries:
        h = e.get("handler")
        target = h or e["name"]
        A(f"### `{e['name']}` — {e['type']} (`{e['file']}:{e['line']}`)")
        if h and h in by_name:
            rchain = sorted(reachable_map(graph, {h}) - {h})
            shown = ", ".join(f"`{r}`" for r in rchain[:15])
            more = f" (+{len(rchain)-15})" if len(rchain) > 15 else ""
            A(f"Rantai: `{h}` → {shown}{more}" if rchain else f"Rantai: `{h}` (tanpa panggilan)")
        elif h:
            A(f"Rantai: handler `{h}` tak ditemukan di codebase → REVIEW")
        else:
            A("Rantai: (tak ada handler terdeteksi)")
        A("")
    A("## Klasifikasi")
    A("")
    A("### PRUNE — confidence high (prioritas hapus)")
    A("")
    if prune_h:
        A("| Fungsi | Lokasi | Alasan |")
        A("|---|---|---|")
        for c in prune_h:
            A(f"| `{c['name']}` | `{c['file']}:{c['line']}` | {c['reason']} |")
    else:
        A("_Tidak ada._")
    A("")
    A("### PRUNE — confidence medium (rantai kode mati)")
    A("")
    if prune_m:
        A("| Fungsi | Lokasi | Alasan |")
        A("|---|---|---|")
        for c in prune_m:
            A(f"| `{c['name']}` | `{c['file']}:{c['line']}` | {c['reason']} |")
    else:
        A("_Tidak ada._")
    A("")
    A("### MERGE — duplikat (verifikasi manual dulu)")
    A("")
    if merge_rows:
        A("| Grup fungsi | Rekomendasi kanonis |")
        A("|---|---|")
        for members, canon in merge_rows:
            A(f"| {members} | `{canon}` (pemanggil terbanyak) |")
    else:
        A("_Tidak ada._")
    A("")
    A("### REVIEW — butuh keputusan manusia")
    A("")
    rows_r = [(c["name"], f"`{c['file']}:{c['line']}`", c["reason"]) for c in review]
    for m in dead["missing_handlers"]:
        rows_r.append((m["handler"],
                       f"`{m['file']}:{m['line']}`",
                       f"handler entry `{m['entry']}` tak ditemukan — mungkin dinamis"))
    if rows_r:
        A("| Fungsi | Lokasi | Kenapa ambigu |")
        A("|---|---|---|")
        for name, loc, why in rows_r:
            A(f"| `{name}` | {loc} | {why} |")
    else:
        A("_Tidak ada._")
    A("")
    A("## Temuan integrasi — rantai yang putus")
    A("")
    A("Fitur yang \"ada\" tapi tidak benar-benar berfungsi — terutama yang saling berkaitan.")
    A("Aturan main: integrasi yang setengah terpasang lebih berbahaya daripada yang")
    A("tak ada sama sekali. Putuskan per temuan: **sambungkan rantainya sampai ujung**")
    A("(termasuk sync offline-first — lihat `references/offline-first.md`) atau")
    A("**cabut total** (kode + dependency + config).")
    A("")
    A("### Dependency tak terpakai")
    A("")
    if unused_deps or dead_only_deps:
        A("| Dependency | Manifest | Status |")
        A("|---|---|---|")
        for d in unused_deps:
            A(f"| `{d['name']}` | `{d['manifest']}` | tak diimpor di mana pun |")
        for d in dead_only_deps:
            locs = ", ".join(f"`{f}`" for f in d["imported_in"][:3])
            A(f"| `{d['name']}` | `{d['manifest']}` | hanya dipakai kode mati ({locs}) |")
    else:
        A("_Tidak ada._" if deps_data["deps"] else
          "_Tidak dicek (jalankan `scripts/unused_deps.py` untuk mengisi bagian ini)._")
    A("")
    A("### Rantai putus — fungsi integrasi yang mati")
    A("")
    if broken:
        A("| Fungsi | Lokasi | Sinyal integrasi | Artinya |")
        A("|---|---|---|---|")
        for c, signals in broken:
            A(f"| `{c['name']}` | `{c['file']}:{c['line']}` | {signals} | "
              f"rantai putus: integrasi terpasang tapi tak ada jalur hidup yang memakainya |")
    else:
        A("_Tidak ada._")
    A("")
    A("## Rekomendasi prioritas")
    A("")
    A("1. **PRUNE high** — risiko terendah. Satu commit per fungsi (mudah revert).")
    A("2. **MERGE** — setelah PRUNE, saat peta sudah bersih. Baca kedua badan manual sebelum gabung.")
    A("3. **REVIEW** — putuskan satu per satu; lengkapi dengan cek runtime (log/analytics).")
    A("4. **Temuan integrasi** — untuk tiap rantai putus: sambungkan sampai ujung atau cabut total.")
    A("5. **Ulangi** fase 2–3 setelah hapus/gabung — rantai mati baru sering muncul.")
    A("")
    A("## Batasan audit")
    A("")
    A("- Deteksi via pola regex: routing dinamis, reflection, magic method, DI container tak terlihat.")
    A("- Pemanggilan lintas bahasa (frontend→API) dan lintas repo tak terdeteksi otomatis.")
    A("- Fungsi `export` yang tak terpanggil dianggap REVIEW, bukan PRUNE.")
    A("- Nama fungsi integrasi ('upload', 'sync', ...) heuristik — bisa false positive, baca konteksnya.")
    A("- Sinyal config/env pada temuan integrasi hanya muncul bila script dijalankan dari root proyek.")
    A("- Kelengkapan rantai offline-first (lokal → antrean → sync) butuh verifikasi manual —")
    A("  lihat `references/offline-first.md`.")
    A("- Cek runtime (log 7–30 hari, analytics) belum dilakukan — lakukan sebelum eksekusi PRUNE.")

    with open(args.output, "w") as f:
        f.write("\n".join(L) + "\n")
    print(f"OK: laporan -> {args.output}")


if __name__ == "__main__":
    main()
