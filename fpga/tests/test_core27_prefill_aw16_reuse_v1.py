import copy
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from fpga.reference import core27_prefill_aw16_reuse_v1 as gate
from fpga.reference import core27_prefill_qualification_v2 as recipes

ROOT = Path(__file__).resolve().parents[1]


class AW16ReuseTests(unittest.TestCase):
    def test_collected_native_predecessor_fully_replays(self):
        _, _, _, pins, report = gate.predecessor(ROOT)
        self.assertEqual(len(pins), 113)
        self.assertEqual(len(report['artifacts']), 22)
        self.assertEqual(len(report['cases']), 7)
        self.assertEqual([case['footer']['age'] for case in report['cases']], list(map(str, range(7))))
        self.assertEqual({case['footer']['row_index'] for case in report['cases']}, {'2048'})
        self.assertEqual(report['builds'][gate.ROLE]['executable_sha256'],
                         'a2e1122650436b3f8ce5fc8cc59ebcc7c21ddd427d5e57bc6bc0a0d1cce2c33e')

    def test_foreign_report_hash_cannot_be_reused(self):
        with patch.object(gate, 'PRE_REPORT_SHA', '0'*64):
            with self.assertRaisesRegex(ValueError, 'predecessor report'): gate.predecessor(ROOT)

    def test_predecessor_semantic_checks_reject_each_malformed_receipt(self):
        raw = (ROOT/gate.PRE_DIRECTORY/'report.json').read_text()
        original = json.loads(raw)
        parse = json.loads
        changes = (
            lambda d: d.update(status='failed_or_incomplete'),
            lambda d: d.update(aw=5),
            lambda d: d['cases'][0]['command'].__setitem__(3, '6'),
            lambda d: d['cases'][0]['footer'].update(middle_aliases_final='1'),
            lambda d: d['steps'][-1].update(returncode=1),
            lambda d: d['builds'][gate.ROLE]['derived_sources'].update({'rtl/kernel/genefer_carry_prefix_stream_precision_emit.sv':'0'*64}),
            lambda d: d['builds'][gate.ROLE].update(executable_sha256='0'*64),
            lambda d: d['builds'][gate.ROLE]['compiled_source_order'].reverse(),
            lambda d: d['builds'][gate.ROLE].update(harness_sha256='0'*64),
            lambda d: d.update(model_threads=2),
        )
        for change in changes:
            altered = copy.deepcopy(original); change(altered)
            # Simulate an approved report with incorrect semantic fields; the
            # actual disk archive remains immutable and its hash check still runs.
            with patch.object(gate.json, 'loads', side_effect=lambda value, *a, **k: copy.deepcopy(altered) if value == raw else parse(value, *a, **k)):
                with self.assertRaises(ValueError): gate.predecessor(ROOT)

    def test_selected_groups_have59_unique_remaining_cases(self):
        groups = [group for group in recipes.AW16_GROUPS if group != 'reset-middle']
        cases = gate.selected_cases(recipes, groups, '/passed-model', '/passed-vectors')
        self.assertEqual(len(groups), 10)
        self.assertEqual(len(cases), 59)
        self.assertEqual(len({name for _, name, _ in cases}), 59)
        for group, name, command in cases:
            self.assertIn((name, command), recipes.group_commands('/passed-model', '/passed-vectors', group))
        for invalid in ([], ['reset-middle'], ['reset-first']*2, ['all'], list(recipes.AW16_GROUPS)):
            with self.assertRaises(ValueError): gate.selected_cases(recipes, invalid, '/e', '/v')

    def test_inherited_commands_stay_exact_when_only_model_vector_paths_change(self):
        for group in recipes.AW16_GROUPS:
            if group == 'reset-middle': continue
            old = recipes.group_commands('/old-model', '/old-vector', group)
            new = gate.selected_cases(recipes, [group], '/new-model', '/new-vector')
            for (old_name, old_command), (_, new_name, new_command) in zip(old, new):
                self.assertEqual(old_name, new_name)
                self.assertEqual(old_command[1], new_command[1])
                self.assertEqual(old_command[3:], new_command[3:])

    def test_source_admission_binds_every_source_and_predecessor(self):
        manifest = {'sources': {'one.py':'1'*64, 'two.py':'2'*64}}
        receipt = dict(status='PASS_scoped_AW16_reuse_source_admission', manifest_sha256='a'*64,
                       predecessor_report_sha256=gate.PRE_REPORT_SHA, sources=manifest['sources'])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'source-review.json'
            path.write_text(json.dumps(receipt))
            self.assertEqual(gate.validate_source_review(path, gate.sha(path), manifest, 'a'*64), receipt)
            for key in ('status', 'manifest_sha256', 'predecessor_report_sha256', 'sources'):
                altered = dict(receipt); altered[key] = 'wrong'; path.write_text(json.dumps(altered))
                with self.assertRaises(ValueError): gate.validate_source_review(path, gate.sha(path), manifest, 'a'*64)

    def test_archives_reject_extra_duplicate_and_traversal_members(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); source = root/'source'; source.write_text('content')
            for names in (['one', 'one'], ['one', 'extra'], ['../escape']):
                archive_path = root/('archive'+str(len(names))+names[0].replace('/', '_')+'.tar.gz')
                with tarfile.open(archive_path, 'w:gz') as archive:
                    for name in names: archive.add(source, arcname=name)
                with self.assertRaises(ValueError): gate.archive_inventory(archive_path, {'one':gate.sha(source)})

    def test_original_assertions_and_frozen_sources_preserved(self):
        _, _, _, _, report = gate.predecessor(ROOT)
        carry = 'rtl/kernel/genefer_carry_prefix_stream_precision_emit.sv'
        self.assertEqual(report['builds'][gate.ROLE]['derived_sources'][carry], report['sources'][carry])
        self.assertIn('T5_EMIT_SIGNED32_REPRESENTATION', (ROOT/carry).read_text())
        self.assertEqual(gate.sha(ROOT/gate.FROZEN), gate.FROZEN_SHA)
        self.assertEqual(gate.sha(ROOT/gate.PRE_MANIFEST), gate.PRE_MANIFEST_SHA)
        pins = gate.source_pins(ROOT)
        self.assertEqual(len(pins), 116)

    def test_no_recompile_two_process_guard_and_per_case_receipts(self):
        source = (ROOT/gate.RUNNER).read_text()
        for token in ('concurrency in (1, 2)', 'os.sched_setaffinity(0, {cpu})',
                      "sorted(os.sched_getaffinity(child.pid)) == [cpu]", "command = [taskset, '-c', str(cpu), *argv]",
                      'resource.RLIMIT_AS, (3*GIB, 3*GIB)', 'max_concurrent_processes=concurrency',
                      'compile_workers=0', 'time.monotonic()-started < 9000', '10*GIB', '4*GIB',
                      "receipt['runtime_probe'] = probes[cpu]", "status='failed_or_incomplete'",
                      "report['status'] = 'passed_selected_aw16_groups_reuse_only'", 'os.killpg', 'current_tools == prior'):
            self.assertIn(token, source)
        self.assertEqual(source.count('subprocess.Popen('), 1)
        self.assertNotIn('shutil.rmtree', source)
        self.assertNotIn('mutate_tee', source)


if __name__ == '__main__': unittest.main()
