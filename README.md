# jn

Microjournal + task log for humans and agents. One Python file, stdlib only, sqlite underneath.

```bash
jn todo "do 10 pushups @fitness"        # -> 1
jn done 1
jn log "shipped discovery @re=1"
jn log <<'EOF'
# multi-line via stdin
- decided X over Y
EOF
jn ls @todo -@done                      # filters: @tag  -@tag  @k=v*  word  ID
jn ls open                              # named query from .jn
jn ls --since 3d --md                   # today | yesterday | 3d | 2w | ISO
jn ls --json | jq ...
jn edit 1                               # $EDITOR seeded with old content
jn history 1                            # every prior content version
```

## Install

Python 3.11+.

```bash
ln -s ~/code/jn/jn.py ~/bin/jn          # or wherever is on PATH
alias kk=jn                             # optional
```

## Model

- Entry: `id, created, updated, content`.
- Tags: `@name` or `@name=value`, `#` works too. Parsed from the text, kept in the text. One name per entry, last write wins.
- `@by` defaults to `$USER`. Agents set `@by=claude:claude-code` etc.
- `edit` keeps prior content in a `history` table. Tag changes are not versioned.
- No hierarchy. `@project=x @area=y` and filters cover it.

## Config

Both files are TOML and optional.

`./.jn` (found by walking up from cwd, nearest wins):

```toml
tags = ["project=cube-reps"]

[queries]
open = "@todo -@done"
```

`~/.jn` (global, also the only file allowed to run code):

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

`rm` (use `sqlite3 ~/.jn.db`), tag rename, date comparison on values, sync. All scriptable via `--json`.
