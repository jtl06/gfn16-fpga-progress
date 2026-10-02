import importlib.util
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

PROJECT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('azure_hours', PROJECT/'cloud/host_hours_azure_v2.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class AzureHoursTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        for name in [*m.AUTHORITY_PINS, *(row['profile'] for row in m.HOSTS.values())]:
            target = self.root/name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(PROJECT/name, target)
        self.root_patch = patch.object(m, 'ROOT', self.root)
        self.root_patch.start()
        self.now = datetime(2026, 10, 1, 7, 52, tzinfo=timezone.utc)
        self.inputs = dict(schema='azure-host-hours-provider-inputs-v2', status='authenticated_read_only_provider_inputs',
            observed_at_utc=self.now.isoformat(), credit=dict(creditCurrency='USD',
            balanceSummary={key: dict(currency='USD', value=200) for key in ('currentBalance', 'estimatedBalance')},
            pendingEligibleCharges=dict(currency='USD', value=0)), vms={})
        for host, row in m.HOSTS.items():
            self.inputs['vms'][host] = dict(id=f'/subscriptions/{m.SUBSCRIPTION}/resourceGroups/{row["group"]}/providers/Microsoft.Compute/virtualMachines/{host}',
                name=host, location='westus2', vmSize=row['size'], timeCreated=row['created'], powerState='VM running')
        self.refresh()

    def tearDown(self):
        self.root_patch.stop()
        self.temp.cleanup()

    def refresh(self, host='gfn16-azure-sim-f32', seconds=3715):
        self.path = self.root/'provider.json'
        self.path.write_text(json.dumps(self.inputs))
        self.value = m.make_budget(host, seconds, 'provider.json', m.sha(self.path), 'a'*64)

    def check(self, value=None, now=None, seconds=None):
        value = value or self.value
        return m.validate_budget(value, value['host'], seconds if seconds is not None else value['max_seconds'],
                                 now or self.now, 'a'*64, value['profile']['sha256'])

    def test_shared_parallel_accrual_has_no_writes_or_job_fees(self):
        before = {str(p): m.sha(p) for p in self.root.rglob('*') if p.is_file()}
        results = [self.check() for _ in range(8)]
        self.assertTrue(all(r['admitted'] and r['per_job_charge_usd'] == 0 for r in results))
        self.assertEqual(len({r['rolling24h_spend_upper_usd'] for r in results}), 1)
        self.assertEqual(results[0]['future_full_hosts_bound_usd'], 3.803748)
        after = {str(p): m.sha(p) for p in self.root.rglob('*') if p.is_file()}
        self.assertEqual(before, after)

    def test_f16_and_f32_have_distinct_protected_deadlines(self):
        for host, row in m.HOSTS.items():
            self.refresh(host)
            result = self.check()
            self.assertEqual(result['deadline_epoch'], row['deadline'])
            self.assertEqual(result['drain_epoch'], row['deadline']-7200)
            self.assertEqual(result['storage_other_reserve_usd'], 15)

    def test_daily_meter_starts_at_original_policy_not_f16_birth(self):
        result = self.check()
        expected_f16 = m.cost('1.75', (self.now-m.moment(m.POLICY_START)).total_seconds())
        actual = result['hosts']['gfn16-azure-f16']
        self.assertEqual(actual['rolling24h_compute_upper_usd'], float(expected_f16))
        self.assertGreater(actual['lifetime_compute_upper_usd'], actual['rolling24h_compute_upper_usd'])

    def test_f32_bootstrap_is_earlier_guard_creation(self):
        result = self.check()
        self.assertEqual(result['hosts']['gfn16-azure-sim-f32']['elapsed_running_upper_seconds'], self.now.timestamp()-m.F32_START)

    def test_unknown_stopped_time_counted_and_current_running_hosts_share_future(self):
        self.inputs['vms']['gfn16-azure-f16']['powerState'] = 'VM deallocated'
        self.refresh()
        result = self.check()
        self.assertGreater(result['hosts']['gfn16-azure-f16']['lifetime_compute_upper_usd'], 0)
        self.assertEqual(result['hosts']['gfn16-azure-f16']['future_compute_upper_usd'], 0)
        self.assertEqual(result['future_full_hosts_bound_usd'], float(m.cost('1.936', 3715)))

    def test_source_profile_runtime_and_host_drift_refused(self):
        with self.assertRaisesRegex(ValueError, 'source/config'):
            m.validate_budget(self.value, self.value['host'], now=self.now, source_sha256='b'*64)
        with self.assertRaisesRegex(ValueError, 'selected profile'):
            m.validate_budget(self.value, self.value['host'], now=self.now, profile_sha256='b'*64)
        for seconds in (0, True, 3716, 21841):
            with self.assertRaises(ValueError):
                self.check(seconds=seconds)
        for host in ('azure-f16', 'gfn16-pilot-c4d', 'unknown'):
            with self.assertRaises(ValueError):
                m.validate_budget(self.value, host, now=self.now)

    def test_stale_future_or_missing_provider_credit_refused(self):
        for delta in (-1, 901):
            with self.assertRaisesRegex(ValueError, 'stale or future'):
                self.check(now=datetime.fromtimestamp(self.now.timestamp()+delta, timezone.utc))
        self.inputs['credit']['balanceSummary']['estimatedBalance']['value'] = 20
        self.refresh()
        with self.assertRaisesRegex(ValueError, 'verified credit'):
            self.check()

    def test_aggregate_daily_cap_refused(self):
        self.now = datetime(2026, 10, 1, 15, 0, tzinfo=timezone.utc)
        self.inputs['observed_at_utc'] = self.now.isoformat()
        self.refresh(seconds=21840)
        with self.assertRaisesRegex(ValueError, 'rolling24h'):
            self.check()

    def test_f32_cumulative_limit_refused_without_proven_stop_intervals(self):
        self.now = datetime.fromtimestamp(m.F32_START+m.F32_LIMIT_SECONDS-3714, timezone.utc)
        self.inputs['observed_at_utc'] = self.now.isoformat()
        self.refresh()
        with self.assertRaisesRegex(ValueError, '23 running-hour'):
            self.check()

    def test_provider_identity_state_authority_and_hash_refused(self):
        for key, bad in (('timeCreated', '2026-10-01T07:16:17Z'), ('vmSize', 'Standard_F64als_v7'), ('powerState', 'VM stopped')):
            old = self.inputs['vms'][self.value['host']][key]
            self.inputs['vms'][self.value['host']][key] = bad
            self.refresh()
            with self.assertRaises(ValueError):
                self.check()
            self.inputs['vms'][self.value['host']][key] = old
        self.refresh()
        self.path.write_text('{}')
        with self.assertRaisesRegex(ValueError, 'SHA256 drift'):
            self.check()
        self.refresh()
        auth = self.root/'cloud/azure-protected-admission-earlier-v1.json'
        auth.write_text('{}')
        with self.assertRaisesRegex(ValueError, 'SHA256 drift'):
            self.check()

    def test_t_minus_two_hour_drain_and_checker_pin_refused(self):
        self.value['checker_sha256'] = '0'*64
        with self.assertRaisesRegex(ValueError, 'meter source drift'):
            self.check()
        self.now = datetime.fromtimestamp(m.HOSTS['gfn16-azure-f16']['deadline']-7200-3715, timezone.utc)
        self.inputs['observed_at_utc'] = self.now.isoformat()
        self.refresh('gfn16-azure-f16')
        with self.assertRaisesRegex(ValueError, 'drain deadline'):
            self.check()

    def test_capture_uses_only_fixed_read_only_calls(self):
        calls = []
        def run(argv, **kwargs):
            calls.append(argv)
            document = self.inputs['credit'] if 'rest' in argv else self.inputs['vms'][list(m.HOSTS)[len(calls)-2]]
            return subprocess.CompletedProcess(argv, 0, json.dumps(document), '')
        result = m.provider_inputs(run, lambda: self.now)
        self.assertEqual(len(calls), 3)
        self.assertIn('--method', calls[0])
        self.assertEqual(calls[0][calls[0].index('--method')+1], 'get')
        self.assertTrue(all(call[1:3] == ['vm', 'show'] for call in calls[1:]))
        self.assertEqual(set(result['vms']), set(m.HOSTS))


if __name__ == '__main__':
    unittest.main()
