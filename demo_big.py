#!/usr/bin/env python3
"""Deterministic ~1000-entry demo journal for jn. Usage: python3 demo_big.py > demo_big.jsonl"""
import json, random, re, uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

R = random.Random(20261024)
NY = ZoneInfo("America/New_York")
END = datetime(2026, 10, 24, 23, 30, tzinfo=NY)
START = datetime(2026, 9, 25, 0, 0, tzinfo=NY)
E = []  # entries; key = index; refs are written as §key§ and remapped to #id at the end

def utc(dt): return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
def add(content, tags, created, updated=None):
    E.append(dict(content=content, tags=tags, created=created, updated=updated or created))
    return len(E) - 1
def ref(k): return f"§{k}§"
def at(day, hour, minute=None):
    return (START + timedelta(days=day)).replace(hour=hour, minute=minute if minute is not None else R.randrange(60), second=R.randrange(60))

PROJ = {
 "webapp": dict(
  objs=["login form", "billing page", "search endpoint", "settings modal", "CSV export", "rate limiter", "session cache", "onboarding flow", "email templates", "audit log", "dark mode", "webhook retries", "pagination", "feature flags", "image uploads"],
  verbs=["fix flaky test in", "refactor", "add tests for", "profile", "implement", "document", "migrate", "review", "debug", "add metrics to"]),
 "infra": dict(
  objs=["postgres replica", "terraform state", "k8s ingress", "secrets rotation", "vpc peering", "cron jobs", "s3 buckets", "dns records", "grafana alerts", "CI runners", "load balancer", "backup policy", "service mesh"],
  verbs=["migrate", "audit", "cut over", "dry-run", "inventory", "write runbook for", "roll back", "provision", "tune", "decommission"]),
 "sidecli": dict(
  objs=["arg parser", "config loader", "--json output", "shell completions", "man page", "update checker", "progress bar", "plugin loader", "error messages", "release script", "fuzzy matcher"],
  verbs=["rewrite", "add tests for", "benchmark", "simplify", "fix edge case in", "implement", "polish", "document"]),
 "reno": dict(
  objs=["kitchen cabinets", "bathroom tile", "electrical panel", "back deck", "paint colors", "permit paperwork", "floor refinishing", "window quotes", "plumbing rough-in", "lighting plan"],
  verbs=["get quote for", "decide on", "order", "schedule", "measure", "inspect", "compare options for", "call about"]),
 "papers": dict(
  objs=["scaling laws survey", "RLHF reward hacking", "retrieval benchmarks", "sparse attention", "eval contamination", "interpretability probes", "tokenization study", "distillation paper"],
  verbs=["read", "summarize", "reproduce figure from", "extract notes from", "compare", "find follow-ups to", "annotate"]),
}
PN = list(PROJ)
WORK = {"webapp", "infra", "sidecli"}

# ---- agent sessions ----
LOGS = ["tests green, {n}/{n}", "found root cause in {o}", "blocked on upstream, moving on", "{o}: done, {n} files touched", "benchmark: {n}ms -> {m}ms",
        "flaky, retried {n}x", "pushed branch, CI running", "{o} needs a decision, see parent", "lint clean after {n} fixes", "skipped {o}, out of scope"]
