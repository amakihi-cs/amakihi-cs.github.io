#!/usr/bin/env python3
"""
Generate the atmospheric-escape icon of the home page (index.html): a star
with granulation, spots and an occasional flare, turning slowly, and a planet
losing a helium tail along its orbit.

The tail is a string of puffs that follow the planet with growing lags; each
is wider, fainter and pushed further out, so the tail curls away along the
orbit. The tail absorbs: it darkens the star where it crosses it, and each
puff switches between behind and in front of the planet according to its
depth (on an inclined orbit, depth follows the projected height). The far
half of the star is drawn again on top, to hide what passes behind it.

The script rewrites the icon's SVG and its CSS animations in index.html,
between the "escape-icon" markers. Usage: python3 tools/make_escape_icon.py
"""
import math
import random
import re
from pathlib import Path

PAGE = Path(__file__).resolve().parent.parent / "index.html"

P, RX, RY = 12.0, 26, 6.5            # orbital period (s) and projected orbit (viewBox units)
SX, SY, SR, PR = 40, 27, 8, 3.0      # star centre and radius, planet radius
TILT, T0 = 22, 3.8                   # orbit position angle (mirrors the RV icon's -22); start just after mid-transit
SPIN, SW = 30.0, 20                  # star rotation period (s) and surface strip period
N_PUFFS, LAG, PUSH = 12, 0.26, 0.055  # tail: puffs, lag between puffs (s), outward push per puff
K = range(N_PUFFS, 0, -1)            # oldest first
lag = {k: LAG * k for k in K}
scale = {k: 1 + PUSH * k for k in K}
rad = {k: 2.4 + 0.42 * k for k in K}
op = {k: 0.42 * (1 - k / (N_PUFFS + 1)) for k in K}


def phi(t):
    """Orbital phase at animation time t (s since the page loaded)."""
    return 2 * math.pi * (t + T0) / P


def compress(stops):
    """Keep only the keyframes where the value changes."""
    return [s for i, s in enumerate(stops)
            if not (0 < i < len(stops) - 1 and stops[i - 1][1] == s[1] == stops[i + 1][1])]


def keyframes():
    out = []
    for k in K:
        d = 2 * math.pi * lag[k] / P
        front, back = [], []
        for i in range(201):
            t = P * i / 200
            yk, yp = scale[k] * RY * math.sin(phi(t) - d), RY * math.sin(phi(t))
            f = min(1, max(0, 0.5 + (yk - yp) / 0.8))          # soft switch over 0.8 units of depth
            front.append((100 * i / 200, round(op[k] * f, 3)))
            back.append((100 * i / 200, round(op[k] * (1 - f), 3)))
        for name, stops in ((f"es-f{k}", front), (f"es-b{k}", back)):
            out.append(f"  @keyframes {name} {{ " + " ".join(f"{pc:.1f}% {{ opacity: {v}; }}" for pc, v in compress(stops)) + " }")
    # day side of the planet: dark in transit (near side), full behind the star
    lit = [(100 * i / 24, round(0.12 + 0.75 * (1 - math.sin(phi(P * i / 24))) / 2, 3)) for i in range(25)]
    out.append("  @keyframes es-lit { " + " ".join(f"{pc:.1f}% {{ opacity: {v}; }}" for pc, v in lit) + " }")
    return out


def orbiting(inner, k=None):
    """Wrap an element centred on the star in the orbit animations, with puff k's lag and push."""
    if k is None:
        dx, g0, g1 = -T0, "", ""
    else:
        dx = -((P - lag[k]) % P) - T0
        g0 = f'<g transform="translate({SX} {SY}) scale({scale[k]:.3f}) translate({-SX} {-SY})">'
        g1 = "</g>"
    return (f'{g0}<g class="es-x sine" style="animation-delay:{dx:.2f}s"><g class="es-y sine" '
            f'style="animation-delay:{dx - P / 4:.2f}s">{inner}</g></g>{g1}')


def puffs(kind):
    rows = []
    for k in K:
        grad = "es-shadow" if kind == "abs" else "es-puff"
        circle = f'<circle cx="{SX}" cy="{SY}" r="{rad[k]:.2f}" fill="url(#{grad})"/>'
        if kind == "abs":
            rows.append(f'        <g opacity="{min(1, 1.2 * op[k]):.3f}">{orbiting(circle, k)}</g>')
        else:
            rows.append(f'        <g class="es-op" style="animation-name:es-{kind}{k}">{orbiting(circle, k)}</g>')
    return "\n".join(rows)


