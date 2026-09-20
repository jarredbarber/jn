# jn

A local microjournal and task log for people and agents. One Python file, standard library only.

```bash
jn todo "do 10 pushups @fitness"        # prints 1
jn close 1                               # adds @done; prints tasks that became unblocked
jn log "shipped discovery @re=#1"
jn log <<'EOF'
- chose X over Y
EOF

jn ls --all --tree                     # render selected parent/child entries
jn ls @todo --unblocked                  # tasks with no unresolved blockers
jn ls @agent=claude:* --since 3d         # entries by any Claude agent
jn ls @todo --tree                       # nest @parent=#N children
jn show 1                                # editable document plus backlinks
```

## Install

Python 3.11+; no runtime dependencies.

```bash
uv tool install git+ssh://git@github.com/jarredbarber/jn
# or
pipx install git+ssh://git@github.com/jarredbarber/jn
```

For a checkout, put the script on `PATH`:

```bash
ln -s ~/code/jn/jn.py ~/bin/jn
```

## Entries and tags

An entry has an integer `id`, UTC `created` and `updated` timestamps, text content, and tags. Tags have the form `@name` or `@name=value`; values are comma-separated lists. A bare tag has an empty value. `#` is never a tag sigil, so `#42` is ordinary text unless a convention assigns it meaning.

Put tags at the beginning or end of the input. jn stores those tags separately and removes them from the saved body. Tags in the middle of a sentence remain prose.

```bash
jn log "@meeting @client=acme agreed on scope"
jn tag 42 @due=tomorrow @owner=jarred
jn tag 42 @owner+=sam @client-=acme -@meeting
```

Escape a literal `@` with a backslash: `jn log 'Explain \@todo and \@re=#42'` creates neither tag. Keep the backslash in stored text and edit buffers so `show` → `edit` remains safe. In a shell, quote the text so the backslash reaches jn; the web composer accepts `\@` directly.

`@k=value` replaces a tag value; `@k+=value` appends unique items; `@k-=value` removes items and leaves a bare tag when none remain; and `-@k` removes the tag. Unmentioned tags do not change, and the final occurrence of a repeated tag wins.

Date words in tag values resolve when written: `today`, `tomorrow`, `yesterday`, and signed durations such as `3d`, `2w`, or `-3d` become ISO dates. The stored date does not move later.

Every tag value equal to `#N` is a pointer to entry `N`. jn does not reserve relationship types: `@re=#42`, `@parent=#42`, and `@blocks=#42` are conventions. `jn show 42` lists every pointer as a backlink. Its output round-trips through `jn edit`; backlink lines are ignored on input.

`jn tag` patches tags. `jn edit` replaces the complete document, including its first tag line. A changed entry (content or tags) keeps its prior document in history. No-op changes do not add a history version.

```bash
jn edit 42 <<'EOF'
@todo @re=#7

Rewrote the parser.
EOF
jn history 42
jn revert 42             # restores the prior version
jn revert 42 v2          # restores version 2
```

Timestamps are stored in UTC and displayed in the local timezone unless `tz` is set in configuration.

### Automatic tags

The code has no fixed domain tags. `@todo`, `@done`, `@archived`, and `@blocked_by` are conventions used by the default filters and actions. Configuration can replace those filters and actions.

When an agent environment is present, `log` automatically adds `@agent=claude:<session-id>` from `CLAUDE_CODE_SESSION_ID`, or `@agent=agy:<id>` from `ANTIGRAVITY_CONVERSATION_ID`. A human shell gets no `@agent` tag. Project tags from `.jn` are also added automatically. Do not add duplicate `@agent` or project tags in agent entries.

## Commands

| Command | Purpose |
| --- | --- |
| `jn log [@tags] [text]` | Create an entry and print its ID. Tag-only input reads the body from stdin or `$EDITOR`. |
| `jn tag ID... PATCH...` | Patch tags without changing content. |
| `jn edit [ID]` | Replace an entry from stdin or `$EDITOR`; omitted ID means the latest entry. |
| `jn show [ID]` | Print the editable document and its backlinks. |
| `jn history [ID]` | Print prior versions followed by the current version. |
| `jn revert [ID] [N]` | Restore the prior version, or version `N`; the restore is versioned. |
| `jn attach [ID] PATH...` | Copy files into the journal's attachment directory and add `@files`. |
| `jn ls [FILTERS] [OPTIONS]` | Query entries. |
| `jn tags [FILTERS]` | Count tags over the rows `ls` would return. |
| `jn import` | Upsert JSONL rows from stdin, preserving IDs. |
| `jn <action> ...` | Run a configured action such as `todo` or `close`. |
| `jn --skill [PAGE]` | Print installed agent documentation. |
| `jn serve` | Start the local web UI and API. |

`--db=<path-or-name>` works with every command and overrides `JN_DB` for that invocation. A path ending in `.jsonl` or `.json` selects the JSONL journal format.

### Querying

`jn ls` combines all filters with AND:

| Filter | Meaning |
| --- | --- |
| `@todo` | Has a tag. |
| `-@done` | Does not have a tag. |
| `@blocked_by=#12` | The comma list contains exactly `#12`, not a substring. |
| `@agent=claude:*` | Matches any value with the `claude:` prefix. |
| `pushups` | Content contains the word. |
| `42` | Entry ID. |
| `--open` | A named filter from configuration. |

Options: `--since today|yesterday|3d|2w|ISO`, `--last N`, `--mine`, `--tree[=tag]`, `--json`, `--md`, and `--all`.

The built-in `default` filter is `-@done -@archived -@parent`. It applies unless `--all`, an explicit ID, or a query that mentions one of those tags lifts it. Thus `jn ls` shows open top-level work; `jn ls @done` and `jn ls @parent=#50` still work.
```bash
jn ls @todo --mine
jn ls --since yesterday --json
jn ls --all --tree=blocked_by
jn ls --all --json | jq -c 'del(.tags.foo)' | jn import
jn tags @home
```

