#!/usr/bin/env python3
"""entry_points.py — deteksi heuristik entry point via pola framework.

Usage:
    entry_points.py <dir> [-o entries.json]

Output JSON: [{"type","name","handler","file","line","source"}, ...]
  type: http-route | cli | cron | export | page
  source: "heuristic" (pola) — entri manual ditambahkan terpisah.

Ini heuristik pola, bukan parser. Yang tak terdeteksi (routing dinamis,
registrasi via config) harus didaftarkan manual, format lihat
references/inventory.md.
"""
import argparse
import json
import os
import re
import sys

SKIP_DIRS = {"node_modules", ".git", "vendor", "__pycache__", ".venv", "venv",
             "dist", "build", ".next", "target", "coverage", ".idea", ".vscode"}
SKIP_FILES = {"package-lock.json", "yarn.lock", "composer.lock"}

# (type, exts, regex, name_group, handler_group|None, handler_is_next_def)
# handler_is_next_def: handler = `def`/`function` di baris-baris berikut (decorator)
PATTERNS = [
    # --- JS/TS: Express/Hono/Fastify/Koa ---
    ("http-route", {".js", ".ts", ".mjs", ".cjs"},
     r"(?:app|router)\s*\.\s*(?:get|post|put|patch|delete|head|options|all|use)"
     r"\s*\(\s*['\"`]([^'\"`]+)['\"`]\s*(?:,\s*(?:async\s*)?(\w+))?", 1, 2, False),
    # --- JS/TS: Commander / yargs ---
    ("cli", {".js", ".ts", ".mjs", ".cjs"},
     r"(?:program|yargs)\s*\.\s*command\s*\(\s*['\"`]([^'\"`]+)['\"`]", 1, None, False),
    # --- JS/TS: cron ---
    ("cron", {".js", ".ts", ".mjs", ".cjs"},
     r"(?:cron\s*\.\s*schedule|node-cron|schedule\s*\.\s*every)\s*\(",
     0, None, False),
    # --- JS/TS: exported API ---
    ("export", {".js", ".ts", ".mjs", ".cjs"},
     r"export\s+(?:async\s+)?(?:function\s+(\w+)|const\s+(\w+)\s*=)", 1, None, False),
    ("export", {".js", ".cjs"},
     r"module\s*\.\s*exports(?:\s*\.\s*(\w+))?\s*=", 1, None, False),
    # --- Python: Flask / FastAPI / Starlette (decorator -> def berikut) ---
    ("http-route", {".py"},
     r"@(?:app|router|bp|blueprint)\s*\.\s*(?:route|get|post|put|patch|delete)"
     r"\s*\(\s*['\"`]([^'\"`]+)['\"`]", 1, None, True),
    # --- Python: Click ---
    ("cli", {".py"},
     r"@click\s*\.\s*(?:command|group)\s*\(", 0, None, True),
    # --- Python: argparse ---
    ("cli", {".py"},
     r"add_parser\s*\(\s*['\"`]([^'\"`]+)['\"`]", 1, None, False),
    # --- Python: Celery task ---
    ("cron", {".py"},
     r"@(?:app\s*\.\s*task|shared_task)\s*(?:\([^)]*\))?", 0, None, True),
    # --- PHP: Laravel (tangkap juga [Controller::class, 'method']) ---
    ("http-route", {".php"},
     r"Route\s*::\s*(?:get|post|put|patch|delete|any|match)"
     r"\s*\(\s*['\"`]([^'\"`]+)['\"`]"
     r"(?:\s*,\s*\[\s*[\w\\]+::class\s*,\s*['\"`](\w+)['\"`])?",
     1, 2, False),
    # --- PHP: WordPress ---
    ("http-route", {".php"},
     r"(?:add_action|add_shortcode|register_rest_route)\s*\(\s*['\"`]([^'\"`]+)['\"`]",
     1, None, False),
    # --- Java: Spring ---
    ("http-route", {".java", ".kt"},
     r"@(?:GetMapping|PostMapping|PutMapping|PatchMapping|DeleteMapping|RequestMapping)"
     r"(?:\s*\(\s*['\"`]([^'\"`]+)['\"`])?", 1, None, True),
    ("cron", {".java", ".kt"},
     r"@Scheduled\s*(?:\([^)]*\))?", 0, None, True),
    # --- Go ---
    ("http-route", {".go"},
     r"(?:http\s*\.\s*HandleFunc|(?:router|mux|r)\s*\.\s*(?:GET|POST|PUT|PATCH|DELETE|HandleFunc))"
     r"\s*\(\s*['\"`]([^'\"`]+)['\"`]\s*(?:,\s*(\w+))?", 1, 2, False),
    # --- Ruby: Rails ---
    ("http-route", {".rb"},
     r"^\s*(?:get|post|put|patch|delete)\s+['\"`]([^'\"`]+)['\"`]", 1, None, False),
    ("cli", {".rb"},
     r"task\s+['\"`:]([\w:]+)['\"`]?\s+do", 1, None, False),
]

