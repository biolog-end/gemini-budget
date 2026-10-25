"""Реальное файловое резервирование; все ключи и ответы вымышленные."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import gemini_budget as gb
from gemini_budget import core


def daily_failure(until):
    return {'kind': 'quota', 'until': until, 'reason': 'исчерпана суточная квота (RPD)',
            'report': {'scope': 'day', 'zero_limit': False}}


class SharedUsageTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = str(Path(self.directory.name) / 'usage.json')
        self.key = 'test-quota-key-a'
        self.model = 'gemini-3.8-flash'

    def values(self, **changes):
        result = dict(rpm=5, tpm=250000, rpd=20, requests_today=0, successful_today=0,
                      requests_last_minute=0, input_tokens_last_minute=0)
        result.update(changes)
        return result

    def reserve(self, key=None, model=None, tokens=0):
        return gb.reserve(key or self.key, model or self.model, tokens, state_file=self.path)

    def finish(self, reservation, **kwargs):
        return gb.finish(self.key, self.model, reservation, state_file=self.path, **kwargs)

    def correct(self, **changes):
        return gb.correct(self.key, self.model, self.values(**changes), state_file=self.path)

    def snapshot(self, key=None, model=None):
        return gb.status(key or self.key, model or self.model, state_file=self.path)

    def test_long_reply_enters_minute_counter_on_completion_and_finish_is_idempotent(self):
        with patch.object(core.time, 'time', return_value=1000):
            reservation, _ = self.reserve(tokens=50)
        with patch.object(core.time, 'time', return_value=1100):
            self.finish(reservation, success=True, input_tokens=123)
            self.finish(reservation, success=True, input_tokens=123)
            row = self.snapshot()
        self.assertEqual((row['requests_today'], row['requests_last_minute'], row['input_tokens_last_minute']),
                         (1, 1, 123))

    def test_v1_attempts_migrate_to_known_successes_without_rewriting_source(self):
        legacy = Path(self.directory.name) / 'old_attempts.json'
        now = core.time.time()
        day = core._calendar(now)[0]
        row = {'day': day, 'requests_today': 20, 'successful_today': 3,
               'minute': [{'id': 'unknown-attempt', 'at': now, 'tokens': 200}], 'pending': {}}
        raw = json.dumps({'version': 1, 'keys': {gb.fingerprint(self.key): {'models': {self.model: row}}}})
        legacy.write_text(raw, encoding='utf-8')
        gb.import_legacy(legacy, state_file=self.path)
        current = self.snapshot()
        self.assertEqual((current['requests_today'], current['successful_today'], current['requests_last_minute']),
                         (3, 3, 0))
        self.assertEqual(legacy.read_text(encoding='utf-8'), raw)

    def test_same_key_shares_day_across_ids_and_other_keys_models_are_independent(self):
        self.correct(requests_today=19, successful_today=19)
        reservation, error = self.reserve()
        self.assertIsNone(error)
        self.finish(reservation, success=True, input_tokens=42)
        rows = gb.snapshots([{'id': 'other-instance-id', 'key': self.key}], state_file=self.path)['other-instance-id']
        row = next(row for row in rows if row['model'] == self.model)
        self.assertEqual((row['requests_today'], row['successful_today'], row['remaining_day']), (20, 20, 0))
        self.assertIn('закончились на сегодня', self.reserve()[1])
        self.assertIsNone(self.reserve(key='different-test-key')[1])
        self.assertIsNone(self.reserve(model='gemini-3.6-flash')[1])
        self.assertNotIn(self.key, Path(self.path).read_text(encoding='utf-8'))

    def test_minute_input_usage_correction_and_restart_persistence(self):
        with patch.object(core.time, 'time', return_value=1000):
            for _ in range(5):
                reservation, error = self.reserve(tokens=10)
                self.assertIsNone(error)
                self.finish(reservation, success=True, input_tokens=50)
            row = self.snapshot()
            self.assertEqual((row['remaining_minute'], row['input_tokens_last_minute']), (0, 250))
            self.assertIsNotNone(self.reserve()[1])
        with patch.object(core.time, 'time', return_value=1061):
            row = self.snapshot()
            self.assertEqual((row['remaining_minute'], row['requests_today'], row['successful_today']), (5, 5, 5))
            self.correct(requests_today=4, successful_today=4, requests_last_minute=1,
                         input_tokens_last_minute=249990)
            self.assertIn('TPM', self.reserve(tokens=20)[1])
            self.assertIsNone(self.reserve(tokens=5)[1])

    def test_server_day_quota_and_manual_correction_clear_shared_pause(self):
        reservation, error = self.reserve()
        self.finish(reservation, failure=daily_failure(core.time.time() + 3600))
        self.assertTrue(self.snapshot()['blocked'])
        self.assertEqual(self.snapshot()['remaining_day'], 0)
        self.assertIsNotNone(self.reserve()[1])
        self.correct(requests_today=2, successful_today=1)
        self.assertFalse(self.snapshot()['blocked'])
        self.assertIsNone(self.reserve()[1])

    def test_manual_zero_limit_disables_until_corrected_without_fake_minute_timer(self):
        row = self.correct(rpm=0)
        self.assertTrue(row['blocked'])
        self.assertEqual(row['left_s'], 0)
        self.assertIn('Нулевая квота RPM', self.reserve()[1])
        self.correct()
        self.assertIsNone(self.reserve()[1])

    def test_pacific_midnight_resets_day_but_keeps_minute(self):
        now = datetime(2026, 9, 18, 6, 59, 59, tzinfo=timezone.utc).timestamp()
        with patch.object(core.time, 'time', return_value=now):
            self.correct(requests_today=20, successful_today=20)
            self.assertEqual(self.snapshot()['remaining_day'], 0)
        with patch.object(core.time, 'time', return_value=now + 2):
            row = self.snapshot()
            self.assertEqual((row['requests_today'], row['successful_today'], row['remaining_day']), (0, 0, 20))

    def test_old_daily_error_received_after_midnight_does_not_block_new_day(self):
        now = datetime(2026, 9, 18, 6, 59, 59, tzinfo=timezone.utc).timestamp()
        with patch.object(core.time, 'time', return_value=now):
            reservation, error = self.reserve()
        with patch.object(core.time, 'time', return_value=now + 2):
            self.finish(reservation, failure=daily_failure(now + 86400))
            row = self.snapshot()
            self.assertFalse(row['blocked'])
            self.assertEqual(row['remaining_day'], 20)

    def test_pacific_reset_without_windows_tzdata_handles_dst_transition_day(self):
        now = datetime(2026, 3, 8, 9, tzinfo=timezone.utc).timestamp()
        with patch.object(core, 'ZoneInfo', side_effect=RuntimeError('нет tzdata')):
            day, reset = core._calendar(now)
        self.assertEqual(day, '2026-03-08')
        self.assertEqual(reset, datetime(2026, 3, 9, 7, tzinfo=timezone.utc).timestamp())

    def test_two_processes_cannot_both_take_last_daily_request(self):
        from concurrent.futures import ThreadPoolExecutor
        self.correct(requests_today=19, successful_today=19)
        code = ('import sys,json,gemini_budget as gb; '
                'print(json.dumps(gb.reserve(sys.argv[2], "gemini-3.8-flash", state_file=sys.argv[1])))')

        def reserve_in_process(_):
            result = subprocess.run([sys.executable, '-X', 'utf8', '-c', code, self.path, self.key],
                                    capture_output=True, text=True, encoding='utf-8', check=True, timeout=20)
            return json.loads(result.stdout)

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(reserve_in_process, range(2)))
        self.assertEqual(sum(result[0] is not None for result in results), 1)
        row = self.snapshot()
        self.assertEqual((row['requests_today'], row['reserved_day'], row['remaining_day']), (19, 1, 0))

    def test_edit_does_not_erase_inflight_request_or_apply_old_error_pause(self):
        reservation, error = self.reserve(tokens=50)
        self.correct()
        row = self.snapshot()
        self.assertEqual((row['requests_today'], row['reserved_day']), (0, 1))
        self.finish(reservation, success=True, failure={'kind': 'quota', 'until': core.time.time() + 10000,
                                                         'reason': 'old error'})
        row = self.snapshot()
        self.assertEqual((row['successful_today'], row['requests_today'], row['in_flight']), (1, 1, 0))
        self.assertFalse(row['blocked'])

    def test_independent_projects_share_user_state(self):
        package_root = str(Path(gb.__file__).resolve().parent.parent)
        environment = dict(os.environ, GEMINI_BUDGET_DIR=self.directory.name, PYTHONPATH=package_root)
        target = str(Path(self.directory.name) / 'state.json')
        gb.correct(self.key, self.model, self.values(requests_today=19, successful_today=19), state_file=target)
        code = ('import json,sys,gemini_budget as gb; '
                'rid,error=gb.reserve(sys.argv[1],sys.argv[2]); '
                'gb.finish(sys.argv[1],sys.argv[2],rid,success=True,input_tokens=12); '
                'print(json.dumps({"accepted":rid is not None,"row":gb.status(sys.argv[1],sys.argv[2])}))')
        results = []
        for project in ('project_a', 'project_b'):
            cwd = Path(self.directory.name) / project
            cwd.mkdir()
            result = subprocess.run([sys.executable, '-X', 'utf8', '-c', code, self.key, self.model],
                                    cwd=cwd, env=environment, capture_output=True, text=True,
                                    encoding='utf-8', check=True, timeout=20)
            results.append(json.loads(result.stdout))
        self.assertEqual([r['accepted'] for r in results], [True, False])
        self.assertEqual([r['row']['remaining_day'] for r in results], [0, 0])

    def test_catalog_copies_defaults_and_returns_shared_key_overrides(self):
        models = gb.free_models()
        self.assertEqual({row['id'] for row in models},
                         {model for model in gb.CHAT_MODEL_IDS if gb.has_free_quota(model)})
        self.assertEqual(len(models), 9)
        self.assertEqual(len(gb.free_models(task='tts')), 4)
        self.assertEqual(len(gb.free_models(task='transcription')), 2)
        models[0]['limits']['rpd'] = 9999
        self.assertEqual(gb.limits(models[0]['id'])['rpd'], 20)
        gb.correct(self.key, self.model, self.values(rpm=7, rpd=32), state_file=self.path)
        self.assertEqual(gb.limits(self.model, self.key, state_file=self.path)['rpm'], 7)
        row = next(r for r in gb.free_models(self.key, state_file=self.path) if r['id'] == self.model)
        self.assertEqual(row['limits']['rpd'], 32)

    def test_legacy_migration_keeps_usage_and_deduplicates_repeat_and_copied_sources(self):
        import shutil
        legacy = Path(self.directory.name) / 'legacy.json'
        copied = Path(self.directory.name) / 'copied.json'
        gb.correct(self.key, self.model, self.values(requests_today=6, successful_today=5), state_file=legacy)
        rid, _ = gb.reserve(self.key, self.model, 10, state_file=legacy)
        gb.finish(self.key, self.model, rid, success=True, input_tokens=20, state_file=legacy)
        shutil.copyfile(legacy, copied)
        self.assertTrue(gb.import_legacy(legacy, state_file=self.path))
        self.assertFalse(gb.import_legacy(legacy, state_file=self.path))
        self.assertTrue(gb.import_legacy(copied, state_file=self.path))
        row = self.snapshot()
        self.assertEqual((row['requests_today'], row['successful_today'], row['requests_last_minute']), (7, 7, 1))
        self.assertEqual(row['input_tokens_last_minute'], 20)
        self.assertTrue(legacy.exists())
        self.assertNotIn(self.key, Path(self.path).read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
