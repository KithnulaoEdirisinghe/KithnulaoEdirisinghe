#!/usr/bin/env python3
"""Builds the Interstellar-themed visuals for the profile README as SVGs in assets/.

GitHub READMEs can't set fonts or backgrounds, so the decorative parts (header,
dividers, TARS briefing, telemetry, featured mission, star chart) are SVGs with the
fonts embedded. Everything people read or click lives in README.md as markdown.
Imagery comes from renders in assets/render/ (scripts/render_space.py and
scripts/render_tars.py); the moon is rendered fresh on every run. It also writes
assets/data.json and refreshes the TARS questions in README.md.

Run locally:
    PROFILE_TOKEN=$(gh auth token) python scripts/build_profile.py
The GitHub Action runs it every few hours. PROFILE_TOKEN must be a token that can
read the private repos you contribute to; without it, the per-repo star chart and
TARS's repo line keep their last values.
"""
import base64
import io
import json
import math
import os
import random
import re
import textwrap
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from html import escape

import numpy as np
from PIL import Image

import tars_reply
from render_space import fbm

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
    ("01", "CREW PROFILE"),
    ("02", "TARS"),
    ("03", "LAZARUS MISSIONS"),
    ("04", "STAR CHART"),
    ("05", "COMMS"),
]
# Private repos whose names are already public in the README. Any other private
# repo is shown as "classified"; HIDDEN_REPOS are left out entirely.
NAMED_PRIVATE = {"tick-talk", "rewards", "orerivals"}
HIDDEN_REPOS = {"test1"}
# Shorter labels for repos with long names.
DISPLAY_NAMES = {"CM1601--Java-Programming-Course-Work": "CM1601 Java", USER: "profile",
                 "AiSleep_WaypointSync": "AiSleep"}
# Build/script glue that shouldn't count as a language you work in.
IGNORED_LANGS = {"Batchfile", "Dockerfile", "Makefile", "Procfile", "PowerShell", "Shell"}

TARS_JOKES = [
    "Humor setting at 75%. Lower it and this README gets 40% less fun.",
    "I ran your build. It compiled first try. I've logged it as an anomaly.",
    "Gravity can cross dimensions. So, apparently, can merge conflicts.",
    "Recommendation: commit more often. Time is relative. Deadlines are not.",
    "Docking sequence complete. Coffee reserves: critical.",
    "A day on Venus is longer than its year. Like your TODO list.",
    "Scanned every repo. Zero black holes. Several bugs.",
    "Honesty setting 90%: those variable names could be better.",
    "I'd tell you a UDP joke, but you might not get it.",
    "Cooper would be proud. Probably. He's hard to read.",
]

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
ASSETS = os.path.join(ROOT, "assets")
DATA_PATH = os.path.join(ASSETS, "data.json")
RENDER = os.path.join(ASSETS, "render")
README = os.path.join(ROOT, "README.md")
# Questions visitors can open under TARS in the README; answers are refreshed every run.
TARS_QUESTIONS = [
    "What is Kithnula building?",
    "What's his tech stack?",
    "How active has he been?",
    "What's in the sky tonight?",
    "How long is that on Miller's planet?",
    "Tell me a joke.",
    "How do I reach him?",
]

W = 1200
# palette, taken from Gargantua: warm near-black, bronze and amber disk light, cream-white core
INK = "#050403"
DEEP = "#1a110a"
EMBER = "#8a5a32"
AMBER = "#e0904a"
GOLD = "#ecc790"
CREAM = "#f6e7cf"
SAND = "#cbb89c"
DIM = "#8a7966"
LINE = "#2e2219"