def star_surface():
    rng = random.Random(1083)
    cells = []
    for _ in range(34):
        x, y = rng.uniform(0, SW), rng.uniform(-SR, SR)
        c, o = ("#fffaf0", rng.uniform(.25, .45)) if rng.random() < .55 else ("#e39445", rng.uniform(.2, .35))
        cells.append((x, y, rng.uniform(.4, .8), c, o))
    x0 = SX - SR - 2

    def copy(off):
        X, q = x0 + off, []
        for x, y, r, c, o in cells:
            q.append(f'<circle cx="{X + x:.2f}" cy="{SY + y:.2f}" r="{r:.2f}" fill="{c}" fill-opacity="{o:.2f}"/>')
        for x, y, rp, ru in ((6, -2.6, 1.7, .95), (14.5, 3.0, 1.1, .6)):          # two spots
            q.append(f'<circle cx="{X + x}" cy="{SY + y}" r="{rp}" fill="#b8642a" fill-opacity=".55"/>'
                     f'<circle cx="{X + x}" cy="{SY + y}" r="{ru}" fill="#5e2a10" fill-opacity=".8"/>')
        q.append(f'<g class="st-flare"><circle cx="{X + 7.6}" cy="{SY - 4.0}" r="3.2" fill="url(#st-hot)"/>'
                 f'<path d="M{X + 6.4} {SY - 3.5} q 1.4 -3.4 3.2 -.6" fill="none" stroke="#fffbe8" '
                 f'stroke-width=".65" stroke-linecap="round"/></g>')
        return "".join(q)
    return copy(0) + copy(SW)


def star_body(surface):
    return (f'      <g>\n'
            f'        <circle cx="{SX}" cy="{SY}" r="{SR}" fill="url(#es-star)"/>\n'
            f'        <g clip-path="url(#es-disk)"><g transform="rotate({TILT} {SX} {SY})"><g class="st-spin">{surface}</g></g></g>\n'
            f'        <circle cx="{SX}" cy="{SY}" r="{SR}" fill="url(#es-limb)"/>\n'
            # the whole star brightens for a moment during the flare
            f'        <circle class="st-flash" cx="{SX}" cy="{SY}" r="{SR}" fill="#fffaf0"/>\n'
            f'      </g>')


def svg():
    surface = star_surface()
    planet = (f'<circle cx="{SX}" cy="{SY}" r="{PR}" fill="#33466f"/>'
              f'<g clip-path="url(#es-pdisk)"><g transform="rotate({TILT} {SX} {SY})">'
              f'<rect x="{SX - PR}" y="{SY - 1.4}" width="{2 * PR}" height=".8" fill="#6f88bd" fill-opacity=".55"/>'
              f'<rect x="{SX - PR}" y="{SY + .3}" width="{2 * PR}" height=".55" fill="#1f2c4a" fill-opacity=".6"/>'
              f'<rect x="{SX - PR}" y="{SY + 1.5}" width="{2 * PR}" height=".5" fill="#7d95c6" fill-opacity=".45"/></g>'
              f'<circle class="es-lit" cx="{SX}" cy="{SY}" r="{PR}" fill="url(#es-day)"/></g>'
              f'<circle cx="{SX}" cy="{SY}" r="{PR}" fill="none" stroke="#9fd8ff" stroke-opacity=".55" stroke-width=".45"/>')
    far = f'<rect x="-30" y="-20" width="140" height="{SY + 20}" transform="rotate({TILT} {SX} {SY})"/>'
    return f"""    <svg class="escape" viewBox="-8 0 96 72" focusable="false">
      <title>Atmospheric escape: the planet loses its helium-rich atmosphere in a comet-like tail, seen in the 1083 nm helium line (WP4)</title>
      <defs>
        <radialGradient id="es-star" cx="50%" cy="50%" r="50%">
          <stop offset="0" stop-color="#fff6de"/><stop offset=".65" stop-color="#ffd58f"/><stop offset="1" stop-color="#f0a050"/>
        </radialGradient>
        <radialGradient id="es-limb" cx="50%" cy="50%" r="50%">
          <stop offset=".55" stop-color="#c8641e" stop-opacity="0"/><stop offset="1" stop-color="#b8561a" stop-opacity=".55"/>
        </radialGradient>
        <radialGradient id="es-glow"><stop offset="0" stop-color="#ffe6b8" stop-opacity=".45"/><stop offset="1" stop-color="#ffe6b8" stop-opacity="0"/></radialGradient>
        <radialGradient id="es-puff"><stop offset="0" stop-color="#b8e6ff" stop-opacity="1"/><stop offset=".55" stop-color="#9fd0ff" stop-opacity=".55"/><stop offset="1" stop-color="#9fd0ff" stop-opacity="0"/></radialGradient>
        <radialGradient id="es-shadow"><stop offset="0" stop-color="#0b1424" stop-opacity="1"/><stop offset=".6" stop-color="#0b1424" stop-opacity=".5"/><stop offset="1" stop-color="#0b1424" stop-opacity="0"/></radialGradient>
        <radialGradient id="es-day" cx="35%" cy="30%" r="75%"><stop offset="0" stop-color="#e3f1ff"/><stop offset=".6" stop-color="#8fb4e8" stop-opacity=".6"/><stop offset="1" stop-color="#8fb4e8" stop-opacity="0"/></radialGradient>
        <radialGradient id="st-hot"><stop offset="0" stop-color="#ffffff"/><stop offset=".4" stop-color="#fff4cf" stop-opacity=".85"/><stop offset="1" stop-color="#fff4cf" stop-opacity="0"/></radialGradient>
        <clipPath id="es-disk"><circle cx="{SX}" cy="{SY}" r="{SR}"/></clipPath>
        <clipPath id="es-pdisk"><circle cx="{SX}" cy="{SY}" r="{PR}"/></clipPath>
        <clipPath id="es-far">{far}</clipPath>
      </defs>
      <ellipse cx="{SX}" cy="{SY}" rx="{RX}" ry="{RY}" transform="rotate({TILT} {SX} {SY})" fill="none" stroke="#a9c4ff" stroke-opacity=".2" stroke-width=".7" stroke-dasharray="2 2.5"/>
      <circle cx="{SX}" cy="{SY}" r="15" fill="url(#es-glow)"/>
{star_body(surface)}
      <!-- the tail absorbs: a dark copy over the star disk -->
      <g clip-path="url(#es-disk)"><g transform="rotate({TILT} {SX} {SY})">
{puffs("abs")}
      </g></g>
      <!-- puffs behind the planet, the planet, puffs in front of it (each puff switches side with its depth) -->
      <g transform="rotate({TILT} {SX} {SY})">
{puffs("b")}
        {orbiting(planet)}
{puffs("f")}
      </g>
      <!-- the far half of the star drawn again on top: it hides whatever passes behind the star -->
      <g clip-path="url(#es-far)">
{star_body(surface)}
      </g>
    </svg>
"""


