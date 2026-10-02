"""Synthetic test fixtures ONLY; no measured stream-core fit is asserted here."""
import tempfile
import unittest
from pathlib import Path
from synthesis.prepare import prepare, CORE27_STREAM_SOURCES
from synthesis.integrated_performance import estimate
from tests import test_integrated_performance27 as baseline_tests


class Stream27PerformanceTests(unittest.TestCase):
    def fixture(self, lanes=64):
        probe, regression, samples = baseline_tests.Atomic27PerformanceTests().fixture(lanes)
        # Reuse baseline cycle values solely to test evidence validation. These
        # are NOT predictions or measurements for the new stream candidate.
        m = probe['manifest']
        m.update(target=f'square_core27_stream_ntt{lanes}_carry16',
                 top='genefer_square_core27_stream', arithmetic_profile='atomic27_stream_precision_v1')
        m['source_sha256'] = {name:'a'*64 for name in CORE27_STREAM_SOURCES}
        regression['sources'] = {'rtl/kernel/'+name:h for name,h in m['source_sha256'].items()}
        regression['configuration'].update(stream_carry=True,precision_carry=True,
            field_profile='sparse27-cached-stream-precision-radix32-v1')
        return probe, regression, samples

    def test_exact_stream_profiles_accept_synthetic_evidence_only(self):
        with tempfile.TemporaryDirectory() as directory:
            for lanes in (16,64):
                p,r,s=self.fixture(lanes)
                result=estimate(p,r,s,100)
                self.assertEqual(result['arithmetic_profile'],'atomic27_stream_precision_v1')
                prepared=prepare(Path(directory)/str(lanes),p['manifest']['target'],aw=16)
                for key in ('target','top','core_parameters','arithmetic_profile',
                            'core_field_basis','core_montgomery_radix_bits'):
                    self.assertEqual(prepared[key],p['manifest'][key])
                self.assertEqual(set(prepared['source_sha256']),set(p['manifest']['source_sha256']))

    def test_old_fit_or_old_simulation_cannot_be_borrowed(self):
        old=baseline_tests.Atomic27PerformanceTests().fixture()
        stream=self.fixture()
        for p,r,s in ((old[0],stream[1],stream[2]),(stream[0],old[1],old[2])):
            with self.assertRaises(ValueError):estimate(p,r,s,100)

    def test_every_stream_identity_boundary_rejects(self):
        mutations=[('configuration','precision_carry',False),
                   ('configuration','precision_carry',1),
                   ('configuration','stream_carry',False),
                   ('configuration','fuse_input_mont',True),
                   ('configuration','generated_roots',True),
                   ('configuration','field_profile','sparse27-cached-radix32-v1'),
                   ('manifest','top','genefer_square_core27'),
                   ('manifest','arithmetic_profile','atomic27_cached_v1')]
        for section,key,value in mutations:
            p,r,s=self.fixture()
            (p[section] if section=='manifest' else r[section])[key]=value
            with self.assertRaises(ValueError):estimate(p,r,s,100)
        p,r,s=self.fixture();del r['configuration']['precision_carry']
        with self.assertRaises(ValueError):estimate(p,r,s,100)

    def test_stream_requires_its_entire_14_source_closure(self):
        for name in CORE27_STREAM_SOURCES:
            p,r,s=self.fixture();del p['manifest']['source_sha256'][name]
            with self.assertRaises(ValueError):estimate(p,r,s,100)
            p,r,s=self.fixture();r['sources']['rtl/kernel/'+name]='b'*64
            with self.assertRaises(ValueError):estimate(p,r,s,100)

    def test_unmeasured_overlap_cannot_reduce_cycle_estimate(self):
        p,r,s=self.fixture()
        s[0]['carry']-=4096;s[0]['cycles']-=4096
        with self.assertRaises(ValueError):estimate(p,r,s,100)

    def test_component_clock_does_not_replace_whole_core_clock(self):
        p,r,s=self.fixture()
        with self.assertRaises(ValueError):estimate(p,r,s,150)
        p['fit_success']=False
        with self.assertRaises(ValueError):estimate(p,r,s,100)
