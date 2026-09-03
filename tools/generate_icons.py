#!/usr/bin/env python3
"""Compose the tool-icon strip.

Most tiles come from skillicons.dev. Helm and ArgoCD are whole lessons of the
course but skillicons has no icon for either, so their tiles are built here
from the official CNCF artwork in the same 256x256 / rx=60 format.

Usage:  python generate_icons.py <out-dir>
"""

import base64
import os
import re
import sys
import urllib.request

TILE = 256          # skillicons tile size
PITCH = 300         # tile + gap, as skillicons lays them out
GAP = PITCH - TILE
RADIUS = 60

ROWS = [
    ["linux", "bash", "py", "docker", "kubernetes", "helm", "argocd",
     "terraform"],
    ["ansible", "aws", "git", "github", "githubactions", "postgres",
     "prometheus", "grafana"],
    ["vscode", "cursor", "claudecode", "codex", "antigravity"],
]

# Hover labels. Each icon ships as its own file so the README can hang a
# `title` on every one; a single combined strip loaded as <img> cannot show
# per-icon tooltips, because an <img> never passes pointer events into the SVG.
LABELS = {
    "linux": "Linux", "bash": "Bash", "py": "Python", "docker": "Docker",
    "kubernetes": "Kubernetes", "helm": "Helm", "argocd": "Argo CD",
    "terraform": "Terraform", "ansible": "Ansible", "aws": "AWS",
    "git": "Git", "github": "GitHub", "githubactions": "GitHub Actions",
    "postgres": "PostgreSQL", "prometheus": "Prometheus",
    "grafana": "Grafana", "vscode": "VS Code", "cursor": "Cursor",
    "claudecode": "Claude Code", "codex": "Codex",
    "antigravity": "Google Antigravity",
}

# Tiles skillicons does not carry, built here from official marks.
SOURCES = {
    "helm": "https://raw.githubusercontent.com/cncf/artwork/main/projects/helm/icon/color/helm-icon-color.svg",
    "argocd": "https://raw.githubusercontent.com/cncf/artwork/main/projects/argo/icon/color/argo-icon-color.svg",
    "claudecode": "https://cdn.simpleicons.org/claude",
    "cursor": "https://cdn.simpleicons.org/cursor",
    "codex": "https://upload.wikimedia.org/wikipedia/commons/0/04/ChatGPT_logo.svg",
    # Google ships no SVG for Antigravity; its touch icon is the only official
    # mark available, so it gets embedded as a bitmap.
    "antigravity": "https://antigravity.google/apple-touch-icon.png",
}
CNCF = SOURCES  # kept for the existing lookups

# Backgrounds chosen for contrast: Helm's mark is a single navy colour so it is
# flipped to white on brand navy; Argo's octopus keeps its own palette and sits
# on the same dark tile skillicons uses for its monochrome logos.
CUSTOM_STYLE = {
    "helm": {"bg": "#0F1689", "recolor": "#FFFFFF", "scale": 0.62},
    "argocd": {"bg": "#242938", "recolor": None, "scale": 0.80},
    "claudecode": {"bg": "#D97757", "recolor": "#FFFFFF", "scale": 0.58},
    "cursor": {"bg": "#18181B", "recolor": "#FFFFFF", "scale": 0.56},
    "codex": {"bg": "#74AA9C", "recolor": None, "scale": 1.0},
    "antigravity": {"bg": "#FFFFFF", "recolor": None, "scale": 1.0,
                    "bitmap": True},
}


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "icon-strip"})
    with urllib.request.urlopen(req) as resp:
        return resp.read().decode("utf-8")


def skillicon_tile(name):
    """Pull one icon from skillicons and return its inner 256x256 <svg>."""
    doc = get(f"https://skillicons.dev/icons?i={name}")
    inner = re.search(r"<g transform=\"translate\(0, 0\)\">\s*(<svg.*?</svg>)\s*</g>",
                      doc, re.S)
    if not inner:
        raise SystemExit(f"could not extract a tile for {name!r}")
    return inner.group(1)


def viewbox(svg):
    m = re.search(r'viewBox="([\d.\-\s]+)"', svg)
    if not m:
        raise SystemExit("logo has no viewBox")
    return [float(v) for v in m.group(1).split()]


def get_bytes(url):
    req = urllib.request.Request(url, headers={"User-Agent": "icon-strip"})
    with urllib.request.urlopen(req) as resp:
        return resp.read()


