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
    Path(d, "proj/.jn").write_text('tags = ["project=demo"]\n[queries]\nopen = "@todo -@done"\n')
    Path(d, ".jn").write_text('tags = ["global"]\ntags_cmd = "echo @ws=${PWD##*/}"\n')
    Path(d, "proj/sub/.jn").write_text('tags_cmd = "echo @evil"\n')  # must be ignored

    a = run("todo", "@fitness do 10 pushups", "#daily", **env)
    b = run("log", stdin="# Heading\nwalked @by=claude:s1 @re=" + a, **env)
    run("done", a, **env)
    rows = json.loads(run("ls", "--json", **env))
    assert rows[0]["content"] == "do 10 pushups" and rows[1]["content"] == "# Heading\nwalked", rows
    t0, t1 = rows[0]["tags"], rows[1]["tags"]
    assert t0["ws"] == "sub" and "evil" not in t0, t0
    assert "todo" not in t0 and "done" in t0 and t0["project"] == "demo" and "global" in t0, t0
    assert t1["by"] == "claude:s1" and t1["re"] == a and "Heading" not in t1, t1
    assert run("ls", "open", **env) == ""                                   # named query, nothing open
    assert run("ls", "@by=claude:*", **env).split()[0] == b                 # value glob
    assert run("ls", "pushups", "--since", "today", **env).split()[0] == a  # text + since
    assert run("ls", "-@done", **env).split()[0] == b                       # negation
    assert run("show", **env) == run("show", b, **env)                     # no id -> last entry
    run("edit", stdin=run("show", **env).replace("walked", "ran") + " @new", **env)   # round-trip edit keeps tags
    e = json.loads(run("ls", b, "--json", **env))[0]
    assert e["content"] == "# Heading\nran" and e["tags"]["re"] == a and "new" in e["tags"] and e["tags"]["by"] == "claude:s1", e
    run("edit", b, "ran instead @by=claude:s1 @new", **env)   # args = whole entry: tags not mentioned are gone
    t1 = json.loads(run("ls", b, "--json", **env))[0]["tags"]
    assert t1 == {"by": "claude:s1", "new": None}, t1
    h = run("history", b, **env)
    assert h.index("walked") < h.index("ran instead") and "v3" in h, h
    c = run("todo", "@due=tomorrow call dentist", **env)
    tc = json.loads(run("ls", c, "--json", **env))[0]["tags"]
    assert tc["due"] == (datetime.date.today() + datetime.timedelta(days=1)).isoformat(), tc
    assert run("ls", "@due=" + tc["due"], **env).split()[0] == c and run("ls", "@due=tomorrow", **env).split()[0] == c
    assert run("ls", "--since", "1d", **env).count("\n") == 2                # bare N is past for --since
    print("ok")
