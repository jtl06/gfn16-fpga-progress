"""Memory-only envelope source checks; no native sufficiency claim."""
import json
import unittest
from fpga.tests.test_native_shared_v1 import SharedNativeTests
from fpga.tools import native_class_gcp24_v1 as c, native_class_package_gcp24_v1 as p, native_stage_gcp24_v1 as s
from fpga.tools import native_profile_variants_v5 as variants


class Gcp24Tests(SharedNativeTests):
    def test_pair_caps_and_reserve(self):
        for pair,cpus in [('01',[0,1]),('23',[2,3])]:
            profile=c.profile('gcp-c4d-static24g'+pair+'-v1')
            self.assertEqual(profile['cpus'],cpus)
            self.assertEqual(profile['memory_bytes'],24<<30)
            self.assertEqual(profile['minimum_host_available_bytes'],32<<30)
            self.assertEqual(profile['compile_workers'],2)
            self.assertEqual(profile['model_threads'],1)
            self.assertEqual(profile['cpu_quota_percent'],200)
            parent=c.parent(profile['profile_id'])
            self.assertEqual(parent.PROFILES[profile['host']]['memory_bytes'],24<<30)
        with self.assertRaises(ValueError):c.profile('gcp-c4d-static24g04-v1')

    def test_closed_package_preserves_functional_inputs(self):
        for pair in ('01','23'):
            out=self.root/pair
            result=p.prepare(self.manifest,self.source,'gcp-c4d-static24g'+pair+'-v1',
                             'memory-only-'+pair,'run',out,self.budget_path)
            manifest=json.loads((out/'manifest.json').read_text())
            for key in ('build','probe','steps'):self.assertEqual(manifest[key],self.m[key])
            for name,pin in self.m['sources'].items():self.assertEqual(manifest['sources'][name],pin)
            self.assertEqual(variants.functional_fingerprint(manifest)['sha256'],
                             variants.functional_fingerprint(self.m)['sha256'])
            inspected=s.worker().inspect_archive(out/'package.tar.gz',result['archive_sha256'],result['ticket_sha256'])
            self.assertEqual(inspected[3]['memory_bytes'],24<<30)
            with self.assertRaises(ValueError):s.worker().inspect_archive(out/'package.tar.gz','0'*64,result['ticket_sha256'])


if __name__=='__main__':unittest.main()
