import importlib.util
import hashlib
import json
from pathlib import Path
import tarfile
import unittest

ROOT=Path(__file__).resolve().parents[1]


def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    value=importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
    return value


class AuditCollectionTests(unittest.TestCase):
    def setUp(self):
        self.audit=module('audit_collection_test',ROOT/'tools/collect_plain_fit_audit_v1.py')
        self.terminal=module('terminal_collection_test',ROOT/'tools/collect_plain_fit_v1.py')

    def test_time_binding(self):
        proof=dict(manager_start_realtime_us='1790856768133561',manager_end_realtime_us='1790857177449564')
        self.audit.time_bound('2026-10-01T12:19:37.431909+00:00',proof)
        with self.assertRaises(ValueError): self.audit.time_bound('2026-10-01T13:00:00+00:00',proof)

    def test_source_tamper(self):
        with self.assertRaises(ValueError): self.audit.load('tamper',ROOT/'tools/collect_plain_fit_v1.py','0'*64)

    def test_gc_requires_manager_proof(self):
        unit='gfn16-audit-c1-8-9580-v1.service'; inv='20d77a3e45704ebb8be6852b957bc7b9'
        self.terminal.quiescent(dict(MainPID='0',ActiveState='inactive',SubState='dead',InvocationID=''),inv)
        with self.assertRaises(ValueError): self.terminal.journal_proof([],unit,inv)
        rows=[dict(_PID='1',UNIT=unit,INVOCATION_ID=inv,JOB_TYPE='start',JOB_RESULT='done',
                   __MONOTONIC_TIMESTAMP='22514788101',__REALTIME_TIMESTAMP='1790856768133561'),
              dict(_PID='1',UNIT=unit,INVOCATION_ID=inv,MESSAGE=unit+': Deactivated successfully.',
                   __MONOTONIC_TIMESTAMP='22924104104',__REALTIME_TIMESTAMP='1790857177449564')]
        proof,_=self.terminal.journal_proof(rows,unit,inv)
        self.assertAlmostEqual(proof['manager_elapsed_seconds'],409.316003)
        with self.assertRaises(ValueError): self.terminal.journal_proof(rows,unit,'0'*32)

    def test_actual_c1_journal_and_pin_negative(self):
        archive=ROOT/'results/throughput-20260929/c1-8-9580-timing-audit-v1/native-audit.tar.gz'
        if not archive.exists(): self.skipTest('actual local C1 archive not present')
        with tarfile.open(archive,'r:gz') as tar:
            raw=tar.extractfile('collection/native-journal.jsonl').read()
            rows=[json.loads(row) for row in raw.splitlines()]
            proof,_=self.terminal.journal_proof(rows,'gfn16-audit-c1-8-9580-v1.service','20d77a3e45704ebb8be6852b957bc7b9')
            self.assertEqual(proof['terminal_kind'],'deactivated_successfully')
            self.assertEqual(proof['manager_elapsed_seconds'],409.316003)
            with self.assertRaises(ValueError):
                self.terminal.journal_proof(rows,'gfn16-audit-c1-8-9580-v1.service','f'*32)
            receipt=tar.extractfile('audit/receipt.json').read()
            self.assertEqual(hashlib.sha256(receipt).hexdigest(),'d8dfd981eb645f0202e048f85fbcfa6ff20951c14373a2bb75015b559d72a556')
            self.assertNotEqual(hashlib.sha256(receipt+b' ').hexdigest(),hashlib.sha256(receipt).hexdigest())
            result=json.loads(receipt)
            self.assertTrue(result['original_unchanged'] and result['compiled_input_unchanged'])
            self.assertEqual(result['final_verification_errors'],[])


if __name__=='__main__': unittest.main()
