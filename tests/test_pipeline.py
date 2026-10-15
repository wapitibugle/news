import copy
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import pipeline as p
import build as b

NOW = datetime(2026, 10, 15, 20, tzinfo=timezone.utc)
CONFIG = {'timezone': 'America/Chicago', 'daily_target': 40, 'daily_max': 50}


def candidate(n=1, **kw):
    return dict(title=f'City number {n} approves housing development plan', url=f'https://example.com/{n}', publisher='Example', category='World', published_at=p.iso(NOW - timedelta(hours=1)), primary=False, **kw)


class Safeguards(unittest.TestCase):
    def collect(self, old, items, reviews=None, now=NOW):
        return p.collect(copy.deepcopy(old), copy.deepcopy(items), reviews or {}, CONFIG, now)

    def test_american_editorial_scope(self):
        config = json.loads((Path(__file__).resolve().parents[1] / 'config.json').read_text())
        excluded = [
            ('Russell Brand accuser describes trial testimony', 'Culture'),
            ('Healey says surprise UK growth is sign of resilience', 'Business'),
            ('Children killed after school roof collapses in Pakistan', 'World'),
            ('City council in England approves new parking rules', 'World'),
            ('Champions League results', 'Sports'),
        ]
        for title, category in excluded:
            self.assertEqual(p.editorial_priority(dict(title=title, category=category), config), 0, title)
        for title, category in [
            ('US midterm polling shows close Senate races', 'U.S.'),
            ('Ukraine war threatens energy supply', 'World'),
            ('Federal Reserve holds interest rates steady', 'Business'),
            ('Actor testifies before Congress on federal AI legislation', 'Culture'),
        ]:
            self.assertGreater(p.editorial_priority(dict(title=title, category=category), config), 0, title)

    def test_elections_have_selection_priority(self):
        config = json.loads((Path(__file__).resolve().parents[1] / 'config.json').read_text())
        config.update(CONFIG)
        items = [candidate(n) for n in range(50)]
        for item in items:
            item['category'] = 'Science'
        election = candidate(99)
        election.update(title='US Senate election polling shows a close midterm race', category='U.S.')
        records = p.collect([], items + [election], {}, config, NOW)
        self.assertEqual(records[0]['category'], 'Elections')

    def test_no_duplicate_on_repeat(self):
        first = self.collect([], [candidate()])
        again = self.collect(first, [candidate()])
        self.assertEqual(len(again), 1)
        self.assertEqual(first[0]['first_seen_at'], again[0]['first_seen_at'])

    def test_old_story_does_not_reenter(self):
        item = candidate()
        item['published_at'] = p.iso(NOW - timedelta(hours=25))
        self.assertEqual(self.collect([], [item]), [])

    def test_daily_cap_survives_reruns(self):
        config = dict(CONFIG, daily_target=100, daily_max=50)
        records = p.collect([], [candidate(n) for n in range(100)], {}, config, NOW)
        self.assertEqual(len(records), 50)
        again = p.collect(records, [candidate(n) for n in range(100, 200)], {}, config, NOW)
        self.assertEqual(len(again), 50)

    def test_interest_rotation(self):
        items = [candidate(n) for n in range(30)]
        science = candidate(70)
        science['category'] = 'Science'
        result = self.collect([], items + [science])
        self.assertIn('Science', {s['category'] for s in result})

    def test_source_count_never_verifies(self):
        first, second = candidate(), candidate()
        second['url'] = 'https://other.example/story'
        second['publisher'] = 'Second'
        records = self.collect([], [first, second])
        self.assertEqual(len(records), 1)
        self.assertEqual(len(records[0]['sources']), 2)
        self.assertEqual(records[0]['verification'], 'source-reported')
        self.assertEqual(records[0]['tier'], 'brief')

    def test_review_needs_evidence(self):
        records = self.collect([], [candidate()])
        sid = records[0]['id']
        review = {sid: {'status': 'verified', 'reviewed_at': p.iso(NOW), 'tier': 'lead', 'claims': [{'text': 'Claim', 'urls': ['https://madeup.example/']}]}}
        self.assertEqual(self.collect(records, [], review)[0]['verification'], 'source-reported')
        review[sid]['claims'][0]['urls'] = [candidate()['url']]
        record = self.collect(records, [], review)[0]
        self.assertEqual(record['verification'], 'human-verified')
        self.assertEqual(record['tier'], 'lead')

    def test_withdrawal_retains_identity(self):
        records = self.collect([], [candidate()])
        sid = records[0]['id']
        record = self.collect(records, [], {sid: {'status': 'withdrawn', 'correction': 'Incorrect account'}})[0]
        self.assertTrue(record['withdrawn'])
        self.assertEqual(record['id'], sid)

    def test_no_archive_pruning(self):
        records = self.collect([], [candidate()])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            p.save_archive(path, records)
            old = self.collect(p.load_archive(path), [], now=NOW + timedelta(days=400))
            p.save_archive(path, old)
            self.assertEqual(len(p.load_archive(path)), 1)

    def test_month_rollover(self):
        a = self.collect([], [candidate()])[0]
        old = copy.deepcopy(a)
        old['id'] = 'old'
        old['first_seen_at'] = '2026-09-01T00:00:00Z'
        with tempfile.TemporaryDirectory() as tmp:
            p.save_archive(Path(tmp), [old, a])
            self.assertEqual(len(list(Path(tmp).glob('*.json'))), 2)

    def test_urls(self):
        for url in ['javascript:alert(1)', 'http://example.com', 'https://example.com.evil.test/a', 'https://user:pass@example.com']:
            self.assertIsNone(p.safe_url(url, ['example.com']))
        self.assertEqual(p.safe_url('https://example.com/story?utm_source=rss#a', ['example.com']), 'https://example.com/story')

    def test_date_and_xml_gate(self):
        feed = {'publisher': 'Example', 'category': 'World', 'hosts': ['example.com']}
        xml = f'<rss><channel><item><title>Test item</title><link>https://example.com/a</link><pubDate>{p.iso(NOW)}</pubDate></item></channel></rss>'.encode()
        self.assertEqual(len(p.parse_feed(xml, feed, NOW)), 1)
        self.assertEqual(p.parse_feed(xml, feed, NOW - timedelta(days=2)), [])
        with self.assertRaises(ValueError):
            p.parse_feed(b'<!DOCTYPE x><rss/>', feed, NOW)

    def test_dist_only_contains_public_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'site').mkdir()
            for name in ('style.css', 'app.js', 'elk.png'):
                (root / 'site' / name).write_text('')
            (root / 'data/archive').mkdir(parents=True)
            (root / '.env').write_text('SECRET=must-not-be-published')
            old = b.ROOT
            try:
                b.ROOT = root
                b.build()
                self.assertFalse((root / 'dist/.env').exists())
                self.assertTrue((root / 'dist/index.html').exists())
            finally:
                b.ROOT = old

    def test_escape_feed_markup(self):
        story = self.collect([], [candidate()])[0]
        story['title'] = '<script>alert(1)</script>'
        markup = b.card(story)
        self.assertNotIn('<script>', markup)
        self.assertIn('&lt;script&gt;', markup)

    def test_similar_events_with_different_numbers_stay_separate(self):
        self.assertFalse(p.same_event('City approves 10 million dollar housing project', 'City approves 20 million dollar housing project'))


if __name__ == '__main__':
    unittest.main()
