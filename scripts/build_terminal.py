#!/usr/bin/env python3
"""Builds assets/terminal.svg: a Windows Terminal window that types out the profile.

Run locally with GITHUB_TOKEN set (e.g. `GITHUB_TOKEN=$(gh auth token) python scripts/build_terminal.py`).
The GitHub Action runs it daily so the stats stay current.
"""
import json
import os
import urllib.request
from html import escape

USER = "KithnulaoEdirisinghe"
NAME = "Kithnula Edirisinghe"
TAGLINE = "AI & Data Science undergrad @ IIT · building Windows apps, games and web stuff"
EMAIL = "kithnulaedirisinghe@gmail.com"
DISCORD = "kithnula"
CURRENTLY = "building a Roblox game"
LANGS = "C# · Python · TypeScript · Luau · Java"
FOCUS = "Windows apps · Game dev · Web dev"

# (name, language, stars source, note). Stars source is "owner/repo" for public repos, None for private.
PROJECTS = [
    ("MicBridge", "C#", f"{USER}/MicBridge", "phone -> PC wireless mic"),
    ("Live-Wallpaper", "HTML", "Hirukadeven07/Live-Wallpaper", "contributor"),
    ("tick-talk", "C#", None, "contributor"),
    ("rewards", "TypeScript", None, "contributor"),
    ("orerivals", "Luau", None, "contributor · Roblox"),
]

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "terminal.svg")

# Campbell (Windows Terminal default) colours
BG = "#0c0c0c"
FG = "#cccccc"
WHITE = "#f2f2f2"
GRAY = "#767676"
BLUE = "#3b78ff"
CYAN = "#61d6d6"
GREEN = "#16c60c"
YELLOW = "#f9f1a5"
CAMPBELL = ["#0c0c0c", "#c50f1f", "#13a10e", "#c19c00", "#0037da", "#881798", "#3a96dd", "#cccccc"]
# Oh My Posh prompt segments
SEGMENTS = [("kithnula", "#2f6fde"), ("~\\github", "#7b4fe0"), ("main", "#d6457d")]

W = 900
FONT = 14
CH = 8.4  # monospace advance at 14px; typed text is forced to this with textLength
LH = 22
X0 = 24
TYPE_SPEED = 0.055

MONO = "'Cascadia Mono','Cascadia Code',Consolas,SFMono-Regular,Menlo,'DejaVu Sans Mono',monospace"
SANS = "'Segoe UI Variable','Segoe UI',system-ui,-apple-system,sans-serif"


def gh(path, body=None):
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    url = "https://api.github.com/" + path
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, headers={"Accept": "application/vnd.github+json"})
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req) as r:
        return json.load(r)


def fetch_stats():
    user = gh(f"users/{USER}")
    repos = gh(f"users/{USER}/repos?per_page=100&type=owner")
    stars = sum(r["stargazers_count"] for r in repos if not r["fork"])
    q = '{user(login:"%s"){contributionsCollection{contributionCalendar{totalContributions}}}}' % USER
    contribs = gh("graphql", {"query": q})["data"]["user"]["contributionsCollection"]["contributionCalendar"][
        "totalContributions"
    ]
    project_stars = {src: gh(f"repos/{src}")["stargazers_count"] for _, _, src, _ in PROJECTS if src}
    return {
        "repos": user["public_repos"],
        "followers": user["followers"],
        "stars": stars,
        "contribs": contribs,
        "project_stars": project_stars,
    }


