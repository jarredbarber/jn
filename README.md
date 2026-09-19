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
jn ls @agent=claude:*                   # any of, * is a wildcard
jn ls --open                            # named filter from .jn
jn ls --since 3d --md                   # today | yesterday | 3d | 2w | ISO
jn ls @todo --mine                      # @agent = whatever log would stamp right now
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
jn attach 1 shot.png notes.pdf          # copy files in beside the journal, listed under @files
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
- `@agent` is stamped automatically from the environment: `claude:$CLAUDE_CODE_SESSION_ID` or `agy:$ANTIGRAVITY_CONVERSATION_ID`, nothing in a human shell. Agents don't set it themselves.
- Two verbs: `tag` is a patch from args, `edit` is a document from stdin or `$EDITOR` and replaces the whole entry, tags line included. `edit` refuses args. `show` output round-trips through `edit`; backlink lines are ignored. Every change keeps the prior version, see `jn history`.
- Timestamps are stored in UTC and shown in local time, or in `tz = "America/New_York"` from config. Tag changes are not versioned.
- No hierarchy. `@project=x @area=y` and filters cover it.

### Attachments

`jn attach [ID] path...` copies files into `<journal>.files/` beside the db (`~/.jn.db` → `~/.jn.files/`), named by content (first 16 hex of sha256 + extension, so the same file is stored once), and appends the names to the entry's `@files` tag. That tag is the whole link: `jn tag 1 @files-=<name>` detaches, `jn show` lists them, and a jsonl export carries the names, so back up the `.files/` dir alongside it. Files are never deleted.

## Tags the code knows about

None. `@agent` is a builtin default stamped from the environment (see Model), and `@todo`, `@done`, `@archived`, `@blocked_by` come from the default actions and filters below. All of it can be redefined in config; `jn -h` shows the effective set.

Any value `#N` is a pointer to entry N. `jn show N` lists them as backlinks whatever the tag name. `@re=#N` for comments and `@parent=#N` for subtasks are conventions only.

## Actions

`jn <name> args` runs a list of `jn` command lines with `$1`, `$2`, and `$@` substituted. An action that only uses `$1` runs once per argument, so `jn close 1 2 3` works. Built in:

```toml
todo  = ["log @todo $@"]
close = ["tag $1 @done", "ls @blocked_by=#$1 --unblocked"]
```

Any `.jn` may add or override them under `[actions]`, so a project can redefine `todo`; the blast radius is your journal. If `log`'s arguments are tags only, the body is read from stdin or `$EDITOR`, so `jn todo <<EOF` works.

## Filters and config

`--name` on `ls` looks up a filter. The one named `default` is applied to every `ls` unless you pass `--all`, an explicit id, or mention one of its tags yourself, so `jn ls @done` just works. A filter is either a token string (starts with `@`, `-@`, or `--`) that expands into `ls` arguments, opts and other `--names` included (`week = "@todo --since 1w --mine"`), or a Python expression evaluated per entry. Built in:

```toml
default   = "-@done -@archived"
mine      = "tag('agent') == default('agent')"
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
claude  = "(tag('agent') or [''])[0].startswith('claude:')"
```

Python namespace:

- `tag('name')` returns the value as a list of items, `[]` for a bare tag, `None` if absent. `tag('name', id)` reads another entry. The `@` is optional.
- `env('VAR')` returns the variable or `None`. The `$` is optional.
- `default('name')` has the same shape, read from the tags `log` would stamp right now (config, `tags_expr`, `$JN_TAGS`, `$USER`). So `tag('project') == default('project')` means "in the project I'm standing in".
- `cwd` is the working directory, `F('name')` evaluates another filter.
- `id created updated content tags` are the raw entry fields, `tags` being `{name: value}`.

`tags_expr` sees `env()` and `cwd` and returns a string or list of tags.

`$JN_TAGS` adds tags per shell or session. `$JN_DB` overrides `~/.jn.db`, and `--db=<path>` overrides it for one run (anywhere on the line, any command). Name journals under `[dbs]` in any `.jn` and `--db=<name>` resolves them; `jn -h` lists them. `tz = "UTC"` in any `.jn` sets the display timezone.

```toml
[dbs]
work = "~/work.jn.db"
notes = "~/notes/journal.db"
```

`favorites = ["todo", "due"]` pins tags to the top of the web tag column, and `[colors]` (`todo = "#FF7A1A"`) tints their chips; both are data, so a project `.jn` may set them, layered like `[dbs]` with the nearer file first. `jn -h` lists both.

## Agents

`skills/jn/SKILL.md` tells an agent when and how to write entries. Symlink it into your tool's skills dir:

