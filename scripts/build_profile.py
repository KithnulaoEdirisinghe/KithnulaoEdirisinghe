#!/usr/bin/env python3
"""Builds the space-themed visuals for the profile README as SVGs in assets/.

GitHub READMEs can't set fonts or backgrounds, so the decorative parts (header,
section dividers, telemetry, featured mission, star chart) are SVGs with the fonts
embedded. Everything people read or click lives in README.md as normal markdown.

Run locally with GITHUB_TOKEN set:
    GITHUB_TOKEN=$(gh auth token) python scripts/build_profile.py
The GitHub Action runs it daily so the stats and moon phase stay current.
"""
import base64
import json
import math
import os
import random
import textwrap
import urllib.request
from datetime import datetime, timedelta, timezone
from html import escape

USER = "KithnulaoEdirisinghe"
NAME = "Kithnula Edirisinghe"
TAGLINE = "AI & DATA SCIENCE @ IIT  ·  WINDOWS APPS  ·  GAMES  ·  WEB"

FEATURED = {
    "name": "MicBridge",
    "repo": f"{USER}/MicBridge",
    "desc": "Turns an Android phone into a wireless microphone for a Windows PC over Wi-Fi. "
            "A 100 KB Windows app using about 12 MB of RAM, with low-latency audio and automatic reconnect.",
    "tags": ["C#", "ANDROID", "WINDOWS"],
}
DIVIDERS = [
    ("01", "MISSION PROFILE"),
    ("02", "MISSION LOG"),
    ("03", "PAYLOAD"),
    ("04", "GROUND CONTROL"),
]
STACK = {
    "LANGUAGES": [("C#", 3), ("Python", 3), ("TypeScript", 2), ("Java", 2), ("Luau", 2)],
    "ENGINES & TOOLS": [(".NET", 3), ("Unity", 2), ("Roblox Studio", 3), ("Blender", 2), ("Android", 2)],
}

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
ASSETS = os.path.join(ROOT, "assets")

W = 1200
RED = "#fc3d21"
VIOLET = "#a78bfa"
LILAC = "#cfc4f5"
DIM = "#8b7fb0"
LINE = "#2c1d4a"

# "KITHNULA" set in Nasalization (Typodermic Fonts, used under its desktop licence
# for fixed wordmark artwork) and converted to one outline, so the font itself is
# not shipped. Font units: baseline at y=0, cap height 675.
WORDMARK_PATH = "M82 -675V0H200V-282H265C392 -282 416 -272 453 -200L556 0H688L579 -212C539 -290 508 -325 445 -342C500 -366 532 -405 562 -465L668 -675H541L438 -473C400 -399 381 -389 265 -389H200V-675ZM790 -675V0H908V-675ZM1018 -675V-557H1215V0H1334V-557H1531V-675ZM1642 -675V0H1760V-282H2105V0H2224V-675H2105V-400H1760V-675ZM2504 -534C2504 -558 2518 -573 2545 -573C2566 -573 2578 -564 2587 -544L2784 -113C2812 -36 2855 12 2949 12C3053 12 3104 -47 3104 -136V-675H2985V-141C2985 -118 2970 -103 2945 -103C2923 -103 2910 -115 2902 -131L2705 -562C2677 -639 2635 -687 2541 -687C2436 -687 2386 -628 2386 -540V0H2504ZM3261 -675V-215C3261 -73 3335 0 3479 0H3621C3765 0 3840 -73 3840 -215V-675H3724V-224C3724 -157 3689 -118 3613 -118H3493C3415 -118 3381 -157 3381 -224V-675ZM3991 -675V-233C3991 -98 4061 0 4240 0H4509V-118H4247C4141 -118 4109 -169 4109 -234V-675ZM4901 -543C4908 -559 4919 -566 4935 -566C4951 -566 4962 -559 4968 -543L5173 0H5304L5076 -600C5052 -663 5006 -687 4936 -687C4865 -687 4819 -663 4794 -600L4557 0H4687Z"
WORDMARK_BOUNDS = (82, -687, 5304, 12)


# ---------------------------------------------------------------- data

