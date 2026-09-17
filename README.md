# jn

Microjournal + task log for humans and agents. One Python file, stdlib only.

```bash
jn todo "do 10 pushups @fitness"        # -> 1
jn close 1
jn log "shipped discovery @re=1"
jn log <<'EOF'
# multi-line via stdin
- decided X over Y
EOF
jn ls @todo -@done                      # filters: @tag  -@tag  @k=v  @k=a,b  @k=v*  word  ID
jn ls @blocked_by=#12                   # #12 is an item of the list (not substring)
jn ls @by=jarred,claude:*               # any of
jn ls open                              # named query from .jn
jn ls --since 3d --md                   # today | yesterday | 3d | 2w | ISO
jn ls @todo --mine                      # @by = whatever log would stamp right now
jn todo "@blocked_by=#12,#15 ship it"   # blocked until 12 and 15 are @done; `jn close 15` prints what it freed
jn ls @todo --unblocked                 # actionable now
jn ls --json | jq ...
jn show                                 # last entry: tags line, blank, content
jn edit                                 # $EDITOR seeded with show output; replaces whole entry
jn history 1                            # every prior version, tags included
```

## Install

Python 3.11+.

```bash
ln -s ~/code/jn/jn.py ~/bin/jn          # or wherever is on PATH
```

## Model

- Entry: `id, created, updated, content`.
- Tags: `@name` or `@name=value`. A value is a comma list: `@blocked_by=#12,#15`. `#` is never a tag sigil. Leading and trailing tags are stripped from the saved text (lead with context: `jn log "@meeting @client=acme agreed on scope"`). Tags mid-sentence stay as prose. One name per entry, last write wins.
- Date words in values resolve when written: `@due=tomorrow`, `@due=2w`, `@due=-3d`, `@due=today`. Stored as ISO, so `@due=tomorrow` still means the same day next week.
- `#42` points at entry 42, in prose or in values: `@parent=#42`, `@re=#42`, `@blocks=#42`. `jn show 42` lists everything pointing at it (on stderr, so stdout still round-trips into `edit`). No relationship types are built in.
- `@by` defaults to `$USER`. Agents set `@by=claude:claude-code` etc.
- `show` output round-trips through `edit`. `edit` replaces tags and content; use `tag` to change tags alone. Every change to tags or content keeps the prior version, see `jn history`. Tag changes are not versioned.
- No hierarchy. `@project=x @area=y` and filters cover it.

## Tags the code knows about

Everything else is convention. These four have behavior:

| tag | set by | read by |
|---|---|---|
| `@by=<who>` | every `log`/`todo`, default `$USER`, override via config, `tags_cmd`, `$JN_TAGS`, or text | `--mine` filter |
| `@todo` | `jn todo` | removed by `close` |
| `@done` | `jn close` | `@blocked_by` resolution |
| `@blocked_by=#12,#15,vendor` | you | `--blocked` / `--unblocked` filters, `close` prints what it freed. Non-`#N` items block until edited out |

Any value `#N` is a pointer to entry N. `jn show N` lists them as backlinks whatever the tag name. `@re=#N` for comments and `@parent=#N` for subtasks are conventions only.

## Filters

`--name` on `ls` runs a Python expression against each entry. Built in:

```toml
mine      = "tags.get('by') == me"
blocked   = "any(i and not (i[0] == '#' and i[1:].isdigit() and 'done' in E.get(int(i[1:]), {})) for i in (tags.get('blocked_by') or '').split(','))"
unblocked = "not F('blocked')"
```

Add your own under `[filters]` in `~/.jn` (same names override). Namespace: `id created updated content tags`, `me` (the `@by` that `log` would stamp now), `E` (every entry's tags by id), `F(name)` (another filter).

```toml
[filters]
overdue = "'todo' in tags and (tags.get('due') or '9') < __import__('datetime').date.today().isoformat()"
```

## Config

Both files are TOML and optional.

`./.jn` (found by walking up from cwd, nearest wins):

```toml
tags = ["project=cube-reps"]

[queries]
open = "@todo -@done"
```

`~/.jn` (global, and the only file allowed to hold code: `tags_cmd`, `[filters]`):

```toml
tags = []
tags_cmd = 'case "$PWD" in ~/code/*) echo "@workspace=${PWD#$HOME/code/}" | cut -d/ -f1;; esac'
```

`$JN_TAGS` adds tags per shell/session. `$JN_DB` overrides `~/.jn.db`.

## Agents

`skills/jn/SKILL.md` tells an agent when and how to write entries. Symlink it into your tool's skills dir:

```bash
ln -s ~/code/jn/skills/jn ~/.claude/skills/jn
```

## Not included

`rm`, tag rename, date comparison on values, sync. All scriptable via `--json`.