# "KITHNULA" set in Nasalization (Typodermic Fonts, used under its desktop licence
# for fixed wordmark artwork) and converted to one outline, so the font itself is
# not shipped. Font units: baseline at y=0, cap height 675.
WORDMARK_PATH = "M82 -675V0H200V-282H265C392 -282 416 -272 453 -200L556 0H688L579 -212C539 -290 508 -325 445 -342C500 -366 532 -405 562 -465L668 -675H541L438 -473C400 -399 381 -389 265 -389H200V-675ZM790 -675V0H908V-675ZM1018 -675V-557H1215V0H1334V-557H1531V-675ZM1642 -675V0H1760V-282H2105V0H2224V-675H2105V-400H1760V-675ZM2504 -534C2504 -558 2518 -573 2545 -573C2566 -573 2578 -564 2587 -544L2784 -113C2812 -36 2855 12 2949 12C3053 12 3104 -47 3104 -136V-675H2985V-141C2985 -118 2970 -103 2945 -103C2923 -103 2910 -115 2902 -131L2705 -562C2677 -639 2635 -687 2541 -687C2436 -687 2386 -628 2386 -540V0H2504ZM3261 -675V-215C3261 -73 3335 0 3479 0H3621C3765 0 3840 -73 3840 -215V-675H3724V-224C3724 -157 3689 -118 3613 -118H3493C3415 -118 3381 -157 3381 -224V-675ZM3991 -675V-233C3991 -98 4061 0 4240 0H4509V-118H4247C4141 -118 4109 -169 4109 -234V-675ZM4901 -543C4908 -559 4919 -566 4935 -566C4951 -566 4962 -559 4968 -543L5173 0H5304L5076 -600C5052 -663 5006 -687 4936 -687C4865 -687 4819 -663 4794 -600L4557 0H4687Z"
WORDMARK_BOUNDS = (82, -687, 5304, 12)


# ---------------------------------------------------------------- data

def token():
    return os.environ.get("PROFILE_TOKEN") or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")


def gh(path, body=None):
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request("https://api.github.com/" + path, data=data,
                                 headers={"Accept": "application/vnd.github+json"})
    if token():
        req.add_header("Authorization", f"Bearer {token()}")
    for attempt in range(3):  # the API occasionally drops connections
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except (urllib.error.URLError, ConnectionError) as e:
            if isinstance(e, urllib.error.HTTPError) or attempt == 2:
                raise


def commit_count(repo, since):
    """Commits authored by USER on the repo's default branch since the given time."""
    total, page = 0, 1
    while True:
        try:
            batch = gh(f"repos/{repo}/commits?author={USER}&since={since:%Y-%m-%dT%H:%M:%SZ}&per_page=100&page={page}")
        except urllib.error.HTTPError as e:
            if e.code == 409:  # empty repository
                return 0
            raise
        total += len(batch)
        if len(batch) < 100:
            return total
        page += 1


