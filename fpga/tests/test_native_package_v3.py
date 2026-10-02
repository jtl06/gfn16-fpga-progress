"""Class packet safe staging and unchanged failure guards."""
import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from fpga.tools import native_package_v3 as stage, native_class_package_v1 as package
from fpga.tests.test_native_shared_v1 import SharedNativeTests


class ClassStageTests(SharedNativeTests):
    def prepared(self):
        out=self.root/'class-packet'
        result=package.prepare(self.manifest,self.source,'gcp-c4d-static23-v1','class-stage','run',out,self.budget_path)
        module=stage.worker()
        args=(out/'package.tar.gz',result['archive_sha256'],result['ticket_sha256'])
        return module,args,module.inspect_archive(*args)

    def test_complete_class_archive_then_safe_repeat(self):
        module,args,values=self.prepared()
        payload,ticket,manifest,profile=copy.deepcopy(values)
        self.assertEqual(profile['cpus'],[2,3])
        profile['base']=str(self.root/'native');profile['lock']=str(self.root/'native/compile.lock')
        profile['scratch_base']=str(self.root/'native/scratch-v2')
        ticket['native_root']=str(self.root/'native/jobs/class-stage')
        with patch.object(module,'inspect_archive',return_value=(payload,ticket,manifest,profile)),patch.object(module,'host_check'):
            first=module.stage(*args)
            root=Path(first['root']);(root/'output/keep').write_text('native evidence')
            second=module.stage(*args)
            self.assertEqual(second['status'],'already_staged_exact_inputs')
            self.assertEqual((root/'output/keep').read_text(),'native evidence')
            self.assertTrue(Path(profile['scratch_base']).is_dir())

    def test_profile_and_archive_drift_refuse(self):
        module,args,values=self.prepared()
        with self.assertRaises(ValueError):module.inspect_archive(args[0],'0'*64,args[2])
        payload,ticket,manifest,profile=values
        for key in ('tools/native_class_package_v1.py','tools/native_class_v1.py','cloud/gcp-native-thread-profiles-v1.json'):
            changed=copy.deepcopy(manifest['sources']);changed[key]='0'*64
            with self.assertRaises(ValueError):stage.profile_from_payload(payload,ticket,changed)
        changed=copy.deepcopy(ticket);changed['profile']='unknown'
        with self.assertRaises(ValueError):stage.profile_from_payload(payload,changed,manifest['sources'])


if __name__=='__main__':unittest.main()
