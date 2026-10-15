"""Build a self-contained GitHub Pages artifact; never copy credentials or source data wholesale."""
import html
import json
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from pipeline import ROOT, date, iso, load_archive, editorial_priority, scientific_publication_allowed


def e(value):
    return html.escape(str(value), quote=True)


def shell(title, body, prefix='./'):
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="The Wapiti Bugle. A considered selection of news, with the sources in view.">
<title>{e(title)} · The Wapiti Bugle</title><link rel="stylesheet" href="{prefix}style.css">
<script src="{prefix}app.js" defer></script></head><body><a class="skip" href="#main">Skip to stories</a>
<header><a class="masthead" href="{prefix}index.html"><span>The Wapiti Bugle</span><img class="elk-mark" src="{prefix}elk.png" alt="Bull elk with head raised, bugling" width="110" height="100"></a>
<nav aria-label="Main navigation"><a href="{prefix}index.html">Today's edition</a><a href="{prefix}archive.html">The archive</a></nav></header>
<main id="main">{body}</main><footer><strong>The Wapiti Bugle</strong>
<a href="mailto:wapitibugle@gmail.com">Corrections & feedback</a></footer></body></html>'''


def card(s, prefix='./', homepage=False):
    sources = ''.join(f'<li><a href="{e(x["url"])}" rel="noopener noreferrer">{e(x["publisher"])}: {e(x["title"])}</a></li>' for x in s['sources'])
    verified = s['verification'] == 'human-verified'
    label = 'Human reviewed' if verified else 'Source-reported · not independently verified'
    significance = '<span class="significance" role="img" aria-label="Major development" title="Major development">!!</span> ' if verified and s['tier'] == 'lead' else ''
    claims = ''.join('<li>' + e(c['text']) + ' ' + ' '.join(f'<a href="{e(u)}">Evidence {i + 1}</a>' for i, u in enumerate(c['urls'])) + '</li>' for c in s['claims'])
    more = f'<p>{e(s["context"])}</p>' if s.get('context') else '<p>Read the linked reporting for the full account. Similar headlines are grouped automatically; grouping does not confirm that their claims agree.</p>'
    correction = f'<p class="correction"><strong>Correction:</strong> {e(s["correction"])}</p>' if s.get('correction') else ''
    expired = f'data-published="{e(s["published_at"])}"' if homepage else ''
    return f'''<article class="story" {expired} data-category="{e(s['category'])}">
