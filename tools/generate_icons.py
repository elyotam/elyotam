#!/usr/bin/env python3
"""Compose the tool-icon strip.

Most tiles come from skillicons.dev. Helm and ArgoCD are whole lessons of the
course but skillicons has no icon for either, so their tiles are built here
from the official CNCF artwork in the same 256x256 / rx=60 format.

Usage:  python generate_icons.py <out-dir>
"""

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
     "terraform", "ansible"],
    ["aws", "git", "github", "githubactions", "nginx", "postgres",
     "prometheus", "grafana"],
]

CNCF = {
    "helm": "https://raw.githubusercontent.com/cncf/artwork/main/projects/helm/icon/color/helm-icon-color.svg",
    "argocd": "https://raw.githubusercontent.com/cncf/artwork/main/projects/argo/icon/color/argo-icon-color.svg",
}

# Backgrounds chosen for contrast: Helm's mark is a single navy colour so it is
# flipped to white on brand navy; Argo's octopus keeps its own palette and sits
# on the same dark tile skillicons uses for its monochrome logos.
CUSTOM_STYLE = {
    "helm": {"bg": "#0F1689", "recolor": "#FFFFFF", "scale": 0.62},
    "argocd": {"bg": "#242938", "recolor": None, "scale": 0.80},
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


def custom_tile(name):
    style = CUSTOM_STYLE[name]
    logo = get(CNCF[name])
    _, _, vw, vh = viewbox(logo)

    body = re.sub(r"^.*?<svg[^>]*>", "", logo, flags=re.S)
    body = re.sub(r"</svg>\s*$", "", body, flags=re.S)
    if style["recolor"]:
        body = re.sub(r'fill:\s*#[0-9A-Fa-f]{3,6}', f'fill:{style["recolor"]}', body)
        body = re.sub(r'fill="#[0-9A-Fa-f]{3,6}"', f'fill="{style["recolor"]}"', body)

    # Fit the logo into the tile, centred, at the configured scale.
    span = TILE * style["scale"]
    k = min(span / vw, span / vh)
    dx = (TILE - vw * k) / 2
    dy = (TILE - vh * k) / 2

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{TILE}" height="{TILE}" '
        f'viewBox="0 0 {TILE} {TILE}">'
        f'<rect width="{TILE}" height="{TILE}" rx="{RADIUS}" fill="{style["bg"]}"/>'
        f'<g transform="translate({dx:.2f},{dy:.2f}) scale({k:.5f})">{body}</g>'
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
    os.makedirs(out_dir, exist_ok=True)
    svg, custom = build()
    path = os.path.join(out_dir, "tools.svg")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(svg)
    total = sum(len(r) for r in ROWS)
    print(f"wrote {path} ({len(svg) / 1024:.1f} KB)")
    print(f"  {total} icons; hand-built tiles: {', '.join(custom)}")


if __name__ == "__main__":
    main()
