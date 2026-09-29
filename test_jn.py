"""Smallest check that fails if tag parsing / querying / config discovery breaks. Run: python3 test_jn.py"""
import base64, datetime, hashlib, json, os, subprocess, sys, tempfile
from pathlib import Path

JN = Path(__file__).with_name("jn.py")

def run(*args, stdin=None, **env):
    return subprocess.run([sys.executable, JN, *args], input=stdin, capture_output=True, text=True,
                          env={**os.environ, **env}, cwd=env["CWD"], check=True).stdout.strip()

with tempfile.TemporaryDirectory() as d:
    env = dict(JN_DB=f"{d}/t.db", HOME=d, CWD=f"{d}/proj/sub", CLAUDE_CODE_SESSION_ID="s0", ANTIGRAVITY_CONVERSATION_ID="")
    Path(env["CWD"]).mkdir(parents=True)
    Path(d, "proj/.jn").write_text('tags = ["project=demo"]\nfavorites = ["todo", "due"]\n[actions]\nnote = "log @note $@"\n[filters]\nopen = "@todo -@done"\nevil = "__import__(\'os\').system(\'touch pwned\')"\n[colors]\ntodo = "#ff0"\n')
    Path(d, ".jn").write_text('tags = ["global"]\nfavorites = ["due", "home"]\ntags_expr = "\'@ws=\' + cwd.rsplit(\'/\', 1)[1]"\n[colors]\ntodo = "#000"\ndue = "#0ff"\n[filters]\nfit = "tag(\'@fitness\') == [] and env(\'$JN_DB\')"\n')
    Path(d, "proj/sub/.jn").write_text('tags_expr = "[\'@evil\']"\n')  # must be ignored

    ids = lambda out: [l.split()[0] for l in out.splitlines()[1:] if l.split()[:1] and l.split()[0].isdigit()]   # skip header + @parent context lines
    js = lambda out: [json.loads(l) for l in out.splitlines() if l]        # --json is jsonl
    a = run("todo", "@fitness do 10 pushups", "@daily", **env)
    b = run("log", stdin="# Heading\nwalked @agent=claude:s1 @see=#" + a, **env)
    run("close", a, **env)
    rows = js(run("ls", "--json", "--all", **env))
    assert rows[0]["content"] == "do 10 pushups" and rows[1]["content"] == "# Heading\nwalked", rows
    t0, t1 = rows[0]["tags"], rows[1]["tags"]
    assert t0["ws"] == "sub" and "evil" not in t0 and t0["agent"] == "claude:s0", t0   # builtin @agent from env
    assert "todo" in t0 and "done" in t0 and t0["project"] == "demo" and "global" in t0, t0   # close adds @done, keeps @todo
    assert t1["agent"] == "claude:s1" and t1["see"] == "#" + a and "Heading" not in t1, t1   # text overrides the builtin
    assert run("ls", "--open", **env) == ""                                 # token filter from project .jn, nothing open
    assert ids(run("ls", "@agent=claude:*", **env))[0] == b                 # value glob (a is @done, hidden)
    assert ids(run("ls", "pushups", "--since", "today", "--all", **env))[0] == a  # text + since
    assert ids(run("ls", "-@done", **env))[0] == b                       # negation
    assert run("show", **env) == run("show", b, **env)                     # no id -> last entry
    assert run("show", a, **env).endswith(f"<- #{b} @see  # Heading"), run("show", a, **env)   # backlinks with title
    run("edit", stdin=run("show", **env).replace("walked", "ran") + " @new", **env)   # show (with backlinks) pipes into edit
    e = js(run("ls", b, "--json", **env))[0]
    assert e["content"] == "# Heading\nran" and e["tags"]["see"] == "#" + a and "new" in e["tags"] and e["tags"]["agent"] == "claude:s1", e
    run("edit", b, stdin="@agent=claude:s2 @see=#" + a + "\n\nran instead", **env)   # document: buffer is the whole entry (no builtin merge)
    e = js(run("ls", b, "--json", **env))[0]
    assert e["content"] == "ran instead" and e["tags"] == {"agent": "claude:s2", "see": "#" + a}, e
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
    assert "colors:\n  todo           #ff0\n  due            #0ff\n" in h and "favorites: @todo @due @home" in h, h   # [colors]/favorites layer, nearer wins
    n = run("note", "@k=v", stdin="body from stdin", **env)                  # custom action; tag-only args read stdin
    e = js(run("ls", n, "--json", **env))[0]
    assert e["content"] == "body from stdin" and e["tags"]["note"] is None and e["tags"]["k"] == "v", e
    assert "  note           log @note $@" in h, h
    run("revert", b, **env)                                                  # back to previous version
    assert run("show", b, **env).startswith("@agent=claude:s2 @see=#" + a + "\n\nran instead"), run("show", b, **env)
    run("revert", b, "v1", **env)
    assert "walked" in run("show", b, **env) and "v6" in run("history", b, **env)   # reverts are versioned
    p1 = run("todo", "@tree root", **env); p2 = run("todo", "@tree @parent=#" + p1 + " child", **env)
    p3 = run("todo", "@tree @parent=#" + p2 + " grandchild", **env); p4 = run("todo", "@tree @parent=#999 orphan", **env)
    out = run("ls", "@tree", "--all", "--tree", **env).splitlines()[1:]
    assert ids("h\n" + "\n".join(out)) == [p1, p2, p3, p4] and "    grandchild" in out[2] and out[4].split("  ")[3] == "orphan", out
    assert [l.strip() for l in out if "↳" in l] == ["↳ #999 (missing)"], out     # context only on roots whose parent isn't shown
    bad = lambda *a, **k: subprocess.run([sys.executable, JN, *a], input=k.get("stdin"), capture_output=True, text=True, env={**os.environ, **env}, cwd=env["CWD"])
    assert bad("log", "x @parent=#1,#2").returncode == 1 and "one @parent" in bad("tag", p1, "@parent=#1,#2").stderr and bad("tag", p1, "@parent+=#1,#2").returncode == 1   # one home per entry
    assert bad("edit", p1, stdin="@parent=#1,#2\n\nx").returncode == 1 and bad("log", "ok @refs=#1,#2").returncode == 0                                              # many pointers: another tag
    run("tag", p1, p2, "@multi", **env)
    assert ids(run("ls", "@multi", "--all", **env)) == [p1, p2]
    run("close", p3, p4, **env)
    assert ids(run("ls", "@tree", "-@done", "--all", **env)) == [p1, p2]     # multi-arg action runs per arg
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
    Path(d, "a.PNG").write_bytes(b"\x89PNG fake"); Path(d, "b.txt").write_text("hi")   # attachments: content-addressed beside the db
    fa = run("attach", b, f"{d}/a.PNG", f"{d}/b.txt", **env).splitlines()
    assert fa[0] == hashlib.sha256(b"\x89PNG fake").hexdigest()[:16] + ".png" and fa[1].endswith(".txt") and Path(d, "t.files", fa[0]).read_bytes() == b"\x89PNG fake", fa
    assert js(run("ls", b, "--json", **env))[0]["tags"]["files"] == ",".join(fa)
    assert run("attach", b, f"{d}/a.PNG", **env) == fa[0] and js(run("ls", b, "--json", **env))[0]["tags"]["files"] == ",".join(fa)   # same bytes -> same name, deduped
    assert run("attach", f"{d}/b.txt", **env) == fa[1] and js(run("ls", "--last", "1", "--json", "--all", **env))[0]["tags"]["files"] == fa[1]   # no id -> last entry
    run("--db", f"{d}/alt.db", "log", "only in alt", **env)                  # --db overrides $JN_DB, either position
    assert ids(run("ls", "alt", "--db", f"{d}/alt.db", **env)) and not ids(run("ls", "alt", **env))
    # jsonl storage: a .jsonl db path is the journal itself (one entry per line, sorted by id), sqlite only in memory
    jl = f"{d}/proj/journal.jsonl"; jenv = {**env, "JN_DB": jl}
    ja = run("todo", "@fitness jsonl pushups", **jenv); jb = run("log", "second @see=#" + ja, **jenv)
    run("close", ja, **jenv); run("tag", jb, "@k=v", **jenv)
    run("edit", ja, stdin="@todo @done\n\nedited body", **jenv)
    lines = Path(jl).read_text().splitlines()
    assert [json.loads(l)["id"] for l in lines] == [1, 2] and Path(jl).read_text().endswith("\n") and not Path(jl + ".tmp").exists(), lines
    assert json.loads(lines[0])["content"] == "edited body" and len(json.loads(lines[0])["history"]) == 2 and len(json.loads(lines[1])["history"]) == 1, lines   # tag is versioned too
    assert all(l == json.dumps(json.loads(l), sort_keys=True) for l in lines)                       # sorted keys, stable
    run("close", ja, **jenv); assert Path(jl).read_text().splitlines() == lines                     # no-op write: bytes identical
    assert "v3" in run("history", ja, **jenv) and "@fitness" in run("history", ja, **jenv)          # history survives a reload
    run("revert", ja, "v1", **jenv); assert "jsonl pushups" in run("show", ja, **jenv)
    assert js(run("ls", jb, "--json", **jenv))[0]["tags"] == {"agent": "claude:s0", "global": None, "k": "v", "project": "demo", "see": "#" + ja, "ws": "sub"}
    assert run("import", stdin=json.dumps({"id": 9, "content": "imported", "tags": {"todo": None}}), **jenv) == "imported 1"
    assert [json.loads(l)["id"] for l in Path(jl).read_text().splitlines()] == [1, 2, 9] and ids(run("ls", "@todo", **jenv)) == ["1", "9"]   # 1 reverted to its @todo-only v1
    Path(d, "proj/.jn").write_text(Path(d, "proj/.jn").read_text() + '[dbs]\njl = "journal.jsonl"\n')   # [dbs] name -> .jsonl, relative to that .jn
    assert ids(run("ls", "imported", "--db=jl", **env)) == ["9"] and ids(run("ls", "--db=jl", "--all", **env)) == ["1", "2", "9"]
    # children: @parent=#N context line in ls, threaded show
    r1 = run("log", "@thr root of the thread", **env)
    r2 = run("log", "@thr @parent=#" + r1 + " first reply", **env)
    r3 = run("log", "@thr @parent=#" + r2 + " nested reply", **env)
    r4 = run("log", "@thr @parent=#999 orphan reply", **env)
    out = run("ls", "@thr", "--all", **env).splitlines()[1:]
    assert ids("h\n" + "\n".join(out)) == [r1, r2, r3, r4], out
    assert out[1].strip() == f"↳ #{r1}  root of the thread", out                 # context line above the reply
    assert out[3].strip() == f"↳ #{r2}  first reply" and out[5].strip() == "↳ #999 (missing)", out
    sl = [l for l in run("show", r1, **env).splitlines() if l.strip().startswith("<-")]
    assert sl[0] == f"<- #{r2} @parent  first reply" and sl[1] == f"  <- #{r3} @parent  nested reply", sl   # @parent backlinks nest by depth
    run("edit", r1, stdin=run("show", r1, **env), **env)                          # indented backlink lines strip on round-trip
    assert js(run("ls", r1, "--json", **env))[0]["content"] == "root of the thread"
    literal = r"\@todo explain \@parent=#42 -\@done \@tail"
    escaped = run("log", literal, "@real", **env)
    before = js(run("ls", escaped, "--json", **env))[0]
    assert before["content"] == literal and "real" in before["tags"]
    assert not {"todo", "parent", "done", "tail"} & before["tags"].keys(), before
    history = run("history", escaped, **env)
    run("edit", escaped, stdin=run("show", escaped, **env), **env)
    assert js(run("ls", escaped, "--json", **env))[0] == before
    assert run("history", escaped, **env) == history  # escaped words remain prose across edits
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
    assert "<!doctype" in urllib.request.urlopen(url + "/?q=%40todo&db=alt").read().decode() and {"name": "mine", "own": False} in post("config")[1]["filters"]
    v = post("vocab")[1]; assert v["done"] == [] and v["x"] == [] and "todo" in v, v
    c = post("config")[1]; assert c["colors"] == {"todo": "#ff0", "due": "#0ff"} and c["favorites"] == ["todo", "due", "home"], c
    r = post("filter", name="hot", expr="@todo --since 1w"); assert {"name": "hot", "own": True} in r[1]["filters"], (r, Path(d, ".jn").read_text())
    assert post("filter", name="hot", expr="tag('x')")[0] == 400 and post("filter", name="a b", expr="@x")[0] == 400   # no python from the web
    r = post("filter", name="fit", expr="@x -@done"); assert r[0] == 200, r
    r = post("ls", args=["--fit", "--all"]); assert r[1] == [], r      # overrides the ~/.jn one in place
    cfg = Path(d, ".jn").read_text()
    assert cfg.count("[filters]") == 1 and 'fit = "@x -@done"' in cfg and 'hot = "@todo --since 1w"' in cfg and "week2" in cfg, cfg
    assert post("filter", name="hot")[0] == 200 and "hot" not in Path(d, ".jn").read_text()
    Path(d, ".jn").write_text(Path(d, ".jn").read_text().replace("[filters]\n", '[filters]\nlive = "@todo"\n', 1)); os.utime(Path(d, ".jn"), ns=(0, 10**18))   # edited on disk: next request sees it, no restart
    assert "live" in [f["name"] for f in post("config")[1]["filters"]]
    assert post("dbs")[1] == ["alt", "jl"] and post("ls", db="alt", args=["--all"])[1][0]["content"] == "in alt" and post("ls", args=["--all"])[1][0]["content"] == "from the web"
    post("log", text="@todo parent task"); post("log", text="@todo @parent=#2 child task"); post("log", text="@todo loose")
    t = post("ls", args=["-@done", "--all", "--tree"])[1]
    assert [(r["id"], r["depth"]) for r in t] == [(4, 0), (2, 0), (3, 1)], t      # newest root first, child under its parent
    assert "depth" not in post("ls")[1][0]
    g = post("roots", args=["-@done", "--by"])[1]      # roots view: pointer tag rolls children up under their root
    assert g["pointer"] and [(x["row"]["id"], x["n"], x["open"]) for x in g["groups"]] == [(4, 0, 0), (2, 1, 1)] and g["groups"][1]["latest"]["id"] == 3, g
    post("log", text="@todo @parent=#3 @sess=s9 grandchild"); post("log", text="@todo @sess=s9 second"); post("log", text="@todo @sess=s8 third")
    g = post("roots", args=["-@done", "--by=parent"])[1]["groups"]; assert [(x["row"]["id"], x["n"]) for x in g if x["row"]["id"] == 2] == [(2, 2)], g   # depth > 1 counts
    g = post("roots", args=["-@done", "--by=sess"])[1]  # value tag: one group per value, entries without it under ""
    assert not g["pointer"] and {x["key"]: x["n"] for x in g["groups"]} == {"s9": 1, "s8": 1, "": 2}, g   # the default filter still hides children
    post("tag", id=6, patch=["@team=core"]); post("tag", id=2, patch=["@team=core"])
    g = post("roots", args=["-@done", "--by=team", "--by=parent"])[1]["groups"]   # nested: parent roots inside each team
    core = next(x for x in g if x["key"] == "core"); assert core["n"] == 2 and [x["row"]["id"] for x in core["sub"]["groups"]] == [6, 2] and core["sub"]["groups"][1]["n"] == 2, g
    post("log", text="just a note")
    g = post("roots", args=["-@done", "--by=todo"])[1]["groups"]                 # a bare tag splits into present / absent
    assert sorted((x["absent"], x["n"]) for x in g) == [(False, 4), (True, 1)], g
    assert post("explain", args=["--tasks", "--default", "--tasks"])[1] == "@todo -@done -@archived -@parent", post("explain", args=["--tasks", "--default"])
    assert post("explain", args=["--tasks", "--since", "2w"])[1] == "@todo -@done -@archived -@parent --since 2w", post("explain", args=["--tasks", "--since", "2w"])
    assert post("ls", db="/nope/x.db")[0] == 400 and post("ls", db="nope")[0] == 400   # names only from the web
    assert post("log", db="jl", text="@todo from the web into jsonl") == (200, 10) and post("tag", db="jl", id=10, patch=["@done"])[0] == 200
    assert post("edit", db="jl", id=9, text="@todo\n\nweb edit")[0] == 200 and post("show", db="jl", id=9)[1]["text"] == "@todo\n\nweb edit\n"
    jrows = {json.loads(l)["id"]: json.loads(l) for l in Path(jl).read_text().splitlines()}
    assert "done" in jrows[10]["tags"] and jrows[9]["content"] == "web edit" and len(jrows[9]["history"]) == 1, jrows
    # A live JSONL server must reload CLI writes before reads AND mutations, without losing old versions.
    jcli = int(run("log", "@todo cli original", **jenv))
    run("edit", str(jcli), stdin="@todo\n\ncli revised", **jenv)
    cli_history = run("history", str(jcli), **jenv)
    r = post("ls", db="jl", args=["--all"])
    assert r[0] == 200 and {e["id"]: e["content"] for e in r[1]}[jcli] == "cli revised", r
    jlate = int(run("log", "@todo cli after web read", **jenv))  # no intervening web read before its write
    before_web = {e["id"]: e for e in js(Path(jl).read_text())}
    r = post("log", db="jl", text="@todo web after cli")
    assert r[0] == 200 and r[1] not in before_web, r
    jweb = r[1]
    cli_rows = {e["id"]: e["content"] for e in js(run("ls", "--all", "--json", **jenv))}
    assert {i: cli_rows[i] for i in (jcli, jlate, jweb)} == {jcli: "cli revised", jlate: "cli after web read", jweb: "web after cli"}, cli_rows
    after_web = {e["id"]: e for e in js(Path(jl).read_text())}
    assert {i: after_web[i] for i in before_web} == before_web  # every preexisting entry, tag and history survives
    assert run("history", str(jcli), **jenv) == cli_history
    # Even malformed external edits must invalidate the cache, never be overwritten by a stale web snapshot.
    saved = Path(jl).read_text(); broken = saved + "{broken\n"
    Path(jl).write_text(broken)
    assert post("ls", db="jl", args=["--all"])[0] == 400
    assert post("log", db="jl", text="must not overwrite malformed journal")[0] == 400
    assert Path(jl).read_text() == broken
    Path(jl).write_text(saved)
    assert post("tag", db="jl", id=jweb, patch=["@recovered"])[0] == 200
    assert "recovered" in js(run("ls", str(jweb), "--json", **jenv))[0]["tags"]
    assert run("history", str(jcli), **jenv) == cli_history
    assert ids(run("ls", "--fit", "--all", **env)) == []
    png = b"\x89PNG\r\n\x1a\n" + b"x" * 8                                    # attachments over HTTP
    def get(p):
        try:
            with urllib.request.urlopen(url + p) as r: return r.status, r.headers["Content-Type"], r.read()
        except urllib.error.HTTPError as e: return e.code, None, None
    r = post("attach", id=1, name="Shot.PNG", data=base64.b64encode(png).decode()); assert r == (200, hashlib.sha256(png).hexdigest()[:16] + ".png"), r
    name = r[1]
    assert post("show", id=1)[1]["row"]["tags"]["files"] == name and Path(d, "web.files", name).is_file()
    assert get("/files/" + name) == (200, "image/png", png)
    assert get("/files/../jn.py")[0] == 404 and get("/files/" + name.upper())[0] == 404 and get("/files/x" + name)[0] == 404 and get("/files/")[0] == 404
    assert get("/files/" + name + "?db=nope")[0] == 400 and get("/files/" + name + "?db=alt")[0] == 404   # alt has its own .files dir
    r = post("attach", id=1, name="n.txt", data=base64.b64encode(b"hi").decode(), db="alt"); assert r[0] == 200, r
    assert get("/files/" + r[1] + "?db=alt") == (200, "text/plain", b"hi") and get("/files/" + r[1])[0] == 404 and get("/files/" + name) == (200, "image/png", png)
    assert post("attach", id=1, name="big.bin", data=base64.b64encode(b"\0" * (21 << 20)).decode())[0] == 400   # 20 MB cap
    assert post("tag", id=1, patch=["@files-=" + name])[0] == 200 and post("show", id=1)[1]["row"]["tags"]["files"] is None
    srv.shutdown()
