---
name: jn
description: Shared microjournal and task log for humans and agents.
---

# jn

`jn` stores text entries with tags. Write tags as `@name` or `@name=value`; values are comma-separated lists. Put tags at the beginning or end of an entry; jn stores those as metadata. A tag-shaped word mid-sentence stays prose.

```bash
jn log "@parent=#42 parser handles nested lists"
```

For a literal tag-shaped word, write `\@name` (for example, `jn log 'Discuss \@todo'`). The backslash stays in the entry so later edits do not turn the word into a tag. Quote shell input to preserve it.

Agent attribution is automatic. `log` adds `@agent=claude:<session-id>` or `@agent=agy:<id>` when the matching environment variable exists, and `~/.jn` may add project tags. Do not add duplicate `@agent` or project tags yourself.

## Start here

At the beginning of a session, inspect the project's open work:

```bash
jn ls --open
jn ls --mine --last 5
```

`--open` is a named filter from `~/.jn`. If it is not defined, use `jn ls --tasks`.

## Common commands

```bash
jn todo "write tests for parser"             # create @todo task; prints ID
jn close 42                                   # add @done; prints newly unblocked tasks
jn log "parser shipped @parent=#42"          # record a completed milestone
jn tag 42 @blocked_by+=#7 -@urgent            # patch tags only
jn tag 42 43 @done                            # patch several entries
jn show 42                                    # editable document plus backlinks
jn history 42                                 # prior versions and current version
```

Use `jn edit` when replacing the whole entry. Its input includes the tag line and body; use `jn tag` for a tag-only change.

```bash
jn edit 42 <<'EOF'
@todo @parent=#7

Rewrote the parser.
EOF
```

Multi-line logs read from stdin:

```bash
jn log <<'EOF'
Finished auth refactor @parent=#42
- moved the token check to middleware
- left refresh-token expiry open
EOF
```

## Querying

`jn ls` combines every filter with AND:

| Filter | Meaning |
| --- | --- |
| `@todo` | Has a tag. |
| `-@done` | Does not have a tag. |
| `@blocked_by=#12` | The tag list contains `#12`. |
| `@agent=claude:*` | Any Claude agent entry. |
| `pushups` | Content contains the word. |
| `42` | Entry ID. |
| `--open` | Named filter from `~/.jn`. |

Options include `--since today|yesterday|3d|2w|2026-09-01`, `--last N`, `--mine`, `--tree`, `--json`, `--md`, and `--all`.

```bash
jn ls @todo -@done @agent=claude:*
jn ls --since yesterday --json
jn ls @todo --unblocked
jn tags
```

By default, `ls` hides `@done`, `@archived`, and `@parent`. Mentioning one of those tags, passing an entry ID, or using `--all` lifts that default filter.

## When to write

- After completing a user-requested task: close its entry, then log one line describing the change.
- At a durable decision or blocker: log the decision and link it with `@parent=#ID` when relevant.
- When you find follow-up work: create one `todo` entry.
- Do not log routine tool calls or step-by-step progress. One entry per milestone.

## More detail

Print pages only when needed:

- `jn --skill todo`: projects, subtasks, blockers, and due dates.
- `jn --skill config`: `~/.jn`, filters, actions, timezones, and session tags.
- `jn --skill journal`: attribution, milestones, and linking.
