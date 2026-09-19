# Context: jn

Glossary for `jn`, a microjournal + task log shared by humans and agents. Terms only — no implementation. See `README.md` for behavior, `jn.py` for code.

## Entry

The only record type. Fields: `id`, `created`, `updated`, `content`, and its tags. Everything else — a task, a journal note, a comment — is an Entry wearing tags, not a distinct type. There is no `Task`, `Note`, or `Comment` type.

## Tag

A named marker on an Entry, `@name` or `@name=value`. A tag is **present or absent**; when present its value is a comma-separated list, and bare `@name` is the *empty list* (present-but-empty is distinct from absent). One tag per name per Entry, last write wins. No tag names are built into the schema — even `@todo`/`@done` are convention, defined by actions and filters.

## Tag value

The list carried by a present tag. `@k=a,b` is the two-item list; a query `@k=a,b` matches if *any* listed item is present (any-of). Date words in a value (`tomorrow`, `2w`) resolve to ISO **when written**, then stay fixed.

## Pointer

`#N` — a reference to Entry N, whether in prose or inside a tag value (`@parent=#42`). `#` is *never* a tag sigil; `#42` is a pointer, `# Heading` is prose. No relationship types exist: `@parent`, `@re`, `@blocked_by` are naming conventions, not schema.

## Backlink

The reverse view of a Pointer: `jn show N` lists every Entry whose tag value points at N. Derived, not stored; ignored when piped back through `edit`.

## Agent

A non-human actor (an AI session) writing entries. Distinguished from a human only by the `@agent` tag, which is stamped **automatically from the environment** (`claude:<session>`, `agy:<conversation>`) — never absent in a human shell, never set by hand. "Mine" = entries whose `@agent` matches what a write would stamp right now.

## Action

A named shortcut expanding to one or more `jn` command lines with `$1`/`$@` substitution (`todo`, `close`). Redefinable per-project. An Action is a macro over the same verbs, not new behavior.

## Filter

A named row predicate for `ls`/`tags`. Two kinds: a **token string** (`@tag -@tag`, data-only, safe in any `.jn`) or a **Python expression** (only ever from `~/.jn` — a project `.jn`'s Python-shaped filter is ignored, the security boundary).

## Default filter

The Filter named `default` (`-@done -@archived`), applied to every `ls` unless you pass `--all`, an explicit id, or mention one of its tags yourself. The reason `jn ls` hides done/archived without asking.

## Version

A prior state of an Entry's document (content + tags), kept on every `edit`/`revert`. `tag` patches are **not** versioned. `history` shows the chain; `revert` restores one (and is itself versioned).
