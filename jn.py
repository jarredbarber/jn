#!/usr/bin/env python3
"""jn: microjournal + tasks for humans and agents. See README.md.

  jn log [@tags] [text]      add entry; tags-only args -> body from stdin or $EDITOR. prints id
  jn tag ID @a -@b @k+=x     patch tags: @k=v sets, -@k drops, @k+=x / @k-=x edit list items; nothing else changes
  jn edit [ID]               replace the whole entry with the document from stdin or $EDITOR (seeded with show)
  jn show [ID]               tags line, blank, content, then "<- #N @tag" backlinks. pipeable into edit
  jn history [ID]            prior versions, then current
  jn revert [ID] [N]         restore version N from history (default: the one before current). versioned itself
  jn ls [filters] [opts]     filters: @tag -@tag @k=v @k=a,b @k=v* word ID --name
                             opts: --since today|yesterday|3d|2w|ISO  --last N  --json  --md  --all
                                   --tree[=parent]  nest rows under the entry their @parent=#N (any pointer tag) names
  jn tags [filters]          tag -> count over the same rows ls would show; see where the mass is
  jn <action> ...            todo, close, ... (see below)
"""
import functools, getpass, json, os, re, shlex, shutil, sqlite3, subprocess, sys, tempfile, tomllib, zoneinfo
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

DB = Path(os.environ.get("JN_DB", Path.home() / ".jn.db"))
# @ must follow start/whitespace, so emails are not tags. # is never a sigil: "#42" is a pointer, "# Heading" is prose
TAG = re.compile(r"(?:^|(?<=\s))(-?)@([A-Za-z_]\w*(?:-\w+)*)(?:([+-]?=)(\S+))?")
TOK = r"-?@[A-Za-z_]\w*(?:-\w+)*(?:[+-]?=\S+)?"
LEAD, TRAIL = re.compile(rf"^(?:{TOK}(?:\s+|$))+"), re.compile(rf"(?:(?:^|\s+){TOK})+$")
BACKLINK = re.compile(r"^<- #\d+ @\S+.*$", re.M)
COLS = ("id", "created", "updated", "content")
TAGS = ["by=" + getpass.getuser()]  # builtin default tags; config/tags_expr/$JN_TAGS/text override
ACTIONS = {  # name -> jn command lines. $1.. and $@ substitute the action's args. override/extend in [actions]
    "todo": ["log @todo $@"],
    "close": ["tag $1 @done -@todo", "ls @blocked_by=#$1 --unblocked"],
}
FILTERS = {  # ponytail: eval'd python per row (or @token strings). override/extend in [filters] of .jn files
    "default": "-@done -@archived",
    "mine": "tag('by') == default('by')",
    "blocked": "any(not (i[0] == '#' and i[1:].isdigit() and tag('done', int(i[1:])) is not None) for i in tag('blocked_by') or [])",
    "unblocked": "not F('blocked')",
}


@functools.cache
def db():
    c = sqlite3.connect(DB)
    c.executescript("""
    CREATE TABLE IF NOT EXISTS entry(id INTEGER PRIMARY KEY, created TEXT NOT NULL, updated TEXT NOT NULL, content TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS tagged(entry INTEGER NOT NULL REFERENCES entry(id) ON DELETE CASCADE, name TEXT NOT NULL, value TEXT, UNIQUE(entry, name));
    CREATE INDEX IF NOT EXISTS tagged_name ON tagged(name);
    CREATE TABLE IF NOT EXISTS history(entry INTEGER NOT NULL REFERENCES entry(id) ON DELETE CASCADE, at TEXT NOT NULL, content TEXT NOT NULL);""")
    c.execute("PRAGMA foreign_keys=ON")
    return c


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def local(ts):
    """stored UTC (or legacy naive local) -> configured tz / local time, 'YYYY-MM-DD HH:MM'"""
    tz = zoneinfo.ZoneInfo(config()["tz"]) if config().get("tz") else None
    return datetime.fromisoformat(ts).astimezone(tz).strftime("%Y-%m-%d %H:%M")


