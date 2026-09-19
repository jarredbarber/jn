"""Smallest check that fails if tag parsing / querying / config discovery breaks. Run: python3 test_jn.py"""
import datetime, json, os, subprocess, sys, tempfile
from pathlib import Path

JN = Path(__file__).with_name("jn.py")

def run(*args, stdin=None, **env):
    return subprocess.run([sys.executable, JN, *args], input=stdin, capture_output=True, text=True,
                          env={**os.environ, **env}, cwd=env["CWD"], check=True).stdout.strip()

with tempfile.TemporaryDirectory() as d:
    env = dict(JN_DB=f"{d}/t.db", HOME=d, CWD=f"{d}/proj/sub", CLAUDE_CODE_SESSION_ID="s0", ANTIGRAVITY_CONVERSATION_ID="")
    Path(env["CWD"]).mkdir(parents=True)
    Path(d, "proj/.jn").write_text('tags = ["project=demo"]\n[actions]\nnote = "log @note $@"\n[filters]\nopen = "@todo -@done"\nevil = "__import__(\'os\').system(\'touch pwned\')"\n')
    Path(d, ".jn").write_text('tags = ["global"]\ntags_expr = "\'@ws=\' + cwd.rsplit(\'/\', 1)[1]"\n[filters]\nfit = "tag(\'@fitness\') == [] and env(\'$JN_DB\')"\n')
    Path(d, "proj/sub/.jn").write_text('tags_expr = "[\'@evil\']"\n')  # must be ignored

    ids = lambda out: [l.split()[0] for l in out.splitlines()[1:]]      # skip table header
    js = lambda out: [json.loads(l) for l in out.splitlines() if l]        # --json is jsonl
    a = run("todo", "@fitness do 10 pushups", "@daily", **env)
    b = run("log", stdin="# Heading\nwalked @agent=claude:s1 @re=#" + a, **env)
    run("close", a, **env)
    rows = js(run("ls", "--json", "--all", **env))
    assert rows[0]["content"] == "do 10 pushups" and rows[1]["content"] == "# Heading\nwalked", rows
    t0, t1 = rows[0]["tags"], rows[1]["tags"]
    assert t0["ws"] == "sub" and "evil" not in t0 and t0["agent"] == "claude:s0", t0   # builtin @agent from env
    assert "todo" in t0 and "done" in t0 and t0["project"] == "demo" and "global" in t0, t0   # close adds @done, keeps @todo
    assert t1["agent"] == "claude:s1" and t1["re"] == "#" + a and "Heading" not in t1, t1   # text overrides the builtin
    assert run("ls", "--open", **env) == ""                                 # token filter from project .jn, nothing open
    assert ids(run("ls", "@agent=claude:*", **env))[0] == b                 # value glob (a is @done, hidden)
    assert ids(run("ls", "pushups", "--since", "today", "--all", **env))[0] == a  # text + since
    assert ids(run("ls", "-@done", **env))[0] == b                       # negation
    assert run("show", **env) == run("show", b, **env)                     # no id -> last entry
    assert run("show", a, **env).endswith(f"<- #{b} @re  # Heading"), run("show", a, **env)   # backlinks with title
    run("edit", stdin=run("show", **env).replace("walked", "ran") + " @new", **env)   # show (with backlinks) pipes into edit
    e = js(run("ls", b, "--json", **env))[0]
    assert e["content"] == "# Heading\nran" and e["tags"]["re"] == "#" + a and "new" in e["tags"] and e["tags"]["agent"] == "claude:s1", e
    run("edit", b, stdin="@agent=claude:s2 @re=#" + a + "\n\nran instead", **env)   # document: buffer is the whole entry (no builtin merge)
    e = js(run("ls", b, "--json", **env))[0]
    assert e["content"] == "ran instead" and e["tags"] == {"agent": "claude:s2", "re": "#" + a}, e
    run("tag", b, "@agent=claude:s1", "@global", **env)          # patch: content untouched
    assert js(run("ls", b, "--json", **env))[0]["content"] == "ran instead"
    assert subprocess.run([sys.executable, JN, "edit", b, "text"], capture_output=True, env={**os.environ, **env}, cwd=env["CWD"]).returncode == 1
    run("edit", b, stdin=run("show", b, **env), **env)         # no-op edit adds no history
    h = run("history", b, **env)
    assert "v5" not in h, h
    ha = run("history", a, **env)
    assert "@todo" in ha.split("v2")[0] and "@done" in ha.split("v2")[1], ha   # close is versioned
    run("close", a, **env)                                                     # idempotent flip: no new version
    assert "v3" not in run("history", a, **env)
    assert h.index("walked") < h.index("ran instead") and "v3" in h, h
    c = run("todo", "@due=tomorrow call dentist", **env)
    tc = js(run("ls", c, "--json", **env))[0]["tags"]
    assert tc["due"] == (datetime.date.today() + datetime.timedelta(days=1)).isoformat(), tc
    assert ids(run("ls", "@due=" + tc["due"], **env))[0] == c and ids(run("ls", "@due=tomorrow", **env))[0] == c
    assert len(ids(run("ls", "--since", "1d", "--all", **env))) == 3                # bare N is past for --since
    pr = run("log", "see #1 and #2", **env)
    assert js(run("ls", pr, "--json", **env))[0]["content"] == "see #1 and #2"   # #N is prose, not a tag
    assert b not in ids(run("ls", "--mine", **env)) and a in ids(run("ls", "--mine", "--all", **env))
    assert a not in ids(run("ls", **env)) and a in ids(run("ls", "@done", **env)) and ids(run("ls", a, **env)) == [a]   # default filter
    assert ids(run("ls", "--mine", JN_TAGS="@agent=claude:s1", **env)) == [b]
    x = run("todo", "@blocked_by=#" + a + ",#" + c + " ship it", **env)      # a done, c open
    y = run("todo", "@blocked_by=#" + a + ",vendor manual block", **env)
    assert ids(run("ls", "@todo", "--blocked", **env)) == [x, y]
    assert ids(run("ls", "@todo", "--unblocked", **env)) == [c]
    assert ids(run("close", c, **env)) == [x]                                 # done prints what it unblocked
    assert ids(run("ls", "@todo", "--unblocked", **env)) == [x]
    z = run("todo", "@blocked_by=#420 false positive bait", **env)
    assert ids(run("ls", "@blocked_by=#" + a, **env)) == [x, y]             # item match, not substring
    assert ids(run("ls", "@blocked_by=#420,vendor", **env)) == [y, z]       # any-of
    assert ids(run("ls", "@blocked_by=#4*", **env)) == [z]                  # glob per item
    assert ids(run("ls", "--fit", "--all", **env)) == [a]                            # custom filter from ~/.jn
    run("tag", z, "@blocked_by+=#7,#420", "@seen+=x", **env)               # append dedup, create on +=
    tz = js(run("ls", z, "--json", **env))[0]["tags"]
    assert tz["blocked_by"] == "#420,#7" and tz["seen"] == "x", tz
    run("tag", z, "@blocked_by-=#420,#7", "@nope-=x", **env)               # emptied tag stays; -= on absent is a no-op
    tz = js(run("ls", z, "--json", **env))[0]["tags"]
    assert tz["blocked_by"] is None and "nope" not in tz, tz
    Path(d, ".jn").write_text(Path(d, ".jn").read_text() + 'week = "@todo --since 1w --mine"\nweek2 = "--week @fitness"\n')   # token filters carry opts + names
    assert ids(run("ls", "--week", "--all", **env)) == [a, c, x, y, z] and ids(run("ls", "--week2", "--all", **env)) == [a]
    Path(d, ".jn").write_text(Path(d, ".jn").read_text() + f'[dbs]\nalt = "{d}/alt.db"\n')
    assert run("log", "in alt", "--db=alt", **env) == "1" and ids(run("ls", "--db", "alt", **env)) == ["1"] and "in alt" not in run("ls", **env)   # named db
    assert f"alt            {d}/alt.db" in run("-h", **env)
    h = run("-h", **env)
    assert "--evil" not in h and not Path(d, "proj/sub/pwned").exists()   # python filter in project .jn ignored
    rd = str(Path(d).resolve())
    assert next(l for l in h.splitlines() if l.startswith("config:")).split(", ")[1:] == [f"{rd}/{x}" for x in (".jn", "proj/.jn", "proj/sub/.jn")], (h, rd)
    assert "fit" in h and "unblocked" in h and "open" in h, h
    n = run("note", "@k=v", stdin="body from stdin", **env)                  # custom action; tag-only args read stdin
    e = js(run("ls", n, "--json", **env))[0]
    assert e["content"] == "body from stdin" and e["tags"]["note"] is None and e["tags"]["k"] == "v", e
    assert "  note           log @note $@" in h, h
    run("revert", b, **env)                                                  # back to previous version
    assert run("show", b, **env).startswith("@agent=claude:s2 @re=#" + a + "\n\nran instead"), run("show", b, **env)
    run("revert", b, "v1", **env)
    assert "walked" in run("show", b, **env) and "v6" in run("history", b, **env)   # reverts are versioned
    p1 = run("todo", "@tree root", **env); p2 = run("todo", "@tree @parent=#" + p1 + " child", **env)
    p3 = run("todo", "@tree @parent=#" + p2 + " grandchild", **env); p4 = run("todo", "@tree @parent=#999 orphan", **env)
    out = run("ls", "@tree", "--tree", **env).splitlines()[1:]
    assert [l.split()[0] for l in out] == [p1, p2, p3, p4] and "    grandchild" in out[2] and out[3].split("  ")[3] == "orphan", out
    run("tag", p1, p2, "@multi", **env)
    assert ids(run("ls", "@multi", **env)) == [p1, p2]
    run("close", p3, p4, **env)
    assert ids(run("ls", "@tree", **env)) == [p1, p2]                        # multi-arg action runs per arg
    g = run("log", "agy note", **{**env, "CLAUDE_CODE_SESSION_ID": "", "ANTIGRAVITY_CONVERSATION_ID": "cv9"})
    assert js(run("ls", g, "--json", **env))[0]["tags"]["agent"] == "agy:cv9"   # second env var wins when first is unset
    hh = run("log", "human note", **{**env, "CLAUDE_CODE_SESSION_ID": ""})
    assert "agent" not in js(run("ls", hh, "--json", **env))[0]["tags"]          # no agent env -> no @agent
    assert ids(run("ls", "--mine", "--all", **{**env, "CLAUDE_CODE_SESSION_ID": "", "ANTIGRAVITY_CONVERSATION_ID": ""})) == [hh]  # human --mine = entries with no @agent
    assert "task workflow" in run("--skill", "todo", **env) and "# jn" in run("--skill", **env)   # --skill pages
    assert subprocess.run([sys.executable, JN, "--skill", "nope"], capture_output=True, env={**os.environ, **env}, cwd=env["CWD"]).returncode == 1
    row = js(run("ls", p1, "--json", **env))[0]; row["tags"].pop("multi")    # import: round-trip a tag removal
    assert run("import", stdin=json.dumps(row), **env) == "imported 1"
    assert "multi" not in js(run("ls", p1, "--json", **env))[0]["tags"] and ids(run("ls", p1, **env)) == [p1]  # id preserved
    assert subprocess.run([sys.executable, JN, "import"], input="junk\n", capture_output=True, text=True,
                          env={**os.environ, **env}, cwd=env["CWD"]).returncode == 1                          # bad jsonl aborts
    run("--db", f"{d}/alt.db", "log", "only in alt", **env)                  # --db overrides $JN_DB, either position
    assert ids(run("ls", "alt", "--db", f"{d}/alt.db", **env)) and not ids(run("ls", "alt", **env))
    print("ok")

    # jn serve: the library over HTTP. stdin never read, errors are 400s, tags-only log rejected
    import importlib, threading, urllib.request, urllib.error
    os.environ["JN_DB"], os.environ["HOME"] = f"{d}/web.db", d; sys.path.insert(0, str(JN.parent)); os.chdir(env["CWD"])   # HOME: filter saves go to the temp ~/.jn
    jn, jn_web = importlib.import_module("jn"), importlib.import_module("jn_web")
    srv = jn_web.server(jn, "127.0.0.1", 0); threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_address[1]}"
    def post(verb, **body):
        try:
            with urllib.request.urlopen(urllib.request.Request(url + "/api/" + verb, json.dumps(body).encode())) as r:
                return r.status, json.loads(r.read())["out"]
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())["error"]
    assert post("log", text="@todo @fitness from phone") == (200, 1)
    assert post("log", text="@todo")[0] == 400 and post("nope")[0] == 404 and post("tag", id="x")[0] == 400
    assert post("edit", id=1, text="@todo @x\n\nfrom the web")[0] == 200
    e = post("ls", args=["1"])[1][0]
    assert e["content"] == "from the web" and "x" in e["tags"], e
    assert post("show", id=1)[1]["text"].startswith("@todo @x") and post("tags", args=[])[1][0] == ["todo", 1]
    assert post("tag", id=1, patch=["@done"])[0] == 200 and post("ls")[1] == []      # closed, default filter hides it
    assert "<!doctype" in urllib.request.urlopen(url + "/").read().decode() and {"name": "mine", "own": False} in post("config")[1]["filters"]
    v = post("vocab")[1]; assert v["done"] == [] and v["x"] == [] and "todo" in v, v
    r = post("filter", name="hot", expr="@todo --since 1w"); assert {"name": "hot", "own": True} in r[1]["filters"], (r, Path(d, ".jn").read_text())
    assert post("filter", name="hot", expr="tag('x')")[0] == 400 and post("filter", name="a b", expr="@x")[0] == 400   # no python from the web
    r = post("filter", name="fit", expr="@x -@done"); assert r[0] == 200, r
    r = post("ls", args=["--fit", "--all"]); assert r[1] == [], r      # overrides the ~/.jn one in place
    cfg = Path(d, ".jn").read_text()
    assert cfg.count("[filters]") == 1 and 'fit = "@x -@done"' in cfg and 'hot = "@todo --since 1w"' in cfg and "week2" in cfg, cfg
    assert post("filter", name="hot")[0] == 200 and "hot" not in Path(d, ".jn").read_text()
    assert post("dbs")[1] == ["alt"] and post("ls", db="alt", args=["--all"])[1][0]["content"] == "in alt" and post("ls", args=["--all"])[1][0]["content"] == "from the web"
    post("log", text="@todo parent task"); post("log", text="@todo @parent=#2 child task"); post("log", text="@todo loose")
    t = post("ls", args=["--tree"])[1]
    assert [(r["id"], r["depth"]) for r in t] == [(4, 0), (2, 0), (3, 1)], t      # newest root first, child under its parent
    assert "depth" not in post("ls")[1][0]
    assert post("ls", db="/nope/x.db")[0] == 400 and post("ls", db="nope")[0] == 400   # names only from the web
    assert ids(run("ls", "--fit", "--all", **env)) == []
    srv.shutdown()
