#!/usr/bin/env python3
"""Self-hosted GitHub profile cards for anilcodematrix.

Runs inside GitHub Actions with the built-in GITHUB_TOKEN, queries the
GraphQL API and writes SVG cards into an output folder. No third-party
card service is involved, so the images never go down or hit rate limits.

Usage: python scripts/generate_cards.py --out dist [--fixture data.json]
"""
import argparse
import datetime as dt
import html
import json
import os
import urllib.request

USER = os.environ.get("PROFILE_USER", "anilcodematrix")
FEATURED = [
    "Full-Stack-Development-Assignment",
    "Concept-of-AI-and-Technologies",
    "anil-sharma-daily",
    "anilcodematrix.github.io",
]

# Palette (matches the README theme)
BG = "#0d0221"
BG2 = "#160b33"
BORDER = "#3b1a6e"
TITLE = "#c084fc"
ACCENT = "#a855f7"
DEEP = "#7c3aed"
TEXT = "#e2e8f0"
MUTED = "#a3a3c2"
FONT = "'Segoe UI', Ubuntu, 'Helvetica Neue', Sans-Serif"


# --------------------------------------------------------------- data ----
def gql(query, variables=None):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables or {}}).encode(),
        headers={
            "Authorization": f"bearer {os.environ['GITHUB_TOKEN']}",
            "Content-Type": "application/json",
            "User-Agent": "profile-cards",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        payload = json.load(r)
    if payload.get("errors"):
        raise SystemExit(f"GraphQL error: {payload['errors']}")
    return payload["data"]


MAIN_QUERY = """
query($login: String!) {
  user(login: $login) {
    name login createdAt
    followers { totalCount }
    pullRequests { totalCount }
    issues { totalCount }
    repositories(ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC, first: 100) {
      totalCount
      nodes {
        name description stargazerCount forkCount
        primaryLanguage { name color }
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
    contributionsCollection { contributionYears }
  }
}
"""


def fetch():
    user = gql(MAIN_QUERY, {"login": USER})["user"]
    years = user["contributionsCollection"]["contributionYears"]
    parts = []
    for y in years:
        parts.append(
            f'y{y}: contributionsCollection(from: "{y}-01-01T00:00:00Z", to: "{y}-12-31T23:59:59Z") {{'
            " totalCommitContributions restrictedContributionsCount"
            " contributionCalendar { weeks { contributionDays { date contributionCount } } } }"
        )
    yq = "query($login: String!) { user(login: $login) { " + " ".join(parts) + " } }"
    yearly = gql(yq, {"login": USER})["user"]
    days, commits = {}, 0
    for y in years:
        block = yearly[f"y{y}"]
        commits += block["totalCommitContributions"] + block["restrictedContributionsCount"]
        for w in block["contributionCalendar"]["weeks"]:
            for d in w["contributionDays"]:
                days[d["date"]] = d["contributionCount"]
    return {"user": user, "days": days, "commits": commits}


# ------------------------------------------------------------ helpers ----
def esc(s):
    return html.escape(str(s or ""), quote=True)


def fmt(n):
    return f"{n/1000:.1f}k" if n >= 10000 else f"{n:,}"


def wrap(text, width, lines=2):
    words, out, cur = (text or "").split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > width:
            out.append(cur)
            cur = w
            if len(out) == lines:
                break
        else:
            cur = f"{cur} {w}".strip()
    else:
        if cur:
            out.append(cur)
    if len(out) == lines and len(" ".join(out)) < len(text or "") - 1:
        out[-1] = out[-1].rstrip(".,") + "..."
    return out[:lines]


def frame(w, h, title, body, extra_style=""):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="{esc(title)}">
<title>{esc(title)}</title>
<defs>
  <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0%" stop-color="{BG}"/><stop offset="100%" stop-color="{BG2}"/>
  </linearGradient>
  <linearGradient id="accent" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0%" stop-color="{DEEP}"/><stop offset="100%" stop-color="{TITLE}"/>
  </linearGradient>
</defs>
<style>
  .t {{ font: 600 17px {FONT}; fill: {TITLE}; }}
  .l {{ font: 400 13px {FONT}; fill: {MUTED}; }}
  .v {{ font: 700 14px {FONT}; fill: {TEXT}; }}
  .big {{ font: 800 28px {FONT}; fill: {TEXT}; }}
  .s {{ font: 400 12px {FONT}; fill: {MUTED}; }}
  .fade {{ opacity: 0; animation: fade .6s ease-out forwards; }}
  @keyframes fade {{ to {{ opacity: 1; }} }}
  @keyframes grow {{ from {{ transform: scaleX(0); }} to {{ transform: scaleX(1); }} }}
  {extra_style}
</style>
<rect x=".5" y=".5" rx="12" width="{w-1}" height="{h-1}" fill="url(#bg)" stroke="{BORDER}"/>
<rect x="24" y="50" width="48" height="3" rx="1.5" fill="url(#accent)"/>
<text x="24" y="38" class="t">{esc(title)}</text>
{body}
</svg>"""


# -------------------------------------------------------------- cards ----
def card_overview(data):
    u = data["user"]
    repos = u["repositories"]["nodes"]
    stars = sum(r["stargazerCount"] for r in repos)
    total = sum(data["days"].values())
    rows = [
        ("Total stars earned", stars),
        ("Total commits (all time)", data["commits"]),
        ("Pull requests", u["pullRequests"]["totalCount"]),
        ("Issues", u["issues"]["totalCount"]),
        ("Public repositories", u["repositories"]["totalCount"]),
        ("Followers", u["followers"]["totalCount"]),
    ]
    body = []
    for i, (label, val) in enumerate(rows):
        y = 84 + i * 25
        body.append(
            f'<g class="fade" style="animation-delay:{i*120}ms">'
            f'<circle cx="30" cy="{y-4}" r="4" fill="{ACCENT}"/>'
            f'<text x="44" y="{y}" class="l">{label}</text>'
            f'<text x="290" y="{y}" class="v" text-anchor="end">{fmt(val)}</text></g>'
        )
    # contribution ring
    cx, cy, r = 395, 125, 52
    circ = 2 * 3.14159 * r
    body.append(
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{BORDER}" stroke-width="8"/>'
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="url(#accent)" stroke-width="8" '
        f'stroke-linecap="round" stroke-dasharray="{circ:.1f}" stroke-dashoffset="{circ:.1f}" '
        f'transform="rotate(-90 {cx} {cy})" class="ring"/>'
        f'<text x="{cx}" y="{cy+4}" class="big" text-anchor="middle">{fmt(total)}</text>'
        f'<text x="{cx}" y="{cy+24}" class="s" text-anchor="middle">contributions</text>'
    )
    style = f".ring {{ animation: ring 1.4s ease-out forwards; }} @keyframes ring {{ to {{ stroke-dashoffset: {circ*0.08:.1f}; }} }}"
    return frame(495, 240, "Anil's GitHub Stats", "\n".join(body), style)


def card_languages(data):
    totals, colors = {}, {}
    for r in data["user"]["repositories"]["nodes"]:
        for e in r["languages"]["edges"]:
            n = e["node"]["name"]
            totals[n] = totals.get(n, 0) + e["size"]
            colors[n] = e["node"]["color"] or ACCENT
    top = sorted(totals.items(), key=lambda kv: -kv[1])[:8]
    whole = sum(v for _, v in top) or 1
    body, x = [], 24
    bar_w = 447
    body.append(f'<clipPath id="barclip"><rect x="24" y="72" width="{bar_w}" height="10" rx="5"/></clipPath><g clip-path="url(#barclip)">')
    for name, size in top:
        w = bar_w * size / whole
        body.append(f'<rect x="{x:.1f}" y="72" width="{w+0.5:.1f}" height="10" fill="{colors[name]}"/>')
        x += w
    body.append("</g>")
    for i, (name, size) in enumerate(top):
        col, row = i % 2, i // 2
        px, py = 24 + col * 230, 112 + row * 28
        pct = 100 * size / whole
        body.append(
            f'<g class="fade" style="animation-delay:{i*90}ms">'
            f'<circle cx="{px+5}" cy="{py-4}" r="5" fill="{colors[name]}"/>'
            f'<text x="{px+18}" y="{py}" class="l" style="fill:{TEXT}">{esc(name)}</text>'
            f'<text x="{px+205}" y="{py}" class="s" text-anchor="end">{pct:.1f}%</text></g>'
        )
    h = 112 + ((len(top) + 1) // 2) * 28
    return frame(495, max(h, 240), "Most Used Languages", "\n".join(body))


def streaks(days):
    today = dt.date.today()
    dates = sorted(d for d in days if dt.date.fromisoformat(d) <= today)
    longest = run = 0
    best = (None, None)
    start = None
    for d in dates:
        if days[d] > 0:
            run += 1
            start = start or d
            if run > longest:
                longest, best = run, (start, d)
        else:
            run, start = 0, None
    cur, end = 0, today
    if days.get(today.isoformat(), 0) == 0:
        end = today - dt.timedelta(days=1)
    d = end
    while days.get(d.isoformat(), 0) > 0:
        cur += 1
        d -= dt.timedelta(days=1)
    cur_range = (d + dt.timedelta(days=1), end) if cur else (None, None)
    return cur, cur_range, longest, best, (dates[0] if dates else None)


def nice(d):
    if not d:
        return ""
    d = dt.date.fromisoformat(d) if isinstance(d, str) else d
    return d.strftime("%b %-d, %Y")


def card_streak(data):
    days = data["days"]
    total = sum(days.values())
    cur, cur_range, longest, best, first = streaks(days)
    cols = [
        ("Total Contributions", fmt(total), f"{nice(first)} - Present"),
        ("Current Streak", f"{cur} days", f"{nice(cur_range[0])} - {nice(cur_range[1])}" if cur else "Start one today"),
        ("Longest Streak", f"{longest} days", f"{nice(best[0])} - {nice(best[1])}" if longest else ""),
    ]
    body = []
    for i, (label, val, sub) in enumerate(cols):
        cx = 87 + i * 165
        if i:
            body.append(f'<line x1="{cx-82}" y1="80" x2="{cx-82}" y2="170" stroke="{BORDER}"/>')
        hi = i == 1
        if hi:
            body.append(
                f'<circle cx="{cx}" cy="112" r="34" fill="none" stroke="url(#accent)" stroke-width="5"/>'
                f'<text x="{cx}" y="78" text-anchor="middle" style="font-size:18px">&#128293;</text>'
            )
        body.append(
            f'<g class="fade" style="animation-delay:{i*150}ms">'
            + (f'<text x="{cx}" y="116" class="big" text-anchor="middle" style="font-size:24px">{cur}</text>'
               f'<text x="{cx}" y="131" class="s" text-anchor="middle">days</text>' if hi else
               f'<text x="{cx}" y="118" class="big" text-anchor="middle" style="font-size:24px">{esc(val)}</text>')
            + f'<text x="{cx}" y="166" class="v" text-anchor="middle" style="fill:{TITLE};font-size:13px">{label}</text>'
            f'<text x="{cx}" y="184" class="s" text-anchor="middle" style="font-size:10.5px">{esc(sub)}</text></g>'
        )
    return frame(495, 205, "Contribution Streak", "\n".join(body))


def card_activity(data):
    days = data["days"]
    today = dt.date.today()
    span = [today - dt.timedelta(days=i) for i in range(59, -1, -1)]
    vals = [days.get(d.isoformat(), 0) for d in span]
    peak = max(vals) or 1
    x0, y0, w, h = 40, 70, 920, 150
    step = w / (len(vals) - 1)
    pts = [(x0 + i * step, y0 + h - h * v / peak) for i, v in enumerate(vals)]
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    area = f"{x0},{y0+h} {line} {x0+w},{y0+h}"
    body = [
        f'<defs><linearGradient id="area" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0%" stop-color="{ACCENT}" stop-opacity=".45"/>'
        f'<stop offset="100%" stop-color="{ACCENT}" stop-opacity="0"/></linearGradient></defs>'
    ]
    for g in range(5):
        gy = y0 + h * g / 4
        body.append(f'<line x1="{x0}" y1="{gy:.1f}" x2="{x0+w}" y2="{gy:.1f}" stroke="{BORDER}" stroke-dasharray="3 5"/>')
        body.append(f'<text x="{x0-8}" y="{gy+4:.1f}" class="s" text-anchor="end">{round(peak*(4-g)/4)}</text>')
    body.append(f'<polygon points="{area}" fill="url(#area)" class="fade"/>')
    body.append(f'<polyline points="{line}" fill="none" stroke="{TITLE}" stroke-width="2.5" stroke-linejoin="round" class="draw"/>')
    for i, (x, y) in enumerate(pts):
        if vals[i]:
            body.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="{DEEP}" stroke="{TITLE}" stroke-width="1.5" class="fade"/>')
    for i in range(0, 60, 10):
        body.append(f'<text x="{pts[i][0]:.1f}" y="{y0+h+22}" class="s" text-anchor="middle">{span[i].strftime("%b %-d")}</text>')
    body.append(f'<text x="{x0+w}" y="{y0+h+22}" class="s" text-anchor="end">Today</text>')
    style = ".draw { stroke-dasharray: 4000; stroke-dashoffset: 4000; animation: draw 2.2s ease-out forwards; } @keyframes draw { to { stroke-dashoffset: 0; } }"
    return frame(1000, 260, "Last 60 Days of Contributions", "\n".join(body), style)


def card_repo(repo):
    lang = repo.get("primaryLanguage") or {}
    desc = wrap(repo.get("description") or "No description yet.", 52)
    body = []
    for i, line in enumerate(desc):
        body.append(f'<text x="24" y="{80+i*19}" class="l">{esc(line)}</text>')
    y = 132
    meta = []
    if lang.get("name"):
        meta.append(f'<circle cx="30" cy="{y-4}" r="6" fill="{lang.get("color") or ACCENT}"/>'
                    f'<text x="42" y="{y}" class="s" style="fill:{TEXT}">{esc(lang["name"])}</text>')
    meta.append(f'<text x="200" y="{y}" class="s">&#9733; {repo["stargazerCount"]}</text>'
                f'<text x="250" y="{y}" class="s">&#9906; {repo["forkCount"]}</text>')
    body.extend(meta)
    return frame(400, 150, repo["name"], "\n".join(body))


# --------------------------------------------------------------- main ----
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="dist")
    ap.add_argument("--fixture")
    a = ap.parse_args()
    data = json.load(open(a.fixture)) if a.fixture else fetch()
    os.makedirs(a.out, exist_ok=True)
    cards = {
        "overview.svg": card_overview(data),
        "languages.svg": card_languages(data),
        "streak.svg": card_streak(data),
        "activity.svg": card_activity(data),
    }
    by_name = {r["name"]: r for r in data["user"]["repositories"]["nodes"]}
    for name in FEATURED:
        if name in by_name:
            cards[f"repo-{name}.svg"] = card_repo(by_name[name])
    for fn, svg in cards.items():
        with open(os.path.join(a.out, fn), "w", encoding="utf-8") as f:
            f.write(svg)
        print("wrote", fn)


if __name__ == "__main__":
    main()
