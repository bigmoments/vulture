#!/usr/bin/env python3
"""interactive.py — wizard interaktif vulture: triase + eksekusi mekanis.

Usage:
    interactive.py <dir> [--project NAME]

Alur:
  1. Jalankan fase 1-3 (+deps) otomatis.
  2. Tampilkan ringkasan temuan.
  3. Tuntun per temuan, satu per satu:
     - PRUNE  : preview fungsi -> konfirmasi -> hapus (potongan di-backup).
     - MERGE  : tampilkan grup -> pilih kanonis (dicatat; eksekusi oleh agent).
     - REVIEW : pertahankan / tandai hapus (dicatat).
     - Rantai putus : sambungkan (masuk antrean agent -> FIX-QUEUE.md) /
                      cabut / lewati.
     - Dep tak terpakai : catat keputusan (edit manifest oleh manusia/agent).
  4. Tulis vulture-decisions.json + vulture-removed.bak.md + FIX-QUEUE.md.
  5. Re-audit fase 2-3 untuk konfirmasi hasil.

Batasan jujur: penyambungan rantai (wiring) TIDAK dilakukan script ini —
butuh penilaian kode, didelegasikan ke agent via FIX-QUEUE.md.
Penghapusan selalu preview + konfirmasi; direktori non-git diberi peringatan
karena revert tidak semudah `git checkout`.

Stdlib only. Bahasa: Indonesia.
"""
import argparse
import datetime
import json
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
from audit_report import INTEGRATION_HINTS, ENV_RX  # noqa: E402

DECISIONS_FILE = "vulture-decisions.json"
BACKUP_FILE = "vulture-removed.bak.md"
FIXQUEUE_FILE = "FIX-QUEUE.md"


def sh(script, *args):
    r = subprocess.run([sys.executable, os.path.join(SCRIPT_DIR, script),
                        *args], capture_output=True, text=True)
    if r.returncode != 0:
        print(f"GAGAL menjalankan {script}:\n{r.stderr}", file=sys.stderr)
        sys.exit(1)
    return r


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def ask(prompt, default="n"):
    """default 'n' bila EOF (piped) — aman: lewati, bukan eksekusi."""
    try:
        ans = input(prompt).strip().lower()
    except EOFError:
        return default
    if ans == "q":
        print("\nDibatalkan user. Keputusan sejauh ini sudah tersimpan.")
        sys.exit(0)
    return ans or default


def fn_range(lines, start_1based):
    """(start0, end0_excl) blok fungsi mulai baris start_1based (1-based).

    C-like: brace matching dari '{' pertama. Python/dll: sampai node
    berikut (dibatasi pemanggil via max_end). Termasuk decorator di atasnya.
    """
    n = len(lines)
    s = start_1based - 1
    # sertakan decorator/baris @ di atas def
    while s > 0 and lines[s - 1].lstrip().startswith("@"):
        s -= 1
    # coba brace matching
    depth = 0
    started = False
    for i in range(start_1based - 1, n):
        for ch in lines[i]:
            if ch == "{":
                depth += 1
                started = True
            elif ch == "}":
                depth -= 1
        if started and depth == 0:
            return s, i + 1
    return s, n  # fallback: sampai akhir (pemanggil boleh memotong)


