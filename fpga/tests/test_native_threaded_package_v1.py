"""Matched-thread package selection and identity; no HDL execution."""
import copy
import json
import unittest
from fpga.tests.test_native_shared_v1 import SharedNativeTests
from fpga.tools import native_threaded_package_v1 as p, native_threaded_stage_v1 as s, native_threaded_class_v1 as c
from fpga.tools import build_identity_v2 as identity


class ThreadPackageTests(SharedNativeTests):
    def test_both_thread_counts_close_and_replay_identity_v2(self):
        keys=[]
        for count in (1,2):
            m=copy.deepcopy(self.m);m['build']['parameters']['AW']=16
            m['build']['runtime_threads']=count;m['build']['cflags'].append('-DGFN16_RUNTIME_THREADS='+str(count))
            m['probe']['expected_json']={key:count for key in ('model_threads','context_threads','expected_threads')}
            manifest=self.root/('thread'+str(count)+'.json');manifest.write_text(json.dumps(m))
            out=self.root/('packet'+str(count))
            result=p.prepare(manifest,self.source,'gcp-c4d-static01-v1','thread-pilot-'+str(count),'run',out,self.budget_path)
            prepared=json.loads((out/'manifest.json').read_text());ticket=json.loads((out/'ticket.json').read_text())
            expected=identity.build_identity(prepared,c.profile('gcp-c4d-static01-v1'))
            self.assertEqual(expected['build_key'],ticket['build_key']);keys.append(ticket['build_key'])
            self.assertEqual(expected['identity']['model_threads'],count)
            self.assertEqual(prepared['build'],m['build']);self.assertEqual(prepared['steps'],m['steps'])
            self.assertIn('tools/build_identity_v2.py',prepared['sources'])
            s.worker().inspect_archive(out/'package.tar.gz',result['archive_sha256'],result['ticket_sha256'])
        self.assertNotEqual(keys[0],keys[1])

    def test_probe_and_macro_drift_reject_before_output(self):
        m=copy.deepcopy(self.m);m['build']['parameters']['AW']=16
        m['build']['runtime_threads']=2;m['build']['cflags'].append('-DGFN16_RUNTIME_THREADS=2')
        self.manifest.write_text(json.dumps(m))
        with self.assertRaises(ValueError):
            p.prepare(self.manifest,self.source,'gcp-c4d-static01-v1','bad-thread','run',self.root/'bad',self.budget_path)
        self.assertFalse((self.root/'bad').exists())


if __name__=='__main__':unittest.main()
