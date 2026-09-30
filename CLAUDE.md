# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

`jn` is a microjournal + task log for humans and agents. Core is `jn.py`; `jn serve` (web UI) lives in `jn_web.py` + `jn_web.html` and only imports the core. See `README.md` for the full user-facing model, tag syntax, filters, and config; this file is only what isn't in there.

## Philosophy / Project Tenets

The main goal is to be **maximally generic** and avoid prescribing behavior as much as possible

- The data model is simple: Journal entries with kv-style tags and cross-refs (`#42`)
- Behavior is "emergent": New use cases or custom data organization enabled via creative uses of the tags. 
- Minimize "special" tags. 

## Special tags

The current special tags are:

**DB**: None
**Default Config**: `@archived`, `@todo`, `@done`, `@parent`, `@blocked_by`, `@agent` (auto-stamped via `builtin_tags()`, used by `--mine`)
**CLI** (hardcoded in `jn.py`): `@files` (`attach`), `@parent` (`show` nests children, `ls` prints a `↳ #N` context line on rows whose parent isn't shown; `--tree` defaults to it, but any pointer tag works).
**Web UI** (`jn_web.html`/`jn_web.py`): `@todo` (shows the Mark done button), `@done` (struck-through, done toggle), `@files` (attachment embeds, hidden from tag chips), `@parent` (Reply button, ancestor thread above an expanded entry)

Adding a tag to these lists needs a reason. Prefer a config filter or action.

## Commands

```bash
python3 test_jn.py        # the whole test suite (one file, asserts, no framework)
python3 jn.py <args>       # run without installing
uv tool install .          # or: pipx install .  — installs `jn` + skills/ (for `jn --skill`)

JN_DB=/tmp/jn-demo.db jn import < fixture.jsonl   # canonical demo db: 32 entries covering the feature surface
```

There is no build step, linter, or CI. `test_jn.py` is a single script of asserts against a subprocess in a temp dir; add cases there.

## Dogfood log — `jn.jsonl`

This repo tracks its own tasks and change log in `jn.jsonl` (committed). Use it — jn is its own tracker.

```bash
export JN_DB=$PWD/jn.jsonl          # or: python3 jn.py --db=jn.jsonl <args>
python3 jn.py log "shipped X (<sha>)"        # a change note — stays in the journal
python3 jn.py todo "fix Y"                    # a task
python3 jn.py ls @todo                        # open tasks
python3 jn.py close 4                          # complete task #4 (stamps @done)
```

- Log one note per milestone (same beat as a commit); open a `@todo` for follow-ups and `close` it when done.
- `log` notes are journal, not tasks — don't tag them `@done`; the default filter hides `@done`, so a note tagged that way vanishes from `ls`.
- The file rewrites in full on each write with sorted keys, so diffs stay clean — commit it alongside the code change it describes.

## Architecture

`jn.py` is the whole program (~570 lines). Entry point is `cli()` (in `[project.scripts]`), which calls `main(argv)`.

- **Storage:** SQLite at `~/.jn.db` (`$JN_DB` / `--db=` override). Portable form is jsonl via `--json` / `import` (upsert by id, idempotent — that's the sync/backup layer, git holds the file). A db path ending in `.jsonl`/`.json` is loaded into an in-memory SQLite (`JsonlConn`) and the whole file is rewritten on every commit (leaving `with db() as c`), so all write paths go through that `with`. The web server discards JSONL snapshots before each request to preserve intervening CLI writes; simultaneous writers remain uncoordinated.
- **Config** (`config()`): builtin defaults, then `~/.jn` only. TOML. Holds `tags`, `tags_expr`, `[actions]`, `[filters]`, `[dbs]`, `[colors]`, `favorites`, `tz`.
- **Security boundary — do not weaken:** filters and `tags_expr` can be Python expressions, so **`~/.jn` is the only file jn reads** — no project-local config exists. A `.jn` in a repo or cwd is never opened, so an untrusted repo can't execute code. `test_jn.py` locks this (the `evil`/`@evil` cases) — keep those green. Anything new that can run code (hooks) must also come from `~/.jn` only.
- **Writes** (`stage`/`save`): every write path (`add_entry`, `edit`, `tag`, `revert`, `import`, web) goes through one function that runs the `on_write` hook from `~/.jn.py`, enforces one `@parent`, and stores with history. Add new write paths there, not as ad-hoc INSERTs. The hook file is code: `~/.jn.py` only.
- **Actions** (`run_action`): an action is a list of `jn` command-lines with `$1`/`$@` substitution; single-`$1` actions loop over args. `todo`/`close` are builtins, overridable in `~/.jn`.
- **Tags** (`parse_tags`/`strip_tags`): `@name` or `@name=comma,list`; leading/trailing tags are stripped from saved text, mid-sentence ones stay prose. `#N` is an entry pointer, never a tag. `@agent` is auto-stamped from `$CLAUDE_CODE_SESSION_ID` / `$ANTIGRAVITY_CONVERSATION_ID` — nothing in a human shell.
- **Versioning** (`versioned`): `edit`/`revert` keep prior versions (`history`); `tag` patches are *not* versioned.

The `skills/jn/` dir ships beside `jn.py` (see `[tool.hatch.build.targets.wheel]`) so `jn --skill <page>` works after install.

## Agent skills

### Issue tracker

Issues are `@todo` entries in `jn.jsonl`, managed with `jn` itself (`#N` = issue id, `@done` closes). See `docs/agents/issue-tracker.md`.

### Triage labels

Default five roles, each a bare jn tag of the same name (`@needs-triage`, `@ready-for-agent`, ...). See `docs/agents/triage-labels.md`.

After triage, add `@triaged` to the issue. Put only findings, decisions, or open questions in triage comments; agent attribution comes from `@agent`, not prose boilerplate.

### Domain docs

Single-context: `CONTEXT.md` at the root plus `docs/adr/`. See `docs/agents/domain.md`.
