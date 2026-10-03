"""Synthetic small transcript sensitivity only, not native B equivalence."""
import copy
import json
import importlib.util
import unittest
from unittest import mock

from fpga.reference import stream27_r14_host_offload_equivalence_native as eq


def fixture(special=False):
    n, base, generation, epoch, count = 256, 1009, 1, 65534, 2
    expected = dict(label='synthetic-special' if special else 'synthetic-dense',
                    n=n, p=16, context=0, base=base, generation=generation,
                    epoch_seed=epoch, count=count, special=special)
    setup = eq.model.profile(n, 16, base, generation)
    digits = [0]*n if special else [(j*17)%base for j in range(n)]
    c0 = [-1]+[0]*15 if special else [0]*16
    c1 = [0]*16
    source = [0]*n
    source[n//2] = 1
    cold = eq.model.prepare_cold(source, [0]*16, [0]*16, setup, context=0, epoch=epoch)
    raw = [digits[lane*16+row] for row in range(16) for lane in range(16)] + c0+c1
    canonical = [-1]+[0]*(n-1) if special else digits
    final_owner = ((count-1)<<24) | (((epoch+count-1)&65535)<<8) | generation
    value = {k:expected[k] for k in expected if k != 'special'}
    value.update(input_owner=(epoch<<8)|generation, owner=final_owner,
                 input=eq.wire_bytes(source+[0]*32).hex(),
                 cold=eq.model.cold_payload_bytes(cold).hex(),
                 profile=eq.model.profile_payload_bytes(setup).hex(),
                 raw_twin=eq.wire_bytes(raw).hex(), raw_b=eq.wire_bytes(raw).hex(),
                 canonical_twin=eq.wire_bytes(canonical).hex(),
                 canonical_host=eq.wire_bytes(canonical).hex(),
                 reference=eq.wire_bytes(canonical).hex())
    config = dict(packets=[expected], footer='R14_B_EQ_SYNTHETIC_PASS')
    return value, config


def transcript(value, config):
    return 'R14_B_EQ_PACKET '+json.dumps(value)+'\n'+config['footer']+'\n'


class ComparisonContractTests(unittest.TestCase):
    def test_dynamic_native_callback_import_without_package_name(self):
        spec=importlib.util.spec_from_file_location('_native_result_validator',eq.ROOT/eq.SELF)
        callback=importlib.util.module_from_spec(spec);spec.loader.exec_module(callback)
        value,config=fixture()
        self.assertEqual(callback.validate(transcript(value,config),'',0,config,{})['status'],
                         'PASS_expected_contracts')

    def test_full_role_keeps_numeric_geometry_and_source_specific_counts(self):
        manifest,files,bundle=eq.role('full')
        config=manifest['steps'][0]['validator']['config']
        self.assertEqual([p['n'] for p in config['packets']],[65536,65536])
        self.assertEqual([p['count'] for p in config['packets']],[2,2])
        self.assertIn('n=65536 contexts=2 counts=2/2',config['footer'])
        self.assertIn('R14_B_ACTUAL_WARM_TO_RAW_DONE_TWO_EDGES',files[eq.CPP].decode())
        self.assertEqual(len(manifest['build']['sv_sources']),67)

    def test_special_role_requires_actual_raw_and_special_minus_one(self):
        manifest,files,bundle=eq.role('special')
        config=manifest['steps'][0]['validator']['config']
        self.assertEqual([p['count'] for p in config['packets']],[3,5])
        self.assertTrue(all(p['special'] for p in config['packets']))
        self.assertIn('&&info.special',files[eq.CPP].decode())
        self.assertIn('EXPECT_CAPTURE_COPY=false',files['rtl/tb/s4_host_contexts_config_v1.h'].decode())
        self.assertIn('CANON_PASSES=10',files['rtl/tb/s4_host_contexts_config_v1.h'].decode())

    def test_full_special_is_actual_impulse_and_ten_pass_twin_not_local_math(self):
        manifest,files,bundle=eq.role('fullspecial')
        config=manifest['steps'][0]['validator']['config']
        self.assertEqual([p['n'] for p in config['packets']],[65536,65536])
        self.assertEqual([p['count'] for p in config['packets']],[1,1])
        self.assertTrue(all(p['special'] for p in config['packets']))
        self.assertIn('INITIAL[0][N/2]=INITIAL[1][N/2]=1',files[eq.CPP].decode())
        self.assertIn('lane64(d.canonical_cycles,ctx)==10*N',files['rtl/tb/stream27_r14_twin_driver.cpp'].decode())

    def test_control_extent_and_nonzero_failure_are_not_waived(self):
        manifest,files,bundle=eq.role('controls');step=manifest['steps'][1]
        config=step['validator']['config']
        lines=['R14_B_HOST_ATOMIC_PASS final_cases=6 cold_cases=5']+[
            'R14_B_CONTROL_CASE '+n+' abort=1 quiet=24' for n in eq.CONTROL_CASES]+[
            'R14_B_CONTROL_PASS chip_cases=20 host_cases=11 quiet_edges=480 reset_recovery=1 public_pins_only=1']
        body='\n'.join(lines)+'\n'
        self.assertEqual(eq.validate_controls(body,'',0,config,{})['actual_public_pin_chip_cases'],20)
        for text,err,rc in ((lines[-1]+'\n','',0),(body,'',1),(body,'bad\n',0)):
            with self.assertRaises(ValueError):eq.validate_controls(text,err,rc,config,{})
        self.assertEqual(manifest['test_role'],'deliberate_fault')
        self.assertEqual(step['argv'],['{exe}','--controls'])
        self.assertNotIn('force(',files[eq.CPP].decode())

    def test_prp_complete_exponent_feed_and_independent_scalar_asset(self):
        manifest,files,bundle=eq.role('prp')
        oracle=json.loads(files['reference-assets/r14-prp-n256.json'])
        self.assertEqual(oracle['counts'],[2555,2811])
        self.assertTrue(oracle['leading_bit_included'])
        for c,base in enumerate(oracle['bases']):
            self.assertEqual(oracle['bits'][c],bin(base**256)[2:])
            value=sum(d*base**i for i,d in enumerate(oracle['expected'][c]))
            self.assertEqual(value,pow(2,base**256,base**256+1))
        self.assertIn('#define R14_PRP 1',files['rtl/tb/s4_host_contexts_config_v1.h'].decode())
        self.assertIn('R14_PRP_TWIN_COMPLETE_NO_CHECKPOINT',files[eq.CPP].decode())

    def test_actual_dual_source_normal_role_and_every_parameter(self):
        manifest, files, bundle = eq.role()
        self.assertEqual(len(manifest['build']['sv_sources']), 67)
        self.assertEqual(bundle['parameters']['HOST_OFFLOAD'], 1)
        shell = files['rtl/tb/stream27_r14_host_offload_equivalence.sv'].decode()
        self.assertIn('.HOST_OFFLOAD(0)', shell)
        self.assertIn('.HOST_OFFLOAD(1)', shell)
        self.assertNotRegex(shell, r'\b(always|initial|force)\b')
        for parameter in manifest['build']['parameters']:
            if parameter != 'HOST_OFFLOAD':
                self.assertIn('.'+parameter+'('+parameter+')', shell)
        for name in eq.MODEL_CLOSURE:
            self.assertIn(name, files)
        cpp = files[eq.CPP].decode()
        self.assertLess(cpp.index('gfn16_runtime::configure(context,argc,argv)'),
                        cpp.index('DUT d(&context)'))
        self.assertEqual(cpp.count('DUT d(&context)'), 1)
        self.assertIn('raw_twin', cpp)
        self.assertIn('gfn16_b_cold_write', cpp)
        self.assertIn('gfn16_b_final_decode', cpp)

    def test_dense_and_special_actual_body_contract(self):
        for special in (False, True):
            value, config = fixture(special)
            result = eq.validate(transcript(value, config), '', 0, config, {})
            self.assertEqual(result['status'], 'PASS_expected_contracts')
            self.assertEqual(result['packets'][0]['special'], special)
            self.assertFalse(result['independent_review'])
            self.assertFalse(result['promotion_allowed'])

    def test_footer_cannot_substitute_raw_final_arrays(self):
        value, config = fixture()
        for payload in (config['footer']+'\n', transcript(value, config)+'unexpected\n'):
            with self.assertRaises(ValueError):
                eq.validate(payload, '', 0, config, {})
        for key in ('input', 'cold', 'profile', 'raw_twin', 'raw_b',
                    'canonical_twin', 'canonical_host', 'reference'):
            wrong = copy.deepcopy(value)
            wrong[key] = wrong[key][:-8]
            with self.subTest(key=key), self.assertRaises(ValueError):
                eq.validate(transcript(wrong, config), '', 0, config, {})

    def test_numeric_profile_owner_context_and_mutant_body_reject(self):
        value, config = fixture()
        for key in ('cold', 'profile', 'raw_b', 'canonical_twin', 'canonical_host', 'reference'):
            wrong = copy.deepcopy(value)
            raw = bytearray.fromhex(wrong[key]); raw[0] ^= 1; wrong[key] = raw.hex()
            with self.subTest(key=key), self.assertRaises(ValueError):
                eq.validate(transcript(wrong, config), '', 0, config, {})
        for key, delta in (('owner', 1<<48), ('owner', 1<<8), ('input_owner', 1),
                           ('context', 1), ('generation', 1), ('count', 1)):
            wrong = copy.deepcopy(value); wrong[key] ^= delta
            with self.subTest(key=key, delta=delta), self.assertRaises(ValueError):
                eq.validate(transcript(wrong, config), '', 0, config, {})

    def test_c1_is_unscaled_and_cold_layout_is_reverse4(self):
        value, config = fixture()
        setup = eq.model.profile(256, 16, 1009, 1)
        packet = eq.model.prepare_cold(list(range(256)), [0]*16, [1]*16,
                                       setup, context=0, epoch=65534)
        for plane in packet.correction_high:
            self.assertEqual(plane, (1,)*16)
        self.assertEqual(packet.field_rows[0][0][1], 128)

    def test_full_payload_rejected_before_any_local_conversion(self):
        value, config = fixture(); config['packets'][0]['n'] = 65536
        with mock.patch.object(eq.sys, 'platform', 'darwin'), \
             mock.patch.object(eq.model, 'profile') as profile:
            with self.assertRaisesRegex(ValueError, 'ADMITTED_LINUX_ONLY'):
                eq.validate(transcript(value, config), '', 0, config, {})
            profile.assert_not_called()

    def test_process_contract_is_exact_not_rc_boolean_or_stderr_waiver(self):
        value, config = fixture()
        for stderr, code in (('unexpected', 0), ('', 1), ('', False)):
            with self.assertRaises(ValueError):
                eq.validate(transcript(value, config), stderr, code, config, {})


if __name__ == '__main__':
    unittest.main()
