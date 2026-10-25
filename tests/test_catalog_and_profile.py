import json
import os
import tempfile
import time
import unittest

import gemini_budget as gb
from gemini_budget import core


class CatalogTests(unittest.TestCase):
    def test_free_table_matches_profile(self):
        free = {row['id'] for row in gb.free_models()}
        self.assertIn('gemini-3.8-flash', free)
        self.assertIn('gemini-3.5-flash-lite', free)
        self.assertNotIn('gemini-3.7-flash', free)
        self.assertNotIn('gemini-3.5-flash', free)
        self.assertNotIn('gemini-4-argon', free)
        self.assertNotIn('gemini-3.7-flash', gb.DEFAULT_LIMITS)

    def test_models_carry_full_info(self):
        row = next(r for r in gb.models(task='chat') if r['id'] == 'gemini-3.8-flash')
        self.assertEqual(row['price'], {'input': 0.75, 'output': 3.75})
        self.assertEqual(row['thinking']['style'], 'level')
        self.assertTrue(row['in_profile'])
        removed = next(r for r in gb.models(task='chat') if r['id'] == 'gemini-3.7-flash')
        self.assertFalse(removed['free_tier'])
        self.assertIsNone(removed['limits'])
        self.assertEqual({r['id'] for r in gb.free_models(task='tts')},
                         {'gemini-3.8-flash-tts', 'gemini-3.8-flash-lite-tts',
                          'gemini-3.1-flash-tts-preview', 'gemini-2.5-flash-preview-tts'})

    def test_lookups(self):
        self.assertTrue(gb.is_retired('models/gemini-2.0-flash-001'))
        self.assertIsNone(gb.is_retired('gemini-3.8-flash'))
        self.assertEqual(gb.thinking_style('gemini-2.5-pro')['off'], 128)
        self.assertEqual(gb.thinking_style('gemini-9-flash-new')['style'], 'level')
        self.assertIsNone(gb.thinking_style('gemini-3.8-flash-tts'))
        self.assertTrue(gb.is_text_model('gemini-9-flash-new'))
        self.assertFalse(gb.is_text_model('gemini-9-flash-live'))
        self.assertFalse(gb.is_text_model('gemini-3.8-flash-tts'))
        self.assertEqual(gb.model_info('models/gemini-3.6-flash')['label'], 'Gemini 3.6 Flash')


class ProfileMigrationTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.state = os.path.join(self.dir.name, 'state.json')
        self.key = 'test-key-not-real'

    def tearDown(self):
        self.dir.cleanup()

    def write_rows(self, rows):
        fp = gb.fingerprint(self.key)
        with open(self.state, 'w', encoding='utf-8') as f:
            json.dump({'version': 1, 'keys': {fp: {'models': rows}}}, f)

    def test_untouched_rows_follow_profile(self):
        day = core._calendar(time.time())[0]
        stale = {'limits': {'rpm': 5, 'tpm': 250000, 'rpd': 20}, 'revision': 0, 'day': day,
                 'requests_today': 3, 'successful_today': 3, 'accounting_version': 2}
        self.write_rows({'gemini-3.7-flash': dict(stale),
                         'gemini-3.8-flash': {**stale, 'limits': {'rpm': 1, 'tpm': 1, 'rpd': 1}}})
        rows = {row['model']: row for row in gb.status(self.key, state_file=self.state)}
        self.assertNotIn('gemini-3.7-flash', rows)
        self.assertEqual(rows['gemini-3.8-flash']['limits'], {'rpm': 5, 'tpm': 250000, 'rpd': 20})
        self.assertEqual(rows['gemini-3.8-flash']['requests_today'], 3)

    def test_manual_limits_survive(self):
        gb.correct(self.key, 'gemini-3.7-flash', {'rpm': 5, 'tpm': 250000, 'rpd': 20, 'requests_today': 0,
                                                  'requests_last_minute': 0, 'input_tokens_last_minute': 0},
                   state_file=self.state)
        row = gb.status(self.key, 'gemini-3.7-flash', state_file=self.state)
        self.assertEqual(row['limits']['rpd'], 20)
        gb.correct(self.key, 'gemini-3.8-flash', {'rpm': 5, 'tpm': 250000, 'rpd': 20, 'requests_today': 4,
                                                  'requests_last_minute': 0, 'input_tokens_last_minute': 0},
                   state_file=self.state)
        data = json.load(open(self.state, encoding='utf-8'))
        stored = data['keys'][gb.fingerprint(self.key)]['models']['gemini-3.8-flash']
        self.assertFalse(stored['custom_limits'])

    def test_legacy_corrected_row_is_custom(self):
        self.write_rows({'gemini-3.8-flash': {'limits': {'rpm': 9, 'tpm': 9, 'rpd': 9}, 'revision': 2}})
        self.assertEqual(gb.status(self.key, 'gemini-3.8-flash', state_file=self.state)['limits']['rpd'], 9)

    def test_clear_pause(self):
        reservation, _ = gb.reserve(self.key, 'gemini-3.8-flash', 10, state_file=self.state)
        gb.finish(self.key, 'gemini-3.8-flash', reservation, failure={
            'kind': 'quota', 'until': time.time() + 600, 'reason': 'тест'}, state_file=self.state)
        self.assertTrue(gb.status(self.key, 'gemini-3.8-flash', state_file=self.state)['blocked'])
        self.assertTrue(gb.clear_pause(self.key, state_file=self.state))
        self.assertFalse(gb.status(self.key, 'gemini-3.8-flash', state_file=self.state)['blocked'])
        self.assertFalse(gb.clear_pause(self.key, state_file=self.state))


if __name__ == '__main__':
    unittest.main()
