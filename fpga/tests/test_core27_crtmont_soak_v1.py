"""Small-N scalar/source tests only; no HDL or full-N integer computation."""
import copy
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from fpga.reference import core27_crtmont_soak_v1 as s
from fpga.tools import native_thread_config_v1 as threads


def fixture(oracle, negative='none'):
    plan, segment = s.check_oracle(oracle)
    rows = []
    target = segment['start'] if negative == 'loaded-state' else segment['checkpoints'][1]['step']
    operations = 0
    for check in segment['checkpoints']:
        while operations < check['step']-segment['start']:
            rows.append(('SOAK_STEP', dict(case_id=plan['case_id'], step=segment['start']+operations+1,
                bit=int(segment['double_bits'][operations]), cycles=100, conversion=10, roots=20,
                ntt=30, crt=15, carry=25, profile_loads=int(operations == 0), profile_hits=int(operations != 0))))
            operations += 1
        values = list(check['digits'])
        if negative == 'loaded-state' and check['step'] == target:
            values[0] = 0 if values[0] == -1 else (values[0]+1) % plan['profile']['base']
        rows.append(('SOAK_CHECK', dict(case_id=plan['case_id'], step=check['step'], digits=values)))
        if negative != 'none' and check['step'] == target:
            return rows, 1, f'SOAK_BOUNDARY_MISMATCH step={target} digit=0\n'
    rows.append(('SOAK_PASS', dict(case_id=plan['case_id'], mode=segment['mode'], start=segment['start'], end=segment['end'],
        operations=operations, doubles=segment['doubles'], readbacks=len(segment['checkpoints']), cycles=100*operations,
        resets=1, loaded_digits=plan['profile']['n'], cold=1, warm=operations-1)))
    return rows, 0, ''


def render(rows):
    return ''.join(prefix+' '+json.dumps(value, separators=(',', ':'))+'\n' for prefix, value in rows)


