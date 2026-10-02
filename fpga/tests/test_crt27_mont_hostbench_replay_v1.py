"""Pure offline source/runtime/journal negatives; no HDL, cloud or native fit."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from fpga.synthesis import replay_crt27_mont_hostbench_v1 as replay


class HostBenchmarkReplay(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.archive = Path(self.temp.name) / 'archive'
        shutil.copytree(replay.ARCHIVE, self.archive)
        self.inventory = replay.read_json(self.archive / 'collection-inventory.json')
        self.journal = replay.read_json(self.archive / 'terminal-journal-read.json')

    def payload(self):
        return replay.replay_payload(self.archive, self.inventory, self.journal)

    def rewrite_same_size(self, name, value):
        path = self.archive / name
        old_size = path.stat().st_size
        suffix = '\n' if path.read_bytes().endswith(b'\n') else ''
        text = json.dumps(value, indent=2) + suffix
        self.assertEqual(len(text.encode()), old_size, 'fixture must reach semantic gate after fixed byte closure')
        path.write_text(text)
        self.inventory['files'][name]['sha256'] = replay.sha(path)

    def rewrite_context(self, mutate):
        context = replay.read_json(self.archive / 'project/execution-context.json')
        mutate(context)
        self.rewrite_same_size('project/execution-context.json', context)
        result = replay.read_json(self.archive / 'project/execution-result.json')
        result['context_sha256'] = replay.sha(self.archive / 'project/execution-context.json')
        self.rewrite_same_size('project/execution-result.json', result)
        self.journal.update(context=context, result=result, context_sha256=result['context_sha256'],
                            result_sha256=replay.sha(self.archive / 'project/execution-result.json'))

    def test_exact_archive_and_source_bound_comparison(self):
        result = replay.verify(self.archive)
        self.assertEqual(result['wall_reduction_seconds'], '79.15')
        self.assertEqual(result['collected_files'], 34)
        self.assertFalse(result['promotion_allowed'])
        self.assertFalse(result['fresh_native_binary_hash_after_resize'])
        self.assertEqual(result['component_summary_unchanged']['alms_placed'], 12790)
        self.assertEqual(result['cgroup_memory_peak_bytes'], 6952120320)

    def test_source_byte_fault(self):
        source = self.archive / 'project/rtl/crt27_resource16.sv'
        source.write_bytes(source.read_bytes() + b'\n')
        with self.assertRaisesRegex(ValueError, 'artifact identity'):
            replay.verify(self.archive)

    def test_extra_database_payload(self):
        (self.archive / 'unexpected.qdb').write_bytes(b'fixture')
        with self.assertRaisesRegex(ValueError, 'archive file closure'):
            replay.verify(self.archive)

    def test_rebound_inventory_cannot_replace_public_anchor(self):
        value = copy.deepcopy(self.inventory)
        value['file_count'] = 35
        (self.archive / 'collection-inventory.json').write_text(json.dumps(value) + '\n')
        with self.assertRaisesRegex(ValueError, 'immutable collection anchor'):
            replay.verify(self.archive)

    def test_wrong_invocation_typed_negative(self):
        self.journal['invocation_id'] = '0' * 32
        with self.assertRaisesRegex(ValueError, 'exact successful invocation'):
            self.payload()

    def test_gc_not_found_is_not_success(self):
        self.journal['journal_manager_rows'][1]['MESSAGE'] = replay.UNIT + ': Failed with result exit-code.'
        with self.assertRaisesRegex(ValueError, 'manager successful terminal'):
            self.payload()

    def test_swap_usage_rejected(self):
        self.journal['journal_manager_rows'][2]['MEMORY_SWAP_PEAK'] = '1'
        with self.assertRaisesRegex(ValueError, 'manager successful terminal/no swap'):
            self.payload()

    def test_six_worker_context_cannot_masquerade_as_matched_benchmark(self):
        self.rewrite_context(lambda value: value.__setitem__('quartus_workers', 6))
        with self.assertRaisesRegex(ValueError, 'four-worker bounded exclusive benchmark'):
            self.payload()

    def test_nonzero_native_terminal_rejected(self):
        result = replay.read_json(self.archive / 'project/execution-result.json')
        result['quartus_returncode'] = 1
        self.rewrite_same_size('project/execution-result.json', result)
        self.journal.update(result=result, result_sha256=replay.sha(self.archive / 'project/execution-result.json'))
        with self.assertRaisesRegex(ValueError, 'successful terminal exits'):
            self.payload()

    def test_rebound_raw_wall_fault(self):
        name = replay.PROJECT + '-fit.log'
        path = self.archive / name
        raw = path.read_bytes()
        self.assertEqual(raw.count(b': 3:29.90'), 1)
        path.write_bytes(raw.replace(b': 3:29.90', b': 3:29.91', 1))
        self.inventory['files'][name]['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
        with self.assertRaisesRegex(ValueError, 'matched raw wall measurements'):
            self.payload()


if __name__ == '__main__':
    unittest.main()
