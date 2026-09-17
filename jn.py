#!/usr/bin/env python3
"""jn: microjournal + tasks for humans and agents. Single file, stdlib only (py3.11+).

  jn log [text...]           add entry; no text -> stdin (if piped) or $EDITOR. prints id
  jn todo [text...]          same, plus @todo
  jn done ID                 @done -@todo
  jn tag ID @a -@b @k=v      add/remove tags
  jn edit ID [text...]       replace content ($EDITOR seeded with old); tags in text re-synced
  jn show ID                 full entry
  jn history ID              prior versions of content (oldest first), then current
  jn ls [filters] [opts]     filters: @tag  -@tag  @k=v*  word  ID  <query-name>
                             opts: --since today|yesterday|3d|2w|ISO  --last N  --json  --md

tags: @name or #name, optional =value. Defaults come from ~/.jn and nearest ./.jn (TOML:
  tags = ["project=x"]  [queries] open = "@todo -@done") plus $JN_TAGS. @by defaults to $USER.
  ~/.jn only: tags_cmd = "shell snippet" whose stdout is extra tags (e.g. derive @workspace from $PWD).
db: $JN_DB or ~/.jn.db
"""
import getpass, json, os, re, sqlite3, subprocess, sys, tempfile, tomllib
from datetime import datetime, timedelta
from pathlib import Path

DB = Path(os.environ.get("JN_DB", Path.home() / ".jn.db"))
# sigil must follow start/whitespace and touch a word char, so "# Heading" is not a tag
TAG = re.compile(r"(?:^|(?<=\s))(-?)[@#]([\w-]+)(?:=(\S+))?")
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
        (rm.add if neg else lambda n: add.__setitem__(n, val or None))(name)
    return add, rm


def get_text(args, seed=""):
    if args:
        return " ".join(args)
    if not sys.stdin.isatty():
        return sys.stdin.read().strip()
    with tempfile.NamedTemporaryFile("w+", suffix=".md") as f:
        f.write(seed); f.flush()
        subprocess.run([*os.environ.get("EDITOR", "vi").split(), f.name])
        return Path(f.name).read_text().strip()


def add_entry(text, extra=""):
    if not text:
        sys.exit("empty entry")
    defaults = " ".join("@" + t.lstrip("@#") for t in config()["tags"])
    tags, _ = parse_tags(" ".join([defaults, os.environ.get("JN_TAGS", ""), extra, text]))
    tags.setdefault("by", getpass.getuser())
    with db() as c:
        eid = c.execute("INSERT INTO entry(created,updated,content) VALUES(?,?,?)", (now(), now(), text)).lastrowid
        c.executemany("INSERT INTO tagged VALUES(?,?,?)", [(eid, k, v) for k, v in tags.items()])
    return eid


def retag(eid, text):
    add, rm = parse_tags(text)
    with db() as c:
        if not c.execute("SELECT 1 FROM entry WHERE id=?", (eid,)).fetchone():
            sys.exit(f"no entry {eid}")
        c.executemany("INSERT OR REPLACE INTO tagged VALUES(?,?,?)", [(eid, k, v) for k, v in add.items()])
        c.executemany("DELETE FROM tagged WHERE entry=? AND name=?", [(eid, n) for n in rm])
        c.execute("UPDATE entry SET updated=? WHERE id=?", (now(), eid))


def edit(eid, args):
    with db() as c:
        old = c.execute("SELECT content FROM entry WHERE id=?", (eid,)).fetchone() or sys.exit(f"no entry {eid}")
        new = get_text(args, old[0]) or sys.exit("empty entry")
        # ponytail: content only; tag flips are not versioned, `updated` says something changed
        c.execute("INSERT INTO history SELECT id, updated, content FROM entry WHERE id=?", (eid,))
        c.execute("UPDATE entry SET content=?, updated=? WHERE id=?", (new, now(), eid))
    # tags typed in old content but gone from new are dropped; tags set via `jn tag` survive
    retag(eid, new + " " + " ".join("-@" + k for k in parse_tags(old[0])[0].keys() - parse_tags(new)[0].keys()))


def history(eid):
    c = db()
    old = c.execute("SELECT at, content FROM history WHERE entry=? ORDER BY rowid", (eid,)).fetchall()
    cur = c.execute("SELECT updated, content FROM entry WHERE id=?", (eid,)).fetchone() or sys.exit(f"no entry {eid}")
    for n, (at, content) in enumerate([*old, cur], 1):
        print(f"## {eid} v{n} · {at}\n\n{content}\n")


def since(s):
    if s in ("today", "yesterday"):
        return (datetime.now().date() - timedelta(days=s == "yesterday")).isoformat()
    if m := re.fullmatch(r"(\d+)([hdw])", s):
        unit = {"h": "hours", "d": "days", "w": "weeks"}[m[2]]
        return (datetime.now() - timedelta(**{unit: int(m[1])})).isoformat(timespec="seconds")
    return s  # assume ISO


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
        where.append("created>=?"); params.append(since(since_))
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
            head = (r["content"].splitlines() or [""])[0][:60]
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
    elif cmd == "edit":
        edit(int(pos[0]), pos[1:])
    elif cmd == "history":
        history(int(pos[0]))
    elif cmd == "show":
        show(query(pos[:1]), "md")
    elif cmd == "ls":
        rows = query(pos, opts.get("since"))
        if "last" in opts:
            rows = rows[-int(opts["last"]):]
        show(rows, "json" if "json" in opts else "md" if "md" in opts else "")
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
