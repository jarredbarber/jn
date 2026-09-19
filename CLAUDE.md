# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

`jn` is a microjournal + task log for humans and agents. **Stdlib only, no dependencies.** Core is `jn.py`; `jn serve` (web UI) lives in `jn_web.py` + `jn_web.html` and only imports the core. See `README.md` for the full user-facing model, tag syntax, filters, and config; this file is only what isn't in there.

## Commands

```bash
python3 test_jn.py        # the whole test suite (one file, asserts, no framework)
python3 jn.py <args>       # run without installing
uv tool install .          # or: pipx install .  — installs `jn` + skills/ (for `jn --skill`)

JN_DB=/tmp/jn-demo.db jn import < fixture.jsonl   # canonical demo db: 32 entries covering the feature surface
```

There is no build step, linter, or CI. `test_jn.py` is a single script of asserts against a subprocess in a temp dir; add cases there.

## Architecture

`jn.py` is the whole program (~450 lines). Entry point is `cli()` (in `[project.scripts]`), which calls `main(argv)`.

- **Storage:** SQLite at `~/.jn.db` (`$JN_DB` / `--db=` override). Portable form is jsonl via `--json` / `import` (upsert by id, idempotent — that's the sync/backup layer, git holds the file).
- **Config layering** (`config()`): builtin defaults → `~/.jn` → every `.jn` from `/` down to cwd, nearer wins. TOML. Holds `tags`, `[actions]`, `[filters]`.
- **Security boundary — do not weaken:** filters and `tags_expr` can be Python expressions, but **only `~/.jn` may contain Python.** A project `.jn` found by walking up from cwd is data-only; its Python-shaped filters/`tags_expr` are ignored so an untrusted repo's `.jn` can't execute code. `test_jn.py` locks this (the `evil`/`@evil` cases) — keep those green.
- **Actions** (`run_action`): an action is a list of `jn` command-lines with `$1`/`$@` substitution; single-`$1` actions loop over args. `todo`/`close` are builtins, overridable in any `.jn`.
- **Tags** (`parse_tags`/`strip_tags`): `@name` or `@name=comma,list`; leading/trailing tags are stripped from saved text, mid-sentence ones stay prose. `#N` is an entry pointer, never a tag. `@agent` is auto-stamped from `$CLAUDE_CODE_SESSION_ID` / `$ANTIGRAVITY_CONVERSATION_ID` — nothing in a human shell.
- **Versioning** (`versioned`): `edit`/`revert` keep prior versions (`history`); `tag` patches are *not* versioned.

The `skills/jn/` dir ships beside `jn.py` (see `[tool.hatch.build.targets.wheel]`) so `jn --skill <page>` works after install.
