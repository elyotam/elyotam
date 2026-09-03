#!/usr/bin/env python3
"""
Generate an animated "growing snake" SVG from a GitHub contribution graph.

Unlike the usual snake action, this snake gets one segment longer every time it
eats a contribution square, so it visibly grows across the animation.

Palette follows the Python language colours: a yellow snake eating blue squares.

Usage:
    GITHUB_TOKEN=... python generate_snake.py <username> <out-dir>
"""

import json
import os
import random
import sys
import urllib.request

# ---------------------------------------------------------------- layout ----

CELL = 12          # square size
GAP = 3            # space between squares
PITCH = CELL + GAP
ROWS = 7
LEAD_IN = 14       # off-screen cells the snake slides in from
RUN_OFF = 16       # off-screen cells it exits through
START_LEN = 4      # segments before it has eaten anything
STEP_MS = 50       # time per cell

# A full board would make a +1-per-square snake longer than the grid itself,
# which reads as a yellow blob rather than a snake. Growing once every few
# meals keeps it dramatic and still legible.
GROW_EVERY = 3
DENSITY = 0.38     # share of squares filled on the decorative board
BOARD_SEED = 20260904
BOARD_TEXT = "ELYOTAM COHEN"

# A 5-row pixel font. Most glyphs are three columns wide; M and N get more
# because they are unreadable any narrower. "ELYOTAM COHEN" comes to 52 of the
# board's 53 columns, which is the whole reason the letters are this cramped.
FONT = {
    "A": ["010", "101", "111", "101", "101"],
    "C": ["111", "100", "100", "100", "111"],
    "E": ["111", "100", "110", "100", "111"],
    "H": ["101", "101", "111", "101", "101"],
    "L": ["100", "100", "100", "100", "111"],
    "M": ["10001", "11011", "10101", "10001", "10001"],
    "N": ["1001", "1101", "1011", "1001", "1001"],
    "O": ["111", "101", "101", "101", "111"],
    "T": ["111", "010", "010", "010", "010"],
    "Y": ["101", "101", "010", "010", "010"],
    " ": ["0"] * 5,
}

RADIUS = 3
EPS = 0.01        # keyframe percentages must never collide

# ---------------------------------------------------------------- themes ----

# Still the Python palette, just the other way round: a blue snake eating
# yellow squares. The light theme drops to amber for the squares because bright
# yellow on a white page is close to invisible.
THEMES = {
    "dark": {
        "empty": "#161b22",
        "levels": ["#5c4a12", "#9c7d0d", "#D9A404", "#FFD43B"],
        "snake_head": "#8FC1E3",
        "snake_body": "#4B8BBE",
        "snake_tail": "#2B6087",
        "flash": "#8FC1E3",
    },
    "light": {
        "empty": "#ebedf0",
        "levels": ["#fbeeb8", "#F0CE4E", "#E8B90B", "#C9930A"],
        "snake_head": "#4B8BBE",
        "snake_body": "#3776AB",
        "snake_tail": "#21445F",
        "flash": "#4B8BBE",
    },
}


def level_of(count):
    """Map a contribution count onto one of four intensity levels."""
    if count >= 20:
        return 3
    if count >= 10:
        return 2
    if count >= 4:
        return 1
    return 0


