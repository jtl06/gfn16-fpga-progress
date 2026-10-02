"""Local source/snapshot/negative-fixture tests only; never execute HDL/cloud."""
import copy
import hashlib
import inspect
import json
from pathlib import Path
import tempfile
import tarfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from fpga.synthesis import prepare_core27_rootfused_crtmont_syn as prep
from fpga.cloud import aws_syn_v1 as worker
from fpga.cloud import aws_fit_v6 as frozen

ROOT=Path(__file__).resolve().parents[1]


class Whole64SynthesisPairTests(unittest.TestCase):
    def prepare(self,directory):
        return prep.prepare_pair(Path(directory).resolve()/'pair',source_root=ROOT)

    def test_exact_source_controls_and_frozen_parent_untouched(self):
        before=prep.checked_inputs(ROOT)
        with tempfile.TemporaryDirectory() as temp:
            receipt=self.prepare(temp);a=Path(temp).resolve()/'pair/rootfused';b=Path(temp).resolve()/'pair/rootfused_crtmont'
            left=worker.verify_project(a);right=worker.verify_project(b)
            self.assertEqual(len(left['source_sha256']),16);self.assertEqual(len(right['source_sha256']),16)
            self.assertEqual(len(set(left['source_sha256'])&set(right['source_sha256'])),14)
            for n in set(left['source_sha256'])&set(right['source_sha256']):self.assertEqual((a/'rtl'/n).read_bytes(),(b/'rtl'/n).read_bytes())
            candidate=(b/'rtl'/(prep.NEW_TOP+'.sv')).read_bytes()
            self.assertEqual(candidate.replace(prep.NEW_TOP.encode(),prep.OLD_TOP.encode()).replace(
                (prep.NEW_CRT+' crt (').encode(),(prep.OLD_CRT+' crt (').encode()),(a/'rtl'/(prep.OLD_TOP+'.sv')).read_bytes())
            qsf=(a/'probe.qsf').read_bytes().replace((prep.OLD_TOP+'.sv').encode(),(prep.NEW_TOP+'.sv').encode()).replace(
                ('TOP_LEVEL_ENTITY '+prep.OLD_TOP+'\n').encode(),('TOP_LEVEL_ENTITY '+prep.NEW_TOP+'\n').encode()).replace(
                (prep.OLD_CRT+'.sv').encode(),(prep.NEW_CRT+'.sv').encode())
            self.assertEqual(qsf,(b/'probe.qsf').read_bytes())
            for n in ('run.tcl','probe.sdc','probe.qpf'):self.assertEqual((a/n).read_bytes(),(b/n).read_bytes())
            self.assertEqual((a/'probe.sdc').read_bytes(),before[2]['probe.sdc'])
            self.assertEqual((a/'probe.qpf').read_bytes(),before[2]['probe.qpf'])
            for p in (a,b):
                m=json.loads((p/'manifest.json').read_bytes())
                self.assertEqual(m['allowed_stages'],['syn']);self.assertFalse(m['normal_G4_AW16_qualified'])
                self.assertFalse(m['physical_fit_qualified']);self.assertFalse((p/'output_files').exists())
                with self.assertRaisesRegex(ValueError,'compute-only'):frozen.verify_project(p)
            self.assertEqual(receipt['status'],'prepared_matched_whole64_synthesis_pair_not_dispatched')
        self.assertEqual(before,prep.checked_inputs(ROOT))

    def test_closed_archive_fresh_only(self):
        with tempfile.TemporaryDirectory() as temp:
            receipt=self.prepare(temp);directory=Path(temp).resolve()/'pair'
            for n,pin in receipt['input_sha256'].items():self.assertEqual(prep.digest((directory/n).read_bytes()),pin)
            with tarfile.open(directory/'source.tar.gz') as tar:
                self.assertEqual(set(tar.getnames()),set(receipt['input_sha256'])|{'pair.json'})
                self.assertTrue(all(x.isfile() and not x.issym() for x in tar))
                for n,pin in receipt['input_sha256'].items():self.assertEqual(prep.digest(tar.extractfile(n).read()),pin)
            with self.assertRaises(FileExistsError):self.prepare(temp)

    def test_pin_failure_precedes_output_creation(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(prep,'NEW_TOP_SHA','0'*64):
            with self.assertRaisesRegex(ValueError,'candidate'):self.prepare(temp)
            self.assertFalse((Path(temp)/'pair').exists())
        with tempfile.TemporaryDirectory() as temp,patch.object(prep,'G3_SHA','0'*64):
            with self.assertRaisesRegex(ValueError,'G3'):self.prepare(temp)
            self.assertFalse((Path(temp)/'pair').exists())

    def test_exact_driver_transform_rejects_mutation(self):
        raw=prep.checked_inputs(ROOT)[2]['run.tcl'];driver=prep.synthesis_driver(raw)
        self.assertEqual(driver.count(b'execute_module -tool syn'),1)
        self.assertNotIn(b'execute_module -tool fit',driver);self.assertNotIn(b'execute_module -tool sta',driver)
        with self.assertRaises(ValueError):prep.synthesis_driver(raw.replace(b'ni {syn fit}',b'ni {syn fit sta}'))
        with self.assertRaises(ValueError):prep.synthesis_driver(raw.replace(b'execute_module -tool sta',b'execute_module -tool asm'))

    def test_worker_reuses_frozen_policy_guards(self):
        for n in ('validate_topology','live_topology','validate_limits','live_limits','slot_locks','locked','read_regular'):
            self.assertEqual(inspect.getsource(getattr(worker.base,n)),inspect.getsource(getattr(frozen,n)))
        self.assertEqual(worker.BASE_SHA,hashlib.sha256(Path(frozen.__file__).read_bytes()).hexdigest())
        self.assertEqual((worker.base.HOST,worker.base.ROOT,worker.base.MEMORY,worker.base.TIMEOUT),
                         (frozen.HOST,frozen.ROOT,frozen.MEMORY,frozen.TIMEOUT))
        src=inspect.getsource(worker.launch)
        self.assertIn("str(project/'run.tcl'),'syn']",src)
        self.assertNotIn("'fit']",src);self.assertNotIn('execute_module',src)
        self.assertEqual(src.count('subprocess.run('),1)
        self.assertIn('check_g4(g4_path,g4_sha,context)',src)

    def test_worker_control_rtl_stage_geometry_tampering_rejected(self):
        for mutation in ('control','rtl','stage','geometry'):
            with self.subTest(mutation=mutation),tempfile.TemporaryDirectory() as temp:
                self.prepare(temp);p=Path(temp).resolve()/'pair/rootfused';m=json.loads((p/'manifest.json').read_bytes())
                if mutation=='control':(p/'run.tcl').write_bytes((p/'run.tcl').read_bytes()+b'# drift\n')
                elif mutation=='rtl':(p/'rtl'/next(iter(m['source_sha256']))).write_bytes(b'bad')
                elif mutation=='stage':m['allowed_stages']=['syn','fit','sta'];(p/'manifest.json').write_text(json.dumps(m))
                else:
                    raw=(p/'probe.qsf').read_bytes().replace(b'AW 16',b'AW 15');(p/'probe.qsf').write_bytes(raw)
                    m['control_sha256']['probe.qsf']=prep.digest(raw);(p/'manifest.json').write_text(json.dumps(m))
                with self.assertRaises(ValueError):worker.verify_project(p)

    def test_syn_estimates_never_fit_values_and_fit_reports_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp).resolve();o=p/'output_files';o.mkdir()
            summary=o/'probe.syn.summary'
            summary.write_text('Synthesis Status : Successful\nLogic utilization estimate (in ALMs) : 338,930 / 427,200\nTotal registers : 335042\nEstimated DSP Blocks Post-Merging : 802\n')
            r=worker.summarize_synthesis(p)
            self.assertEqual(r['metrics'],{'synthesis_alms_estimate':338930,'synthesis_registers':335042,
                'synthesis_dsp_blocks_post_merging_estimate':802})
            for n in ('alms_needed','alms_placed','M20K_placed','fmax_mhz','setup_slack_ns','hold_slack_ns'):self.assertIsNone(r[n])
            summary.write_text(summary.read_text()+'Total registers : 2\n')
            with self.assertRaisesRegex(ValueError,'ambiguous'):worker.summarize_synthesis(p)
            summary.write_text('Synthesis Status : Failed\n');self.assertFalse(worker.summarize_synthesis(p)['synthesis_success'])
            (o/'probe.fit.summary').write_text('Fitter Status : Successful')
            with self.assertRaisesRegex(ValueError,'forbidden'):worker.summarize_synthesis(p)

    def test_exact_version_append_is_only_allowed_final_drift(self):
        with tempfile.TemporaryDirectory() as temp:
            self.prepare(temp);p=Path(temp).resolve()/'pair/rootfused';context=worker.verify_project(p)
            raw=(p/'probe.qsf').read_bytes();version=b'set_global_assignment -name LAST_QUARTUS_VERSION "26.1.0 Pro Edition"\n'
            (p/'probe.qsf').write_bytes(raw+version)
            self.assertEqual(worker.final_inputs(p,context)['unexpected_drift'],[])
            self.assertEqual(len(worker.final_inputs(p,context)['allowed_vendor_drift']),1)
            (p/'probe.qsf').write_bytes(raw+version+version)
            self.assertEqual(worker.final_inputs(p,context)['unexpected_drift'],['probe.qsf'])
            (p/'probe.qsf').write_bytes(raw)
            (p/'rtl/extra.sv').write_text('module extra;endmodule')
            self.assertIn('RTL closure',worker.final_inputs(p,context)['unexpected_drift'])

    def gate_fixture(self,context):
        expected=dict(context['source_sha256'])
        for old,new,pin in [(prep.OLD_CRT+'.sv',prep.NEW_CRT+'.sv',prep.NEW_CRT_SHA),
                            (prep.OLD_TOP+'.sv',prep.NEW_TOP+'.sv',prep.NEW_TOP_SHA)]:
            if old in expected:expected.pop(old);expected[new]=pin
        return dict(status='passed',aw=16,n=65536,ntt_lanes=64,top=prep.NEW_TOP,model_threads=1,compile_workers=2,
            manifest_sha256='fc10698824eb675c490eefd06c517c1a00cdf58e952185532c0c3552dff8172d',g2_sha256=prep.G2_SHA,
            parent_report_sha256='7447dbe4813e1e6b45c5c5071da5019c7aa4ee0b47e0a8a923f75852fd01468a',
            sources={'rtl/kernel/'+n:pin for n,pin in expected.items()},compiled_source_order=['rtl/kernel/'+n for n in expected],
            matched_cycle_delta=dict(crt=-45,cycles=-45,all_other_fields_identical=True),
            vectors=dict(sha256='3449c1e3e1d7c0820842ecb30295b963b4aa81af6b27be8e38b7c87f2bd39f3d',squares=12,readbacks=10),
            metrics=[{} for _ in range(12)],steps=[dict(name=n,returncode=0) for n in ('build','probe','test-segment0','test-segment1')])

    def test_deferred_AW16_receipt_binding_and_negative_contracts(self):
        with tempfile.TemporaryDirectory() as temp:
            self.prepare(temp);p=Path(temp).resolve()/'pair';g4=Path(temp).resolve()/'G4-fixture.json'
            for name in ('rootfused','rootfused_crtmont'):
                context=worker.verify_project(p/name);fixture=self.gate_fixture(context)
                g4.write_text(json.dumps(fixture));pin=prep.digest(g4.read_bytes())
                context['required_G4_report_sha256']=pin  # synthetic fixture, not native qualification
                self.assertEqual(worker.check_g4(g4,pin,context)['normal_operations'],12)
                with self.assertRaises(ValueError):worker.check_g4(g4,'0'*64,context)
                for key,value in [('status','running'),('aw',5),('model_threads',2),('ntt_lanes',16),('metrics',[]),
                                  ('compiled_source_order',[]),('matched_cycle_delta',dict(crt=-44))]:
                    changed=copy.deepcopy(fixture);changed[key]=value;g4.write_text(json.dumps(changed))
                    context['required_G4_report_sha256']=prep.digest(g4.read_bytes())
                    with self.subTest(project=name,key=key),self.assertRaises(ValueError):worker.check_g4(g4,prep.digest(g4.read_bytes()),context)

    def test_no_offhost_execution(self):
        with patch.object(worker,'verify_worker_user'),patch.object(worker.base,'ROOT',Path('/not-current-directory')),patch.object(worker.subprocess,'run',side_effect=AssertionError('no HDL')):
            with self.assertRaisesRegex(ValueError,'directory'):worker.launch('test','a',Path('/missing'),Path('/missing'),'0'*64)

    def test_root_other_user_qdb_refused_and_real_g4_bound(self):
        for uid,name in ((0,'root'),(1000,'other')):
            with patch.object(worker.os,'geteuid',return_value=uid),patch.object(worker.pwd,'getpwuid',return_value=SimpleNamespace(pw_name=name)):
                with self.assertRaisesRegex(ValueError,'ubuntu'):worker.verify_worker_user()
        with patch.object(worker.os,'geteuid',return_value=1000),patch.object(worker.pwd,'getpwuid',return_value=SimpleNamespace(pw_name='ubuntu')):
            worker.verify_worker_user()
        with tempfile.TemporaryDirectory() as temp:
            self.prepare(temp);p=Path(temp).resolve()/'pair'
            for name in ('rootfused','rootfused_crtmont'):
                directory=p/name;context=worker.verify_project(directory)
                result=worker.check_g4((ROOT/prep.G4).resolve(),prep.G4_SHA,context)
                self.assertEqual(result['readbacks'],10)
                (directory/'qdb').mkdir()
                with self.assertRaisesRegex(ValueError,'existing execution'):worker.verify_project(directory)


if __name__=='__main__':unittest.main()
