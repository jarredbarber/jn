---
name: jn
description: Microjournal and task log shared by humans and agents. Use at session start to see open tasks, at milestones to log progress, and whenever creating or finishing tasks.
---

# jn

`jn` is a CLI journal. Entries are text plus tags (`@name` or `@name=value`). Project tags come from a `.jn` file automatically, so never add `@project` yourself.

Always tag entries you write with `@by=<agent>:<tool>`, e.g. `@by=claude:claude-code` or `@by=gemini:antigravity`.

## Commands

```bash
jn ls open                      # open tasks in this project (do this at session start)
jn todo "write tests for X @by=claude:claude-code"   # -> prints id
jn done 42                      # mark task 42 finished
jn log "milestone: parser works, 3 edge cases left @by=claude:claude-code @re=42"
jn ls --since today             # what happened today
jn show 42                      # full entry
```

Multi-line entries via stdin:

```bash
jn log <<'EOF'
Finished auth refactor @by=claude:claude-code @re=42
- moved token check to middleware
- open question: refresh token expiry
EOF
```

## Querying

`jn ls` takes any mix of filters, all ANDed:

| filter | meaning |
|---|---|
| `@todo` | has tag |
| `-@done` | lacks tag |
| `@by=claude:*` | tag value glob (`*` wildcard) |
| `pushups` | content contains word |
| `42` | entry id |
| `open` | named query from `.jn` |

Options: `--since today|yesterday|3d|2w|2026-09-01`, `--last N`, `--json`, `--md`.

```bash
jn ls @todo -@done @by=claude:*          # open tasks created by any claude agent
jn ls @re=42                             # everything linking to entry 42
jn ls --since yesterday --json           # machine-readable, tags as {name: value}
jn history 42                            # prior content versions after edits
```

Useful tags: `@todo`/`@done` for tasks, `@re=ID` to link to another entry, `@due=YYYY-MM-DD`, `@blocked`. Invent others freely; tags are just names.

## When to write

- After completing a task the user asked for: `jn done ID`, then a one-line `jn log` of what changed.
- When you hit a decision point or blocker worth remembering: `jn log`.
- When you notice follow-up work: `jn todo`. Keep it one line.
- Don't log routine tool calls. One entry per milestone, not per step.
