# jn task workflow

The built-in actions cover the normal path; the sections below cover the exceptions.

## Create and close tasks

```bash
jn todo "ship the parser"             # creates @todo and prints the entry ID
jn close 42                            # adds @done and prints newly unblocked tasks
jn ls @todo --unblocked                # tasks with no unresolved blockers
```

`@todo` and `@done` are ordinary tags applied by the default `todo` and `close` actions. The built-in `default` filter hides done tasks, archived entries, and subtasks. See `jn --skill config` to change those defaults.

## Projects and subtasks

A project is a normal entry. Give its children `@parent=#N`:

```bash
jn log "auth rewrite"                         # prints 50: project head
jn todo "@parent=#50 move token check"
jn todo "@parent=#50 set refresh-token expiry"
```

- `jn ls @parent=#50` lists the children of entry 50.
- `jn show 50` prints the project and its `@parent` backlinks.
- `jn ls --all --tree` renders a complete parent/child hierarchy.
- `jn ls --all --tree=blocked_by` can tree any pointer tag.
The default filter includes `-@parent`, so `jn ls` shows project heads and standalone tasks. `--tree` only nests rows selected by the query; use `--all` when a tree needs both the parent and its children. A query that names `@parent` lifts that hide, but it returns only entries carrying that tag. Tag-only grouping also works: apply `@auth` to related entries and query `jn ls @auth`. Use a project head only when the project itself should appear as an entry.

## Blockers

```bash
jn todo "@blocked_by=#12,#15 deploy"
jn close 15
jn ls @todo --unblocked
```

Each `#N` item blocks until entry `N` has `@done`; every listed blocker must be resolved. A non-pointer item is a manual blocker. Clear it explicitly:

```bash
jn tag 42 @blocked_by-=vendor
```

`jn close N` prints tasks that become unblocked because `N` was closed.

## Due dates

```bash
jn tag 42 @due=tomorrow
jn tag 42 @due=3d
jn tag 42 @due=2026-10-01
jn ls @due=2026-10-01
```

Date words resolve to ISO dates when written. They do not move on later days. Define an `overdue` filter in `~/.jn` when needed; `jn --skill config` includes an example.
