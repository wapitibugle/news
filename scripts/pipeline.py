"""Collect publisher RSS metadata. Never infer verification from source count."""
import argparse
import hashlib
import html
import json
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
STOP = set('a an the and or of to in on for with as at by from is are was were has have after over into amid says said new live updates news latest'.split())


def iso(dt):
    return dt.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')


def date(value):
    try:
        dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        dt = parsedate_to_datetime(value)
    if dt.tzinfo is None:
        raise ValueError('Missing timezone')
    return dt.astimezone(timezone.utc)


def text(value):
    return re.sub(r'\s+', ' ', html.unescape(re.sub('<[^>]*>', '', value or ''))).strip()


def safe_url(value, hosts=None):
    try:
        p = urllib.parse.urlsplit(value)
        if p.scheme != 'https' or not p.hostname or p.username or p.password:
            return None
        host = p.hostname.lower()
        if hosts and not any(host == h or host.endswith('.' + h) for h in hosts):
            return None
        query = urllib.parse.parse_qsl(p.query)
        query = [(k, v) for k, v in query if not k.startswith('utm_') and k not in ('CMP', 'at_campaign', 'at_medium')]
        return urllib.parse.urlunsplit((p.scheme, p.netloc, p.path, urllib.parse.urlencode(query), ''))
    except ValueError:
        return None


def fingerprint(title):
    return set(re.findall(r'[a-z0-9]+', title.lower())) - STOP


def same_event(a, b):
    """Conservative grouping hint, NEVER a factual verification signal."""
    x, y = fingerprint(a), fingerprint(b)
    if min(len(x), len(y)) < 4:
        return a.lower() == b.lower()
    # Require matching numbers to avoid confusing distinct developments.
    if set(re.findall(r'\d+', a)) != set(re.findall(r'\d+', b)):
        return False
    return len(x & y) >= 5 and len(x & y) / len(x | y) >= .72


def parse_feed(raw, feed, now):
    if len(raw) > 2_000_000 or b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():
        raise ValueError('Unsafe or oversized XML')
    root = ET.fromstring(raw)
    records = []
    for item in root.findall('.//item')[:100]:
        title = text(item.findtext('title'))[:240]
        url = safe_url(item.findtext('link', ''), feed['hosts'])
        try:
            published = date(item.findtext('pubDate', ''))
        except (ValueError, TypeError, OverflowError):
            continue
        if not title or not url or published > now + timedelta(minutes=5) or published < now - timedelta(hours=48):
            continue
        # Opinion and live streams cannot be automatically presented as factual briefs.
        if re.search(r'\b(opinion|editorial|live updates|live blog|podcast)\b', title, re.I) or '/commentisfree/' in url or '/live/' in url:
            continue
        records.append(dict(title=title, url=url, publisher=feed['publisher'], category=feed['category'],
                            published_at=iso(published), primary=feed.get('primary', False), excerpt=text(item.findtext('description', ''))[:600]))
    return records


def fetch_feed(feed, now):
    try:
        req = urllib.request.Request(feed['url'], headers={'User-Agent': 'WapitiBugle/1.0 (+https://wapitibugle.com)'})
        with urllib.request.urlopen(req, timeout=20) as response:
            raw = response.read(2_000_001)
        return parse_feed(raw, feed, now), {'feed': feed['name'], 'ok': True}
    except Exception as exc:
        return [], {'feed': feed['name'], 'ok': False, 'error': type(exc).__name__}


def reviewed(record, review):
    # Verification is an explicit human assertion with checkable, cited claims.
    if review.get('status') != 'verified' or not review.get('reviewed_at') or not review.get('claims'):
        return False
    try:
        date(review['reviewed_at'])
    except (ValueError, TypeError):
        return False
    urls = {s['url'] for s in record['sources']}
    return all(c.get('text') and c.get('urls') and all(u in urls for u in c['urls']) for c in review['claims'])


def editorial_priority(story, config):
    """Transparent headline rules for a U.S. audience; not factual verification."""
    rules = config.get('editorial')
    if not rules:
        return 1  # Legacy/test configurations retain their existing behavior.
    title = story['title'].lower()
    category = story['category']
    matches = lambda key: bool(re.search(rules[key], title, re.I))
    if category == 'Sports' or matches('sports') or (rules.get('entertainment') and matches('entertainment')):
        return 0
    ai = story.get('ai_editor', {})
    if ai.get('state') == 'assessed' and ai.get('title') == story['title'] and type(ai.get('priority')) is int and 0 <= ai['priority'] <= 5:
        return ai['priority']
    us = matches('us_relevance')
    election = matches('us_elections')
    global_impact = matches('global_impact')
    if matches('celebrity') and not (election or matches('public_policy')):
        return 0
    if matches('foreign_local') and not (us or global_impact):
        return 0
    if category == 'Culture' and not (us and matches('public_policy')):
        return 0
    if election and (us or category in ('U.S.', 'Elections')):
        return 5
    if rules.get('accountability') and matches('accountability') and (us or category in ('U.S.', 'Elections')):
        return 4
    if rules.get('human_impact_science') and matches('human_impact_science') and category in ('Science', 'Health', 'Technology'):
        return 4
    if rules.get('routine_feature') and matches('routine_feature'):
        return 1
    if category == 'World':
        return 3 if global_impact else (2 if us else 0)
    if category == 'Business':
        return 3 if us or global_impact else 0
    if category == 'Elections':
        return 4
    if category == 'U.S.':
        return 3
    return 2