def gh(path, body=None):
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request("https://api.github.com/" + path, data=data,
                                 headers={"Accept": "application/vnd.github+json"})
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def fetch_stats():
    user = gh(f"users/{USER}")
    repos = gh(f"users/{USER}/repos?per_page=100&type=owner")
    q = '{user(login:"%s"){contributionsCollection{contributionCalendar{totalContributions}}}}' % USER
    contribs = gh("graphql", {"query": q})["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    created = datetime.fromisoformat(user["created_at"].replace("Z", "+00:00"))
    return {
        "repos": user["public_repos"],
        "followers": user["followers"],
        "stars": sum(r["stargazers_count"] for r in repos if not r["fork"]),
        "contribs": contribs["totalContributions"],
        "days": (datetime.now(timezone.utc) - created).days,
        "featured_stars": gh(f"repos/{FEATURED['repo']}")["stargazers_count"],
    }


def moon_phase(now):
    """Returns (fraction of the synodic month 0..1, illuminated fraction 0..1, name, next full, next new)."""
    synodic = 29.530588853
    ref_new_moon = datetime(2000, 1, 6, 18, 14, tzinfo=timezone.utc)
    phase = ((now - ref_new_moon).total_seconds() / 86400 / synodic) % 1
    lit = (1 - math.cos(2 * math.pi * phase)) / 2
    names = ["New moon", "Waxing crescent", "First quarter", "Waxing gibbous",
             "Full moon", "Waning gibbous", "Last quarter", "Waning crescent"]
    next_full = now + timedelta(days=((0.5 - phase) % 1 or 1) * synodic)
    next_new = now + timedelta(days=((1 - phase) % 1 or 1) * synodic)
    return phase, lit, names[int(phase * 8 + 0.5) % 8], next_full, next_new


# ---------------------------------------------------------------- drawing helpers

def font_css():
    faces = [("Michroma", "Michroma.woff2", 400), ("Space Grotesk", "SpaceGrotesk-Regular.woff2", 400),
             ("Space Grotesk", "SpaceGrotesk-Bold.woff2", 700), ("JetBrains Mono", "JetBrainsMono-Regular.woff2", 400)]
    out = []
    for family, file, weight in faces:
        with open(os.path.join(ASSETS, "fonts", file), "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        out.append(f"@font-face{{font-family:'{family}';font-weight:{weight};"
                   f"src:url(data:font/woff2;base64,{b64}) format('woff2')}}")
    return "\n".join(out)


FONT_CSS = None


def svg(h, body, title, seed, nebulas=(), extra_css="", w=W, star_density=3200):
    """Wraps body in a framed cosmic panel: purple/black gradient, nebula glows, stars."""
    global FONT_CSS
    FONT_CSS = FONT_CSS or font_css()
    rnd = random.Random(seed)
    glows = "".join(
        f'<radialGradient id="n{i}" cx="{cx}%" cy="{cy}%" r="{r}%"><stop offset="0" stop-color="{c}" stop-opacity="{o}"/>'
        f'<stop offset="1" stop-color="{c}" stop-opacity="0"/></radialGradient>'
        for i, (cx, cy, r, c, o) in enumerate(nebulas))
    glow_rects = "".join(f'<rect width="{w}" height="{h}" fill="url(#n{i})"/>' for i in range(len(nebulas)))
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-labelledby="title">
<title id="title">{escape(title)}</title>
<style>
{FONT_CSS}
.t{{font-family:'Michroma','Segoe UI',sans-serif}}
.b{{font-family:'Space Grotesk','Segoe UI',sans-serif}}
.m{{font-family:'JetBrains Mono',Consolas,monospace}}
.tw{{animation:tw 3s ease-in-out infinite}}
@keyframes tw{{50%{{opacity:.1}}}}
{extra_css}
@media (prefers-reduced-motion:reduce){{*{{animation:none!important}}.sat{{display:none}}}}
</style>
<defs>
  <clipPath id="frame"><rect width="{w}" height="{h}" rx="18"/></clipPath>
  <linearGradient id="base" x1="0" y1="0" x2=".35" y2="1"><stop offset="0" stop-color="#1b0b35"/><stop offset=".55" stop-color="#0d0619"/><stop offset="1" stop-color="#040107"/></linearGradient>
  <linearGradient id="rule" x1="0" x2="1"><stop offset="0" stop-color="{VIOLET}" stop-opacity=".7"/><stop offset="1" stop-color="{VIOLET}" stop-opacity="0"/></linearGradient>
  {glows}
</defs>
<g clip-path="url(#frame)">
<rect width="{w}" height="{h}" fill="url(#base)"/>
{glow_rects}
{stars(rnd, w, h, int(w * h / star_density))}
{body}
</g>
<rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="18" fill="none" stroke="{LINE}"/>
</svg>
"""


def stars(rnd, w, h, count, twinkle=0.25):
    out = []
    for _ in range(count):
        x, y = rnd.uniform(0, w), rnd.uniform(0, h)
        r = rnd.choice([0.5, 0.6, 0.8, 0.8, 1, 1.3, 1.7])
        o = rnd.uniform(0.25, 0.9)
        anim = ""
        if rnd.random() < twinkle:
            anim = (f' class="tw" style="animation-delay:{rnd.uniform(0, 4):.1f}s;'
                    f'animation-duration:{rnd.uniform(2.5, 5):.1f}s"')
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="#fff" opacity="{o:.2f}"{anim}/>')
    return "".join(out)


def lines(x, y, text_lines, size, color, cls="b", lh=None):
    lh = lh or size * 1.5
    return "".join(f'<text class="{cls}" x="{x}" y="{y + i * lh:.1f}" fill="{color}" font-size="{size}">'
                   f'{escape(t)}</text>' for i, t in enumerate(text_lines))


def chip(x, y, label):
    w = len(label) * 8.4 + 28
    return (f'<rect x="{x}" y="{y}" width="{w:.0f}" height="30" rx="15" fill="#ffffff" fill-opacity=".03" stroke="{LINE}"/>'
            f'<text class="m" x="{x + w / 2:.1f}" y="{y + 20}" text-anchor="middle" fill="{LILAC}" font-size="13" '
            f'letter-spacing="1.5">{escape(label)}</text>'), w


def moon_path(cx, cy, r, phase):
    """Lit region of the moon (waxing = lit on the right)."""
    rx = abs(math.cos(2 * math.pi * phase)) * r
    top, bottom = f"{cx} {cy - r}", f"{cx} {cy + r}"
    if phase < 0.5:
        sweep = 0 if phase < 0.25 else 1
        return f"M{top}A{r} {r} 0 0 1 {bottom}A{rx:.2f} {r} 0 0 {sweep} {top}z"
    sweep = 1 if phase > 0.75 else 0
    return f"M{top}A{r} {r} 0 0 0 {bottom}A{rx:.2f} {r} 0 0 {sweep} {top}z"


def wordmark(cx, cy, width):
    """Places the wordmark outline centred on (cx, cy), scaled to the given width."""
    x0, y0, x1, y1 = WORDMARK_BOUNDS
    k = width / (x1 - x0)
    tx, ty = cx - (x0 + x1) / 2 * k, cy - (y0 + y1) / 2 * k
    return f'<path transform="translate({tx:.1f} {ty:.1f}) scale({k:.5f})" fill="{RED}" d="{WORDMARK_PATH}"/>'


# ---------------------------------------------------------------- visuals

def header():
    H = 400
    cx, cy, rx, ry = 600, 168, 500, 92
    orbit = f"M{cx - rx} {cy}A{rx} {ry} 0 1 1 {cx + rx} {cy}A{rx} {ry} 0 1 1 {cx - rx} {cy}"
    back = f"M{cx - rx} {cy}A{rx} {ry} 0 0 1 {cx + rx} {cy}"
    front = f"M{cx + rx} {cy}A{rx} {ry} 0 0 1 {cx - rx} {cy}"
    css = (".shoot{animation:shoot 9s linear 2s infinite;opacity:0}"
           "@keyframes shoot{0%{transform:translate(780px,30px);opacity:0}2%{opacity:1}"
           "9%{transform:translate(1080px,180px);opacity:0}100%{transform:translate(1080px,180px);opacity:0}}")
    body = f"""
<defs>
  <radialGradient id="planet" cx="65%" cy="30%" r="80%"><stop offset="0" stop-color="#9d7bff"/><stop offset=".55" stop-color="#3a1f8f"/><stop offset="1" stop-color="#0e0628"/></radialGradient>
  <radialGradient id="glow" r="50%"><stop offset=".82" stop-color="#9d7bff" stop-opacity=".35"/><stop offset="1" stop-color="#9d7bff" stop-opacity="0"/></radialGradient>
  <radialGradient id="moon" cx="40%" cy="35%" r="70%"><stop offset="0" stop-color="#f1efe8"/><stop offset="1" stop-color="#8f8d86"/></radialGradient>
  <linearGradient id="orbit" x1="0" x2="1"><stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset=".5" stop-color="#fff" stop-opacity=".9"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>
  <linearGradient id="tail" x1="1" y1="1" x2="0" y2="0"><stop offset="0" stop-color="#fff"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>
</defs>
<g class="shoot"><line x1="0" y1="0" x2="-110" y2="-55" stroke="url(#tail)" stroke-width="2" stroke-linecap="round"/></g>
<circle cx="70" cy="470" r="230" fill="url(#glow)"/>
<circle cx="70" cy="470" r="190" fill="url(#planet)"/>
<circle cx="1090" cy="64" r="20" fill="url(#moon)"/>
<circle cx="1084" cy="58" r="3.5" fill="#000" opacity=".12"/><circle cx="1097" cy="71" r="2.5" fill="#000" opacity=".12"/>
<g transform="rotate(-7 {cx} {cy})">
  <path d="{back}" fill="none" stroke="url(#orbit)" stroke-width="2"/>
  <circle class="sat" r="4" fill="#fff"><animateMotion dur="16s" repeatCount="indefinite" path="{orbit}"/></circle>
</g>
{wordmark(cx, cy, 900)}
<g transform="rotate(-7 {cx} {cy})"><path d="{front}" fill="none" stroke="url(#orbit)" stroke-width="2.5"/></g>
<text class="t" x="{cx}" y="308" text-anchor="middle" fill="#fff" font-size="19" letter-spacing="9">{escape(NAME.upper())}</text>
<text class="m" x="{cx}" y="340" text-anchor="middle" fill="{LILAC}" font-size="13" letter-spacing="3">{escape(TAGLINE)}</text>
<text class="m" x="28" y="36" fill="{DIM}" font-size="12" letter-spacing="2">MISSION KE-01</text>
<text class="m" x="{W - 28}" y="{H - 24}" text-anchor="end" fill="{DIM}" font-size="12" letter-spacing="2">PER ASPERA AD ASTRA</text>
<text class="m" x="28" y="{H - 24}" fill="{DIM}" font-size="12" letter-spacing="2">RA 05h 35m 17s  DEC −05° 23′ 28″</text>"""
    return svg(H, body, f"{NAME}: {TAGLINE}", 42, extra_css=css, nebulas=[
        (80, 20, 45, "#8b3dff", .5), (18, 30, 40, "#5b2bd6", .35), (55, 95, 40, "#d6457d", .25)])


def divider(num, title):
    """Slim section heading strip: index, wide title, fading rule, small ringed planet."""
    H = 84
    title_w = len(title) * (22 * 0.95 + 6)
    rule_x = 92 + title_w + 24
    body = f"""
<text class="m" x="40" y="51" fill="{VIOLET}" font-size="14" letter-spacing="3">{num}</text>
<text class="t" x="88" y="53" fill="#fff" font-size="22" letter-spacing="6">{escape(title)}</text>
<rect x="{rule_x:.0f}" y="45" width="{W - 120 - rule_x:.0f}" height="1" fill="url(#rule)"/>
<circle cx="{W - 70}" cy="45" r="11" fill="{VIOLET}" fill-opacity=".85"/>
<ellipse cx="{W - 70}" cy="45" rx="22" ry="6" fill="none" stroke="{LILAC}" stroke-opacity=".7" transform="rotate(-18 {W - 70} 45)"/>"""
    return svg(H, body, title.title(), int(num) * 13, star_density=1800,
               nebulas=[(85, 50, 40, "#8b3dff", .35), (10, 50, 30, "#d6457d", .15)])


def telemetry(stats, now):
    H = 300
    phase, lit, phase_name, next_full, next_new = moon_phase(now)
    mx, my, mr = 1040, 116, 66
    tiles = []
    for i, (label, value, caption) in enumerate([
        ("CONTRIBUTIONS", stats["contribs"], "in the last 12 months"),
        ("REPOSITORIES", stats["repos"], "public on GitHub"),
        ("STARS", stats["stars"], "earned across repos"),
        ("CREW", stats["followers"], "followers"),
    ]):
        x = 40 + i * 214
        tiles.append(
            f'<rect x="{x}" y="76" width="198" height="150" rx="14" fill="#fff" fill-opacity=".035" stroke="{LINE}"/>'
            f'<rect x="{x + 20}" y="76" width="36" height="2" fill="{VIOLET}"/>'
            f'<text class="m" x="{x + 20}" y="108" fill="{DIM}" font-size="12" letter-spacing="2.5">{label}</text>'
            f'<text class="t" x="{x + 20}" y="166" fill="#fff" font-size="40">{value}</text>'
            f'<text class="b" x="{x + 20}" y="198" fill="{LILAC}" font-size="14">{caption}</text>')
    css = ".live{animation:live 1.6s ease-in-out infinite}@keyframes live{50%{opacity:.25}}"
    body = f"""
<defs><radialGradient id="lit" cx="40%" cy="35%" r="75%"><stop offset="0" stop-color="#f6f3ea"/><stop offset="1" stop-color="#b8b3a6"/></radialGradient>
<radialGradient id="halo" r="50%"><stop offset=".6" stop-color="#c9b8ff" stop-opacity=".2"/><stop offset="1" stop-color="#c9b8ff" stop-opacity="0"/></radialGradient></defs>
<circle class="live" cx="46" cy="44" r="5" fill="#6ee7c8"/>
<text class="m" x="60" y="49" fill="#fff" font-size="13" letter-spacing="3">LIVE TELEMETRY</text>
<text class="m" x="882" y="49" text-anchor="end" fill="{DIM}" font-size="12" letter-spacing="1.5">T+{stats['days']} DAYS SINCE LAUNCH</text>
{"".join(tiles)}
<text class="m" x="40" y="268" fill="{DIM}" font-size="11" letter-spacing="2">UPDATED {now:%d %b %Y}  ·  LIVE FROM GITHUB</text>
<circle cx="{mx}" cy="{my}" r="{mr * 1.7}" fill="url(#halo)"/>
<circle cx="{mx}" cy="{my}" r="{mr + 14}" fill="none" stroke="{LINE}" stroke-dasharray="2 6"/>
<circle cx="{mx}" cy="{my}" r="{mr}" fill="#140c26"/>
<path d="{moon_path(mx, my, mr, phase)}" fill="url(#lit)"/>
<g fill="#000" opacity=".07"><circle cx="{mx - 22}" cy="{my - 16}" r="12"/><circle cx="{mx + 20}" cy="{my + 22}" r="8"/><circle cx="{mx + 8}" cy="{my - 34}" r="5"/><circle cx="{mx - 32}" cy="{my + 24}" r="6"/></g>
<text class="m" x="{mx}" y="222" text-anchor="middle" fill="{DIM}" font-size="11" letter-spacing="2.5">MOON TONIGHT</text>
<text class="b" x="{mx}" y="246" text-anchor="middle" fill="#fff" font-size="17" font-weight="700">{phase_name} · {round(lit * 100)}%</text>
<text class="m" x="{mx}" y="270" text-anchor="middle" fill="{DIM}" font-size="11" letter-spacing="1">FULL {next_full:%d %b} · NEW {next_new:%d %b}</text>"""
    title = (f"Live telemetry: {stats['contribs']} contributions, {stats['repos']} repos, {stats['stars']} stars, "
             f"{stats['followers']} followers. Moon tonight: {phase_name}, {round(lit * 100)}% lit.")
    return svg(H, body, title, 7, extra_css=css, nebulas=[(88, 40, 30, "#8b3dff", .35), (10, 100, 40, "#5b2bd6", .25)])


def featured(stats):
    H = 320
    f = FEATURED
    desc = textwrap.wrap(f["desc"], 58)
    chips, cx = [], 56
    for t in f["tags"]:
        el, w = chip(cx, 224, t)
        chips.append(el)
        cx += w + 10
    css = ("@keyframes wave{0%,100%{opacity:.15}50%{opacity:1}}"
           ".w1{animation:wave 1.8s ease-in-out infinite}.w2{animation:wave 1.8s ease-in-out .3s infinite}"
           ".w3{animation:wave 1.8s ease-in-out .6s infinite}")
    # phone (left) transmitting to a PC monitor (right)
    art = f"""
<g fill="none" stroke="{LILAC}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" transform="translate(0 -70)">
  <rect x="742" y="150" width="78" height="146" rx="14"/>
  <path d="M770 160h22"/>
  <polyline points="756,238 764,226 770,248 777,212 784,256 791,224 798,240 806,232" stroke="{VIOLET}"/>
  <path class="w1" d="M842 205a26 26 0 0 1 0 36"/>
  <path class="w2" d="M856 192a44 44 0 0 1 0 62"/>
  <path class="w3" d="M870 179a62 62 0 0 1 0 88"/>
  <rect x="910" y="150" width="236" height="148" rx="10"/>
  <path d="M1028 298v30M988 330h80"/>
  <circle cx="1028" cy="224" r="22" stroke="{VIOLET}"/>
  <path d="M1028 212v14M1020 222a8 8 0 0 0 16 0M1028 232v6" stroke="{VIOLET}"/>
</g>
<text class="m" x="944" y="286" fill="{DIM}" font-size="11" letter-spacing="2">PHONE  →  WI-FI  →  PC</text>"""
    body = f"""
<text class="m" x="56" y="58" fill="{RED}" font-size="12" letter-spacing="3">FEATURED  ·  KE-01  ·  LAUNCHED</text>
<text class="t" x="56" y="110" fill="#fff" font-size="40" letter-spacing="2">{escape(f["name"].upper())}</text>
{lines(56, 150, desc, 17, LILAC, lh=26)}
{"".join(chips)}
<text class="m" x="56" y="290" fill="{VIOLET}" font-size="12" letter-spacing="2.5">STARS {stats["featured_stars"]}  ·  VIEW MISSION  →</text>
{art}"""
    return svg(H, body, f"Featured mission: {f['name']}. {f['desc']}", 11, extra_css=css,
               nebulas=[(80, 60, 40, "#8b3dff", .35), (0, 0, 35, "#d6457d", .18)])


def payload():
    H = 380
    layouts = {
        "LANGUAGES": ([(150, 140), (300, 90), (420, 180), (310, 270), (180, 310)], [(0, 1), (1, 2), (2, 3), (3, 4), (4, 0), (1, 3)]),
        "ENGINES & TOOLS": ([(720, 110), (860, 80), (1000, 160), (900, 260), (760, 290)], [(0, 1), (1, 2), (2, 3), (3, 4), (0, 3)]),
    }
    parts = []
    for gx, (group, items) in zip((60, 640), STACK.items()):
        pts, edges = layouts[group]
        parts.append(f'<text class="m" x="{gx}" y="48" fill="{VIOLET}" font-size="12" letter-spacing="3">{escape(group)}</text>')
        for a, b in edges:
            (x1, y1), (x2, y2) = pts[a], pts[b]
            parts.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{LILAC}" stroke-opacity=".28" stroke-width="1.2"/>')
        for (x, y), (label, mag) in zip(pts, items):
            r = 2 + mag * 1.3
            parts.append(
                f'<circle cx="{x}" cy="{y}" r="{r * 6}" fill="url(#sg)"/>'
                f'<circle cx="{x}" cy="{y}" r="{r}" fill="#fff"/>'
                f'<text class="b" x="{x + r + 12}" y="{y + 6}" fill="#fff" font-size="17" font-weight="700">{escape(label)}</text>')
    grid = "".join(f'<path d="M0 {y}Q600 {y - 60} 1200 {y}" fill="none" stroke="{LINE}" stroke-dasharray="3 7"/>'
                   for y in (100, 200, 300))
    grid += "".join(f'<path d="M{x} 0Q{x + 40} 190 {x} 380" fill="none" stroke="{LINE}" stroke-dasharray="3 7"/>'
                    for x in (280, 600, 920))
    body = f"""
<defs><radialGradient id="sg" r="50%"><stop offset="0" stop-color="#d9ccff" stop-opacity=".55"/><stop offset="1" stop-color="#d9ccff" stop-opacity="0"/></radialGradient></defs>
{grid}
{"".join(parts)}
<text class="m" x="{W - 40}" y="{H - 24}" text-anchor="end" fill="{DIM}" font-size="11" letter-spacing="2">STAR CHART  ·  BRIGHTER = USED MORE</text>"""
    flat = ", ".join(l for items in STACK.values() for l, _ in items)
    return svg(H, body, f"Tech stack: {flat}", 21, nebulas=[(50, 60, 45, "#5b2bd6", .3), (95, 10, 30, "#d6457d", .15)])


# ---------------------------------------------------------------- main

def write(name, text):
    with open(os.path.join(ASSETS, name), "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print(f"wrote assets/{name} ({len(text) // 1024} KB)")


if __name__ == "__main__":
    now = datetime.now(timezone.utc)
    stats = fetch_stats()
    write("header.svg", header())
    for num, title in DIVIDERS:
        write(f"divider-{num}.svg", divider(num, title))
    write("telemetry.svg", telemetry(stats, now))
    write("mission-featured.svg", featured(stats))
    write("payload.svg", payload())
