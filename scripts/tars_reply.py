#!/usr/bin/env python3
"""Ask TARS: replies in character to issues titled "TARS: <question>", then closes them.

Run by .github/workflows/tars.yml when an issue is opened. Answers come from
keyword matching plus the live numbers in assets/data.json; the visitor's text is
only ever matched against keywords, never executed or echoed back as markdown.
"""
import json
import os
import random
import re
import urllib.request

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
PROFILE = "https://github.com/KithnulaoEdirisinghe"


def load_data():
    with open(os.path.join(ROOT, "assets", "data.json"), encoding="utf-8") as f:
        return json.load(f)


def answer(question, data, rnd):
    q = question.lower()
    s, moon, act = data["stats"], data["moon"], data.get("activity") or {}
    langs = ", ".join(f"{l['name']} ({round(l['share'] * 100)}%)" for l in act.get("languages", [])[:5])
    top = next(iter(act.get("repos", [])), None)

    def has(*words):  # prefix match, so "language" also hits "languages"
        return any(re.search(rf"\b{w}", q) for w in words)

    if len(q.split()) <= 3 and re.search(r"\b(hi|hello|hey|yo|sup)\b", q):
        return rnd.choice(["Hello. I'm TARS, Kithnula's onboard assistant. Ask me about projects, stack, stats, the sky or how to reach him.",
                           "Greetings, traveller. You've reached the Endurance. Kithnula's out exploring; I'm minding the ship."])
    if has("who are you", "what are you", "your name"):
        return ("I'm TARS: a former Marine Corps tactical robot, now the assistant on Kithnula's profile. "
                "Humor setting 75%, honesty 90%. I report live telemetry and answer questions.")
    if has("project", "work", "build", "built", "micbridge", "portfolio", "mission"):
        return (f"Featured mission: [MicBridge]({PROFILE}/MicBridge), which turns an Android phone into a wireless mic "
                "for Windows. He's also crewed Tick-Talk, OreRivals, Rewards and Live-Wallpaper with friends. "
                + (f"Most commits this year: {top['name']} ({top['commits']})." if top else ""))
    if has("stack", "language", "tech", "skill", "code in", "program"):
        return f"Language mix over the last 12 months, weighted by his commits: {langs or 'C#, Python, TypeScript, Luau, Java'}."
    if has("stat", "commit", "contribution", "streak", "active"):
        return (f"{s['contribs']} contributions in the last 12 months, {s['week']} in the last 7 days. "
                f"Current streak {s['streak']} days, longest this year {s['longest']}. {s['followers']} crew members follow him.")
    if has("black hole", "gargantua", "wormhole", "miller", "time", "relativ"):
        return (f"On Miller's planet one hour is seven years here. Kithnula's {s['days']} days on GitHub add up to "
                f"{data['miller']} there. Gargantua, meanwhile, is still very heavy.")
    if has("moon", "sky", "night", "space", "star", "planet", "astronom"):
        return (f"Tonight's moon is {moon['name'].lower()}, {moon['lit']}% lit. Next full moon {moon['next_full']}, "
                f"next new moon {moon['next_new']}. Good nights for deep-sky viewing are around the new moon.")
    if has("contact", "email", "discord", "hire", "reach", "talk", "collab"):
        return "Open a channel: kithnulaedirisinghe@gmail.com, or Discord **kithnula**. Response times beat Miller's planet."
    if has("joke", "funny", "humor", "humour", "laugh"):
        return rnd.choice(["Humor setting at 75%. Here's one: there are 10 kinds of astronauts. Those who read binary, and those who don't.",
                           "Why did the developer go to space? To find more space for his node_modules.",
                           "I'd tell you a UDP joke, but you might not get it.",
                           "Knock knock. Who's there? Very long pause. Light from a distant star."])
    if has("honest", "truth"):
        return "Honesty setting 90%. The other 10% is reserved for telling you your code looks great."
    return rnd.choice([
        "That's outside my databanks. Try asking about projects, stack, stats, the moon or how to contact Kithnula.",
        "I've analysed your question from every dimension, including the fifth. Try: projects, stack, stats, moon, contact.",
    ])


def gh(method, path, body):
    req = urllib.request.Request(f"https://api.github.com/{path}", method=method, data=json.dumps(body).encode(),
                                 headers={"Accept": "application/vnd.github+json",
                                          "Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


if __name__ == "__main__":
    title = os.environ.get("ISSUE_TITLE", "")
    if not re.match(r"\s*tars\b", title, re.I):
        raise SystemExit("not a TARS question")
    question = re.sub(r"^\s*tars\s*[:,\-]?\s*", "", title, flags=re.I) + " " + os.environ.get("ISSUE_BODY", "")
    data = load_data()
    rnd = random.Random(os.environ.get("ISSUE_NUMBER"))
    reply = (f"**TARS:** {answer(question, data, rnd)}\n\n"
             f"<sub>Humor 75% · Honesty 90% · Telemetry from {data['updated']} · This transmission closes automatically.</sub>")
    repo, number = os.environ["REPO"], os.environ["ISSUE_NUMBER"]
    gh("POST", f"repos/{repo}/issues/{number}/comments", {"body": reply})
    gh("PATCH", f"repos/{repo}/issues/{number}", {"state": "closed", "state_reason": "completed"})
    print("replied to issue", number)