def scientific_review_required(story, config):
    rules = config.get('editorial', {})
    title = story['title']
    match = lambda key: bool(rules.get(key) and re.search(rules[key], title, re.I))
    return match('disputed_medical_claim') or (match('medical_public_figure') and match('medical_subject'))


def scientific_publication_allowed(story, config, review=None):
    if not scientific_review_required(story, config):
        return True
    if review is not None:
        return reviewed(story, review) and review.get('scientific_assessment') == 'evidence-based-critique' and bool(review.get('context'))
    return story.get('verification') == 'human-verified' and story.get('scientific_assessment') == 'evidence-based-critique' and bool(story.get('context'))


def collect(existing, candidates, reviews, config, now):
    """Append-only story identities; re-runs never reset first publication time."""
    zone = ZoneInfo(config['timezone'])
    today = now.astimezone(zone).date()
    records = {s['id']: s for s in existing}
    for story in records.values():
        if story['category'] == 'Elections' and not re.search(config.get('editorial', {}).get('us_elections', r'(?!)'), story['title'], re.I):
            story['category'] = 'U.S.'
        story['editorial_excluded'] = editorial_priority(story, config) == 0 or not scientific_publication_allowed(story, config, reviews.get(story['id'], {}))
    known_urls = {source['url']: s for s in records.values() for source in s['sources']}
    pending = []
    for candidate in sorted(candidates, key=lambda c: c['published_at'], reverse=True):
        sid = hashlib.sha256(candidate['url'].encode()).hexdigest()[:20]
        if not scientific_publication_allowed(dict(candidate, sources=[candidate]), config, reviews.get(sid, {})):
            continue
        priority = editorial_priority(candidate, config)
        if not priority:
            continue
        if priority == 5 and re.search(config.get('editorial', {}).get('us_elections', r'(?!)'), candidate['title'], re.I):
            candidate = dict(candidate, category='Elections')
        if candidate['url'] in known_urls:
            known = known_urls[candidate['url']]
            if candidate.get('ai_editor', {}).get('title') == known['title']:
                known['ai_editor'] = candidate['ai_editor']
            continue
        match = next((s for s in list(records.values()) + pending
                      if abs((date(s['published_at']) - date(candidate['published_at'])).total_seconds()) < 36 * 3600
                      and (same_event(s['title'], candidate['title']) or (candidate.get('ai_editor', {}).get('group') and s.get('ai_editor', {}).get('group') == candidate['ai_editor']['group']))), None)
        if match:
            match['sources'].append(candidate)
            known_urls[candidate['url']] = match
            match['updated_at'] = iso(now)
            continue
        if date(candidate['published_at']) < now - timedelta(hours=24):
            continue
        sid = hashlib.sha256(candidate['url'].encode()).hexdigest()[:20]
        record = dict(id=sid, title=candidate['title'], category=candidate['category'],
                      published_at=candidate['published_at'], first_seen_at=iso(now), updated_at=iso(now),
                      sources=[candidate], tier='brief', verification='source-reported', claims=[], ai_editor=candidate.get('ai_editor', {}))
        pending.append(record)
        known_urls[candidate['url']] = record
    for story in records.values():
        story['editorial_excluded'] = editorial_priority(story, config) == 0 or not scientific_publication_allowed(story, config, reviews.get(story['id'], {}))
    day_records = [s for s in records.values() if date(s['first_seen_at']).astimezone(zone).date() == today]
    # 40 stories spread through the day; a small initial edition, hard cap 50.
    hour = now.astimezone(zone).hour
    quota = min(config['daily_max'], max(config.get('edition_minimum', 5), round(config['daily_target'] * (hour + 1) / 24)))
    eligible_today = [s for s in day_records if not s.get('editorial_excluded')]
    categories = Counter(s['category'] for s in eligible_today)
    publishers = Counter(s['sources'][0]['publisher'] for s in day_records)
    while pending and len(eligible_today) < quota and len(day_records) < config['daily_max']:
        pending.sort(key=lambda s: (-(s['category'] == 'Elections' and categories['Elections'] < max(3, quota // 4)), -min(editorial_priority(s, config), 4), categories[s['category']], publishers[s['sources'][0]['publisher']], -date(s['published_at']).timestamp()))
        s = pending.pop(0)
        records[s['id']] = s
        day_records.append(s)
        eligible_today.append(s)
        categories[s['category']] += 1
        publishers[s['sources'][0]['publisher']] += 1
    for s in records.values():
        r = reviews.get(s['id'], {})
        s['verification'] = 'human-verified' if reviewed(s, r) else 'source-reported'
        s['claims'] = r.get('claims', []) if s['verification'] == 'human-verified' else []
        s['withdrawn'] = r.get('status') == 'withdrawn'
        s['correction'] = text(r.get('correction', ''))
        s['tier'] = r.get('tier', 'brief') if r.get('tier') in ('lead', 'brief', 'second') else 'brief'
        if s['tier'] == 'lead' and s['verification'] != 'human-verified':
            s['tier'] = 'brief'
        if s.get('ai_editor', {}).get('state') == 'assessed' and s['verification'] != 'human-verified' and r.get('status') != 'withdrawn':
            s['tier'] = s['ai_editor'].get('section', 'brief')
        # Context cannot be invented: it is added by a reviewer with citations.
        s['context'] = text(r.get('context', '')) if s['verification'] == 'human-verified' else ''
        s['scientific_assessment'] = r.get('scientific_assessment', '') if s['verification'] == 'human-verified' else ''
    # A separate 3–5 story discovery selection, within the same 24-hour window.
    eligible = [s for s in records.values() if not s['withdrawn'] and not s.get('editorial_excluded') and now - timedelta(hours=24) <= date(s['published_at']) <= now]
    second = sorted([s for s in eligible if s['tier'] == 'second'], key=lambda s: s['published_at'], reverse=True)[:5]
    for s in sorted(eligible, key=lambda s: (-editorial_priority(s, config), -date(s['published_at']).timestamp())):
        if len(second) >= 5:
            break
        if s['tier'] == 'brief' and s['category'] in ('Science', 'Health', 'Outdoors', 'Technology'):
            s['tier'] = 'second'
            second.append(s)
    second_ids = {s['id'] for s in second}
    for story in eligible:
        if story['tier'] == 'second' and story['id'] not in second_ids:
            story['tier'] = 'brief'
    return sorted(records.values(), key=lambda s: s['first_seen_at'])


def load_archive(path):
    records = []
    for p in sorted(path.glob('*.json')):
        records.extend(json.loads(p.read_text()))
    return records


def save_archive(path, records):
    path.mkdir(parents=True, exist_ok=True)
    months = {}
    for s in records:
        months.setdefault(s['first_seen_at'][:7], []).append(s)
    for month, stories in months.items():
        dest = path / (month + '.json')
        payload = json.dumps(stories, ensure_ascii=False, indent=2) + '\n'
        if not dest.exists() or dest.read_text() != payload:
            temp = dest.with_suffix('.tmp')
            temp.write_text(payload)
            temp.replace(dest)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--offline', action='store_true')
    args = parser.parse_args()
    config = json.loads((ROOT / 'config.json').read_text())
    from ai_editor import edit_candidates
    now = datetime.now(timezone.utc)
    archive = ROOT / 'data/archive'
    results = [] if args.offline else list(ThreadPoolExecutor(max_workers=6).map(lambda f: fetch_feed(f, now), config['feeds']))
    candidates = [s for records, _ in results for s in records]
    health = [status for _, status in results]
    if results and not candidates:
        sys.exit('No current feed stories collected; keeping the last successful archive and deployment.')
    existing = load_archive(archive)
    candidates, ai_status = edit_candidates(ROOT, candidates, existing, config, now, editorial_priority, scientific_review_required) if not args.offline else (candidates, {'state': 'offline'})
    records = collect(existing, candidates, json.loads((ROOT / 'data/reviews.json').read_text()), config, now)
    save_archive(archive, records)
    if ai_status.get('state') not in ('ready', 'disabled', 'missing_key', 'budget_pause', 'offline', 'local_paid_calls_disabled'):
        print('::warning::AI editor paused (' + ai_status.get('state', 'unknown') + '). Free feed publication continues; inspect the budget ledger before retrying.')
    status = {'collected_at': iso(now) if not args.offline else None, 'feeds': health,
              'ai_accounted_usd': ai_status.get('accounted_usd', 0), 'ai_enabled': config['ai']['enabled'], 'ai': ai_status, 'stories': len(records)}
    (ROOT / 'data/status.json').write_text(json.dumps(status, indent=2) + '\n')
    print(f'Archive: {len(records)} stories; feeds: {sum(h["ok"] for h in health)}/{len(health)}; AI: {ai_status['state']}')


if __name__ == '__main__':
    main()
