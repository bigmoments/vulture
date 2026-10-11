# vulture

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Format: Markdown](https://img.shields.io/badge/format-markdown-blue.svg)](#)
[![Python: stdlib only](https://img.shields.io/badge/python-stdlib%20only-blue.svg)](scripts/)
[![PRs welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

A language-agnostic agent skill for **auditing application features**: inventory entry points, map function relationships, detect dead code & duplicates, classify every function as KEEP / MERGE / PRUNE / REVIEW, and produce a prioritized report. Works for JS/TS, PHP, Python, Java, Go, Ruby, and other C-like languages.

> **Note:** the skill content itself is written in **Bahasa Indonesia** (its trigger phrases and working language). This README is in English for the GitHub audience.

---

## Why this skill exists

Every long-lived codebase accumulates the same unknowns: *what features actually exist? how are they connected? which code is dead?* Guessing leads to either paralysis ("don't touch anything") or breakage ("oops, that was used"). This skill encodes a disciplined 5-phase workflow so an agent maps the territory first — with an explicit honesty rule: **heuristics find candidates, never verdicts**. Ambiguous findings go to REVIEW for a human to decide.

**Core principles:**

1. **Heuristics = candidates.** The scripts use regex patterns, not a compiler. Never delete code on a report alone.
2. **Entry points first.** Without a correct entry-point list, every later phase points the wrong way.
3. **REVIEW is a feature.** Ambiguous functions belong in REVIEW — that's the design working, not failing.
4. **Smallest scope first.** Audit one module before the whole repo.
5. **Record what's missed.** Patterns the scripts can't see go in the report's Limitations section — never silently ignored.

---

## The 5-phase workflow

1. **Inventory entry points** — HTTP routes, pages, UI actions, cron/jobs, CLI commands, exported APIs, connectivity events (`online`/`offline`), background sync → `scripts/entry_points.py` → `entries.json`
2. **Map relationships** — entry point → called functions → touched data (tables, external APIs, files) → `scripts/call_graph.py` → `graph.json`
3. **Test usefulness** — three questions per function: *any callers? any runtime access? what breaks if deleted?* → `scripts/dead_code.py` → `dead.json` (candidates with confidence: high / medium / low); declared-but-never-imported dependencies → `scripts/unused_deps.py` → `deps.json`. For interrelated features, verify the **end of the chain** (data actually landed in the cloud), not just that the entry fired. Offline-first apps: see `references/offline-first.md`
4. **Classify** — KEEP (live) / MERGE (duplicate) / PRUNE (dead) / REVIEW (ambiguous, needs a human)
5. **Report** — one document: feature map, classification tables, **integration findings (broken chains)**, draft fix proposals, priority order → `scripts/audit_report.py` → `AUDIT.md`
6. **Fix (optional)** — only on explicit request ("fix", "perbaiki", "sambungkan"): wire broken chains so related features actually work, guided by `references/fixing.md`. Every diff needs human approval; every fix is verified by re-running phases 2–3 (PRUNE → KEEP) plus runtime tests

---

## Usage

**Via chat (primary).** This is an agent skill — invoke it by asking your assistant. Examples:

- "vulture, audit the codebase at ~/my-project"
- "check for dead code in this repo"
- "what features exist in this app?"

The agent runs the 5-phase workflow and delivers `AUDIT.md`: feature map, KEEP/MERGE/PRUNE/REVIEW classification tables, and prioritized recommendations. Deletion/merging decisions stay with the human.

**Manual (optional).** The scripts are pure Python 3 stdlib and can be run directly, no assistant needed:

```bash
python3 scripts/entry_points.py <dir> -o entries.json
python3 scripts/call_graph.py <dir> -o graph.json
python3 scripts/dead_code.py --graph graph.json --entries entries.json -o dead.json
python3 scripts/unused_deps.py <dir> -o deps.json
python3 scripts/audit_report.py --entries entries.json --graph graph.json --dead dead.json --deps deps.json -o AUDIT.md
```

**Interactive (optional).** `python3 scripts/interactive.py <dir>` — wizard that runs phases 1–3 automatically, then walks you through each finding: delete PRUNE candidates with confirmation (backed up), record MERGE/REVIEW decisions, and queue broken-chain wiring for the agent (`FIX-QUEUE.md`). Wiring itself stays with the agent in chat (phase 6) since it needs code judgment.

---

## Modules

| Module | When the agent reads it |
|---|---|
| `references/inventory.md` | Phase 1 — entry-point patterns per framework/language |
| `references/relations.md` | Phase 2 — building the relationship map, heuristic limits |
| `references/usefulness.md` | Phase 3 — the three usefulness questions, chain-end verification, runtime checks (logs, analytics, grep) |
| `references/classification-report.md` | Phases 4–5 — KEEP/MERGE/PRUNE/REVIEW criteria, report format, execution priority |
| `references/offline-first.md` | Phase 3/5 — offline-first requirements: local-first chain, outbox, sync triggers, retry, conflict strategy, no-data-loss verification |
| `references/fixing.md` | Phase 6 (optional, explicit request only) — fix principles, relatedness signals, wiring vs prune/merge execution, approval workflow, mandatory verification |

The agent reads only the relevant modules — never everything at once.

---

## Scripts

Pure Python 3, **stdlib only**, executable directly:

| Script | Input → Output |
|---|---|
| `scripts/entry_points.py <dir>` | source dir → `entries.json` (heuristic entry-point detection, incl. `online`/`offline` events & background sync) |
| `scripts/call_graph.py <dir>` | source dir → `graph.json` (nodes, edges, body hashes) |
| `scripts/dead_code.py --graph g.json --entries e.json` | graph + entries → `dead.json` (PRUNE candidates + confidence) |
| `scripts/unused_deps.py <dir>` | source dir → `deps.json` (declared but never imported dependencies) |
| `scripts/audit_report.py --entries e.json --graph g.json --dead d.json [--deps d.json] -o AUDIT.md` | all findings → Markdown report (incl. broken-chain integration findings) |
| `scripts/interactive.py <dir>` | interactive wizard: auto phases 1–3, per-finding triage (delete PRUNE with confirmation + backup, record MERGE/REVIEW decisions, queue wiring for agent → `FIX-QUEUE.md`), auto re-audit |

```bash
scripts/entry_points.py ./src -o entries.json
scripts/call_graph.py ./src -o graph.json
scripts/dead_code.py --graph graph.json --entries entries.json -o dead.json
scripts/unused_deps.py ./src -o deps.json
scripts/audit_report.py --entries entries.json --graph graph.json --dead dead.json --deps deps.json -o AUDIT.md
```

See `examples/sample-report.md` and `examples/sample-output.json` for the output shape.

---

## Installation

Pure Markdown + Python scripts, standard `SKILL.md` format. No hooks, plugins, MCP, or dependencies. Copy the `vulture/` folder into your harness's skills directory:

| Harness | Skills directory |
|---|---|
| Claude Code | `~/.claude/skills/` |
| Cursor | `<project>/.cursor/skills/` or `~/.cursor/skills/` |
| Codex | `~/.codex/skills/` |
| Antigravity / Gemini CLI | skills directory per each tool's docs |

---

## Honesty contract

This skill will not tell you a function is dead — it tells you it's a *candidate*, with a confidence level and a reason, plus everything it could not verify. The REVIEW category exists because real codebases have dynamic routing, reflection, cross-repo usage, and seasonal jobs. A report with zero REVIEW items on a large codebase should make you suspicious, not happy.

The same honesty extends to fixing (phase 6, explicit request only): proposals are drafts, every diff needs human approval one by one, and "fixed" means verified — re-audit shows PRUNE → KEEP plus a runtime test proving the chain's end actually fired.

---

## License

MIT — see [LICENSE](LICENSE).
