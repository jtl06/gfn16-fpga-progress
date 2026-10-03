"""Bounded source/packet fixtures; never execute HDL or full-N arithmetic."""
import copy
import json
from pathlib import Path
import unittest
from unittest import mock

from fpga.reference import stream27_host_offload_endpoint_native as source
from fpga.reference import stream27_host_offload_endpoint_output as output


def hex_words(values):
    return b''.join((v & 0xffffffff).to_bytes(4, 'little') for v in values).hex()


def fixture(mode='dense'):
    packets = []
    for c, base in enumerate((1009, 2017)):
        count = 1 if mode == 'sentinel' else (3, 14)[c]
        owner = ((count-1) << 24) | ((((65534, 42)[c]+count-1) & 65535) << 8) | 1
        digits = [0]*256 if mode == 'sentinel' else [(j*17+c)%base for j in range(256)]
        c0 = [-1]+[0]*15 if mode == 'sentinel' else [0]*16
        canonical = [-1]+[0]*255 if mode == 'sentinel' else digits
        raw = [digits[lane*16+row] for row in range(16) for lane in range(16)] + c0 + [0]*16
        packets.append(dict(label='sentinel' if mode == 'sentinel' else 'dense', n=256, p=16,
            context=c, base=base, owner=owner, rows=16, boundaries=1, words=256,
            raw=hex_words(raw), actual=hex_words(canonical), reference=hex_words(canonical)))
    return packets


def transcript(packets, mode='dense'):
    footer = ('B_ENDPOINT_SENTINEL_PASS ' + json.dumps(dict(n=256,p=16,squares=2,reads=512,
        special=True,signed96=True,independent_reference=True)) if mode == 'sentinel' else
        'S4_HOST_CONTEXTS_PASS kind=dense aw=8 p=16 counts=3/14 chains=2 squares=17 reads=1024 peer_live_reads=256 waiting_b=1 capture_during_copy=1 canonical_peer_arithmetic=1 owner_bits=56 signed96=1 canonical_host=1')
    return ''.join('B_ENDPOINT_PACKET '+json.dumps(p)+'\n' for p in packets)+footer+'\n'


class EndpointTests(unittest.TestCase):
    def test_both_immutable_captures_preserved_and_only_native_wrapper_added(self):
        for stage in ('aw8','full'):
            before, originals, bundle = source.capture(stage)
            manifest, files, production = source.role(stage)
            self.assertEqual(production, bundle)
            self.assertEqual(len(production['files']),53)
            self.assertTrue(all(files[name]==raw for name,raw in originals.items()))
            self.assertEqual(manifest['build']['parameters'],before['build']['parameters'])
            self.assertEqual(manifest['probe'],before['probe'])
            self.assertEqual(len(manifest['build']['sv_sources']),54)
            for name, pin in bundle['generated_sha256'].items():
                self.assertEqual(source.sha(files['rtl/'+name]),pin)
            self.assertEqual(manifest['host_offload_endpoint']['hardware_trimmed'],False)

    def test_stateless_taps_and_true_live_owner_and_pre_edge(self):
        for stage in ('aw8','full'):
            m,files,b=source.role(stage)
            wrapper=files['rtl/'+m['build']['top']+'.sv'].decode()
            self.assertNotRegex(wrapper,r'\b(always|always_ff|always_comb|initial)\b')
            self.assertIn("16'(candidate.boundary_epoch-16'd1)",wrapper)
            self.assertIn('candidate.live_owner[candidate.final_context*56+:56]',wrapper)
            cpp=files[m['build']['cpp_source']].decode()
            self.assertIn('d.clk=0;d.eval();offload.pre(d);d.clk=1;d.eval();',cpp)
            self.assertIn('offload_sentinel(d)',cpp)
            original=files[source.capture(stage)[0]['build']['cpp_source']].decode()
            # Every existing assertion diagnostic survives the private adaptation.
            import re
            self.assertTrue(set(re.findall(r'"(?:S4_HOST_CONTEXT|R84_)[A-Z0-9_]+',original)) <=
                            set(re.findall(r'"(?:S4_HOST_CONTEXT|R84_)[A-Z0-9_]+',cpp)))

    def test_guarded_adaptation_rejects_ambiguous_source(self):
        with self.assertRaisesRegex(ValueError,'UNIQUE_PRIVATE'):
            source.replace_once('same same','same','new')
        with self.assertRaises(ValueError):
            source.capture('aw5')

    def test_exact_finalizer_with_dense_and_special_row_layout(self):
        for mode in ('dense','sentinel'):
            result=output.validate(transcript(fixture(mode),mode),'',0,dict(stage='aw8',mode=mode),{})
            self.assertEqual(result['status'],'PASS_expected_contracts')
            self.assertTrue(result['exact_frozen_finalizer'])
            self.assertEqual([p['special'] for p in result['packets']],[mode=='sentinel']*2)
            self.assertFalse(result['native_trimmed_core'])

    def test_full_size_rejected_before_decode_on_coordinator(self):
        with mock.patch.object(output.sys,'platform','darwin'), mock.patch.object(output.model,'profile') as profile:
            with self.assertRaisesRegex(ValueError,'ADMITTED_LINUX_ONLY'):
                output.packet({},65536,'dense')
            profile.assert_not_called()

    def test_bad_wire_owner_layout_boundary_actual_and_reference_reject(self):
        for key,value in [('owner',1),('rows',15),('boundaries',2),('context',True),
                          ('raw','00'),('actual',hex_words([1]*256)),('reference',hex_words([1]*256))]:
            packets=fixture();packets[0][key]=value
            with self.subTest(key=key), self.assertRaises(ValueError):
                output.validate(transcript(packets),'',0,dict(stage='aw8',mode='dense'),{})
        packets=fixture();raw=bytearray.fromhex(packets[0]['raw']);raw[0:4]=(1009).to_bytes(4,'little');packets[0]['raw']=raw.hex()
        with self.assertRaises(ValueError):
            output.validate(transcript(packets),'',0,dict(stage='aw8',mode='dense'),{})

    def test_missing_reordered_packets_footer_or_wrong_command_reject(self):
        normal=transcript(fixture())
        bad=(transcript(fixture()[::-1]),normal.replace('reads=1024','reads=1023'),
             normal.splitlines()[0]+'\n',normal+'unexpected\n')
        for text in bad:
            with self.assertRaises(ValueError):
                output.validate(text,'',0,dict(stage='aw8',mode='dense'),{})
        for stderr,code in (('diagnostic',0),('',1),('',True)):
            with self.assertRaises(ValueError):
                output.validate(normal,stderr,code,dict(stage='aw8',mode='dense'),{})


if __name__=='__main__':
    unittest.main()