def is_tokens(expr):
    return expr.lstrip("-").startswith("@")


@functools.cache
def config():
    """builtin, ~/.jn, then root/.jn ... ./.jn; nearer wins. Only ~/.jn may hold code (python filters, tags_expr)."""
    cfg = {"tags": list(TAGS), "filters": dict(FILTERS), "actions": dict(ACTIONS), "files": ["builtin"],
           "src": {n: "builtin" for n in [*FILTERS, *ACTIONS]}}
    home = (Path.home() / ".jn").resolve()
    for f in dict.fromkeys(p.resolve() for p in [home, *(p / ".jn" for p in reversed([Path.cwd(), *Path.cwd().parents]))]):
        if f.is_file():
            c = tomllib.loads(f.read_text())
            cfg["files"].append(str(f))
            cfg["tags"] += c.get("tags", [])
            if "tz" in c:
                cfg["tz"] = c["tz"]
            for n, cmds in c.get("actions", {}).items():
                cfg["actions"][n], cfg["src"][n] = [cmds] if isinstance(cmds, str) else list(cmds), str(f)
            for n, expr in c.get("filters", {}).items():
                if f == home or is_tokens(expr):
                    cfg["filters"][n], cfg["src"][n] = expr, str(f)
            if f == home and "tags_expr" in c:
                extra = eval(c["tags_expr"], {"env": envf, "cwd": os.getcwd()})
                cfg["tags"] += extra.split() if isinstance(extra, str) else list(extra)
    return cfg


def parse_tags(text, current=None):
    """-> (add: {name: value|None}, rm: {name}). A value is a comma list; bare @name is the empty list.
    += / -= edit the list in `current` (the entry's tags); without `current`, += acts as = and -= is ignored."""
    add, rm = {}, set()
    for neg, name, op, val in TAG.findall(text):
        if neg:
            rm.add(name); continue
        val = ",".join(dateword(i) for i in val.split(",")) if val else None
        if op in ("+=", "-=") and current is not None:
            if name not in add and name not in current:
                if op == "-=": continue
            else:
                have = [i for i in ((add if name in add else current)[name] or "").split(",") if i]
                new = val.split(",")
                items = have + [i for i in new if i not in have] if op == "+=" else [i for i in have if i not in new]
                val = ",".join(items) or None
        elif op == "-=":
            continue
        add[name] = val
    return add, rm


def strip_tags(text):
    """drop leading/trailing tag runs and show's backlink lines; tags mid-sentence stay as prose"""
    return TRAIL.sub("", LEAD.sub("", BACKLINK.sub("", text).strip())).strip()


def read_body(seed=""):
    if not sys.stdin.isatty():
        return sys.stdin.read()
    with tempfile.NamedTemporaryFile("w+", suffix=".md") as f:
        f.write(seed); f.flush()
        subprocess.run([*os.environ.get("EDITOR", "vi").split(), f.name])
        return Path(f.name).read_text()


def run_action(cmds, args):
    for cmd in cmds:
        argv = []
        for t in shlex.split(cmd):
            argv += args if t == "$@" else [re.sub(r"\$(\d+)", lambda m: args[int(m[1]) - 1], t)]
        main(argv)


def default_tags():
    """builtin -> config -> tags_expr -> $JN_TAGS, later wins"""
    return parse_tags(" ".join(["@" + t.lstrip("@") for t in config()["tags"]] + [os.environ.get("JN_TAGS", "")]))[0]


def add_entry(args):
    text = " ".join(args)
    if not strip_tags(text):  # tags only: body from stdin or $EDITOR
        text = (text + "\n" + read_body()).strip()
    tags = default_tags() | parse_tags(text)[0]
    content = strip_tags(text) or sys.exit("empty entry")
    with db() as c:
        eid = c.execute("INSERT INTO entry(created,updated,content) VALUES(?,?,?)", (now(), now(), content)).lastrowid
        c.executemany("INSERT INTO tagged VALUES(?,?,?)", [(eid, k, v) for k, v in tags.items()])
    return eid


