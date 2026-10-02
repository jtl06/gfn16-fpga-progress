import importlib.util
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest

FPGA = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('prefit_da_gate', FPGA/'tools/run_prefit_da_gate_v2.py')
gate = importlib.util.module_from_spec(spec); spec.loader.exec_module(gate)
C1 = FPGA/'results/throughput-20260929/core27-crtmont-c1-8ns-aws-fit-v1'


class InputGuardTests(unittest.TestCase):
    def test_actual_c1_source_context_and_manifest_correspondence(self):
        context = json.loads((C1/'execution-context.json').read_text())
        source, settings, identity, appended = gate.verify_inputs(C1.resolve(), context)
        self.assertEqual(len(source), 16)
        self.assertEqual(len(settings), 5)
        self.assertEqual(identity['parameters'], {'AW': 16, 'NTT_LANES': 64})
        self.assertEqual(identity['clock_period_ns'], 8.0)
        self.assertEqual(len(gate.QSF_SUFFIX), 70)
        self.assertTrue(appended)

    def test_actual_c1_extra_qsf_change_rtl_mutation_and_closure_fail(self):
        context = json.loads((C1/'execution-context.json').read_text())
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            shutil.copytree(C1/'rtl', root/'rtl')
            for name in gate.CONTROLS:
                shutil.copyfile(C1/name, root/name)
            qsf = root/'probe.qsf'; before = qsf.read_bytes()
            qsf.write_bytes(before+b'# unauthorized change\n')
            with self.assertRaises(ValueError): gate.verify_inputs(root, context)
            qsf.write_bytes(before+gate.QSF_SUFFIX)
            with self.assertRaises(ValueError): gate.verify_inputs(root, context)
            qsf.write_bytes(before)
            source = next((root/'rtl').iterdir()); original = source.read_bytes(); source.write_bytes(original+b'// mutation\n')
            with self.assertRaises(ValueError): gate.verify_inputs(root, context)
            source.write_bytes(original)
            (root/'rtl/extra.sv').write_text('module extra; endmodule\n')
            with self.assertRaises(ValueError): gate.verify_inputs(root, context)


class NativeEnvironmentTests(unittest.TestCase):
    def test_quartus_parent_sentinels_loader_and_python_state_removed(self):
        result = gate.native_environment(dict(HOME='/home/worker', PATH='/usr/bin:/bin', LANG='C.UTF-8',
            QUARTUS_ROOTDIR='/vendor', QUARTUS_ROOTDIR_OVERRIDE='/vendor',
            _QUARTUS_ROOTDIR='/vendor', LD_LIBRARY_PATH='/inherited/libs', LD_PRELOAD='/injected',
            PYTHONHOME='/inherited', PYTHONPATH='/inherited', LM_LICENSE_FILE='fixture_not_logged'))
        self.assertEqual(result, dict(HOME='/home/worker', PATH='/usr/bin:/bin', LANG='C.UTF-8'))
        self.assertEqual(gate.native_environment({}), {})


class DatabaseGuardTests(unittest.TestCase):
    def test_only_exact_actual_cdb_message_schema_excluded(self):
        captured = FPGA/'results/throughput-20260929/quartus-prefit-azure-diag-stage-v4/native-collection/generated-probe.cdb.qmsgdb'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve(); compiled = root/'qdb/synthesized/chip.cdb'; compiled.parent.mkdir(parents=True); compiled.write_bytes(b'synthetic compiled input')
            message = root/'qdb/_compiler/probe/_flat/26.1.0/legacy/1/probe.cdb.qmsgdb'; message.parent.mkdir(parents=True); shutil.copyfile(captured, message)
            inputs, outputs = gate.database(root)
            self.assertEqual(set(inputs), {'qdb/synthesized/chip.cdb'})
            self.assertEqual(set(outputs), {str(message.relative_to(root))})
            other = message.with_name('other.qmsgdb'); shutil.copyfile(captured, other)
            self.assertIn(str(other.relative_to(root)), gate.database(root)[0])
            with sqlite3.connect(message) as database:
                database.execute('CREATE TABLE unknown_native_state(value INTEGER)')
            with self.assertRaises(ValueError): gate.database(root)


if __name__ == '__main__':
    unittest.main()
