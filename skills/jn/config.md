# jn configuration

Configuration is TOML. jn reads built-ins, `~/.jn`, and `.jn` files on the path to the current directory, resolving each named definition from the nearest file. Run `jn -h` to inspect the result.

Project `.jn` files are data-only. Python expressions in them are ignored. Only `~/.jn` may define Python filters or `tags_expr`.

## Tags

Project tags are added to every new entry made below that directory:

```toml
# project/.jn
tags = ["project=cube-reps", "area=infra"]
```

When present, jn first adds the built-in agent tag, then configured `tags`, `tags_expr` from `~/.jn`, `JN_TAGS`, and tags supplied in entry text. Later values for the same name win. The agent tag is `@agent=claude:<id>` or `@agent=agy:<id>`; a human shell gets none.

## Filters

A filter is either a token string that starts with `@`, `-@`, or `--`, or a Python expression that runs once per entry. Pass a filter as `--name` to `ls`.

```toml
[filters]
open    = "@todo -@done"                       # token filter; any .jn
default = "-@done -@archived -@parent"         # replaces the built-in default

# ~/.jn only
overdue = "tag('todo') is not None and (tag('due') or ['9'])[0] < __import__('datetime').date.today().isoformat()"
```

The `default` filter runs for every `ls` command unless the query uses `--all`, an explicit ID, or one of the tags hidden by that filter. For example, adding `-@parent` hides subtasks from `jn ls`, while `jn ls @parent=#50` still shows them.

Python filters can use:

- `tag('name')`: value list; `[]` for a bare tag and `None` if absent. `tag('name', id)` reads another entry.
- `default('name')`: tag list that a new entry would receive in this environment.
- `env('VAR')`: environment value or `None`.
- `cwd`: current working directory.
- `F('name')`: evaluate another filter.
- `id`, `created`, `updated`, `content`, and `tags`: raw entry fields.

The `@` in `tag()` and `$` in `env()` are optional.

## Actions

An action is a list of jn command lines. `$1`, `$2`, and `$@` expand to action arguments. When an action references only `$1`, it runs once for each supplied argument.

```toml
[actions]
bug = ["log @todo @bug $@"]
wip = ["tag $1 @wip", "show $1"]
```

The built-in actions are:

```toml
todo  = ["log @todo $@"]
close = ["tag $1 @done", "ls @blocked_by=#$1 --unblocked"]
```

An action in a project `.jn` changes behavior for the journal selected in that project.

## Environment and display settings

- `JN_TAGS`: extra tags for the current shell or session, for example `export JN_TAGS="@by=claude:claude-code"`.
- `JN_DB`: journal path. `--db=<path-or-name>` overrides it for one command.
- `tz = "America/New_York"`: display timezone. jn stores timestamps in UTC.
- `tags_expr`: Python in `~/.jn` that returns a string or list of tags; it can use `env()` and `cwd`.

```toml
# ~/.jn
tags_expr = "'@workspace=' + cwd.split('/')[4] if cwd.startswith(env('HOME') + '/code/') else ''"

[dbs]
work = "~/work.jn.db"
notes = "~/notes/journal.db"
```

Named databases can be declared in any `.jn`; relative paths resolve from the file that declares them. `favorites = ["todo", "due"]` pins tags at the top of the web tag list. `[colors]` maps tag names to chip colors, for example `todo = "#FF7A1A"`.