def entry_text(eid, c=None):
    """tags line, blank, content. edit seeds with this and accepts it back"""
    c = c or db()
    row = c.execute("SELECT content FROM entry WHERE id=?", (eid,)).fetchone() or sys.exit(f"no entry {eid}")
    return f"{fmt_tags(dict(c.execute('SELECT name,value FROM tagged WHERE entry=?', (eid,))))}\n\n{row[0]}\n"


def backlinks(eid):
    rows = db().execute("SELECT t.entry, t.name, e.content FROM tagged t JOIN entry e ON e.id=t.entry WHERE t.value=? ORDER BY t.entry", (f"#{eid}",)).fetchall()
    return "".join(f"<- #{e} @{n}  {c.splitlines()[0][:60]}\n" for e, n, c in rows)


def versioned(c, eid, write):
    """run write(); every change to tags or content keeps the old version in history"""
    before = entry_text(eid, c)
    write()
    if entry_text(eid, c) != before:
        c.execute("INSERT INTO history SELECT id, updated, ? FROM entry WHERE id=?", (before, eid))
        c.execute("UPDATE entry SET updated=? WHERE id=?", (now(), eid))


def tag(eid, args):
    """patch: @k sets, -@k drops, += / -= edit items. Content untouched"""
    with db() as c:
        add, rm = parse_tags(" ".join(args), dict(c.execute("SELECT name,value FROM tagged WHERE entry=?", (eid,))))
        versioned(c, eid, lambda: (
            c.executemany("INSERT OR REPLACE INTO tagged VALUES(?,?,?)", [(eid, k, v) for k, v in add.items()]),
            c.executemany("DELETE FROM tagged WHERE entry=? AND name=?", [(eid, n) for n in rm])))


def edit(eid, text=None):
    """document: the buffer (stdin or $EDITOR) is the whole entry, tags line included. show output round-trips"""
    text = read_body(entry_text(eid)) if text is None else text
    tags, content = parse_tags(text)[0], strip_tags(text) or sys.exit("empty entry")
    with db() as c:
        versioned(c, eid, lambda: (
            c.execute("UPDATE entry SET content=? WHERE id=?", (content, eid)),
            c.execute("DELETE FROM tagged WHERE entry=?", (eid,)),
            c.executemany("INSERT INTO tagged VALUES(?,?,?)", [(eid, k, v) for k, v in tags.items()])))


def revert(eid, n=None):
    versions = [r[0] for r in db().execute("SELECT content FROM history WHERE entry=? ORDER BY rowid", (eid,))]
    if not versions:
        sys.exit(f"no history for {eid}")
    edit(eid, versions[(n or len(versions)) - 1] if 0 < (n or 1) <= len(versions) else sys.exit(f"versions: 1..{len(versions)}"))


def last():
    return (db().execute("SELECT max(id) FROM entry").fetchone()[0]) or sys.exit("no entries")


def history(eid):
    c = db()
    old = c.execute("SELECT at, content FROM history WHERE entry=? ORDER BY rowid", (eid,)).fetchall()
    cur = (c.execute("SELECT updated FROM entry WHERE id=?", (eid,)).fetchone() or sys.exit(f"no entry {eid}"))[0]
    for n, (at, text) in enumerate([*old, (cur, entry_text(eid, c))], 1):
        print(f"## {eid} v{n} · {local(at)}\n\n{text}")


def envf(k):
    return os.environ.get(k.lstrip("$"))


def aslist(tags, name):
    """tag value as a list of items: [] for a bare tag, None if absent"""
    name = name.lstrip("@")
    return ([i for i in tags[name].split(",") if i] if tags[name] else []) if name in tags else None


