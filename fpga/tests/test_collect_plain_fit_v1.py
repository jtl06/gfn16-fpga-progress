"""Terminal binding/source/archive tests; no native fit or host actions."""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

FPGA = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('plain_collect', FPGA/'tools/collect_plain_fit_v1.py')
q = importlib.util.module_from_spec(spec); spec.loader.exec_module(q)
UNIT = 'gfn16-plain-probe-v1.service'
INV = 'a'*32
STAMP = int(datetime(2026,10,1,10,0,tzinfo=timezone.utc).timestamp()*1e6)


def journal(failed=False):
    common = dict(_PID='1', UNIT=UNIT, INVOCATION_ID=INV)
    return [dict(common, JOB_TYPE='start', JOB_RESULT='done', MESSAGE='Started '+UNIT,
        __MONOTONIC_TIMESTAMP='1000000', __REALTIME_TIMESTAMP=str(STAMP)),
        dict(_PID='42', _SYSTEMD_UNIT=UNIT, _SYSTEMD_INVOCATION_ID=INV, MESSAGE='native summary retained'),
        dict(common, MESSAGE=UNIT+(': Failed with result \'exit-code\'.' if failed else ': Deactivated successfully.'),
            __MONOTONIC_TIMESTAMP='21000000', __REALTIME_TIMESTAMP=str(STAMP+20000000))]


class TerminalTests(unittest.TestCase):
    def test_exact_gc_invocation_and_failure_are_distinct(self):
        q.quiescent(dict(MainPID='0', ActiveState='inactive', SubState='dead', InvocationID=''), INV)
        good, rows = q.journal_proof(journal(), UNIT, INV)
        self.assertEqual(good['manager_elapsed_seconds'], 20)
        self.assertEqual(good['terminal_kind'], 'deactivated_successfully')
        self.assertEqual(len(rows), 3)
        failed, _ = q.journal_proof(journal(True), UNIT, INV)
        self.assertEqual(failed['terminal_kind'], 'failed')

    def test_inactivity_wrong_invocation_spoof_or_truncated_journal_not_proof(self):
        cases = [[], journal()[:-1], [dict(row, INVOCATION_ID='b'*32) for row in journal()],
            [dict(row, _PID='44') for row in journal()]]
        for rows in cases:
            with self.subTest(rows=rows), self.assertRaises(ValueError): q.journal_proof(rows, UNIT, INV)
        for current in (dict(MainPID='4', ActiveState='active', SubState='running'),
            dict(MainPID='0', ActiveState='inactive', SubState='dead', InvocationID='b'*32)):
            with self.assertRaises(ValueError): q.quiescent(current, INV)

    def test_unrelated_restart_journal_is_filtered_not_bound(self):
        rows = journal()+[dict(journal()[0], INVOCATION_ID='b'*32)]
        proof, exact = q.journal_proof(rows, UNIT, INV)
        self.assertEqual(len(exact), 3)
        self.assertTrue(proof['terminal_proven'])


class SourceArchiveTests(unittest.TestCase):
    def fixture(self, root, native_returncode=0):
        project = root/'probe'; project.mkdir(); (project/'rtl').mkdir()
        (project/'rtl/probe.sv').write_text('module probe; endmodule\n')
        for name in ('manifest.json','probe.qsf','probe.qpf','probe.sdc','run.tcl'):
            (project/name).write_text('{}\n' if name == 'manifest.json' else '# synthetic control\n')
        controls = {name:q.pin(project/name)['sha256'] for name in ('manifest.json','probe.qsf','probe.qpf','probe.sdc','run.tcl')}
        context = dict(manifest_sha256=controls['manifest.json'], source_sha256={'probe.sv':q.pin(project/'rtl/probe.sv')['sha256']},
            control_sha256=controls, qsf_parameters={}, started_at='2026-10-01T10:00:01+00:00', quartus_workers=6)
        q.save(project/'execution-context.json', context)
        q.save(project/'execution-result.json', dict(quartus_returncode=native_returncode, summarize_returncode=0,
            context_sha256=q.pin(project/'execution-context.json')['sha256'], finished_at='2026-10-01T10:00:19+00:00'))
        q.save(project/'plain-final-source-guard.json', dict(unchanged=True,drift=[],vendor_returncode=native_returncode))
        q.save(project/'database-inventory-final.json', {'qdb/placed/chip.cdb':dict(sha256='f'*64,size=123)})
        request = dict(project={key:context[key] for key in ('manifest_sha256','source_sha256','control_sha256','qsf_parameters')})
        request_path = root/'request.json'; q.save(request_path, request)
        return project, request, request_path

    def test_failed_native_result_preserved_and_exact_qsf_suffix_is_scoped(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve(); project, request, _ = self.fixture(root, 2)
            proof, _ = q.journal_proof(journal(True), UNIT, INV)
            result = q.assess(project, request, proof)
            self.assertFalse(result['native_job_succeeded'])
            self.assertEqual(result['native_result']['quartus_returncode'], 2)
            self.assertEqual(result['findings'], [])
            qsf = project/'probe.qsf'; before = qsf.read_bytes(); qsf.write_bytes(before+q.SUFFIX)
            self.assertEqual(q.assess(project, request, proof)['findings'], [])
            qsf.write_bytes(before+q.SUFFIX+q.SUFFIX)
            self.assertIn('source_drift_probe.qsf', q.assess(project, request, proof)['findings'])

    def test_result_context_source_or_out_of_interval_tamper_recorded(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve(); project, request, _ = self.fixture(root)
            proof, _ = q.journal_proof(journal(), UNIT, INV)
            self.assertTrue(q.assess(project, request, proof)['native_job_succeeded'])
            result_path = project/'execution-result.json'; result = json.loads(result_path.read_text())
            result.update(context_sha256='0'*64,finished_at='2026-10-01T11:00:00+00:00'); result_path.write_text(json.dumps(result))
            (project/'rtl/probe.sv').write_text('tampered source\n')
            findings = q.assess(project, request, proof)['findings']
            self.assertIn('native_result_context_sha_mismatch', findings)
            self.assertIn('source_drift_rtl/probe.sv', findings)
            self.assertIn('native_result_time_outside_invocation', findings)

    def test_archive_selection_never_reads_or_includes_raw_qdb(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve(); project, request, request_path = self.fixture(root)
            (project/'qdb').mkdir(); (project/'qdb/giant.db').write_bytes(b'raw QDB fixture, must not be selected')
            (project/'output_files').mkdir(); (project/'output_files/probe.sta.rpt').write_text('native report\n')
            files = q.select_files(root, project, request_path)
            self.assertIn('project/database-inventory-final.json', files)
            self.assertIn('project/output_files/probe.sta.rpt', files)
            self.assertFalse(any('qdb' in Path(name).parts for name in files))
            (project/'output_files/linked.rpt').symlink_to(project/'output_files/probe.sta.rpt')
            with self.assertRaises(ValueError): q.select_files(root, project, request_path)


if __name__ == '__main__':
    unittest.main()
