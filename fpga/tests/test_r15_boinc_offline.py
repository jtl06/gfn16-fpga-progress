"""Offline lifecycle author tests; no SDK, project connection or device."""
from copy import deepcopy
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from fpga.host import r15_boinc_wrapper as w
from fpga.host.r15_arithmetic import Checkpoint, HostFault, SoftwareBackend


def job(bits='10110101101'):
    return dict(schema=w.JOB_SCHEMA, job_id='offline-test', base=10, n=32,
                owner=0x123456789abcde, context=1, initial_hex='0x7', bits=bits,
                window_size=4, gl_width=2)


def expected(document):
    modulus=document['base']**document['n']+1
    return (pow(int(document['initial_hex'],16),1 << len(document['bits']),modulus)*
            pow(2,int(document['bits'],2),modulus)) % modulus


class Calls(w.OfflineCallbacks):
    def __init__(self, states):
        super().__init__();self.states=list(states);self.progress=[]
    def status(self):return self.states.pop(0) if self.states else w.Status()
    def fraction_done(self, value):
        super().fraction_done(value);self.progress.append(value)


class OfflineWrapper(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve();self.slot=self.root/'slot'

    def run_job(self, document=None, **kwargs):
        return w.run_offline_job(document or job(),self.slot,enabled=True,**kwargs)

    def result(self):return json.loads((self.slot/'result.json').read_text())

    def checkpoint(self):
        identity=json.loads((self.slot/'slot.json').read_text())
        return Checkpoint.decode((self.slot/'checkpoint.r15').read_bytes(),
            expected_source=identity['source_sha256'],expected_owner=job()['owner'],expected_context=1)

    def test_default_off_and_actual_backend_refusal_before_slot(self):
        with self.assertRaises(HostFault):w.run_offline_job(job(),self.slot)
        with self.assertRaises(HostFault):self.run_job(engine='vfio')
        self.assertFalse(self.slot.exists())

    def test_normal_independent_scalar_oracle_and_partial_tail(self):
        calls=Calls([]);out=self.run_job(callbacks=calls)
        self.assertEqual(out['phase'],'complete')
        self.assertEqual(int(self.result()['residue_hex'],16),expected(job()))
        self.assertEqual(self.checkpoint().completed,11)
        self.assertEqual(calls.checkpoint_acks,3)
        self.assertEqual(calls.progress,sorted(calls.progress))
        self.assertEqual(calls.progress[-1],1.0)
        self.assertFalse(self.result()['scope']['BOINC_SDK'])
        self.assertFalse(self.result()['scope']['canonical_EndA_transport'])

    def test_restart_matches_uninterrupted_bytes_and_is_idempotent(self):
        self.assertEqual(self.run_job(max_windows=1)['phase'],'yielded')
        self.assertEqual(self.checkpoint().completed,4)
        self.assertFalse((self.slot/'result.json').exists())
        with self.assertRaisesRegex(HostFault,'EXPLICIT_RESUME'):self.run_job()
        self.assertEqual(self.run_job(resume=True)['phase'],'complete')
        observed=(self.slot/'result.json').read_bytes()
        other=self.root/'uninterrupted'
        w.run_offline_job(job(),other,enabled=True)
        self.assertEqual(observed,(other/'result.json').read_bytes())
        self.assertEqual(self.run_job(resume=True)['phase'],'complete')
        self.assertEqual(observed,(self.slot/'result.json').read_bytes())

    def test_suspension_does_not_advance_and_resumes(self):
        self.assertEqual(self.run_job(callbacks=Calls([w.Status(suspended=True)]))['phase'],'suspended')
        self.assertEqual(self.checkpoint().completed,0)
        self.assertFalse((self.slot/'result.json').exists())
        self.assertEqual(self.run_job(resume=True)['phase'],'complete')

    def test_quit_after_verified_window_then_resume(self):
        out=self.run_job(callbacks=Calls([w.Status(),w.Status(quit_request=True)]))
        self.assertEqual(out['phase'],'deferred');self.assertEqual(self.checkpoint().completed,4)
        self.assertFalse((self.slot/'result.json').exists())
        self.assertEqual(self.run_job(resume=True)['phase'],'complete')

    def test_heartbeat_loss_defers_without_result(self):
        self.assertEqual(self.run_job(callbacks=Calls([w.Status(no_heartbeat=True)]))['phase'],'deferred')
        self.assertFalse((self.slot/'result.json').exists())
        self.assertEqual(self.checkpoint().value,7)

    def test_abort_is_terminal_and_never_publishes(self):
        out=self.run_job(callbacks=Calls([w.Status(),w.Status(abort_request=True)]))
        self.assertEqual(out['phase'],'aborted');self.assertEqual(self.checkpoint().completed,4)
        with self.assertRaisesRegex(HostFault,'ABORTED_JOB'):self.run_job(resume=True)
        self.assertFalse((self.slot/'result.json').exists())

    def test_stop_at_last_boundary_does_not_publish_until_resumed(self):
        out=self.run_job(job('1011'),callbacks=Calls([w.Status(),w.Status(quit_request=True)]))
        self.assertEqual(out['phase'],'deferred');self.assertFalse((self.slot/'result.json').exists())
        self.assertEqual(self.run_job(job('1011'),resume=True)['phase'],'complete')

    def test_gl_corruption_restores_last_verified_position(self):
        original=SoftwareBackend.step
        def corrupt(backend,bit):
            original(backend,bit)
            if backend.steps == 2:backend.load((backend.read()+1) % int(backend.modulus))
        with patch.object(SoftwareBackend,'step',corrupt):out=self.run_job()
        self.assertEqual(out['phase'],'failed');self.assertIn('GL_WINDOW_REJECTED',out['error'])
        self.assertEqual((self.checkpoint().completed,self.checkpoint().value),(0,7))
        self.assertFalse((self.slot/'result.json').exists())
        self.assertEqual(self.run_job(resume=True)['phase'],'complete')

    def test_backend_exception_retains_verified_checkpoint(self):
        with patch.object(SoftwareBackend,'step',side_effect=RuntimeError('synthetic backend failure')):
            out=self.run_job()
        self.assertEqual(out['phase'],'failed');self.assertEqual(self.checkpoint().completed,0)
        self.assertFalse((self.slot/'result.json').exists())

    def test_corrupt_checkpoint_is_not_silently_reinitialized(self):
        self.run_job(max_windows=1)
        path=self.slot/'checkpoint.r15';path.write_bytes(path.read_bytes()+b'broken')
        before=path.read_bytes()
        with self.assertRaises(HostFault):self.run_job(resume=True)
        self.assertEqual(path.read_bytes(),before);self.assertFalse((self.slot/'result.json').exists())

    def test_restart_wrong_job_or_code_does_not_overwrite(self):
        self.run_job(max_windows=1);before=(self.slot/'checkpoint.r15').read_bytes()
        bad=job();bad['bits']='0'+bad['bits'][1:]
        with self.assertRaisesRegex(HostFault,'RESTART_IDENTITY'):self.run_job(bad,resume=True)
        with patch.object(w,'source_pins',return_value={'unqualified.py':'0'*64}):
            with self.assertRaisesRegex(HostFault,'RESTART_IDENTITY'):self.run_job(resume=True)
        self.assertEqual((self.slot/'checkpoint.r15').read_bytes(),before)

    def test_checkpoint_ordinal_must_be_a_real_window_boundary(self):
        self.run_job(max_windows=0);cp=self.checkpoint()
        bad=Checkpoint(cp.base,cp.n,cp.owner,cp.context,1,cp.value,cp.source)
        (self.slot/'checkpoint.r15').write_bytes(bad.encode())
        with self.assertRaisesRegex(HostFault,'DESCRIPTOR_BOUNDARY'):self.run_job(resume=True)

    def test_existing_nonprivate_directory_and_symlink_refused(self):
        self.slot.mkdir();(self.slot/'init_data.xml').write_text('<real-client-marker/>')
        before={p.name:p.read_bytes() for p in self.slot.iterdir()}
        with self.assertRaisesRegex(HostFault,'NOT_BOINC_INSTALLATION'):self.run_job()
        self.assertEqual({p.name:p.read_bytes() for p in self.slot.iterdir()},before)
        linked=self.root/'link';linked.symlink_to(self.slot,target_is_directory=True)
        with self.assertRaisesRegex(HostFault,'PRIVATE_SLOT'):
            w.run_offline_job(job(),linked,enabled=True)

    def test_checkpoint_symlink_and_hardlink_refused(self):
        self.run_job(max_windows=0);path=self.slot/'checkpoint.r15'
        saved=self.root/'saved';saved.write_bytes(path.read_bytes());path.unlink();path.symlink_to(saved)
        with self.assertRaises(OSError):self.run_job(resume=True)
        path.unlink();os.link(saved,path)
        # Wrapper reads its checkpoint digest at publication; the store's
        # pre-existing loader independently refuses links through O_NOFOLLOW.
        with self.assertRaises(HostFault):self.run_job(resume=True)

    def test_same_slot_concurrent_runner_is_refused(self):
        self.slot.mkdir();fd=os.open(self.slot/'.r15-offline.lock',os.O_RDWR|os.O_CREAT,0o600)
        self.addCleanup(os.close,fd);fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        with self.assertRaisesRegex(HostFault,'SLOT_BUSY'):self.run_job()

    def test_invalid_private_input_and_unknown_project_format(self):
        for delta in ({'schema':'primegrid'}, {'n':65536}, {'base':True}, {'context':False},
                      {'bits':'102'}, {'window_size':3}, {'initial_hex':'0x00'}, {'device':'vfio'}):
            with self.subTest(delta=delta):
                bad=job();bad.update(delta)
                with self.assertRaises(HostFault):self.run_job(bad)
        with self.assertRaises(HostFault):w._decode(b'{"schema":1,"schema":2}')
        self.assertFalse(self.slot.exists())

    def test_unknown_or_nonboolean_control_fails_without_result(self):
        control=self.root/'control.json';control.write_text(json.dumps(dict(
            schema='r15-boinc-offline-control-v1',status=dict(suspended=1),checkpoint=True)))
        out=self.run_job(callbacks=w.OfflineCallbacks(control))
        self.assertEqual(out['phase'],'failed');self.assertFalse((self.slot/'result.json').exists())

    def test_result_recovery_and_tamper_rejection(self):
        self.run_job();status=self.slot/'status.json';status.unlink()
        self.assertEqual(self.run_job(resume=True)['phase'],'complete')
        path=self.slot/'result.json';bad=self.result();bad['residue_hex']='0x0';path.write_text(json.dumps(bad))
        with self.assertRaisesRegex(HostFault,'RESULT_MISMATCH'):self.run_job(resume=True)
        self.assertEqual(json.loads(path.read_text()),bad)

    def test_malformed_status_restart_is_a_typed_refusal(self):
        self.run_job(max_windows=1)
        path=self.slot/'status.json'
        for value in (None,[],{'phase':'unknown'}):
            path.write_text(json.dumps(value))
            with self.assertRaisesRegex(HostFault,'RESTART_STATUS'):self.run_job(resume=True)
        self.assertFalse((self.slot/'result.json').exists())

    def test_real_cli_run_resume_and_explicit_off(self):
        input_file=self.root/'input.json';input_file.write_text(json.dumps(job()))
        argv=[sys.executable,'-B','-m','fpga.host.r15_boinc_wrapper','--job',str(input_file),'--slot',str(self.slot)]
        root=Path(__file__).resolve().parents[2]
        refused=subprocess.run(argv,cwd=root,capture_output=True,text=True,timeout=10)
        self.assertEqual(refused.returncode,2);self.assertFalse(self.slot.exists())
        paused=subprocess.run(argv+['--software-only','--max-windows','1'],cwd=root,capture_output=True,text=True,timeout=10)
        self.assertEqual(paused.returncode,75);self.assertEqual(json.loads(paused.stdout)['phase'],'yielded')
        done=subprocess.run(argv+['--software-only','--resume'],cwd=root,capture_output=True,text=True,timeout=10)
        self.assertEqual(done.returncode,0,done.stderr);self.assertEqual(json.loads(done.stdout)['phase'],'complete')

    def test_checkpoint_notification_occurs_after_durable_verified_bytes(self):
        checkpoints=[];outer=self
        class Durable(Calls):
            def checkpoint_completed(self):
                checkpoints.append(outer.checkpoint().completed)
                super().checkpoint_completed()
        self.run_job(callbacks=Durable([]))
        self.assertEqual(checkpoints,[4,8,11])

    def test_recipe_is_exact_small_software_closure_not_a_launcher(self):
        recipe=w.recipe()
        self.assertEqual(len(recipe['source_sha256']),8)
        self.assertEqual(recipe['allowed_hosts'],['azure-fit'])
        self.assertEqual(recipe['max_command_seconds'],105)
        self.assertEqual(recipe['argv'][-2:],['--engine','gmp'])
        self.assertFalse(recipe['scope']['HDL']);self.assertFalse(recipe['scope']['BOINC_runtime'])

    def test_output_validator_rejects_scope_source_and_extra_output(self):
        value=dict(schema='r15-boinc-offline-tests-v1',status='software_tests_pass',tests=28,
            cases=[dict(base=b,n=n,steps=137,independent_pow_equal=True,restart_byte_equal=True,
                        no_provisional_result=True,chosen_engine_corruption_rejected=True) for b,n in ((599,32),(600,256))],
            runtime={'engine':'python-small-reference'},platform='Darwin',source_pins=w.source_pins(),
            elapsed_seconds=0.1,scope=w.SCOPE)
        def output(x):return 'R15_BOINC_OFFLINE_RESULT '+json.dumps(x)
        w.validate(output(value),require_gmp=False,expected_source_pins=w.source_pins())
        bad=deepcopy(value);bad['scope']['BOINC_SDK']=True
        with self.assertRaises(HostFault):w.validate(output(bad),require_gmp=False,expected_source_pins=w.source_pins())
        with self.assertRaises(HostFault):w.validate(output(value),require_gmp=True,expected_source_pins=w.source_pins())
        with self.assertRaises(HostFault):w.validate(output(value),require_gmp=False,expected_source_pins={})
        with self.assertRaises(HostFault):w.validate(output(value)+'\nunrelated',require_gmp=False,expected_source_pins=w.source_pins())

    def test_exact_reference_callback_loader_has_no_relative_import_dependency(self):
        spec=importlib.util.spec_from_file_location('_r15_software_output',Path(w.__file__))
        module=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertTrue(callable(module.validate))
        self.assertEqual(module.source_pins(),w.source_pins())
        with self.assertRaises(HostFault):module.validate('not a result',expected_source_pins=w.source_pins())


if __name__=='__main__':unittest.main()
