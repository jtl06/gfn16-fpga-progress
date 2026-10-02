import copy
import json
from pathlib import Path
import tempfile
import unittest
from fpga.tools.prefit_structural_guard_v1 import evaluate,identities,file_digest,SCHEMA

class PrefitGuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        source='always_ff @(posedge clk) source_word<=payload;\nalways_ff @(posedge clk) destination_word<=source_word;\n'
        (self.root/'stage.sv').write_text(source);(self.root/'probe.sdc').write_text('create_clock -period 10 [get_ports clk]\n')
        (self.root/'probe.qsf').write_text('set_global_assignment -name TOP_LEVEL_ENTITY top\nset_global_assignment -name DEVICE GX1150\nset_global_assignment -name SEED 1\nset_global_assignment -name SDC_FILE probe.sdc\nset_global_assignment -name SYSTEMVERILOG_FILE stage.sv\n')
        stages=[dict(id=name,owner=owner,kind='flop',edge=edge,payload=[name],valid=['valid'],metadata=['tag'],source='stage.sv',anchors=[anchor],alignment='same_accepted_edge')
            for name,owner,edge,anchor in [('source_word','a',0,source.splitlines()[0]),('destination_word','b',1,source.splitlines()[1])]]
        self.spec=dict(schema=SCHEMA,scope='whole_core',identity=dict(top='top',device='GX1150',parameters={},clock_period_ns=10,seed=1),
            sources={'stage.sv':file_digest(self.root/'stage.sv')},settings={'probe.sdc':file_digest(self.root/'probe.sdc')},blocks=['a','b'],
            transfers=[dict(id='payload',producer='a',consumer='b',signals=['word','valid','tag'],registered_stages=stages,control_reconvergence=[dict(signal='guard',sink='enable',registered_barrier='destination_word')])],
            exclusions=[],coverage_claim='declared_source_inventory_not_netlist_completeness',vendor_helper_sha256='1'*64,vendor_tool_sha256={'quartus':'2'*64})
        self.spec['settings']['probe.qsf']=file_digest(self.root/'probe.qsf')
        manifest=dict(top='top',device='GX1150',clock_period_ns=10,seed=1,core_parameters={},source_sha256=self.spec['sources'],control_sha256=self.spec['settings'].copy())
        (self.root/'manifest.json').write_text(json.dumps(manifest))
        self.spec['settings']['manifest.json']=file_digest(self.root/'manifest.json')
        # Synthetic report fixtures exercise the checker, not vendor validation.
        (self.root/'vendor.txt').write_text('synthetic report fixture, no real vendor execution\n')
        self.vendor=dict(schema='quartus-prefit-evidence-v1',**identities(self.spec),helper_sha256='1'*64,tool_sha256={'quartus':'2'*64},phase='post_synthesis',raw_report_sha256={'vendor.txt':file_digest(self.root/'vendor.txt')},
            cross_block_coverage=dict(supported=True,complete=True,observed_crossings=['payload'],uncovered_endpoints=[],unjustified_findings=[]),
            design_assistant=dict(supported=True,complete=True,rules_checked=['fixture-rule'],high_severity_findings=[],new_high_severity_findings=[]))
        self.vendor['native_script_sha256']='4'*64
        context=dict(schema='quartus-prefit-execution-v1',platform='Linux',owner_admission_passed=True,returncode=0,
            **identities(self.spec),tool_sha256={'quartus':'2'*64},helper_sha256='1'*64,native_script_sha256='4'*64,
            source_before_sha256=self.spec['sources'],source_after_sha256=self.spec['sources'],settings_before_sha256=self.spec['settings'],settings_after_sha256=self.spec['settings'],
            raw_report_sha256=self.vendor['raw_report_sha256'].copy(),database_before_sha256={'fixture.qdb':'3'*64},database_after_sha256={'fixture.qdb':'3'*64})
        (self.root/'execution.json').write_text(json.dumps(context));pin=file_digest(self.root/'execution.json')
        self.vendor.update(native_execution_identity_verified=True,native_execution_context=dict(path='execution.json',sha256=pin))
        self.vendor['raw_report_sha256']['execution.json']=pin

    def test_missing_native_evidence_blocks(self):
        result=evaluate(self.root,self.spec)
        self.assertFalse(result['fit_allowed']);self.assertTrue(result['source_evidence_only'])

    def test_complete_synthetic_fixture_and_no_timing_claim(self):
        result=evaluate(self.root,self.spec,self.vendor)
        self.assertTrue(result['fit_allowed']);self.assertFalse(result['physical_timing_proven'])
        self.assertFalse(result['promotion_allowed'])

    def test_no_reg_endpoint_double_count_or_raw_reconvergence(self):
        for mutate in ('one_stage','duplicate_edge','raw_guard','source_anchor'):
            spec=copy.deepcopy(self.spec)
            if mutate=='one_stage':spec['transfers'][0]['registered_stages'].pop()
            if mutate=='duplicate_edge':spec['transfers'][0]['registered_stages'][1]['edge']=0
            if mutate=='raw_guard':spec['transfers'][0]['control_reconvergence'][0]['registered_barrier']=None
            if mutate=='source_anchor':spec['transfers'][0]['registered_stages'][0]['anchors']=['not actual source']
            if mutate in ('duplicate_edge','source_anchor'):
                with self.assertRaises(ValueError):evaluate(self.root,spec,self.vendor)
            else:self.assertFalse(evaluate(self.root,spec,self.vendor)['fit_allowed'])

    def test_unsupported_uncovered_new_high_findings_fail_closed(self):
        for mutate in ('unsupported','partial','uncovered','duplicate','high','unclassified','missing_fields','no_execution'):
            v=copy.deepcopy(self.vendor)
            if mutate=='unsupported':v['design_assistant']['supported']=False
            if mutate=='partial':v['cross_block_coverage']['complete']=False
            if mutate=='uncovered':v['cross_block_coverage']['uncovered_endpoints']=['RAMena']
            if mutate=='duplicate':v['cross_block_coverage']['observed_crossings']*=2
            if mutate=='high':v['design_assistant']['new_high_severity_findings']=['long_raw_control']
            if mutate=='unclassified':v['design_assistant']['high_severity_findings']=['unknown']
            if mutate=='missing_fields':del v['design_assistant']['new_high_severity_findings']
            if mutate=='no_execution':v['native_execution_identity_verified']=False
            if mutate=='missing_fields':
                with self.assertRaises(ValueError):evaluate(self.root,self.spec,v)
            else:self.assertFalse(evaluate(self.root,self.spec,v)['fit_allowed'])

    def test_identity_tool_raw_bytes_and_matched_scope_drift_rejected(self):
        for key in ('design_sha256','source_sha256','settings_sha256','helper_sha256','tool_sha256'):
            v=copy.deepcopy(self.vendor);v[key]='0'*64
            with self.assertRaises(ValueError):evaluate(self.root,self.spec,v)
        (self.root/'vendor.txt').write_text('changed')
        with self.assertRaises(ValueError):evaluate(self.root,self.spec,self.vendor)
        spec=copy.deepcopy(self.spec);spec['scope']='matched_component_benchmark'
        self.assertFalse(evaluate(self.root,spec)['fit_allowed'])

    def test_real_unchanged_component_benchmark_is_narrowly_scoped(self):
        root=Path(__file__).resolve().parents[1]
        project='artifacts/azure-matched-crt-hostbench-prepared-v2/crt27-mont-azure-hostbench-v1'
        context='results/throughput-20260929/crt27-mont-hostbench-m8azn-v1/project/execution-context.json'
        receipt='results/throughput-20260929/crt27-mont-hostbench-m8azn-v1/verification.json'
        m=json.loads((root/project/'manifest.json').read_text())
        sources={project+'/rtl/'+name:pin for name,pin in m['source_sha256'].items()}
        settings={project+'/'+name:pin for name,pin in m['control_sha256'].items()}
        settings[project+'/manifest.json']=file_digest(root/project/'manifest.json')
        spec=dict(schema=SCHEMA,scope='matched_component_benchmark',identity={k:m[k] for k in ('top','device','clock_period_ns','seed')},
            sources=sources,settings=settings,blocks=['crt27_resource16'],transfers=[],
            exclusions=[dict(kind='external_virtual_io',endpoints=['top input/output pins'],reason='unchanged virtual-I/O benchmark')],coverage_claim='declared_source_inventory_not_netlist_completeness')
        spec['identity']['parameters']=m['core_parameters']
        reference=dict(schema='prefit-matched-component-reference-v1',scope='component_benchmark',native_completed=True,
            sources=sources,settings=settings,identity=spec['identity'],evidence={p:file_digest(root/p) for p in (context,receipt)},execution_context=context,native_receipt=receipt)
        result=evaluate(root,spec,reference=reference)
        self.assertTrue(result['fit_allowed']);self.assertFalse(result['physical_timing_proven'])
        spec['scope']='whole_core'
        self.assertFalse(evaluate(root,spec,reference=reference)['fit_allowed'])
        spec['scope']='matched_component_benchmark';spec['identity']=dict(spec['identity'],seed=2)
        with self.assertRaises(ValueError):evaluate(root,spec,reference=reference)

if __name__=='__main__':unittest.main()
