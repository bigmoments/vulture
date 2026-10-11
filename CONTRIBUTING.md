# Contributing to vulture

Thanks for considering a contribution! This is a small, focused skill — a short, accurate addition beats a long, stale one.

## What makes a good contribution

- **New framework patterns** — entry-point or function-definition regexes for frameworks/languages not yet covered, with a fixture proving they work.
- **False-positive / false-negative reports** — a minimal code snippet the scripts misclassify, plus what the correct output should be.
- **Runtime verification methods** — concrete ways to prove a function is truly unused (log queries, analytics exports).
- **Corrections** — outdated patterns, wrong defaults, broken assumptions.
- **Translations** — the skill content is in Bahasa Indonesia; an English `references/` would be a welcome parallel effort (open an issue first so work doesn't duplicate).

## Ground rules

1. **Heuristics stay honest.** Any new detection must document what it *cannot* see. Candidates, never verdicts.
2. **Portable over stack-specific.** Examples may name a stack, but the rule must survive any stack.
3. **Scripts are stdlib-only.** No third-party Python dependencies, ever. Keep them executable (`chmod +x`) and compile-check with `python3 -m py_compile scripts/*.py`.
4. **Prove with a fixture.** New patterns ship with a minimal fixture in the PR description showing before/after output.
5. **REVIEW is sacred.** Don't "fix" ambiguity by auto-classifying it — ambiguous findings belong in REVIEW.
6. **No AI slop.** Write like an engineer, not a brochure.

## How to contribute

1. Fork the repo and create a branch (`fix/...`, `feat/...`).
2. Edit the relevant file (`references/` for knowledge, `scripts/` for detection, `SKILL.md` for workflow changes).
3. Add or extend the fixture check: run all four scripts on a sample and paste the output in the PR.
4. Open a pull request describing **what**, **why**, and **how you verified it**.

## Reporting issues

Open an issue with: what you expected, what happened, and the smallest reproduction (language, framework, code snippet, script output).
