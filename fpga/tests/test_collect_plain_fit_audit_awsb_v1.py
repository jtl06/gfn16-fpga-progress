import hashlib
import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('awsb_collector',ROOT/'tools/collect_plain_fit_audit_awsb_v1.py')
mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)


class AWSBTests(unittest.TestCase):
    def test_exact_frozen_derivative(self):
        raw=(ROOT/'tools/collect_plain_fit_audit_v1.py').read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),mod.BASE_SHA)
        child=mod.derive(raw.decode()); restored=child
        for old,new in reversed(mod.CHANGES):
            self.assertEqual(restored.count(new),1); restored=restored.replace(new,old,1)
        self.assertEqual(restored,raw.decode())
        self.assertIn("ad.lock_names(ad.AWS,'b',physical)",child)
        self.assertIn("context['slot']=='b'",child)
        compile(child,'qualified-aws-b-derivative','exec')

    def test_anchor_tamper_refused(self):
        text=(ROOT/'tools/collect_plain_fit_audit_v1.py').read_text()
        for old,_ in mod.CHANGES:
            with self.assertRaises(ValueError): mod.derive(text.replace(old,'True',1))
            with self.assertRaises(ValueError): mod.derive(text+'\n'+old+'\n')


if __name__=='__main__': unittest.main()
