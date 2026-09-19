"""jn serve: web UI over the jn library. POST /api/<verb> with a JSON body, JSON back; sys.exit(msg) inside jn becomes a 400.
No auth: bind to loopback and put Cloudflare Zero Trust / Tailscale in front. ponytail: single-threaded server = the global lock."""
import contextlib, json
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
        opts, pos = jn.parse_opts(list(args))
        return jn.select(pos, opts)

    def show(id):
        row = jn.select([str(int(id))], {"all": True})
        return {"text": jn.entry_text(int(id)), "backlinks": jn.backlinks(int(id)), "row": row[0] if row else None}

    return {
        "ls": lambda args=(): rows(args),
        "tags": lambda args=(): jn.tag_counts(rows(args)),
        "show": show,
        "log": log,
        "tag": lambda id, patch=(): jn.tag(int(id), list(patch)),
        "edit": lambda id, text="": jn.edit(int(id), text),
        "config": lambda: {"filters": list(jn.config()["filters"]), "tags": jn.fmt_tags(jn.default_tags())},
    }


def server(jn, host, port):
    api = verbs(jn)

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
