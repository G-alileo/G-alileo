import os
import json
import urllib.request
import urllib.error
from datetime import datetime, timezone
from collections import defaultdict

USERNAME  = "G-alileo"
TOKEN     = os.environ.get("GITHUB_TOKEN", "")
OUT_PATH  = os.path.join(os.path.dirname(__file__), "..", "profile-stats.svg")

HEADERS = {
    "Authorization": f"bearer {TOKEN}",
    "Content-Type":  "application/json",
    "User-Agent":    "profile-stats-generator",
}

BG          = "#0d1117"
BG2         = "#161b22"
BG3         = "#1f2937"
BORDER      = "#30363d"
ACCENT      = "#4fc3f7"
ACCENT2     = "#7ee787"
ACCENT3     = "#f78166"
MUTED       = "#8b949e"
TEXT        = "#e6edf3"
TEXT_DIM    = "#6e7681"
DOT_RED     = "#ff5f57"
DOT_YEL     = "#febc2e"
DOT_GRN     = "#28c840"

LANG_COLORS = {
    "Python":     "#3572A5",
    "JavaScript": "#f1e05a",
    "TypeScript": "#3178c6",
    "HTML":       "#e34c26",
    "CSS":        "#563d7c",
    "Java":       "#b07219",
    "C++":        "#f34b7d",
    "C":          "#555555",
    "PHP":        "#4F5D95",
    "Shell":      "#89e051",
    "Dockerfile": "#384d54",
    "Makefile":   "#427819",
}

