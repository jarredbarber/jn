# jn: journaling workflow (agents)

The journal is shared by the user and every agent. Your entries are how the user (and the next agent) sees what happened.

## Attribution is automatic

`jn` stamps `@agent=claude:<session-id>` (or `agy:<id>`) on everything you log, derived from your environment. **Don't add `@by` or `@agent` yourself** — it's already there. Project tags come from `.jn` files automatically too.

Filter to your own work with `--mine` (entries stamped the way you'd stamp now):

```bash
jn ls --mine --since today        # what I did today
jn ls @agent=claude:* --all       # anything by a claude agent
```

## At session start

```bash
jn ls --open          # open tasks in this project (or `jn ls @todo`)
jn ls --mine --last 5 # your recent context
```

## What to write, and when

- **Finished a task the user asked for:** `jn close ID`, then a one-line `jn log` of what actually changed.
- **Decision or blocker worth remembering:** `jn log "chose X over Y because … @re=#42"`.
- **Follow-up work you noticed:** `jn todo "…"`, one line. Don't fix it silently and forget it.
- **Don't** log routine tool calls or step-by-step progress. One entry per milestone, not per command.

## Linking

`@re=#ID` comments on or links to another entry; `jn show ID` lists everything pointing at it as backlinks. Use it to thread progress under a task instead of writing disconnected notes:

```bash
jn log "middleware approach worked, tests green @re=#42"
jn show 42            # the task + all its @re / @parent backlinks with titles
```

## Multi-line entries

```bash
jn log <<'EOF'
Finished auth refactor @re=#42
- moved token check to middleware
- open question: refresh-token expiry
EOF
```

Body comes from stdin (or `$EDITOR` if interactive). `jn edit ID` replaces a whole entry; `jn tag ID …` patches tags only. See `jn --skill todo` for task structure and `jn --skill config` for filters/tags.
