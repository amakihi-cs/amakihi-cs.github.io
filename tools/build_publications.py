#!/usr/bin/env python3
"""
Build the public publication page (publications.html) from
tools/publications.json.

Usage:
    python3 tools/build_publications.py             # render from the JSON, offline
    python3 tools/build_publications.py --refresh   # first fill missing metadata from CrossRef

To add a paper, append {"doi": "..."} (or {"arxiv": "2507.01746"}) to the
"amakihi" list or to a "background" group, then run with --refresh.
"""
import argparse
import html
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SOURCE = REPO / "tools" / "publications.json"
OUT = REPO / "publications.html"
ADS = "https://ui.adsabs.harvard.edu"


def crossref(doi):
    req = urllib.request.Request("https://api.crossref.org/works/" + urllib.parse.quote(doi),
                                 headers={"User-Agent": "amakihi-site"})
    m = json.load(urllib.request.urlopen(req, timeout=30))["message"]
    authors = [(a.get("family") or a.get("name") or "").strip()
               + (", " + "".join(p[0] + "." for p in re.split(r"[\s-]+", a.get("given", "")) if p) if a.get("given") else "")
               for a in m.get("author", [])]
    year = (m.get("published-print") or m.get("published-online") or m.get("issued"))["date-parts"][0][0]
    return dict(title=re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", m["title"][0])).strip(), authors=authors, year=year,
                journal=(m.get("container-title") or [""])[0], volume=m.get("volume"),
                page=m.get("page") or m.get("article-number"))


def arxiv(aid):
    x = urllib.request.urlopen(f"http://export.arxiv.org/api/query?id_list={aid}", timeout=30).read().decode()
    e = re.search(r"<entry>(.*?)</entry>", x, re.S).group(1)
    names = re.findall(r"<name>(.*?)</name>", e)
    return dict(title=re.sub(r"\s+", " ", re.search(r"<title>(.*?)</title>", e, re.S).group(1)).strip(),
                authors=[n.split()[-1] + ", " + "".join(p[0] + "." for p in n.split()[:-1]) for n in names],
                year=int(re.search(r"<published>(\d{4})", e).group(1)), journal="arXiv preprint", volume=None, page=None)


def refresh(papers):
    for p in papers:
        if p.get("title"):
            continue
        meta = crossref(p["doi"]) if p.get("doi") else arxiv(p["arxiv"])
        p.update({k: v for k, v in meta.items() if not p.get(k)})
        print(f"  + {p['year']} {p['authors'][0] if p['authors'] else ''}: {p['title'][:70]}")
        time.sleep(0.2)


def ads_link(p):
    if p.get("bibcode"):
        return f"{ADS}/abs/{urllib.parse.quote(p['bibcode'])}/abstract"
    query = f'doi:"{p["doi"]}"' if p.get("doi") else f'identifier:"arXiv:{p["arxiv"]}"'
    return f"{ADS}/search/q={urllib.parse.quote(query)}"


def authors_text(authors):
    if not authors:
        return ""
    shown = authors[:3]
    return "; ".join(shown) + (" et al." if len(authors) > 3 else "")


def paper_html(p):
    # house style: no long dashes, even inside quoted titles (en dash -> hyphen, em dash -> " - ")
    def e(text):
        # CrossRef metadata sometimes arrives HTML-escaped already ("Astronomy &amp; Astrophysics")
        text = re.sub(r"\s*—\s*", " - ", html.unescape(str(text))).replace("–", "-")
        return html.escape(text)
    where = e(p.get("journal") or "")
    if p.get("volume"):
        where += f" {e(str(p['volume']))}"
    if p.get("page"):
        where += f", {e(str(p['page']).split('-')[0])}"
    links = [f'<a href="{ads_link(p)}">ADS</a>']
    if p.get("doi"):
        links.append(f'<a href="https://doi.org/{e(p["doi"])}">DOI</a>')
    if p.get("arxiv"):
        links.append(f'<a href="https://arxiv.org/abs/{e(p["arxiv"])}">arXiv</a>')
    return (f'        <li><p class="ref-title">{e(p["title"])}</p>'
            f'<p class="ref-meta">{e(authors_text(p["authors"]))} ({p["year"]}), <i>{where}</i>'
            f' · {" · ".join(links)}</p></li>')


