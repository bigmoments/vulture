#!/usr/bin/env python3
"""audit_report.py — gabungkan temuan jadi laporan Markdown.

Usage:
    audit_report.py --entries entries.json --graph graph.json --dead dead.json
                    [--project NAME] -o AUDIT.md

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
from collections import defaultdict


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
    ap.add_argument("--project", default="proyek")
    ap.add_argument("-o", "--output", required=True)
    args = ap.parse_args()

    entries = load(args.entries)
    graph = load(args.graph)
    dead = load(args.dead)
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
    A("## Rekomendasi prioritas")
    A("")
    A("1. **PRUNE high** — risiko terendah. Satu commit per fungsi (mudah revert).")
    A("2. **MERGE** — setelah PRUNE, saat peta sudah bersih. Baca kedua badan manual sebelum gabung.")
    A("3. **REVIEW** — putuskan satu per satu; lengkapi dengan cek runtime (log/analytics).")
    A("4. **Ulangi** fase 2–3 setelah hapus/gabung — rantai mati baru sering muncul.")
    A("")
    A("## Batasan audit")
    A("")
    A("- Deteksi via pola regex: routing dinamis, reflection, magic method, DI container tak terlihat.")
    A("- Pemanggilan lintas bahasa (frontend→API) dan lintas repo tak terdeteksi otomatis.")
    A("- Fungsi `export` yang tak terpanggil dianggap REVIEW, bukan PRUNE.")
    A("- Cek runtime (log 7–30 hari, analytics) belum dilakukan — lakukan sebelum eksekusi PRUNE.")

    with open(args.output, "w") as f:
        f.write("\n".join(L) + "\n")
    print(f"OK: laporan -> {args.output}")


if __name__ == "__main__":
    main()
