"""Synthetic profile-validation fixtures; NOT physical folded-core evidence."""
import tempfile
import unittest
from pathlib import Path
from synthesis.prepare import prepare, CORE27_FOLDED_SOURCES
from synthesis.integrated_performance import estimate
from tests import test_integrated_performance27 as baseline_tests
from tests import test_integrated_performance27_stream as stream_tests


class Folded27PerformanceTests(unittest.TestCase):
    def fixture(self, lanes=64):
        p,r,s=baseline_tests.Atomic27PerformanceTests().fixture(lanes)
        p['manifest'].update(target=f'square_core27_folded_ntt{lanes}_carry16',
            top='genefer_square_core27_folded',arithmetic_profile='atomic27_cached_folded_v1')
        p['manifest']['source_sha256']={name:'c'*64 for name in CORE27_FOLDED_SOURCES}
        r['sources']={'rtl/kernel/'+name:h for name,h in p['manifest']['source_sha256'].items()}
        r['configuration'].update(ntt_routing='folded-root-v1',
            field_profile='sparse27-cached-folded-radix32-v1')
        # Baseline counts are deliberately synthetic placeholders here; no
        # result file is emitted and no physical throughput claim is made.
        return p,r,s

    def test_profile_matches_preparation_for_both_widths(self):
        with tempfile.TemporaryDirectory() as directory:
            for lanes in (16,64):
                p,r,s=self.fixture(lanes)
                result=estimate(p,r,s,100)
                self.assertEqual(result['arithmetic_profile'],'atomic27_cached_folded_v1')
                m=prepare(Path(directory)/str(lanes),p['manifest']['target'],aw=16)
                for key in ('target','top','core_parameters','arithmetic_profile',
                            'core_field_basis','core_montgomery_radix_bits'):
                    self.assertEqual(m[key],p['manifest'][key])
                self.assertEqual(set(m['source_sha256']),set(p['manifest']['source_sha256']))

    def test_cannot_mix_baseline_or_streaming_evidence(self):
        folded=self.fixture()
        for other in (baseline_tests.Atomic27PerformanceTests().fixture(),
                      stream_tests.Stream27PerformanceTests().fixture()):
            for p,r,s in ((folded[0],other[1],other[2]),(other[0],folded[1],folded[2])):
                with self.assertRaises(ValueError):estimate(p,r,s,100)

    def test_routing_and_architecture_flags_are_exact(self):
        for key,value in (('ntt_routing','native'),('ntt_routing',True),
                          ('field_profile','sparse27-cached-radix32-v1'),
                          ('stream_carry',True),('precision_carry',False),
                          ('fuse_input_mont',True),('generated_roots',True)):
            p,r,s=self.fixture();r['configuration'][key]=value
            with self.assertRaises(ValueError):estimate(p,r,s,100)
        p,r,s=self.fixture();del r['configuration']['ntt_routing']
        with self.assertRaises(ValueError):estimate(p,r,s,100)

    def test_complete_fourteen_source_identity_required(self):
        for name in CORE27_FOLDED_SOURCES:
            p,r,s=self.fixture();del p['manifest']['source_sha256'][name]
            with self.assertRaises(ValueError):estimate(p,r,s,100)
            p,r,s=self.fixture();r['sources']['rtl/kernel/'+name]='d'*64
            with self.assertRaises(ValueError):estimate(p,r,s,100)

    def test_clock_and_cycles_must_be_whole_core_measured(self):
        p,r,s=self.fixture()
        with self.assertRaises(ValueError):estimate(p,r,s,125)
        s[0]['ntt']+=35;s[0]['cycles']+=35
        with self.assertRaises(ValueError):estimate(p,r,s,100)
