#!/usr/bin/env python3
"""
Generate img/sky.svg, the star field tiled behind the dark-blue headers.

A fixed random seed gives the same sky every time. A 1600 x 1000 px patch of
sky is drawn four times, mirrored left-right and top-bottom ("db" over "pq"),
into a 3200 x 2000 px tile: every edge of the tile meets its own reflection,
so the pages can repeat it on very wide or very tall headers without seams.
The tile is drawn at that size (not scaled), so stars stay crisp.

Usage: python3 tools/make_sky.py
"""
import math
import random
from pathlib import Path

W, H = 1600, 1000
OUT = Path(__file__).resolve().parent.parent / "img" / "sky.svg"
COLOURS = [("#ffffff", 0.60), ("#d6e4ff", 0.20), ("#ffe4c4", 0.15), ("#ffc89a", 0.05)]


def colour(rng):
    x, acc = rng.random(), 0.0
    for c, w in COLOURS:
        acc += w
        if x < acc:
            return c
    return COLOURS[0][0]


def main():
    rng = random.Random(20261105)
    stars = []
    # field stars, mostly faint
    for _ in range(120):
        stars.append((rng.uniform(0, W), rng.uniform(0, H), rng.uniform(0.45, 1.25), rng.uniform(0.25, 0.75)))
    # a faint diagonal band, like the Milky Way
    for _ in range(90):
        t = rng.uniform(-0.1, 1.1)
        x = t * W
        y = H * (0.85 - 0.6 * t) + rng.gauss(0, 70)
        stars.append((x, y, rng.uniform(0.35, 0.8), rng.uniform(0.18, 0.5)))

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
           f'viewBox="0 0 {2 * W} {2 * H}" width="{2 * W}" height="{2 * H}">',
           "<!-- Star field for the ʻAmakihi site headers, made by tools/make_sky.py -->",
           "<defs>",
           '<radialGradient id="glow"><stop offset="0" stop-color="#fff" stop-opacity=".55"/>'
           '<stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient>',
           '<linearGradient id="spike-h"><stop offset="0" stop-color="#fff" stop-opacity="0"/>'
           '<stop offset=".5" stop-color="#fff" stop-opacity=".55"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>',
           '<linearGradient id="spike-v" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff" stop-opacity="0"/>'
           '<stop offset=".5" stop-color="#fff" stop-opacity=".55"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>',
           '<filter id="soft" x="-20%" y="-60%" width="140%" height="220%"><feGaussianBlur stdDeviation="55"/></filter>',
           f'<clipPath id="patch"><rect width="{W}" height="{H}"/></clipPath>',
           "</defs>",
           # the patch itself, clipped to its own quadrant so that its mirrors meet edge to edge
           '<g id="patch-a" clip-path="url(#patch)">',
           # the band's diffuse glow, blurred so that it has no edges
           f'<path d="M{-100} {H * 0.91:.0f} L{W + 100} {H * 0.19:.0f}" stroke="#a9c4ff" stroke-opacity=".05" '
           f'stroke-width="170" stroke-linecap="round" fill="none" filter="url(#soft)"/>']
    for x, y, r, a in stars:
        if -5 < x < W + 5 and -5 < y < H + 5:
            out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.2f}" fill="{colour(rng)}" fill-opacity="{a:.2f}"/>')
    # a few bright stars with four diffraction spikes, as on CFHT images
    for x, y, size in [(1290, 170, 1.0), (215, 610, 0.8), (760, 880, 0.7)]:
        L = 26 * size
        out.append(f'<g transform="translate({x} {y})">'
                   f'<circle r="{7 * size:.1f}" fill="url(#glow)"/>'
                   f'<rect x="{-L:.1f}" y="-0.45" width="{2 * L:.1f}" height="0.9" fill="url(#spike-h)"/>'
                   f'<rect x="-0.45" y="{-L:.1f}" width="0.9" height="{2 * L:.1f}" fill="url(#spike-v)"/>'
                   f'<circle r="{1.5 * size:.2f}" fill="#fff"/></g>')
    out.append("</g>")
    for m in (f"-1 0 0 1 {2 * W} 0", f"1 0 0 -1 0 {2 * H}", f"-1 0 0 -1 {2 * W} {2 * H}"):
        out.append(f'<use xlink:href="#patch-a" href="#patch-a" transform="matrix({m})"/>')
    out.append("</svg>")
    OUT.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"Wrote {OUT} ({len(stars)} stars, {OUT.stat().st_size / 1024:.1f} kB)")


if __name__ == "__main__":
    main()
