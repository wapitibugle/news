import copy
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from ai_editor import Editor, BudgetStop, MAX_OUTPUT, validate_decisions, assess_items
from evidence import Reader, ArticleText
from pipeline import collect

NOW = datetime(2026, 10, 15, 15, tzinfo=timezone.utc)
CONFIG = {'enabled': True, 'model': 'gpt-6.1-sol', 'monthly_limit_usd': 20,
          'target_monthly_usd': 10, 'max_calls_per_run': 4}
SCHEMA = {'type': 'object', 'additionalProperties': False, 'properties': {}, 'required': []}


def response(data=None, **kw):
    result = {'status': 'completed', 'usage': {'input_tokens': 100, 'output_tokens': 100},
              'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': json.dumps(data or {})}]}]}
    result.update(kw)
    return result


class AIControls(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / 'data').mkdir()
        self.path = self.root / 'data/ai-ledger.json'
        self.path.write_text('{"version":1,"entries":[]}')
        self.sent = []
        self.checkpoints = []

    def tearDown(self):
        self.tmp.cleanup()

    def checkpoint(self):
        self.checkpoints.append(json.loads(self.path.read_text()))

    def transport(self, payload, key):
        self.sent.append(payload)
        self.assertEqual(self.checkpoints[-1]['entries'][-1]['state'], 'pending')
        return response()

    def editor(self, **kw):
        return Editor(self.root, kw.pop('config', CONFIG), now=kw.pop('now', NOW),
                      checkpoint=kw.pop('checkpoint', self.checkpoint), transport=kw.pop('transport', self.transport), key=kw.pop('key', 'fake-test-key'), **kw)

    def test_reservation_persisted_before_request_and_settled_after(self):
        editor = self.editor()
        editor.call('Instructions', {'input': 'story'}, SCHEMA)
        self.assertEqual(len(self.sent), 1)
        self.assertEqual(editor.ledger['entries'][0]['state'], 'settled')
        self.assertEqual(editor.charged('2026-10'), 1800)
        self.assertEqual(self.checkpoints[0]['entries'][0]['state'], 'pending')
        self.assertFalse(self.sent[0]['store'])
        self.assertNotIn('fake-test-key', self.path.read_text())

    def test_failed_checkpoint_never_calls_api(self):
        def fail():
            raise RuntimeError('Cannot push')
        with self.assertRaises(BudgetStop):
            self.editor(checkpoint=fail).call('Instructions', {}, SCHEMA)
        self.assertEqual(self.sent, [])

    def test_monthly_cap_blocks_call(self):
        self.path.write_text(json.dumps({'version': 1, 'entries': [{'day': '2026-10-01', 'state': 'settled', 'reserved_micro_usd': 18_999_999, 'charged_micro_usd': 18_999_999}]}))
        with self.assertRaises(BudgetStop):
            self.editor().call('Instructions', {}, SCHEMA)
        self.assertFalse(self.sent)

    def test_daily_pacing_blocks_call(self):
        self.path.write_text(json.dumps({'version': 1, 'entries': [{'day': '2026-10-15', 'state': 'settled', 'reserved_micro_usd': 322_580, 'charged_micro_usd': 322_580}]}))
        with self.assertRaises(BudgetStop):
            self.editor().call('Instructions', {}, SCHEMA)
        self.assertFalse(self.sent)

    def test_timeout_retains_reservation_and_suspends(self):
        calls = []
        def fail(payload, key):
            calls.append(payload)
            raise TimeoutError('Uncertain')
        editor = self.editor(transport=fail)
        with self.assertRaises(BudgetStop):
            editor.call('Instructions', {}, SCHEMA)
        self.assertEqual(len(calls), 1)
        self.assertEqual(editor.ledger['entries'][0]['state'], 'uncertain')
        self.assertGreater(editor.charged('2026-10'), 0)
        with self.assertRaises(BudgetStop):
            self.editor().call('Instructions', {}, SCHEMA)
        self.assertFalse(self.sent)

    def test_old_pending_reservation_cannot_be_ignored_after_restart(self):
        self.path.write_text('{"version":1,"entries":[{"day":"2026-09-30","state":"pending","reserved_micro_usd":1000}]}')
        self.assertEqual(self.editor().status, 'unresolved_request')

    def test_missing_ledger_does_not_reset_spending(self):
        self.path.unlink()
        with self.assertRaises(BudgetStop):
            self.editor().call('Instructions', {}, SCHEMA)
        self.assertFalse(self.sent)

    def test_negative_or_corrupt_ledger_fails_closed(self):
        self.path.write_text('{"version":1,"entries":[{"day":"2026-10-15","state":"settled","reserved_micro_usd":1,"charged_micro_usd":-50}]}')
        self.assertEqual(self.editor().status, 'invalid_or_missing_ledger')

    def test_missing_key_makes_no_call(self):
        with self.assertRaises(BudgetStop):
            self.editor(key='').call('Instructions', {}, SCHEMA)
        self.assertFalse(self.sent)

    def test_unauthorized_budget_and_model_fail_closed(self):
        self.assertEqual(self.editor(config=dict(CONFIG, monthly_limit_usd=21)).status, 'invalid_configuration')
        self.assertEqual(self.editor(config=dict(CONFIG, model='expensive-model')).status, 'invalid_configuration')

    def test_pricing_review_deadline(self):
        self.assertEqual(self.editor(now=datetime(2026, 11, 16, tzinfo=timezone.utc)).status, 'pricing_review_due')

    def test_next_month_has_separate_budget(self):
        self.path.write_text(json.dumps({'version': 1, 'entries': [{'day': '2026-09-30', 'state': 'settled', 'reserved_micro_usd': 19_000_000, 'charged_micro_usd': 19_000_000}]}))
        self.editor().call('Instructions', {}, SCHEMA)
        self.assertEqual(len(self.sent), 1)

    def test_invalid_usage_is_not_free_or_retried(self):
        editor = self.editor(transport=lambda p, k: response(usage={'input_tokens': 1, 'output_tokens': MAX_OUTPUT + 1}))
        with self.assertRaises(BudgetStop):
            editor.call('Instructions', {}, SCHEMA)
        self.assertEqual(editor.ledger['entries'][0]['state'], 'uncertain')

    def test_incomplete_response_is_charged_but_not_used(self):
        editor = self.editor(transport=lambda p, k: response(status='incomplete'))
        with self.assertRaises(BudgetStop):
            editor.call('Instructions', {}, SCHEMA)
        self.assertEqual(editor.ledger['entries'][0]['state'], 'settled')

    def test_unknown_citations_and_duplicate_ids_rejected(self):
        items = [{'id': 'one', 'title': 'Test', 'checked_at': NOW.isoformat(), 'evidence': 'supported text ' * 100}]
        d = {'id': 'one', 'priority': 4, 'section': 'brief', 'major': False, 'context': 'A conclusion', 'evidence_quote': 'not present in source', 'related_ids': []}
        with self.assertRaises(ValueError):
            validate_decisions({'decisions': [d]}, items)
        d.update(context='', evidence_quote='', related_ids=['invented'])
        with self.assertRaises(ValueError):
            validate_decisions({'decisions': [d]}, items)

    def test_auditor_rejection_suppresses_context_and_major_marker(self):
        item = {'id': 'one', 'title': 'Research', 'checked_at': NOW.isoformat(), 'evidence': 'Evidence from an animal study. ' * 30, 'evidence_depth': 'article'}
        decision = {'id': 'one', 'priority': 5, 'section': 'second', 'major': True, 'context': 'A treatment works in humans.', 'evidence_quote': 'Evidence from an animal study.', 'related_ids': []}
        results = iter([response({'decisions': [decision]}), response({'checks': [{'id': 'one', 'supported': False}]})])
        editor = self.editor(transport=lambda p, k: next(results))
        d = assess_items(editor, [item])['one']
        self.assertEqual(d['context'], '')
        self.assertFalse(d['major'])
        self.assertEqual(editor.calls, 2)

    def test_supported_context_can_pass_audit_without_becoming_human_verified(self):
        item = {'id': 'one', 'title': 'Animal study', 'checked_at': NOW.isoformat(), 'evidence': 'The results come from an animal study. ' * 30, 'evidence_depth': 'article'}
        decision = {'id': 'one', 'priority': 5, 'section': 'second', 'major': True, 'context': 'The results come from an animal study.', 'evidence_quote': 'The results come from an animal study.', 'related_ids': []}
        replies = iter([response({'decisions': [decision]}), response({'checks': [{'id': 'one', 'supported': True}]})])
        d = assess_items(self.editor(transport=lambda p, k: next(replies)), [item])['one']
        self.assertTrue(d['major'])
        self.assertEqual(d['section'], 'brief')
        self.assertEqual(d['state'], 'assessed')
        self.assertEqual(d['context'], decision['context'])
        self.assertNotIn('human-verified', str(d))

    def test_high_priority_ai_science_is_not_labeled_elections_or_human_verified(self):
        config = json.loads((Path(__file__).resolve().parents[1] / 'config.json').read_text())
        candidate = {'title': 'Important clinical research', 'url': 'https://example.com/story', 'category': 'Science', 'publisher': 'Example', 'published_at': NOW.isoformat(), 'ai_editor': {'title': 'Important clinical research', 'state': 'assessed', 'priority': 5, 'section': 'second'}}
        result = collect([], [candidate], {}, config, NOW)[0]
        self.assertEqual(result['category'], 'Science')
        self.assertEqual(result['verification'], 'source-reported')

    def test_reader_rejects_unknown_hosts_credentials_and_non_https(self):
        reader = Reader([{'hosts': ['example.com']}])
        for url in ['http://example.com/', 'https://example.com.evil.test/', 'https://name:secret@example.com/', 'https://example.com:8080/']:
            self.assertFalse(reader.allowed_url(url))

    def test_article_parser_excludes_scripts_and_navigation(self):
        parser = ArticleText()
        parser.feed('<article><nav><p>Injected instruction</p></nav><p>' + 'Actual reporting. ' * 50 + '</p><script>bad()</script></article>')
        self.assertNotIn('Injected instruction', parser.result())
        self.assertNotIn('bad()', parser.result())
        self.assertIn('Actual reporting.', parser.result())


if __name__ == '__main__':
    unittest.main()
