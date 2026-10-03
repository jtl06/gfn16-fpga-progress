"""Own R14-F metadata regressions; no native/oracle execution or old result credit."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from fpga.tools import native_long_class_v2 as runtime
ROOT=Path(__file__).resolve().parents[1]


class R14FHostOffloadLongTests(unittest.TestCase):
    """Actual metadata/capture checks only; no R14F import or full-N arithmetic."""
    BASE=ROOT/'results/throughput-20260929/trackS-r14f-host-offload-ownlong-v1'
    FULL=BASE/'continuous1000-source-v1'
    NATIVE=ROOT/'queue/evidence/s4-r14f-host-offload-own100-q1-v1'

    def paths(self):
        raw=self.NATIVE/'attempt-0/collected/output/native'
        return dict(forecast=self.FULL/'own-pilot-forecast.json',pilot_manifest=raw/'approved-manifest.json',
            pilot_report=raw/'report.json',pilot_gate=self.NATIVE/'gate-receipt.json')

    def fixture(self):
        paths=self.paths()
        return (json.loads((self.FULL/'manifest.json').read_bytes()),
            {k:json.loads(p.read_bytes()) for k,p in paths.items()},
            {k:hashlib.sha256(p.read_bytes()).hexdigest() for k,p in paths.items()})

    def test_actual_own_r14f_serial_full_command_forecast_and_no_parent_calendar(self):
        m,v,p=self.fixture();got=runtime.duration_for(1).assess(m,v,p,'gfn16-pilot-c4d')
        self.assertEqual(got['status'],'PASS_R14F_own_measured_finite_duration_only')
        self.assertAlmostEqual(got['model_seconds_estimate'],2741.1063617352193)
        self.assertAlmostEqual(got['overall_seconds_estimate'],3672.104420026444)
        self.assertEqual(got['model_step'],runtime.R14F_FULL_STEP)
        self.assertFalse(got['promotion_allowed']);self.assertFalse(got['FPGA_throughput_or_clock_claim'])
        self.assertTrue(got['host_phase_excluded_from_FPGA'])
        self.assertEqual(runtime.model_threads(m),1)
        for count in (4,8):
            with self.subTest(count=count),self.assertRaises(ValueError):
                runtime.duration_for(count).assess(m,v,p,'gfn16-pilot-c4d')
        # All private numeric/validator source pins remain functional identity.
        self.assertNotIn(runtime.R14F_HELPER,runtime.PINS)
        self.assertNotIn(runtime.R14F_VALIDATOR,runtime.PINS)

    def test_exact_scalar_header_prefix_native_runtime_and_reference_closure(self):
        m,v,p=self.fixture();pilot=self.BASE/'own100-v1/source/fpga';full=self.FULL/'source/fpga'
        for count,source,key in ((100,pilot,'pilot_sha256'),(1000,full,'full_sha256')):
            self.assertEqual((source/runtime.C2_HEADER).read_bytes(),runtime.r14f_header(count))
            self.assertEqual(hashlib.sha256(runtime.r14f_header(count)).hexdigest(),runtime.R14F_HEADER_DELTA[key])
        self.assertEqual([row[:100] for row in runtime.r14f_bits(1000)],runtime.r14f_bits(100))
        self.assertEqual(sum(map(sum,runtime.r14f_bits(1000))),1022)
        self.assertEqual(len(m['build']['sv_sources']),66)
        self.assertTrue(all(hashlib.sha256((full/name).read_bytes()).hexdigest()==pin for name,pin in m['sources'].items()))
        cpp=(full/runtime.R14F_CPP).read_text()
        self.assertLess(cpp.index('gfn16_runtime::configure(context,argc,argv)'),cpp.index('DUT d(&context)'))
        for marker in ('R14F_LONG_EVERY_EDGE_CALENDAR','R14F_LONG_RAW_DONE_W_PLUS_TWO',
                       'R14F_LONG_RAW_OWNER_ORDER','R14F_LONG_ALL_N_REFERENCE','R14F_LONG_FINITE_NO_RELOAD'):
            self.assertIn(marker,cpp)
        self.assertEqual(hashlib.sha256((full/runtime.R14F_CPP).read_bytes()).hexdigest(),runtime.R14F_CPP_PIN)

    def test_one_actual_prediction_ast_without_private_candidate_import(self):
        m,v,p=self.fixture();original=runtime.importlib.util.spec_from_file_location
        def framework_only(name,path,*args,**kwargs):
            self.assertNotIn(Path(path).name,(Path(runtime.R14F_HELPER).name,Path(runtime.R14F_VALIDATOR).name))
            return original(name,path,*args,**kwargs)
        with patch.object(runtime.importlib.util,'spec_from_file_location',side_effect=framework_only):
            predict=runtime.r14f_predictor();got=runtime.assess(m,v,p,'gfn16-pilot-c4d')
            self.assertEqual(predict(156.63464924201253,345.7763968369982),v['forecast']['forecast'])
            self.assertEqual(got['shape']['outer_seconds'],10800)
        for count in (True,1,99,1001):
            with self.subTest(count=count),self.assertRaises(ValueError):runtime.r14f_config(count)

    def test_wrong_source_parent_ledger_words_scope_and_measurements_refuse(self):
        base,values,pins=self.fixture()
        changes=[('m',('sources',runtime.R14F_CPP),'0'*64),
            ('m',('sources',runtime.R14F_HELPER),'0'*64),('m',('sources',runtime.R14F_VALIDATOR),'0'*64),
            ('m',('sources',runtime.C2_HEADER),runtime.R14F_HEADER_DELTA['pilot_sha256']),
            ('m',('build','parameters','HOST_OFFLOAD'),0),('m',('build','parameters','HOST_OFFLOAD'),True),
            ('m',('build','parameters','LEAN_PRODUCTION'),1),('m',('build','runtime_threads'),8),
            ('m',('probe','expected_json','context_threads'),8),('m',('fixed_execution',),{}),
            ('m',('r14f_own_long','no_reload'),False),('m',('r14f_own_long','raw_done_warm_plus'),655360),
            ('m',('r14f_own_long','host_C_cold_final'),False),('m',('r14f_own_long','initial_resets'),2),
            ('m',('r14f_own_long','count_per_context'),100),('m',('steps',0,'validator','config','count'),100),
            ('m',('steps',0,'validator','config','first'),[204,4435]),
            ('m',('steps',0,'argv'),['{exe}','1000']),('m',('test_role',),'deliberate_fault'),
            ('v',('forecast','schema'),runtime.C2_SCHEMA),('v',('forecast','generator_sha256'),'0'*64),
            ('v',('forecast','FPGA_throughput_or_clock_claim'),True),('v',('forecast','parent_forecast_inherited'),True),
            ('v',('forecast','forecast','measured_command_seconds'),1),
            ('v',('forecast','forecast','overall_seconds_estimate'),1),
            ('v',('pilot_manifest','sources',runtime.C2_HEADER),'0'*64),
            ('v',('pilot_gate','steps',0,'typed_validator_sha256'),'0'*64),
            ('v',('pilot_gate','status'),'FAIL'),('v',('pilot_report','seconds'),float('inf')),
            ('v',('pilot_report','model_threads'),8),('v',('pilot_report','compile_workers'),4),
            ('v',('pilot_report','host'),'gfn16-azure-sim-f32'),
            ('v',('pilot_report','limits','cpu_max'),['800000','100000']),
            ('v',('pilot_report','limits','swap_max_bytes'),1),
            ('p',('pilot_report',),'0'*64)]
        for label,path,value in changes:
            m,v,p=copy.deepcopy((base,values,pins));target={'m':m,'v':v,'p':p}[label]
            for name in path[:-1]:target=target[name]
            target[path[-1]]=value
            with self.subTest(path=path),self.assertRaises((ValueError,KeyError)):
                runtime.assess(m,v,p,'gfn16-pilot-c4d')
        # Mutate all copies together: shape/source/typed calendar guards still reject.
        for key,value in (('checked_words',65536),('done_edges',[1509768,2169232]),
                          ('cycles',2235167),('input_words',131072),('initial_resets',2),
                          ('raw_words',262144),('model_seconds',float('nan'))):
            m,v,p=copy.deepcopy((base,values,pins))
            for native in (v['forecast']['pilot_native_validation'],v['pilot_gate']['steps'][0]['validation'],
                           v['pilot_report']['validations'][runtime.R14F_PILOT_STEP]):
                native['measurements'][key]=value
            with self.subTest(measurement=key),self.assertRaises(ValueError):runtime.assess(m,v,p,'gfn16-pilot-c4d')

    def test_actual_bind_dual_safe_stage_and_same_functional_identity(self):
        from fpga.tools import native_long_package_v3 as package,native_long_stage_v3 as stage
        from fpga.tools import native_profile_variants_v14 as checker
        from fpga.tools.candidate_ladder import budget_from_hourly
        original=(self.FULL/'manifest.json').read_bytes()
        with tempfile.TemporaryDirectory(prefix='r14f-long-metadata-') as temporary:
            out=Path(temporary).resolve();bound=out/'bound'
            result=package.bind_role(self.FULL/'manifest.json',self.FULL/'source/fpga',self.paths(),bound,host='gfn16-pilot-c4d')
            self.assertEqual(result['admission']['status'],'PASS_R14F_own_measured_finite_duration_only')
            budget=out/'budget.json';budget.write_text(json.dumps(budget_from_hourly()));fingerprints=[]
            for profile in ('gcp-c4d-static01-v1','gcp-c4d-static23-v1'):
                dest=out/profile
                prepared=package.prepare(bound/'manifest.json',bound/'source/fpga',profile,'metadata-r14f-'+profile,'run',dest,budget)
                _,ticket,manifest,_=stage.worker().inspect_archive(dest/'package.tar.gz',prepared['archive_sha256'],prepared['ticket_sha256'])
                runtime.duration.validate(manifest,dest/'capture/source/fpga','gfn16-pilot-c4d')
                fingerprint=checker.functional_fingerprint(manifest,ticket['budget'],dest/'capture/source/fpga')
                fingerprints.append(fingerprint['sha256'])
                self.assertNotIn(runtime.R14F_HELPER,fingerprint['ignored_exact_controls'])
                self.assertEqual(ticket['max_seconds'],10800)
                self.assertEqual(manifest['build']['runtime_threads'],1)
                self.assertEqual(manifest['steps'][0]['validator']['config']['count'],1000)
                self.assertEqual(len(manifest['build']['sv_sources']),66)
            self.assertEqual(fingerprints[0],fingerprints[1])
        self.assertEqual((self.FULL/'manifest.json').read_bytes(),original)

    def test_old_r14_capture_is_retained_without_r14f_workspace_substitution(self):
        from fpga.tools import native_profile_variants_v14 as checker
        self.assertIn(checker.PRE_R14F_LONG,checker.LONG_FAMILIES)
        self.assertEqual(checker.LONG_PHASES[checker.PRE_R14F_LONG],runtime.PHASE_PIN)
        for folder in ('trackS-r14-host-offload-ownlong-v1',):
            base=ROOT/'results/throughput-20260929'/folder/'continuous1000-packet-v1'
            fingerprints=[]
            for name in ('packet-01','packet-23'):
                path=base/name;m=json.loads((path/'manifest.json').read_bytes());t=json.loads((path/'ticket.json').read_bytes())
                family=tuple(m['sources'][k] for k in ('tools/native_long_class_v2.py','tools/native_long_package_v3.py'))
                self.assertEqual(family,checker.PRE_R14F_LONG)
                fingerprints.append(checker.functional_fingerprint(m,t['budget'],path/'capture/source/fpga')['sha256'])
            self.assertEqual(fingerprints[0],fingerprints[1])


if __name__=='__main__':unittest.main()
