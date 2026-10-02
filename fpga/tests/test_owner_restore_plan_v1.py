import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fpga.tools.owner_restore_plan_v1 import build_plan, main


class RestorePlanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        self.folder = self.repo / 'fpga/docs/briefs/replies/status'
        self.folder.mkdir(parents=True)

    def status(self, owner, text):
        path = self.folder / (owner + '.md')
        path.write_text(text)
        return path

    def test_focused_payload_and_source_identity(self):
        path = self.status('t5b_e2e', '# E2E\n- Restore: active.\n- Current candidate: same frozen T5b\n- Blockers: quota\n- Last receipt: exact/report.json\n- Next: native lint\n')
        before = path.read_bytes()
        plan = build_plan(self.repo)
        item = plan['inventory'][0]
        self.assertEqual(item['status_path'], str(path.resolve()))
        self.assertEqual(item['restore_state'], 'active')
        self.assertEqual(item['current_candidate'], 'same frozen T5b')
        self.assertEqual(item['blocker'], 'quota')
        self.assertEqual(item['last_receipt'], 'exact/report.json')
        call = plan['followup_tasks'][0]
        self.assertEqual(call['tool'], 'collaboration.followup_task')
        self.assertEqual(call['arguments']['target'], '/root/t5b_e2e')
        self.assertIn('same frozen T5b', call['arguments']['message'])
        self.assertEqual(path.read_bytes(), before)
        self.assertTrue(plan['read_only'] and plan['calls_are_drafts'])

    def test_completed_gate_is_not_completed_owner(self):
        self.status('independent_review', '# Review\n- Current closed milestone: smoke completed\n- Next: exact A4b receipt\n')
        plan = build_plan(self.repo)
        self.assertEqual(len(plan['followup_tasks']), 1)

    def test_explicit_completed_deferred_and_parked_filtered(self):
        self.status('t5_qualification', '# T5\n- Restore: completed\n')
        self.status('sim_compile_slots', '# Leases\nStatus: later\n')
        self.status('dashboard', '# Dashboard\n- Current work: old dashboard\n')
        self.assertEqual(build_plan(self.repo)['followup_tasks'], [])

    def test_dependency_ready_completed_owner_only(self):
        self.status('t5_qualification', '# T5\nRestore: completed\nNext: await E2E receipt\n')
        self.status('dashboard', '# Dashboard\nRestore: parked\n')
        plan = build_plan(self.repo, ready=['t5_qualification'])
        self.assertEqual(len(plan['followup_tasks']), 1)
        self.assertTrue(plan['followup_tasks'][0]['dependency_ready'])

    def test_main_excluded_unranked_not_implicitly_started(self):
        self.status('main', '# Main\nRestore: active\n')
        self.status('new_owner', '# Unknown\nRestore: active\n')
        plan = build_plan(self.repo)
        self.assertEqual(plan['followup_tasks'], [])
        self.assertEqual(len(plan['skipped']), 2)

    def test_missing_status_not_fake_complete(self):
        plan = build_plan(self.repo, only=['soak_chunks'])
        self.assertEqual(plan['missing_status_owners'], ['soak_chunks'])
        self.assertEqual(plan['followup_tasks'], [])

    def test_section_complete_not_whole_owner_complete(self):
        self.status('threaded_aw16', '# Thread owner\n## Old gate\nStatus: complete\n## NEXT\nNative pilot\n')
        self.assertEqual(len(build_plan(self.repo)['followup_tasks']), 1)

    def test_period_terminated_complete_marker(self):
        self.status('t5_qualification', '# T5\n- Restore: completed.\n')
        self.assertEqual(build_plan(self.repo)['followup_tasks'], [])

    def test_symlink_rejected(self):
        target = self.repo / 'other.md'
        target.write_text('not an owner status')
        (self.folder / 't5b_e2e.md').symlink_to(target)
        with self.assertRaisesRegex(ValueError, 'unsafe'):
            build_plan(self.repo)

    def test_bad_name_rejected(self):
        with self.assertRaisesRegex(ValueError, 'invalid'):
            build_plan(self.repo, only=['../outside'])

    def test_cli_only_prints_plan(self):
        self.status('t5b_e2e', '# E2E\nRestore: active\n')
        output = io.StringIO()
        with patch('sys.argv', ['restore', '--repo', str(self.repo), '--owner', 't5b_e2e']), contextlib.redirect_stdout(output):
            main()
        self.assertIn('collaboration.followup_task', output.getvalue())
        self.assertEqual(sorted(path.name for path in self.folder.iterdir()), ['t5b_e2e.md'])


if __name__ == '__main__':
    unittest.main()
