#!/usr/bin/env python3
"""Builds assets/stats.svg from the GitHub API. No third-party services, stdlib only."""
import json, os, sys, urllib.request, urllib.error

USER = os.environ.get("GH_USER", "kryvexo")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
OUT = os.environ.get("OUT", "assets/stats.svg")

def api(path):
    req = urllib.request.Request("https://api.github.com" + path)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "profile-stats")
    if TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)

def collect():
    u = api(f"/users/{USER}")
    repos, page = [], 1
    while True:
        chunk = api(f"/users/{USER}/repos?per_page=100&type=owner&page={page}")
        repos += chunk
        if len(chunk) < 100:
            break
        page += 1
    own = [r for r in repos if not r["fork"]]
    stars = sum(r["stargazers_count"] for r in own)
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
    commits = count(f"/search/commits?q=author:{USER}&per_page=1")
    prs = count(f"/search/issues?q=author:{USER}+type:pr&per_page=1")
    return {
        "repos": u["public_repos"], "followers": u["followers"], "stars": stars,
        "commits": commits, "prs": prs, "langs": langs,
    }

PALETTE = ["#c084fc", "#f472b6", "#818cf8", "#38bdf8", "#34d399", "#fbbf24"]

def render(d):
    def num(v):
        return "--" if v is None else f"{v:,}"
    items = [("Repositories", d["repos"]), ("Stars earned", d["stars"]),
             ("Commits", d["commits"]), ("Pull requests", d["prs"]),
             ("Followers", d["followers"])]
    langs = sorted((d["langs"] or {}).items(), key=lambda kv: -kv[1])[:6]
    total = sum(v for _, v in langs) or 1
    W, H = 900, 270
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="GitHub stats for {USER}" font-family="-apple-system,Segoe UI,Helvetica,Arial,sans-serif">',
           '<defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#0d0a1c"/><stop offset="1" stop-color="#160a28"/></linearGradient>'
           '<linearGradient id="ln" x1="0" x2="1"><stop offset="0" stop-color="#7c3aed"/><stop offset="1" stop-color="#f472b6"/></linearGradient></defs>',
           f'<rect width="{W}" height="{H}" rx="14" fill="url(#bg)" stroke="#a78bfa" stroke-opacity="0.28"/>',
           '<text x="32" y="44" font-size="16" font-weight="700" fill="#e9d5ff">GitHub, in numbers</text>',
           '<rect x="32" y="54" width="60" height="3" rx="1.5" fill="url(#ln)"/>']
    for i, (label, val) in enumerate(items):
        y = 96 + i * 32
        out.append(f'<text x="32" y="{y}" font-size="14" fill="#a1a1aa">{label}</text>')
        out.append(f'<text x="250" y="{y}" font-size="16" font-weight="700" fill="#f5f3ff" text-anchor="end">{num(val)}</text>')
    out.append('<text x="330" y="44" font-size="16" font-weight="700" fill="#e9d5ff">Languages</text>')
    out.append('<rect x="330" y="54" width="60" height="3" rx="1.5" fill="url(#ln)"/>')
    x0, bw = 330, 540
    out.append(f'<rect x="{x0}" y="76" width="{bw}" height="12" rx="6" fill="#ffffff" fill-opacity="0.06"/>')
    cx = x0
    for i, (name, v) in enumerate(langs):
        w = bw * v / total
        c = PALETTE[i % len(PALETTE)]
        begin = f"{i*0.15:.2f}s"
        out.append(f'<rect x="{cx:.1f}" y="76" width="0" height="12" fill="{c}"><animate attributeName="width" from="0" to="{w:.1f}" dur="1.1s" begin="{begin}" fill="freeze"/></rect>')
        cx += w
    for i, (name, v) in enumerate(langs):
        col, row = i % 2, i // 2
        lx, ly = 330 + col * 270, 124 + row * 34
        c = PALETTE[i % len(PALETTE)]
        out.append(f'<circle cx="{lx+5}" cy="{ly-5}" r="5" fill="{c}"/>')
        out.append(f'<text x="{lx+18}" y="{ly}" font-size="14" fill="#e5e7eb">{name}</text>')
        out.append(f'<text x="{lx+250}" y="{ly}" font-size="14" fill="#a1a1aa" text-anchor="end">{v*100/total:.1f}%</text>')
    if not langs:
        out.append('<text x="330" y="130" font-size="14" fill="#71717a">Stats refresh automatically every few hours.</text>')
    out.append('</svg>')
    return "\n".join(out)

if __name__ == "__main__":
    if "--placeholder" in sys.argv:
        data = {"repos": None, "stars": None, "commits": None, "prs": None, "followers": None, "langs": {}}
    else:
        data = collect()
    os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
    open(OUT, "w").write(render(data))
    print("wrote", OUT)