class SoakPlanTests(unittest.TestCase):
    def small(self, initial='dense'):
        return s.make_plan(aw=5, squares=13, chunk_squares=5, checkpoint_every=3,
                           seed=902341, base=1000000000, initial=initial)

    def test_aw16_metadata_has_distinct_gates_without_full_reference_work(self):
        with patch.object(s, 'backend', side_effect=AssertionError('not metadata')):
            plan = s.make_plan()
        self.assertEqual(len(plan['chunks']), 10)
        self.assertEqual(plan['checkpoints'], list(range(0, 1001, 100)))
        self.assertEqual(s.check_plan(plan), plan)
        self.assertEqual(plan['double_bits'][:2], '01')
        changed = copy.deepcopy(plan); changed['double_bits'] = '1'+changed['double_bits'][1:]
        with self.assertRaisesRegex(ValueError, 'PLAN_IDENTITY'):
            s.check_plan(changed)

    def test_plan_rejects_profile_and_bound_mutations(self):
        for kwargs in (dict(aw=True), dict(aw=17), dict(base=131076), dict(squares=0),
                       dict(squares=4097), dict(chunk_squares=1001), dict(checkpoint_every=1001),
                       dict(checkpoint_every=1), dict(chunk_squares=1),
                       dict(seed=-1), dict(seed=True), dict(initial='unknown')):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                s.make_plan(**kwargs)

    def test_full_n_integer_work_rejected_on_mac_before_gmp_import(self):
        with patch.object(s.platform, 'system', return_value='Darwin'):
            with self.assertRaisesRegex(ValueError, 'FULL_INTEGER_LINUX_ONLY'):
                s.corpus(s.make_plan(), 'gmpy2')
            with self.assertRaises(ValueError):
                s.corpus(s.make_plan(), 'python-small-only')

    def test_radix_special_and_dense_states_roundtrip(self):
        for aw, base in ((5, 69), (8, 1000000000)):
            m, encode, decode = s.digit_tools(base, 1 << aw, int)
            for value in (0, 1, base-1, base, m-2, m-1):
                self.assertEqual(decode(encode(value)), value)
            self.assertEqual(encode(m-1), [-1]+[0]*((1 << aw)-1))
            with self.assertRaises(ValueError):
                decode([-1, 1]+[0]*((1 << aw)-2))
            with self.assertRaises(ValueError):
                decode([base]+[0]*((1 << aw)-1))

    def test_chunks_start_from_the_exact_global_state_and_check_every_boundary(self):
        plan = self.small()
        items = s.corpus(plan, 'python-small-only')
        continuous = items['continuous'][1]
        _, encode, decode = s.digit_tools(plan['profile']['base'], plan['profile']['n'], int)
        modulus = plan['profile']['base']**plan['profile']['n']+1
        reference = decode(s.initial_digits(plan))
        expected = {0: reference}
        for step, bit in enumerate(plan['double_bits'], 1):
            reference = reference*reference*(1 << int(bit)) % modulus
            expected[step] = reference
        for name, (text, oracle) in items.items():
            self.assertEqual(s.text_sha(text), oracle['corpus_sha256'])
            self.assertEqual(s.check_oracle(oracle)[0], plan)
            for check in oracle['segment']['checkpoints']:
                self.assertEqual(check['digits'], encode(expected[check['step']]))
                self.assertEqual(check['residue_sha256'], s.residue_sha(expected[check['step']]))
            self.assertEqual(oracle['segment']['double_bits'], plan['double_bits'][oracle['segment']['start']:oracle['segment']['end']])
        self.assertEqual(continuous['oracle']['schedule_exponent_crosscheck'], True)
        self.assertEqual(items['chunk-00'][1]['segment']['checkpoints'][-1], items['chunk-01'][1]['segment']['checkpoints'][0])
        self.assertEqual(items['chunk-01'][1]['segment']['checkpoints'][-1], items['chunk-02'][1]['segment']['checkpoints'][0])

    def test_corner_initial_states_and_seed_are_reproducible(self):
        for initial in ('dense', 'zero', 'one', 'minus-one'):
            first = s.corpus(self.small(initial), 'python-small-only')
            second = s.corpus(self.small(initial), 'python-small-only')
            self.assertEqual(first, second)
            self.assertFalse(first['continuous'][1]['oracle']['native_qualification_allowed'])
        self.assertNotEqual(s.initial_digits(self.small()), s.initial_digits(s.make_plan(
            aw=5, squares=13, chunk_squares=5, checkpoint_every=3, seed=902342, base=1000000000)))

    def test_exact_promoted_sixteen_source_parent_is_unchanged(self):
        order, pins = s.parent_sources()
        self.assertEqual(len(order), 16)
        self.assertEqual(pins['rtl/kernel/'+s.TOP+'.sv'], 'b6dbd4fccc6d7708fd295d3c82e2ebec444c4a2fbde8612851f10f979da04895')

    def test_generated_small_assets_are_write_once_and_cannot_stage_native(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = s.generate(root/'reference', self.small(), 'python-small-only')
            self.assertEqual(result['gates']['uninterrupted_1000_square_rtl'], 'not_run')
            for name, digest in result['files'].items():
                self.assertEqual(s.sha(root/'reference'/name), digest)
            with self.assertRaisesRegex(ValueError, 'FRESH_REFERENCE_OUTPUT'):
                s.generate(root/'reference', self.small(), 'python-small-only')
            with self.assertRaisesRegex(ValueError, 'NATIVE_REFERENCE_ONLY'):
                s.stage_segment(root/'reference', 'continuous', root/'stage', 'gfn16-pilot-c4d', '/admitted/soak')
            self.assertFalse((root/'stage').exists())

    def test_mocked_stage_closes_every_source_and_rejects_reference_drift(self):
        # These temporary fixtures deliberately mock the backend. They are
        # package-contract tests, never exported as Linux/gmpy2/native evidence.
        provenance = dict(engine='gmpy2', platform='Linux', native_qualification_allowed=True,
                          fixture='MOCKED_SCALAR_BACKEND_NOT_NATIVE_EVIDENCE')
        with tempfile.TemporaryDirectory() as directory, patch.object(s, 'backend', return_value=(int, provenance)):
            root = Path(directory)
            s.generate(root/'reference', self.small(), 'gmpy2')
            result = s.stage_segment(root/'reference', 'chunk-01', root/'stage', 'gfn16-pilot-c4d', '/admitted/soak')
            manifest = json.loads((root/'stage/manifest.json').read_text())
            actual = {str(path.relative_to(root/'stage/source/fpga')):s.sha(path)
                for path in (root/'stage/source/fpga').rglob('*') if path.is_file()}
            self.assertEqual(actual, manifest['sources'])
            self.assertEqual(result['manifest_sha256'], s.sha(root/'stage/manifest.json'))
            self.assertEqual(manifest['build']['runtime_threads'], 1)
            self.assertEqual(threads.validate_build(manifest['build'], manifest['probe']['expected_json']), 1)
            self.assertEqual(manifest['soak']['requested_gate'], 'chunked_arithmetic_coverage')
            self.assertEqual(manifest['steps'][1]['expected_returncode'], 1)
            self.assertEqual(manifest['steps'][2]['validator']['config'], {'negative':'loaded-state'})
            for step in manifest['steps']:
                self.assertIn(step['validator']['source'], actual)
                self.assertIn(step['validator']['assets']['oracle'], actual)
            with self.assertRaisesRegex(ValueError, 'SHORT_AW_SINGLE_THREAD'):
                s.stage_segment(root/'reference', 'continuous', root/'threads2', 'gfn16-pilot-c4d', '/admitted/soak', 2)
            corpus = root/'reference/chunk-01.txt'
            corpus.write_text(corpus.read_text()+'DRIFT\n')
            with self.assertRaisesRegex(ValueError, 'REFERENCE_FILE_DRIFT'):
                s.stage_segment(root/'reference', 'chunk-01', root/'drift', 'gfn16-pilot-c4d', '/admitted/soak')

    def test_host_bench_cpp_syntax_against_scalar_port_stub(self):
        compiler = shutil.which('c++')
        if compiler is None:
            self.skipTest('No C++ compiler for host-only syntax check')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'verilated.h').write_text('''#pragma once
class VerilatedContext { unsigned n=1; public:
  void threads(unsigned v){n=v;} unsigned threads()const{return n;}
  void commandArgs(int,char**){} };
''')
            (root/('V'+s.TOP+'.h')).write_text('''#pragma once
#include "verilated.h"
#include <cstdint>
class Vgenefer_square_core27_stream_prefetch_r2_host_broadcast_orient8_rootfused_crtmont {
 public:
  explicit Vgenefer_square_core27_stream_prefetch_r2_host_broadcast_orient8_rootfused_crtmont(VerilatedContext*){}
  unsigned threads()const{return GFN16_RUNTIME_THREADS;} void eval(){} void final(){}
  uint8_t clk=0,start=0,load_we=0,read_en=0,rst_n=0,double_bit=0;
  uint8_t busy=0,done=0,error=0,read_valid=0,profile_cache_valid=0,profile_loads=0,profile_hits=0;
  uint32_t base=0,host_addr=0; int32_t write_data=0; uint32_t read_data[3]={0,0,0};
  uint64_t cycles=0,conversion_cycles=0,root_cycles=0,ntt_cycles=0,crt_cycles=0,carry_cycles=0;
};
''')
            checked = subprocess.run([compiler, '-std=c++17', '-Wall', '-Wextra', '-Werror', '-fsyntax-only',
                '-DGFN16_SOAK_AW=5', '-DGFN16_RUNTIME_THREADS=1', '-I'+str(root), str(s.ROOT/s.BENCH)],
                capture_output=True, text=True, timeout=30)
            self.assertEqual(checked.returncode, 0, checked.stderr)


