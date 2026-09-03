#!/usr/bin/env python3
"""Build the profile banner: a matrix rain in the Python palette behind a
neon nameplate.

Usage:  python generate_banner.py <out-dir>
"""

import os
import random
import sys

W, H = 1200, 300
BLUE = "#3776AB"
LIGHT = "#4B8BBE"
YELLOW = "#FFD43B"
PALE = "#FFE873"
COL_W = 20
GLYPH_H = 18
GLYPHS_PER_COL = 34
SEED = 20260904


def rain():
    random.seed(SEED)
    out = []
    for i in range(W // COL_W):
        x = i * COL_W + 6
        duration = round(random.uniform(4.5, 13.0), 2)
        # A negative delay starts each column already part-way down, so the
        # rain looks established rather than beginning all at once.
        delay = round(-random.uniform(0, duration), 2)
        opacity = round(random.uniform(0.18, 0.62), 2)
        glyphs = "".join(
            f'<tspan x="{x}" dy="{GLYPH_H if k else 0}">{random.choice("01")}</tspan>'
            for k in range(GLYPHS_PER_COL)
        )
        out.append(
            f'<g class="rain" style="animation-duration:{duration}s;'
            f'animation-delay:{delay}s">'
            f'<text x="{x}" y="-300" fill="{BLUE}" opacity="{opacity}">{glyphs}</text>'
            f"</g>"
        )
    return "".join(out)


def blips(count=16):
    return "".join(
        f'<rect class="blip" x="{388 + i * 27}" y="196" width="21" height="14" '
        f'rx="2" fill="{YELLOW}" style="animation-delay:{i * 0.12:.2f}s"/>'
        for i in range(count)
    )


def build():
    travel = GLYPH_H * GLYPHS_PER_COL
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" \
viewBox="0 0 {W} {H}" font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace">
<defs>
<linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">
  <stop offset="0" stop-color="#0b1220"/><stop offset="1" stop-color="#0d1117"/>
</linearGradient>
<linearGradient id="fade" x1="0" y1="0" x2="1" y2="0">
  <stop offset="0" stop-color="#fff" stop-opacity="1"/>
  <stop offset="0.30" stop-color="#fff" stop-opacity="0.22"/>
  <stop offset="0.70" stop-color="#fff" stop-opacity="0.22"/>
  <stop offset="1" stop-color="#fff" stop-opacity="1"/>
</linearGradient>
<mask id="fademask"><rect width="{W}" height="{H}" fill="url(#fade)"/></mask>
<filter id="glow">
  <feGaussianBlur stdDeviation="3" result="b"/>
  <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
</filter>
<style>
  /* Scoped to .rain on purpose: a bare `text` rule would outrank the
     font-size attributes on the nameplate and shrink the whole title. */
  .rain text {{ font-size: 15px }}
  .rain {{ animation-name: fall; animation-timing-function: linear;
           animation-iteration-count: infinite }}
  @keyframes fall {{ from {{ transform: translateY(0) }}
                     to {{ transform: translateY({travel}px) }} }}
  .blip {{ animation: blip 2.4s steps(1) infinite }}
  @keyframes blip {{ 0%,49% {{ opacity: 1 }} 50%,100% {{ opacity: .2 }} }}
</style>
</defs>
<rect width="{W}" height="{H}" fill="url(#bg)"/>
<g mask="url(#fademask)">{rain()}</g>
<rect x="258" y="62" width="684" height="176" rx="16" fill="#0d1117" opacity="0.85"/>
<rect x="258" y="62" width="684" height="176" rx="16" fill="none" stroke="{PALE}"
      stroke-width="2" opacity="0.9" filter="url(#glow)"/>
<text x="600" y="107" text-anchor="middle" font-size="20" fill="{LIGHT}"
      letter-spacing="4">DevOps &#183; Cloud &#183; Automation</text>
<text x="600" y="170" text-anchor="middle" font-size="52" font-weight="700">
  <tspan fill="{YELLOW}">\\</tspan><tspan fill="#e6edf3">Elyotam</tspan>\
<tspan fill="{LIGHT}">Cohen</tspan><tspan fill="{YELLOW}">\\</tspan>
</text>
<rect x="380" y="190" width="440" height="26" rx="5" fill="none" stroke="{YELLOW}"
      stroke-width="2" opacity="0.85"/>
{blips()}
</svg>"""


def main():
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "banner.svg")
    svg = build()
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(svg)
    print(f"wrote {path} ({len(svg) / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
