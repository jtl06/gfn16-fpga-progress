import hashlib
import json
from pathlib import Path
import random
import unittest
from unittest.mock import patch

from fpga.reference import core27_prefill_qualification_v2 as recipes
from fpga.reference import core27_prefill_qualification_v2_regression as gate
from fpga.reference import core27_prefill_mutant_sources as recipe
from fpga.reference import core27_prefill_target_vectors as old_vectors
from fpga.reference import core27_prefill_adversarial_regression as frozen
from fpga.reference import core27_prefetch_r2_regression as baseline

ROOT = Path(__file__).resolve().parents[1]


class QualificationV2Tests(unittest.TestCase):
    def test_shared_control_is_exactly_matched_for_all_four_contracts(self):
        control, mutants = recipes.batch_sources(ROOT, recipe, recipes.REMAINING)
        self.assertEqual(tuple(mutants), ('base_tag', 'late_host_error', 'omitted_tee', 'corrupted_tee'))
        for name, (mutant, contract) in mutants.items():
            original_control, original_mutant, original_contract = recipe.pair_sources(ROOT, name)
            if name not in recipe.TEE_MUTANTS:
                original_control[recipe.CARRY] = recipe.tee_control(original_control[recipe.CARRY])
                original_mutant[recipe.CARRY] = recipe.tee_control(original_mutant[recipe.CARRY])
            self.assertEqual(control, original_control)
            self.assertEqual(mutant, original_mutant)
            self.assertEqual(contract['fatal'], original_contract['fatal'])
            self.assertEqual(contract['lines'], original_contract['lines'])
            self.assertEqual(set(contract['changed_sources']), {recipe.CARRY} if name in recipe.TEE_MUTANTS else {recipe.CORE, recipe.BRIDGE})
            for sources in (control, mutant):
                self.assertNotIn('T5_EMIT_SIGNED32_REPRESENTATION', sources[recipe.CARRY])
                self.assertIn('T5_EMIT_NOT_ACTUAL_COMMIT', sources[recipe.CARRY])
            self.assertEqual(recipe.command('/control', '/vectors', name)[1:], recipe.command('/mutant', '/vectors', name)[1:])
        for names in ((), recipes.REMAINING[:-1], recipes.REMAINING[::-1], recipe.NAMES):
            with self.assertRaises(ValueError): recipes.batch_sources(ROOT, recipe, names)

    def test_every_mutant_requires_the_exact_independent_observer_fatal(self):
        _, mutants = recipes.batch_sources(ROOT, recipe, recipes.REMAINING)
        for _, contract in mutants.values():
            line = contract['lines'][0]
            output = f"[0] %Fatal: core27_prefill_tail_probe_v3.sv:{line}: Assertion failed in TOP.core27_prefill_tail_probe_v3: {contract['fatal']}\nAborting...\n"
            self.assertEqual(recipe.check_fatal(output, -6, contract)['fatal'], contract['fatal'])
            for code in (0, 1, -9, 124):
                with self.assertRaises(ValueError): recipe.check_fatal(output, code, contract)
            with self.assertRaises(ValueError): recipe.check_fatal(output.replace(contract['fatal'], 'T5_EMIT_NOT_ACTUAL_COMMIT'), -6, contract)

    def test_aw16_derivation_preserves_fault_free_assertions(self):
        source = (ROOT/'rtl/tb/core27_prefill_adversarial_v1.cpp').read_text()
        result = recipes.aw16_harness(source)
        self.assertIn('n==65536', result)
        self.assertIn('d.conversion_cycles==(fast?0:4102)', result)
        self.assertIn('n/16>2 && (n/16)/2<n/16-1', result)
        self.assertNotIn('age==0', result)
        for marker in ('T5_RESET_TAIL_GHOST', 'T5_FAILED_QUARANTINE_LEAK', 'T5_TARGET_READBACK',
                       'T5_TARGET_IMAGE_COUNT', 'T5_SMALLER_BASE_DIGIT_NOT_REJECTED',
                       'start(b,1);finish(b,v[3],true)', 'load(a);start(a,0);finish(a,v[1],false)'):
            self.assertIn(marker, result)
        self.assertEqual(gate.sha(ROOT/'rtl/tb/core27_prefill_adversarial_v1.cpp'),
                         '14661ac736180b91247cea4552d2d88cc608b67ba6cad849c2e4d690f4c15478')
        with self.assertRaises(ValueError): recipes.aw16_harness(result)

    def test_aw16_groups_cover_each_real_row_all_seven_ages(self):
        cases = [entry for group in recipes.AW16_GROUPS for entry in recipes.group_commands('/e', '/v', group)]
        self.assertEqual(len(cases), 66)
        self.assertEqual(len({name for name, _ in cases}), 66)
        for group in recipes.AW16_GROUPS:
            commands = recipes.group_commands('/e', '/v', group)
            self.assertLessEqual(len(commands), 7)
            if group not in ('base-change', 'reload-control'):
                self.assertEqual([argv[3] for _, argv in commands], list(map(str, range(7))))
        with self.assertRaises(ValueError): recipes.group_commands('/e', '/v', 'all')

    def test_aw16_footer_binds_middle_distinct_final_and_every_field(self):
        for group in recipes.AW16_GROUPS:
            for _, argv in recipes.group_commands('/e', '/v', group):
                mode = argv[1]
                age, row = ('0', 'none') if len(argv) == 4 else (argv[3], argv[4])
                counts = (3, 3, 0) if mode == '--changed-base' else (2, 2, 1) if mode == '--base-reject' else (2, 2, 0) if mode == '--reload-control' else (1, 1, 1)
                fields = dict(mode=mode, age=age, row=row, row_index=str({'first':0, 'middle':2048}.get(row, 4095)),
                              middle_aliases_final='0', event_hits='1', successful=str(counts[0]), readbacks=str(counts[1]), recoveries=str(counts[2]))
                render = lambda f: 'T5_TARGET_PASS '+' '.join(k+'='+v for k, v in f.items())+'\n'
                self.assertEqual(recipes.check_aw16_footer(render(fields), argv), fields)
                for key in fields:
                    changed = dict(fields); changed[key] = 'wrong'
                    with self.assertRaises(ValueError): recipes.check_aw16_footer(render(changed), argv)
                with self.assertRaises(ValueError): recipes.check_aw16_footer(render(fields)*2, argv)

    def test_balanced_integer_oracle_matches_independent_small_n_arithmetic(self):
        rng = random.Random(7142)
        for n in (1, 2, 4, 8, 32, 64, 128):
            for base in (7, 257, 604832956):
                for digits in ([-1]+[0]*(n-1), [0]*n, [base-1]*n, [rng.randrange(base) for _ in range(n)]):
                    for bit in (0, 1):
                        self.assertEqual(recipes.integer_square(digits, base, bit), old_vectors.square(digits, base, bit))
        self.assertEqual(recipes.integer_square([2], 4), [-1])
        self.assertEqual(recipes.target_vectors(5), old_vectors.target_vectors(5))
        self.assertEqual(hashlib.sha256(recipes.target_vectors(5).encode()).hexdigest(), frozen.TARGET_VECTOR_SHA)

    def test_source_closure_preserves_frozen_ancestry(self):
        old, pins = gate.source_pins(ROOT)
        for name, digest in old.source_pins(ROOT).items(): self.assertEqual(pins[name], digest)
        self.assertEqual(gate.sha(ROOT/gate.OLD), gate.OLD_SHA)
        self.assertEqual(gate.sha(ROOT/gate.AW16_RUNNER), gate.AW16_RUNNER_SHA)
        self.assertEqual(pins[gate.AW16_REPORT], gate.AW16_SHA)

    def test_aw16_passed_normal_replays_from_collected_artifacts(self):
        path = (ROOT/gate.AW16_REPORT).resolve()
        with patch.object(gate, 'AW16_NORMAL', path):
            report = gate.aw16_prerequisite(ROOT, path, baseline)
        self.assertEqual(len(report['metrics']), 12)

    def test_native_caps_and_receipt_binding(self):
        source = (ROOT/gate.RUNNER).read_text()
        for token in ('socket.gethostname() == \'aethia\'', 'resource.RLIMIT_CORE', 'resource.RLIMIT_AS',
                      'len({tuple(x) for x in limits[\'physical_cores\']}) == 2', 'PYTHONPATH=str(root)',
                      "CCACHE_DISABLE='1'", 'fcntl.LOCK_EX | fcntl.LOCK_NB', 'time.monotonic()+1800',
                      'command_timeout_seconds=1800', '10*GIB', '2*GIB', '4*GIB',
                      "status='failed_or_incomplete'", "report['status'] = passed_status", 'probe_sha256',
                      'control_build=', 'mutant_build', 'vector_sha256', 'compiled_source_sha256'):
            self.assertIn(token, source)
        self.assertIn("run('integer-oracle'", source)
        self.assertIn('sys.dont_write_bytecode = True', source)
        self.assertNotIn('shutil.rmtree', source)


if __name__ == '__main__': unittest.main()
