#!/usr/bin/env python3
"""jn: microjournal + tasks for humans and agents. Single file, stdlib only (py3.11+).

  jn log [text...]           add entry; no text -> stdin (if piped) or $EDITOR. prints id
  jn todo [text...]          same, plus @todo
  jn done ID                 @done -@todo
  jn tag ID @a -@b @k=v      add/remove tags
  jn show [ID]               tags line + blank + content; round-trips through edit. backlinks on stderr. default: last
  jn edit [ID] [text...]     replace the WHOLE entry (tags + content) from text/stdin/$EDITOR seeded with show
  jn history [ID]            prior versions (tags + content, oldest first), then current
  jn ls [filters] [opts]     filters: @tag  -@tag  @k=v*  word  ID  <query-name>
                             opts: --since today|yesterday|3d|2w|ISO  --last N  --mine  --json  --md
                             --mine = @by=<what log would assign now: config, tags_cmd, $JN_TAGS, else $USER>

tags: @name, optional =value. Leading/trailing tags are stripped from content.
  Values today|tomorrow|yesterday|[+-]N[hdw] become ISO dates at write time (@due=tomorrow, @due=2w).
  #42 points at entry 42: use it in prose or values (@parent=#42, @re=#42); show lists what points here. Defaults come from ~/.jn and nearest ./.jn (TOML:
  tags = ["project=x"]  [queries] open = "@todo -@done") plus $JN_TAGS. @by defaults to $USER.
  ~/.jn only: tags_cmd = "shell snippet" whose stdout is extra tags (e.g. derive @workspace from $PWD).
db: $JN_DB or ~/.jn.db
"""
import getpass, json, os, re, sqlite3, subprocess, sys, tempfile, tomllib
from datetime import date, datetime, timedelta
from pathlib import Path

DB = Path(os.environ.get("JN_DB", Path.home() / ".jn.db"))
# sigil must follow start/whitespace and touch a word char, so "# Heading" is not a tag
# @ must follow start/whitespace, so emails are not tags. # is never a sigil: "#42" is a pointer, "# Heading" is prose
TAG = re.compile(r"(?:^|(?<=\s))(-?)@([A-Za-z_][\w-]*)(?:=(\S+))?")
TOK = r"-?@[A-Za-z_][\w-]*(?:=\S+)?"
LEAD, TRAIL = re.compile(rf"^(?:{TOK}(?:\s+|$))+"), re.compile(rf"(?:(?:^|\s+){TOK})+$")
COLS = ("id", "created", "updated", "content")


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
    return datetime.now().isoformat(timespec="seconds")


def config():
    """~/.jn, then root/.jn ... ./.jn; nearer wins."""
    cfg = {"tags": [], "queries": {}}
    for f in [Path.home() / ".jn", *(p / ".jn" for p in reversed([Path.cwd(), *Path.cwd().parents]))]:
        if f.is_file():
            c = tomllib.loads(f.read_text())
            cfg["tags"] += c.get("tags", [])
            cfg["queries"].update(c.get("queries", {}))
            if f.parent == Path.home() and "tags_cmd" in c:  # only ~/.jn may run code; project .jn is data
                cfg["tags"] += subprocess.run(c["tags_cmd"], shell=True, capture_output=True, text=True).stdout.split()
    return cfg


def parse_tags(text):
    add, rm = {}, set()
    for neg, name, val in TAG.findall(text):
        (rm.add if neg else lambda n: add.__setitem__(n, dateword(val) if val else None))(name)
    return add, rm


def strip_tags(text):
    """drop leading/trailing tag runs; tags mid-sentence stay as prose"""
    return TRAIL.sub("", LEAD.sub("", text)).strip()


def get_text(args, seed=""):
    if args:
        return " ".join(args)
    if not sys.stdin.isatty():
        return sys.stdin.read().strip()
    with tempfile.NamedTemporaryFile("w+", suffix=".md") as f:
        f.write(seed); f.flush()
        subprocess.run([*os.environ.get("EDITOR", "vi").split(), f.name])
        return Path(f.name).read_text().strip()


def default_tags():
    """config -> tags_cmd -> $JN_TAGS -> @by=$USER, later wins"""
    tags, _ = parse_tags(" ".join(["@" + t.lstrip("@") for t in config()["tags"]] + [os.environ.get("JN_TAGS", "")]))
    tags.setdefault("by", getpass.getuser())
    return tags


def add_entry(text, extra=""):
    if not text:
        sys.exit("empty entry")
    tags = default_tags() | parse_tags(extra + " " + text)[0]
    content = strip_tags(text) or sys.exit("empty entry")
    with db() as c:
        eid = c.execute("INSERT INTO entry(created,updated,content) VALUES(?,?,?)", (now(), now(), content)).lastrowid
        c.executemany("INSERT INTO tagged VALUES(?,?,?)", [(eid, k, v) for k, v in tags.items()])
    return eid


def versioned(c, eid, write):
    """run write(); if the entry text changed, keep the old version in history and bump updated"""
    before = entry_text(eid, c)
    write()
    if entry_text(eid, c) != before:
        c.execute("INSERT INTO history SELECT id, updated, ? FROM entry WHERE id=?", (before, eid))
        c.execute("UPDATE entry SET updated=? WHERE id=?", (now(), eid))


