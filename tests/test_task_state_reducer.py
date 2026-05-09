from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
REDUCER = REPO_ROOT / 'scripts' / 'task-state-reducer.py'
FIXTURE_ROOT = REPO_ROOT / 'tests' / 'fixtures' / 'task-state'


def run_reducer(task_dir: Path) -> dict:
    completed = subprocess.run(
        ['python3', str(REDUCER), '--task-dir', str(task_dir)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(completed.stdout)


class TaskStateReducerFixtureTests(unittest.TestCase):
    def _copy_fixture(self, name: str) -> Path:
        tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(tmpdir.cleanup)
        src = FIXTURE_ROOT / name
        dst = Path(tmpdir.name) / name
        shutil.copytree(src, dst)
        return dst

    def test_result_success_routes_to_review_pending(self):
        task_dir = self._copy_fixture('result-success-review-pending')
        payload = run_reducer(task_dir)
        self.assertEqual(payload['patches']['status'], 'ready_for_merge')
        self.assertEqual(payload['patches']['merge_gate_state'], 'review_pending')
        self.assertEqual(payload['actions'][0]['type'], 'dispatch_review')

    def test_review_rejected_routes_to_blocked(self):
        task_dir = self._copy_fixture('review-rejected')
        payload = run_reducer(task_dir)
        self.assertEqual(payload['patches']['status'], 'blocked')
        self.assertEqual(payload['patches']['merge_gate_state'], 'review_rejected')
        self.assertEqual(payload['patches']['rework_reason'], 'review')
        self.assertTrue(any(item['reason_type'] == 'blocked' for item in payload['attention_items']))

    def test_resume_stale_result_is_ignored_and_flagged(self):
        task_dir = self._copy_fixture('resume-stale-result')
        stale_epoch = 1
        os.utime(task_dir / 'ack.json', (stale_epoch, stale_epoch))
        os.utime(task_dir / 'result.json', (stale_epoch, stale_epoch))
        payload = run_reducer(task_dir)
        self.assertEqual(payload['patches'], {})
        self.assertTrue(any(item['reason_type'] == 'stale_resume' for item in payload['attention_items']))
        self.assertFalse(payload['artifacts']['result']['is_current_round'])
        self.assertFalse(payload['artifacts']['ack']['is_current_round'])

    def test_new_tasks_require_review_json_instead_of_markdown_fallback(self):
        task_dir = self._copy_fixture('review-json-required')
        payload = run_reducer(task_dir)
        self.assertEqual(payload['patches']['merge_gate_state'], 'review_pending')
        self.assertEqual(payload['artifacts']['review']['normalized_status'], 'missing')


if __name__ == '__main__':
    unittest.main()
