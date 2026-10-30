#!/usr/bin/env python3
"""Builds assets/stats.svg, assets/activity.svg and assets/recent.svg from the GitHub API.
Stdlib only, no third-party services. Run with --placeholder to write empty cards."""
import json, os, sys, urllib.request, datetime as dt
from xml.sax.saxutils import escape

USER = os.environ.get("GH_USER", "kryvexo")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
DIR = os.environ.get("OUT_DIR", "assets")
SANS = "-apple-system,'Segoe UI',Helvetica,Arial,sans-serif"
MONO = "ui-monospace,SFMono-Regular,Menlo,Consolas,'DejaVu Sans Mono',monospace"
PALETTE = ["#c084fc", "#f472b6", "#818cf8", "#38bdf8", "#34d399", "#fbbf24"]

def _req(url, data=None):
    req = urllib.request.Request(url, data=data)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "profile-stats")
    if TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)

def api(path):
    return _req("https://api.github.com" + path)

def graphql(query):
    return _req("https://api.github.com/graphql", json.dumps({"query": query}).encode())

def write(name, svg):
    os.makedirs(DIR, exist_ok=True)
    with open(os.path.join(DIR, name), "w") as f:
        f.write(svg)
    print("wrote", name)

def defs():
    return ('<defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#0d0a1c"/><stop offset="1" stop-color="#160a28"/></linearGradient>'
            '<linearGradient id="ln" x1="0" x2="1"><stop offset="0" stop-color="#7c3aed"/><stop offset="1" stop-color="#f472b6"/></linearGradient></defs>')

# ------------------------------------------------------------ stats card
def collect_stats():
    u = api(f"/users/{USER}")
    repos, page = [], 1
    while True:
        chunk = api(f"/users/{USER}/repos?per_page=100&type=owner&page={page}")
        repos += chunk
        if len(chunk) < 100:
            break
        page += 1
    own = [r for r in repos if not r["fork"]]
    langs = {}
    for r in own:
        try:
            for k, v in api(f"/repos/{USER}/{r['name']}/languages").items():
                langs[k] = langs.get(k, 0) + v
        except Exception:
            pass
    def count(path):
        try:
            return api(path)["total_count"]
        except Exception:
            return 0
    return {"repos": u["public_repos"], "followers": u["followers"],
            "stars": sum(r["stargazers_count"] for r in own),
            "commits": count(f"/search/commits?q=author:{USER}&per_page=1"),
            "prs": count(f"/search/issues?q=author:{USER}+type:pr&per_page=1"),
            "langs": langs}

