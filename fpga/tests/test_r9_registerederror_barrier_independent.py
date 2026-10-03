import importlib.util
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
PATH=ROOT/'results/throughput-20260929/r9-registerederror-barrier-replay-independent-v1.py'
spec=importlib.util.spec_from_file_location('r9_scoped_review',PATH)
review=importlib.util.module_from_spec(spec)
spec.loader.exec_module(review)


class ScopedReviewControls(unittest.TestCase):
    def test_own_binary_source_equations(self):
        value=review.binary_checks()
        self.assertEqual(value['field_cases'],512)
        self.assertEqual(value['three_edge_fault_sequences'],4096)
        self.assertEqual(value['coherent_owner_count_drain_cases'],2048)
        self.assertEqual(value['proposal_drain_hazards'],16)
        self.assertFalse(value['arbitrary_XZ_equivalence'])

    def test_aggregation_exact_three_reversals_and_ancestors(self):
        for stage in ('aw8-normal','full-normal'):
            value=review.source_delta(stage)
            self.assertEqual(value['unchanged_literal_files'],51)
            self.assertEqual(value['aggregation_definitions_reversed'],3)
            self.assertFalse(value['authored_storage2_reviewed_here'])

    def test_actual_fixture_reverse_and_changed_origin_rejected(self):
        manifest=json.loads((ROOT/'results/throughput-20260929/trackS-c2-r9-barrier-native-v1/faults-v2/manifest.json').read_bytes())
        source=ROOT/'results/throughput-20260929/trackS-c2-r9-barrier-native-v1/faults-v2/source/fpga'
        for clone in manifest['r9_barrier_fixture']['diagnostic_clones']:
            raw=(source/('rtl/'+clone['diagnostic']+'.sv')).read_text()
            parent=(source/('rtl/'+clone['parent']+'.sv')).read_text()
            self.assertEqual(review.reverse(raw,clone['changes']),parent)
            before,after=clone['changes'][-1]
            with self.assertRaises(ValueError):
                review.reverse(raw.replace(after,after+' /* unintended new semantic */',1).replace(after,'BROKEN',1),clone['changes'])
            self.assertNotEqual(review.reverse(raw+'\n// unrecorded source delta\n',clone['changes']),parent)

    def test_handoff_pin_and_expected_negative_scope(self):
        handoff=review.load(review.HANDOFF,review.HANDOFF_PIN)
        self.assertFalse(handoff['promotion_allowed'])
        self.assertEqual(handoff['author'],'p16_independent_reviewer')
        for mode in ('normal','faults'):
            manifest=json.loads((ROOT/'results/throughput-20260929/trackS-c2-r9-barrier-native-v1'/(mode+'-v2')/'manifest.json').read_bytes())
            self.assertEqual(len(manifest['build']['sv_sources']),62)
            if mode=='faults':
                self.assertEqual(manifest['steps'][1]['expected_returncode'],1)
                self.assertEqual(manifest['steps'][1]['expected_stderr'],'R9_BARRIER_EXTERNAL_MASK\n')
        with self.assertRaises(ValueError):
            review.load(review.HANDOFF,'0'*64)


if __name__=='__main__':
    unittest.main()
