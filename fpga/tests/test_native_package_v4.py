import unittest
from fpga.tests.test_native_shared_v1 import SharedNativeTests
from fpga.tools import native_class_package_v2 as package, native_package_v4 as stage


class StrictStageTests(SharedNativeTests):
    def test_strict_package_closure_and_profile(self):
        out=self.root/'strict-package'
        result=package.prepare(self.manifest,self.source,'gcp-c4d-static23-v1','strict-stage','run',out,self.budget_path)
        module=stage.worker()
        payload,ticket,manifest,profile=module.inspect_archive(out/'package.tar.gz',result['archive_sha256'],result['ticket_sha256'])
        self.assertEqual(profile['host'],'gfn16-pilot-c4d')
        self.assertEqual(profile['cpus'],[2,3])
        self.assertEqual(manifest['sources']['tools/native_class_package_v2.py'],stage.V2_SHA)
        changed=dict(manifest['sources']);changed['tools/native_class_package_v2.py']='0'*64
        with self.assertRaisesRegex(ValueError,'strict host-budget'):
            module.profile_from_payload(payload,ticket,changed)


if __name__=='__main__':unittest.main()