```bash
ln -s ~/code/jn/skills/jn ~/.claude/skills/jn
```

The skill is split for progressive discovery: `SKILL.md` (CLI + querying) points to deeper pages an agent pulls on demand via `jn --skill <page>` (`config`, `todo`, `journal`; no arg prints the overview). The pages ship with the package, so `jn --skill` works after `uv tool install` too.

## Web

```bash
jn serve                     # http://127.0.0.1:8787, --host/--port to change
```

Capture box on top (**Add**, or ⌘↩), filter box (same tokens as `ls`, mirrored in the URL as `?q=`, so a view is a link), named-filter chips, day-grouped list, and a tag column on the right (under the filter on a phone): every tag in view with its count, `favorites` from config first with a ● and always shown, `[colors]` tinting their chips; click one to add it to the filter. Tap an entry and it opens in place: its tag chips are the tag editor (click one to edit it, ✕ drops it, type in the trailing field to add; the `@` is optional there and completion still pops), the text below is the content (the box grows with it), and `#N` anywhere is a link to that entry. Clicking anywhere outside closes it. Clicking `jn` returns to the default view. Installable as a PWA from the phone. A dropdown in the masthead switches between `[dbs]` journals (names only, never paths). The **tree** chip nests entries under their `@parent=#N` like `ls --tree` (no day breaks in that mode); **Add subtask** in an entry seeds the composer with `@parent=#N @todo`. Typing `@` pops known tag names, `=` their known values. **+ save view** writes the filter box as a token filter under `[filters]` in `~/.jn`, so it is a `--name` in the CLI too; the ✕ on such a chip removes it (only token strings are ever written, never Python). **Attach** in an open entry (or paste/drop files onto its text) uploads to the same `.files/` dir; images show as thumbnails below the content, other files as links, ✕ detaches. Files are served at `/files/<name>` (`?db=` picks a `[dbs]` journal). `POST /api/<verb>` with a JSON body (`ls tags show log tag edit attach config vocab filter dbs`, plus an optional `db` name on any of them) calls the library directly, so config and filters apply as in the shell it was started from; `close` is `tag @done`, and `[actions]` are CLI-only. **No auth.** Keep it on loopback and front it with Cloudflare Zero Trust / Tailscale if you want it from a phone. Entries logged from the web carry whatever `@agent` the server's shell would stamp, so start it from a human shell.

## Backup and sync

The db is SQLite, but the portable form is jsonl. `--json` sorts keys, so a dump is stable and diffs cleanly in git:

```bash
jn ls --all --json > journal.jsonl && git -C ~/journal commit -am "$(date +%F)"
```

Restore or move machines by piping it back — `import` upserts by id, so pointers survive and re-imports are idempotent:

```bash
jn import < journal.jsonl                 # whole file
jn ls --since 3d --all --json | jn import  # or just a slice
```

git is the sync layer: dump/commit/push on one machine, pull/`import` on another. `import` only touches the ids in the stream; it never deletes.

### Storage formats

A db path ending in `.jsonl` (or `.json`) *is* the journal: one entry per line, sorted by id, keys sorted, trailing newline, so it lives in git and diffs cleanly. Anything else is SQLite as before. Point at one with `$JN_DB`, `--db=journal.jsonl`, or a `[dbs]` name:

```toml
[dbs]
proj = "journal.jsonl"        # relative paths resolve against the .jn that names them
```

Each line is the `ls --all --json` shape (`id created updated content tags`) plus an optional `history` list of `{at, content}` (prior versions, as `jn history` shows them). A missing file is an empty journal, created on the first write; the parent directory must exist. Under the hood jn loads the file into an in-memory SQLite per process and rewrites the whole file atomically after every write, so it's fine for thousands of entries, not millions. `jn import` into a jsonl db works, and `ls --json` output is unchanged (no `history` key).

Ids are plain integers, so two machines appending offline will both mint the same next id and git will show a conflict on that line. Resolve it by hand or `import` one side's dump into the other; that is the accepted ceiling, there is no merge driver.

**From beads** (github.com/steveyegge/beads, the `bd` tracker for agents): taken: the JSONL file is the thing you commit, one record per line, in a stable order with stable key order so diffs are per-entry, and SQLite is a disposable per-machine cache rebuilt from the file. Rejected: the `.beads/` directory with a gitignored `.db` beside the JSONL and a debounced two-way sync between them (jn has no cache to drift, it reloads per run and rewrites per commit); hash ids (`bd-a1b2`) to dodge merge collisions (integers keep `#N` pointers readable, collisions are rare and `import` handles them); the git merge driver, daemon, and Dolt backend.

## Not included

`rm`, tag rename, date comparison on values, sync. All scriptable via `--json`.
