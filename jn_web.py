"""jn serve: web UI over the jn library. POST /api/<verb> with a JSON body, JSON back; sys.exit(msg) inside jn becomes a 400.
No auth: bind to loopback and put Cloudflare Zero Trust / Tailscale in front. ponytail: single-threaded server = the global lock."""
import base64, contextlib, json, mimetypes, re, tomllib
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs

HERE = Path(__file__).resolve().parent


def verbs(jn):
    """request body -> response value. ponytail: close/todo are plain tag/log here, config [actions] are CLI-only"""
    def log(text=""):
        if not jn.strip_tags(text):
            raise SystemExit("empty entry")  # add_entry would otherwise read the server's stdin
        return jn.add_entry([text])

    def rows(args):
        """--tree[=tag] nests like the CLI: rows come back in forest order, newest root first, with a depth"""
        opts, pos = jn.parse_opts(list(args))
        rs = jn.select(pos, opts)
        if t := opts.get("tree"):
            rs = [r | {"depth": d} for r, d in jn.as_tree(rs[::-1], "parent" if t is True else t)]
        q = jn.parent_quotes([r for r in rs if not r.get("depth")])  # @parent=#N context line, batched; nested rows already sit under theirs
        return [r | {"parent_ctx": q[r["id"]]} if r["id"] in q else r for r in rs]

    def roots(args):
        """--by[=tag] rolls the view up: one group per root entry (pointer tag, default parent) or per value of a
        plain tag (agent, project...). Each carries its size, open todos, and latest activity beneath it"""
        by, rest = "parent", []
        for a in args:
            if a.startswith("--by"): by = a.partition("=")[2] or "parent"
            else: rest.append(a)
        opts, pos = jn.parse_opts(rest)
        rs = jn.select(pos, opts)
        info = {i: (u, c, bool(o)) for i, u, c, o in jn.db().execute(
            "SELECT e.id, e.updated, e.content, EXISTS(SELECT 1 FROM tagged WHERE entry=e.id AND name='todo') AND NOT EXISTS(SELECT 1 FROM tagged WHERE entry=e.id AND name='done') FROM entry e")}
        head = lambda i: {"id": i, "text": next((l for l in info[i][1].splitlines() if l.strip()), "")[:140]}
        agent = dict(jn.db().execute("SELECT entry, value FROM tagged WHERE name='agent'"))
        item = lambda i: head(i) | {"updated": info[i][0], "open": info[i][2], "agent": agent.get(i)}
        def roll(ids, own=()):  # ids: the entries beneath a group; own: entries that count toward its activity but not its size
            top = max([*ids, *own], key=lambda i: (info[i][0], i), default=None)
            return {"n": len(ids), "open": sum(info[i][2] for i in ids), "updated": info[top][0] if top else "", "latest": head(top) if top and top in ids else None,
                    "preview": [item(i) for i in sorted(ids, key=lambda i: (info[i][0], i), reverse=True)[:4]]}
        pointer = jn.db().execute("SELECT 1 FROM tagged WHERE name=? AND value LIKE '#%' LIMIT 1", (by,)).fetchone()
        if pointer:
            kids = {}
            for e, v in jn.db().execute("SELECT entry, value FROM tagged WHERE name=?", (by,)):
                for i in (v or "").split(","):
                    if i[:1] == "#" and i[1:].isdigit(): kids.setdefault(int(i[1:]), []).append(e)
            def under(root):  # cycle-safe walk down the pointer tag
                out, stack = {root}, [root]
                while stack:
                    for k in kids.get(stack.pop(), []):
                        if k not in out: out.add(k); stack.append(k)
                return out - {root}
            groups = [{"row": r, **roll(under(r["id"]), [r["id"]])} for r in rs]
        else:
            by_val = {}
            for r in rs:
                for v in jn.aslist(r["tags"], by) or [""]: by_val.setdefault(v, []).append(r["id"])
            groups = [{"key": k, **roll(ids)} for k, ids in by_val.items()]
        return {"by": by, "pointer": bool(pointer), "groups": sorted(groups, key=lambda g: (g["updated"], g["row"]["id"] if "row" in g else g["latest"]["id"]), reverse=True)}

    def show(id):
        row = jn.select([str(int(id))], {"all": True})
        anc, seen, r = [], {int(id)}, row[0] if row else None  # @parent chain walked up: root first, cycle-safe, capped
        while r and (p := jn.parent_of(r)) and p not in seen and len(anc) < 10:
            seen.add(p); pr = jn.select([str(p)], {"all": True}); r = pr[0] if pr else None
            if r: anc.append(r)
        return {"text": jn.entry_text(int(id)), "backlinks": jn.backlinks(int(id)), "row": row[0] if row else None, "ancestors": anc[::-1]}

    def vocab():
        """tag name -> its known items, for @ completion"""
        out = {}
        for n, v in jn.db().execute("SELECT name, value FROM tagged"):
            out.setdefault(n, set()).update(i for i in (v or "").split(",") if i)
        return {n: sorted(s) for n, s in sorted(out.items())}

    def filt(name, expr=None):
        """save (or drop, expr=None) a token filter under [filters] in ~/.jn; python never comes from the web"""
        if not re.fullmatch(r"[A-Za-z_][\w-]*", name) or (expr is not None and (not jn.is_tokens(expr) or re.search(r"[\"'\\\n]", expr))):
            raise SystemExit("name must be a word and the filter ls tokens (@tag -@tag --since 1w ...)")
        f = (jn.Path.home() / ".jn").resolve()
        text = f.read_text() if f.is_file() else ""
        m = re.search(r"(?ms)^\[filters\]\n(.*?)(?=^\[|\Z)", text)
        body = re.sub(rf"(?m)^{re.escape(name)}\s*=.*\n?", "", m[1]) if m else ""
        body += f'{name} = "{expr}"\n' if expr is not None else ""
        new = text[:m.start(1)] + body + text[m.end(1):] if m else text.rstrip("\n") + ("\n\n" if text else "") + "[filters]\n" + body
        tomllib.loads(new)  # a ValueError here is a 400, and the file is untouched
        f.write_text(new)
        jn.config.cache_clear()  # config() is cached per process; the CLI never lives long enough to notice
        return {"filters": [{"name": n, "own": src == str(f)} for n, src in cfg_filters()]}

    def attach(id, name, data):
        """base64 upload -> stored name, appended to @files"""
        raw = base64.b64decode(data)
        if len(raw) > 20 << 20:
            raise SystemExit("file over 20 MB")  # ponytail: checked after the read; the body cap is the server's RAM
        stored = jn.store_file(raw, name)
        jn.tag(int(id), ["@files+=" + stored])
        return stored

    def cfg_filters():
        c = jn.config()
        return [(n, c["src"][n]) for n in c["filters"]]

    return {
        "vocab": vocab,
        "filter": filt,
        "ls": lambda args=(): rows(args),
        "roots": roots,
        "tags": lambda args=(): jn.tag_counts(rows(args)),
        "show": show,
        "log": log,
        "tag": lambda id, patch=(): jn.tag(int(id), list(patch)),
        "edit": lambda id, text="": jn.edit(int(id), text),
        "attach": attach,
        "dbs": lambda: list(jn.config()["dbs"]),
        "config": lambda: {"filters": [{"name": n, "own": src == str((jn.Path.home() / ".jn").resolve())} for n, src in cfg_filters()], "tags": jn.fmt_tags(jn.default_tags()),
                          "colors": jn.config()["colors"], "favorites": jn.config()["favorites"], "db": str(jn.DB)},
    }


