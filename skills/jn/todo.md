# jn: task workflow

## Basics

```bash
jn todo "ship the parser"                           # adds @todo, prints id
jn close 42                                         # adds @done, prints tasks it unblocked
jn ls @todo --unblocked                             # actionable now (nothing open blocking them)
```

`@todo`/`@done` are just tags the default `todo`/`close` actions apply. `jn ls` hides `@done` by default (see `jn --skill config` to change the default filter).

## Projects and subtasks

There is no project type — a project is a normal entry with children pointing at it via `@parent=#N`:

```bash
jn log "auth rewrite"                          # -> 50, the project "head"
jn todo "@parent=#50 move token check to middleware"
jn todo "@parent=#50 refresh-token expiry"
```

- `jn ls @parent=#50` — the children of #50.
- `jn show 50` — the head plus its children as `<- #N @parent title` backlinks.
- `jn ls @todo --tree` — nest children under parents visually (`--tree=blocked_by` trees any pointer tag).

To make `jn ls` show only high-level items (project heads + standalone tasks) and hide subtasks, add `-@parent` to the default filter. Mentioning `@parent` in a query lifts the hide, so `jn ls @parent=#50` still works. See `jn --skill config`.

Tag-only grouping (no head entry) also works: tag everything `@auth`, then `jn ls @auth` and `jn tags` for a per-tag rollup. Use a head entry when you want the project itself to be one line in `jn ls`.

## Blocking

```bash
jn todo "@blocked_by=#12,#15 deploy"   # blocked until 12 AND 15 are @done
jn close 15                            # prints what this freed
jn ls @todo --unblocked                # 'deploy' appears once nothing blocks it
```

A `#N` item blocks until entry N is `@done`. A bare word (`@blocked_by=vendor`) is a manual block you clear with `jn tag ID @blocked_by-=vendor`.

## Due dates

```bash
jn tag 42 @due=tomorrow      # date words resolve to ISO when written
jn tag 42 @due=3d            # +3 days; @due=2026-10-01 for an explicit date
jn ls @due=2026-10-01        # filter by the stored ISO value
```

Define an `overdue` filter in `~/.jn` if you want it (see `jn --skill config`).
