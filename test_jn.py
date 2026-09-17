"""Smallest check that fails if tag parsing / querying / config discovery breaks. Run: python3 test_jn.py"""
import datetime, json, os, subprocess, sys, tempfile
from pathlib import Path

JN = Path(__file__).with_name("jn.py")

def run(*args, stdin=None, **env):
    return subprocess.run([sys.executable, JN, *args], input=stdin, capture_output=True, text=True,
                          env={**os.environ, **env}, cwd=env["CWD"], check=True).stdout.strip()

with tempfile.TemporaryDirectory() as d:
    env = dict(JN_DB=f"{d}/t.db", HOME=d, CWD=f"{d}/proj/sub")
    Path(env["CWD"]).mkdir(parents=True)
    Path(d, "proj/.jn").write_text('tags = ["project=demo"]\n[actions]\nnote = "log @note $@"\n[filters]\nopen = "@todo -@done"\nevil = "__import__(\'os\').system(\'touch pwned\')"\n')
    Path(d, ".jn").write_text('tags = ["global"]\ntags_expr = "\'@ws=\' + cwd.rsplit(\'/\', 1)[1]"\n[filters]\nfit = "tag(\'@fitness\') == [] and env(\'$JN_DB\')"\n')
    Path(d, "proj/sub/.jn").write_text('tags_expr = "[\'@evil\']"\n')  # must be ignored

    ids = lambda out: [l.split()[0] for l in out.splitlines()[1:]]      # skip table header
    a = run("todo", "@fitness do 10 pushups", "@daily", **env)
    b = run("log", stdin="# Heading\nwalked @by=claude:s1 @re=#" + a, **env)
    run("close", a, **env)
    rows = json.loads(run("ls", "--json", **env))
    assert rows[0]["content"] == "do 10 pushups" and rows[1]["content"] == "# Heading\nwalked", rows
    t0, t1 = rows[0]["tags"], rows[1]["tags"]
    assert t0["ws"] == "sub" and "evil" not in t0, t0
    assert "todo" not in t0 and "done" in t0 and t0["project"] == "demo" and "global" in t0, t0
    assert t1["by"] == "claude:s1" and t1["re"] == "#" + a and "Heading" not in t1, t1
    assert run("ls", "--open", **env) == ""                                 # token filter from project .jn, nothing open
    assert ids(run("ls", "@by=claude:*", **env))[0] == b                 # value glob
    assert ids(run("ls", "pushups", "--since", "today", **env))[0] == a  # text + since
    assert ids(run("ls", "-@done", **env))[0] == b                       # negation
    assert run("show", **env) == run("show", b, **env)                     # no id -> last entry
    bl = subprocess.run([sys.executable, JN, "show", a], capture_output=True, text=True, env={**os.environ, **env}, cwd=env["CWD"]).stderr
    assert bl == f"← #{b} @re\n", bl                                       # backlinks on stderr
    run("edit", stdin=run("show", **env).replace("walked", "ran") + " @new", **env)   # round-trip edit keeps tags
    e = json.loads(run("ls", b, "--json", **env))[0]
    assert e["content"] == "# Heading\nran" and e["tags"]["re"] == "#" + a and "new" in e["tags"] and e["tags"]["by"] == "claude:s1", e
    run("edit", b, "ran instead @by=claude:s1 @new", **env)   # args = whole entry: tags not mentioned are gone
    t1 = json.loads(run("ls", b, "--json", **env))[0]["tags"]
    assert t1 == {"by": "claude:s1", "new": None}, t1
    run("edit", b, stdin=run("show", b, **env), **env)         # no-op edit adds no history
    h = run("history", b, **env)
    assert "v4" not in h, h
    ha = run("history", a, **env)
    assert "@todo" in ha.split("v2")[0] and "@done" in ha.split("v2")[1], ha   # done flip is versioned
    run("close", a, **env)                                                     # idempotent flip: no new version
    assert "v3" not in run("history", a, **env)
    assert h.index("walked") < h.index("ran instead") and "v3" in h, h
    c = run("todo", "@due=tomorrow call dentist", **env)
    tc = json.loads(run("ls", c, "--json", **env))[0]["tags"]
    assert tc["due"] == (datetime.date.today() + datetime.timedelta(days=1)).isoformat(), tc
    assert ids(run("ls", "@due=" + tc["due"], **env))[0] == c and ids(run("ls", "@due=tomorrow", **env))[0] == c
    assert len(ids(run("ls", "--since", "1d", **env))) == 3                # bare N is past for --since
    pr = run("log", "see #1 and #2", **env)
    assert json.loads(run("ls", pr, "--json", **env))[0]["content"] == "see #1 and #2"   # #N is prose, not a tag
    assert b not in ids(run("ls", "--mine", **env)) and a in ids(run("ls", "--mine", **env))
    assert ids(run("ls", "--mine", JN_TAGS="@by=claude:s1", **env)) == [b]
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
    assert ids(run("ls", "--fit", **env)) == [a]                            # custom filter from ~/.jn
    run("tag", z, "@blocked_by+=#7,#420", "@seen+=x", **env)               # append dedup, create on +=
    tz = json.loads(run("ls", z, "--json", **env))[0]["tags"]
    assert tz["blocked_by"] == "#420,#7" and tz["seen"] == "x", tz
    run("tag", z, "@blocked_by-=#420,#7", "@nope-=x", **env)               # emptied tag stays; -= on absent is a no-op
    tz = json.loads(run("ls", z, "--json", **env))[0]["tags"]
    assert tz["blocked_by"] is None and "nope" not in tz, tz
    h = run("-h", **env)
    assert "--evil" not in h and not Path(d, "proj/sub/pwned").exists()   # python filter in project .jn ignored
    rd = str(Path(d).resolve())
    assert next(l for l in h.splitlines() if l.startswith("config:")).split(", ")[1:] == [f"{rd}/{x}" for x in (".jn", "proj/.jn", "proj/sub/.jn")], (h, rd)
    assert "fit" in h and "unblocked" in h and "open" in h, h
    n = run("note", "@k=v", stdin="body from stdin", **env)                  # custom action; tag-only args read stdin
    e = json.loads(run("ls", n, "--json", **env))[0]
    assert e["content"] == "body from stdin" and e["tags"]["note"] is None and e["tags"]["k"] == "v", e
    assert "  note           log @note $@" in h, h
    print("ok")
