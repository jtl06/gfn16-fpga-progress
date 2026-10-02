import copy
from datetime import datetime,timedelta,timezone
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from fpga.cloud import aws_fit_m8azn12_v1 as p


class M8aznPolicyTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,10,1,3,tzinfo=timezone.utc)
        self.rows=[dict(cpu=i,package_id=0,core_id=i) for i in range(12)]
        self.total=47252*(1<<20)
        self.document=p.document(self.rows,self.total,self.now)

    def validate(self,document=None,slot='a',affinity=None,rows=None,now=None):
        return p.validate_topology(document or self.document,slot,
                                   affinity or list(range(4) if slot=='bench' else range(6) if slot=='a' else range(6,12)),
                                   rows or self.rows,p.runner.HOST,now or self.now)

    def test_two_six_slots_and_exclusive_four_worker_benchmark(self):
        a=self.validate();b=self.validate(slot='b');bench=self.validate(slot='bench')
        self.assertEqual(a['affinity'],list(range(6)))
        self.assertEqual(b['affinity'],list(range(6,12)))
        self.assertFalse(set(map(tuple,a['physical_cores']))&set(map(tuple,b['physical_cores'])))
        self.assertEqual(bench['affinity'],[0,1,2,3])
        self.assertEqual(bench['reserved_cpus'],list(range(4,12)))
        self.assertEqual(a['actual_two_fit_host_headroom_bytes'],self.total-(40<<30))

    def test_no_cpu_core_numbering_or_smt_assumption(self):
        rows=[dict(cpu=i,package_id=i%2,core_id=100+i) for i in range(12)]
        document=p.document(rows,self.total,self.now)
        self.assertEqual(self.validate(document=document,rows=rows)['physical_cores'][0],(0,100))

    def test_overlap_extra_slots_oversubscription_and_wrong_affinity(self):
        changes=[('overlap',lambda d:d['slots']['b'].__setitem__(0,5)),
                 ('extra',lambda d:d['slots'].__setitem__('c',[8,9,10,11])),
                 ('seven_workers',lambda d:d['slots']['a'].append(6)),
                 ('ram',lambda d:d.__setitem__('fit_memory_max_bytes',24<<30))]
        for label,change in changes:
            document=copy.deepcopy(self.document);change(document)
            with self.subTest(label=label),self.assertRaises(ValueError):self.validate(document=document)
        for slot in ('c','d','a,b'):
            with self.subTest(slot=slot),self.assertRaises(ValueError):self.validate(slot=slot)
        with self.assertRaisesRegex(ValueError,'affinity'):self.validate(affinity=[0,1,2,3])

    def test_stale_future_live_drift_and_old_profile_misuse(self):
        for age in (-1,86401):
            document=copy.deepcopy(self.document)
            document['observed_at']=(self.now-timedelta(seconds=age)).isoformat()
            with self.subTest(age=age),self.assertRaisesRegex(ValueError,'fresh'):self.validate(document=document)
        rows=copy.deepcopy(self.rows);rows[0]['core_id']=50
        with self.assertRaisesRegex(ValueError,'live topology'):self.validate(rows=rows)
        for key,value in (('schema','v6'),('profile','m8a16'),('instance_type','m8i.4xlarge')):
            document=copy.deepcopy(self.document);document[key]=value
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'old profiles'):self.validate(document=document)

    def test_smt_and_bad_actual_guest_memory_rejected(self):
        rows=copy.deepcopy(self.rows);rows[11]['core_id']=0
        document=copy.deepcopy(self.document);document['cpus']=rows
        with self.assertRaisesRegex(ValueError,'12logical/12physical'):self.validate(document=document,rows=rows)
        for total in ((44<<30)-1,(48<<30)+1):
            document=copy.deepcopy(self.document);document['memory_total_bytes']=total
            with self.subTest(total=total),self.assertRaisesRegex(ValueError,'guest memory'):self.validate(document=document)

    def test_exact_six20_and_four24_cgroups_and_ancestor_guards(self):
        p.validate_limits('600000 100000',str(20<<30))
        p.validate_limits('400000 100000',str(24<<30),workers=4,memory=24<<30)
        for cpu,memory in (('max 100000',20<<30),('400000 100000',20<<30),
                           ('700000 100000',20<<30),('600000 100000',24<<30)):
            with self.subTest(cpu=cpu,memory=memory),self.assertRaises(ValueError):
                p.validate_limits(cpu,str(memory))
        with self.assertRaisesRegex(ValueError,'only admitted'):
            p.validate_limits('800000 100000',str(24<<30),workers=8,memory=24<<30)
        with self.assertRaisesRegex(ValueError,'ancestor CPU'):
            p.validate_limits('600000 100000',str(20<<30),[('400000 100000','max')])

    def test_legacy_and_profile_locks_do_not_serialize_two6_slots(self):
        self.assertEqual(p.slot_locks(self.document,'a',[]),['m8azn12-a'])
        self.assertEqual(p.slot_locks(self.document,'b',[]),['m8azn12-b'])
        with tempfile.TemporaryDirectory() as folder:
            mode=Path(folder)/'mode';legacy=Path(folder)/'legacy'
            with p.compatibility_lock(mode,shared=True),p.compatibility_lock(mode,shared=True):
                with self.assertRaises(BlockingIOError):
                    with p.compatibility_lock(mode):pass
            with p.compatibility_lock(mode):
                with self.assertRaises(BlockingIOError):
                    with p.compatibility_lock(mode,shared=True):pass
            with p.compatibility_lock(legacy,shared=True),p.compatibility_lock(legacy,shared=True):
                with self.assertRaises(BlockingIOError):
                    with p.compatibility_lock(legacy):pass

    def test_frozen_source_pin_and_existing_guards_preserved(self):
        raw=(p.HERE/'aws_fit_v6.py').read_bytes();source=p.adapted_source(raw)
        self.assertEqual(p.V6_SHA,'ef66b020cf4317492c43a6baba6aea85f186e32dfdef6e7de7fa150a854e47a4')
        for token in ("'source SHA mismatch: '","'existing execution refused'",'os.O_NOFOLLOW',
                      "'.fit-physical-p{package}-c{core}.lock'","'topology file changed'",'str(TIMEOUT)'):
            self.assertIn(token,source)
        with self.assertRaisesRegex(ValueError,'source SHA'):p.adapted_source(raw+b'\n')


if __name__=='__main__':unittest.main()