def render(src):
    groups = src["background"]
    n_bg = sum(len(g["papers"]) for g in groups)
    years = [p["year"] for g in groups for p in g["papers"]]
    chips = "\n".join(f'      <a class="chip" href="#{g["id"]}">{html.escape(g["title"].split(":")[0])}'
                      f' <span>{len(g["papers"])}</span></a>' for g in groups)
    blocks = []
    for g in groups:
        items = "\n".join(paper_html(p) for p in g["papers"])
        blocks.append(f'    <section class="group" id="{g["id"]}">\n      <h3>{html.escape(g["title"])}</h3>\n'
                      f'      <ol class="refs">\n{items}\n      </ol>\n    </section>')
    if src["amakihi"]:
        amakihi = '      <ol class="refs">\n' + "\n".join(paper_html(p) for p in src["amakihi"]) + "\n      </ol>"
    else:
        amakihi = ('      <div class="empty"><p><b>Nothing yet.</b> ʻAmakihi observations have not started; '
                   "papers based on survey data will be listed here.</p></div>")
    return (TEMPLATE.replace("{{amakihi}}", amakihi)
            .replace("{{chips}}", chips)
            .replace("{{groups}}", "\n".join(blocks))
            .replace("{{n_background}}", str(n_bg))
            .replace("{{year_range}}", f"{min(years)} to {max(years)}"))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--refresh", action="store_true", help="fill missing metadata from CrossRef / arXiv")
    args = ap.parse_args()
    src = json.loads(SOURCE.read_text(encoding="utf-8"))
    if args.refresh:
        refresh(src["amakihi"])
        for g in src["background"]:
            refresh(g["papers"])
            g["papers"].sort(key=lambda p: (-p["year"], p["authors"][0].lower() if p["authors"] else ""))
        SOURCE.write_text(json.dumps(src, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    OUT.write_text(render(src), encoding="utf-8")
    print(f"Wrote {OUT} ({len(src['amakihi'])} ʻAmakihi papers, "
          f"{sum(len(g['papers']) for g in src['background'])} background papers)")


TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ʻAmakihi publications</title>
<meta name="description" content="Publications of the ʻAmakihi community survey and the recent ESPaDOnS and SPIRou work it builds on.">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Ccircle cx='16' cy='16' r='15' fill='%230d1726'/%3E%3Ccircle cx='16' cy='16' r='7' fill='%23cfdc4f'/%3E%3C/svg%3E">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,600&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  :root {
    --bg: #fbfaf6; --surface: #ffffff; --ink: #18202b; --muted: #5a6370; --line: #e3e1d8;
    --accent: #5d6e0f; --accent-soft: #eef2d3;
    --hero-bg: #0d1726; --hero-bg-2: #15263d; --hero-ink: #eef1e6; --hero-muted: #a9b3bf; --hero-accent: #cfdc4f;
    --radius: 14px;
    --serif: "Fraunces", Georgia, "Times New Roman", serif;
    --sans: "Inter", system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
    color-scheme: light;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --bg: #0f1620; --surface: #151e2a; --ink: #e7eae3; --muted: #9ea8b3; --line: #253140;
      --accent: #c9d65a; --accent-soft: #222d1d; --hero-bg: #0a111c; --hero-bg-2: #111d2f;
      color-scheme: dark;
    }
  }
  * { box-sizing: border-box; }
  html { scroll-behavior: smooth; }
  body { margin: 0; background: var(--bg); color: var(--ink); font: 400 1.0625rem/1.6 var(--sans); -webkit-font-smoothing: antialiased; }
  a { color: var(--accent); text-underline-offset: 0.18em; }
  .wrap { max-width: 1080px; margin: 0 auto; padding: 0 16px; }
  @media (min-width: 720px) { .wrap { padding: 0 32px; } }

  .hero { color: var(--hero-ink); background: url("img/sky.svg") center top / 3200px 2000px repeat, radial-gradient(60% 90% at 88% 0%, rgba(207,220,79,.14), transparent 70%), linear-gradient(180deg, var(--hero-bg), var(--hero-bg-2)); }
  .topbar { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 18px 0; }
  .brand { font: 600 1.25rem/1 var(--serif); color: var(--hero-ink); text-decoration: none; }
  .nav { display: flex; align-items: center; gap: 22px; }
  .nav a.link { color: var(--hero-muted); text-decoration: none; font-size: 0.94rem; }
  .nav a.link:hover, .nav a.link[aria-current] { color: var(--hero-ink); }
  @media (max-width: 680px) { .nav a.link { display: none; } }
  .btn-members {
    display: inline-flex; align-items: center; gap: 8px; padding: 8px 14px; border-radius: 999px;
    border: 1px solid rgba(207,220,79,.55); color: var(--hero-accent); text-decoration: none;
    font-size: 0.92rem; font-weight: 500; white-space: nowrap;
  }
  .btn-members:hover { background: rgba(207,220,79,.12); }
  .btn-members svg { width: 16px; height: 16px; flex: none; }
  .hero-body { padding: 36px 0 48px; }
  .eyebrow { margin: 0 0 12px; color: var(--hero-accent); font-size: 0.8rem; font-weight: 600; letter-spacing: 0.14em; text-transform: uppercase; }
  .hero h1 { margin: 0; font: 600 clamp(2.4rem, 8vw, 4rem)/1.05 var(--serif); }
  .hero p.lead { margin: 14px 0 0; max-width: 44rem; color: var(--hero-muted); }

  section.part { padding: 56px 0; border-bottom: 1px solid var(--line); }
  .kicker { margin: 0 0 10px; color: var(--accent); font-size: 0.78rem; font-weight: 600; letter-spacing: 0.14em; text-transform: uppercase; }
  h2 { margin: 0 0 10px; font: 600 clamp(1.7rem, 4vw, 2.2rem)/1.15 var(--serif); }
  .intro { max-width: 46rem; color: var(--muted); margin: 0 0 24px; }
  .empty { background: var(--surface); border: 1px dashed var(--line); border-radius: var(--radius); padding: 22px; color: var(--muted); max-width: 46rem; }
  .empty p { margin: 0; }
  .empty b { color: var(--ink); }

  .chips { display: flex; flex-wrap: wrap; gap: 8px; margin: 0 0 30px; }
  .chip { display: inline-flex; gap: 8px; align-items: center; padding: 5px 12px; border-radius: 999px; border: 1px solid var(--line); background: var(--surface); color: var(--ink); text-decoration: none; font-size: 0.88rem; }
  .chip span { color: var(--accent); font-weight: 600; }
  .chip:hover { border-color: var(--accent); }

  .group { margin: 0 0 36px; scroll-margin-top: 16px; }
  .group h3 { margin: 0 0 12px; font: 600 1.25rem/1.3 var(--serif); }
  .refs { list-style: none; margin: 0; padding: 0; background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius); }
  .refs li { padding: 14px 20px; border-bottom: 1px solid var(--line); }
  .refs li:last-child { border-bottom: 0; }
  .ref-title { margin: 0 0 3px; font-weight: 500; }
  .ref-meta { margin: 0; color: var(--muted); font-size: 0.9rem; overflow-wrap: break-word; }

  footer { padding: 36px 0 48px; color: var(--muted); font-size: 0.9rem; }
  footer p { margin: 0 0 6px; }
