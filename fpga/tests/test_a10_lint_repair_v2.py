import hashlib
import json
from pathlib import Path
import re
import tempfile
import unittest

from fpga.reference import a10_banked_engine_generate_v1 as gen
from fpga.reference import a10_lint_repair_v2 as repair
from fpga.reference import a10_packed_root_lookup_v1 as lookup


class A10ObservedLintRepairTests(unittest.TestCase):
    def test_counter_only_delta_and_drift_rejection(self):
        source = (repair.ROOT / repair.ENGINE_V1).read_text()
        result = repair.engine_source(source)
        self.assertEqual(result.replace("stage_root_count<=32'(1<<",
                                        "stage_root_count<=KW'(1<<"), source)
        with self.assertRaisesRegex(ValueError, 'FROZEN_ENGINE'):
            repair.engine_source(source + '\n')
        for aw in range(1, 17):
            for stage in range(aw):
                value = 1 << max(0, min(aw, 7) - stage - 1)
                self.assertLessEqual(value, 64)
                self.assertEqual(value, value & 127)

    def test_route_graph_and_root_words_unchanged(self):
        for aw in (5, 8):
            binding = gen.lookup_binding(1 << aw, 64)
            original = '\n'.join(x['source'] for x in binding['compiled']) + '\n' + binding['source']
            source = repair.repair_lookup(original, aw)
            constants = r"(?:assign \w+_q|\w+_rom\[\d+\])=\d+'h[0-9a-f]+;"
            self.assertEqual(re.findall(constants, original), re.findall(constants, source))
            self.assertEqual(re.findall(r' always_ff.*|.*<=.*', original.replace('selected_stage_roots[stage_q]',
                f"selected_stage_roots[{(aw-1).bit_length()}'(stage_q)]")),
                re.findall(r' always_ff.*|.*<=.*', source))
            for stage, level, refs in re.findall(r'assign s(\d+)_route_d(\d+)\[\d+\]=(.*);', source):
                for upstream in re.findall(r's\d+_route_d(\d+)\[', refs):
                    self.assertEqual(int(upstream), int(level) - 1)
            with self.assertRaisesRegex(ValueError, 'THREE_FIELD_ROUTES'):
                repair.repair_lookup(original.replace('wire [26:0]', 'wire [25:0]', 1), aw)
            # Exact admitted stage indices fit the narrow selector; malformed
            # 5-bit stages are rejected before any valid_q admission in v1/v2.
            self.assertIn(f"wire bad=stage>=5'd{aw}", source)
            self.assertIn('accept=request_valid && request_ready && !bad', source)
            for stage in range(aw):
                self.assertEqual(stage, stage & ((1 << (aw-1).bit_length()) - 1))

    def test_closed_packet_originals_untouched(self):
        donor = repair.ROOT / 'results/throughput-20260929/a10-banked-aw5-stage-v1/engine-f0'
        before = (donor / 'manifest.json').read_bytes()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'repair'
            result = repair.prepare(donor / 'manifest.json', donor / 'source/fpga', out)
            manifest = json.loads((out / 'manifest.json').read_text())
            self.assertFalse(result['promotion_allowed'])
            self.assertNotIn(repair.ENGINE_V1, manifest['build']['sv_sources'])
            self.assertIn(repair.ENGINE_V2, manifest['build']['sv_sources'])
            original = json.loads(before)
            for name, pin in original['sources'].items():
                self.assertEqual(hashlib.sha256((out / 'source/fpga' / name).read_bytes()).hexdigest(), pin)
            self.assertEqual(manifest['build']['top'], original['build']['top'])
            self.assertEqual(manifest['steps'], original['steps'])
            self.assertNotIn('lint_baseline', manifest)
            with self.assertRaisesRegex(ValueError, 'FRESH_OUTPUT'):
                repair.prepare(donor / 'manifest.json', donor / 'source/fpga', out)
        self.assertEqual(before, (donor / 'manifest.json').read_bytes())
