"""Draw the animated SVG cards used by the profile README.

    python scripts/render_cards.py            # fetch live data, then draw
    python scripts/render_cards.py --offline  # redraw from data/*.json only

Standard library only. Text content (models, featured repos, taglines) lives in
data/profile.json; contribution and star numbers are fetched from GitHub's public
pages, so the cards show what a signed-out visitor sees. The workflow in
.github/workflows/profile-cards.yml runs this once a day.

Cards are embedded with <img>, where GitHub runs CSS animations but no scripts
and no external fonts, so everything here is plain shapes, system monospace
fonts and one-shot CSS keyframes that end in the final state.
"""
import datetime as dt
import html
import json
import os
import re
import sys
import urllib.request

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DATA = os.path.join(ROOT, "data")
CARDS = os.path.join(ROOT, "cards")

W = 880          # card width in SVG units; README shows them at 100%
GAP = 10         # transparent strip under each card = spacing between cards
BG, BAR, LINE = "#0b0d14", "#11141d", "#232838"
INK, DIM, FAINT = "#e6e8f0", "#8a93ad", "#4d5570"
BLUE, VIOLET, GREEN = "#6b7bff", "#a78bfa", "#4ade80"
HEAT = ["#151927", "#252d63", "#3743a8", "#5b6cff", "#a9b4ff"]
FONT = "ui-monospace,SFMono-Regular,'SF Mono',Menlo,Consolas,'Liberation Mono',monospace"
LANG = {"JavaScript": "#f1e05a", "TypeScript": "#3178c6", "Python": "#3572A5",
        "Shell": "#89e051", "Ruby": "#701516", "HTML": "#e34c26"}
MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()

STYLE = f"""<style>
text{{font-family:{FONT}}}
.a{{opacity:0;animation:fi .5s ease-out forwards}}
.g{{transform-box:fill-box;transform-origin:50% 100%;transform:scaleY(0);animation:gr .7s cubic-bezier(.2,.8,.2,1) forwards}}
.c{{animation:bl 1.1s steps(1) infinite}}
.p{{animation:pu 2.4s ease-in-out infinite}}
@keyframes fi{{to{{opacity:1}}}}
@keyframes gr{{to{{transform:scaleY(1)}}}}
@keyframes bl{{50%{{opacity:0}}}}
@keyframes pu{{50%{{opacity:.35}}}}
@media (prefers-reduced-motion:reduce){{.a,.g,.c,.p{{animation:none;opacity:1;transform:none}}}}
</style>"""


def esc(s):
    return html.escape(str(s), quote=True)


def text(x, y, s, size=13, fill=INK, weight=400, anchor="start", delay=None, extra=""):
    cls = ' class="a" style="animation-delay:%.2fs"' % delay if delay is not None else ""
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{fill}" font-weight="{weight}" '
            f'text-anchor="{anchor}"{cls}{extra}>{esc(s)}</text>')


def prompt(user, x, y, cmd, delay=0.1):
    """`user@github ~ $ cmd` line."""
    return (f'<text x="{x}" y="{y}" font-size="13" class="a" style="animation-delay:{delay}s">'
            f'<tspan fill="{GREEN}">{esc(user)}@github</tspan><tspan fill="{FAINT}"> ~ </tspan>'
            f'<tspan fill="{VIOLET}">$ </tspan><tspan fill="{INK}">{esc(cmd)}</tspan></text>')