def retag(eid, text):
    add, rm = parse_tags(text)
    with db() as c:
        versioned(c, eid, lambda: (
            c.executemany("INSERT OR REPLACE INTO tagged VALUES(?,?,?)", [(eid, k, v) for k, v in add.items()]),
            c.executemany("DELETE FROM tagged WHERE entry=? AND name=?", [(eid, n) for n in rm])))


def entry_text(eid, c=None):
    """what `show` prints and `edit` seeds; parse_tags + strip_tags recover the entry exactly"""
    c = c or db()
    row = c.execute("SELECT content FROM entry WHERE id=?", (eid,)).fetchone() or sys.exit(f"no entry {eid}")
    return f"{fmt_tags(dict(c.execute('SELECT name,value FROM tagged WHERE entry=?', (eid,))))}\n\n{row[0]}\n"


def backlinks(eid):
    rows = db().execute("SELECT entry, name FROM tagged WHERE value=? ORDER BY entry", (f"#{eid}",)).fetchall()
    return "".join(f"← #{e} @{n}\n" for e, n in rows)


def edit(eid, args):
    new = get_text(args, entry_text(eid))
    tags, content = parse_tags(new)[0], strip_tags(new) or sys.exit("empty entry")
    with db() as c:
        versioned(c, eid, lambda: (
            c.execute("UPDATE entry SET content=? WHERE id=?", (content, eid)),
            c.execute("DELETE FROM tagged WHERE entry=?", (eid,)),
            c.executemany("INSERT INTO tagged VALUES(?,?,?)", [(eid, k, v) for k, v in tags.items()])))


def last():
    return (db().execute("SELECT max(id) FROM entry").fetchone()[0]) or sys.exit("no entries")


def history(eid):
    c = db()
    old = c.execute("SELECT at, content FROM history WHERE entry=? ORDER BY rowid", (eid,)).fetchall()
    cur = (c.execute("SELECT updated FROM entry WHERE id=?", (eid,)).fetchone() or sys.exit(f"no entry {eid}"))[0]
    for n, (at, text) in enumerate([*old, (cur, entry_text(eid, c))], 1):
        print(f"## {eid} v{n} · {at}\n\n{text}")


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


def query(tokens, since_=None):
    queries = config()["queries"]
    tokens = [t for tok in tokens for t in queries.get(tok, tok).split()]
    add, rm = parse_tags(" ".join(t for t in tokens if TAG.fullmatch(t)))
    where, params = [], []
    for k, v in add.items():
        where.append("id IN (SELECT entry FROM tagged WHERE name=?" + (" AND value LIKE ?)" if v else ")"))
        params += [k, v.replace("*", "%")] if v else [k]
    for k in rm:
        where.append("id NOT IN (SELECT entry FROM tagged WHERE name=?)"); params.append(k)
    for w in (t for t in tokens if not TAG.fullmatch(t)):
        if w.isdigit():
            where.append("id=?"); params.append(int(w))
        else:
            where.append("content LIKE ?"); params.append(f"%{w}%")
    if since_:
        where.append("created>=?"); params.append(dateword(since_, future=False))
    sql = "SELECT id,created,updated,content FROM entry" + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY id"
    c = db()
    rows = [dict(zip(COLS, r)) for r in c.execute(sql, params)]
    for r in rows:  # ponytail: N+1 tag fetch, join+group if ls ever feels slow
        r["tags"] = dict(c.execute("SELECT name,value FROM tagged WHERE entry=?", (r["id"],)))
    return rows


def fmt_tags(t):
    return " ".join(f"@{k}" + (f"={v}" if v else "") for k, v in sorted(t.items()))


def show(rows, fmt):
    if fmt == "json":
        print(json.dumps(rows, indent=1))
    elif fmt == "md":
        for r in rows:
            print(f"## {r['id']} · {r['created']}\n{fmt_tags(r['tags'])}\n\n{r['content']}\n")
    else:
        for r in rows:
            lines = r["content"].splitlines() or [""]
            head = lines[0][:59] + "…" if len(lines) > 1 or len(lines[0]) > 60 else lines[0]
            print(f"{r['id']:>5}  {r['created'][:16]}  {head:<60}  {fmt_tags(r['tags'])}")


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
        print(add_entry(get_text(pos)))
    elif cmd == "todo":
        print(add_entry(get_text(pos), "@todo"))
    elif cmd in ("done", "complete"):
        retag(int(pos[0]), "@done -@todo")
    elif cmd == "tag":
        retag(int(pos[0]), " ".join(pos[1:]))
    elif cmd in ("edit", "show", "history"):
        eid = int(pos.pop(0)) if pos and pos[0].isdigit() else last()
        if cmd == "edit":
            edit(eid, pos)
        elif cmd == "history":
            history(eid)
        else:
            print(entry_text(eid), end="")
            print(backlinks(eid), end="", file=sys.stderr)  # ponytail: stderr keeps stdout round-trippable
    elif cmd == "ls":
        rows = query(pos + ["@by=" + default_tags()["by"]] * ("mine" in opts), opts.get("since"))
        if "last" in opts:
            rows = rows[-int(opts["last"]):]
        show(rows, "json" if "json" in opts else "md" if "md" in opts else "")
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
