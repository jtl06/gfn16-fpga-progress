import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

FPGA=Path(__file__).resolve().parents[1]
RESULTS=FPGA/'results/throughput-20260929'
SPEC=importlib.util.spec_from_file_location('lint_acceptance',RESULTS/'core27_t5b_lint_acceptance_v1.py')
gate=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(gate)
LINT=RESULTS/'core27-t5b-lint-first-v1'
STAGE=RESULTS/'core27-t5b-qualification-stage-v1'


class ExactLintAcceptanceTests(unittest.TestCase):
    def test_only_exact_known_observation_accepted_as_debt(self):
        result=gate.accept(LINT,STAGE/'manifest.json',STAGE/'source/fpga')
        self.assertEqual(result['raw_returncode'],1)
        self.assertFalse(result['clean_lint']);self.assertFalse(result['mutant_or_AW16_lint_accepted'])

    def test_new_missing_changed_secondary_error_and_truncation_rejected(self):
        raw=(LINT/'shared-control.stderr.log').read_bytes()
        mutants=[raw+b'%Warning-NEW: fake.sv:1:1: new warning\n',
            raw.replace(b'%Warning-DECLFILENAME:',b'%Warning-CHANGED:',1),
            raw.replace(b'138 |     always_ff',b'138 |     always   ',1),
            raw.replace(b"source_capture",b"source_changed",1),
            raw.replace(b'%Warning-DECLFILENAME:',b'%Warning-WIDTH:',1),
            raw.replace(b'%Warning-DECLFILENAME:',b'%Warning-UNOPTFLAT:',1),
            raw+b'%Error: Actual syntax error\n',raw[:-30],raw[raw.index(b'%Warning-',1):]]
        for mutant in mutants:
            self.assertNotEqual(mutant,raw)
            with self.assertRaises((ValueError,UnicodeError)):gate.diagnostics(mutant)

    def test_source_tool_command_exit_and_role_mismatch_rejected(self):
        for kind in ('source','tool','command','exit','role'):
            with tempfile.TemporaryDirectory() as name:
                out=Path(name)
                for p in LINT.glob('*.log'):shutil.copyfile(p,out/p.name)
                report=json.loads((LINT/'report.json').read_text())
                if kind=='source':report['sources'][next(iter(report['sources']))]='0'*64
                elif kind=='tool':report['tools'][next(iter(report['tools']))]='0'*64
                elif kind=='command':report['steps'][0]['command'].append('-Wno-fatal')
                elif kind=='exit':report['steps'][0]['returncode']=0
                else:report['steps'][0]['role']='omitted_tee'
                (out/'report.json').write_text(json.dumps(report))
                with self.assertRaises(ValueError):gate.accept(out,STAGE/'manifest.json',STAGE/'source/fpga')

    def test_source_bytes_and_extra_file_rejected(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name).resolve()/'fpga';shutil.copytree(STAGE/'source/fpga',root)
            first=next(root.rglob('*.sv'));original=first.read_bytes();first.write_bytes(original+b'\n')
            with self.assertRaisesRegex(ValueError,'source byte drift'):gate.accept(LINT,STAGE/'manifest.json',root)
            first.write_bytes(original);(root/'extra.pyc').write_bytes(b'extra')
            with self.assertRaisesRegex(ValueError,'closed canonical'):gate.accept(LINT,STAGE/'manifest.json',root)


if __name__=='__main__':unittest.main()