def bitmap_tile(name):
    """For marks that ship only as a raster image, embedded as a data URI."""
    style = CUSTOM_STYLE[name]
    data = base64.b64encode(get_bytes(SOURCES[name])).decode("ascii")
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'width="{TILE}" height="{TILE}" viewBox="0 0 {TILE} {TILE}">'
        f'<defs><clipPath id="r"><rect width="{TILE}" height="{TILE}" '
        f'rx="{RADIUS}"/></clipPath></defs>'
        f'<g clip-path="url(#r)">'
        f'<rect width="{TILE}" height="{TILE}" fill="{style["bg"]}"/>'
        f'<image href="data:image/png;base64,{data}" width="{TILE}" '
        f'height="{TILE}" preserveAspectRatio="xMidYMid meet"/>'
        f"</g></svg>"
    )


def custom_tile(name):
    style = CUSTOM_STYLE[name]
    if style.get("bitmap"):
        return bitmap_tile(name)
    logo = get(SOURCES[name])
    _, _, vw, vh = viewbox(logo)

    body = re.sub(r"^.*?<svg[^>]*>", "", logo, flags=re.S)
    body = re.sub(r"</svg>\s*$", "", body, flags=re.S)
    # simple-icons declares its colour on the root <svg>, which gets stripped
    # here - so the recolour is applied on the wrapping group as well, and any
    # explicit fills inside are rewritten so they cannot override it.
    group_fill = ""
    if style["recolor"]:
        body = re.sub(r'fill:\s*#[0-9A-Fa-f]{3,6}', f'fill:{style["recolor"]}', body)
        body = re.sub(r'fill="#[0-9A-Fa-f]{3,6}"', f'fill="{style["recolor"]}"', body)
        group_fill = f'fill="{style["recolor"]}" '

    # Fit the logo into the tile, centred, at the configured scale.
    span = TILE * style["scale"]
    k = min(span / vw, span / vh)
    dx = (TILE - vw * k) / 2
    dy = (TILE - vh * k) / 2

    # xlink must be declared here: Argo's mark uses <use xlink:href="#a">, and
    # as a standalone file there is no parent <svg> left to inherit it from.
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'width="{TILE}" height="{TILE}" viewBox="0 0 {TILE} {TILE}">'
        f'<rect width="{TILE}" height="{TILE}" rx="{RADIUS}" fill="{style["bg"]}"/>'
        f'<g {group_fill}transform="translate({dx:.2f},{dy:.2f}) '
        f'scale({k:.5f})">{body}</g>'
        f"</svg>"
    )


def build():
    width = max(len(r) for r in ROWS) * PITCH - GAP
    height = len(ROWS) * TILE + GAP * (len(ROWS) - 1)

    parts, added = [], []
    for row_i, row in enumerate(ROWS):
        row_w = len(row) * PITCH - GAP
        x0 = (width - row_w) / 2          # centre short rows
        y = row_i * (TILE + GAP)
        for col_i, name in enumerate(row):
            if name in CNCF:
                tile = custom_tile(name)
                added.append(name)
            else:
                tile = skillicon_tile(name)
            x = x0 + col_i * PITCH
            parts.append(f'<g transform="translate({x:.0f},{y})">{tile}</g>')

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
        f'fill="none">{"".join(parts)}</svg>'
    )
    return svg, added


def main():
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    icon_dir = os.path.join(out_dir, "icons")
    os.makedirs(icon_dir, exist_ok=True)

    custom, markup = [], []
    for row in ROWS:
        for name in row:
            if name in CNCF:
                tile = custom_tile(name)
                custom.append(name)
            else:
                tile = skillicon_tile(name)
            with open(os.path.join(icon_dir, f"{name}.svg"), "w",
                      encoding="utf-8") as fh:
                fh.write(tile)
            label = LABELS[name]
            markup.append(
                f'  <img src="assets/icons/{name}.svg" title="{label}" '
                f'alt="{label}" width="48" height="48">'
            )
        markup.append("  <br>")
    markup.pop()  # no trailing break

    snippet = os.path.join(out_dir, "icons-snippet.html")
    with open(snippet, "w", encoding="utf-8") as fh:
        fh.write("\n".join(markup) + "\n")

    total = sum(len(r) for r in ROWS)
    print(f"wrote {total} tiles to {icon_dir}")
    print(f"  hand-built: {', '.join(custom)}")
    print(f"  README snippet: {snippet}")


if __name__ == "__main__":
    main()
