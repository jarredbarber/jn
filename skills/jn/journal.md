# jn journaling for agents

The journal gives people and future agents a durable handoff without a transcript, so a few specific notes matter more than a step-by-step activity log.

## Attribution

`jn log` adds `@agent=claude:<session-id>` or `@agent=agy:<id>` from the current environment. `.jn` configuration can add project tags. Do not add `@agent`, `@by`, or duplicate project tags yourself.

```bash
jn ls --mine --since today        # entries this environment would create
jn ls @agent=claude:* --all       # all Claude entries, including done work
```

## Session start

Read project work before acting:

```bash
jn ls --open
jn ls --mine --last 5
```

If `--open` is unavailable, use `jn ls @todo -@done`.

## What to record

- Completed user work: close its task, then log one concise result linked with `@re=#ID`.
- A decision or blocker that changes later work: state the decision and its reason.
- Newly discovered follow-up work: create a one-line `todo` entry.

Do not log ordinary tool calls, partial progress, or every command. One milestone creates one journal entry.

```bash
jn log "used middleware because it centralizes token checks @re=#42"
jn todo "measure refresh-token expiry behavior @re=#42"
```

## Links and full entries

A tag value of `#ID` creates a backlink. `@re=#ID` is the convention for a progress note; `@parent=#ID` makes a subtask. `jn show ID` prints those backlinks below the editable document.

```bash
jn log <<'EOF'
Finished auth refactor @re=#42
- moved token checks to middleware
- left refresh-token expiry open
EOF
```

Body text comes from stdin, or `$EDITOR` in an interactive shell. `jn edit ID` replaces an entire entry, including its tag line. `jn tag ID ...` changes tags without replacing the body. See `jn --skill todo` for task structure and `jn --skill config` for project settings.
