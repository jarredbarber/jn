---
name: jn
description: Microjournal and task log shared by humans and agents. Use at session start to see open tasks, at milestones to log progress, and whenever creating or finishing tasks.
---

# jn

`jn` is a CLI journal. Entries are text plus tags (`@name` or `@name=value`). Lead with tags, then text: `jn log "@re=#42 parser handles nested lists"`. Leading/trailing tags are stripped from the saved text; tags mid-sentence stay as prose.

**Attribution is automatic:** `jn` stamps `@agent=claude:<session-id>` on everything you log, and project tags come from `.jn` files. Don't add `@agent` or `@project` yourself.

## Commands

```bash
jn ls --open                    # open tasks in this project (run at session start)
jn todo "write tests for X"     # -> prints id
jn close 42                     # mark task 42 done; prints anything it unblocked
jn tag 42 @blocked_by+=#7 -@urgent   # patch tags: @k sets, += / -= edit items, -@ drops. unmentioned tags stay
jn tag 42 43 @done              # patch several ids at once
jn log "milestone: parser works, 3 edge cases left @re=#42"
jn show 42                      # tags line, blank, content, "<- #N @tag title" backlinks. no id = last entry
jn edit 42 <<'EOF'              # replaces the WHOLE entry (tags line + content). for tags only use `jn tag`
@todo @re=#7
rewritten text
EOF
```

Multi-line entries via stdin:

```bash
jn log <<'EOF'
Finished auth refactor @re=#42
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
| `@blocked_by=#12` | `#12` is an item of the value's comma list (not substring) |
| `@agent=claude:*` | any of, `*` is a wildcard |
| `pushups` | content contains word |
| `42` | entry id |
| `--open` | named filter from `.jn`; `jn -h` lists them |

Options: `--since today|yesterday|3d|2w|2026-09-01`, `--last N`, `--mine`, `--tree` (nest by `@parent=#N`), `--json` (jsonl), `--md`, `--all`. Done/archived are hidden unless you pass `--all`, an id, or `@done`/`@archived`.

```bash
jn ls @todo -@done @agent=claude:*       # open tasks by any claude agent
jn ls --since yesterday --json           # machine-readable, one entry per line
jn tags                                  # tag -> count: where the work clusters
jn history 42                            # prior versions (tags + content)
```

## Deeper topics

Pull these on demand — they print to stdout:

- `jn --skill todo` — task workflow: projects, `@parent` subtasks, `@blocked_by`, `@due`, collapsing.
- `jn --skill config` — `.jn` files: default tags, custom filters, actions, timezone, per-session tags.
- `jn --skill journal` — journaling workflow for agents: what to write, when, and how to link.

## When to write

- After finishing a task the user asked for: `jn close ID`, then a one-line `jn log` of what changed.
- At a decision point or blocker worth remembering: `jn log`.
- When you spot follow-up work: `jn todo`, one line.
- Don't log routine tool calls. One entry per milestone, not per step.