def css():
    return "\n".join([
        "  /* escape-icon:start (generated by tools/make_escape_icon.py) */",
        "  .escape { position: absolute; width: 96px; bottom: 6px; left: calc(50% - 48px); pointer-events: auto; }",
        "  @media (max-width: 719px) { .escape { width: 64px; left: calc(50% - 32px); } }",
        f"  .escape .es-x {{ animation-name: es-x; animation-duration: {P / 2:g}s; }}",
        f"  .escape .es-y {{ animation-name: es-y; animation-duration: {P / 2:g}s; }}",
        f"  @keyframes es-x {{ from {{ transform: translateX(-{RX}px); }} to {{ transform: translateX({RX}px); }} }}",
        f"  @keyframes es-y {{ from {{ transform: translateY(-{RY}px); }} to {{ transform: translateY({RY}px); }} }}",
        f"  .escape .es-op {{ animation-duration: {P:g}s; animation-timing-function: linear; animation-iteration-count: infinite; }}",
        f"  .escape .es-lit {{ animation: es-lit {P:g}s linear infinite; }}",
        f"  .escape .st-spin {{ animation: st-spin {SPIN:g}s linear infinite; }}",
        f"  @keyframes st-spin {{ from {{ transform: translateX(0); }} to {{ transform: translateX(-{SW}px); }} }}",
        f"  .escape .st-flare {{ opacity: 0; animation: st-flare {SPIN:g}s linear infinite; }}",
        # the flare goes off when its spot is near the middle of the disk (about 20 s into the 30 s turn)
        "  @keyframes st-flare { 0%, 64% { opacity: 0; } 65% { opacity: 1; } 68% { opacity: .5; } 72% { opacity: .15; } 76%, 100% { opacity: 0; } }",
        f"  .escape .st-flash {{ opacity: 0; animation: st-flash {SPIN:g}s linear infinite; }}",
        "  @keyframes st-flash { 0%, 64% { opacity: 0; } 65% { opacity: .3; } 68% { opacity: .1; } 72%, 100% { opacity: 0; } }",
        *keyframes(),
        "  /* escape-icon:end */",
    ]) + "\n"


def main():
    s = PAGE.read_text(encoding="utf-8")
    s, n1 = re.subn(r"    <svg class=\"escape\".*?</svg>\n", lambda m: svg(), s, count=1, flags=re.S)
    s, n2 = re.subn(r"  /\* escape-icon:start.*?escape-icon:end \*/\n", lambda m: css(), s, count=1, flags=re.S)
    if n1 != 1 or n2 != 1:
        raise SystemExit(f"markers not found in {PAGE} (svg: {n1}, css: {n2})")
    PAGE.write_text(s, encoding="utf-8")
    print(f"Rewrote the escape icon in {PAGE}")


if __name__ == "__main__":
    main()
