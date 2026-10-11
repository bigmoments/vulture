# Changelog

All notable changes to this skill are documented here. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Added
- "Cara pakai" / "Usage" section in `SKILL.md` and `README.md`: how to invoke via chat (primary) + manual script commands (optional).

### Changed
- Renamed skill from `feature-audit` to `vulture` (persona-style name, ala `ponytail`): mode burung bangkai — melayang di atas codebase, mencium bangkai fungsi dari kejauhan, menukik tepat sasaran. Fungsionalitas tidak berubah.

## [1.0.0] - 2026-10-11

### Added
- Initial release.
- `SKILL.md`: 5-phase workflow (inventory → relations → usefulness → classification → report), KEEP/MERGE/PRUNE/REVIEW taxonomy, Output Contract, Operating Rules, explicit honesty principle (heuristics find candidates, never verdicts).
- Four knowledge modules under `references/`: inventory (entry-point patterns per framework/language), relations (relationship mapping + heuristic limits), usefulness (three usefulness questions + runtime checks), classification-report (criteria, report format, execution priority).
- Four stdlib-only Python scripts under `scripts/`: `entry_points.py` (Express/Hono, Flask/FastAPI, Laravel, Django, Spring, Go, Rails, Click/argparse/Commander, cron, exports, package.json bin), `call_graph.py` (regex def/call graph + body hashes for duplicates), `dead_code.py` (unreachable-from-entry candidates with high/medium/low confidence), `audit_report.py` (Markdown report: summary, feature map, classification tables, priorities, limitations).
- `examples/sample-report.md` + `examples/sample-output.json`.
- Professional repo files: README (English), LICENSE (MIT), CONTRIBUTING, CHANGELOG, .gitignore.

### Notes
- Skill content is written in Bahasa Indonesia; README/CONTRIBUTING in English.
- Pure Markdown + Python stdlib scripts. Compatible with Claude Code, Cursor, Codex, Antigravity, Gemini CLI.
- Verified end-to-end on a synthetic 3-language fixture (JS + PHP + Python): 6 entry points, 20 functions, dead code (high/medium) and duplicates all detected correctly.

### Known limitations
- Callback references (`arr.map(fn)` without invocation parens) are not tracked as calls — documented in `references/relations.md`.
- Dynamic dispatch (reflection, magic methods, DI containers), cross-language frontend→API links, and cross-repo usage require manual verification (REVIEW category).
