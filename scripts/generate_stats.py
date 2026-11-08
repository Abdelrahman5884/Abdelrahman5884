#!/usr/bin/env python3
"""Generates the animated profile SVGs (stats, languages, streaks, contribution snake).

Data sources (no third-party services):
  1. GitHub API (needs GITHUB_TOKEN - provided automatically inside GitHub Actions)
  2. Fallback: the public github.com profile pages (works without any token)

Usage: generate_stats.py [--mock]
"""
import json, os, re, sys, datetime, random, html as htmllib, urllib.request

USER = os.environ.get("GH_USER", "Abdelrahman5884")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
OUT = os.environ.get("OUT_DIR", "assets")
BG, PANEL, LINE = "#13110f", "#1b1815", "#302a25"
ACC, SAND, MUTE, SAGE, GOLD = "#ff6b3d", "#ece0c8", "#9a8f80", "#8fbf9f", "#f2b134"
SANS = "'Segoe UI','Helvetica Neue',Arial,sans-serif"
MONO = "'JetBrains Mono','SFMono-Regular',Consolas,'Courier New',monospace"
SERIF = "Georgia,'Times New Roman',serif"
UA = "Mozilla/5.0 (compatible; profile-stats)"

# ------------------------------------------------------------------ data
def http(url, data=None, auth=False):
    req = urllib.request.Request(url, data=json.dumps(data).encode() if data else None)
    req.add_header("User-Agent", UA)
    if auth and TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.read().decode("utf-8", "replace")

def api(url, data=None):
    return json.loads(http(url, data, auth=True))

def weekday(date): return (datetime.date.fromisoformat(date).weekday() + 1) % 7  # Sunday = 0

