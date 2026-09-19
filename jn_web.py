"""jn serve: web UI over the jn library. POST /api/<verb> with a JSON body, JSON back; sys.exit(msg) inside jn becomes a 400.
No auth: bind to loopback and put Cloudflare Zero Trust / Tailscale in front. ponytail: single-threaded server = the global lock."""
import contextlib, json, re, tomllib
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

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
        return rs

    def show(id):
        row = jn.select([str(int(id))], {"all": True})
        return {"text": jn.entry_text(int(id)), "backlinks": jn.backlinks(int(id)), "row": row[0] if row else None}

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

    def cfg_filters():
        c = jn.config()
        return [(n, c["src"][n]) for n in c["filters"]]

    return {
        "vocab": vocab,
        "filter": filt,
        "ls": lambda args=(): rows(args),
        "tags": lambda args=(): jn.tag_counts(rows(args)),
        "show": show,
        "log": log,
        "tag": lambda id, patch=(): jn.tag(int(id), list(patch)),
        "edit": lambda id, text="": jn.edit(int(id), text),
        "dbs": lambda: list(jn.config()["dbs"]),
        "config": lambda: {"filters": [{"name": n, "own": src == str((jn.Path.home() / ".jn").resolve())} for n, src in cfg_filters()], "tags": jn.fmt_tags(jn.default_tags())},
    }


def server(jn, host, port):
    api, default_db = verbs(jn), jn.DB

    def use(name):
        """point the library at a [dbs] name (or the startup db) for this request; db() is cached per path"""
        if name and name not in jn.config()["dbs"]:
            raise SystemExit(f"no db named {name}; add it under [dbs] in .jn")  # names only from the web, never paths
        path = jn.db_path(name) if name else default_db
        if path != jn.DB:
            jn.DB = path; jn.db.cache_clear()

    class H(BaseHTTPRequestHandler):
        def send(self, code, body, ctype="application/json"):
            body = body.encode()
            self.send_response(code); self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(body)))
            self.end_headers(); self.wfile.write(body)

        def do_GET(self):
            if self.path == "/":
                self.send(200, (HERE / "jn_web.html").read_text(), "text/html; charset=utf-8")
            elif self.path == "/manifest.json":
                self.send(200, json.dumps({"name": "jn", "short_name": "jn", "start_url": "/", "display": "standalone",
                                           "background_color": "#111", "theme_color": "#111", "icons": []}), "application/manifest+json")
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
