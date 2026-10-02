"""Exercise exact derived launch provenance/argv without any vendor process."""
from contextlib import ExitStack
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

FPGA = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('plain_v4', FPGA/'cloud/plain_fit_v4.py')
p = importlib.util.module_from_spec(spec); spec.loader.exec_module(p)
C1 = FPGA/'results/throughput-20260929/core27-crtmont-c1-8ns-aws-fit-v1'


def policy(root, host, continuation=False):
    config = dict(p.HOSTS[host], root=str(root))
    (root/'run-aws-fit-v6.sh').write_text('# Synthetic context descriptor, never executed.\n')
    return p.runner(config, host, continuation), config


class LaunchTests(unittest.TestCase):
    def launch_fixture(self, root, host, slot, native_returncode=0):
        module, config = policy(root, host)
        project = root/'probe'; project.mkdir(); (project/'run.tcl').write_text(p.FULL_TCL)
        topology = root/'topology.json'; topology.write_text('{}\n')
        cpus = config['slots'][slot]
        selected = dict(affinity=cpus, physical_cores=[(0,c) for c in cpus], topology={str(c):[0,c] for c in cpus})
        module.verify_project = lambda path: dict(manifest_sha256='a'*64, source_sha256={}, control_sha256={})
        module.live_limits = lambda: dict(cgroup_path='/synthetic', cpu_max=f'{config["workers"]*100000} 100000', memory_max=str(config['memory']))
        module.live_topology = lambda: []
        module.validate_topology = lambda *args: selected
        calls = []
        def fake_run(argv, **kwargs):
            calls.append(argv)
            return SimpleNamespace(returncode=native_returncode if argv[0] == '/usr/bin/time' else 0)
        with ExitStack() as mocks:
            mocks.enter_context(patch.object(Path, 'cwd', return_value=root))
            mocks.enter_context(patch.object(module.os, 'sched_getaffinity', return_value=set(cpus), create=True))
            mocks.enter_context(patch.object(module.socket, 'gethostname', return_value=host))
            mocks.enter_context(patch.object(module.subprocess, 'run', side_effect=fake_run))
            code = module.launch('probe', slot, topology)
        return code, json.loads((project/'execution-context.json').read_text()), json.loads((project/'execution-result.json').read_text()), calls

    def test_aws_six_worker_context_and_absolute_qsh_both_slots(self):
        for slot in ('a', 'b'):
            with self.subTest(slot=slot), tempfile.TemporaryDirectory() as directory:
                root = Path(directory).resolve()
                code, context, result, calls = self.launch_fixture(root, 'gfn16-aws-m8i', slot)
                self.assertEqual(code, 0)
                self.assertEqual(context['quartus_workers'], 6)
                self.assertEqual(len(context['affinity']), 6)
                self.assertEqual(calls[0][5], str(root/'altera_pro/26.1/quartus/bin/quartus_sh'))
                self.assertTrue(Path(calls[0][5]).is_absolute())
                self.assertNotIn('quartus_sh', calls[0])
                self.assertEqual(calls[0][6:], ['-t', str(root/'probe/run.tcl'), 'fit'])
                self.assertEqual(result['quartus_returncode'], 0)

    def test_f16_four_worker_provenance_and_absolute_qsh_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            code, context, result, calls = self.launch_fixture(root, 'gfn16-azure-f16', 'c')
            self.assertEqual(code, 0)
            self.assertEqual(context['quartus_workers'], 4)
            self.assertEqual(context['affinity'], [8,9,10,11])
            self.assertEqual(calls[0][5], str(root/'altera_pro/26.1/quartus/bin/quartus_sh'))

    def test_native_failure_retained_in_write_once_result(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            code, context, result, calls = self.launch_fixture(root, 'gfn16-aws-m8i', 'a', 2)
            self.assertEqual(code, 2)
            self.assertEqual(result['quartus_returncode'], 2)
            self.assertEqual(result['summarize_returncode'], 0)
            self.assertEqual(context['quartus_workers'], 6)
            self.assertEqual(len(calls), 2)


class SourceTests(unittest.TestCase):
    def copy_actual_c1(self, root):
        project = root/'probe'; project.mkdir()
        shutil.copytree(C1/'rtl', project/'rtl')
        for name in ('manifest.json', 'probe.qsf', 'probe.qpf', 'probe.sdc', 'run.tcl'):
            shutil.copyfile(C1/name, project/name)
        return project

    def test_actual_six_worker_source_manifest_qsf_and_wrong_worker_negative(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve(); module, config = policy(root, 'gfn16-aws-m8i')
            project = self.copy_actual_c1(root)
            result = module.verify_project(project)
            self.assertEqual(len(result['source_sha256']), 16)
            qsf = project/'probe.qsf'; before = qsf.read_text()
            qsf.write_text(before.replace('NUM_PARALLEL_PROCESSORS 6', 'NUM_PARALLEL_PROCESSORS 4'))
            with self.assertRaises(ValueError): module.verify_project(project)
            qsf.write_text(before)
            manifest = json.loads((project/'manifest.json').read_text()); manifest['compile_processors'] = 4
            (project/'manifest.json').write_text(json.dumps(manifest))
            with self.assertRaises(ValueError): module.verify_project(project)

    def test_no_extra_vendor_flow_or_diagnostic_gate(self):
        self.assertEqual(p.FULL_TCL.count('execute_module -tool'), 3)
        self.assertEqual(p.CONTINUE_TCL.count('execute_module -tool'), 2)
        self.assertNotIn('execute_module -tool syn', p.CONTINUE_TCL)
        for source in (p.FULL_TCL, p.CONTINUE_TCL):
            self.assertNotIn('exec ', source)
            self.assertNotIn('-tool asm', source)
            self.assertNotIn('design_assistant', source)

    def test_unexpected_parent_source_or_launch_anchor_fails_closed(self):
        config = p.HOSTS['gfn16-aws-m8i']
        with patch.object(p, 'PARENT_SHA', '0'*64), self.assertRaises(ValueError):
            p.runner(config, 'gfn16-aws-m8i', False)
        raw = (FPGA/'cloud/aws_fit_v6.py').read_bytes().replace(b"'quartus_sh','-t'", b"'different_executable','-t'")
        with patch.object(p, 'regular', return_value=raw), self.assertRaises(ValueError):
            p.runner(config, 'gfn16-aws-m8i', False)


    def test_exact_meter_only_derivative_from_frozen_azure_ready_v3(self):
        original=(FPGA/'cloud/plain_fit_v3.py').read_text()
        self.assertEqual(p.sha(FPGA/'cloud/plain_fit_v3.py'),'520dce549b44d5efcef340ce37f65338c9c161bd9e88affd7200574837ec65a0')
        expected=original.replace('"""r53 additive v3 plain fit runner: approved Azure USD60/day checker.',
            '"""r53 additive v4 plain fit runner: Azure USD60/day and AWS USD50/day.')
        expected=expected.replace("AZURE_METER_SHA='"+p.AZURE_METER_SHA+"'",
            "AZURE_METER_SHA='"+p.AZURE_METER_SHA+"'\nAWS_METER_SHA='"+p.AWS_METER_SHA+"'")
        expected=expected.replace("else 'host_hours_admit_v1.py'","else 'host_hours_admit_v2.py'")
        expected=expected.replace(" if host=='gfn16-azure-f16':regular(meter_path,AZURE_METER_SHA)",
            " regular(meter_path,AZURE_METER_SHA if host=='gfn16-azure-f16' else AWS_METER_SHA)")
        expected=expected.replace('usage: plain_fit_v3.py REQUEST SHA256','usage: plain_fit_v4.py REQUEST SHA256')
        self.assertEqual((FPGA/'cloud/plain_fit_v4.py').read_text(),expected+'\n')
        self.assertEqual(p.AWS_METER_SHA,p.sha(FPGA/'cloud/host_hours_admit_v2.py'))
        self.assertEqual(p.AZURE_METER_SHA,p.sha(FPGA/'cloud/host_hours_azure_v4.py'))
        with self.assertRaisesRegex(ValueError,'SHA drift'):
            p.regular(FPGA/'cloud/host_hours_admit_v2.py','0'*64)


if __name__ == '__main__':
    unittest.main()