def apply_filters(rows, names):
    filters, defaults = config()["filters"], default_tags()
    E = {}
    for eid, n, v in db().execute("SELECT entry,name,value FROM tagged"):
        E.setdefault(eid, {})[n] = v

    def ok(r, name):
        expr = filters.get(name) or sys.exit(f"unknown filter --{name}")
        ns = dict(r, tag=lambda n, eid=None: aslist(r["tags"] if eid is None else E.get(eid, {}), n),
                  default=lambda n: aslist(defaults, n), env=envf, cwd=os.getcwd(), F=lambda n: ok(r, n))
        return bool(eval(expr, ns))
    return [r for r in rows if all(ok(r, n) for n in names)]


def resolve_filters(names):
    """split requested --names into ls tokens (for @... filters) and python filter names"""
    filters, tokens, py = config()["filters"], [], []
    for n in names:
        expr = filters.get(n) or sys.exit(f"unknown filter --{n}")
        (tokens.extend(expr.split()) if is_tokens(expr) else py.append(n))
    return tokens, py


def dateword(s, future=True):
    """today|tomorrow|yesterday|[+-]N[hdw] -> ISO; anything else passes through. bare N is future for tag values, past for --since"""
    words = {"today": 0, "tomorrow": 1, "yesterday": -1}
    if s in words:
        return (date.today() + timedelta(days=words[s])).isoformat()
    if m := re.fullmatch(r"([+-]?)(\d+)([hdw])", s):
        n = int(m[2]) * (-1 if m[1] == "-" or (not m[1] and not future) else 1)
        delta = timedelta(**{{"h": "hours", "d": "days", "w": "weeks"}[m[3]]: n})
        return (datetime.now() + delta).isoformat(timespec="seconds") if m[3] == "h" else (date.today() + delta).isoformat()
    return s


def to_utc(s):
    """local date or datetime string -> stored UTC form, for comparing against created"""
    return datetime.fromisoformat(s).astimezone(timezone.utc).isoformat(timespec="seconds")


def query(tokens, since_=None):
    add, rm = parse_tags(" ".join(t for t in tokens if TAG.fullmatch(t)))
    where, params = [], []
    for k, v in add.items():  # value is a comma list; @k=a,b matches if any of a,b is an item of k
        alts = v.split(",") if v else []
        where.append("id IN (SELECT entry FROM tagged WHERE name=?" + (" AND (" + " OR ".join(["','||value||',' LIKE ?"] * len(alts)) + "))" if alts else ")"))
        params += [k] + [f"%,{a.replace('*', '%')},%" for a in alts]
    for k in rm:
        where.append("id NOT IN (SELECT entry FROM tagged WHERE name=?)"); params.append(k)
    for w in (t for t in tokens if not TAG.fullmatch(t)):
        if w.isdigit():
            where.append("id=?"); params.append(int(w))
        else:
            where.append("content LIKE ?"); params.append(f"%{w}%")
    if since_:
        where.append("created>=?"); params.append(to_utc(dateword(since_, future=False)))
    sql = "SELECT id,created,updated,content FROM entry" + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY id"
    c = db()
    rows = [dict(zip(COLS, r)) for r in c.execute(sql, params)]
    for r in rows:  # ponytail: N+1 tag fetch, join+group if ls ever feels slow
        r["tags"] = dict(c.execute("SELECT name,value FROM tagged WHERE entry=?", (r["id"],)))
    return rows


def fmt_tags(t):
    return " ".join(f"@{k}" + (f"={v}" if v else "") for k, v in sorted(t.items()))


def as_tree(rows, by):
    """order rows as a forest by pointer tag `by` (@parent=#N); yields (row, depth). Rows whose parent isn't listed are roots"""
    ids = {r["id"] for r in rows}
    kids, seen = {}, set()
    for r in rows:
        ptrs = [int(i[1:]) for i in aslist(r["tags"], by) or [] if i[1:].isdigit()]
        kids.setdefault(next((p for p in ptrs if p in ids), None), []).append(r)

    def walk(parent, depth):
        for r in kids.get(parent, []):
            if r["id"] not in seen:
                seen.add(r["id"])
                yield r, depth
                yield from walk(r["id"], depth + 1)
    yield from walk(None, 0)


