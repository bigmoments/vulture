#!/usr/bin/env python3
"""unused_deps.py — deteksi dependency yang dideklarasikan tapi tak diimpor.

Usage:
    unused_deps.py <dir> [-o deps.json]

Output JSON: {"deps": [{"name","manifest","file","imported","imported_in"}], "stats"}
  imported: True bila nama paket muncul di statement import/require codebase.
  imported_in: daftar file yang mengimpornya (untuk cek "hanya dipakai kode mati").

Mendukung: package.json (npm), requirements.txt (pip), composer.json,
go.mod, Gemfile. Heuristik nama paket vs nama import bisa beda
(mis. pip `Pillow` -> `import PIL`) — kasus itu dilaporkan di Batasan,
bukan false positive diam-diam.

Ini heuristik grep, bukan resolver. Yang tak terdeteksi (import dinamis,
plugin yang diregistrasi via config) harus diverifikasi manual.
"""
import argparse
import json
import os
import re
import sys

SKIP_DIRS = {"node_modules", ".git", "vendor", "__pycache__", ".venv", "venv",
             "dist", "build", ".next", "target", "coverage", ".idea", ".vscode"}

# pola import per ekstensi: (exts, [regex dengan grup nama paket])
IMPORT_PATTERNS = [
    ({".js", ".ts", ".mjs", ".cjs", ".jsx", ".tsx"}, [
        # import x from 'pkg' / import 'pkg' / export ... from 'pkg'
        # karakter pertama mengecualikan './' & '../' (import relatif),
        # tapi mengizinkan '@' (scoped package)
        r"""(?:import|export)[^'\"`]*?from\s*['"`]([^'\"`.\/][^'\"`]*)['\"`]""",
        r"""import\s*\(\s*['"`]([^'\"`.\/][^'\"`]*)['\"`]\s*\)""",
        r"""require\s*\(\s*['"`]([^'\"`.\/][^'\"`]*)['\"`]\s*\)""",
    ]),
    ({".py"}, [
        r"""^\s*(?:from|import)\s+([a-zA-Z0-9_]+)""",
    ]),
    ({".php"}, [
        r"""^\s*use\s+([A-Za-z0-9_\\]+)""",
    ]),
    ({".go"}, [
        r'''"([^"]+)"''',  # path import go: "github.com/org/pkg"
    ]),
    ({".rb"}, [
        r"""^\s*require\s*[''"]([^'"']+)[''"]""",
    ]),
]

# nama paket -> nama import yang dinormalisasi untuk dicocokkan
def norm_pkg(name):
    name = name.strip().lower()
    # pip: Pillow==x -> pillow ; npm @scope/pkg -> @scope/pkg
    name = re.split(r"[=<>!~\[\];\s]", name)[0]
    return name.replace("-", "_").replace(".", "_")


def norm_import(raw, ext):
    raw = raw.strip()
    if ext == ".go":
        # "github.com/cloudinary/cloudinary-go" -> cloudinary_go (cocok parsial)
        return raw.lower().replace("-", "_").replace(".", "_").replace("/", "_")
    if ext == ".php":
        # use Cloudinary\Uploader -> cloudinary
        return raw.split("\\")[0].lower()
    if raw.startswith("@"):
        return raw.lower()  # scoped npm: cocok penuh
    # npm: 'cloudinary/lib/x' -> 'cloudinary'
    return raw.split("/")[0].lower()


