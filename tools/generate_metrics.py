#!/usr/bin/env python3
"""Render a GitHub metrics panel as SVG, straight from the API.

Every number here is queried live - nothing is hard-coded - so the panel can
never drift from the account it describes.

Usage:  GITHUB_TOKEN=... python generate_metrics.py <username> <out-dir>
"""

import datetime
import glob
import json
import os
import re
import sys
import urllib.request

W = 700
PAD = 22
COL2 = 372
LINE = 25
ICON = 15

THEMES = {
    "dark": {"fg": "#c9d1d9", "dim": "#8b949e", "head": "#58a6ff",
             "rule": "#21262d", "empty": "#161b22"},
    "light": {"fg": "#24292f", "dim": "#57606a", "head": "#0969da",
              "rule": "#d0d7de", "empty": "#ebedf0"},
}

QUERY = """
query($login: String!) {
  user(login: $login) {
    login name createdAt
    followers { totalCount } following { totalCount }
    starredRepositories { totalCount } watching { totalCount }
    organizations { totalCount } sponsoring { totalCount } sponsors { totalCount }
    repositories(first: 100, ownerAffiliations: OWNER) {
      totalCount totalDiskUsage
      nodes {
        stargazerCount forkCount
        watchers { totalCount } releases { totalCount } packages { totalCount }
        licenseInfo { spdxId }
        languages(first: 20, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
    contributionsCollection {
      totalCommitContributions totalPullRequestContributions
      totalPullRequestReviewContributions totalIssueContributions
      totalRepositoriesWithContributedCommits
      contributionCalendar { weeks { contributionDays { contributionCount } } }
    }
    issueComments { totalCount }
  }
}
"""


def fetch(login, token):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": login}}).encode(),
        headers={"Authorization": f"bearer {token}",
                 "Content-Type": "application/json",
                 "User-Agent": "metrics-panel"},
    )
    with urllib.request.urlopen(req) as resp:
        payload = json.load(resp)
    if "errors" in payload:
        raise SystemExit(f"GraphQL error: {payload['errors']}")
    return payload["data"]["user"]


def load_icons():
    """Octicon path data, keyed by icon name."""
    icons = {}
    here = os.path.dirname(os.path.abspath(__file__))
    for path in glob.glob(os.path.join(here, "octicons", "*.svg")):
        svg = open(path, encoding="utf-8").read()
        paths = re.findall(r"<path[^>]*d=\"([^\"]+)\"", svg)
        icons[os.path.basename(path)[:-4]] = paths
    return icons


def plural(n, word):
    return f"{n} {word}{'' if n == 1 else 's'}"


def humanise_age(created):
    days = (datetime.date.today() - created).days
    if days >= 730:
        return f"{days // 365} years ago"
    if days >= 365:
        return "1 year ago"
    if days >= 60:
        return f"{days // 30} months ago"
    return f"{days} days ago"


class Canvas:
    """Tiny helper so the layout code reads as a list of rows."""

    def __init__(self, theme, icons):
        self.t, self.icons, self.out = theme, icons, []

    def icon(self, name, x, y, colour=None):
        for d in self.icons.get(name, []):
            self.out.append(
                f'<path transform="translate({x},{y}) scale({ICON / 16:.4f})" '
                f'd="{d}" fill="{colour or self.t["dim"]}"/>'
            )

    def row(self, x, y, icon, text, colour=None, size=13, weight=400):
        self.icon(icon, x, y - ICON + 3)
        self.out.append(
            f'<text x="{x + ICON + 8}" y="{y}" font-size="{size}" '
            f'font-weight="{weight}" fill="{colour or self.t["fg"]}">{text}</text>'
        )

    def heading(self, x, y, icon, text):
        self.row(x, y, icon, text, colour=self.t["head"], size=14, weight=600)

    def text(self, x, y, s, colour=None, size=11, anchor="start", style=""):
        self.out.append(
            f'<text x="{x}" y="{y}" font-size="{size}" text-anchor="{anchor}" '
            f'fill="{colour or self.t["dim"]}" {style}>{s}</text>'
        )


