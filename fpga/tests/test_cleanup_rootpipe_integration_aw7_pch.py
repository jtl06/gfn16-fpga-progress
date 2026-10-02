import hashlib
from pathlib import Path
import re
import unittest
from fpga.tools import cleanup_rootpipe_integration_aw7_pch as aw7


class AW7CleanupCloneTests(unittest.TestCase):
    def test_exact_mechanical_clone_of_reviewed_helper(self):
        parent=Path(aw7.__file__).with_name('cleanup_rootpipe_integration_pch.py').read_text()
        self.assertEqual(hashlib.sha256(parent.encode()).hexdigest(),
            'df1de3a54ee39b626e1ea8827a984bea7d9ae9647175a9589f547add92122d32')
        child=Path(aw7.__file__).read_text()
        normalize=lambda text:re.sub(r'GATES=\{.*?\n\n\ndef stopped', 'GATES=REVIEWED\n\n\ndef stopped',text,flags=re.S)
        expected=parent.replace('Four exact regenerable PCH caches from two completed integration gates only.',
            'Two exact regenerable PCH caches from one completed AW7 integration gate only.')
        expected=expected.replace('rootpipe-integration-small-pch-cleanup-v1.json','rootpipe-integration-aw7-pch-cleanup-v1.json')
        expected=expected.replace('Regenerate four PCH caches','Regenerate two PCH caches')
        expected=expected.replace('removed_four_pch_caches_retained_hashes_verified','removed_two_pch_caches_retained_hashes_verified')
        self.assertEqual(normalize(child),normalize(expected))

    def test_exact_inventory_scope_report_and_two_cache_pins(self):
        self.assertEqual(set(aw7.GATES),{7})
        scope,report,kinds=aw7.GATES[7]
        self.assertEqual(scope,'gfn-core27-rootpipe-aw7-v1.scope')
        self.assertEqual(report,'cc0a83f3b698923b8f9a1e2c966cee1fe73d8405f67930530248e422dcc36525')
        self.assertEqual(kinds,{
            'fast':(101675475,101679104,'95d542406ecb7cf040fcc1b87db1cd81df0264441ca247ac5d72cd823d181b73'),
            'slow':(100405620,100409344,'7ced983ea4503e8d6eb866ca75bd15901ffb2967f2ba91ba714ef4e2478754be')})
        self.assertEqual(sum(value[1] for value in kinds.values()),202088448)
        self.assertEqual(str(aw7.RECEIPT),'/home/jtl/gfn-fpga-lab/fpga/tools/rootpipe-integration-aw7-pch-cleanup-v1.json')


if __name__=='__main__':unittest.main()