# ------------------------------------------------------------------ data ----

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount weekday } }
      }
    }
  }
}
"""


def fetch_calendar(login, token):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": login}}).encode(),
        headers={
            "Authorization": f"bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "growing-snake",
        },
    )
    with urllib.request.urlopen(req) as resp:
        payload = json.load(resp)
    if "errors" in payload:
        raise SystemExit(f"GraphQL error: {payload['errors']}")
    return payload["data"]["user"]["contributionsCollection"]["contributionCalendar"]


def text_grid(cols, text=BOARD_TEXT):
    """Spell `text` out in squares, centred on the board.

    Glyphs are five rows tall, leaving one blank row above and below.
    """
    glyphs = [FONT[ch] for ch in text.upper()]
    width = sum(len(g[0]) for g in glyphs) + len(glyphs) - 1
    if width > cols:
        raise SystemExit(f"{text!r} needs {width} columns, board is {cols}")

    grid = {(c, r): 0 for c in range(cols) for r in range(ROWS)}
    col = (cols - width) // 2
    top = (ROWS - 5) // 2
    for glyph in glyphs:
        for r, line in enumerate(glyph):
            for dc, bit in enumerate(line):
                if bit == "1":
                    # Brightest level, so the lettering stays legible.
                    grid[(col + dc, top + r)] = 26
        col += len(glyph[0]) + 1
    return grid


def decorative_grid(cols):
    """A hand-tuned board for when the real graph is too sparse to play on.

    Deliberately not the contribution calendar: weekends stay quieter and
    filled cells cluster, so it reads like a board rather than static noise.
    """
    rng = random.Random(BOARD_SEED)
    grid = {(c, r): 0 for c in range(cols) for r in range(ROWS)}
    for col in range(cols):
        for row in range(ROWS):
            weight = DENSITY * (0.45 if row in (0, 6) else 1.0)
            neighbours = sum(
                1 for d in (-1, 1)
                if grid.get((col + d, row), 0) > 0 or grid.get((col, row + d), 0) > 0
            )
            if rng.random() < weight + neighbours * 0.12:
                grid[(col, row)] = rng.choice([1, 2, 3, 5, 8, 12, 18, 26])
    return grid


def build_grid(calendar):
    """Return {(col, row): count} plus the column count."""
    grid = {}
    weeks = calendar["weeks"]
    for col, week in enumerate(weeks):
        for day in week["contributionDays"]:
            grid[(col, day["weekday"])] = day["contributionCount"]
    return grid, len(weeks)


# ------------------------------------------------------------------ path ----

def build_path(cols):
    """Serpentine sweep: left to right along one row, back along the next.

    Sweeping by row rather than by column matters: contributions cluster into a
    few recent weeks, so a column sweep leaves the snake starving until the very
    end. Going row by row spreads the meals - and therefore the growth - across
    the whole animation.

    Padded on both sides with off-screen cells so the snake slides in from the
    left and leaves through the right before the animation loops.
    """
    path = [(-LEAD_IN + i, 0) for i in range(LEAD_IN)]
    for row in range(ROWS):
        columns = range(cols) if row % 2 == 0 else range(cols - 1, -1, -1)
        path.extend((col, row) for col in columns)
    last_col, last_row = path[-1]
    direction = 1 if last_col >= cols - 1 else -1
    path.extend((last_col + direction * (i + 1), last_row) for i in range(RUN_OFF))
    return path


# ------------------------------------------------------------------- svg ----

def xy(col, row):
    return col * PITCH, row * PITCH


def render(grid, cols, theme_name):
    theme = THEMES[theme_name]
    path = build_path(cols)
    total = len(path)
    duration = total * STEP_MS / 1000.0

    # When each filled square gets eaten, in path-step order.
    eaten_at = {}
    for step, cell in enumerate(path):
        if grid.get(cell, 0) > 0 and cell not in eaten_at:
            eaten_at[cell] = step
    eat_steps = sorted(eaten_at.values())
    growth_steps = eat_steps[GROW_EVERY - 1::GROW_EVERY]
    max_len = START_LEN + len(growth_steps)

    width = cols * PITCH - GAP
    height = ROWS * PITCH - GAP
    pad = 6
    view_w = width + pad * 2
    view_h = height + pad * 2

    css = []
    body = []

    # --- the squares -------------------------------------------------------
    for (col, row), count in sorted(grid.items()):
        if col >= cols:
            continue
        x, y = xy(col, row)
        if count <= 0:
            body.append(
                f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" '
                f'rx="{RADIUS}" fill="{theme["empty"]}"/>'
            )
            continue

        colour = theme["levels"][level_of(count)]
        name = f"c{col}_{row}"
        pct = eaten_at[(col, row)] / total * 100
        flash_end = min(pct + 1.2, 99.98)
        # Each state gets its own percentage. Two rules at the identical
        # percentage would override one another, and the square would drift
        # towards its eaten colour from the very start instead of snapping
        # to it the moment the snake arrives.
        css.append(
            f"@keyframes {name}{{"
            f"0%,{pct:.3f}%{{fill:{colour}}}"
            f"{pct + EPS:.3f}%,{flash_end:.3f}%{{fill:{theme['flash']}}}"
            f"{flash_end + EPS:.3f}%,100%{{fill:{theme['empty']}}}}}"
        )
        body.append(
            f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="{RADIUS}" '
            f'fill="{colour}" style="animation:{name} {duration}s linear infinite"/>'
        )

    # --- the shared path the whole snake follows ---------------------------
    stops = []
    for step, (col, row) in enumerate(path):
        x, y = xy(col, row)
        stops.append(f"{step / total * 100:.4f}%{{transform:translate({x}px,{y}px)}}")
    css.append("@keyframes slither{" + "".join(stops) + "}")

    # --- the snake ---------------------------------------------------------
    for i in range(max_len):
        delay = i * STEP_MS / 1000.0
        anims = [f"slither {duration}s linear {delay}s infinite both"]

        if i >= START_LEN:
            # This segment only exists once the (i - START_LEN + 1)-th square
            # has been eaten, so the tail grows one cell at a time.
            appear = growth_steps[i - START_LEN] / total * 100
            grow = f"grow{i}"
            css.append(
                f"@keyframes {grow}{{"
                f"0%,{appear:.3f}%{{opacity:0}}"
                f"{appear + EPS:.3f}%,100%{{opacity:1}}}}"
            )
            anims.append(f"{grow} {duration}s linear 0s infinite both")

        if i == 0:
            fill = theme["snake_head"]
        elif i >= max_len - 2:
            fill = theme["snake_tail"]
        else:
            fill = theme["snake_body"]

        # Segments are drawn wider than a cell so they overlap across the grid
        # gap and read as one continuous body, tapering towards the tail.
        taper = i / max(max_len - 1, 1)
        size = PITCH - taper * (PITCH - CELL + 3)
        inset = (CELL - size) / 2
        css.append(f".s{i}{{animation:{','.join(anims)}}}")
        body.append(
            f'<rect class="s{i}" x="{inset:.2f}" y="{inset:.2f}" '
            f'width="{size:.2f}" height="{size:.2f}" rx="{RADIUS}" fill="{fill}"/>'
        )

    style = "<style>" + "".join(css) + "</style>"
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{view_w}" height="{view_h}" '
        f'viewBox="0 0 {view_w} {view_h}">'
        f"{style}"
        f'<g transform="translate({pad},{pad})">'
        f"{''.join(body)}"
        f"</g></svg>"
    )


def main():
    if len(sys.argv) != 3:
        raise SystemExit(f"usage: {sys.argv[0]} <username> <out-dir>")
    login, out_dir = sys.argv[1], sys.argv[2]

    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise SystemExit("GITHUB_TOKEN is not set")

    calendar = fetch_calendar(login, token)
    grid, cols = build_grid(calendar)
    real_filled = sum(1 for v in grid.values() if v > 0)
    print(
        f"{login}: {calendar['totalContributions']} contributions, "
        f"{real_filled} filled squares over {cols} weeks"
    )
    board = os.environ.get("SNAKE_BOARD", "text")
    if board == "text":
        grid = text_grid(cols)
        print(f"  board spells {BOARD_TEXT!r}: "
              f"{sum(1 for v in grid.values() if v > 0)} squares")
    elif board == "full":
        grid = decorative_grid(cols)
        print(f"  decorative board: {sum(1 for v in grid.values() if v > 0)} squares")

    os.makedirs(out_dir, exist_ok=True)
    for theme in THEMES:
        svg = render(grid, cols, theme)
        path = os.path.join(out_dir, f"snake-{theme}.svg")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(svg)
        print(f"  wrote {path} ({len(svg) / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
