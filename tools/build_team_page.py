#!/usr/bin/env python3
"""
Compile the private ʻAmakihi wiki into the password-protected team page.

Every wiki page is converted from Markdown, laid out with the site's style
(tools/team_template.html), and the result is encrypted with StatiCrypt into
team/index.html. This repository is public: only the encrypted file is ever
written into it, and the clear page only goes to --preview, outside the repository.

Usage:
    python3 tools/build_team_page.py                 # pull the wiki, build, encrypt
    python3 tools/build_team_page.py --no-pull       # use the local wiki as it is
    python3 tools/build_team_page.py --preview /tmp/team.html   # also save the clear page

The password is read from $AMAKIHI_TEAM_PASSWORD, or else from the first line
of .team_password at the repository root (git-ignored). StatiCrypt's salt is
kept in tools/staticrypt.json so that "Remember me" survives rebuilds.

The page only changes when the wiki does: team/source.sha256 holds a hash of
the clear page, and the encryption is skipped when it matches (--force to
encrypt anyway, e.g. after a password change). A git mailmap merging the
names of one person (it contains e-mail addresses, so it is kept in the
private repository) can be passed with --mailmap.
"""
import argparse
import datetime
import hashlib
import html
import os
import re
import string
import subprocess
import sys
import tempfile
from pathlib import Path

import markdown

REPO = Path(__file__).resolve().parent.parent
WIKI_URL = "https://github.com/eartigau/amakihi/wiki"
STATICRYPT = "staticrypt@3.5.4"
SKIP = {"_Sidebar", "_Footer", "_Header"}


MAILMAP = None   # set from --mailmap


def git(wiki, *args):
    # the mailmap merges the names under which one person committed (%aN)
    config = ["-c", f"mailmap.file={MAILMAP}"] if MAILMAP else []
    return subprocess.run(["git", *config, "-C", str(wiki), *args], check=True,
                          capture_output=True, text=True).stdout.strip()


def anchor(name):
    return "p-" + re.sub(r"[^A-Za-z0-9_-]", "-", name)


WIKI_LINK = r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]"


def layout(wiki, names):
    """
    Groups and order of the pages, taken from the wiki's _Sidebar.md: a bold
    line starts a group, an indented link is a sub-page. Returns
    [(group, [(page, label, is_sub)])]; pages missing from the sidebar go last.
    """
    side = wiki / "_Sidebar.md"
    lines = side.read_text(encoding="utf-8").splitlines() if side.exists() else []
    groups, seen, group = [], set(), ("Pages", [])
    for line in lines:
        head = re.fullmatch(r"\s*\*\*(.+?)\*\*\s*", line)
        if head:
            if group[1]:
                groups.append(group)
            group = (head.group(1), [])
            continue
        m = re.search(WIKI_LINK, line)
        if not m:
            continue
        label, target = (m.group(1), m.group(2)) if m.group(2) else (m.group(1), m.group(1))
        target = target.strip().replace(" ", "-")
        if target not in seen:
            seen.add(target)
            group[1].append((target, label.strip(), len(line) - len(line.lstrip()) >= 2))
    if group[1]:
        groups.append(group)
    if "Home" in names and "Home" not in seen:
        groups.insert(0, ("Start", [("Home", "Home", False)]))
        seen.add("Home")
    rest = sorted(names - seen, key=str.lower)
    if rest:
        groups.append(("Other pages", [(n, n.replace("-", " "), False) for n in rest]))
    return groups


def convert(text, names):
    """Markdown of one wiki page -> (title or None, HTML body)."""

    def wiki_link(m):
        first, second = m.group(1).strip(), m.group(2)
        label, target = (first, second.strip()) if second else (first, first)
        target = target.replace(" ", "-")
        href = "#" + anchor(target) if target in names else f"{WIKI_URL}/{target}"
        return f"[{label}]({href})"

    text = re.sub(WIKI_LINK, wiki_link, text)
    body = markdown.markdown(text, extensions=["tables", "fenced_code", "sane_lists"])

    # links written as plain Markdown to another wiki page, e.g. (WP1-Nearby-exoplanets)
    def page_href(m):
        target = m.group(1)
        if target in names:
            return f'href="#{anchor(target)}"'
        return f'href="{WIKI_URL}/{target}"'

    body = re.sub(r'href="([A-Za-z0-9_.%-]+)"', page_href, body)
    body = re.sub(r"<script\b.*?</script>", "", body, flags=re.S | re.I)

    # the page's own top-level heading becomes its title
    title = None
    m = re.match(r"\s*<h1>(.*?)</h1>", body, flags=re.S)
    if m:
        title, body = m.group(1), body[m.end():]
    # the page title is an h2 in the compiled page, so every heading moves down one level
    body = re.sub(r"<(/?)h([1-5])>", lambda h: f"<{h.group(1)}h{int(h.group(2)) + 1}>", body)
    body = body.replace("<table>", '<div class="table-wrap"><table>').replace("</table>", "</table></div>")
    return title, body