def parse_manifests(root):
    """-> [(pkg_name, manifest_rel_path)]"""
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            p = os.path.join(dirpath, fn)
            rel = os.path.relpath(p, root)
            try:
                if fn == "package.json":
                    with open(p, encoding="utf-8", errors="replace") as f:
                        data = json.load(f)
                    for section in ("dependencies", "devDependencies",
                                    "peerDependencies"):
                        for name in (data.get(section) or {}):
                            found.append((name, rel))
                elif fn == "requirements.txt":
                    with open(p, encoding="utf-8", errors="replace") as f:
                        for line in f:
                            line = line.strip()
                            if not line or line.startswith(("#", "-")):
                                continue
                            found.append((line, rel))
                elif fn == "composer.json":
                    with open(p, encoding="utf-8", errors="replace") as f:
                        data = json.load(f)
                    for section in ("require", "require-dev"):
                        for name in (data.get(section) or {}):
                            if name != "php":
                                found.append((name, rel))
                elif fn == "go.mod":
                    with open(p, encoding="utf-8", errors="replace") as f:
                        in_req = False
                        for line in f:
                            s = line.strip()
                            if s.startswith("require ("):
                                in_req = True
                                continue
                            if in_req and s == ")":
                                in_req = False
                                continue
                            if in_req or s.startswith("require "):
                                m = re.match(r"(?:require\s+)?(\S+)\s+v", s)
                                if m:
                                    found.append((m.group(1), rel))
                elif fn == "Gemfile":
                    with open(p, encoding="utf-8", errors="replace") as f:
                        for line in f:
                            m = re.match(r"""\s*gem\s*['"]([^'"]+)['"]""", line)
                            if m:
                                found.append((m.group(1), rel))
            except (OSError, json.JSONDecodeError, UnicodeDecodeError):
                continue
    # dedup, pertahankan manifest pertama
    seen, uniq = set(), []
    for name, rel in found:
        key = norm_pkg(name)
        if key not in seen:
            seen.add(key)
            uniq.append((name, rel))
    return uniq


def scan_imports(root):
    """-> {import_normalized: set(file_rel)}"""
    found = {}
    compiled = []
    for exts, pats in IMPORT_PATTERNS:
        for pat in pats:
            compiled.append((exts, re.compile(pat, re.MULTILINE)))
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            ext = os.path.splitext(fn)[1].lower()
            p = os.path.join(dirpath, fn)
            rel = os.path.relpath(p, root)
            # jangan hitung manifest sebagai "pemakaian"
            if os.path.basename(fn) in ("package.json", "composer.json",
                                        "go.mod", "Gemfile",
                                        "requirements.txt"):
                continue
            try:
                with open(p, encoding="utf-8", errors="replace") as f:
                    text = f.read()
            except OSError:
                continue
            for exts, rx in compiled:
                if ext not in exts:
                    continue
                for m in rx.finditer(text):
                    key = norm_import(m.group(1), ext)
                    found.setdefault(key, set()).add(rel)
    return found


def main():
    ap = argparse.ArgumentParser(description="Deteksi dependency tak terpakai")
    ap.add_argument("dir", help="direktori source yang diaudit")
    ap.add_argument("-o", "--output", default=None, help="file JSON output")
    args = ap.parse_args()

    root = os.path.abspath(args.dir)
    manifests = parse_manifests(root)
    imports = scan_imports(root)

    deps = []
    for name, rel in sorted(manifests, key=lambda x: x[0].lower()):
        key = norm_pkg(name)
        # cocok: sama persis, atau import mengandung nama paket (go paths)
        hits = set()
        for ikey, files in imports.items():
            if ikey == key or key in ikey or ikey in key:
                # hindari false positive substring pendek ("go" di "django")
                if len(key) >= 3:
                    hits |= files
        deps.append({"name": name, "manifest": rel,
                     "imported": bool(hits), "imported_in": sorted(hits)})

    unused = [d for d in deps if not d["imported"]]
    out = {"deps": deps,
           "stats": {"total": len(deps), "unused": len(unused)}}
    text = json.dumps(out, ensure_ascii=False, indent=1)
    if args.output:
        with open(args.output, "w") as f:
            f.write(text)
    else:
        print(text)
    print(f"OK: {len(deps)} dependency, {len(unused)} tak diimpor",
          file=sys.stderr)


if __name__ == "__main__":
    main()