def preview(lines, s, e, max_lines=18):
    out = []
    for i in range(s, min(e, s + max_lines)):
        out.append(f"  {i+1:4d}: {lines[i].rstrip()}")
    if e - s > max_lines:
        out.append(f"  ... (+{e - s - max_lines} baris)")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description="Wizard interaktif vulture")
    ap.add_argument("dir", help="direktori source yang diaudit")
    ap.add_argument("--project", default="proyek")
    args = ap.parse_args()

    root = os.path.abspath(args.dir)
    os.chdir(root)
    if not os.path.isdir(os.path.join(root, ".git")):
        print("PERINGATAN: bukan git repo — penghapusan tak mudah di-revert.\n"
              f"Potongan yang dihapus di-backup ke {BACKUP_FILE}.\n")

    print("Fase 1-3 berjalan otomatis...")
    sh("entry_points.py", ".", "-o", "entries.json")
    sh("call_graph.py", ".", "-o", "graph.json")
    sh("dead_code.py", "--graph", "graph.json",
       "--entries", "entries.json", "-o", "dead.json")
    sh("unused_deps.py", ".", "-o", "deps.json")

    graph = load("graph.json")
    dead = load("dead.json")
    deps_data = load("deps.json")
    nodes = graph["nodes"]

    by_name = {}
    for x in nodes:
        by_name.setdefault(x["name"], []).append(x)

    # duplikat
    dup_groups = {}
    for x in nodes:
        if x.get("body_hash"):
            dup_groups.setdefault(x["body_hash"], []).append(x)
    dup_groups = {h: g for h, g in dup_groups.items() if len(g) > 1}
    dup_names = {x["name"] for g in dup_groups.values() for x in g}

    dead_by_name = {c["name"]: c for c in dead["candidates"]}
    prune = [c for c in dead["candidates"]
             if c["confidence"] in ("high", "medium") and c["name"] not in dup_names]
    review = [c for c in dead["candidates"]
              if c["confidence"] == "low" and c["name"] not in dup_names]

    # rantai putus (ringkas dari logika audit_report)
    dep_importers = {d["name"]: d.get("imported_in", [])
                     for d in deps_data["deps"]}
    broken = []
    for c in [x for x in dead["candidates"]
              if x["confidence"] in ("high", "medium")]:
        hint = next((h for h in INTEGRATION_HINTS if h in c["name"].lower()), None)
        sdks = [dn for dn, fs in dep_importers.items() if c["file"] in fs]
        if hint or sdks:
            broken.append((c, hint, sdks))

    total = len(prune) + len(dup_groups) + len(review) + len(broken)
    print(f"\nDitemukan {total} temuan: PRUNE {len(prune)} | MERGE {len(dup_groups)} grup | "
          f"REVIEW {len(review)} | rantai putus {len(broken)}")
    print("Jawab 'q' kapan saja untuk berhenti (keputusan tersimpan).\n")

    decisions = {"date": datetime.date.today().isoformat(),
                 "project": args.project, "deleted": [],
                 "merge_decisions": [], "review_decisions": [],
                 "dep_decisions": [], "fix_queue": []}
    backup = [f"# Backup potongan yang dihapus — {args.project} "
              f"({decisions['date']})\n"]

    def save():
        with open(DECISIONS_FILE, "w") as f:
            json.dump(decisions, f, ensure_ascii=False, indent=1)
        with open(BACKUP_FILE, "w") as f:
            f.write("\n".join(backup) + "\n")

    def do_delete(c):
        node = next((x for x in by_name.get(c["name"], [])
                     if x["file"] == c["file"] and x["line"] == c["line"]), None)
        if node is None:
            print("  (node tak ditemukan di graph — dilewati)")
            return False
        with open(node["file"], encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        # batasi akhir blok oleh node berikut di file yang sama
        same = sorted(x["line"] for x in nodes if x["file"] == node["file"])
        idx = same.index(node["line"])
        limit = same[idx + 1] if idx + 1 < len(same) else None
        s, e = fn_range(lines, node["line"])
        if limit is not None:
            e = min(e, limit - 1)
        print(f"\n--- {c['name']} @ {node['file']}:{node['line']} "
              f"(alasan: {c['reason']}) ---")
        print(preview(lines, s, e))
        if ask("Hapus fungsi ini? [y/N/q]: ") != "y":
            print("  Dilewati.")
            return False
        snippet = "".join(lines[s:e])
        backup.append(f"\n## {c['name']} — {node['file']}:{s+1}-{e}\n"
                      f"```\n{snippet}```\n")
        del lines[s:e]
        with open(node["file"], "w", encoding="utf-8") as f:
            f.writelines(lines)
        decisions["deleted"].append(
            {"name": c["name"], "file": node["file"],
             "lines": [s + 1, e]})
        save()
        print("  Dihapus. Potongan tersimpan di " + BACKUP_FILE)
        return True

    # --- 1. PRUNE ---
    for i, c in enumerate(prune, 1):
        print(f"\n=== [{i}/{len(prune)}] PRUNE ({c['confidence']}): "
              f"`{c['name']}` — {c['file']}:{c['line']}")
        do_delete(c)

    # --- 2. MERGE ---
    for gi, (h, g) in enumerate(sorted(dup_groups.items(),
                                       key=lambda kv: kv[1][0]["file"]), 1):
        members = ", ".join(f"{x['name']} ({x['file']}:{x['line']})" for x in g)
        print(f"\n=== [{gi}/{len(dup_groups)}] MERGE: {members}")
        print("Fungsi-fungsi ini berbadan identik. Penggabungan butuh baca manual.")
        ans = ask("Pilih kanonis (ketik nama) / lewati [Enter] / q: ", default="")
        if ans and ans != "q":
            decisions["merge_decisions"].append(
                {"group": members, "canonical": ans,
                 "note": "eksekusi oleh agent/manusia"})
            save()
            print(f"  Dicatat: kanonis = {ans} (belum dieksekusi).")

    # --- 3. REVIEW ---
    for i, c in enumerate(review, 1):
        print(f"\n=== [{i}/{len(review)}] REVIEW: `{c['name']}` — "
              f"{c['file']}:{c['line']}\nAlasan ambigu: {c['reason']}")
        ans = ask("Pertahankan? [Y/n/q] (n = tandai untuk dihapus): ", default="y")
        decisions["review_decisions"].append(
            {"name": c["name"], "file": c["file"],
             "decision": "keep" if ans == "y" else "drop"})
        save()

    # --- 4. Rantai putus ---
    for i, (c, hint, sdks) in enumerate(broken, 1):
        sig = []
        if hint:
            sig.append(f"nama mengandung '{hint}'")
        if sdks:
            sig.append("SDK: " + ", ".join(sdks))
        print(f"\n=== [{i}/{len(broken)}] RANTAI PUTUS: `{c['name']}` — "
              f"{c['file']}:{c['line']}\nSinyal: {'; '.join(sig)}")
        print("  [s]ambungkan (dikerjakan agent — butuh penilaian kode)")
        print("  [c]abut total (fungsi + dep + config)")
        print("  [l]ewati")
        ans = ask("Pilih [s/c/l/q]: ", default="l")
        if ans == "s":
            decisions["fix_queue"].append(
                {"name": c["name"], "file": c["file"], "line": c["line"],
                 "action": "wire", "signals": "; ".join(sig),
                 "note": "butuh agent: tentukan titik sambung, tulis diff, minta persetujuan"})
            save()
            print("  Masuk antrean agent → " + FIXQUEUE_FILE)
        elif ans == "c":
            if do_delete(c):
                print("  Catatan: cabut juga dependency & config terkait secara manual.")

    # --- 5. Dep tak terpakai (keputusan saja) ---
    unused = [d for d in deps_data["deps"] if not d["imported"]]
    for i, d in enumerate(unused, 1):
        print(f"\n=== [{i}/{len(unused)}] DEP TAK TERPAKAI: `{d['name']}` "
              f"({d['manifest']})")
        ans = ask("Setujui pencabutan dari manifest? [y/N/q] "
                  "(dieksekusi manual/agent): ")
        decisions["dep_decisions"].append(
            {"name": d["name"], "manifest": d["manifest"],
             "approved": ans == "y"})
        save()

    # --- FIX-QUEUE.md untuk agent ---
    if decisions["fix_queue"]:
        q = ["# Antrean perbaikan wiring (untuk agent)\n",
             "> Dibuat oleh interactive.py. Setiap item: tentukan titik sambung,",
             "> tulis diff minimal, minta persetujuan user per diff",
             "> (lihat references/fixing.md), lalu verifikasi via re-audit.\n"]
        for it in decisions["fix_queue"]:
            q.append(f"## `{it['name']}` — {it['file']}:{it['line']}")
            q.append(f"- Sinyal keterkaitan: {it['signals']}")
            q.append(f"- Aksi: {it['action']} (wiring)")
            q.append("")
        with open(FIXQUEUE_FILE, "w") as f:
            f.write("\n".join(q) + "\n")
        print(f"\nAntrean wiring ditulis ke {FIXQUEUE_FILE}")

    # --- re-audit ---
    if decisions["deleted"]:
        print("\nRe-audit fase 2-3 untuk konfirmasi...")
        sh("call_graph.py", ".", "-o", "graph.json")
        sh("dead_code.py", "--graph", "graph.json",
           "--entries", "entries.json", "-o", "dead.json")
        d2 = load("dead.json")
        left = [c for c in d2["candidates"]
                if c["confidence"] in ("high", "medium")]
        print(f"Sisa kandidat PRUNE: {len(left)} "
              f"(sebelum: {len(prune)})")

    save()
    print(f"\nSelesai. Keputusan tersimpan di {DECISIONS_FILE}.")
    if decisions["deleted"]:
        print(f"Backup potongan di {BACKUP_FILE}.")


if __name__ == "__main__":
    main()