`--mine` compares `@agent` with the tag a new `log` command would add in the current environment. `--json` emits one JSON object per line. `--md` emits Markdown rows.
### Tasks and blockers



The built-in actions are:

```toml
todo  = ["log @todo $@"]
close = ["tag $1 @done", "ls @blocked_by=#$1 --unblocked"]
```

Actions are lists of `jn` command lines with `$1`, `$2`, and `$@` substituted. An action that references only `$1` runs once for each argument, so `jn close 1 2 3` closes each task.

`@blocked_by=#N` blocks a task until entry `N` has `@done`. A non-pointer item is a manual blocker that you remove yourself.

```bash
jn todo "@blocked_by=#12,#15 deploy"
jn close 15
jn ls @todo --unblocked
jn tag 42 @blocked_by-=vendor
```

Projects and subtasks are conventions. Use a normal entry as the project head and point children at it with `@parent=#N`. `jn ls --all --tree` renders the complete hierarchy. `--tree` only nests rows selected by the query, so filters or the default view can omit a parent or child. Tag-only grouping also works when no head entry is needed.

### Attachments

`jn attach [ID] PATH...` copies files to `<journal>.files/` beside the database, names them with the first 16 hexadecimal characters of the SHA-256 digest plus the lowercased extension, and adds the names to `@files`. Identical content is stored once. Omit the ID to attach to the latest entry.

`@files` is the link. `jn tag 1 @files-=<name>` detaches a file; it does not delete it. Back up the `.files/` directory with the journal. Files are never deleted automatically.

## Configuration

Configuration is layered: built-ins, `~/.jn`, then every `.jn` from filesystem root to the current directory. Nearer files override named settings; `tags` accumulate and `favorites` merge with nearer tags first. `jn -h` prints the active layers plus effective tags, filters, and actions.

Project `.jn` files are data-only. They may add tags, token filters, actions, databases, colors, favorites, and a display timezone. Python expressions are accepted only in `~/.jn`: project expressions are ignored.

```toml
# project/.jn
tags = ["project=cube-reps"]
tz = "America/New_York"
favorites = ["todo", "due"]

[filters]
open = "@todo -@done"

[actions]
bug = ["log @todo @bug $@"]

[dbs]
work = "journal.jsonl"

[colors]
todo = "#FF7A1A"
```

A filter is either a token string beginning with `@`, `-@`, or `--`, which expands into `ls` arguments, or a Python expression evaluated for each entry. Python filters use `tag(name)`, `default(name)`, `env(name)`, `cwd`, `F(name)`, and raw `id`, `created`, `updated`, `content`, and `tags` fields. `tag` returns a list, `[]` for a bare tag, or `None` when absent. `default` returns the tags a new entry would receive.

```toml
# ~/.jn only
tags_expr = "'@workspace=' + cwd.split('/')[4] if cwd.startswith(env('HOME') + '/code/') else ''"

[filters]
overdue = "tag('todo') is not None and (tag('due') or ['9'])[0] < __import__('datetime').date.today().isoformat()"
```

`tags_expr` can return a string or list of tags and can use `env()` and `cwd`. Tag precedence is built-in agent tag, configured `tags`, `tags_expr`, `JN_TAGS`, then tags in the entry text.

`JN_TAGS` adds tags for a shell or session. `JN_DB` sets the database path; `--db` takes precedence for one command. Named databases under `[dbs]` resolve relative paths against the `.jn` that names them. `favorites` orders web tag chips, and `[colors]` sets their colors.

## Agent documentation

`skills/jn/SKILL.md` is the small entry point for agents. It links to detailed pages for task workflow, configuration, and journaling. Install it in a tool's skills directory:

```bash
ln -s ~/code/jn/skills/jn ~/.claude/skills/jn
```

Installed packages include those pages, so `jn --skill`, `jn --skill todo`, `jn --skill config`, and `jn --skill journal` work without a checkout.

## Web UI

```bash
jn serve                     # http://127.0.0.1:8787
jn serve --host 127.0.0.1 --port 9000
```

The browser UI accepts the same query tokens as `ls` and exposes a POST API. The default listener is loopback. It has no authentication; do not bind it to an untrusted network unless another layer protects it.

## Backup and storage

SQLite is the default. `jn ls --all --json` produces a stable, key-sorted JSONL export suitable for version control:

```bash
jn ls --all --json > journal.jsonl
git -C ~/journal add journal.jsonl && git -C ~/journal commit -m "$(date +%F)"

jn import < journal.jsonl
```

`import` upserts only IDs in the stream. It preserves pointers and is idempotent, but it does not delete missing entries or import history. Use it to move current journal state; retain native JSONL files or SQLite backups when history matters.

A database path ending in `.jsonl` or `.json` is a native JSONL journal. Each line holds `id`, `created`, `updated`, `content`, and `tags`, plus `history` when present. Entries are sorted by ID; keys are sorted; writes use an atomic replacement. jn loads a native JSONL journal into in-memory SQLite and rewrites the file after a successful write. The web server reloads it before each request so intervening CLI changes remain visible and survive later web writes. Simultaneous writes from separate processes are not coordinated; use SQLite when writers may overlap. Use JSONL for journals with thousands of entries.

A missing native JSONL file starts as an empty journal; its parent directory must already exist. Two machines that append offline can mint the same next integer ID and produce a Git conflict. Resolve that conflict manually or import one side's export into the other. jn has no merge driver or sync protocol.

## Not included

No `rm`, tag rename, date comparisons on tag values, merge driver, or sync service. JSONL output keeps those workflows scriptable.
