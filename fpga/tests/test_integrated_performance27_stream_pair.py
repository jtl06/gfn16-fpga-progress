"""SYNTHETIC fit fixtures only. No fit is launched or physical result emitted."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from synthesis.compare_integrated import compare
from synthesis.integrated_performance import estimate
from synthesis.prepare import prepare, CORE27_STREAM_PAIR_SOURCES, CORE27_STREAM_PAIR_PARAMETERS
from tests import test_integrated_performance27 as baseline_tests
from tests import test_integrated_performance27_stream as stream_tests
from tests import test_integrated_performance27_folded as folded_tests


PAIR_SOURCES = {
    'genefer_montgomery_mul32_pipe.sv', 'genefer_montgomery_mul27_sparse_pipe.sv',
    'genefer_digit_reduce27_pipe.sv', 'genefer_sdp_ram32.sv',
    'genefer_ntt_banked27_engine.sv', 'genefer_ntt_banked27_host_engine.sv',
    'genefer_mod27_pair_pipe.sv', 'genefer_crt3_27_pair_pipe.sv',
    'genefer_sp_ram.sv', 'genefer_div_recip_narrow.sv',
    'genefer_carry_prefix_stream_pipe.sv', 'genefer_div_recip_precision.sv',
    'genefer_carry_prefix_stream_precision.sv', 'genefer_square_core27_stream_pair.sv',
}


class PairStream27PerformanceTests(unittest.TestCase):
    def fixture(self,lanes=64):
        p,r,_=stream_tests.Stream27PerformanceTests().fixture(lanes)
        p['manifest'].update(target=f'square_core27_stream_pair_ntt{lanes}_carry16',
            top='genefer_square_core27_stream_pair',arithmetic_profile='atomic27_stream_precision_pair_v1')
        p['manifest']['source_sha256']={name:'d'*64 for name in PAIR_SOURCES}
        r['sources']={'rtl/kernel/'+name:h for name,h in p['manifest']['source_sha256'].items()}
        r['configuration'].update(pair_crt=True,crt_latency=96,
            field_profile='sparse27-cached-stream-precision-pair-radix32-v1')
        # Synthetic phase counts test the contract, NOT new performance data.
        # Preserve the fixture's other counters; give pair CRT its fixed full-N
        # drain and recalculate total so old latency cannot slip through.
        for row in r['metrics']:
            if row['n']==65536:
                row['cycles']+=4193-row['crt'];row['crt']=4193
        samples=[copy.deepcopy(row) for row in r['metrics'] if row['n']==65536
                 and row['base']==604832956 and row['case'].startswith('full-random-')]
        return p,r,samples

    def test_only_known_profiles_and_exact_fourteen_sources_are_prepared(self):
        self.assertEqual(set(CORE27_STREAM_PAIR_PARAMETERS),{
            f'square_core27_stream_pair_ntt{n}_carry16' for n in (16,64)})
        self.assertEqual(set(CORE27_STREAM_PAIR_SOURCES),PAIR_SOURCES)
        self.assertEqual(len(CORE27_STREAM_PAIR_SOURCES),14)
        with tempfile.TemporaryDirectory() as directory:
            for lanes in (16,64):
                p,r,s=self.fixture(lanes)
                self.assertEqual(estimate(p,r,s,100)['arithmetic_profile'],'atomic27_stream_precision_pair_v1')
                path=Path(directory)/str(lanes)
                m=prepare(path,p['manifest']['target'],aw=16,processors=4)
                for key in ('target','top','core_parameters','arithmetic_profile',
                            'core_field_basis','core_montgomery_radix_bits'):
                    self.assertEqual(m[key],p['manifest'][key])
                self.assertEqual(set(m['source_sha256']),PAIR_SOURCES)
                qsf=(path/'probe.qsf').read_text()
                self.assertEqual([line for line in qsf.splitlines() if line.startswith('set_parameter')],
                    ['set_parameter -name AW 16',f'set_parameter -name NTT_LANES {lanes}'])
                self.assertIn('NUM_PARALLEL_PROCESSORS 4',qsf)
                self.assertFalse(m['bitstream_generation'])
                self.assertNotIn('-tool asm',(path/'run.tcl').read_text())

    def test_archived_pair_simulation_matches_synthetic_fit_contract(self):
        # Real simulation metadata, but the probe/Fmax remains explicitly
        # synthetic. Never serialize this calculated test-only projection.
        path=Path(__file__).resolve().parents[1]/'results/throughput-20260929/core27-stream-pair-full64/normalized-report.json'
        r=json.loads(path.read_text());p,_,_=self.fixture(64)
        p['manifest']['source_sha256']={name:r['sources']['rtl/kernel/'+name] for name in PAIR_SOURCES}
        samples=[copy.deepcopy(row) for row in r['metrics'] if row['n']==65536
                 and row['base']==604832956 and row['case'].startswith('full-random-')]
        result=estimate(p,r,samples,100)
        self.assertEqual(result['cached_chain_projection']['warm_cycles_sample_max'],32188)
        self.assertEqual(result['cached_chain_projection']['cold_cycles_sample_max'],294340)
        with tempfile.TemporaryDirectory() as directory:
            manifest=prepare(Path(directory)/'snapshot',p['manifest']['target'],aw=16)
            self.assertEqual(manifest['source_sha256'],p['manifest']['source_sha256'])

    def test_predecessor_and_folded_evidence_cannot_be_borrowed(self):
        pair=self.fixture()
        for other in (baseline_tests.Atomic27PerformanceTests().fixture(),
                      stream_tests.Stream27PerformanceTests().fixture(),
                      folded_tests.Folded27PerformanceTests().fixture()):
            for p,r,s in ((pair[0],other[1],other[2]),(other[0],pair[1],pair[2])):
                with self.assertRaises(ValueError):estimate(p,r,s,100)

    def test_pair_flags_and_profile_are_exact_not_truthy(self):
        for key,value in (('pair_crt',False),('pair_crt',1),('crt_latency',61),
                          ('crt_latency',64),('crt_latency',96.0),('crt_latency','96'),
                          ('precision_carry',False),('stream_carry',False),
                          ('field_profile','sparse27-cached-stream-precision-radix32-v1'),
                          ('fuse_input_mont',True),('generated_roots',True)):
            p,r,s=self.fixture();r['configuration'][key]=value
            with self.subTest(key=key,value=value),self.assertRaises(ValueError):estimate(p,r,s,100)
        for key in ('pair_crt','crt_latency'):
            p,r,s=self.fixture();del r['configuration'][key]
            with self.assertRaises(ValueError):estimate(p,r,s,100)
        for key,value in (('top','genefer_square_core27_stream'),
                          ('arithmetic_profile','atomic27_stream_precision_v1')):
            p,r,s=self.fixture();p['manifest'][key]=value
            with self.assertRaises(ValueError):estimate(p,r,s,100)

    def test_complete_pair_source_identity_required_on_both_sides(self):
        for name in PAIR_SOURCES:
            for side in ('fit','simulation'):
                p,r,s=self.fixture()
                sources=p['manifest']['source_sha256'] if side=='fit' else r['sources']
                del sources[name if side=='fit' else 'rtl/kernel/'+name]
                with self.subTest(name=name,side=side),self.assertRaises(ValueError):estimate(p,r,s,100)
            p,r,s=self.fixture();r['sources']['rtl/kernel/'+name]='e'*64
            with self.assertRaises(ValueError):estimate(p,r,s,100)
        for old in ('genefer_crt3_27_pipe.sv','genefer_crt3_27_retimed_pipe.sv','genefer_crt3_pipe.sv'):
            p,r,s=self.fixture()
            del p['manifest']['source_sha256']['genefer_crt3_27_pair_pipe.sv']
            del r['sources']['rtl/kernel/genefer_crt3_27_pair_pipe.sv']
            p['manifest']['source_sha256'][old]='d'*64;r['sources']['rtl/kernel/'+old]='d'*64
            with self.assertRaises(ValueError):estimate(p,r,s,100)
        p,r,s=self.fixture();r['sources']['rtl/kernel/genefer_mod64_pipe.sv']='d'*64
        with self.assertRaises(ValueError):estimate(p,r,s,100)

    def test_old_crt_cycles_rejected_even_after_metadata_relabelling(self):
        for latency_delta in (35,32,1):
            p,r,s=self.fixture()
            for row in r['metrics']+s:
                if row['n']==65536:
                    row['crt']-=latency_delta;row['cycles']-=latency_delta
            with self.assertRaisesRegex(ValueError,'pair CRT measured latency'):estimate(p,r,s,100)
        p,r,s=self.fixture()
        with self.assertRaisesRegex(ValueError,'Fmax'):estimate(p,r,s,150)

    def test_comparator_accepts_independently_validated_pair_delta_only(self):
        with tempfile.TemporaryDirectory() as directory:
            paths=[Path(directory)/name for name in ('stream','pair')]
            fixtures=[stream_tests.Stream27PerformanceTests().fixture(),self.fixture()]
            probes=[];reports=[]
            for path,(p,r,_) in zip(paths,fixtures):
                m=prepare(path,p['manifest']['target'],aw=16,period=10,processors=4)
                p['manifest']=m;r['sources']={'rtl/kernel/'+k:v for k,v in m['source_sha256'].items()}
                (path/'output_files').mkdir()
                (path/'output_files/probe.fit.summary').write_text('Quartus Prime Version : SYNTHETIC-TEST-ONLY\n')
                probes.append(p);reports.append(r)
            with patch('synthesis.compare_integrated.read_probe',side_effect=probes):
                result=compare(*paths,*reports,100,100)
            self.assertEqual(result['planning_clock_ratio'],1)
            self.assertLess(result['projected_cached_chain_speedup'],1)
            self.assertEqual(result['phase_deltas']['full-random-s1-d1']['crt'],35)
            self.assertIn('genefer_crt3_27_pair_pipe.sv',result['changed_rtl'])
            reports[1]['configuration']['crt_latency']=61
            with patch('synthesis.compare_integrated.read_probe',side_effect=probes):
                with self.assertRaisesRegex(ValueError,'architecture/profile'):
                    compare(*paths,*reports,100,100)


if __name__=='__main__':unittest.main()
