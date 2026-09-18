# jn: configuration

Config is TOML, layered: builtin, then `~/.jn`, then every `.jn` from `/` down to the current directory — nearer wins. `jn -h` prints the active layers and every filter/action/tag with its source. Only `~/.jn` may contain Python (`tags_expr`, Python filters); project `.jn` files are data-only (a Python filter in one is ignored).

## Default tags

```toml
# project/.jn — stamped on every entry logged under this dir
tags = ["project=cube-reps", "area=infra"]
```

A builtin `@agent=claude:<id>` (or `agy:<id>`) is stamped when the matching agent env var is set — nothing for a human shell. Precedence, later wins: builtin `@agent` → config `tags` → `~/.jn` `tags_expr` → `$JN_TAGS` → tags in the entry text.

## Filters

A filter is either a **token string** (starts with `@`/`-@`, expands into `ls` args) or a **Python expression** evaluated per entry (True = keep). `--name` on `ls` applies it.

```toml
[filters]
open      = "@todo -@done"                     # token string — allowed in any .jn
default   = "-@done -@archived -@parent"        # override the built-in default filter
overdue   = "tag('todo') is not None and (tag('due') or ['9'])[0] < __import__('datetime').date.today().isoformat()"  # python — ~/.jn only
```

The filter named `default` is applied to every `ls` unless you pass `--all`, an id, or mention one of its tags. So with `-@parent` in `default`, `jn ls` hides subtasks but `jn ls @parent=#50` shows them.

Python namespace: `tag('name')` → value as list (`[]` bare, `None` absent; `tag('name', id)` reads another entry), `default('name')` (tags `log` would stamp now), `env('VAR')`, `cwd`, `F('name')` (another filter), and the raw fields `id created updated content tags`.

## Actions

An action is a list of `jn` command lines with `$1`, `$2`, `$@` substituted. An action using only `$1` runs once per argument (`jn close 1 2 3`).

```toml
[actions]
bug = ["log @todo @bug $@"]        # jn bug "crash on empty input"
wip = ["tag $1 @wip", "show $1"]
```

Built-ins: `todo = ["log @todo $@"]`, `close = ["tag $1 @done", "ls @blocked_by=#$1 --unblocked"]`. Redefining an action in a project `.jn` only affects that journal.

## Environment and misc

- `$JN_TAGS` — extra tags per shell/session, e.g. `export JN_TAGS="@by=claude:claude-code"`.
- `$JN_DB` — path to the journal db (default `~/.jn.db`). `--db=<path>` overrides it for one run, anywhere on the line.
- `tz = "America/New_York"` in any `.jn` — display timezone (stored UTC).
- `tags_expr` (`~/.jn` only) — Python returning a string/list of tags, sees `env()` and `cwd`. Example: stamp the workspace from the path:
  ```toml
  tags_expr = "'@workspace=' + cwd.split('/')[4] if cwd.startswith(env('HOME') + '/code/') else ''"
  ```