def fetch_profile(now):
    user = gh(f"users/{USER}")
    owned = gh(f"users/{USER}/repos?per_page=100&type=owner")
    q = """{user(login:"%s"){contributionsCollection{contributionCalendar{totalContributions
           weeks{contributionDays{date contributionCount}}}}}}""" % USER
    cal = gh("graphql", {"query": q})["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    days = [d for w in cal["weeks"] for d in w["contributionDays"]]
    days = [d for d in days if d["date"] <= f"{now:%Y-%m-%d}"]
    counts = [d["contributionCount"] for d in days]
    streak, i = 0, len(counts) - 1
    if counts and counts[-1] == 0:  # today may not have activity yet
        i -= 1
    while i >= 0 and counts[i] > 0:
        streak, i = streak + 1, i - 1
    longest = run = 0
    for c in counts:
        run = run + 1 if c else 0
        longest = max(longest, run)
    created = datetime.fromisoformat(user["created_at"].replace("Z", "+00:00"))
    return {
        "repos": user["public_repos"],
        "followers": user["followers"],
        "stars": sum(r["stargazers_count"] for r in owned if not r["fork"]),
        "contribs": cal["totalContributions"],
        "week": sum(counts[-7:]),
        "streak": streak,
        "longest": longest,
        "days": (now - created).days,
        "featured_stars": gh(f"repos/{FEATURED['repo']}")["stargazers_count"],
    }


def fetch_activity(now):
    """Per-repo commit counts and a language mix weighted by your commits.

    Needs a token that can list your private and collaborator repos; returns None
    when the token can't (e.g. the Action's default GITHUB_TOKEN)."""
    try:
        repos = gh("user/repos?affiliation=owner,collaborator,organization_member&per_page=100")
    except urllib.error.HTTPError:
        return None
    if not any(r["private"] for r in repos):
        return None
    year_ago, week_ago = now - timedelta(days=365), now - timedelta(days=7)
    activity, langs = [], {}
    for r in repos:
        if r["fork"] or r["name"] in HIDDEN_REPOS:
            continue
        commits = commit_count(r["full_name"], year_ago)
        if not commits:
            continue
        label = DISPLAY_NAMES.get(r["name"], r["name"])
        if r["private"] and r["name"] not in NAMED_PRIVATE:
            label = "classified"
        activity.append({"name": label, "private": r["private"], "commits": commits,
                         "week": commit_count(r["full_name"], week_ago)})
        sizes = {k: v for k, v in gh(f"repos/{r['full_name']}/languages").items() if k not in IGNORED_LANGS}
        total = sum(sizes.values())
        for lang, size in sizes.items():
            langs[lang] = langs.get(lang, 0) + commits * size / total
    activity.sort(key=lambda a: -a["commits"])
    lang_total = sum(langs.values()) or 1
    languages = sorted(({"name": k, "share": v / lang_total} for k, v in langs.items()), key=lambda l: -l["share"])
    return {"repos": activity, "languages": languages}


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


def miller_time(days):
    """Time that passes on Miller's planet (1 hour there = 7 years here) while `days` pass on Earth."""
    seconds = days * 86400 / (7 * 365.25 * 24)
    return f"{int(seconds // 60)} min {int(seconds % 60)} s"


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


def data_uri(img, fmt="JPEG", **options):
    buf = io.BytesIO()
    img.save(buf, fmt, **options)
    mime = {"JPEG": "image/jpeg", "WEBP": "image/webp", "PNG": "image/png"}[fmt]
    return f"data:{mime};base64," + base64.b64encode(buf.getvalue()).decode()


_SPACE = None


def space_bg(w, h, seed):
    """A w x h slice of the rendered space texture, as an <image>."""
    global _SPACE
    if _SPACE is None:
        _SPACE = Image.open(os.path.join(RENDER, "space.jpg")).convert("RGB")
    src = _SPACE if _SPACE.width == w else _SPACE.resize((w, round(_SPACE.height * w / _SPACE.width)))
    y = (seed * 137) % max(1, src.height - h)
    crop = src.crop((0, y, w, y + h))
    return f'<image width="{w}" height="{h}" href="{data_uri(crop, quality=78, optimize=True, progressive=True)}"/>'


def svg(h, body, title, seed, nebulas=(), extra_css="", w=W, background=None):
    """Wraps body in a framed panel over a slice of the space render (or a given background)."""
    global FONT_CSS
    FONT_CSS = FONT_CSS or font_css()
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
{extra_css}
@media (prefers-reduced-motion:reduce){{*{{animation:none!important}}.cover{{display:none}}}}
</style>
<defs>
  <clipPath id="frame"><rect width="{w}" height="{h}" rx="18"/></clipPath>
  <linearGradient id="rule" x1="0" x2="1"><stop offset="0" stop-color="{AMBER}" stop-opacity=".75"/><stop offset="1" stop-color="{EMBER}" stop-opacity="0"/></linearGradient>
  {glows}
</defs>
<g clip-path="url(#frame)">
<rect width="{w}" height="{h}" fill="{INK}"/>
{background or space_bg(w, h, seed)}
{glow_rects}
{body}
</g>
<rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="18" fill="none" stroke="{LINE}"/>
</svg>
"""


def lines(x, y, text_lines, size, color, cls="b", lh=None):
    lh = lh or size * 1.5
    return "".join(f'<text class="{cls}" x="{x}" y="{y + i * lh:.1f}" fill="{color}" font-size="{size}">'
                   f'{escape(t)}</text>' for i, t in enumerate(text_lines))


def chip(x, y, label):
    w = len(label) * 8.4 + 28
    return (f'<rect x="{x}" y="{y}" width="{w:.0f}" height="30" rx="15" fill="{EMBER}" fill-opacity=".12" stroke="{LINE}"/>'
            f'<text class="m" x="{x + w / 2:.1f}" y="{y + 20}" text-anchor="middle" fill="{CREAM}" font-size="13" '
            f'letter-spacing="1.5">{escape(label)}</text>'), w


def render_moon(phase, size):
    """Moon with maria, craters and the real terminator for this phase, as an RGBA image."""
    y, x = (np.mgrid[0:size, 0:size].astype(np.float32) + 0.5) / size * 2 - 1
    d = np.sqrt(x ** 2 + y ** 2)
    nz = np.sqrt(np.clip(1 - d ** 2, 0, 1))
    theta = 2 * np.pi * phase  # 0 new, .25 first quarter (lit right), .5 full
    lambert = np.clip(x * np.sin(theta) - nz * np.cos(theta), 0, 1)
    maria = np.clip((fbm((size, size), 5, 31, scale=0.4) - 0.52) * 6, 0, 1)
    detail = fbm((size, size), 7, 47, scale=0.08)
    albedo = (0.62 + 0.3 * detail) * (1 - 0.38 * maria)
    rnd = np.random.default_rng(5)
    for _ in range(26):
        cx, cy, r = rnd.uniform(-0.8, 0.8), rnd.uniform(-0.8, 0.8), rnd.uniform(0.03, 0.12)
        dd = np.sqrt((x - cx) ** 2 + (y - cy) ** 2) / r
        albedo = albedo * (1 - 0.18 * np.exp(-dd ** 4)) + 0.12 * np.exp(-((dd - 1) * 6) ** 2)
    shade = albedo * (lambert ** 0.85 + 0.035)  # faint earthshine on the dark side
    rgb = np.stack([shade * 1.0, shade * 0.95, shade * 0.86], -1)
    alpha = np.clip((1 - d) * size / 2, 0, 1)
    return Image.fromarray(np.dstack([np.clip(rgb, 0, 1) * 255, alpha * 255]).astype(np.uint8), "RGBA")


def wordmark(cx, cy, width, fill):
    """Places the wordmark outline centred on (cx, cy), scaled to the given width."""
    x0, y0, x1, y1 = WORDMARK_BOUNDS
    k = width / (x1 - x0)
    tx, ty = cx - (x0 + x1) / 2 * k, cy - (y0 + y1) / 2 * k
    return f'<path transform="translate({tx:.1f} {ty:.1f}) scale({k:.5f})" fill="{fill}" d="{WORDMARK_PATH}"/>'


# ---------------------------------------------------------------- visuals

def header():
    H = 400
    with open(os.path.join(RENDER, "gargantua.jpg"), "rb") as f:
        bh = base64.b64encode(f.read()).decode()
    body = f"""
<defs>
  <linearGradient id="wm" x1="0" x2="1"><stop offset="0" stop-color="{CREAM}"/><stop offset=".55" stop-color="#f0c48c"/><stop offset="1" stop-color="{AMBER}"/></linearGradient>
  <linearGradient id="shade" x1="0" x2="1"><stop offset="0" stop-color="#000" stop-opacity=".55"/><stop offset=".5" stop-color="#000" stop-opacity="0"/></linearGradient>
</defs>
<rect width="{W}" height="{H}" fill="url(#shade)"/>
{wordmark(370, 150, 600, "url(#wm)")}
<text class="t" x="72" y="236" fill="#fff" font-size="17" letter-spacing="8">{escape(NAME.upper())}</text>
<text class="m" x="72" y="268" fill="{SAND}" font-size="13" letter-spacing="3">{escape(TAGLINE)}</text>
<text class="m" x="28" y="36" fill="{DIM}" font-size="12" letter-spacing="2">LAZARUS PROGRAM  ·  MISSION KE-01</text>
<text class="m" x="28" y="{H - 24}" fill="{DIM}" font-size="12" letter-spacing="2">GARGANTUA  ·  RAY-TRACED SCHWARZSCHILD BLACK HOLE</text>
<text class="m" x="{W - 28}" y="{H - 24}" text-anchor="end" fill="{DIM}" font-size="12" letter-spacing="2">PER ASPERA AD ASTRA</text>"""
    background = f'<image width="{W}" height="{H}" href="data:image/jpeg;base64,{bh}"/>'
    return svg(H, body, f"{NAME}: {TAGLINE}", 42, background=background)


_HOLE_ICON = None


def hole_icon():
    """Small crop of the black hole render for the section dividers."""
    global _HOLE_ICON
    if _HOLE_ICON is None:
        crop = Image.open(os.path.join(RENDER, "gargantua.jpg")).crop((980, 150, 1640, 420)).resize((340, 140), Image.LANCZOS)
        _HOLE_ICON = data_uri(crop, quality=85)
    return _HOLE_ICON


def divider(num, title):
    """Slim section heading strip: index, wide title, fading rule, tiny black hole."""
    H = 84
    title_w = len(title) * (22 * 0.95 + 6)
    rule_x = 92 + title_w + 24
    body = f"""
<defs><radialGradient id="fade" r="50%"><stop offset=".55" stop-color="#fff"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient>
<mask id="feather"><rect x="{W - 190}" y="0" width="170" height="{H}" fill="url(#fade)"/></mask></defs>
<text class="m" x="40" y="51" fill="{AMBER}" font-size="14" letter-spacing="3">{num}</text>
<text class="t" x="88" y="53" fill="#fff" font-size="22" letter-spacing="6">{escape(title)}</text>
<rect x="{rule_x:.0f}" y="45" width="{max(0, W - 200 - rule_x):.0f}" height="1" fill="url(#rule)"/>
<image x="{W - 190}" y="7" width="170" height="70" href="{hole_icon()}" mask="url(#feather)"/>"""
    return svg(H, body, title.title(), int(num) * 13)


def tars(stats, activity, now):
    """TARS with a daily briefing typed out on his display."""
    H = 420
    phase, lit, phase_name, next_full, _ = moon_phase(now)
    top = next((r for r in (activity or {}).get("repos", []) if r["week"]), None)
    where = f", mostly on {top['name']}" if top and top["name"] != "classified" else (
        ", mostly on a classified repo" if top else "")
    briefing = [
        "Hello, Kithnula. TARS online. Running daily briefing.",
        f"{stats['week']} contributions in the last 7 days{where}.",
        f"Current streak: {stats['streak']} days. Longest this year: {stats['longest']}.",
        f"Moon tonight: {phase_name.lower()}, {round(lit * 100)}% lit. Full moon {next_full:%d %b}.",
        f"{stats['days']} days since launch = {miller_time(stats['days'])} on Miller's planet.",
        TARS_JOKES[now.toordinal() % len(TARS_JOKES)],
    ]
    px, py, pw, ph = 330, 60, 820, 290
    panel_fill = "#0b0805"
    char_w, size, lh = 9.6, 16, 34
    tx, ty = px + 28, py + 84
    css = ["@keyframes blink{50%{opacity:0}}.caret{animation:blink 1s steps(1) infinite}",
           ".s{animation:show .01s both}@keyframes show{from{opacity:0}to{opacity:1}}",
           "@keyframes glow{0%,100%{opacity:.55}50%{opacity:.85}}.rim{animation:glow 5s ease-in-out infinite}"]
    text, t = [], 0.6
    for i, line in enumerate(briefing):
        y = ty + i * lh
        n = len(line)
        width = n * char_w
        dur = n * 0.028
        text.append(
            f'<g class="s" style="animation-delay:{t:.2f}s"><text class="m" x="{tx}" y="{y}" fill="{AMBER}" font-size="{size}">&gt;</text>'
            f'<text class="m" x="{tx + 22}" y="{y}" fill="{GOLD if i < 5 else CREAM}" font-size="{size}" '
            f'textLength="{width:.1f}" lengthAdjust="spacingAndGlyphs">{escape(line)}</text></g>'
            f'<rect class="cover" x="{tx + 20}" y="{y - 18}" width="{width + 4:.1f}" height="26" fill="{panel_fill}" '
            f'style="animation:ty{i} {dur:.2f}s steps({n + 1},jump-none) {t + 0.15:.2f}s both"/>')
        css.append(f"@keyframes ty{i}{{to{{transform:translateX({width + 4:.1f}px)}}}}")
        t += 0.15 + dur + 0.35
    caret_y = ty + len(briefing) * lh
    text.append(f'<g class="s" style="animation-delay:{t:.2f}s"><text class="m" x="{tx}" y="{caret_y}" fill="{AMBER}" '
                f'font-size="{size}">&gt;</text><rect class="caret" x="{tx + 22}" y="{caret_y - 14}" width="9" height="17" fill="{GOLD}"/></g>')

    # TARS: Cycles render from scripts/render_tars.py, standing in a pool of warm light
    render = Image.open(os.path.join(RENDER, "tars.png")).convert("RGBA")
    rh = 340
    rw = round(render.width * rh / render.height)
    tars_img = data_uri(render.resize((rw * 2, rh * 2), Image.LANCZOS), "WEBP", quality=88, method=6)
    robot = f"""
<defs><radialGradient id="floor" r="50%"><stop offset="0" stop-color="{AMBER}" stop-opacity=".35"/><stop offset="1" stop-color="{AMBER}" stop-opacity="0"/></radialGradient></defs>
<ellipse class="rim" cx="{60 + rw / 2:.0f}" cy="{48 + rh - 8}" rx="150" ry="22" fill="url(#floor)"/>
<image x="60" y="48" width="{rw}" height="{rh}" href="{tars_img}"/>"""
    body = f"""
{robot}
<rect x="{px}" y="{py}" width="{pw}" height="{ph}" rx="14" fill="{panel_fill}" stroke="{GOLD}" stroke-opacity=".35"/>
<text class="m" x="{px + 28}" y="{py + 36}" fill="{GOLD}" font-size="13" letter-spacing="3">TARS // DAILY BRIEFING</text>
<text class="m" x="{px + pw - 28}" y="{py + 36}" text-anchor="end" fill="{DIM}" font-size="12" letter-spacing="2">HUMOR 75%  ·  HONESTY 90%</text>
<rect x="{px + 28}" y="{py + 50}" width="{pw - 56}" height="1" fill="{GOLD}" fill-opacity=".25"/>
{"".join(text)}
<text class="m" x="{px}" y="{H - 30}" fill="{DIM}" font-size="11" letter-spacing="2">UPDATED {now:%d %b %Y  ·  %H:%M} UTC  ·  ASK TARS BELOW</text>"""
    return svg(H, body, "TARS daily briefing. " + " ".join(briefing), 77, extra_css="\n".join(css),
               nebulas=[(15, 80, 35, EMBER, .18)])


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
            f'<rect x="{x}" y="76" width="198" height="150" rx="14" fill="{EMBER}" fill-opacity=".08" stroke="{LINE}"/>'
            f'<rect x="{x + 20}" y="76" width="36" height="2" fill="{AMBER}"/>'
            f'<text class="m" x="{x + 20}" y="108" fill="{DIM}" font-size="12" letter-spacing="2.5">{label}</text>'
            f'<text class="t" x="{x + 20}" y="166" fill="{CREAM}" font-size="40">{value}</text>'
            f'<text class="b" x="{x + 20}" y="198" fill="{SAND}" font-size="14">{caption}</text>')
    css = ".live{animation:live 1.6s ease-in-out infinite}@keyframes live{50%{opacity:.25}}"
    body = f"""
<defs><radialGradient id="halo" r="50%"><stop offset=".6" stop-color="{CREAM}" stop-opacity=".12"/><stop offset="1" stop-color="{CREAM}" stop-opacity="0"/></radialGradient></defs>
<circle class="live" cx="46" cy="44" r="5" fill="{GOLD}"/>
<text class="m" x="60" y="49" fill="#fff" font-size="13" letter-spacing="3">LIVE TELEMETRY</text>
<text class="m" x="882" y="49" text-anchor="end" fill="{DIM}" font-size="12" letter-spacing="1.5">T+{stats['days']} DAYS SINCE LAUNCH</text>
{"".join(tiles)}
<text class="m" x="40" y="268" fill="{DIM}" font-size="11" letter-spacing="2">UPDATED {now:%d %b %Y  ·  %H:%M} UTC  ·  LIVE FROM GITHUB</text>
<circle cx="{mx}" cy="{my}" r="{mr * 1.7}" fill="url(#halo)"/>
<circle cx="{mx}" cy="{my}" r="{mr + 14}" fill="none" stroke="{LINE}" stroke-dasharray="2 6"/>
<image x="{mx - mr}" y="{my - mr}" width="{mr * 2}" height="{mr * 2}" href="{data_uri(render_moon(phase, mr * 4), 'PNG', optimize=True)}"/>
<text class="m" x="{mx}" y="222" text-anchor="middle" fill="{DIM}" font-size="11" letter-spacing="2.5">MOON TONIGHT</text>
<text class="b" x="{mx}" y="246" text-anchor="middle" fill="#fff" font-size="17" font-weight="700">{phase_name} · {round(lit * 100)}%</text>
<text class="m" x="{mx}" y="270" text-anchor="middle" fill="{DIM}" font-size="11" letter-spacing="1">FULL {next_full:%d %b} · NEW {next_new:%d %b}</text>"""
    title = (f"Live telemetry: {stats['contribs']} contributions, {stats['repos']} repos, {stats['stars']} stars, "
             f"{stats['followers']} followers. Moon tonight: {phase_name}, {round(lit * 100)}% lit.")
    return svg(H, body, title, 7, extra_css=css, nebulas=[(88, 40, 30, AMBER, .12), (10, 100, 40, EMBER, .18)])


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
<g fill="none" stroke="{SAND}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" transform="translate(0 -70)">
  <rect x="742" y="150" width="78" height="146" rx="14"/>
  <path d="M770 160h22"/>
  <polyline points="756,238 764,226 770,248 777,212 784,256 791,224 798,240 806,232" stroke="{GOLD}"/>
  <path class="w1" d="M842 205a26 26 0 0 1 0 36" stroke="{AMBER}"/>
  <path class="w2" d="M856 192a44 44 0 0 1 0 62" stroke="{AMBER}"/>
  <path class="w3" d="M870 179a62 62 0 0 1 0 88" stroke="{AMBER}"/>
  <rect x="910" y="150" width="236" height="148" rx="10"/>
  <path d="M1028 298v30M988 330h80"/>
  <circle cx="1028" cy="224" r="22" stroke="{GOLD}"/>
  <path d="M1028 212v14M1020 222a8 8 0 0 0 16 0M1028 232v6" stroke="{GOLD}"/>
</g>
<text class="m" x="944" y="286" fill="{DIM}" font-size="11" letter-spacing="2">PHONE  →  WI-FI  →  PC</text>"""
    body = f"""
<text class="m" x="56" y="58" fill="{AMBER}" font-size="12" letter-spacing="3">FEATURED  ·  KE-01  ·  LAUNCHED</text>
<text class="t" x="56" y="110" fill="{CREAM}" font-size="40" letter-spacing="2">{escape(f["name"].upper())}</text>
{lines(56, 150, desc, 17, SAND, lh=26)}
{"".join(chips)}
<text class="m" x="56" y="290" fill="{GOLD}" font-size="12" letter-spacing="2.5">STARS {stats["featured_stars"]}  ·  VIEW MISSION  →</text>
{art}"""
    return svg(H, body, f"Featured mission: {f['name']}. {f['desc']}", 11, extra_css=css,
               nebulas=[(80, 60, 40, EMBER, .21), (0, 0, 35, AMBER, .08)])


def star_chart(activity, now):
    """Two live constellations: languages and repos, brighter = more of your commits."""
    H = 400
    slots = {
        "left": ([(140, 150), (290, 105), (420, 190), (330, 290), (180, 315), (80, 240)],
                 [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 0), (1, 3)]),
        "right": ([(690, 140), (840, 100), (990, 170), (930, 285), (780, 310), (660, 245)],
                  [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (0, 5), (0, 3)]),
    }
    groups = [
        ("left", "LANGUAGES", 60, [(l["name"], f"{round(l['share'] * 100)}%", l["share"]) for l in activity["languages"][:6]]),
        ("right", "REPOSITORIES", 640, [(r["name"], f"{r['commits']} commits", r["commits"]) for r in activity["repos"][:6]]),
    ]
    parts = []
    for side, label, gx, items in groups:
        pts, edges = slots[side]
        top = max((v for *_, v in items), default=1)
        parts.append(f'<text class="m" x="{gx}" y="56" fill="{AMBER}" font-size="12" letter-spacing="3">{label}</text>')
        for a, b in edges:
            if a < len(items) and b < len(items):
                (x1, y1), (x2, y2) = pts[a], pts[b]
                parts.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{SAND}" stroke-opacity=".25" stroke-width="1.2"/>')
        for (x, y), (name, value, v) in zip(pts, items):
            r = 2.5 + 4.5 * math.sqrt(v / top)
            right_edge = x > 950
            anchor = ' text-anchor="end"' if right_edge else ""
            lx = x - r - 12 if right_edge else x + r + 12
            parts.append(
                f'<circle cx="{x}" cy="{y}" r="{r * 6:.1f}" fill="url(#sg)"/>'
                f'<circle cx="{x}" cy="{y}" r="{r:.1f}" fill="{CREAM}"/>'
                f'<text class="b" x="{lx:.1f}" y="{y + 1}" fill="#fff" font-size="17" font-weight="700"{anchor}>{escape(name)}</text>'
                f'<text class="m" x="{lx:.1f}" y="{y + 20}" fill="{GOLD}" font-size="11" letter-spacing="1"{anchor}>{escape(value)}</text>')
    grid = "".join(f'<path d="M0 {y}Q600 {y - 60} 1200 {y}" fill="none" stroke="{LINE}" stroke-dasharray="3 7"/>'
                   for y in (110, 210, 310))
    grid += "".join(f'<path d="M{x} 0Q{x + 40} 200 {x} 400" fill="none" stroke="{LINE}" stroke-dasharray="3 7"/>'
                    for x in (280, 600, 920))
    body = f"""
<defs><radialGradient id="sg" r="50%"><stop offset="0" stop-color="{AMBER}" stop-opacity=".55"/><stop offset=".5" stop-color="{EMBER}" stop-opacity=".2"/><stop offset="1" stop-color="{EMBER}" stop-opacity="0"/></radialGradient></defs>
{grid}
{"".join(parts)}
<text class="m" x="40" y="{H - 24}" fill="{DIM}" font-size="11" letter-spacing="2">UPDATED {now:%d %b %Y}  ·  LIVE FROM GITHUB</text>
<text class="m" x="{W - 40}" y="{H - 24}" text-anchor="end" fill="{DIM}" font-size="11" letter-spacing="2">BRIGHTER = MORE OF YOUR COMMITS  ·  LAST 12 MONTHS</text>"""
    flat = "; ".join(f"{n} {v}" for *_, items in groups for n, v, _ in items)
    return svg(H, body, f"Star chart of your last 12 months: {flat}", 21,
               nebulas=[(50, 60, 45, EMBER, .18), (95, 10, 30, AMBER, .08)])