def window(h, title, body, w=W, pad=0):
    """A terminal window: rounded frame, title bar with three dots, body."""
    x0, cw = pad, w - pad * 2
    dots = "".join(f'<circle cx="{x0 + 20 + i * 16}" cy="17" r="5" fill="{c}"/>'
                   for i, c in enumerate(["#ff5f57", "#febc2e", "#28c840"]))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h + GAP}" width="{w}" '
            f'height="{h + GAP}" role="img">{STYLE}'
            f'<clipPath id="k"><rect x="{x0}" width="{cw}" height="{h}" rx="12"/></clipPath>'
            f'<g clip-path="url(#k)"><rect x="{x0}" width="{cw}" height="{h}" fill="{BG}"/>'
            f'<rect x="{x0}" width="{cw}" height="34" fill="{BAR}"/>'
            f'<rect x="{x0}" y="34" width="{cw}" height="1" fill="{LINE}"/></g>{dots}'
            f'{text(w / 2, 21.5, title, 11.5, DIM, anchor="middle")}{body}'
            f'<rect x="{x0 + .5}" y=".5" width="{cw - 1}" height="{h - 1}" rx="12" fill="none" stroke="{LINE}"/>'
            f'</svg>\n')


def wrap(s, width):
    lines, cur = [], ""
    for word in s.split():
        if cur and len(cur) + 1 + len(word) > width:
            lines.append(cur)
            cur = word
        else:
            cur = (cur + " " + word).strip()
    return lines + [cur] if cur else lines


# ---------------------------------------------------------------- data

def get(url, headers=None):
    req = urllib.request.Request(url, headers={"User-Agent": "profile-cards", **(headers or {})})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8")


def fetch_contributions(user):
    """Parse the public contribution calendar (what a signed-out visitor sees)."""
    page = get(f"https://github.com/users/{user}/contributions", {"X-Requested-With": "XMLHttpRequest"})
    tips = {}
    for cid, tip in re.findall(r'<tool-tip[^>]*\bfor="([^"]+)"[^>]*>([^<]*)', page):
        m = re.match(r"\s*(\d+) contribution", tip)
        tips[cid] = int(m.group(1)) if m else 0
    days = []
    for tag in re.findall(r"<td[^>]*data-date=[^>]*>", page):
        attr = dict(re.findall(r'([\w-]+)="([^"]*)"', tag))
        days.append({"date": attr["data-date"], "level": int(attr.get("data-level", 0)),
                     "count": tips.get(attr.get("id"), 0)})
    days.sort(key=lambda d: d["date"])
    if len(days) < 300:
        raise RuntimeError(f"contribution calendar parse failed: {len(days)} days")
    m = re.search(r"([\d,]+)\s+contributions?\s+in the last year", page)
    total = int(m.group(1).replace(",", "")) if m else sum(d["count"] for d in days)
    return {"total": total, "days": days}


def fetch_repos(user, names):
    token = os.environ.get("GITHUB_TOKEN")
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    out = {}
    for n in names:
        r = json.loads(get(f"https://api.github.com/repos/{user}/{n}", headers))
        out[n] = {"stars": r["stargazers_count"], "forks": r["forks_count"], "language": r["language"]}
    return out


def load(name):
    with open(os.path.join(DATA, name)) as f:
        return json.load(f)


def save(name, obj):
    with open(os.path.join(DATA, name), "w") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
        f.write("\n")


def stats(days):
    by = {d["date"]: d["count"] for d in days}
    last = dt.date.fromisoformat(days[-1]["date"])
    # today may still be empty: a streak that reached yesterday is still alive
    cur, day = 0, last if by[last.isoformat()] else last - dt.timedelta(days=1)
    while by.get(day.isoformat(), 0) > 0:
        cur, day = cur + 1, day - dt.timedelta(days=1)
    longest = run = 0
    for d in days:
        run = run + 1 if d["count"] else 0
        longest = max(longest, run)
    best = max(days, key=lambda d: d["count"])
    months = {}
    for d in days:
        months[d["date"][:7]] = months.get(d["date"][:7], 0) + d["count"]
    return {"current": cur, "longest": longest, "active": sum(1 for d in days if d["count"]),
            "span": len(days), "best": best, "months": sorted(months.items())[-12:]}


# ---------------------------------------------------------------- cards