def render_stats(d):
    num = lambda v: "--" if v is None else f"{v:,}"
    items = [("Repositories", d["repos"]), ("Stars earned", d["stars"]), ("Commits", d["commits"]),
             ("Pull requests", d["prs"]), ("Followers", d["followers"])]
    langs = sorted((d["langs"] or {}).items(), key=lambda kv: -kv[1])[:6]
    total = sum(v for _, v in langs) or 1
    W, H = 900, 270
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="GitHub stats" font-family="{SANS}">', defs(),
         f'<rect width="{W}" height="{H}" rx="14" fill="url(#bg)" stroke="#a78bfa" stroke-opacity="0.28"/>',
         '<text x="32" y="44" font-size="16" font-weight="700" fill="#e9d5ff">GitHub, in numbers</text><rect x="32" y="54" width="60" height="3" rx="1.5" fill="url(#ln)"/>']
    for i, (label, val) in enumerate(items):
        y = 96 + i * 32
        o.append(f'<text x="32" y="{y}" font-size="14" fill="#a1a1aa">{label}</text><text x="250" y="{y}" font-size="16" font-weight="700" fill="#f5f3ff" text-anchor="end">{num(val)}</text>')
    o.append('<text x="330" y="44" font-size="16" font-weight="700" fill="#e9d5ff">Languages</text><rect x="330" y="54" width="60" height="3" rx="1.5" fill="url(#ln)"/>')
    o.append('<rect x="330" y="76" width="540" height="12" rx="6" fill="#fff" fill-opacity="0.06"/>')
    cx = 330
    for i, (n, v) in enumerate(langs):
        w = 540 * v / total
        o.append(f'<rect x="{cx:.1f}" y="76" width="0" height="12" fill="{PALETTE[i % 6]}"><animate attributeName="width" from="0" to="{w:.1f}" dur="1.1s" begin="{i*0.15:.2f}s" fill="freeze"/></rect>')
        cx += w
    for i, (n, v) in enumerate(langs):
        lx, ly = 330 + (i % 2) * 270, 124 + (i // 2) * 34
        o.append(f'<circle cx="{lx+5}" cy="{ly-5}" r="5" fill="{PALETTE[i % 6]}"/><text x="{lx+18}" y="{ly}" font-size="14" fill="#e5e7eb">{escape(n)}</text><text x="{lx+250}" y="{ly}" font-size="14" fill="#a1a1aa" text-anchor="end">{v*100/total:.1f}%</text>')
    if not langs:
        o.append('<text x="330" y="130" font-size="14" fill="#71717a">Refreshes automatically every few hours.</text>')
    o.append('</svg>')
    return "".join(o)

# ------------------------------------------------------------ contribution heatmap
def collect_activity():
    q = ('{ user(login: "%s") { contributionsCollection { contributionCalendar { totalContributions '
         'weeks { contributionDays { contributionCount date weekday } } } } } }' % USER)
    cal = graphql(q)["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    return cal["totalContributions"], [w["contributionDays"] for w in cal["weeks"]]

def streaks(weeks):
    days = [d["contributionCount"] for w in weeks for d in w]
    longest = run = 0
    for c in days:
        run = run + 1 if c > 0 else 0
        longest = max(longest, run)
    cur, seq = 0, list(reversed(days))
    if seq and seq[0] == 0:
        seq = seq[1:]
    for c in seq:
        if c > 0: cur += 1
        else: break
    return cur, longest

def render_activity(total, weeks):
    W, H = 1000, 270
    LV = ["#ffffff0d", "#4c1d95", "#6d28d9", "#a855f7", "#f472b6"]
    flat = [d["contributionCount"] for w in weeks for d in w]
    mx = max(flat) if flat and max(flat) > 0 else 1
    def lvl(c):
        if c == 0: return 0
        r = c / mx
        return 1 if r <= .25 else 2 if r <= .5 else 3 if r <= .75 else 4
    cur, longest = streaks(weeks) if weeks else (None, None)
    fmt = lambda v: "--" if v is None else f"{v:,}"
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="Contribution activity" font-family="{SANS}">', defs(),
         f'<rect width="{W}" height="{H}" rx="14" fill="url(#bg)" stroke="#a78bfa" stroke-opacity="0.28"/>']
    for i, (label, val) in enumerate([("contributions, last year", total), ("current streak", cur), ("longest streak", longest)]):
        x = 36 + i * 300
        o.append(f'<text x="{x}" y="48" font-size="28" font-weight="800" fill="#f5f3ff">{fmt(val)}</text><text x="{x}" y="68" font-size="12.5" fill="#a1a1aa">{label}</text>')
    o.append('<rect x="36" y="80" width="60" height="3" rx="1.5" fill="url(#ln)"/>')
    gx, gy, cell, gap = 36, 104, 14, 4
    last_month = None
    for ci, w in enumerate(weeks):
        for d in w:
            x = gx + ci * (cell + gap); y = gy + d["weekday"] * (cell + gap)
            o.append(f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="3" fill="{LV[lvl(d["contributionCount"])]}" opacity="0"><animate attributeName="opacity" from="0" to="1" dur="0.4s" begin="{ci*0.025:.3f}s" fill="freeze"/></rect>')
        m = dt.date.fromisoformat(w[0]["date"]).strftime("%b")
        if m != last_month:
            o.append(f'<text x="{gx + ci*(cell+gap)}" y="{gy-8}" font-size="11" fill="#71717a">{m}</text>'); last_month = m
    ly = H - 24
    o.append(f'<text x="{W-232}" y="{ly+10}" font-size="11" fill="#71717a">less</text>')
    for i, c in enumerate(LV):
        o.append(f'<rect x="{W-198+i*20}" y="{ly}" width="14" height="14" rx="3" fill="{c}"/>')
    o.append(f'<text x="{W-92}" y="{ly+10}" font-size="11" fill="#71717a">more</text>')
    if not weeks:
        o.append('<text x="36" y="150" font-size="14" fill="#71717a">Your contribution map appears after the first workflow run.</text>')
    o.append('</svg>')
    return "".join(o)

# ------------------------------------------------------------ recent activity
def ago(iso):
    t = dt.datetime.fromisoformat(iso.replace("Z", "+00:00"))
    s = int((dt.datetime.now(dt.timezone.utc) - t).total_seconds())
    for n, u in ((86400, "d"), (3600, "h"), (60, "m")):
        if s >= n: return f"{s // n}{u} ago"
    return "just now"

def describe(e):
    repo = e["repo"]["name"].split("/")[-1]; p = e.get("payload", {}); t = e["type"]
    if t == "PushEvent":
        n = len(p.get("commits", [])) or p.get("size", 1)
        return f"pushed {n} commit{'s' if n != 1 else ''} to {repo}"
    if t == "CreateEvent": return f"created {p.get('ref_type', 'repo')} {p.get('ref') or repo}"
    if t == "WatchEvent": return f"starred {repo}"
    if t == "ForkEvent": return f"forked {repo}"
    if t == "PullRequestEvent": return f"{p.get('action', 'opened')} a pull request in {repo}"
    if t == "IssuesEvent": return f"{p.get('action', 'opened')} an issue in {repo}"
    if t == "ReleaseEvent": return f"released {repo}"
    return None

def collect_recent():
    rows = []
    for e in api(f"/users/{USER}/events/public?per_page=50"):
        d = describe(e)
        if d: rows.append((ago(e["created_at"]), d))
        if len(rows) == 6: break
    return rows

def render_recent(rows):
    W, LH = 1000, 30
    H = 76 + max(len(rows), 1) * LH + 24
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="Recent activity" font-family="{MONO}">',
         '<defs><linearGradient id="tb" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#150d26"/><stop offset="1" stop-color="#090512"/></linearGradient></defs>',
         f'<rect width="{W}" height="{H}" rx="14" fill="url(#tb)" stroke="#a78bfa" stroke-opacity="0.3"/>',
         '<circle cx="24" cy="20" r="6" fill="#ff5f56"/><circle cx="46" cy="20" r="6" fill="#ffbd2e"/><circle cx="68" cy="20" r="6" fill="#27c93f"/>',
         f'<text x="{W/2}" y="25" text-anchor="middle" font-size="12" fill="#a1a1aa">git log --live</text>',
         '<circle cx="36" cy="64" r="4" fill="#34d399"><animate attributeName="opacity" values="1;0.2;1" dur="1.6s" repeatCount="indefinite"/></circle>',
         '<text x="50" y="68" font-size="13" fill="#34d399">live from GitHub</text>']
    if not rows:
        o.append('<text x="36" y="110" font-size="14" fill="#71717a">waiting for the first run...</text>')
    for i, (when, what) in enumerate(rows):
        y = 106 + i * LH
        o.append(f'<g opacity="0"><animate attributeName="opacity" from="0" to="1" dur="0.4s" begin="{i*0.25:.2f}s" fill="freeze"/>'
                 f'<text x="36" y="{y}" font-size="14" fill="#c084fc">+</text><text x="56" y="{y}" font-size="14" fill="#e5e7eb">{escape(what)}</text>'
                 f'<text x="{W-36}" y="{y}" font-size="13" fill="#71717a" text-anchor="end">{when}</text></g>')
    o.append('</svg>')
    return "".join(o)

if __name__ == "__main__":
    if "--placeholder" in sys.argv:
        write("stats.svg", render_stats({"repos": None, "stars": None, "commits": None, "prs": None, "followers": None, "langs": {}}))
        write("activity.svg", render_activity(None, []))
        write("recent.svg", render_recent([]))
        sys.exit(0)
    failed = 0
    for name, fn in (("stats.svg", lambda: render_stats(collect_stats())),
                     ("activity.svg", lambda: render_activity(*collect_activity())),
                     ("recent.svg", lambda: render_recent(collect_recent()))):
        try:
            write(name, fn())
        except Exception as ex:
            failed += 1
            print("skipped", name, "->", ex)
    sys.exit(1 if failed == 3 else 0)
