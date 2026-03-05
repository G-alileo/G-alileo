import os
import json
import urllib.request
from datetime import datetime, timezone
from collections import defaultdict

USERNAME = "G-alileo"
TOKEN    = os.environ.get("GITHUB_TOKEN", "")
OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "profile-stats.svg")

HEADERS = {
    "Authorization": f"bearer {TOKEN}",
    "Content-Type":  "application/json",
    "User-Agent":    "profile-stats-generator",
}

BG      = "#0d1117"
BG2     = "#161b22"
BG3     = "#1c2330"
BORDER  = "#30363d"
ACCENT  = "#4fc3f7"
GREEN   = "#7ee787"
ORANGE  = "#ffa657"
YELLOW  = "#e3b341"
RED_S   = "#f78166"
MUTED   = "#8b949e"
TEXT    = "#e6edf3"
DIM     = "#6e7681"
DOT_R   = "#ff5f57"
DOT_Y   = "#febc2e"
DOT_G   = "#28c840"

LANG_COLORS = {
    "Python":           "#3572A5",
    "JavaScript":       "#f1e05a",
    "TypeScript":       "#3178c6",
    "HTML":             "#e34c26",
    "CSS":              "#563d7c",
    "Java":             "#b07219",
    "C++":              "#f34b7d",
    "C":                "#555555",
    "PHP":              "#4F5D95",
    "Shell":            "#89e051",
    "Jupyter Notebook": "#DA5B0B",
    "Makefile":         "#427819",
}