def render(u, theme_name, icons):
    t = THEMES[theme_name]
    c = Canvas(t, icons)
    cc = u["contributionsCollection"]
    repos = u["repositories"]
    nodes = repos["nodes"]

    created = datetime.date.fromisoformat(u["createdAt"][:10])
    disk_mb = repos["totalDiskUsage"] / 1024
    licences = [(n["licenseInfo"] or {}).get("spdxId") for n in nodes]
    common = max(set(licences), key=licences.count) if licences else None
    licence_text = f"Prefers {common} license" if common else "No preferred license"

    langs, colours = {}, {}
    for n in nodes:
        for e in n["languages"]["edges"]:
            langs[e["node"]["name"]] = langs.get(e["node"]["name"], 0) + e["size"]
            colours[e["node"]["name"]] = e["node"]["color"] or t["dim"]
    total_bytes = sum(langs.values()) or 1
    ordered = sorted(langs.items(), key=lambda kv: -kv[1])

    # ---------------------------------------------------------- left column
    x, y = PAD, 34
    c.out.append(
        f'<circle cx="{x + 8}" cy="{y - 5}" r="9" fill="{t["head"]}" opacity="0.25"/>'
        f'<text x="{x + 8}" y="{y - 1}" font-size="10" text-anchor="middle" '
        f'fill="{t["head"]}" font-weight="700">'
        f'{(u["name"] or u["login"])[0].upper()}</text>'
    )
    c.out.append(
        f'<text x="{x + 24}" y="{y}" font-size="17" font-weight="700" '
        f'fill="{t["head"]}">{u["name"] or u["login"]}</text>'
    )
    y += LINE
    c.row(x, y, "clock", f"Joined GitHub {humanise_age(created)}")
    y += LINE
    c.row(x, y, "people", f"Followed by {plural(u['followers']['totalCount'], 'user')}")

    y += LINE + 12
    c.heading(x, y, "graph", "Activity")
    for icon, text in [
        ("git-commit", plural(cc["totalCommitContributions"], "Commit")),
        ("git-pull-request-closed",
         f"{cc['totalPullRequestReviewContributions']} Pull "
         f"request{'' if cc['totalPullRequestReviewContributions'] == 1 else 's'} reviewed"),
        ("git-pull-request",
         f"{cc['totalPullRequestContributions']} Pull "
         f"request{'' if cc['totalPullRequestContributions'] == 1 else 's'} opened"),
        ("issue-opened",
         f"{cc['totalIssueContributions']} "
         f"Issue{'' if cc['totalIssueContributions'] == 1 else 's'} opened"),
        ("comment", plural(u["issueComments"]["totalCount"], "issue comment")),
    ]:
        y += LINE
        c.row(x, y, icon, text)

    y += LINE + 12
    c.heading(x, y, "repo", plural(repos["totalCount"], "Repositorie").replace("Repositories", "Repositories"))
    for icon, text in [
        ("law", licence_text),
        ("tag", plural(sum(n["releases"]["totalCount"] for n in nodes), "Release")),
        ("package", plural(sum(n["packages"]["totalCount"] for n in nodes), "Package")),
        ("database", f"{disk_mb:.2f} MB used"),
    ]:
        y += LINE
        c.row(x, y, icon, text)

    y += LINE + 12
    c.heading(x, y, "code", plural(len(langs), "Language"))
    lang_top = y + 22

    # --------------------------------------------------------- right column
    x2, y2 = COL2, 30
    weeks = cc["contributionCalendar"]["weeks"][-16:]
    peak = max((sum(d["contributionCount"] for d in w["contributionDays"])
                for w in weeks), default=0) or 1
    for i, wk in enumerate(weeks):
        n = sum(d["contributionCount"] for d in wk["contributionDays"])
        ratio = n / peak
        fill = t["empty"] if not n else (
            "#0e4429" if ratio < .25 else "#006d32" if ratio < .5
            else "#26a641" if ratio < .75 else "#39d353")
        c.out.append(f'<rect x="{x2 + i * 17}" y="{y2 - 11}" width="13" '
                     f'height="13" rx="3" fill="{fill}"/>')
    y2 += LINE + 6
    c.row(x2, y2, "repo-forked",
          f"Contributed to {plural(cc['totalRepositoriesWithContributedCommits'], 'repositorie').replace('repositories','repositories')}")

    y2 += LINE + 12
    c.heading(x2, y2, "organization", "Community stats")
    for icon, text in [
        ("organization",
         f"Member of {plural(u['organizations']['totalCount'], 'organization')}"),
        ("people", f"Following {plural(u['following']['totalCount'], 'user')}"),
        ("heart", f"Sponsoring {plural(u['sponsoring']['totalCount'], 'repositorie').replace('repositories','repositories')}"),
        ("star", f"Starred {plural(u['starredRepositories']['totalCount'], 'repositorie').replace('repositories','repositories')}"),
        ("eye", f"Watching {plural(u['watching']['totalCount'], 'repositorie').replace('repositories','repositories')}"),
    ]:
        y2 += LINE
        c.row(x2, y2, icon, text)

    y2 += LINE + 16
    for icon, text in [
        ("heart", plural(u["sponsors"]["totalCount"], "Sponsor")),
        ("star", plural(sum(n["stargazerCount"] for n in nodes), "Stargazer")),
        ("repo-forked", plural(sum(n["forkCount"] for n in nodes), "Forker")),
        ("eye", plural(sum(n["watchers"]["totalCount"] for n in nodes), "Watcher")),
    ]:
        c.row(x2, y2, icon, text)
        y2 += LINE

    # ------------------------------------------------------- language block
    y = lang_top
    c.text(W / 2, y, "Most used languages", t["head"], 13, "middle")
    y += 16
    c.text(W / 2, y,
           f"measured across {total_bytes / 1024:.0f} KB of code in "
           f"{repos['totalCount']} repositories", t["dim"], 10, "middle")
    y += 14

    bar_x, bar_w = PAD, W - PAD * 2
    c.out.append(f'<clipPath id="bar"><rect x="{bar_x}" y="{y}" width="{bar_w}" '
                 f'height="9" rx="4.5"/></clipPath>')
    cursor = bar_x
    for name, size in ordered:
        seg = bar_w * size / total_bytes
        c.out.append(f'<rect x="{cursor:.2f}" y="{y}" width="{max(seg, 0.6):.2f}" '
                     f'height="9" fill="{colours[name]}" clip-path="url(#bar)"/>')
        cursor += seg
    y += 26

    per_row = 4
    for i, (name, size) in enumerate(ordered[:12]):
        col, rowi = i % per_row, i // per_row
        lx = PAD + col * ((W - PAD * 2) / per_row)
        ly = y + rowi * 20
        c.out.append(f'<circle cx="{lx + 5}" cy="{ly - 4}" r="5" '
                     f'fill="{colours[name]}"/>')
        c.text(lx + 16, ly, f"{name} {size / total_bytes * 100:.1f}%", t["fg"], 11)
    y += ((len(ordered[:12]) + per_row - 1) // per_row) * 20 + 10

    height = max(y + 16, y2 + 16)
    c.out.append(f'<line x1="{PAD}" y1="{height - 26}" x2="{W - PAD}" '
                 f'y2="{height - 26}" stroke="{t["rule"]}"/>')
    c.text(W - PAD, height - 10,
           f"Live from the GitHub API - {datetime.date.today().isoformat()}",
           t["dim"], 10, "end")

    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" '
            f'height="{height:.0f}" viewBox="0 0 {W} {height:.0f}" '
            f'font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,'
            f'Arial,sans-serif">{"".join(c.out)}</svg>')


def main():
    if len(sys.argv) != 3:
        raise SystemExit(f"usage: {sys.argv[0]} <username> <out-dir>")
    login, out_dir = sys.argv[1], sys.argv[2]
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise SystemExit("GITHUB_TOKEN is not set")

    user = fetch(login, token)
    icons = load_icons()
    if not icons:
        raise SystemExit("no octicons found next to the script")

    os.makedirs(out_dir, exist_ok=True)
    for theme in THEMES:
        svg = render(user, theme, icons)
        path = os.path.join(out_dir, f"metrics-{theme}.svg")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(svg)
        print(f"  wrote {path} ({len(svg) / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
