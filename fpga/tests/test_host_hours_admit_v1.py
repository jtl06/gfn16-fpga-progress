import importlib.util
from pathlib import Path
import unittest
from datetime import datetime, timezone

root = Path(__file__).resolve().parents[1]
s = importlib.util.spec_from_file_location('meter', root/'cloud/host_hours_admit_v1.py')
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

    def test_gcp_daily_removed_total_retained_and_aws_daily_unchanged(self):
        result=m.admit('gcp-c4d',10815,datetime(2026,10,2,7,38,tzinfo=timezone.utc))
        self.assertIsNone(result['rolling24h_cap_usd'])
        self.assertGreater(result['remaining_total_after_storage_usd'],0)
        with self.assertRaisesRegex(m.g.Refused,'remaining total'):
            m.admit('gcp-c4d',10815,datetime(2026,10,10,7,38,tzinfo=timezone.utc))
        with self.assertRaisesRegex(m.g.Refused,'host-hours cap'):
            m.admit('aws-m8azn',3715,datetime(2026,10,2,7,38,tzinfo=timezone.utc))
    def test_future_evidence_refused(self):
        with self.assertRaisesRegex(m.g.Refused,'future'):
            m.admit('gcp-c4d',3715,datetime(2026,10,1,5,0,tzinfo=timezone.utc))


if __name__=='__main__':unittest.main()