def logline(o):
    n = R.randrange(3, 40)
    return R.choice(LOGS).format(n=n, m=max(1, n // R.randrange(2, 5)), o=o)

def session(day, hour, ntasks, kind):
    p = R.choice(PN); P = PROJ[p]
    sid = ("claude:" + str(uuid.UUID(int=R.getrandbits(128), version=4))) if kind == "claude" else "agy:" + "%08x" % R.getrandbits(32)
    t = at(day, hour); t = min(t, END - timedelta(hours=4))
    base = {"agent": sid, "project": p}
    head = add(f"{R.choice(['Overhaul','Stabilize','Ship','Clean up','Investigate'])} {R.choice(P['objs'])}", dict(base, todo=None), t)
    nodes = [(head, 0)]; kids = {head: []}; done = {}; allk = [head]
    for _ in range(ntasks):
        t += timedelta(minutes=R.randrange(1, 7), seconds=R.randrange(60))
        par, d = R.choice([x for x in nodes if x[1] < 3 and (x[1] == 0 or R.random() < .6)])
        o = R.choice(P["objs"])
        tags = dict(base, todo=None, parent=ref(par))
        sib = [s for s in kids[par] if R.random() < .5][:R.choice([1, 1, 2])]
        if sib and R.random() < .25: tags["blocked_by"] = ",".join(ref(s) for s in sib)
        k = add(f"{R.choice(P['verbs'])} {o}", tags, t)
        kids[par].append(k); kids[k] = []; nodes.append((k, d + 1)); allk.append(k)
        if R.random() < .45:
            lt = t + timedelta(minutes=R.randrange(1, 15))
            add(logline(o), dict(base, parent=ref(k)), lt); allk.append(len(E) - 1)
    # closing pass
    for k in allk:
        e = E[k]
        if "todo" not in e["tags"]: continue
        blk = [int(x[1:-1]) for x in e["tags"].get("blocked_by", "").split(",") if x]
        ok = R.random() < (.88 if k != head else 1) and all(done.get(b) for b in blk)
        if k == head: ok = all(done.get(c, False) for c in kids[head]) and R.random() < .8
        if ok:
            e["tags"]["done"] = None
            e["updated"] = max(e["created"] + timedelta(minutes=R.randrange(2, 45)), E[k]["updated"])
            done[k] = True
    return sid

def plan_sessions():
    days = []
    for w in range(5):
        pool = list(range(w * 7, min(w * 7 + 7, 30)))
        days += R.sample(pool, min(len(pool), R.choice([3, 4, 5])) if len(pool) == 7 else 1)
    for i, d in enumerate(sorted(days)):
        big = i == 7
        session(d, R.choice([1, 3, 9, 10, 11, 13, 14, 15, 16, 20, 22]), 60 if big else R.randrange(10, 36),
                "agy" if i % 6 == 4 else "claude")
    return len(days)

# ---- human entries ----
ONE = {
 "webapp": ["standup: auth migration slipping a day", "prod error rate back to baseline", "pairing w/ Dana on the cache layer", "need to look at p99 on /search", "deploy went fine, no rollback", "PR #review queue is 9 deep", "hotfix for null avatar crash", "cut v2.14 release notes"],
 "infra": ["cutover rehearsal #2 went clean", "replica lag spiked to 40s again", "terraform plan shows 31 changes, too many", "old VPC still has 3 orphaned ENIs", "alert noise down 60% after tuning", "waiting on security review for the IAM roles"],
 "sidecli": ["side project: shell completions finally work in zsh", "profiled startup, 90ms is mostly imports", "idea: `--watch` flag", "published 0.3.1 to the index", "someone filed an issue about Windows paths", "refactored parser, deleted 200 lines"],
 "reno": ["electrician can come Thursday", "tile samples arrived, the grey one wins", "deck permit approved", "contractor quote came in $2k over", "measured the window openings twice", "paint: Swiss Coffee for the hallway"],
 "papers": ["finished the attention paper, section 4 is the good part", "skimmed 3 papers on eval leakage", "reading group Thursday", "the ablation table is suspicious", "notes on the probing paper are in the doc"],
}
MOOD = ["slept badly, foggy all morning", "good energy today, got deep work done", "headache after lunch", "ran 5k, felt easy", "anxious about the cutover", "tired but fine", "mood 7/10", "skipped the gym, walked instead", "knee feels better", "sleep 6.5h, coffee x3", "great day, finished early", "low energy, stayed off slack"]
HOME = ["fix the leaking kitchen faucet", "buy lightbulbs", "call landlord about the mailbox", "laundry, groceries, dishes", "sourdough starter is alive", "water the ferns", "recycling is Wednesday", "oil change due"]
TODOS = {
 "webapp": ["review Sam's PR", "write migration for user prefs", "update dependency pins", "add alerting for 5xx", "triage the bug backlog"],
 "infra": ["draft rollback plan", "rotate the db credentials", "ask finance about the reserved instances", "update the architecture diagram"],
 "sidecli": ["write README quickstart", "tag 0.4.0", "reply to issue about config paths", "add CI matrix for 3.12"],
 "reno": ["pay deposit to contractor", "pick faucet finish", "email inspector", "return the extra tile"],
 "papers": ["read the RLHF survey", "write 1-page summary for group", "request code from authors", "re-run baseline eval"],
}
LINKS = ["https://news.ycombinator.com/item?id=41{n}", "https://arxiv.org/abs/2410.{n}", "https://example.com/blog/post-{n}", "https://github.com/example/repo/pull/{n}"]
TOPICS = ["roadmap sync", "1:1 with manager", "incident review", "vendor call", "design review", "retro", "contractor walkthrough"]

def human(day, hour, hum):
    t = at(day, hour, 0) + timedelta(minutes=R.randrange(60))
    prior = [k for k in hum if E[k]['created'] < t]
    if t > END: return
    r = R.random(); p = R.choice(PN); work = p in WORK
    if work and t.weekday() >= 5 and R.random() < .8: p = R.choice(["reno", "papers", "sidecli"])
    tags = {"project": p}; txt = ""
    if r < .25:  # todo
        txt = R.choice(TODOS[p]); tags["todo"] = None
        if R.random() < .4: tags["due"] = (t + timedelta(days=R.randrange(1, 14))).strftime("%Y-%m-%d")
        if R.random() < .25: tags["priority"] = R.choice(["high", "high", "low"])
        if R.random() < .1 and prior: tags["blocked_by"] = ref(R.choice(prior))
        k = add(txt, tags, t)
        if R.random() < .6:
            E[k]["tags"]["done"] = None
            E[k]["updated"] = min(t + timedelta(hours=R.randrange(1, 100)), END)
        hum.append(k); return
    if r < .52: txt = R.choice(ONE[p]); 
    elif r < .60: txt = R.choice(MOOD); tags = {R.choice(["health", "health", "mood"]): None}
    elif r < .66: txt = R.choice(HOME); tags = {"home": None}
    elif r < .72: txt = R.choice(LINKS).format(n=R.randrange(1000, 9999)) + " " + R.choice(["worth a read", "for later", "relevant to the migration", "good thread"]); tags["reading"] = None
    elif r < .80:
        tp = R.choice(TOPICS); txt = f"{tp}\n- {R.choice(['agreed to ship Friday','need owner for follow-up','budget unchanged','risk: vendor delay'])}\n- {R.choice(['action: send notes','action: update ticket','open q: who owns alerts?','next sync in 2 weeks'])}\n- attendees: {', '.join(R.sample(['Dana','Sam','Priya','Lee','Marcus'], 3))}"
        tags["meeting"] = None
    elif r < .86:
        txt = f"Decision: {R.choice(['use Postgres logical replication','keep the monolith for now','drop Python 3.9 support','go with the grey tile','defer the deck to spring','adopt weekly reading group'])}\n- why: {R.choice(['lower risk','cheaper','team already knows it','deadline pressure'])}\n- revisit in {R.randrange(2,9)} weeks"
        tags["decision"] = None
    elif r < .92:
        txt = f"## {p} notes\n- ran `{R.choice(['make test','kubectl get pods','jn ls @todo','pytest -x'])}` and it passed\n- remaining: {R.choice(PROJ[p]['objs'])}\n- thought: {R.choice(['keep it simple','measure first','ask Dana'])}"
    elif r < .96 and prior: txt = f"followup on {ref(R.choice(prior))}: {R.choice(['still true','changed my mind','done now','needs a second look'])}"
    else: txt = R.choice(["idea: weekly review template", "quote: simple is hard", "need to stop context switching so much"]); tags = {"idea": None}
    if prior and R.random() < .1: txt += f" (see {ref(R.choice(prior))})"
    if prior and R.random() < .05: tags["parent"] = ref(R.choice(prior))
    hum.append(add(txt, tags, t))

def main():
    hum = []
    # pages first (early)
    pages = [("# Open webapp work", "@todo -@done @project=webapp", "webapp"), ("# Infra board", "@todo -@done @project=infra --by=parent", "infra"), ("# My week", "@todo -@done @due", "webapp")]
    for i, (h, q, p) in enumerate(pages):
        hum.append(add(f"{h}\n\nLive view.\n\n```jn\n{q}\n```", {"page": None, "project": p}, at(i, 8)))
    for day in range(30):
        wd = (START + timedelta(days=day)).weekday()
        for _ in range(R.randrange(10, 16) if wd < 5 else R.randrange(5, 9)):
            human(day, R.choice([7, 8, 9, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22]), hum)
    plan_sessions()
    for e in E:  # archive some older entries
        if e["created"] < START + timedelta(days=18) and "page" not in e["tags"] and R.random() < .05:
            e["tags"]["archived"] = None
    order = sorted(range(len(E)), key=lambda k: (E[k]["created"], k))
    newid = {k: i + 1 for i, k in enumerate(order)}
    sub = lambda s: re.sub(r"§(\d+)§", lambda m: "#%d" % newid[int(m[1])], s)
    for k in order:
        e = E[k]
        tags = {n: (None if v is None else sub(v)) for n, v in sorted(e["tags"].items())}
        print(json.dumps({"id": newid[k], "created": utc(e["created"]), "updated": utc(max(e["updated"], e["created"])),
                          "content": sub(e["content"]), "tags": tags}, sort_keys=True))

main()