# ---------------------------------------------------------------- main

def write(name, text):
    with open(os.path.join(ASSETS, name), "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print(f"wrote assets/{name} ({len(text) // 1024} KB)")


if __name__ == "__main__":
    now = datetime.now(timezone.utc)
    stats = fetch_profile(now)
    previous = {}
    if os.path.exists(DATA_PATH):
        with open(DATA_PATH, encoding="utf-8") as f:
            previous = json.load(f)
    activity = fetch_activity(now)
    if activity is None:
        print("token can't see private repos; keeping the last star chart (set PROFILE_TOKEN to refresh it)")
        activity = previous.get("activity")
    phase, lit, phase_name, next_full, next_new = moon_phase(now)

    write("header.svg", header())
    for num, title in DIVIDERS:
        write(f"divider-{num}.svg", divider(num, title))
    write("tars.svg", tars(stats, activity, now))
    write("telemetry.svg", telemetry(stats, now))
    write("mission-featured.svg", featured(stats))
    if activity:
        write("star-chart.svg", star_chart(activity, now))
    data = {
        "updated": f"{now:%Y-%m-%dT%H:%MZ}",
        "stats": stats,
        "activity": activity,
        "moon": {"name": phase_name, "lit": round(lit * 100), "next_full": f"{next_full:%d %b}",
                 "next_new": f"{next_new:%d %b}"},
        "miller": miller_time(stats["days"]),
    }
    write("data.json", json.dumps(data, indent=2) + "\n")

    # TARS answers on the page: each question expands in place, no link out
    rnd = random.Random(now.toordinal())
    block = "\n".join(
        f"<details>\n<summary><b>{escape(q, quote=False)}</b></summary>\n\n> **TARS:** {tars_reply.answer(q, data, rnd)}\n\n</details>"
        for q in TARS_QUESTIONS)
    with open(README, encoding="utf-8") as f:
        readme = f.read()
    readme = re.sub(r"(<!-- TARS:START -->).*?(<!-- TARS:END -->)", lambda m: f"{m[1]}\n{block}\n{m[2]}", readme, flags=re.S)
    with open(README, "w", encoding="utf-8", newline="\n") as f:
        f.write(readme)
    print("updated TARS answers in README.md")