def hero(p):
    h = 336
    b = [prompt(p["prompt_user"], 32, 70, "whoami")]
    b.append(text(31, 128, p["wordmark"], 46, INK, 800, delay=0.5, extra=' letter-spacing="3"'))
    b.append(text(33, 158, p["role"], 16, VIOLET, 600, delay=0.8))
    for i, line in enumerate(p["tagline"]):
        b.append(text(33, 192 + i * 20, line, 13.5, DIM, delay=1.0 + i * 0.12))
    for i, (k, v) in enumerate(p["facts"]):
        y, d = 250 + i * 20, 1.4 + i * 0.12
        b.append(text(33, y, k, 12.5, FAINT, delay=d))
        b.append(text(100, y, v, 12.5, INK, delay=d))
    b.append(f'<text x="33" y="318" font-size="13" class="a" style="animation-delay:2s">'
             f'<tspan fill="{VIOLET}">$ </tspan></text>'
             f'<rect class="c" x="50" y="306" width="8" height="15" fill="{INK}"/>')
    # logo ASCII: every row is stretched to an exact width so any monospace font lines up
    with open(os.path.join(DATA, "logo_ascii.txt")) as f:
        rows = f.read().rstrip("\n").split("\n")
    cw, lh = 6.9, 10.4
    cols = max(map(len, rows))
    x0, y0 = W - 40 - cols * cw, 62
    b.append(f'<linearGradient id="lg" gradientUnits="userSpaceOnUse" x1="0" y1="{y0}" x2="0" '
             f'y2="{y0 + len(rows) * lh}"><stop offset="0" stop-color="#b7c0ff"/>'
             f'<stop offset=".5" stop-color="{BLUE}"/><stop offset="1" stop-color="{VIOLET}"/></linearGradient>')
    for i, row in enumerate(rows):
        s = row.lstrip(" ")
        if not s:
            continue
        x = x0 + (len(row) - len(s)) * cw
        b.append(f'<text x="{x:.1f}" y="{y0 + i * lh:.1f}" font-size="11" fill="url(#lg)" xml:space="preserve" '
                 f'textLength="{len(s) * cw:.1f}" lengthAdjust="spacingAndGlyphs" class="a" '
                 f'style="animation-delay:{0.6 + i * 0.07:.2f}s">{esc(s)}</text>')
    return window(h, f'{p["prompt_user"]}@github: ~', "".join(b))


def contributions(p, c):
    days, h = c["days"], 250
    first = dt.date.fromisoformat(days[0]["date"])
    offset = (first.weekday() + 1) % 7          # column rows run Sun..Sat
    weeks = (offset + len(days) + 6) // 7
    pitch = min(15.0, (W - 32 - 62) / weeks)
    cell, gx, gy = pitch - 3, 62, 100
    b = [prompt(p["prompt_user"], 32, 66, "./contributions.sh --last-year")]
    for r, lab in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        b.append(text(32, gy + r * pitch + cell - 2, lab, 10, FAINT))
    seen = None
    for i, d in enumerate(days):
        col, row = divmod(i + offset, 7)
        x, y = gx + col * pitch, gy + row * pitch
        month = d["date"][5:7]
        if row == 0 and month != seen and col < weeks - 1:
            if seen is not None or int(d["date"][8:]) <= 7:
                b.append(text(x, gy - 8, MONTHS[int(month) - 1], 10, FAINT))
            seen = month
        b.append(f'<rect class="a" style="animation-delay:{0.3 + col * 0.022:.2f}s" x="{x:.1f}" y="{y:.1f}" '
                 f'width="{cell:.1f}" height="{cell:.1f}" rx="2.5" fill="{HEAT[min(d["level"], 4)]}"/>')
    fy = gy + 7 * pitch + 24
    b.append(f'<text x="32" y="{fy}" font-size="13" class="a" style="animation-delay:1.6s">'
             f'<tspan fill="{INK}" font-weight="700">{c["total"]:,}</tspan>'
             f'<tspan fill="{DIM}"> contributions in the last year</tspan></text>')
    lx = W - 32 - 5 * 15 - 40
    b.append(text(lx - 8, fy, "less", 10, FAINT, anchor="end"))
    for i, col in enumerate(HEAT):
        b.append(f'<rect x="{lx + i * 15}" y="{fy - 10}" width="12" height="12" rx="2.5" fill="{col}"/>')
    b.append(text(lx + 5 * 15 + 4, fy, "more", 10, FAINT))
    return window(h, "contributions.sh", "".join(b))


