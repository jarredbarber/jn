"""Smallest check that fails if tag parsing / querying / config discovery breaks. Run: python3 test_jn.py"""
import json, os, subprocess, sys, tempfile
from pathlib import Path

JN = Path(__file__).with_name("jn.py")

def run(*args, stdin=None, **env):
    return subprocess.run([sys.executable, JN, *args], input=stdin, capture_output=True, text=True,
                          env={**os.environ, **env}, cwd=env["CWD"], check=True).stdout.strip()

with tempfile.TemporaryDirectory() as d:
    env = dict(JN_DB=f"{d}/t.db", HOME=d, CWD=f"{d}/proj/sub")
    Path(env["CWD"]).mkdir(parents=True)
    Path(d, "proj/.jn").write_text('tags = ["project=demo"]\n[queries]\nopen = "@todo -@done"\n')
    Path(d, ".jn").write_text('tags = ["global"]\n')

    a = run("todo", "do 10 pushups", "#fitness", **env)
    b = run("log", stdin="# Heading\nwalked @by=claude:s1 @re=" + a, **env)
    run("done", a, **env)
    rows = json.loads(run("ls", "--json", **env))
    t0, t1 = rows[0]["tags"], rows[1]["tags"]
    assert "todo" not in t0 and "done" in t0 and t0["project"] == "demo" and "global" in t0, t0
    assert t1["by"] == "claude:s1" and t1["re"] == a and "Heading" not in t1, t1
    assert run("ls", "open", **env) == ""                                   # named query, nothing open
    assert run("ls", "@by=claude:*", **env).split()[0] == b                 # value glob
    assert run("ls", "pushups", "--since", "today", **env).split()[0] == a  # text + since
    assert run("ls", "-@done", **env).split()[0] == b                       # negation
    run("edit", b, "ran instead @by=claude:s1 @new", **env)   # drops @re (gone from text), keeps @global (from config)
    t1 = json.loads(run("ls", b, "--json", **env))[0]["tags"]
    assert "re" not in t1 and "new" in t1 and "global" in t1 and t1["by"] == "claude:s1", t1
    print("ok")
