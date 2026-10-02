"""Source/metadata bridge checks only; no HDL or fullN arithmetic."""
import copy
import json
import unittest
from unittest.mock import patch
from fpga.reference import stream27_p8_canonpipe_qualification as q


class CanonicalBridge(unittest.TestCase):
    def test_same_eight_numeric_assets_labels_bits_and_once_per_job_cycles(self):
        donor=json.loads((q.DONOR/'manifest.json').read_text())
        m,files=q.role('normal')
        old=donor['p8_prp_qualification'];new=m['p8_prp_qualification']
        self.assertEqual(new['operations'],5000)
        self.assertEqual(new['host_cycles'],638440)
        self.assertEqual(new['host_cycles']-old['host_cycles'],8*3*32)
        self.assertEqual(new['reads'],256)
        for before,after in zip(old['cases'],new['cases']):
            self.assertEqual(after['cycles']-before['cycles'],96)
            for field in before.keys()-{'cycles'}:self.assertEqual(before[field],after[field])
        for name in ('assets/p8-eight-prp-v1.txt','assets/p8-eight-prp-oracle-v1.json'):
            self.assertEqual(q.sha(files[name]),donor['sources'][name])
        self.assertTrue(m['steps'][0]['expected_stdout'].endswith('cycles=638440 base_floor=172\n'))

    def test_exact_compiler_source_and_unique_helper_bindings(self):
        m,files=q.role('normal')
        b=q.compiler.prepare(32,8,paired=True,contexts=1,canonical_pipe_stages=1)
        self.assertEqual(m['build']['parameters']['CANONICAL_PIPE_STAGES'],1)
        self.assertEqual(m['build']['sv_sources'],['rtl/'+name for name in b['rtl_sources']])
        for name,text in b['files'].items():self.assertEqual(files['rtl/'+name],text.encode())
        scalar=files[q.SCALAR].decode();helper=files[q.HELPER].decode()
        self.assertEqual(scalar.count('(job.expected[0]==-1?10u:9u)*N'),2)
        self.assertNotIn('?7u:6u',scalar)
        self.assertEqual(helper.count('?10u:9u'),2)
        self.assertNotIn('?7u:6u',helper)
        self.assertIn('#include "stream27_p8_canonpipe_scalar_v1.cpp"',helper)
        self.assertIn('#include "stream27_p8_canonpipe_config_v1.h"',scalar)
        self.assertEqual(q.sha((q.DONOR/'manifest.json').read_bytes()),q.DONOR_SHA)

    def test_faults_separate_same_candidate_exact_expectations(self):
        normal,nfiles=q.role('normal');fault,ffiles=q.role('faults')
        self.assertEqual(normal['build']['top'],fault['build']['top'])
        self.assertEqual(normal['build']['parameters'],fault['build']['parameters'])
        for name in normal['build']['sv_sources']+[q.HELPER,q.SCALAR,q.CONFIG]:
            self.assertEqual(nfiles[name],ffiles[name])
        self.assertEqual(len(fault['steps']),2)
        self.assertEqual(fault['steps'][1]['expected_returncode'],1)
        self.assertIn('expected=19 actual=18',fault['steps'][1]['expected_stderr'])
        self.assertNotIn('p8_prp_qualification',fault)

    def test_drifted_compiler_and_wrong_helper_anchor_reject(self):
        with patch.object(q,'COMPILER_SHA','0'*64),self.assertRaises(ValueError):q.role('normal')
        with self.assertRaises(ValueError):q.replace_once('duplicate duplicate','duplicate','new')
        with self.assertRaises(ValueError):q.role('unknown')


if __name__=='__main__':unittest.main()