class SoakBoundaryTests(unittest.TestCase):
    def small(self):
        return s.make_plan(aw=5, squares=13, chunk_squares=5, checkpoint_every=3,
                           seed=902341, base=1000000000)
    def oracle(self, name='continuous'):
        return s.corpus(self.small(), 'python-small-only')[name][1]

    def review(self, rows, oracle=None, stderr='', returncode=0, negative='none'):
        return s.validate_rows(render(rows), stderr, returncode, dict(negative=negative), oracle or self.oracle())

    def test_fixture_contract_and_both_negative_boundary_controls(self):
        for name in ('continuous', 'chunk-00', 'chunk-01', 'chunk-02'):
            oracle = self.oracle(name)
            for negative in ('none', 'boundary', 'loaded-state'):
                rows, code, error = fixture(oracle, negative)
                result = self.review(rows, oracle, error, code, negative)
                if negative == 'none':
                    self.assertFalse(result['uninterrupted_1000_square_rtl'])
                    self.assertEqual(result['operations'], oracle['segment']['operations'])
                else:
                    self.assertEqual(result['status'], 'passed_matched_soak_negative')

    def test_missing_duplicate_reordered_or_corrupt_boundary_cannot_pass(self):
        rows, _, _ = fixture(self.oracle())
        check_indexes = [i for i, (kind, _) in enumerate(rows) if kind == 'SOAK_CHECK']
        mutations = []
        missing = copy.deepcopy(rows); del missing[check_indexes[1]]; mutations.append(missing)
        duplicate = copy.deepcopy(rows); duplicate.insert(check_indexes[1], duplicate[check_indexes[1]]); mutations.append(duplicate)
        reordered = copy.deepcopy(rows); reordered[check_indexes[1]], reordered[check_indexes[2]] = reordered[check_indexes[2]], reordered[check_indexes[1]]; mutations.append(reordered)
        for index in check_indexes:
            corrupt = copy.deepcopy(rows); corrupt[index][1]['digits'][0] = (corrupt[index][1]['digits'][0]+1) % 1000000000; mutations.append(corrupt)
        for changed in mutations:
            with self.assertRaises(ValueError):
                self.review(changed)

    def test_operation_bit_cache_cycles_counts_and_footer_cannot_drift(self):
        rows, _, _ = fixture(self.oracle())
        first = next(i for i, (kind, _) in enumerate(rows) if kind == 'SOAK_STEP')
        mutations = []
        for key, value in (('bit', 1), ('step', 2), ('cycles', 99), ('profile_hits', 1), ('carry', -1), ('cycles', True)):
            changed = copy.deepcopy(rows); changed[first][1][key] = value; mutations.append(changed)
        for key, value in (('operations', 12), ('resets', 2), ('loaded_digits', 64), ('readbacks', 2), ('warm', 0)):
            changed = copy.deepcopy(rows); changed[-1][1][key] = value; mutations.append(changed)
        missing = copy.deepcopy(rows); del missing[first]; mutations.append(missing)
        for changed in mutations:
            with self.assertRaises(ValueError):
                self.review(changed)

    def test_negative_controls_require_exact_failure_point_and_error(self):
        for negative in ('boundary', 'loaded-state'):
            rows, code, error = fixture(self.oracle(), negative)
            for changed_code, changed_error in ((0, error), (code, ''), (code, error.replace('digit=0', 'digit=1'))):
                with self.assertRaises(ValueError):
                    self.review(rows, stderr=changed_error, returncode=changed_code, negative=negative)
            with self.assertRaises(ValueError):
                self.review(rows+rows[-1:], stderr=error, returncode=code, negative=negative)

    def test_small_python_fixture_never_passes_the_native_adapter(self):
        oracle = self.oracle(); rows, code, error = fixture(oracle)
        with self.assertRaisesRegex(ValueError, 'NATIVE_GMPY2_REFERENCE_REQUIRED'):
            s.validate(render(rows), error, code, dict(negative='none'), {'oracle':json.dumps(oracle)})

    def test_chunks_cannot_become_a_continuous_gate(self):
        plan = self.small()
        results = []
        for chunk in plan['chunks']:
            oracle = self.oracle(f"chunk-{chunk['index']:02d}")
            rows, _, _ = fixture(oracle)
            result = self.review(rows, oracle)
            # Explicit parser fixtures, not native evidence.
            result.update(independent_gmpy2_boundary_replay=True, parent_manifest_sha256=s.PARENT_SHA,
                          native_qualification_allowed=True)
            results.append(result)
        combined = s.combine_chunks(plan, results)
        self.assertEqual(combined['operations'], 13)
        self.assertFalse(combined['uninterrupted_1000_square_rtl'])
        self.assertEqual(combined['continuous_gate'], 'still_required')
        for changed in (results[:-1], results+[results[0]]):
            with self.assertRaises(ValueError):
                s.combine_chunks(plan, changed)
        mutated = copy.deepcopy(results); mutated[1]['checkpoint_residue_sha256']['5'] = '0'*64
        with self.assertRaisesRegex(ValueError, 'ADJACENT_CHUNK_STATE_IDENTITY'):
            s.combine_chunks(plan, mutated)


if __name__ == '__main__':
    unittest.main()