def gql(query, variables=None):
    payload = json.dumps({"query": query, "variables": variables or {}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=payload,
        headers=HEADERS,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode())

def fetch_stats():
    q = """
    query($login: String!) {
      user(login: $login) {
        name
        repositories(first: 100, ownerAffiliations: OWNER, isFork: false) {
          nodes {
            stargazerCount
            languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
              edges { size node { name color } }
            }
          }
        }
        contributionsCollection {
          totalCommitContributions
          totalPullRequestContributions
          restrictedContributionsCount
          contributionCalendar {
            totalContributions
            weeks {
              contributionDays {
                contributionCount
                date
              }
            }
          }
        }
        followers { totalCount }
        following { totalCount }
      }
    }
    """
    data = gql(q, {"login": USERNAME})["data"]["user"]

    lang_bytes = defaultdict(int)
    total_stars = 0
    for repo in data["repositories"]["nodes"]:
        total_stars += repo["stargazerCount"]
        for edge in repo["languages"]["edges"]:
            lang_bytes[edge["node"]["name"]] += edge["size"]

    total_bytes = sum(lang_bytes.values()) or 1
    top_langs = sorted(lang_bytes.items(), key=lambda x: x[1], reverse=True)[:6]
    lang_pcts = [(n, round(b / total_bytes * 100, 1)) for n, b in top_langs]

    days = []
    for week in data["contributionsCollection"]["contributionCalendar"]["weeks"]:
        days.extend(week["contributionDays"])
    days.sort(key=lambda d: d["date"], reverse=True)

    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    current_streak = 0
    for day in days:
        if day["date"] > today_str:
            continue
        if day["contributionCount"] > 0:
            current_streak += 1
        else:
            break

    total_contributions = data["contributionsCollection"]["contributionCalendar"]["totalContributions"]
    commits = data["contributionsCollection"]["totalCommitContributions"] + \
              data["contributionsCollection"]["restrictedContributionsCount"]

    grid_days = days[:91][::-1]

    return {
        "name":          data["name"] or USERNAME,
        "stars":         total_stars,
        "followers":     data["followers"]["totalCount"],
        "commits":       commits,
        "contributions": total_contributions,
        "streak":        current_streak,
        "langs":         lang_pcts,
        "grid":          grid_days,
    }

def build_svg(s):
    W, H = 820, 340
    now  = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    grid_cells = []
    CELL = 9
    GAP  = 2
    grid_x0 = 32
    grid_y0 = 270
    levels = [0, 2, 5, 10]
    colors = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"]

    for i, day in enumerate(s["grid"]):
        col = i // 7
        row = i %  7
        x   = grid_x0 + col * (CELL + GAP)
        y   = grid_y0 + row * (CELL + GAP)
        c   = day["contributionCount"]
        if   c == 0: clr = colors[0]
        elif c < 3:  clr = colors[1]
        elif c < 6:  clr = colors[2]
        elif c < 10: clr = colors[3]
        else:         clr = colors[4]
        grid_cells.append(
            f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" '
            f'rx="2" fill="{clr}" opacity="0.9"/>'
        )
    grid_svg = "\n    ".join(grid_cells)

    lang_bars = []
    BAR_X  = 460
    BAR_Y0 = 110
    BAR_W  = 320
    BAR_H  = 10
    for idx, (lang, pct) in enumerate(s["langs"]):
        y      = BAR_Y0 + idx * 30
        fill   = LANG_COLORS.get(lang, ACCENT)
        filled = max(4, int(pct / 100 * BAR_W))
        lang_bars.append(f"""
    <text x="{BAR_X}" y="{y - 2}" font-size="11" fill="{MUTED}" font-family="'JetBrains Mono',monospace">{lang}</text>
    <rect x="{BAR_X}" y="{y + 2}" width="{BAR_W}" height="{BAR_H}" rx="5" fill="{BG3}"/>
    <rect x="{BAR_X}" y="{y + 2}" width="{filled}" height="{BAR_H}" rx="5" fill="{fill}" opacity="0.9"/>
    <text x="{BAR_X + BAR_W + 8}" y="{y + 11}" font-size="10" fill="{TEXT_DIM}" font-family="'JetBrains Mono',monospace">{pct}%</text>""")
    lang_svg = "".join(lang_bars)

    stats = [
        ("total_commits",       str(s["commits"]),       ACCENT,  "commits"),
        ("contributions",       str(s["contributions"]), ACCENT2, "this year"),
        ("current_streak",      str(s["streak"]),        "#ffa657","days"),
        ("stars_earned",        str(s["stars"]),         "#e3b341","stars"),
        ("followers",           str(s["followers"]),     ACCENT3, "followers"),
    ]
    stat_rows = []
    for i, (key, val, color, label) in enumerate(stats):
        y = 118 + i * 28
        stat_rows.append(f"""
    <text x="34" y="{y}" font-size="11" fill="{TEXT_DIM}" font-family="'JetBrains Mono',monospace">{key}</text>
    <text x="200" y="{y}" font-size="11" fill="{color}" font-family="'JetBrains Mono',monospace" font-weight="700">{val} <tspan fill="{MUTED}" font-weight="400">{label}</tspan></text>""")
    stat_svg = "".join(stat_rows)

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">
  <defs>
    <linearGradient id="bg_grad" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%"   stop-color="#0d1117"/>
      <stop offset="100%" stop-color="#111827"/>
    </linearGradient>
    <filter id="glow">
      <feGaussianBlur stdDeviation="2.5" result="blur"/>
      <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
  </defs>

  <!-- background -->
  <rect width="{W}" height="{H}" rx="14" fill="url(#bg_grad)"/>
  <rect width="{W}" height="{H}" rx="14" fill="none" stroke="{BORDER}" stroke-width="1"/>

  <!-- title bar -->
  <rect width="{W}" height="42" rx="14" fill="{BG2}"/>
  <rect y="28" width="{W}" height="14" fill="{BG2}"/>
  <rect x="1" y="42" width="{W-2}" height="1" fill="{BORDER}"/>

  <!-- traffic lights -->
  <circle cx="22" cy="21" r="6" fill="{DOT_RED}"/>
  <circle cx="42" cy="21" r="6" fill="{DOT_YEL}"/>
  <circle cx="62" cy="21" r="6" fill="{DOT_GRN}"/>

  <!-- title -->
  <text x="{W//2}" y="26" text-anchor="middle" font-size="12"
        font-family="'JetBrains Mono',monospace" fill="{MUTED}">
    ~/G-alileo/stats.py — last updated {now}
  </text>

  <!-- LEFT PANEL — stats ──────────────────────────────────────── -->
  <text x="34" y="80" font-size="10" fill="{TEXT_DIM}" font-family="'JetBrains Mono',monospace" letter-spacing="1">▸ OVERVIEW</text>
  <line x1="34" y1="86" x2="420" y2="86" stroke="{BORDER}" stroke-width="0.8"/>
  {stat_svg}

  <!-- DIVIDER -->
  <line x1="440" y1="58" x2="440" y2="{H - 20}" stroke="{BORDER}" stroke-width="0.8"/>

  <!-- RIGHT PANEL — languages ─────────────────────────────────── -->
  <text x="{BAR_X}" y="80" font-size="10" fill="{TEXT_DIM}" font-family="'JetBrains Mono',monospace" letter-spacing="1">▸ LANGUAGES</text>
  <line x1="{BAR_X}" y1="86" x2="{W - 20}" y2="86" stroke="{BORDER}" stroke-width="0.8"/>
  {lang_svg}

  <!-- BOTTOM — contribution grid ───────────────────────────────── -->
  <line x1="20" y1="258" x2="{W - 20}" y2="258" stroke="{BORDER}" stroke-width="0.8"/>
  <text x="34" y="252" font-size="10" fill="{TEXT_DIM}" font-family="'JetBrains Mono',monospace" letter-spacing="1">▸ CONTRIBUTIONS  last 13 weeks</text>
  {grid_svg}

  <!-- streak badge -->
  <rect x="{W - 160}" y="265" width="140" height="52" rx="8" fill="{BG3}" stroke="{BORDER}" stroke-width="0.8"/>
  <text x="{W - 90}" y="285" text-anchor="middle" font-size="9" fill="{MUTED}" font-family="'JetBrains Mono',monospace">current_streak</text>
  <text x="{W - 90}" y="308" text-anchor="middle" font-size="22" fill="#ffa657" font-family="'JetBrains Mono',monospace" font-weight="700" filter="url(#glow)">{s["streak"]}</text>
</svg>"""

    return svg

if __name__ == "__main__":
    print("Fetching GitHub stats...")
    stats = fetch_stats()
    print(f"  commits={stats['commits']}  streak={stats['streak']}  stars={stats['stars']}")
    print(f"  top langs: {[l[0] for l in stats['langs']]}")

    svg = build_svg(stats)
    out = os.path.abspath(OUT_PATH)
    with open(out, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"SVG written → {out}")