def gql(query, variables=None):
    payload = json.dumps({"query": query, "variables": variables or {}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=payload, headers=HEADERS, method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode())

def fetch_stats():
    q = """
    query($login: String!) {
      user(login: $login) {
        repositories(first: 100, ownerAffiliations: OWNER, isFork: false) {
          nodes {
            stargazerCount
            languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
              edges { size node { name } }
            }
          }
        }
        contributionsCollection {
          totalCommitContributions
          restrictedContributionsCount
          contributionCalendar {
            totalContributions
            weeks { contributionDays { contributionCount date } }
          }
        }
        followers { totalCount }
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
    streak = 0
    for day in days:
        if day["date"] > today_str:
            continue
        if day["contributionCount"] > 0:
            streak += 1
        else:
            break

    commits = (data["contributionsCollection"]["totalCommitContributions"] +
               data["contributionsCollection"]["restrictedContributionsCount"])

    return {
        "stars":         total_stars,
        "followers":     data["followers"]["totalCount"],
        "commits":       commits,
        "contributions": data["contributionsCollection"]["contributionCalendar"]["totalContributions"],
        "streak":        streak,
        "langs":         lang_pcts,
        "grid":          days[:91][::-1],
    }

def build_svg(s):
    W   = 820
    H   = 260
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    stat_items = [
        ("commits",       str(s["commits"]),       ACCENT),
        ("contributions", str(s["contributions"]), GREEN),
        ("streak",        f"{s['streak']} days",   ORANGE),
        ("stars",         str(s["stars"]),          YELLOW),
        ("followers",     str(s["followers"]),      RED_S),
    ]
    CARD_W   = 136
    CARD_H   = 62
    CARD_Y   = 58
    CARD_GAP = 10
    CARDS_TOTAL = len(stat_items) * CARD_W + (len(stat_items) - 1) * CARD_GAP
    card_x0 = (W - CARDS_TOTAL) // 2

    stat_cards = []
    for i, (label, val, color) in enumerate(stat_items):
        cx = card_x0 + i * (CARD_W + CARD_GAP)
        stat_cards.append(
            f'<rect x="{cx}" y="{CARD_Y}" width="{CARD_W}" height="{CARD_H}" rx="8" fill="{BG3}" stroke="{BORDER}" stroke-width="0.8"/>'
            f'<text x="{cx + CARD_W//2}" y="{CARD_Y + 22}" text-anchor="middle" font-size="9" fill="{MUTED}" font-family="\'JetBrains Mono\',monospace" letter-spacing="0.5">{label.upper()}</text>'
            f'<text x="{cx + CARD_W//2}" y="{CARD_Y + 46}" text-anchor="middle" font-size="18" fill="{color}" font-family="\'JetBrains Mono\',monospace" font-weight="700">{val}</text>'
        )
    stat_svg = "\n  ".join(stat_cards)

    LB_X  = 32
    LB_Y0 = 160
    LB_W  = W - 130   
    LB_H  = 8
    ROW_H = 24

    lang_svg_parts = [
        f'<text x="{LB_X}" y="{LB_Y0 - 14}" font-size="9" fill="{DIM}" font-family="\'JetBrains Mono\',monospace" letter-spacing="1">▸ LANGUAGES</text>',
        f'<line x1="{LB_X}" y1="{LB_Y0 - 8}" x2="{W - 20}" y2="{LB_Y0 - 8}" stroke="{BORDER}" stroke-width="0.6"/>',
    ]
    for idx, (lang, pct) in enumerate(s["langs"]):
        col    = idx % 2
        row    = idx // 2
        x      = LB_X + col * (W // 2)
        y      = LB_Y0 + row * ROW_H
        bw     = (LB_W // 2) - 10
        fill   = LANG_COLORS.get(lang, ACCENT)
        bar    = max(4, int(pct / 100 * bw))
        lang_svg_parts.append(
            f'<text x="{x}" y="{y}" font-size="9.5" fill="{MUTED}" font-family="\'JetBrains Mono\',monospace">{lang}</text>'
            f'<rect x="{x}" y="{y + 3}" width="{bw}" height="{LB_H}" rx="4" fill="{BG3}"/>'
            f'<rect x="{x}" y="{y + 3}" width="{bar}" height="{LB_H}" rx="4" fill="{fill}" opacity="0.85"/>'
            f'<text x="{x + bw + 6}" y="{y + 11}" font-size="9" fill="{DIM}" font-family="\'JetBrains Mono\',monospace">{pct}%</text>'
        )
    lang_svg = "\n  ".join(lang_svg_parts)

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%"   stop-color="#0d1117"/>
      <stop offset="100%" stop-color="#111827"/>
    </linearGradient>
  </defs>

  <!-- card -->
  <rect width="{W}" height="{H}" rx="14" fill="url(#bg)"/>
  <rect width="{W}" height="{H}" rx="14" fill="none" stroke="{BORDER}" stroke-width="1"/>

  <!-- title bar -->
  <rect width="{W}" height="44" rx="14" fill="{BG2}"/>
  <rect y="30" width="{W}" height="14" fill="{BG2}"/>
  <rect x="1" y="44" width="{W - 2}" height="1" fill="{BORDER}"/>

  <!-- linux window buttons — right side, elegant line style -->
  <!-- minimize -->
  <rect x="{W - 74}" y="15" width="18" height="16" rx="4" fill="#2a2f3a" stroke="{BORDER}" stroke-width="0.7"/>
  <line x1="{W - 69}" y1="23" x2="{W - 60}" y2="23" stroke="{MUTED}" stroke-width="1.5" stroke-linecap="round"/>
  <!-- maximize -->
  <rect x="{W - 51}" y="15" width="18" height="16" rx="4" fill="#2a2f3a" stroke="{BORDER}" stroke-width="0.7"/>
  <rect x="{W - 46}" y="20" width="8" height="6" rx="1" fill="none" stroke="{MUTED}" stroke-width="1.2"/>
  <!-- close -->
  <rect x="{W - 28}" y="15" width="18" height="16" rx="4" fill="#c0392b" stroke="#a93226" stroke-width="0.7"/>
  <line x1="{W - 23}" y1="19" x2="{W - 15}" y2="27" stroke="white" stroke-width="1.4" stroke-linecap="round"/>
  <line x1="{W - 15}" y1="19" x2="{W - 23}" y2="27" stroke="white" stroke-width="1.4" stroke-linecap="round"/>

  <!-- prompt -->
  <text x="16" y="27" font-size="11" font-family="'JetBrains Mono',monospace" fill="{GREEN}">james@ubuntu</text>
  <text x="114" y="27" font-size="11" font-family="'JetBrains Mono',monospace" fill="{MUTED}">:</text>
  <text x="122" y="27" font-size="11" font-family="'JetBrains Mono',monospace" fill="{ACCENT}">~/G-alileo</text>
  <text x="198" y="27" font-size="11" font-family="'JetBrains Mono',monospace" fill="{MUTED}">$ python stats.py</text>
  <text x="{W - 90}" y="27" text-anchor="end" font-size="9" font-family="'JetBrains Mono',monospace" fill="{DIM}">{now}</text>

  <!-- stat cards -->
  {stat_svg}

  <!-- divider -->
  <line x1="20" y1="136" x2="{W - 20}" y2="136" stroke="{BORDER}" stroke-width="0.6"/>

  <!-- languages -->
  {lang_svg}
</svg>"""

    return svg

if __name__ == "__main__":
    print("Fetching GitHub stats...")
    stats = fetch_stats()
    print(f"  commits={stats['commits']}  streak={stats['streak']}  stars={stats['stars']}")
    svg = build_svg(stats)
    out = os.path.abspath(OUT_PATH)
    with open(out, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"SVG written → {out}")