def show(rows, fmt, tree=None):
    depth = {}
    if tree:
        ordered = list(as_tree(rows, tree))
        rows, depth = [r for r, _ in ordered], {r["id"]: d for r, d in ordered}
    if fmt == "json":
        print(json.dumps(rows, indent=1))
    elif fmt == "md":
        for r in rows:
            print(f"## {r['id']} · {local(r['created'])}\n{fmt_tags(r['tags'])}\n\n{r['content']}\n")
    elif rows:
        common = dict(set.intersection(*(set(r["tags"].items()) for r in rows)))  # shown once in the header
        own = [fmt_tags({k: v for k, v in r["tags"].items() if k not in common}) for r in rows]
        width = shutil.get_terminal_size().columns
        tagw = min(max(4, *map(len, own)), max(20, width // 3))
        textw = max(20, width - 5 - 2 - 11 - 2 - tagw - 2)
        cut = lambda t, w: t if len(t) <= w else t[:w - 1] + "…"
        print(f"{'id':>5}  {'when':<11}  {'text':<{textw}}  tags" + (f"  (all: {fmt_tags(common)})" if common else ""))
        for r, t in zip(rows, own):
            lines = r["content"].splitlines() or [""]
            head = "  " * depth.get(r["id"], 0) + lines[0] + (" …" if len(lines) > 1 else "")
            print(f"{r['id']:>5}  {local(r['created'])[5:]}  {cut(head, textw):<{textw}}  {cut(t, tagw)}")


def main(argv):
    cmd, *args = argv or ["help"]
    opts, pos, it = {}, [], iter(args)
    for a in it:
        if a.startswith("--"):
            k, _, v = a[2:].partition("=")
            opts[k] = v or (next(it, True) if k in ("since", "last") else True)
        else:
            pos.append(a)
    if cmd == "log":
        print(add_entry(pos))
    elif cmd == "tag":
        tag(int(pos[0]), pos[1:])
    elif cmd in ("edit", "show", "history", "revert"):
        eid = int(pos.pop(0)) if pos and pos[0].isdigit() else last()
        if cmd == "edit":
            edit(eid) if not pos else sys.exit("edit takes the whole entry from stdin or $EDITOR; use `jn tag` for one-liners")
        elif cmd == "revert":
            revert(eid, int(pos[0].lstrip("v")) if pos else None)
        elif cmd == "history":
            history(eid)
        else:
            print(entry_text(eid) + backlinks(eid), end="")
    elif cmd in ("ls", "tags"):
        tokens, py = resolve_filters([k for k in opts if k not in ("since", "last", "json", "md", "all", "tree")])
        if "all" not in opts and not any(t.isdigit() for t in pos):
            mentioned = {m[1] for m in TAG.findall(" ".join(pos + tokens))}
            tokens += [t for t in config()["filters"]["default"].split() if TAG.fullmatch(t)[2] not in mentioned]
        rows = apply_filters(query(pos + tokens, opts.get("since")), py)
        if "last" in opts:
            rows = rows[-int(opts["last"]):]
        if cmd == "tags":
            for name, n in Counter(t for r in rows for t in r["tags"]).most_common():
                print(f"{n:>5}  @{name}")
        else:
            tree = opts.get("tree")
            show(rows, "json" if "json" in opts else "md" if "md" in opts else "", "parent" if tree is True else tree)
    elif cmd in (actions := config()["actions"]):
        run_action(actions[cmd], args)
    else:
        cfg = config()
        print(__doc__ + "\nconfig: " + ", ".join(cfg["files"]) + "\ntags: " + fmt_tags(default_tags()) + "\nactions:")
        for n, v in cfg["actions"].items():
            print(f"  {n:<14} {' ; '.join(v)}   # {cfg['src'][n]}")
        print("filters:")
        for n, v in cfg["filters"].items():
            print(f"  --{n:<12} {v}   # {cfg['src'][n]}")


if __name__ == "__main__":
    main(sys.argv[1:])