NEXT_DEF = re.compile(r"^\s*(?:async\s+)?(?:def|function)\s+(\w+)")


def find_handler_next(lines, start_idx, limit=6):
    for i in range(start_idx + 1, min(start_idx + 1 + limit, len(lines))):
        m = NEXT_DEF.match(lines[i])
        if m:
            return m.group(1)
    return None


def scan_file(path, rel):
    results = []
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except OSError:
        return results
    ext = os.path.splitext(path)[1].lower()
    for etype, exts, pat, ng, hg, next_def in PATTERNS:
        if ext not in exts:
            continue
        rx = re.compile(pat)
        for i, line in enumerate(lines):
            for m in rx.finditer(line):
                name = m.group(ng) if ng else None
                handler = None
                if hg:
                    try:
                        handler = m.group(hg)
                    except IndexError:
                        handler = None
                if next_def:
                    handler = find_handler_next(lines, i)
                # export: grup 1 atau 2
                if etype == "export" and not name:
                    try:
                        name = m.group(2)
                    except IndexError:
                        pass
                results.append({
                    "type": etype,
                    "name": name or "(anonymous)",
                    "handler": handler,
                    "file": rel,
                    "line": i + 1,
                    "source": "heuristic",
                })
    # package.json bin -> cli
    if os.path.basename(path) == "package.json":
        try:
            data = json.loads("".join(lines))
            for bname, bpath in (data.get("bin") or {}).items():
                results.append({"type": "cli", "name": bname,
                                "handler": None, "file": rel, "line": 1,
                                "source": "heuristic"})
        except (json.JSONDecodeError, AttributeError):
            pass
    return results


def walk(root):
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if fn in SKIP_FILES:
                continue
            files.append(os.path.join(dirpath, fn))
    return sorted(files)


def main():
    ap = argparse.ArgumentParser(description="Deteksi entry point (heuristik pola)")
    ap.add_argument("dir", help="direktori source yang diaudit")
    ap.add_argument("-o", "--output", default=None, help="file JSON output")
    args = ap.parse_args()

    root = os.path.abspath(args.dir)
    entries = []
    for path in walk(root):
        entries.extend(scan_file(path, os.path.relpath(path, root)))

    # dedup
    seen, uniq = set(), []
    for e in entries:
        key = (e["type"], e["name"], e["file"], e["line"])
        if key not in seen:
            seen.add(key)
            uniq.append(e)

    out = json.dumps(uniq, ensure_ascii=False, indent=1)
    if args.output:
        with open(args.output, "w") as f:
            f.write(out)
    else:
        print(out)
    by_type = {}
    for e in uniq:
        by_type[e["type"]] = by_type.get(e["type"], 0) + 1
    print(f"OK: {len(uniq)} entry point ({by_type})", file=sys.stderr)


if __name__ == "__main__":
    main()
