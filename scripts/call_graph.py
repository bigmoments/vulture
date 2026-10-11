#!/usr/bin/env python3
"""call_graph.py — call graph kasar via regex definisi fungsi + pemanggilan.

Usage:
    call_graph.py <dir> [-o graph.json]

Output JSON:
  {"nodes": [{"name","file","line","kind","exported","body_hash"}],
   "edges": [{"from","to","file","line"}]}

Heuristik C-like: badan fungsi = baris definisi s/d definisi berikutnya.
body_hash dipakai fase 4 untuk deteksi duplikat (None bila badan trivial).
Bukan pengganti parser/compiler — baca batasan di references/relations.md.
"""
import argparse
import hashlib
import json
import os
import re
import sys

SKIP_DIRS = {"node_modules", ".git", "vendor", "__pycache__", ".venv", "venv",
             "dist", "build", ".next", "target", "coverage", ".idea", ".vscode"}

# (kind, exts, regex)
DEF_PATTERNS = [
    ("function", {".js", ".ts", ".mjs", ".cjs"},
     r"^\s*(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\("),
    ("function", {".js", ".ts", ".mjs", ".cjs"},
     r"^\s*(?:export\s+)?const\s+(\w+)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>"),
    ("function", {".js", ".ts", ".mjs", ".cjs"},
     r"^\s*(?:export\s+)?const\s+(\w+)\s*=\s*(?:async\s*)?function\s*\("),
    ("function", {".py"},
     r"^\s*(?:async\s+)?def\s+(\w+)\s*\("),
    ("function", {".php"},
     r"(?<!use\s)(?<!use)function\s+(\w+)\s*\("),
    ("function", {".java", ".kt"},
     r"^\s*(?:public|private|protected)?\s*(?:static\s+)?[\w<>\[\]]+\s+(\w+)\s*\("),
    ("function", {".go"},
     r"^\s*func\s+(?:\(\s*\w+\s+[\w*]+\s*\)\s*)?(\w+)\s*\("),
    ("function", {".rb"},
     r"^\s*def\s+(\w+)"),
]

CALL_RX = re.compile(r"\b([A-Za-z_]\w*)\s*\(")

KEYWORDS = {
    # js/ts
    "if", "else", "for", "while", "do", "switch", "case", "catch", "try",
    "finally", "return", "throw", "new", "typeof", "instanceof", "in", "of",
    "await", "yield", "delete", "void", "function", "class", "import", "from",
    "with", "debugger",
    # py
    "def", "lambda", "as", "assert", "print",
    # php
    "echo", "isset", "empty", "array", "list", "die", "exit", "include",
    "include_once", "require", "require_once", "print_r", "var_dump",
    "foreach", "endforeach", "endif", "endwhile", "fn", "match", "clone",
    # java/go
    "synchronized",
    # ruby
    "end", "elsif", "unless", "begin", "rescue", "ensure",
}

MIN_BODY_HASH_LEN = 40  # badan lebih pendek dari ini dianggap trivial


def normalize_body(text):
    return re.sub(r"\s+", "", text)


def scan_file(path, rel):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except OSError:
        return []
    ext = os.path.splitext(path)[1].lower()
    defs = []  # (line_idx, name, exported)
    for i, line in enumerate(lines):
        for kind, exts, pat in DEF_PATTERNS:
            if ext not in exts:
                continue
            m = re.search(pat, line)
            if m:
                name = m.group(1)
                if name in KEYWORDS:
                    continue
                exported = bool(re.search(r"^\s*export\b", line))
                defs.append((i, name, exported))
                break
    nodes = []
    for idx, (li, name, exported) in enumerate(defs):
        end = defs[idx + 1][0] if idx + 1 < len(defs) else len(lines)
        body_lines = lines[li + 1:end]
        calls = []
        for j, bl in enumerate(body_lines):
            for cm in CALL_RX.finditer(bl):
                cname = cm.group(1)
                if cname in KEYWORDS or cname == name:
                    continue
                calls.append((cname, li + 1 + j + 1))  # 1-based line
        norm = normalize_body("".join(body_lines))
        body_hash = (hashlib.sha256(norm.encode()).hexdigest()[:16]
                     if len(norm) >= MIN_BODY_HASH_LEN else None)
        nodes.append({"name": name, "file": rel, "line": li + 1,
                      "kind": "function", "exported": exported,
                      "body_hash": body_hash, "_calls": calls})
    return nodes


def walk(root):
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in sorted(filenames):
            files.append(os.path.join(dirpath, fn))
    return files


def main():
    ap = argparse.ArgumentParser(description="Call graph kasar (heuristik regex)")
    ap.add_argument("dir", help="direktori source yang diaudit")
    ap.add_argument("-o", "--output", default=None, help="file JSON output")
    args = ap.parse_args()

    root = os.path.abspath(args.dir)
    all_nodes = []
    for path in walk(root):
        all_nodes.extend(scan_file(path, os.path.relpath(path, root)))

    defined = {n["name"] for n in all_nodes}
    edges, seen_e = [], set()
    for n in all_nodes:
        for cname, cline in n.pop("_calls"):
            if cname in defined:
                key = (n["name"], cname)
                if key not in seen_e:
                    seen_e.add(key)
                    edges.append({"from": n["name"], "to": cname,
                                  "file": n["file"], "line": cline})

    graph = {"nodes": all_nodes, "edges": edges}
    out = json.dumps(graph, ensure_ascii=False, indent=1)
    if args.output:
        with open(args.output, "w") as f:
            f.write(out)
    else:
        print(out)
    print(f"OK: {len(all_nodes)} fungsi, {len(edges)} edge", file=sys.stderr)


if __name__ == "__main__":
    main()