def stats_card(p, c):
    s, h = stats(c["days"]), 262
    b = [prompt(p["prompt_user"], 32, 66, "./stats.sh")]
    best = dt.date.fromisoformat(s["best"]["date"])
    tiles = [(s["current"], "day streak, right now", GREEN if s["current"] else INK),
             (s["longest"], "longest streak (days)", INK),
             (f'{s["active"]}', f'active days of {s["span"]}', INK),
             (s["best"]["count"], f'busiest day · {MONTHS[best.month - 1]} {best.day}', INK)]
    for i, (num, lab, col) in enumerate(tiles):
        x, y = 32 + (i % 2) * 190, 88 + (i // 2) * 80
        d = 0.4 + i * 0.12
        b.append(f'<rect class="a" style="animation-delay:{d:.2f}s" x="{x}" y="{y}" width="178" height="68" '
                 f'rx="8" fill="{BAR}" stroke="{LINE}"/>')
        b.append(text(x + 14, y + 33, num, 24, col, 700, delay=d))
        b.append(text(x + 14, y + 53, lab, 10.5, DIM, delay=d))
    # monthly bars
    x0, x1, base, top = 448, W - 32, 216, 104
    b.append(text(x0, 90, "contributions / month", 10.5, FAINT))
    peak = max(v for _, v in s["months"]) or 1
    step = (x1 - x0) / len(s["months"])
    for i, (ym, v) in enumerate(s["months"]):
        bh = max(3, (base - top) * v / peak)
        x, hot = x0 + i * step, v == peak
        b.append(f'<rect class="g" style="animation-delay:{0.5 + i * 0.06:.2f}s" x="{x + 4:.1f}" '
                 f'y="{base - bh:.1f}" width="{step - 8:.1f}" height="{bh:.1f}" rx="3" '
                 f'fill="{BLUE if hot else HEAT[2]}"/>')
        b.append(text(x + step / 2, base + 16, MONTHS[int(ym[5:]) - 1], 10, FAINT, anchor="middle"))
        if hot:
            b.append(text(x + step / 2, base - bh - 6, v, 10.5, INK, 700, "middle", delay=1.4))
    b.append(f'<rect x="{x0}" y="{base}" width="{x1 - x0}" height="1" fill="{LINE}"/>')
    return window(h, "stats.sh", "".join(b))


def engines(p):
    rows = p["engines"]
    h = 118 + len(rows) * 30 + 42
    b = [prompt(p["prompt_user"], 32, 66, "cat ~/.stack/engines")]
    for x, lab in ((56, "ENGINE"), (190, "MODEL"), (400, "ROLE")):
        b.append(text(x, 96, lab, 10, FAINT, extra=' letter-spacing="1.5"'))
    b.append(f'<rect x="32" y="104" width="{W - 64}" height="1" fill="{LINE}"/>')
    for i, e in enumerate(rows):
        y, d = 128 + i * 30, 0.4 + i * 0.15
        on = e.get("primary")
        b.append(f'<g class="a" style="animation-delay:{d:.2f}s">'
                 f'<circle cx="38" cy="{y - 4}" r="4" fill="{GREEN if on else FAINT}"{" class=\"p\"" if on else ""}/>'
                 f'{text(56, y, e["name"], 13.5, VIOLET if on else INK, 600)}'
                 f'{text(190, y, e["model"], 13.5, INK, 700 if on else 400)}'
                 f'{text(400, y, e["role"], 12.5, DIM)}</g>')
    y = 128 + len(rows) * 30 + 6
    b.append(f'<rect x="32" y="{y - 18}" width="{W - 64}" height="1" fill="{LINE}"/>')
    b.append(text(32, y + 8, "  ·  ".join(p["system"]), 12, DIM, delay=0.4 + len(rows) * 0.15))
    return window(h, "engines", "".join(b))


def strip(p, cmd):
    """Thin one-line window used as a section heading."""
    h = 40
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {h + GAP}" width="{W}" height="{h + GAP}" '
            f'role="img">{STYLE}<rect x=".5" y=".5" width="{W - 1}" height="{h - 1}" rx="10" fill="{BG}" '
            f'stroke="{LINE}"/>{prompt(p["prompt_user"], 20, 25, cmd)}</svg>\n')


