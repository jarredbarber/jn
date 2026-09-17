---
name: jn
description: Microjournal and task log shared by humans and agents. Use at session start to see open tasks, at milestones to log progress, and whenever creating or finishing tasks.
---

# jn

`jn` is a CLI journal. Entries are text plus tags (`@name` or `@name=value`). Lead with tags, then the text: `jn log "@by=claude:claude-code @re=#42 parser handles nested lists"`. Leading and trailing tags are stripped from the saved text. Project tags come from a `.jn` file automatically, so never add `@project` yourself.

Always tag entries you write with `@by=<agent>:<tool>`, e.g. `@by=claude:claude-code` or `@by=gemini:antigravity`.

## Commands

```bash
jn ls open                      # open tasks in this project (do this at session start)
jn todo "write tests for X @by=claude:claude-code"   # -> prints id
jn close 42                      # mark task 42 finished
jn log "milestone: parser works, 3 edge cases left @by=claude:claude-code @re=#42"
jn ls --since today             # what happened today
jn show 42                      # full entry (tags line, blank line, content). no id = last entry
jn edit 42 <<'EOF'              # replaces the WHOLE entry, tags included; to change tags only use `jn tag`
@todo @by=claude:claude-code @re=#7
rewritten text
EOF
```

Multi-line entries via stdin:

```bash
jn log <<'EOF'
Finished auth refactor @by=claude:claude-code @re=#42
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
| `@blocked_by=#12` | `#12` is an item of the value's comma list |
| `@by=jarred,claude:*` | any of, `*` is a wildcard |
| `pushups` | content contains word |
| `42` | entry id |
| `open` | named query from `.jn` |

Options: `--since today|yesterday|3d|2w|2026-09-01`, `--last N`, `--mine`, `--blocked`, `--unblocked`, `--json`, `--md`.

```bash
jn ls @todo -@done @by=claude:*          # open tasks created by any claude agent
jn ls @re=#42                            # replies to entry 42 (or just `jn show 42`)
jn ls --since yesterday --json           # machine-readable, tags as {name: value}
jn history 42                            # prior versions (tags + content), e.g. when it was marked done
```

Useful tags: `@todo`/`@done` for tasks, `@re=#ID` to comment on / link to another entry (`jn show ID` lists backlinks), `@parent=#ID` for subtasks, `@due=tomorrow` / `@due=3d` / `@due=2026-10-01` (date words resolve to ISO when written), `@blocked_by=#12,#15` (any non-done item keeps it blocked; a bare word like `vendor` is a manual block). `jn ls @todo --unblocked` lists actionable tasks, `jn close N` prints what it freed. Invent others freely; tags are just names.

## When to write

- After completing a task the user asked for: `jn close ID`, then a one-line `jn log` of what changed.
- When you hit a decision point or blocker worth remembering: `jn log`.
- When you notice follow-up work: `jn todo`. Keep it one line.
- Don't log routine tool calls. One entry per milestone, not per step.
