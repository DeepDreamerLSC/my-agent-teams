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

    def test_result_success_parallel_quality_gate_dispatches_review_and_qa(self):
        task_dir = self._copy_fixture('result-success-review-pending')
        task = json.loads((task_dir / 'task.json').read_text(encoding='utf-8'))
        task['quality_gate_mode'] = 'parallel'
        (task_dir / 'task.json').write_text(json.dumps(task, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

        payload = run_reducer(task_dir)

        self.assertEqual(payload['patches']['status'], 'ready_for_merge')
        self.assertEqual(payload['patches']['merge_gate_state'], 'quality_pending')
        self.assertEqual(payload['patches']['review_gate_state'], 'pending')
        self.assertEqual(payload['patches']['qa_gate_state'], 'pending')
        self.assertEqual([action['type'] for action in payload['actions'][:2]], ['dispatch_review', 'dispatch_qa'])

    def test_review_rejected_routes_to_blocked(self):
        task_dir = self._copy_fixture('review-rejected')
        payload = run_reducer(task_dir)
        self.assertEqual(payload['patches']['status'], 'blocked')
        self.assertEqual(payload['patches']['merge_gate_state'], 'review_rejected')
        self.assertEqual(payload['patches']['rework_reason'], 'review')
        self.assertTrue(any(item['reason_type'] == 'blocked' for item in payload['attention_items']))

    def test_new_result_after_rejected_review_reopens_review_pending(self):
        task_dir = self._copy_fixture('result-after-review-rejection')
        payload = run_reducer(task_dir)
        self.assertEqual(payload['artifacts']['review']['normalized_status'], 'missing')
        self.assertEqual(payload['artifacts']['review']['source'], 'stale_json')
        self.assertIn('stale_round', payload['artifacts']['review']['warnings'])
        self.assertEqual(payload['patches']['status'], 'ready_for_merge')
        self.assertEqual(payload['patches']['merge_gate_state'], 'review_pending')
        self.assertIsNone(payload['patches']['rework_reason'])
        self.assertTrue(any(item['type'] == 'dispatch_review' for item in payload['actions']))

    def test_old_invalid_review_json_does_not_block_new_result(self):
        task_dir = self._copy_fixture('result-after-review-rejection')
        (task_dir / 'review.json').write_text('{"status": "definitely-not-valid", "round": 1}\n', encoding='utf-8')
        payload = run_reducer(task_dir)
        self.assertEqual(payload['artifacts']['review']['normalized_status'], 'missing')
        self.assertEqual(payload['artifacts']['review']['source'], 'stale_json')
        self.assertEqual(payload['patches']['merge_gate_state'], 'review_pending')
        self.assertFalse(any(
            item['reason_type'] == 'artifact_invalid' and 'review' in item['summary']
            for item in payload['attention_items']
        ))

    def test_old_verify_json_does_not_close_new_round_before_fresh_qa(self):
        task_dir = self._copy_fixture('result-after-review-rejection')
        task = json.loads((task_dir / 'task.json').read_text(encoding='utf-8'))
        task['review_required'] = False
        task['test_required'] = True
        task['merge_gate_state'] = 'qa_failed'
        task['rework_reason'] = 'qa'
        (task_dir / 'task.json').write_text(json.dumps(task, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        (task_dir / 'review.json').unlink(missing_ok=True)
        (task_dir / 'verify.json').write_text(json.dumps({
            'task_id': 'task-result-after-review-rejection',
            'tester': 'qa-1',
            'status': 'pass',
            'round': 1,
            'summary': '旧 QA 通过结果',
        }, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

        payload = run_reducer(task_dir)

        self.assertEqual(payload['artifacts']['verify']['normalized_status'], 'missing')
        self.assertEqual(payload['artifacts']['verify']['source'], 'stale_json')
        self.assertEqual(payload['patches']['merge_gate_state'], 'qa_pending')
        self.assertTrue(any(item['type'] == 'dispatch_qa' for item in payload['actions']))

    def test_done_task_with_old_result_does_not_reopen(self):
        task_dir = self._copy_fixture('result-after-review-rejection')
        task = json.loads((task_dir / 'task.json').read_text(encoding='utf-8'))
        task['status'] = 'done'
        task['merge_gate_state'] = 'closed'
        (task_dir / 'task.json').write_text(json.dumps(task, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        payload = run_reducer(task_dir)
        self.assertEqual(payload['patches'], {})
        self.assertEqual(payload['actions'], [])
        self.assertEqual(payload['reason'], 'terminal_status')

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

    def test_complex_review_requires_both_review_json_files(self):
        task_dir = self._copy_fixture('review-rejected')
        task = json.loads((task_dir / 'task.json').read_text(encoding='utf-8'))
        task['review_level'] = 'complex'
        task['status'] = 'ready_for_merge'
        task['merge_gate_state'] = 'review_pending'
        (task_dir / 'task.json').write_text(json.dumps(task, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        (task_dir / 'review.json').write_text(json.dumps({
            'task_id': 'task-review-rejected',
            'reviewer': 'review-1',
            'status': 'approve',
            'summary': '通过',
            'reviewed_at': '2026-05-09T10:20:00+08:00',
        }, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        (task_dir / 'review.md').unlink(missing_ok=True)
        payload = run_reducer(task_dir)
        self.assertEqual(payload['patches']['merge_gate_state'], 'review_pending')
        self.assertFalse(payload['artifacts']['review']['valid'])
        self.assertIn('design_review_json_missing_for_complex', payload['artifacts']['review']['errors'])

    def test_complex_review_reject_wins_even_when_design_review_json_missing(self):
        task_dir = self._copy_fixture('review-rejected')
        task = json.loads((task_dir / 'task.json').read_text(encoding='utf-8'))
        task['review_level'] = 'complex'
        task['status'] = 'ready_for_merge'
        task['merge_gate_state'] = 'review_pending'
        (task_dir / 'task.json').write_text(json.dumps(task, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

        payload = run_reducer(task_dir)

        self.assertEqual(payload['artifacts']['review']['normalized_status'], 'request_changes')
        self.assertEqual(payload['patches']['status'], 'blocked')
        self.assertEqual(payload['patches']['merge_gate_state'], 'review_rejected')
        self.assertEqual(payload['patches']['rework_reason'], 'review')

    def test_complex_markdown_fallback_single_approve_stays_review_pending(self):
        task_dir = self._copy_fixture('review-rejected')
        task = json.loads((task_dir / 'task.json').read_text(encoding='utf-8'))
        task['review_level'] = 'complex'
        task['status'] = 'ready_for_merge'
        task['merge_gate_state'] = 'review_pending'
        (task_dir / 'task.json').write_text(json.dumps(task, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        (task_dir / 'review.json').unlink(missing_ok=True)
        (task_dir / 'review.md').write_text('# Code Review\n\n## 结论\n审查结论：通过\n', encoding='utf-8')

        payload = run_reducer(task_dir)

        self.assertEqual(payload['artifacts']['review']['source'], 'markdown_fallback')
        self.assertEqual(payload['artifacts']['review']['normalized_status'], 'pending')
        self.assertEqual(payload['patches']['merge_gate_state'], 'review_pending')
        self.assertTrue(any(item['type'] == 'dispatch_review' for item in payload['actions']))

    def test_parallel_quality_gate_review_only_completion_keeps_quality_pending(self):
        task_dir = self._copy_fixture('review-rejected')
        task = json.loads((task_dir / 'task.json').read_text(encoding='utf-8'))
        task.update({
            'status': 'ready_for_merge',
            'merge_gate_state': 'quality_pending',
            'quality_gate_mode': 'parallel',
        })
        (task_dir / 'task.json').write_text(json.dumps(task, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        (task_dir / 'review.json').write_text(json.dumps({
            'task_id': 'task-review-rejected',
            'reviewer': 'review-1',
            'status': 'approve',
            'summary': 'review ok',
        }, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        (task_dir / 'verify.json').unlink(missing_ok=True)

        payload = run_reducer(task_dir)

        self.assertEqual(payload['patches']['merge_gate_state'], 'quality_pending')
        self.assertEqual(payload['patches']['review_gate_state'], 'approved')
        self.assertEqual(payload['patches']['qa_gate_state'], 'pending')
        self.assertTrue(any(item['type'] == 'dispatch_qa' for item in payload['actions']))

    def test_parallel_quality_gate_qa_only_completion_keeps_quality_pending(self):
        task_dir = self._copy_fixture('review-rejected')
        task = json.loads((task_dir / 'task.json').read_text(encoding='utf-8'))
        task.update({
            'status': 'ready_for_merge',
            'merge_gate_state': 'quality_pending',
            'quality_gate_mode': 'parallel',
        })
        (task_dir / 'task.json').write_text(json.dumps(task, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        (task_dir / 'review.json').unlink(missing_ok=True)
        (task_dir / 'verify.json').write_text(json.dumps({
            'task_id': 'task-review-rejected',
            'tester': 'qa-1',
            'status': 'pass',
            'summary': 'qa ok',
        }, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

        payload = run_reducer(task_dir)

        self.assertEqual(payload['patches']['merge_gate_state'], 'quality_pending')
        self.assertEqual(payload['patches']['review_gate_state'], 'pending')
        self.assertEqual(payload['patches']['qa_gate_state'], 'passed')
        self.assertTrue(any(item['type'] == 'dispatch_review' for item in payload['actions']))

    def test_parallel_quality_gate_complete_routes_to_pm_acceptance(self):
        task_dir = self._copy_fixture('review-rejected')
        task = json.loads((task_dir / 'task.json').read_text(encoding='utf-8'))
        task.update({
            'status': 'ready_for_merge',
            'merge_gate_state': 'quality_pending',
            'quality_gate_mode': 'parallel',
        })
        (task_dir / 'task.json').write_text(json.dumps(task, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        (task_dir / 'review.json').write_text(json.dumps({
            'task_id': 'task-review-rejected',
            'reviewer': 'review-1',
            'status': 'approve',
            'summary': 'review ok',
        }, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        (task_dir / 'verify.json').write_text(json.dumps({
            'task_id': 'task-review-rejected',
            'tester': 'qa-1',
            'status': 'pass',
            'summary': 'qa ok',
        }, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

        payload = run_reducer(task_dir)

        self.assertEqual(payload['patches']['merge_gate_state'], 'pm_acceptance_pending')
        self.assertEqual(payload['patches']['review_gate_state'], 'approved')
        self.assertEqual(payload['patches']['qa_gate_state'], 'passed')
        self.assertTrue(any(item['type'] == 'notify_pm_acceptance' for item in payload['actions']))


if __name__ == '__main__':
    unittest.main()