def repo_card(r, live, slot):
    """One third of the row. `slot` 0/1/2 decides which side gets the inner gutter."""
    w, h = 290, 172
    x0 = 0 if slot == 0 else 4
    cw = w - x0 - (0 if slot == 2 else 4)
    if slot == 1:
        x0, cw = 2, w - 4
    tx = x0 + 16
    b = [f'<rect x="{x0 + .5}" y=".5" width="{cw - 1}" height="{h - 1}" rx="10" fill="{BG}" stroke="{LINE}"/>',
         f'<text x="{tx}" y="30" font-size="14.5" font-weight="700"><tspan fill="{FAINT}">~/</tspan>'
         f'<tspan fill="{INK}">{esc(r["name"])}</tspan></text>']
    for i, line in enumerate(wrap(r["blurb"], 36)[:4]):
        b.append(text(tx, 54 + i * 16, line, 11, DIM, delay=0.2 + i * 0.08))
    b.append(f'<text x="{tx}" y="130" font-size="10.5"><tspan fill="{VIOLET}">$ </tspan>'
             f'<tspan fill="{INK}">{esc(r["cmd"])}</tspan></text>')
    b.append(f'<rect x="{x0 + 1}" y="142" width="{cw - 2}" height="1" fill="{LINE}"/>')
    lang = live.get("language")
    x = tx
    if lang:
        b.append(f'<circle cx="{x + 4}" cy="155" r="4" fill="{LANG.get(lang, DIM)}"/>')
        b.append(text(x + 13, 159, lang, 10.5, DIM))
        x += 13 + len(lang) * 6.5 + 14
    b.append(text(x, 159, f'★ {live["stars"]}', 10.5, INK, 600))
    b.append(text(x0 + cw - 16, 159, f'{live["forks"]} forks', 10.5, FAINT, anchor="end"))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h + GAP}" width="{w}" '
            f'height="{h + GAP}" role="img">{STYLE}{"".join(b)}</svg>\n')


def main():
    p = load("profile.json")
    if "--offline" in sys.argv:
        c, live = load("contributions.json"), load("repos.json")
    else:
        c = fetch_contributions(p["user"])
        live = fetch_repos(p["user"], [r["name"] for r in p["repos"]])
        save("contributions.json", c)
        save("repos.json", live)
    os.makedirs(CARDS, exist_ok=True)
    out = {"hero": hero(p), "contributions": contributions(p, c), "stats": stats_card(p, c),
           "engines": engines(p), "title-projects": strip(p, "ls ~/projects --sort=stars"),
           "title-usage": strip(p, "tokscale --me")}
    for i, r in enumerate(p["repos"]):
        out[f'repo-{r["name"]}'] = repo_card(r, live[r["name"]], i % 3)
    for name, svg in out.items():
        with open(os.path.join(CARDS, name + ".svg"), "w") as f:
            f.write(svg)
    print(f'{len(out)} cards · {c["total"]} contributions · stats {stats(c["days"])["current"]}d streak')


if __name__ == "__main__":
    main()