class Terminal:
    def __init__(self):
        self.y = 78
        self.t = 0.5
        self.body = []
        self.css = []
        self.n = 0

    def _shown(self, inner, at=None):
        at = self.t if at is None else at
        self.body.append(f'<g class="s" style="animation-delay:{at:.2f}s">{inner}</g>')

    def text(self, x, s, color=FG, bold=False, size=FONT, length=None):
        weight = ' font-weight="700"' if bold else ""
        tl = f' textLength="{length:.1f}" lengthAdjust="spacingAndGlyphs"' if length else ""
        return f'<text x="{x:.1f}" y="{self.y}" fill="{color}" font-size="{size}"{weight}{tl}>{escape(s)}</text>'

    def line(self, *parts, x=X0, gap=0.06):
        """parts: (text, color) or (text, color, bold); laid out left to right in monospace cells."""
        out, cx = [], x
        for p in parts:
            s, color, bold = (p + (False,))[:3]
            out.append(self.text(cx, s, color, bold, length=len(s) * CH))
            cx += len(s) * CH
        self._shown("".join(out))
        self.y += LH
        self.t += gap

    def blank(self):
        self.y += LH // 2

    def prompt(self, cmd):
        top, h = self.y - 15, 21
        x, segs = X0, []
        for i, (label, color) in enumerate(SEGMENTS):
            lead = 10 if i else 0
            w = lead + 10 + len(label) * 7.8 + 8
            segs.append((x, w, label, color, lead))
            x += w
        parts = []
        for sx, w, label, color, lead in reversed(segs):
            tip = sx + w
            parts.append(
                f'<path d="M{sx:.1f} {top}H{tip:.1f}l10 {h / 2}l-10 {h / 2}H{sx:.1f}z" fill="{color}"/>'
            )
            parts.append(self.text(sx + lead + 10, label, "#ffffff", size=13, length=len(label) * 7.8))
        cmd_x = x + 22
        parts.append(self.text(cmd_x, cmd, YELLOW, length=len(cmd) * CH))
        self._shown("".join(parts))

        # A background-coloured cover slides right one character at a time to "type" the command.
        # jump-none lands on the final position before the animation ends; plain steps(n) can stop
        # one character short in Chrome due to float rounding.
        start = self.t + 0.35
        dur = len(cmd) * TYPE_SPEED
        if cmd:
            self.n += 1
            cw = len(cmd) * CH + 2
            self.css.append(f"@keyframes t{self.n}{{to{{transform:translateX({cw:.1f}px)}}}}")
            self.body.append(
                f'<rect class="c" x="{cmd_x - 1:.1f}" y="{top}" width="{cw:.1f}" height="{h + 2}" fill="{BG}" '
                f'style="animation:t{self.n} {dur:.2f}s steps({len(cmd) + 1},jump-none) {start:.2f}s both"/>'
            )
        self.y += LH + 4
        self.t = start + dur + 0.35

    def cursor_prompt(self):
        self.prompt("")
        self.y -= LH + 4
        x = X0 + sum(10 + len(l) * 7.8 + 8 for l, _ in SEGMENTS) + 10 * (len(SEGMENTS) - 1) + 22
        self.body.append(
            f'<g class="s" style="animation-delay:{self.t - 0.3:.2f}s"><rect class="b" x="{x:.1f}" '
            f'y="{self.y - 14}" width="8.4" height="17" fill="{FG}"/></g>'
        )
        self.y += LH


