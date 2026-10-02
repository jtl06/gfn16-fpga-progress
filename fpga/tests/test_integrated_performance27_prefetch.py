"""Synthetic full-size/fit fixtures only: never publish these as performance data."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from synthesis.compare_integrated import compare
from synthesis.integrated_performance import estimate, _validate_atomic27
from synthesis.prepare import (prepare, CORE27_PREFETCH_PARAMETERS,
    CORE27_PREFETCH_SOURCES, CORE27_PREFETCH_PORTS)
from reference.square_core27_stream_prefetch_normalize import expected_config
from tests.test_integrated_performance27_stream import Stream27PerformanceTests


class PrefetchPerformanceTests(unittest.TestCase):
    def fixture(self):
        p,r,_=Stream27PerformanceTests().fixture(64)
        p['manifest'].update(target='square_core27_stream_prefetch_ntt64_carry16',
            top='genefer_square_core27_stream_prefetch',
            arithmetic_profile='atomic27_stream_precision_prefetch_v1')
        p['manifest']['source_sha256']={n:'e'*64 for n in CORE27_PREFETCH_SOURCES}
        r['sources']={'rtl/kernel/'+n:h for n,h in p['manifest']['source_sha256'].items()}
        r['configuration']=expected_config(64)
        r['fixture_kind']='SYNTHETIC FULL-SIZE COUNTERS, NOT MEASURED PREFETCH EVIDENCE'
        r['metrics']=[x for x in r['metrics'] if x['n']==65536 and x['base']==604832956
                      and x['case'].startswith('full-random-')]
        for x in r['metrics']:
            warm=x['root_cache_warm']
            for key in ('cache_before','root_cache_warm','root_loads','root_hits'):del x[key]
            x.update(profile_before=int(warm),profile_cache_warm=warm,
                profile_loads=int(not warm),profile_hits=int(warm),
                profile_words=0 if warm else 8738,roots=0 if warm else 8743,
                seed_setup=500,passes=2,ntt=25000)
            x['cycles']=sum(x[k] for k in ('conversion','roots','ntt','crt','carry'))
        return p,r,copy.deepcopy(r['metrics'])

    def test_exact_source_closure_and_real_top_ports(self):
        from reference.square_core27_stream_prefetch_regression import NAMES
        self.assertEqual(CORE27_PREFETCH_PARAMETERS,
            {'square_core27_stream_prefetch_ntt64_carry16':{'NTT_LANES':64}})
        self.assertEqual(CORE27_PREFETCH_SOURCES,[n+'.sv' for n in NAMES])
        self.assertEqual(len(set(CORE27_PREFETCH_SOURCES)),16)
        self.assertNotIn('root_cache_valid[*]',CORE27_PREFETCH_PORTS)
        for pin in ('profile_cache_valid','profile_loads','profile_hits',
                    'profile_words_loaded[*]','seed_setup_cycles[*]'):
            self.assertIn(pin,CORE27_PREFETCH_PORTS)
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'probe'
            m=prepare(path,'square_core27_stream_prefetch_ntt64_carry16',aw=16,processors=4)
            self.assertEqual(m['arithmetic_profile'],'atomic27_stream_precision_prefetch_v1')
            self.assertEqual(set(m['source_sha256']),set(CORE27_PREFETCH_SOURCES))
            qsf=(path/'probe.qsf').read_text()
            self.assertIn('VERILOG_CONSTANT_LOOP_LIMIT 10000\n',qsf)
            self.assertNotIn('root_cache_valid',qsf)
            self.assertFalse(m['bitstream_generation'])

    def test_synthetic_amortization_counts_seed_work_once(self):
        p,r,s=self.fixture();out=estimate(p,r,s,100)
        c=out['cached_chain_projection'];warm=max(x['cycles'] for x in s if x['profile_before'])
        self.assertEqual(c['cache_kind'],'compact_profile_bundle')
        self.assertEqual(c['total_cycles'],8743+warm*out['exponent_bits'])
        self.assertIn('seed setup remains included',c['assumption'])

    def test_archived_small_report_matches_profile_but_cannot_support_full_size_estimate(self):
        path=Path(__file__).resolve().parents[1]/'results/throughput-20260929/core27-stream-prefetch-small-v1/normalized-report.json'
        r=json.loads(path.read_text());p,_,_=self.fixture()
        p['manifest']['source_sha256']={n:r['sources']['rtl/kernel/'+n] for n in CORE27_PREFETCH_SOURCES}
        self.assertEqual(_validate_atomic27(p['manifest'],r),{'PROFILE_CACHE':1})
        with self.assertRaises(ValueError):estimate(p,r,r['metrics'][:1],100)

    def test_profile_counters_cannot_be_relabelled_or_truncated(self):
        for key,value in (('profile_before',15),('profile_before',False),
                          ('profile_cache_warm',1),('profile_loads',4),('profile_hits',4),
                          ('profile_words',8737),('seed_setup',25001),('seed_setup',False),
                          ('passes',1),('root_cache_warm',False)):
            p,r,s=self.fixture();r['metrics'][0][key]=value
            with self.subTest(key=key,value=value),self.assertRaises(ValueError):estimate(p,r,s,100)
        for delta in (-1,1):
            p,r,s=self.fixture()
            for x in (r['metrics'][0],s[0]):x['roots']+=delta;x['cycles']+=delta
            with self.assertRaisesRegex(ValueError,'counter mismatch'):estimate(p,r,s,100)

    def test_selected_metadata_must_match_measured_profile(self):
        for key,value in (('profile_before',1),('profile_words',0),('seed_setup',499),
                          ('profile_cache_warm',True),('root_cache_warm',False)):
            p,r,s=self.fixture();s[0][key]=value
            with self.assertRaises(ValueError):estimate(p,r,s,100)
        p,r,s=self.fixture();s[1]['roots']=False
        with self.assertRaisesRegex(ValueError,'integer phase'):estimate(p,r,s,100)

    def comparison_fixture(self,directory):
        paths=[Path(directory)/n for n in ('cached','prefetch')]
        fixtures=[Stream27PerformanceTests().fixture(64),self.fixture()]
        probes=[];reports=[]
        for path,(p,r,_) in zip(paths,fixtures):
            m=prepare(path,p['manifest']['target'],aw=16,period=10,processors=4)
            p['manifest']=m;r['sources']={'rtl/kernel/'+n:h for n,h in m['source_sha256'].items()}
            (path/'output_files').mkdir()
            (path/'output_files/probe.fit.summary').write_text('Quartus Prime Version : SYNTHETIC-TEST-ONLY\n')
            probes.append(p);reports.append(r)
        return paths,probes,reports

    def test_comparison_audits_only_known_interface_and_elaboration_differences(self):
        with tempfile.TemporaryDirectory() as d:
            paths,probes,reports=self.comparison_fixture(d)
            with patch('synthesis.compare_integrated.read_probe',side_effect=probes):
                result=compare(*paths,*reports,100,100)
            self.assertEqual(len(result['declared_control_differences'][0]['assignments']),3)
            self.assertEqual(len(result['declared_control_differences'][1]['assignments']),6)
            self.assertIn('VERILOG_CONSTANT_LOOP_LIMIT 10000',
                          '\n'.join(result['declared_control_differences'][1]['assignments']))
            self.assertNotEqual(result['original_control_sha256']['baseline']['qsf_without_top_sources'],
                                result['original_control_sha256']['candidate']['qsf_without_top_sources'])
            qsf=paths[1]/'probe.qsf';original=qsf.read_text()
            for modified in (
                original.replace('SEED 1','SEED 2'),
                original.replace('NUM_PARALLEL_PROCESSORS 4','NUM_PARALLEL_PROCESSORS 8'),
                original.replace('VERILOG_CONSTANT_LOOP_LIMIT 10000','VERILOG_CONSTANT_LOOP_LIMIT 20000'),
                original.replace('VIRTUAL_PIN ON -to {profile_loads}','VIRTUAL_PIN OFF -to {profile_loads}'),
                original+'set_instance_assignment -name VIRTUAL_PIN ON -to {profile_hits}\n',
                original+'set_global_assignment -name OPTIMIZATION_MODE HIGH PERFORMANCE EFFORT\n'):
                qsf.write_text(modified)
                with patch('synthesis.compare_integrated.read_probe',side_effect=probes):
                    with self.assertRaisesRegex(ValueError,'physical control'):compare(*paths,*reports,100,100)
            qsf.write_text(original)
            sdc=paths[1]/'probe.sdc';sdc.write_text(sdc.read_text()+'set_false_path -to [all_registers]\n')
            with patch('synthesis.compare_integrated.read_probe',side_effect=probes):
                with self.assertRaisesRegex(ValueError,'physical control'):compare(*paths,*reports,100,100)

    def test_comparison_matches_semantic_cache_state_without_equating_counter_encodings(self):
        with tempfile.TemporaryDirectory() as d:
            paths,probes,reports=self.comparison_fixture(d)
            rows=reports[1]['metrics'];cold,warm=rows[0],rows[1]
            cold['case'],warm['case']=warm['case'],cold['case']
            with patch('synthesis.compare_integrated.read_probe',side_effect=probes):
                with self.assertRaisesRegex(ValueError,'cache residency'):compare(*paths,*reports,100,100)

    def test_source_basis_and_architecture_remain_strict(self):
        for mode in ('missing','extra','mismatch','old_top','old_profile','old_config'):
            p,r,s=self.fixture()
            if mode=='missing':del p['manifest']['source_sha256']['genefer_root_profile27_rom.sv']
            elif mode=='extra':r['sources']['rtl/kernel/genefer_montgomery_mul32_pipe.sv']='e'*64
            elif mode=='mismatch':r['sources']['rtl/kernel/genefer_root_profile27_rom.sv']='f'*64
            elif mode=='old_top':p['manifest']['top']='genefer_square_core27_stream'
            elif mode=='old_profile':p['manifest']['arithmetic_profile']='atomic27_stream_precision_v1'
            else:r['configuration']['root_cache']=True
            with self.subTest(mode=mode),self.assertRaises(ValueError):estimate(p,r,s,100)

    def test_absent_whole_fit_and_missing_warm_evidence_not_promoted(self):
        p,r,s=self.fixture();p['fit_success']=False
        with self.assertRaises(ValueError):estimate(p,r,s,100)
        p,r,s=self.fixture();p['hold_slack_ns']=-.001
        with self.assertRaises(ValueError):estimate(p,r,s,100)
        p,r,s=self.fixture()
        with self.assertRaises(ValueError):estimate(p,r,s,1000)
        self.assertIsNone(estimate(p,r,s[:1],100)['cached_chain_projection'])


if __name__=='__main__':unittest.main()