<div class="kicker">{e(s['category'])} <span> / {e(s['sources'][0]['publisher'])}</span></div>
<h3>{significance}<a href="{e(s['sources'][0]['url'])}" target="_blank" rel="noopener noreferrer">{e(s['title'])}</a></h3>
<p class="timestamp"><time datetime="{e(s['published_at'])}">{e(date(s['published_at']).strftime('%b %d · %H:%M UTC'))}</time></p>
<p class="verification">{label}</p>{correction}
<details><summary>Sources & context <span>{len(s['sources'])}</span></summary><div class="context">{more}<ul>{sources}</ul>{('<h4>Checked claims</h4><ul>' + claims + '</ul>') if claims else ''}<a class="permalink" href="{prefix}s/{e(s['id'])}.html">Permanent link ↗</a></div></details></article>'''


def build():
    out = ROOT / 'dist'
    if out.exists():
        shutil.rmtree(out)
    out.mkdir()
    for name in ('style.css', 'app.js', 'elk.png'):
        shutil.copy(ROOT / 'site' / name, out / name)
    (out / '.nojekyll').write_text('')
    records = load_archive(ROOT / 'data/archive')
    config_path = ROOT / 'config.json'
    config = json.loads(config_path.read_text()) if config_path.exists() else {}
    status_file = ROOT / 'data/status.json'
    status = json.loads(status_file.read_text()) if status_file.exists() else {}
    now = datetime.now(timezone.utc)
    active = sorted([s for s in records if not s.get('withdrawn') and editorial_priority(s, config) and scientific_publication_allowed(s, config) and now - timedelta(hours=24) <= date(s['published_at']) <= now], key=lambda s: (editorial_priority(s, config), s['published_at']), reverse=True)
    sections = []
    for tier, title, description in [('brief', 'The daily brief', 'A broad selection. Headlines belong to the publishers named below.'), ('second', 'Worth a second look', 'Science, ideas, culture, and the world beyond the main news cycle.')]:
        selected = [s for s in active if s['tier'] == tier or (tier == 'brief' and s['tier'] == 'lead')]
        if tier == 'brief':
            selected.sort(key=lambda s: s['tier'] == 'lead' and s['verification'] == 'human-verified', reverse=True)
        if tier == 'second':
            selected = selected[:5]
        content = ''.join(card(s, homepage=True) for s in selected)
        if not content:
            content = '<p class="empty">No stories meet this section’s criteria yet. We leave room rather than lower the standard.</p>'
        sections.append(f'<section class="tier"><div class="section-title"><h2>{title}</h2><p>{description}</p></div><div class="stories">{content}</div></section>')
    collected = status.get('collected_at')
    stamp = f'<time datetime="{e(collected)}">{e(collected)}</time>' if collected else 'Awaiting the first successful collection'
    health = status.get('feeds', [])
    errors = sum(not f['ok'] for f in health)
    feed_notice = f'<p class="notice">{errors} source feeds unavailable at the last collection. Other sources are still included.</p>' if errors else ''
    categories = sorted({s['category'] for s in active})
    buttons = '<button class="selected" data-filter="all" aria-pressed="true">All interests</button>' + ''.join(f'<button data-filter="{e(c)}" aria-pressed="false">{e(c)}</button>' for c in categories)
    body = f'''<div class="edition-line"><span>THE LATEST EDITION</span><span>Last collection: {stamp}</span></div>
{feed_notice}
<div class="filters" aria-label="Filter by interest">{buttons}</div><p id="filter-empty" hidden>No current stories in this interest.</p>
{''.join(sections)}<aside class="archive-banner"><h2>News archive</h2><p>Every published selection remains in our searchable archive.</p><a href="./archive.html">Explore the archive ↗</a></aside>'''
    (out / 'index.html').write_text(shell("Today's edition", body))
    (out / 's').mkdir()
    (out / 'archive').mkdir()
    months = {}
    for s in records:
        months.setdefault(s['first_seen_at'][:7], []).append(s)
        detail = '<h1>Withdrawn story</h1><p>This selection was withdrawn. The record remains for transparency.</p>' + (f'<p>{e(s["correction"])}</p>' if s.get('correction') else '') if s.get('withdrawn') else card(s, prefix='../')
        (out / 's' / (s['id'] + '.html')).write_text(shell('Story record', '<div class="story-page">' + detail + '</div>', '../'))
    links = []
    manifest = []
    for month, stories in sorted(months.items(), reverse=True):
        links.append(f'<li><a href="./archive/{month}.html">{month} · {len(stories)} stories</a></li>')
        (out / 'archive' / (month + '.html')).write_text(shell(month + ' archive', f'<h1>{month} archive</h1>' + ''.join(card(s, '../') for s in stories if not s.get('withdrawn')), '../'))
        index = [dict(id=s['id'], title=s['title'], url=s['sources'][0]['url'], category=s['category'], published_at=s['published_at'], publishers=sorted({x['publisher'] for x in s['sources']})) for s in stories if not s.get('withdrawn')]
        (out / 'archive' / (month + '.json')).write_text(json.dumps(index, ensure_ascii=False))
        manifest.append(month)
    (out / 'archive' / 'manifest.json').write_text(json.dumps(manifest))
    archive_body = '''<div class="archive-intro"><div class="kicker">THE PERMANENT RECORD</div><h1>Search the archive</h1><p>Search every headline, category, and publisher we have selected. New archive months are added automatically; older months are never deliberately pruned.</p></div>
<form id="search-form" role="search"><label for="search">Search the entire archive</label><div class="search-row"><input id="search" type="search" placeholder="A topic, place, or publisher…"><button type="submit">Search ↗</button></div></form>
<p id="search-status" role="status" aria-live="polite"></p><div id="search-results"></div><button id="load-more" hidden>Show more results</button><h2>Browse by month</h2><ul class="months">''' + ''.join(links) + '</ul><noscript><p>JavaScript is required for full archive search. You can browse the months above without it.</p></noscript>'
    (out / 'archive.html').write_text(shell('The archive', archive_body))
    (out / '404.html').write_text(shell('Page not found', '<h1>This page could not be found.</h1><p><a href="/archive.html">Search the archive</a></p>', '/'))
    print(f'Built {len(records)} permanent records; {len(active)} eligible on homepage.')


if __name__ == '__main__':
    build()
