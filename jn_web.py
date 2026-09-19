"""jn serve: the CLI over HTTP. POST /api {"argv": [...], "stdin": "..."} runs an allowlisted jn command and returns its stdout.
No auth: bind to loopback and put Cloudflare Zero Trust / Tailscale in front. ponytail: single-threaded server = the global lock."""
import contextlib, io, json, sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
ALLOW = {"ls", "tags", "show", "log", "tag", "edit", "history", "revert"}  # + config actions. never import/--db/--skill


def run(jn, argv, stdin=""):
    """(status, text). sys.exit(msg) inside jn becomes a 400 with msg"""
    if not argv or argv[0] not in ALLOW | set(jn.config()["actions"]) or any(a == "--db" or a.startswith("--db=") for a in argv):
        return 400, "not allowed"
    out, old = io.StringIO(), sys.stdin
    sys.stdin = io.StringIO(stdin)  # read_body() sees a non-tty and reads it
    try:
        with contextlib.redirect_stdout(out):
            jn.main(argv)
        return 200, out.getvalue()
    except SystemExit as e:
        return 400, str(e.code or "")
    finally:
        sys.stdin = old


def server(jn, host, port):
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
            elif self.path == "/config":
                cfg = jn.config()
                self.send(200, json.dumps({"filters": list(cfg["filters"]), "actions": list(cfg["actions"]), "tags": jn.fmt_tags(jn.default_tags())}))
            else:
                self.send(404, "", "text/plain")

        def do_POST(self):
            try:
                req = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
                code, text = run(jn, list(req.get("argv", [])), str(req.get("stdin", "")))
            except (ValueError, TypeError) as e:
                code, text = 400, str(e)
            self.send(code, json.dumps({"out": text} if code == 200 else {"error": text}))

        def log_message(self, *a):  # ponytail: quiet; add real logging when something needs debugging
            pass
    return HTTPServer((host, port), H)


def serve(jn, opts):
    s = server(jn, opts.get("host", "127.0.0.1"), int(opts.get("port", 8787)))
    print(f"jn serve on http://{s.server_address[0]}:{s.server_address[1]}  (db {jn.DB})")
    with contextlib.suppress(KeyboardInterrupt):
        s.serve_forever()
