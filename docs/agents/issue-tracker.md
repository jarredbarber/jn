# Issue tracker: jn

Issues for this repo live in `jn.jsonl` at the repo root, tracked by `jn` itself (`python3 jn.py --db=jn.jsonl <args>`, or `export JN_DB=$PWD/jn.jsonl` then `jn <args>`). Run `jn --skill` for the full command reference.

## Conventions

- A task is any entry tagged `@todo`. `@done` closes it. Entries without `@todo` are journal notes, not issues.
- Issue number = entry id (`#N`). Refer to issues as `#N` in text; `#N` is a pointer, never a tag.
- Specs and long bodies go in the entry itself (multi-line via stdin). Comments are new entries pointing back with `@parent=#N`; `jn show N` lists them as backlinks.
- Dependencies: `@blocked_by=#N`. Grouping/epics: `@parent=#N` on children (hidden from `jn ls` by default; `jn ls @parent=#N` or `--tree` shows them).
- Triage state is a tag on the entry (see `triage-labels.md`).
- Commit `jn.jsonl` alongside the code change it describes; the file rewrites in full with sorted keys.

## When a skill says "publish to the issue tracker"

```bash
jn todo "title @label ..."          # single line; prints the new id
jn todo <<'EOT'                      # multi-line spec
title line
body...
EOT
```

Prefix a new issue with `@needs-triage` unless it is already fully specified.

## When a skill says "fetch the relevant ticket"

`jn show N`. The user will normally pass `#N` or the number directly. `jn ls @todo` lists open issues; `jn ls @todo --unblocked` lists actionable ones.

## When a skill says "close the ticket"

`jn close N` (stamps `@done`, prints newly unblocked tasks), then `jn log "shipped X (<sha>) @parent=#N"`.

## Wayfinding operations

Used by `/wayfinder`. The **map** is a jn entry; each ticket is a **child** entry.

- **Map**: an entry tagged `@map`, body holds Notes / Decisions-so-far / Fog. Edit with `jn edit N`.
- **Child ticket**: `jn todo "question @parent=#MAP @type=research|prototype|grilling|task"`.
- **Blocking**: `@blocked_by=#N,#M`. Unblocked when every pointee has `@done`.
- **Frontier**: `jn ls @parent=#MAP @todo -@claimed --unblocked`; lowest id wins.
- **Claim**: `jn tag N @claimed` before any work.
- **Resolve**: `jn edit N` appending `## Answer`, `jn close N`, then `jn edit MAP` appending the gist + `#N` to Decisions-so-far.

## PRs as a request surface

Off. Set to on if external PRs should enter the triage queue via `gh pr list`.
