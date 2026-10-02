"""Collected-artifact/config/provenance checks only; no arithmetic/GMP/HDL."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('_cross_runtime',ROOT/'reference/core27_t5b_soak_cross_runtime_v1.py')
CROSS=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(CROSS)


def assets(target='f16'):
    ticket_path=ROOT/'queue/done/soak-t5b-aw16-short-reference-q3-v1.json'
    ticket=json.loads(ticket_path.read_text());evidence=Path(ticket['result']['evidence'])
    refs=evidence/'output/reference'
    return {
        'oracle':(refs/'continuous.json').read_text(),
        'generation':(refs/'generation.json').read_text(),
        'generation-admission':(refs/'auxiliary-runtime-admission.json').read_text(),
        'generation-runtime':(ROOT/'results/throughput-20260929/soak-gmpy2-gcp-runtime-v1/module-manifest.json').read_text(),
        'runtime':(ROOT/('results/throughput-20260929/soak-azure-'+target+'-runtime-v1/runtime.json')).read_text(),
        'reference-config':Path(ticket['package']['config']).read_text(),
        'reference-report':(evidence/'output/command-report.json').read_text(),
        'reference-execution':ticket_path.read_text(),
    }


class CrossRuntime(unittest.TestCase):
    def test_original_and_target_are_explicitly_distinct(self):
        for target in ('f16','f32'):
            original,replay,oracle=CROSS.binding(assets(target))
            self.assertEqual(original['host'],'gfn16-pilot-c4d')
            self.assertEqual(original['package_version'],'2.3.1')
            self.assertEqual(replay['package_version'],'2.2.1')
            generated=oracle['oracle'];current={**generated,**CROSS.runtime_identity(replay)}
            before=copy.deepcopy(generated)
            CROSS.verify_pair(current,generated,original,replay)
            self.assertEqual(generated,before)
            self.assertNotEqual(generated['python_sha256'],current['python_sha256'])

    def test_each_runtime_identity_field_is_required(self):
        original,target,oracle=CROSS.binding(assets())
        generated=oracle['oracle'];current={**generated,**CROSS.runtime_identity(target)}
        for identity in CROSS.IDENTITY_KEYS:
            for role in ('generation','target'):
                a,b=copy.deepcopy(current),copy.deepcopy(generated)
                (b if role=='generation' else a)[identity]='unbound-description'
                with self.assertRaisesRegex(ValueError,'IDENTITY'):
                    CROSS.verify_pair(a,b,original,target)

    def test_math_method_modulus_and_unknown_fields_cannot_change(self):
        original,target,oracle=CROSS.binding(assets());generated=oracle['oracle']
        current={**generated,**CROSS.runtime_identity(target)}
        for key in CROSS.MATH_KEYS:
            altered=copy.deepcopy(current);altered[key]='changed'
            with self.assertRaisesRegex(ValueError,'INTEGER_METHOD_MODULUS'):
                CROSS.verify_pair(altered,generated,original,target)
        current['extra']='unbound'
        with self.assertRaisesRegex(ValueError,'COMPLETE_PROVENANCE'):
            CROSS.verify_pair(current,generated,original,target)

    def test_unbound_asset_bytes_reject(self):
        for name in ('runtime','generation-runtime','reference-config','reference-report',
                     'generation','generation-admission','oracle'):
            value=assets();value[name]=value[name]+'\n'
            with self.assertRaises((ValueError,KeyError)):
                CROSS.binding(value)

    def test_unknown_or_missing_asset_reject(self):
        value=assets();value['extra']='{}'
        with self.assertRaisesRegex(ValueError,'EXACT_ASSETS'):
            CROSS.binding(value)
        value=assets();value.pop('reference-execution')
        with self.assertRaisesRegex(ValueError,'EXACT_ASSETS'):
            CROSS.binding(value)

    def test_command_receipt_failure_cannot_be_recast_as_pass(self):
        value=assets();ticket=json.loads(value['reference-execution'])
        ticket['result']['properties']['ExecMainStatus']='1'
        value['reference-execution']=json.dumps(ticket)
        with self.assertRaisesRegex(ValueError,'REFERENCE_EXECUTION_BINDING'):
            CROSS.binding(value)

    def test_missing_or_extra_boundaries_reject_before_numeric_work(self):
        for mode in ('missing','extra'):
            value=assets();oracle=json.loads(value['oracle'])
            if mode=='missing':oracle['segment']['checkpoints'].pop(1)
            else:oracle['segment']['checkpoints'].append(oracle['segment']['checkpoints'][-1])
            value['oracle']=json.dumps(oracle)
            with self.assertRaisesRegex(ValueError,'ALL_BOUNDARIES_REQUIRED'):
                CROSS.binding(value)


if __name__=='__main__':
    unittest.main()