def build(stats):
    term = Terminal()
    term.line(("PowerShell 7.5.2", FG))
    term.line(("Loading personal profile took 6.9ms.", GRAY))
    term.blank()

    term.prompt("whoami")
    term.line((NAME, WHITE, True))
    term.line((TAGLINE, FG))
    term.blank()

    term.prompt("fastfetch")
    info_x = X0 + 150
    logo_top = term.y - 14
    logo_at = term.t
    info = [
        (("kithnula", BLUE, True), ("@", FG), ("github", BLUE, True)),
        (("-" * 15, GRAY),),
        (("Uni", CYAN), (": IIT · BSc AI & Data Science", FG)),
        (("Focus", CYAN), (f": {FOCUS}", FG)),
        (("Langs", CYAN), (f": {LANGS}", FG)),
        (("Repos", CYAN), (f": {stats['repos']} public · {stats['stars']} stars · {stats['followers']} followers", FG)),
        (("Activity", CYAN), (f": {stats['contribs']} contributions in the last year", FG)),
        (("Currently", CYAN), (f": {CURRENTLY}", FG)),
    ]
    for parts in info:
        term.line(*parts, x=info_x, gap=0.08)
    outline = ' stroke="#3a3a3a"'
    swatches = "".join(
        f'<rect x="{info_x + i * 26}" y="{term.y - 13}" width="24" height="14" fill="{c}"'
        f'{outline if c == BG else ""}/>'
        for i, c in enumerate(CAMPBELL)
    )
    term._shown(swatches)
    term.y += LH
    logo = "".join(
        f'<rect x="{X0 + 8 + dx}" y="{logo_top + 12 + dy}" width="52" height="52" fill="{BLUE}"/>'
        for dx in (0, 56)
        for dy in (0, 56)
    )
    term._shown(logo, at=logo_at)
    term.blank()

    term.prompt("Get-ChildItem .\\projects")
    cols = [("Mode", 8), ("Name", 17), ("Lang", 13), ("Stars", 9), ("Note", 0)]
    term.line(*[(h.ljust(w), GREEN) for h, w in cols])
    term.line(*[(("-" * len(h)).ljust(w), GREEN) for h, w in cols])
    for name, lang, src, note in PROJECTS:
        star = f"★ {stats['project_stars'][src]}" if src else "private"
        term.line(
            ("-a---".ljust(8), FG),
            (name.ljust(17), CYAN, True),
            (lang.ljust(13), FG),
            (star.ljust(9), YELLOW if src else GRAY),
            (note, GRAY),
        )
    term.blank()

    term.prompt("Get-Contact")
    term.line(("email".ljust(10), CYAN), (EMAIL, FG))
    term.line(("discord".ljust(10), CYAN), (DISCORD, FG))
    term.blank()

    term.cursor_prompt()

    H = term.y + 6
    css = "\n".join(
        [
            f"text{{font-family:{MONO};white-space:pre}}",
            ".s{animation:show .01s both}",
            "@keyframes show{from{opacity:0}to{opacity:1}}",
            ".b{animation:blink 1.06s steps(1) infinite}",
            "@keyframes blink{50%{opacity:0}}",
            *term.css,
            "@media (prefers-reduced-motion:reduce){.s,.b{animation:none}.c{display:none}}",
        ]
    )
    chrome = f"""
  <rect width="{W}" height="{H}" fill="{BG}"/>
  <rect width="{W}" height="42" fill="#1f1f1f"/>
  <path d="M8 42V18a8 8 0 0 1 8-8h196a8 8 0 0 1 8 8v24z" fill="{BG}"/>
  <rect x="22" y="19" width="16" height="16" rx="3" fill="#012456"/>
  <path d="M26 23l4 4-4 4" stroke="#fff" stroke-width="1.6" fill="none"/><path d="M31 32h4" stroke="#fff" stroke-width="1.6"/>
  <text x="48" y="32" fill="{WHITE}" font-size="12.5" style="font-family:{SANS}">PowerShell</text>
  <path d="M192 23l8 8M200 23l-8 8" stroke="#b0b0b0" stroke-width="1.2"/>
  <path d="M238 21v12M232 27h12" stroke="#b0b0b0" stroke-width="1.3"/>
  <path d="M262 25l4 4 4-4" stroke="#b0b0b0" stroke-width="1.3" fill="none"/>
  <path d="M{W - 142} 27h11" stroke="#d0d0d0" stroke-width="1"/>
  <rect x="{W - 96.5}" y="21.5" width="10" height="10" fill="none" stroke="#d0d0d0" stroke-width="1"/>
  <path d="M{W - 48} 21l11 11M{W - 37} 21l-11 11" stroke="#d0d0d0" stroke-width="1"/>"""
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-labelledby="title">
<title id="title">{escape(NAME)}: {escape(TAGLINE)}</title>
<style>
{css}
</style>
<defs><clipPath id="win"><rect width="{W}" height="{H}" rx="10"/></clipPath></defs>
<g clip-path="url(#win)">{chrome}
{chr(10).join(term.body)}
</g>
<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="10" fill="none" stroke="#3a3a3a"/>
</svg>
"""


if __name__ == "__main__":
    svg = build(fetch_stats())
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(svg)
    print(f"wrote {os.path.normpath(OUT)}")
