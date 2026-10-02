import json
from pathlib import Path
import tempfile
import unittest
from fpga.reference import track_a4_ntt_sequencer_prepare_v1 as p


class SequencerPreparationTests(unittest.TestCase):
    def test_exact_source_closed_small_profile(self):
        pins,guard=p.source_pins();m=p.manifest(pins)
        self.assertEqual(m['build']['parameters'],dict(AW=5))
        self.assertEqual(len(m['build']['sv_sources']),10)
        self.assertEqual(m['probe']['expected_json'],dict(context_threads=1,model_threads=1,expected_threads=1))
        self.assertEqual(m['steps'][1]['expected_returncode'],1)
        self.assertEqual(m['steps'][1]['expected_stderr'],p.NEGATIVE)
        self.assertEqual(guard['phases'][4]['op'],2)
        self.assertTrue(all('post_ntt' not in name and 'crt3' not in name and 'carry' not in name for name in p.SV))

    def test_fresh_preparation_has_exact_file_closure_and_retains_sources(self):
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder)/'stage';result=p.prepare(out)
            self.assertEqual(result['status'],'prepared_early_exploratory_sequencer_not_executed')
            self.assertEqual(json.loads((out/'aw5-manifest.json').read_text()),p.manifest(result['sources']))
            source=out/'source/fpga'
            actual={str(path.relative_to(source)):p.sha(path) for path in source.rglob('*') if path.is_file()}
            self.assertEqual(actual,result['sources'])
            with self.assertRaisesRegex(ValueError,'fresh'):
                p.prepare(out)

    def test_schoolbook_native_bound_and_exploratory_counts(self):
        n=32;prime=104857601
        self.assertLess(n*(prime-1)**2,1<<59)
        self.assertEqual(3*(3*(n+3*n)+3*n),1440)
        source=(p.ROOT/p.CPP).read_text()
        for token in ('A4_SEQ_AW==5','coefficients[(i+j)%N]','i+j<N?product:-product',
                      'A4_SEQ_FROZEN_NTT_METRICS','A4_SEQ_PROFILE_CANCEL',
                      'A4_SEQ_START_BLOCK_REJECT','A4_SEQ_WORD_MISMATCH'):
            self.assertIn(token,source)


if __name__=='__main__':unittest.main()
