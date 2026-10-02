"""Hourly provider cache behavior; no provider calls."""
from datetime import datetime,timedelta,timezone
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('b',Path(__file__).resolve().parents[1]/'cloud/fit_budget_policy.py')
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)

class HourlyTests(unittest.TestCase):
    def test_launch_consumes_hourly_result_without_arithmetic_or_freshness(self):
        ref=dict(path='cloud/fit-policy-signed-credits.json',sha256=b.sha(b.ROOT/'cloud/fit-policy-signed-credits.json'))
        owner=b.PolicyBudget(ref)
        status=dict(schema='provider-hourly-cost-status-v1',provider='azure',status='PASS',checked_at_utc='2026-10-01T19:00:00+00:00')
        with patch.object(owner,'hourly',return_value=status), patch.object(owner,'meter',side_effect=AssertionError('per-launch arithmetic forbidden')):
            meter=owner.hourly_meter('azure')
            value=meter.make_budget('gfn16-azure-f16',21780,'unused','unused','source')
            self.assertEqual(meter.validate_budget(value,'gfn16-azure-f16',21780,source_sha256='source')['per_job_charge_usd'],0)
            with self.assertRaisesRegex(ValueError,'source binding'):
                meter.validate_budget(value,'gfn16-azure-f16',21780,source_sha256='changed')
        for state in ('BLOCKED','UNRESOLVED'):
            with self.assertRaisesRegex(ValueError,'must PASS'):
                owner.launch_status(dict(status,status=state),'azure')
        with self.assertRaisesRegex(ValueError,'must PASS'):
            owner.launch_status(status,'aws')

    def test_one_check_per_provider_hour_and_explicit_change(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve();now=datetime(2026,10,1,19,15,tzinfo=timezone.utc);calls=[]
            def check():calls.append(1);return dict(status='PASS',remaining_usd=100)
            first=b.hourly_provider_status('azure',check,root,now)
            self.assertEqual(first,b.hourly_provider_status('azure',check,root,now+timedelta(minutes=20)))
            self.assertEqual(len(calls),1)
            b.hourly_provider_status('azure',check,root,now+timedelta(minutes=21),force=True)
            self.assertEqual(len(calls),2)
            history=json.loads((root/'queue/provider-cost-status/azure-20261001T19.json').read_text())
            self.assertEqual(len(history['observations']),2)
            b.hourly_provider_status('azure',check,root,now+timedelta(hours=1))
            self.assertEqual(len(calls),3)
            b.hourly_provider_status('aws',check,root,now)
            self.assertEqual(len(calls),4)

    def test_failed_provider_check_is_retained_and_not_spammed(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve();now=datetime(2026,10,1,19,15,tzinfo=timezone.utc);calls=[]
            def bad():calls.append(1);raise ValueError('provider unavailable')
            result=b.hourly_provider_status('azure',bad,root,now)
            self.assertEqual(result['status'],'UNRESOLVED')
            self.assertEqual(result,b.hourly_provider_status('azure',bad,root,now+timedelta(minutes=1)))
            self.assertEqual(len(calls),1)

if __name__=='__main__':unittest.main()