def build(wiki):
    names = {p.stem for p in wiki.glob("*.md") if p.stem not in SKIP}

    toc, articles = [], []
    for group, entries in layout(wiki, names):
        items = []
        for name, label, sub in entries:
            cls = ["sub"] if sub else []
            if name not in names:
                # listed in the sidebar but not written yet: point to the wiki to create it
                items.append(f'      <li class="{" ".join(cls + ["missing"])}"><a href="{WIKI_URL}/{name}">'
                             f'{html.escape(label)} <span>(to write)</span></a></li>')
                continue
            path = wiki / f"{name}.md"
            title, body = convert(path.read_text(encoding="utf-8"), names)
            title = title or html.escape(name.replace("-", " "))
            who, when = git(wiki, "log", "-1", "--format=%aN%x1f%ad", "--date=short", "--", path.name).split("\x1f")
            authors = sorted(set(git(wiki, "log", "--format=%aN", "--", path.name).splitlines()))
            meta = (f"Last edited by {html.escape(who)} on {when}"
                    f" · {len(authors)} contributor{'s' if len(authors) > 1 else ''}: {html.escape(', '.join(authors))}"
                    f' · <a href="{WIKI_URL}/{name}">edit in the wiki</a>')
            articles.append(
                f'    <article class="page" id="{anchor(name)}">\n'
                f'      <div class="page-head"><h2>{title}</h2><p class="meta">{meta}</p></div>\n'
                f'      <div class="content">\n{body}\n      </div>\n    </article>')
            cls_attr = f' class="{" ".join(cls)}"' if cls else ""
            items.append(f'      <li{cls_attr}><a href="#{anchor(name)}">{html.escape(label)}</a></li>')
        toc.append(f'    <p class="toc-title">{html.escape(group)}</p>\n    <ul>\n' + "\n".join(items) + "\n    </ul>")

    # last commits of the wiki, newest first
    changes = []
    log = git(wiki, "log", "-n", "12", "--date=short", "--format=%x1e%aN%x1f%ad%x1f%s", "--name-only")
    for entry in filter(None, log.split("\x1e")):
        head, *touched = entry.strip().split("\n")
        who, when, subject = head.split("\x1f")
        links = ", ".join(
            f'<a href="#{anchor(Path(f).stem)}">{html.escape(Path(f).stem.replace("-", " "))}</a>'
            if Path(f).stem in names else html.escape(Path(f).stem)
            for f in touched if f.endswith(".md"))
        changes.append(f'        <li><span class="when">{when}</span>'
                       f'<span><span class="who">{html.escape(who)}</span> '
                       f'<span class="what">{html.escape(subject)}{" · " + links if links else ""}</span></span></li>')

    template = string.Template((REPO / "tools" / "team_template.html").read_text(encoding="utf-8"))
    return template.substitute(
        wiki_url=WIKI_URL,
        # date of the last wiki commit, not of the build, so that an unchanged wiki gives the same page
        built=datetime.datetime.fromisoformat(git(wiki, "log", "-1", "--format=%cI"))
        .astimezone(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        commit=git(wiki, "rev-parse", "--short", "HEAD"),
        toc="\n".join(toc),
        changes="\n".join(changes),
        pages="\n".join(articles),
    ), len(articles)


def main():
    global MAILMAP
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--wiki", type=Path, default=REPO.parent / "amakihi.wiki",
                    help="local clone of amakihi.wiki.git (default: next to this repository)")
    ap.add_argument("--no-pull", action="store_true", help="do not pull the wiki first")
    ap.add_argument("--preview", type=Path, help="also save the unencrypted page here (never inside this repository)")
    ap.add_argument("--mailmap", type=Path, help="git mailmap merging the names of one person")
    ap.add_argument("--force", action="store_true", help="encrypt even if the wiki has not changed")
    args = ap.parse_args()
    MAILMAP = args.mailmap.resolve() if args.mailmap else None

    password = os.environ.get("AMAKIHI_TEAM_PASSWORD", "").strip()
    if not password and (REPO / ".team_password").exists():
        password = (REPO / ".team_password").read_text(encoding="utf-8").splitlines()[0].strip()
    if not password:
        sys.exit("No password: set AMAKIHI_TEAM_PASSWORD or write it in .team_password")
    if args.preview and REPO in args.preview.resolve().parents:
        sys.exit("--preview must not point inside this repository: everything in it is public")

    if not args.no_pull:
        git(args.wiki, "pull", "--ff-only", "--quiet")
    page, n_pages = build(args.wiki)
    if args.preview:
        args.preview.write_text(page, encoding="utf-8")
        print(f"Unencrypted preview: {args.preview}")

    out_dir = REPO / "team"
    out_dir.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(page.encode("utf-8")).hexdigest()
    stamp = out_dir / "source.sha256"
    if not args.force and (out_dir / "index.html").exists() and stamp.exists() \
            and stamp.read_text().strip() == digest:
        print(f"Wiki unchanged ({n_pages} pages): {out_dir / 'index.html'} left as it is")
        return
    with tempfile.TemporaryDirectory() as tmp:
        clear = Path(tmp) / "index.html"
        clear.write_text(page, encoding="utf-8")
        run = subprocess.run(
            ["npx", "--yes", STATICRYPT, str(clear), "-d", str(out_dir),
             # StatiCrypt prefixes the config path with "./", so it must be relative to cwd
             "--config", "tools/staticrypt.json", "--short", "--remember", "30",
             "--template-title", "ʻAmakihi team pages",
             "--template-instructions", "Team members only. Enter the ʻAmakihi team password.",
             "--template-button", "Open",
             "--template-placeholder", "Team password",
             "--template-remember", "Remember me on this device for 30 days",
             "--template-color-primary", "#5d6e0f",
             "--template-color-secondary", "#0d1726"],
            cwd=REPO, env={**os.environ, "STATICRYPT_PASSWORD": password}, capture_output=True, text=True)
        if run.returncode:
            sys.exit(f"StatiCrypt failed:\n{run.stdout}{run.stderr}")
    stamp.write_text(digest + "\n")
    print(f"Compiled {n_pages} wiki pages into {out_dir / 'index.html'} (encrypted)")


if __name__ == "__main__":
    main()
