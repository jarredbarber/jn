# jn

Microjournal + task log for humans and agents. One Python file, stdlib only.

```bash
jn todo "do 10 pushups @fitness"        # -> 1
jn close 1
jn log "@re=#1 shipped discovery"
jn log <<'EOF'
# multi-line via stdin
- decided X over Y
EOF
jn ls                                   # everything not @done/@archived (the "default" filter)
jn ls @todo                             # filters: @tag  -@tag  @k=v  @k=a,b  @k=v*  word  ID
jn ls @done --since 1w                  # mentioning a default-filter tag lifts it; --all lifts all
jn ls @blocked_by=#12                   # #12 is an item of the list (not substring)
jn ls @by=jarred,claude:*               # any of
jn ls --open                            # named filter from .jn
jn ls --since 3d --md                   # today | yesterday | 3d | 2w | ISO
jn ls @todo --mine                      # @by = whatever log would stamp right now
jn todo "@blocked_by=#12,#15 ship it"   # blocked until 12 and 15 are @done; `jn close 15` prints what it freed
jn ls @todo --unblocked                 # actionable now
jn ls @todo --tree                      # nest under @parent=#N; --tree=blocked_by works too
jn ls --json | jq ...                   # jsonl: one entry per line
jn ls --all --json | jq -c 'del(.tags.foo)' | jn import   # bulk edit, ids preserved
jn tags                                 # tag -> count over what ls would show; where's the mass
jn tags @home                           # counts within one bucket
jn show                                 # last entry: tags line, blank, content, backlinks
jn tag 1 2 @due=tomorrow -@fitness      # patch tags on each id; nothing else changes
jn edit                                 # document: $EDITOR seeded with show, or stdin; replaces the whole entry
jn history 1                            # every prior version, tags included
jn revert 1                             # back one version (or `jn revert 1 v2`); itself versioned
```

## Install

Python 3.11+, no dependencies.

```bash
uv tool install git+ssh://git@github.com/jarredbarber/jn   # or: pipx install git+ssh://git@github.com/jarredbarber/jn
```

Or skip packaging and symlink the single file:

```bash
ln -s ~/code/jn/jn.py ~/bin/jn          # or wherever is on PATH
```

## Model

- Entry: `id, created, updated, content`.
- Tags: `@name` or `@name=value`. A tag is present or absent; when present its value is a comma list, `@name` alone being the empty list. `#` is never a tag sigil.
- `jn tag N @k=a,b` replaces the list, `@k+=c` appends, `@k-=a` removes items (tag stays, possibly empty), `-@k` drops the tag. Tags you don't mention are untouched. Leading and trailing tags are stripped from the saved text (lead with context: `jn log "@meeting @client=acme agreed on scope"`). Tags mid-sentence stay as prose. One name per entry, last write wins.
- Date words in values resolve when written: `@due=tomorrow`, `@due=2w`, `@due=-3d`, `@due=today`. Stored as ISO, so `@due=tomorrow` still means the same day next week.
- `#42` points at entry 42, in prose or in values: `@parent=#42`, `@re=#42`, `@blocks=#42`. `jn show 42` lists everything pointing at it as `<- #N @tag title` lines (title being the referring entry's first line), which `edit` ignores when piped back. No relationship types are built in.
- `@by` defaults to `$USER`. Agents set `@by=claude:claude-code` etc.
- Two verbs: `tag` is a patch from args, `edit` is a document from stdin or `$EDITOR` and replaces the whole entry, tags line included. `edit` refuses args. `show` output round-trips through `edit`; backlink lines are ignored. Every change keeps the prior version, see `jn history`.
- Timestamps are stored in UTC and shown in local time, or in `tz = "America/New_York"` from config. Tag changes are not versioned.
- No hierarchy. `@project=x @area=y` and filters cover it.

## Tags the code knows about

None. `@by=$USER` is a builtin default tag, and `@todo`, `@done`, `@archived`, `@blocked_by` come from the default actions and filters below. All of it can be redefined in config; `jn -h` shows the effective set.

Any value `#N` is a pointer to entry N. `jn show N` lists them as backlinks whatever the tag name. `@re=#N` for comments and `@parent=#N` for subtasks are conventions only.

## Actions

`jn <name> args` runs a list of `jn` command lines with `$1`, `$2`, and `$@` substituted. An action that only uses `$1` runs once per argument, so `jn close 1 2 3` works. Built in:

```toml
todo  = ["log @todo $@"]
close = ["tag $1 @done", "ls @blocked_by=#$1 --unblocked"]
```

Any `.jn` may add or override them under `[actions]`, so a project can redefine `todo`; the blast radius is your journal. If `log`'s arguments are tags only, the body is read from stdin or `$EDITOR`, so `jn todo <<EOF` works.

## Filters and config

`--name` on `ls` looks up a filter. The one named `default` is applied to every `ls` unless you pass `--all`, an explicit id, or mention one of its tags yourself, so `jn ls @done` just works. A filter is either a token string (starts with `@` or `-@`) that expands into `ls` arguments, or a Python expression evaluated per entry. Built in:

```toml
default   = "-@done -@archived"
mine      = "tag('by') == default('by')"
blocked   = "any(not (i[0] == '#' and i[1:].isdigit() and tag('done', int(i[1:])) is not None) for i in tag('blocked_by') or [])"
unblocked = "not F('blocked')"
```

Config is TOML, layered: builtin, then `~/.jn`, then every `.jn` from `/` down to the current directory, nearer wins. `jn -h` prints the layers in order and every action and filter with its source.

Project `.jn` (data only):

```toml
tags = ["project=cube-reps"]

[filters]
open = "@todo -@done"

[actions]
bug = ["log @todo @bug $@"]
```

`~/.jn` (the only file that may hold Python):

```toml
tags_expr = "'@workspace=' + cwd.split('/')[4] if cwd.startswith(env('HOME') + '/code/') else ''"

[filters]
overdue = "tag('todo') is not None and (tag('due') or ['9'])[0] < __import__('datetime').date.today().isoformat()"
claude  = "(tag('by') or [''])[0].startswith('claude:')"
```

Python namespace:

- `tag('name')` returns the value as a list of items, `[]` for a bare tag, `None` if absent. `tag('name', id)` reads another entry. The `@` is optional.
- `env('VAR')` returns the variable or `None`. The `$` is optional.
- `default('name')` has the same shape, read from the tags `log` would stamp right now (config, `tags_expr`, `$JN_TAGS`, `$USER`). So `tag('project') == default('project')` means "in the project I'm standing in".
- `cwd` is the working directory, `F('name')` evaluates another filter.
- `id created updated content tags` are the raw entry fields, `tags` being `{name: value}`.

`tags_expr` sees `env()` and `cwd` and returns a string or list of tags.

`$JN_TAGS` adds tags per shell or session. `$JN_DB` overrides `~/.jn.db`, and `--db=<path>` overrides it for one run (anywhere on the line, any command). `tz = "UTC"` in any `.jn` sets the display timezone.

## Agents

`skills/jn/SKILL.md` tells an agent when and how to write entries. Symlink it into your tool's skills dir:

```bash
ln -s ~/code/jn/skills/jn ~/.claude/skills/jn
```

## Not included

`rm`, tag rename, date comparison on values, sync. All scriptable via `--json`.
