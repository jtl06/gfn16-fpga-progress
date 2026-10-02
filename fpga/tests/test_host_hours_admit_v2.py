import importlib.util
from pathlib import Path
import unittest
import json
import shutil
import tempfile
from unittest.mock import patch
from datetime import datetime, timezone

root = Path(__file__).resolve().parents[1]
s = importlib.util.spec_from_file_location('meter', root/'cloud/host_hours_admit_v2.py')
m = importlib.util.module_from_spec(s); s.loader.exec_module(m)


class HostHoursTests(unittest.TestCase):
    def test_parallel_jobs_do_not_debit_or_double_charge(self):
        now = datetime(2026,10,1,7,38,tzinfo=timezone.utc)
        results = [m.admit('gcp-c4d',3715,now) for _ in range(8)]
        self.assertTrue(all(r['per_job_charge_usd']==0 for r in results))
        self.assertEqual(len({r['rolling24h_spend_upper_usd'] for r in results}),1)

    def test_aws_finite_audit_and_remaining(self):
        r=m.admit('aws-m8azn',2280,datetime(2026,10,1,7,38,tzinfo=timezone.utc))
        self.assertEqual(r['future_full_host_bound_usd'],.95)
        self.assertGreater(r['remaining_total_after_storage_usd'],69)

    def test_azure_unknown_host_and_unbounded_refused(self):
        for host in ('azure-f16','azure-sim-f32','unknown'):
            with self.assertRaises(m.g.Refused):m.admit(host,900)
        for seconds in (0,True,21841):
            with self.assertRaises(m.g.Refused):m.admit('gcp-c4d',seconds)

    def test_daily_cap_or_future_evidence_refused(self):
        with self.assertRaisesRegex(m.g.Refused,'host-hours cap'):
            m.admit('gcp-c4d',3715,datetime(2026,10,2,7,38,tzinfo=timezone.utc))
        with self.assertRaisesRegex(m.g.Refused,'future'):
            m.admit('gcp-c4d',3715,datetime(2026,10,1,5,0,tzinfo=timezone.utc))


    def test_latest50_admits_fit_rejected_by_frozen24_with_total_unchanged(self):
        now = datetime(2026,10,1,17,40,tzinfo=timezone.utc)
        result = m.admit('aws-m8azn',21780,now)
        self.assertEqual(result['rolling24h_cap_usd'],50)
        self.assertGreater(result['rolling24h_spend_upper_usd']+result['future_full_host_bound_usd'],24)
        self.assertLess(result['rolling24h_spend_upper_usd']+result['future_full_host_bound_usd'],50)
        self.assertEqual(result['hourly_rate_usd'],1.5)
        self.assertEqual(result['storage_other_reserve_usd'],5)
        self.assertEqual(result['per_job_charge_usd'],0)
        self.assertFalse(result['host_or_source_admission_conferred'])
        oldspec=importlib.util.spec_from_file_location('old_aws_daily',root/'cloud/host_hours_admit_v1.py')
        old=importlib.util.module_from_spec(oldspec);oldspec.loader.exec_module(old)
        with self.assertRaisesRegex(old.g.Refused,'host-hours cap'):
            old.admit('aws-m8azn',21780,now)

    def test_gcp_values_unchanged_except_explicit_schema_proof_closure(self):
        now=datetime(2026,10,1,7,38,tzinfo=timezone.utc)
        oldspec=importlib.util.spec_from_file_location('old_gcp_same_caps',root/'cloud/host_hours_admit_v1.py')
        old=importlib.util.module_from_spec(oldspec);oldspec.loader.exec_module(old)
        actual=m.admit('gcp-c4d',3715,now); previous=old.admit('gcp-c4d',3715,now)
        for key in previous:
            if key not in ('schema','source_evidence_sha256'):
                self.assertEqual(actual[key],previous[key],key)
        self.assertEqual(actual['schema'],'host-hours-admission-v2')
        self.assertNotIn(str(root/m.DAILY_AUTHORITY_PATH),actual['source_evidence_sha256'])

    def test_missing_tampered_latest_approval_and_parent_refused(self):
        paths=('cloud/owner-dispatch-budget-v1.json','docs/briefs/replies/2026-10-01-fit-queue-allowance-0600-v1.json',
               'cloud/host_hours_admit_v1.py',m.DAILY_AUTHORITY_PATH)
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory).resolve()
            for name in paths:
                path=target/name;path.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(root/name,path)
            with patch.object(m,'ROOT',target):
                now=datetime(2026,10,1,17,40,tzinfo=timezone.utc)
                approval=target/m.DAILY_AUTHORITY_PATH;original=approval.read_bytes()
                approval.unlink()
                with self.assertRaises((m.g.Refused,OSError)):
                    m.admit('aws-m8azn',21780,now)
                approval.write_bytes(original+b' ')
                with self.assertRaises(m.g.Refused):
                    m.admit('aws-m8azn',21780,now)
                approval.write_bytes(original)
                row=json.loads(original);row['change']['approved_cap']=36
                approval.write_text(json.dumps(row))
                with self.assertRaises(m.g.Refused):
                    m.admit('aws-m8azn',21780,now)
                approval.write_bytes(original)
                parent=target/'cloud/host_hours_admit_v1.py';parent.write_bytes(parent.read_bytes()+b' ')
                with self.assertRaisesRegex(m.g.Refused,'source drift'):
                    m.admit('aws-m8azn',21780,now)

    def test_total120_and_finite_horizon_not_raised(self):
        with self.assertRaisesRegex(m.g.Refused,'remaining total'):
            m.admit('aws-m8azn',21780,datetime(2026,10,3,17,40,tzinfo=timezone.utc))
        with self.assertRaisesRegex(m.g.Refused,'finite outer'):
            m.admit('aws-m8azn',21841)
        result=m.admit('aws-m8azn',21780,datetime(2026,10,1,17,40,tzinfo=timezone.utc))
        self.assertEqual(result['source_evidence_sha256'][str(root/m.DAILY_AUTHORITY_PATH)],m.DAILY_AUTHORITY_SHA)
        self.assertEqual(result['source_evidence_sha256'][str(root/'cloud/host_hours_admit_v1.py')],m.PARENT_SHA)
        # A synthetic money conversion proves the rolling predicate remains
        # active; this is not an observed spend/provider-budget fixture.
        money=m.g.money
        with patch.object(m.g,'money',side_effect=lambda value:money(0 if value==50 else value)):
            with self.assertRaisesRegex(m.g.Refused,'rolling24h'):
                m.admit('aws-m8azn',21780,datetime(2026,10,1,17,40,tzinfo=timezone.utc))


if __name__=='__main__':unittest.main()