</style>
</head>
<body>

<header class="hero">
  <div class="wrap">
    <div class="topbar">
      <a class="brand" href="./">ʻAmakihi</a>
      <nav class="nav" aria-label="Main">
        <a class="link" href="./#science">Science</a>
        <a class="link" href="./#work-packages">Work packages</a>
        <a class="link" href="publications.html" aria-current="page">Publications</a>
        <a class="link" href="https://www.cfht.hawaii.edu/">CFHT</a>
        <a class="btn-members" href="team/" title="Team pages, password protected">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="4.5" y="10.5" width="15" height="10" rx="2"/><path d="M8 10.5V7a4 4 0 0 1 8 0v3.5"/></svg>
          Members
        </a>
      </nav>
    </div>
    <div class="hero-body">
      <p class="eyebrow">ʻAmakihi community survey</p>
      <h1>Publications</h1>
      <p class="lead">Papers from the survey, and the recent ESPaDOnS and SPIRou work it builds on. Links go to the NASA Astrophysics Data System (ADS) and to the journals.</p>
    </div>
  </div>
</header>

<main>
  <section class="part" id="amakihi">
    <div class="wrap">
      <p class="kicker">Survey papers</p>
      <h2>ʻAmakihi</h2>
{{amakihi}}
    </div>
  </section>

  <section class="part" id="background" style="border-bottom:0">
    <div class="wrap">
      <p class="kicker">Background effort</p>
      <h2>The work ʻAmakihi builds on</h2>
      <p class="intro">{{n_background}} papers published from {{year_range}} that use ESPaDOnS and SPIRou in the science areas of the survey, grouped by work package. This selection is not exhaustive; it was assembled from literature searches and from the references of the survey proposal.</p>
      <nav class="chips" aria-label="Groups">
{{chips}}
      </nav>
{{groups}}
    </div>
  </section>
</main>

<footer>
  <div class="wrap">
    <p><a href="./">ʻAmakihi</a> · a Wenaokeao community survey at the <a href="https://www.cfht.hawaii.edu/">Canada-France-Hawaii Telescope</a>, Maunakea, Hawaiʻi.</p>
  </div>
</footer>

</body>
</html>
"""

if __name__ == "__main__":
    main()