def server(jn, host, port):
    api, default_db = verbs(jn), jn.DB

    candidates = [jn.Path.home() / ".jn", *(p / ".jn" for p in [jn.Path.cwd(), *jn.Path.cwd().parents])]
    seen = [None]

    def fresh():
        """config() is cached per process; drop it when any .jn that could layer in changes (or appears)"""
        stamp = [p.stat().st_mtime_ns if p.is_file() else None for p in candidates]
        if stamp != seen[0]:
            seen[0] = stamp; jn.config.cache_clear()

    def use(name):
        """select this request's journal; JSONL snapshots last only one request so CLI edits stay visible"""
        fresh()
        if name and name not in jn.config()["dbs"]:
            raise SystemExit(f"no db named {name}; add it under [dbs] in .jn")  # names only from the web, never paths
        path = jn.db_path(name) if name else default_db
        if path != jn.DB or path.suffix in (".jsonl", ".json"):
            if jn.db.cache_info().currsize:
                jn.db().close()
            jn.db.cache_clear()
            jn.DB = path

    class H(BaseHTTPRequestHandler):
        def send(self, code, body, ctype="application/json"):
            body = body.encode() if isinstance(body, str) else body
            self.send_response(code); self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(body)))
            self.end_headers(); self.wfile.write(body)

        def do_GET(self):
            path, _, qs = self.path.partition("?")  # the page keeps its query in the URL
            if path == "/":
                self.send(200, (HERE / "jn_web.html").read_text(), "text/html; charset=utf-8")
            elif path == "/manifest.json":
                self.send(200, json.dumps({"name": "jn", "short_name": "jn", "start_url": "/", "display": "standalone",
                                           "background_color": "#111", "theme_color": "#111", "icons": []}), "application/manifest+json")
            elif path.startswith("/files/"):  # attachments: names are hash+ext only, so no traversal; ?db= like the JSON `db`
                name = path[7:]
                try:
                    use(parse_qs(qs).get("db", [None])[0])
                except SystemExit as e:
                    return self.send(400, str(e.code), "text/plain")
                f = jn.files_dir() / name
                if not re.fullmatch(r"[0-9a-f]{16}(\.[a-z0-9]+)?", name) or not f.is_file():
                    return self.send(404, "", "text/plain")
                self.send(200, f.read_bytes(), mimetypes.guess_type(name)[0] or "application/octet-stream")
            else:
                self.send(404, "", "text/plain")

        def do_POST(self):
            verb = self.path.removeprefix("/api/")
            if verb not in api:
                return self.send(404, json.dumps({"error": "no such verb"}))
            try:
                req = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
                use(req.pop("db", None))
                self.send(200, json.dumps({"out": api[verb](**req)}))
            except SystemExit as e:
                self.send(400, json.dumps({"error": str(e.code or "")}))
            except (ValueError, TypeError) as e:
                self.send(400, json.dumps({"error": str(e)}))

        def log_message(self, *a):  # ponytail: quiet; add real logging when something needs debugging
            pass
    return HTTPServer((host, port), H)


def serve(jn, opts):
    s = server(jn, opts.get("host", "127.0.0.1"), int(opts.get("port", 8787)))
    print(f"jn serve on http://{s.server_address[0]}:{s.server_address[1]}  (db {jn.DB})")
    with contextlib.suppress(KeyboardInterrupt):
        s.serve_forever()
