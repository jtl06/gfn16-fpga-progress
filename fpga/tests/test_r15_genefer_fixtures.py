from pathlib import Path
import unittest

from fpga.host.r15_arithmetic import SoftwareBackend
from fpga.host.r15_genefer_proof import generate_proof
from fpga.host.r15_genefer_pl_fixture import check_upstream, proof_key


class SourceFixtures(unittest.TestCase):
    def test_exact_capture_no_execution(self):
        root=Path(__file__).resolve().parents[1]/'results/throughput-20260929/r15-host-software-v1/genefer22-source-pl-v1'
        check_upstream(root)

    def test_small_proof_key_bound(self):
        backend=SoftwareBackend(10,32,enabled=True)
        raw=generate_proof(backend,10**32,3,enabled=True)
        self.assertTrue(0 <= proof_key(backend,raw) < 1 << 64)
        self.assertEqual(proof_key(backend,raw),proof_key(backend,raw))


if __name__=='__main__':unittest.main()
