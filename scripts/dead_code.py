#!/usr/bin/env python3
"""dead_code.py — kandidat PRUNE: fungsi tak terjangkau dari entry point.

Usage:
    dead_code.py --graph graph.json --entries entries.json [-o dead.json]

Output JSON:
  {"candidates": [{"name","file","line","confidence","reason","callers"}],
   "missing_handlers": [{"entry","file","line"}],
   "stats": {...}}

confidence:
  high   — tak ada pemanggil sama sekali, tak diekspor.
  medium — pemanggil ada tapi semuanya juga mati (rantai kode mati).
  low    — ambigu -> REVIEW (diekspor, nama konvensi khusus).

HEURISTIK = kandidat, bukan vonis. Selalu butuh konfirmasi manusia
(lihat references/usefulness.md untuk cek runtime).
"""
import argparse
import json
import sys

REVIEW_NAMES = {"main", "__main__", "handler", "index", "app", "server",
                "bootstrap", "init"}


def load(p):
    with open(p) as f:
        return json.load(f)


def main():
    ap = argparse.ArgumentParser(description="Deteksi kandidat dead code")
    ap.add_argument("--graph", required=True, help="graph.json dari call_graph.py")
    ap.add_argument("--entries", required=True, help="entries.json dari entry_points.py")
    ap.add_argument("-o", "--output", default=None, help="file JSON output")
    args = ap.parse_args()

    graph = load(args.graph)
    entries = load(args.entries)
    nodes = graph["nodes"]
    edges = graph["edges"]

    by_name = {}
    for n in nodes:
        by_name.setdefault(n["name"], []).append(n)

    # adjacency
    calls = {}
    callers_of = {}
    for e in edges:
        calls.setdefault(e["from"], set()).add(e["to"])
        callers_of.setdefault(e["to"], set()).add(e["from"])

    # roots = handler entry point + konvensi main
    roots = set()
    missing_handlers = []
    for e in entries:
        h = e.get("handler")
        if h:
            if h in by_name:
                roots.add(h)
            else:
                missing_handlers.append({"entry": e.get("name"),
                                         "handler": h,
                                         "file": e.get("file"),
                                         "line": e.get("line")})
    for n in nodes:
        if n["name"] in REVIEW_NAMES:
            roots.add(n["name"])

    # reachability (BFS)
    reachable = set()
    stack = list(roots)
    while stack:
        cur = stack.pop()
        if cur in reachable:
            continue
        reachable.add(cur)
        stack.extend(calls.get(cur, ()))

    candidates = []
    for n in nodes:
        name = n["name"]
        if name in reachable:
            continue
        callers = sorted(callers_of.get(name, ()))
        live_callers = [c for c in callers if c in reachable]
        dead_callers = [c for c in callers if c not in reachable]
        if n.get("exported") or name in REVIEW_NAMES or name.startswith("test_"):
            confidence, reason = "low", (
                "REVIEW: diekspor / konvensi khusus — mungkin public API "
                "atau dipakai repo lain; butuh keputusan manusia")
        elif not callers:
            confidence, reason = "high", "tak ada pemanggil sama sekali"
        elif not live_callers:
            confidence, reason = "medium", (
                "hanya dipanggil kode mati: " + ", ".join(dead_callers))
        else:  # seharusnya tak terjadi (live caller -> reachable)
            confidence, reason = "low", "REVIEW: anomali reachability"
        candidates.append({"name": name, "file": n["file"], "line": n["line"],
                           "confidence": confidence, "reason": reason,
                           "callers": callers})

    out = {
        "candidates": sorted(candidates,
                             key=lambda c: ({"high": 0, "medium": 1, "low": 2}
                                            [c["confidence"]], c["file"], c["line"])),
        "missing_handlers": missing_handlers,
        "stats": {
            "total_functions": len(nodes),
            "reachable": len([n for n in nodes if n["name"] in reachable]),
            "candidates": len(candidates),
            "roots": sorted(roots),
        },
    }
    text = json.dumps(out, ensure_ascii=False, indent=1)
    if args.output:
        with open(args.output, "w") as f:
            f.write(text)
    else:
        print(text)
    print(f"OK: {len(candidates)} kandidat "
          f"(high={sum(1 for c in candidates if c['confidence']=='high')}, "
          f"medium={sum(1 for c in candidates if c['confidence']=='medium')}, "
          f"low={sum(1 for c in candidates if c['confidence']=='low')})",
          file=sys.stderr)


if __name__ == "__main__":
    main()
