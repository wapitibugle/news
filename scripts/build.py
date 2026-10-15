"""Build a self-contained GitHub Pages artifact; never copy credentials or source data wholesale."""
import html
import json
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from pipeline import ROOT, date, iso, load_archive


def e(value):
    return html.escape(str(value), quote=True)


def shell(title, body, prefix='./'):
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="The Wapiti Bugle. A considered selection of news, with the sources in view.">
<title>{e(title)} · The Wapiti Bugle</title><link rel="stylesheet" href="{prefix}style.css">
<script src="{prefix}app.js" defer></script></head><body><a class="skip" href="#main">Skip to stories</a>
<header><a class="masthead" href="{prefix}index.html"><span>The Wapiti Bugle</span><img class="elk-mark" src="{prefix}elk.png" alt="Bull elk with head raised, bugling" width="110" height="100"></a>
<nav aria-label="Main navigation"><a href="{prefix}index.html">Today's edition</a><a href="{prefix}archive.html">The archive</a><a href="{prefix}about.html">Our standards</a></nav></header>
<main id="main">{body}</main><footer><strong>The Wapiti Bugle</strong>
<a href="{prefix}about.html">How we work</a> · <a href="mailto:wapitibugle@gmail.com">Corrections & feedback</a></footer></body></html>'''


def card(s, prefix='./', homepage=False):
    sources = ''.join(f'<li><a href="{e(x["url"])}" rel="noopener noreferrer">{e(x["publisher"])}: {e(x["title"])}</a></li>' for x in s['sources'])
    verified = s['verification'] == 'human-verified'
    label = 'Human reviewed' if verified else 'Source-reported · not independently verified'
    claims = ''.join('<li>' + e(c['text']) + ' ' + ' '.join(f'<a href="{e(u)}">Evidence {i + 1}</a>' for i, u in enumerate(c['urls'])) + '</li>' for c in s['claims'])
    more = f'<p>{e(s["context"])}</p>' if s.get('context') else '<p>Read the linked reporting for the full account. Similar headlines are grouped automatically; grouping does not confirm that their claims agree.</p>'
    correction = f'<p class="correction"><strong>Correction:</strong> {e(s["correction"])}</p>' if s.get('correction') else ''
    expired = f'data-published="{e(s["published_at"])}"' if homepage else ''
    return f'''<article class="story" {expired} data-category="{e(s['category'])}">
<div class="kicker">{e(s['category'])} <span> / {e(s['sources'][0]['publisher'])}</span></div>
<h3><a href="{prefix}s/{e(s['id'])}.html">{e(s['title'])}</a></h3>
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
    status_file = ROOT / 'data/status.json'
    status = json.loads(status_file.read_text()) if status_file.exists() else {}
    now = datetime.now(timezone.utc)
    active = sorted([s for s in records if not s.get('withdrawn') and now - timedelta(hours=24) <= date(s['published_at']) <= now], key=lambda s: s['published_at'], reverse=True)
    sections = []
    for tier, title, description in [('lead', 'The lead', 'Important developments, with claims checked by a human editor.'), ('brief', 'The daily brief', 'A broad selection. Headlines belong to the publishers named below.'), ('second', 'Worth a second look', 'Science, ideas, culture, and the world beyond the main news cycle.')]:
        selected = [s for s in active if s['tier'] == tier]
        if tier == 'second':
            selected = selected[:5]
        if tier == 'lead':
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
        index = [dict(id=s['id'], title=s['title'], category=s['category'], published_at=s['published_at'], publishers=sorted({x['publisher'] for x in s['sources']})) for s in stories if not s.get('withdrawn')]
        (out / 'archive' / (month + '.json')).write_text(json.dumps(index, ensure_ascii=False))
        manifest.append(month)
    (out / 'archive' / 'manifest.json').write_text(json.dumps(manifest))
    archive_body = '''<div class="archive-intro"><div class="kicker">THE PERMANENT RECORD</div><h1>Search the archive</h1><p>Search every headline, category, and publisher we have selected. New archive months are added automatically; older months are never deliberately pruned.</p></div>
<form id="search-form" role="search"><label for="search">Search the entire archive</label><div class="search-row"><input id="search" type="search" placeholder="A topic, place, or publisher…"><button type="submit">Search ↗</button></div></form>
<p id="search-status" role="status" aria-live="polite"></p><div id="search-results"></div><button id="load-more" hidden>Show more results</button><h2>Browse by month</h2><ul class="months">''' + ''.join(links) + '</ul><noscript><p>JavaScript is required for full archive search. You can browse the months above without it.</p></noscript>'
    (out / 'archive.html').write_text(shell('The archive', archive_body))
    about = '''<div class="prose"><div class="kicker">OUR STANDARDS</div><h1>Editorial standards</h1>
<p>The Wapiti Bugle is an independent news selection. We aim for 35–50 new stories each day, with hourly collection across world affairs, U.S. news, business, science, technology, health, culture, sports, and outdoors.</p>
<h2>Three ways to read</h2><p><strong>The lead</strong> is reserved for stories with explicit human review and cited claim checks. <strong>The daily brief</strong> carries attributed publisher headlines. <strong>Worth a second look</strong> highlights up to five science, culture, technology, and outdoors stories within the same 24-hour window.</p>
<h2>What has actually been verified?</h2><p>Automated collection validates source URLs, timestamps, and the feed format, filters obvious opinion and live coverage, and groups very similar headlines. These are technical checks, not a claim of factual truth. Even two publishers can repeat the same mistake or wire report. We never label a story verified because several outlets carry it.</p>
<p>Human reviewed means an editor recorded claim-level evidence and a review date. Other headlines are labeled source-reported and not independently verified. Full articles, medical conclusions, accusations, and political claims require reading the original evidence. We do not generate unsourced summaries or context.</p>
<h2>A broad view</h2><p>Selection rotates between interests and publishers rather than optimizing for political agreement or clicks. The initial feed list is limited and UK-heavy; it is a starting source pool, not a claim of comprehensive geographic or ideological balance. We prefer an underfilled edition to invented certainty.</p>
<h2>A record that stays</h2><p>Homepage eligibility expires 24 hours after the source publication time, even when collection is delayed. Archive pages and permanent links remain. Corrections are recorded visibly; withdrawn stories keep a tombstone. Repository history preserves previous editions. GitHub hosting and repository size limits still apply as the archive grows.</p>
<h2>Updates & budget</h2><p>Collection is scheduled hourly. GitHub can delay or disable scheduled jobs; the last successful collection time is always visible. This edition uses no paid AI calls: AI spending is $0. Paid AI is disabled in code and cannot be enabled by adding a key alone. Any future integration must enforce the $10 monthly ceiling before requests and preserve a durable spending ledger.</p>
<h2>Corrections</h2><p>Found an error? <a href="mailto:wapitibugle@gmail.com">Contact the editor</a> with the story link and the supporting evidence. Publisher headlines and reporting remain the property of their respective publishers.</p></div>'''
    (out / 'about.html').write_text(shell('Our standards', about))
    (out / '404.html').write_text(shell('Page not found', '<h1>This page could not be found.</h1><p><a href="/archive.html">Search the archive</a></p>', '/'))
    print(f'Built {len(records)} permanent records; {len(active)} eligible on homepage.')


if __name__ == '__main__':
    build()