def from_api():
    if not TOKEN:
        raise RuntimeError("no token")
    user = api(f"https://api.github.com/users/{USER}")
    repos = [r for r in api(f"https://api.github.com/users/{USER}/repos?per_page=100&type=owner") if not r["fork"]]
    langs = {}
    for r in repos:
        try:
            for k, v in api(r["languages_url"]).items():
                langs[k] = langs.get(k, 0) + v
        except Exception:
            if r.get("language"):
                langs[r["language"]] = langs.get(r["language"], 0) + 1
    q = "query($u:String!){user(login:$u){contributionsCollection{contributionCalendar{weeks{contributionDays{date contributionCount}}}}}}"
    res = api("https://api.github.com/graphql", {"query": q, "variables": {"u": USER}})
    weeks = [[{"date": d["date"], "c": d["contributionCount"], "wd": weekday(d["date"])} for d in w["contributionDays"]]
             for w in res["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]]
    return {"weeks": weeks, "repos": len(repos), "stars": sum(r["stargazers_count"] for r in repos),
            "followers": user["followers"], "langs": langs, "langs_unit": "by code size"}

def num(s):
    s = s.strip().replace(",", "")
    try:
        return int(float(s[:-1]) * 1000) if s.endswith("k") else int(s)
    except ValueError:
        return 0

def from_web():
    page = http(f"https://github.com/users/{USER}/contributions")
    tips = {}
    for m in re.finditer(r'<tool-tip[^>]*for="([^"]+)"[^>]*>([^<]*)</tool-tip>', page):
        t = m.group(2).strip(); n = re.match(r"(\d+) contribution", t)
        tips[m.group(1)] = int(n.group(1)) if n else 0
    cols = {}
    for m in re.finditer(r"<td[^>]*ContributionCalendar-day[^>]*>", page):
        tag = m.group(0)
        date = re.search(r'data-date="([^"]+)"', tag); ix = re.search(r'data-ix="(\d+)"', tag); ident = re.search(r'id="([^"]+)"', tag)
        if date and ix and ident:
            cols.setdefault(int(ix.group(1)), []).append({"date": date.group(1), "c": tips.get(ident.group(1), 0), "wd": weekday(date.group(1))})
    weeks = [sorted(cols[k], key=lambda x: x["wd"]) for k in sorted(cols)]
    if not weeks:
        raise RuntimeError("calendar not found")
    names, stars, langs = set(), 0, {}
    for pg in range(1, 6):
        rp = http(f"https://github.com/{USER}?tab=repositories&page={pg}")
        parts = re.split(r'(?=itemprop="name codeRepository")', rp)[1:]
        new = 0
        for seg in parts:
            nm = re.search(r'itemprop="name codeRepository"[^>]*>\s*([^<\s]+)', seg)
            if not nm or nm.group(1) in names:
                continue
            seg = seg.split("</li>")[0]
            if "Forked from" in seg:
                continue
            names.add(nm.group(1)); new += 1
            st = re.search(r'/stargazers"[^>]*>(.*?)</a>', seg, re.S)
            if st:
                stars += num(re.sub(r"<[^>]+>", "", st.group(1)))
            lg = re.search(r'itemprop="programmingLanguage">([^<]+)', seg)
            if lg:
                k = htmllib.unescape(lg.group(1).strip()); langs[k] = langs.get(k, 0) + 1
        if not new:
            break
    prof = http(f"https://github.com/{USER}")
    fm = re.search(r'tab=followers"[^>]*>.*?<span[^>]*>\s*([\d.,k]+)\s*</span>', prof, re.S)
    return {"weeks": weeks, "repos": len(names), "stars": stars, "followers": num(fm.group(1)) if fm else 0,
            "langs": langs, "langs_unit": "by repositories"}

def collect():
    try:
        return from_api()
    except Exception as e:
        print("API path failed, using public pages:", e)
        return from_web()

def synth(fn):
    today = datetime.date.today(); start = today - datetime.timedelta(days=364)
    start -= datetime.timedelta(days=(start.weekday() + 1) % 7)
    weeks, d = [], start
    while d <= today:
        wk = []
        for _ in range(7):
            if d <= today:
                wk.append({"date": str(d), "c": fn(), "wd": (d.weekday() + 1) % 7})
            d += datetime.timedelta(days=1)
        weeks.append(wk)
    return weeks

def mock():
    random.seed(3)
    return {"weeks": synth(lambda: random.choice([0, 0, 0, 1, 2, 4, 6, 9, 3])), "repos": 19, "stars": 12, "followers": 19,
            "langs": {"PHP": 7, "Blade": 4, "Jupyter Notebook": 3, "JavaScript": 2, "HTML": 1, "Python": 1}, "langs_unit": "by repositories"}

STAMP = datetime.date.today().isoformat()
def fmt(n): return f"{n:,}"

# ------------------------------------------------------------------ shared card frame
def frame(wd, ht, title, inner, sub=""):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 {wd} {ht}" width="{wd}" height="{ht}">
<defs><style>
.t{{font:700 13px {SANS};fill:{SAND};letter-spacing:2.4px;text-transform:uppercase}}
.k{{font:500 13.5px {SANS};fill:{SAND}}}
.v{{font:700 14px {MONO};fill:{SAND}}}
.n{{font:500 11px {MONO};fill:{MUTE}}}
.rise{{opacity:0;transform:translateY(14px);animation:rs .8s cubic-bezier(.2,.8,.2,1) forwards}}
.g{{transform-box:fill-box;transform-origin:left center;transform:scaleX(0);animation:gr 1.2s cubic-bezier(.2,.8,.2,1) forwards}}
@keyframes rs{{to{{opacity:1;transform:translateY(0)}}}}
@keyframes gr{{to{{transform:scaleX(1)}}}}
</style></defs>
<rect x="1" y="1" width="{wd-2}" height="{ht-2}" rx="18" fill="{PANEL}" stroke="{LINE}" stroke-width="1.5"/>
<circle cx="30" cy="31" r="4" fill="{ACC}"><animate attributeName="opacity" values="1;.25;1" dur="2.2s" repeatCount="indefinite"/></circle>
<text class="t" x="44" y="36">{title}</text>
{sub}
{inner}
</svg>'''

IC = {
 "total": '<path d="M1 8h3l2-5 3 10 2-5h4"/>',
 "cal": '<rect x="2" y="3" width="12" height="11" rx="2"/><path d="M2 7h12M5 1.5v3M11 1.5v3"/>',
 "bolt": '<path d="M9 1L3 9h4l-1 6 7-8H9z"/>',
 "star": '<path d="M8 1.6l2 4.3 4.6.5-3.4 3.1 1 4.5L8 11.6 3.8 14l1-4.5L1.4 6.4 6 5.9z"/>',
 "repo": '<path d="M3 2h10v12H3zM3 11h10"/>',
 "people": '<circle cx="6" cy="5" r="2.6"/><path d="M1 14c0-3 2-4.6 5-4.6s5 1.6 5 4.6M11 3a2.4 2.4 0 0 1 0 4.4M13 14c0-2-.8-3.3-2-4"/>',
}
def icon(k, x, y, col):
    return f'<g transform="translate({x},{y})" fill="none" stroke="{col}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">{IC[k]}</g>'

def flat(d): return [x for w in d["weeks"] for x in w]

def stats_svg(d):
    days = flat(d); cs = [x["c"] for x in days]
    rows = [("total", "Contributions", sum(cs)), ("cal", "Active days", sum(1 for c in cs if c)), ("bolt", "Best day", max(cs + [0])),
            ("repo", "Public repos", d["repos"]), ("star", "Stars earned", d["stars"]), ("people", "Followers", d["followers"])]
    mx = [max(sum(1 for _ in cs) and sum(cs), 1), max(len(cs), 1), max(max(cs + [0]), 1), None, None, None]
    out = []
    for i, (ic, k, v) in enumerate(rows):
        y = 86 + i * 29
        col = ACC if i % 2 == 0 else GOLD
        ref = {0: max(sum(cs), 1), 1: max(len(cs), 1), 2: max(max(cs + [0]) * 1.25, 1), 3: max(d["repos"] * 1.5, 1), 4: max(d["stars"] * 2, 5), 5: max(d["followers"] * 2, 10)}[i]
        bw = max(3, round(min(v / ref, 1) * 100)) if v else 3
        out.append(f'<g class="rise" style="animation-delay:{0.1+i*0.08:.2f}s">{icon(ic, 26, y-14, col)}<text class="k" x="52" y="{y-1}">{k}</text><rect x="226" y="{y-10}" width="100" height="6" rx="3" fill="{SAND}" fill-opacity="0.08"/><rect class="g" x="226" y="{y-10}" width="{bw}" height="6" rx="3" fill="{col}" style="animation-delay:{0.2+i*0.1:.2f}s"/><text class="v" x="414" y="{y-1}" text-anchor="end">{fmt(v)}</text></g>')
    return frame(440, 268, "GitHub stats", "".join(out), f'<text class="n" x="414" y="36" text-anchor="end">updated {STAMP}</text>')

def langs_svg(d):
    tot = sum(d["langs"].values()) or 1
    top = sorted(d["langs"].items(), key=lambda x: -x[1])[:6]
    cols = [ACC, SAGE, GOLD, SAND, "#c9693a", MUTE]
    out = [f'<clipPath id="bc"><rect x="24" y="62" width="392" height="12" rx="6"/></clipPath><rect x="24" y="62" width="392" height="12" rx="6" fill="{SAND}" fill-opacity="0.08"/>']
    x, segs = 24, []
    for i, (k, v) in enumerate(top):
        wd = v / tot * 392
        segs.append(f'<rect x="{x:.1f}" y="62" width="{max(wd-2,1):.1f}" height="12" fill="{cols[i]}"/>'); x += wd
    out.append(f'<g clip-path="url(#bc)">{"".join(segs)}<rect x="24" y="60" width="392" height="16" fill="{PANEL}"><animate attributeName="x" from="24" to="420" dur="1.3s" fill="freeze" calcMode="spline" keyTimes="0;1" keySplines=".2 .8 .2 1"/></rect></g>')
    for i, (k, v) in enumerate(top):
        cx = 24 if i % 2 == 0 else 232; y = 112 + (i // 2) * 44
        out.append(f'<g class="rise" style="animation-delay:{0.3+i*0.08:.2f}s"><circle cx="{cx+5}" cy="{y-4}" r="5" fill="{cols[i]}"/><text class="k" x="{cx+18}" y="{y}">{htmllib.escape(k)}</text><text class="n" x="{cx+18}" y="{y+17}">{v/tot*100:.1f}%</text></g>')
    return frame(440, 268, "Top languages", "".join(out), f'<text class="n" x="414" y="36" text-anchor="end">{d.get("langs_unit","")}</text>')

def streaks(days):
    cnt = [x["c"] for x in days]; longest = run = 0
    for c in cnt:
        run = run + 1 if c > 0 else 0; longest = max(longest, run)
    cur, i = 0, len(cnt) - 1
    if i >= 0 and cnt[i] == 0: i -= 1
    while i >= 0 and cnt[i] > 0: cur += 1; i -= 1
    return cur, longest

def streak_svg(d):
    days = flat(d); cur, longest = streaks(days); total = sum(x["c"] for x in days)
    rng = f'{days[0]["date"]}  to  {days[-1]["date"]}'
    frac = min(cur / max(longest, 1), 1) if longest else 0
    circ = 2 * 3.14159 * 46
    inner = f'''<g class="rise" style="animation-delay:.1s"><text x="150" y="98" text-anchor="middle" font-family="{SERIF}" font-size="46" fill="{SAND}">{fmt(total)}</text><text x="150" y="124" text-anchor="middle" class="k" fill-opacity=".85">Contributions this year</text><text x="150" y="144" text-anchor="middle" class="n">{rng}</text></g>
<rect x="300" y="60" width="1.5" height="92" fill="{LINE}"/><rect x="598" y="60" width="1.5" height="92" fill="{LINE}"/>
<g class="rise" style="animation-delay:.25s"><circle cx="450" cy="96" r="46" fill="none" stroke="{SAND}" stroke-opacity="0.1" stroke-width="6"/>
<circle cx="450" cy="96" r="46" fill="none" stroke="{ACC}" stroke-width="6" stroke-linecap="round" stroke-dasharray="{circ:.1f}" stroke-dashoffset="{circ:.1f}" transform="rotate(-90 450 96)"><animate attributeName="stroke-dashoffset" from="{circ:.1f}" to="{circ*(1-frac):.1f}" dur="1.6s" begin=".4s" fill="freeze" calcMode="spline" keyTimes="0;1" keySplines=".2 .8 .2 1"/></circle>
<text x="450" y="108" text-anchor="middle" font-family="{SERIF}" font-size="38" fill="{SAND}">{cur}</text><text x="450" y="162" text-anchor="middle" class="k" fill="{ACC}">Current streak</text></g>
<g class="rise" style="animation-delay:.4s"><text x="750" y="98" text-anchor="middle" font-family="{SERIF}" font-size="46" fill="{SAND}">{longest}</text><text x="750" y="124" text-anchor="middle" class="k" fill-opacity=".85">Longest streak</text><text x="750" y="144" text-anchor="middle" class="n">days in a row</text></g>'''
    return frame(900, 176, "Streaks", inner)

# ------------------------------------------------------------------ the snake game
def snake_svg(d):
    weeks = d["weeks"]; days = flat(d)
    nz = sorted(x["c"] for x in days if x["c"] > 0)
    q = (lambda p: nz[min(int(len(nz) * p), len(nz) - 1)]) if nz else (lambda p: 1)
    t1, t2, t3 = q(0.25), q(0.5), q(0.75)
    cols = ["#241f1b", "#5a2f1f", "#8f3f21", "#d4572a", "#ff7a4d"]
    EAT = cols[0]
    lvl = lambda c: 0 if c == 0 else 1 if c <= t1 else 2 if c <= t2 else 3 if c <= t3 else 4
    step, cell, x0, y0 = 15.6, 12, 44, 84
    # snake path: column by column, zig-zag, entering from the left and leaving to the right
    pts, owner = [], []
    first_y = y0 + cell / 2
    pts.append((x0 - 46, first_y)); owner.append(None)
    for ci, wk in enumerate(weeks):
        seq = wk if ci % 2 == 0 else list(reversed(wk))
        for x in seq:
            pts.append((x0 + ci * step + cell / 2, y0 + x["wd"] * step + cell / 2)); owner.append((ci, x))
    last = pts[-1]; pts.append((last[0] + 50, last[1])); owner.append(None)
    dist = [0.0]
    for a, b in zip(pts, pts[1:]):
        dist.append(dist[-1] + ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5)
    L = dist[-1]; speed = 170.0  # px per second
    D = L / speed
    path_d = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    eat_t = {}
    for p, o, dd in zip(pts, owner, dist):
        if o: eat_t[(o[0], o[1]["date"])] = dd / L
    cells, months, lastm = [], [], ""
    for ci, wk in enumerate(weeks):
        m = wk[0]["date"][5:7]
        if m != lastm and ci < len(weeks) - 2:
            months.append(f'<text class="n" x="{x0+ci*step:.1f}" y="72">{["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"][int(m)-1]}</text>'); lastm = m
        for x in wk:
            l = lvl(x["c"]); cx, cy = x0 + ci * step, y0 + x["wd"] * step
            anim = ""
            if l:
                kt = min(max(eat_t[(ci, x["date"])], 0.001), 0.999)
                anim = f'<animate attributeName="fill" values="{cols[l]};{EAT}" keyTimes="0;{kt:.4f}" calcMode="discrete" dur="{D:.2f}s" repeatCount="indefinite"/>'
            cells.append(f'<rect class="cl" x="{cx:.1f}" y="{cy:.1f}" width="{cell}" height="{cell}" rx="3" fill="{cols[l]}" style="animation-delay:{ci*0.02:.2f}s">{anim}</rect>')
    n_seg = 9; lag = D / (len(pts) - 1) * 1.0
    lag = 15.6 / speed  # one cell of lag per segment
    body = []
    for i in range(n_seg, 0, -1):
        op = 0.95 - (i - 1) * 0.07; sz = 11 if i > 1 else 11.5
        body.append(f'<rect x="{-sz/2}" y="{-sz/2}" width="{sz}" height="{sz}" rx="3.2" fill="{SAGE}" fill-opacity="{op:.2f}" opacity="0"><set attributeName="opacity" to="1" begin="{i*lag:.3f}s"/><animateMotion dur="{D:.2f}s" begin="{i*lag:.3f}s" repeatCount="indefinite" calcMode="linear"><mpath xlink:href="#sp"/></animateMotion></rect>')
    head = f'<g opacity="0"><set attributeName="opacity" to="1" begin="0s"/><animateMotion dur="{D:.2f}s" repeatCount="indefinite" calcMode="linear"><mpath xlink:href="#sp"/></animateMotion><rect x="-7.5" y="-7.5" width="15" height="15" rx="4.5" fill="#c4efd2" stroke="{BG}" stroke-width="1.5"/><circle cx="2.5" cy="-2.6" r="1.5" fill="{BG}"/><circle cx="2.5" cy="2.6" r="1.5" fill="{BG}"/></g>'
    total = sum(x["c"] for x in days)
    active = sum(1 for x in days if x["c"])
    leg = "".join(f'<rect x="{722+i*18}" y="226" width="12" height="12" rx="3" fill="{c}"/>' for i, c in enumerate(cols))
    inner = f'''<defs><path id="sp" d="{path_d}"/><style>.cl{{opacity:0;animation:cf .5s ease forwards}}@keyframes cf{{to{{opacity:1}}}}</style></defs>
<text class="n" x="14" y="{y0+step*1+10:.0f}">Mon</text><text class="n" x="14" y="{y0+step*3+10:.0f}">Wed</text><text class="n" x="14" y="{y0+step*5+10:.0f}">Fri</text>
{"".join(months)}{"".join(cells)}{"".join(body)}{head}
<text class="n" x="44" y="236">Snake eats {active} active days</text>
<rect x="270" y="229" width="160" height="6" rx="3" fill="{SAND}" fill-opacity="0.1"/><rect x="270" y="229" width="0" height="6" rx="3" fill="{SAGE}"><animate attributeName="width" values="0;160;160" keyTimes="0;0.97;1" dur="{D:.2f}s" repeatCount="indefinite"/></rect>
<text class="n" x="696" y="236" text-anchor="end">Less</text>{leg}<text class="n" x="824" y="236">More</text>'''
    sub = f'<text class="n" x="856" y="36" text-anchor="end">{fmt(total)} contributions in the last year</text>'
    return frame(900, 256, "Contribution snake", inner, sub)

if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    data = mock() if "--mock" in sys.argv else collect()
    for name, fn in [("stats", stats_svg), ("langs", langs_svg), ("streak", streak_svg), ("snake", snake_svg)]:
        open(f"{OUT}/{name}.svg", "w", encoding="utf-8").write(fn(data))
    print("generated for", USER)
