import importlib.util
import json
from datetime import datetime, timezone
from decimal import Decimal, ROUND_FLOOR
from pathlib import Path
import shutil
import unittest
from unittest.mock import patch
import test_host_hours_azure_v2 as fixtures

PROJECT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('azure_hours_v5', PROJECT/'cloud/host_hours_azure_signed_v1.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class AzureHoursSignedTests(unittest.TestCase):
    def test_signed_pending_is_conservative_in_both_accounting_branches(self):
        for qualified in (False, True):
            if qualified:
                self.qualified_fixture()
            self.inputs['credit']['pendingEligibleCharges']['value'] = 1.51
            self.refresh(); positive = self.check()
            self.inputs['credit']['pendingEligibleCharges']['value'] = -1.51
            self.refresh(); negative = self.check()
            for field in ('remaining_total_after_storage_usd', 'verified_provider_credit_remaining_usd'):
                self.assertEqual(positive[field], negative[field])
            self.inputs['credit']['pendingEligibleCharges']['value'] = 0
            self.refresh(); zero = self.check()
            self.assertAlmostEqual(zero['verified_provider_credit_remaining_usd']-negative['verified_provider_credit_remaining_usd'],1.51)
            self.assertEqual(negative['rolling24h_cap_usd'],75)

    def test_nonfinite_nonnumeric_pending_or_negative_balances_never_admit(self):
        for value in (True, None, {}, 'NaN', 'Infinity', '-Infinity', 'not money'):
            with self.assertRaises(ValueError):m.pending_debit(value)
        self.inputs['credit']['balanceSummary']['currentBalance']['value'] = -1
        self.inputs['credit']['pendingEligibleCharges']['value'] = -1.51
        self.refresh()
        with self.assertRaises(ValueError):self.check()

    def setUp(self):
        self.fixture = fixtures.AzureHoursTests()
        self.fixture.setUp()
        self.root = self.fixture.root
        shutil.copyfile(PROJECT/'cloud/host_hours_azure_v2.py', self.root/'cloud/host_hours_azure_v2.py')
        for name in (m.V3_PATH, m.DAILY_AUTHORITY_PATH):
            target = self.root/name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(PROJECT/name, target)
        target = self.root/m.R49_PATH
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(PROJECT/m.R49_PATH, target)
        self.patch = patch.object(m, 'ROOT', self.root)
        self.patch.start()
        self.now = datetime(2026, 10, 1, 8, 57, tzinfo=timezone.utc)
        self.inputs = self.fixture.inputs
        self.inputs['observed_at_utc'] = self.now.isoformat()
        self.inputs['vms'][m.BURST]['vmSize'] = m.NEW_SKU
        self.source_sha = 'a'*64
        self.row = None
        self.refresh()

    def tearDown(self):
        self.patch.stop()
        self.fixture.tearDown()

    def dump(self, name, value):
        path = self.root/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))
        return dict(path=name, sha256=fixtures.m.sha(path))

    def refresh(self, host=m.FIT, seconds=900):
        self.provider = self.dump('provider.json', self.inputs)
        kwargs = {}
        if self.row is not None:
            self.transition = self.dump('transition.json', self.row)
            kwargs.update(transition_path=self.transition['path'], transition_sha256=self.transition['sha256'])
        self.value = m.make_budget(host, seconds, self.provider['path'], self.provider['sha256'], self.source_sha, **kwargs)

    def check(self, now=None):
        return m.validate_budget(self.value, self.value['host'], self.value['max_seconds'], now or self.now,
                                 self.source_sha, self.value['profile']['sha256'])

    def qualified_fixture(self):
        profile = self.dump('cloud/azure-burst-f16as-static-profiles-v1.json', dict(host=m.BURST))
        evidence = {key: self.dump('proof-'+key+'.json', dict(test_fixture_only=True))
                    for key in ('provider_transition', 'retail', 'guard_source', 'guard_capture')}
        evidence['profile'] = profile
        prior = Decimal('3.2912')
        baseline = 4600
        maximum = baseline+int(((Decimal('44.528')-prior)/Decimal('1.093')*3600).to_integral_value(rounding=ROUND_FLOOR))
        self.row = dict(status='PASS_verified_azure_burst_rate_transition', host=m.BURST,
                        old_sku='Standard_F32als_v7', old_rate_usd_hour='1.936', new_sku=m.NEW_SKU,
                        new_rate_usd_hour='1.093', provider_provisioning_state='Succeeded', guard_deployed_verified=True,
                        deadline_epoch=1791162766, compute_cap_usd='44.528', total_cap_usd=55,
                        reserve_usd=5, margin_usd='5.472', phase_boundary_utc='2026-10-01T08:54:46Z',
                        old_cumulative_running_seconds=4500, post_transition_cumulative_running_seconds=4600,
                        evidence=evidence, guard_config=dict(prior_compute_usd=str(prior), rate_phase_epoch=1790844886,
                        expected_vm_size=m.NEW_SKU, compute_usd_per_hour='1.093', compute_cap_usd='44.528',
                        deadline_epoch=1791162766, total_cap_usd=55, noncompute_reserve_usd=5,
                        prior_running_seconds=baseline, max_running_seconds=maximum))

    def test_unrelated_f16_continues_at_conservative_old_burst_rate(self):
        result = self.check()
        self.assertEqual(result['schema'], 'azure-host-hours-admission-v5')
        self.assertFalse(result['new_rate_admitted'])
        self.assertEqual(result['future_full_hosts_bound_usd'], .9215)
        self.assertEqual(result['hosts'][m.BURST]['future_compute_upper_usd'], .484)
        self.assertEqual(result['deadline_epoch'], 1791153913)
        self.assertEqual(result['per_job_charge_usd'], 0)

    def test_burst_new_jobs_fail_closed_without_transition_proof(self):
        self.refresh(m.BURST)
        with self.assertRaisesRegex(ValueError, 'qualified transition'):
            self.check()

    def test_qualified_new_rate_keeps_old_cost_and_counter(self):
        self.qualified_fixture()
        self.refresh(m.BURST)
        result = self.check()
        self.assertTrue(result['new_rate_admitted'])
        self.assertEqual(result['hosts'][m.BURST]['old_phase_compute_upper_usd'], 3.2912)
        self.assertEqual(result['hosts'][m.BURST]['preserved_counter_baseline'], 4600)
        self.assertEqual(result['future_full_hosts_bound_usd'], .71075)
        self.assertEqual(result['deadline_epoch'], 1791162766)
        self.assertLess(result['hosts'][m.BURST]['remaining_compute_after_context_usd'], 44.528)

    def test_parallel_admissions_do_not_change_files_or_add_runtime(self):
        self.qualified_fixture()
        self.refresh(m.BURST)
        before = {str(p): fixtures.m.sha(p) for p in self.root.rglob('*') if p.is_file()}
        results = [self.check() for _ in range(8)]
        self.assertEqual(len({r['aggregate_lifetime_compute_upper_usd'] for r in results}), 1)
        self.assertTrue(all(r['per_job_charge_usd'] == 0 for r in results))
        after = {str(p): fixtures.m.sha(p) for p in self.root.rglob('*') if p.is_file()}
        self.assertEqual(before, after)

    def test_counter_reset_fresh_hours_caps_and_unverified_guard_refused(self):
        for mutate in (
            lambda: self.row.update(guard_deployed_verified=False),
            lambda: self.row.update(post_transition_cumulative_running_seconds=0),
            lambda: self.row['guard_config'].update(prior_compute_usd=0),
            lambda: self.row['guard_config'].update(max_running_seconds=146520),
            lambda: self.row.update(compute_cap_usd=44.53),
            lambda: self.row.update(deadline_epoch=1791162767),
            lambda: self.row.update(new_rate_usd_hour=1),
        ):
            self.qualified_fixture()
            mutate()
            self.refresh(m.BURST)
            with self.assertRaises(ValueError):
                self.check()

    def test_actual_sku_credit_freshness_source_profile_and_runtime_refused(self):
        self.inputs['vms'][m.BURST]['vmSize'] = 'Standard_F64as_v7'
        self.refresh()
        with self.assertRaisesRegex(ValueError, 'user-authorized'):
            self.check()
        self.inputs['vms'][m.BURST]['vmSize'] = m.NEW_SKU
        self.refresh()
        with self.assertRaisesRegex(ValueError, 'stale or future'):
            self.check(datetime.fromtimestamp(self.now.timestamp()+901, timezone.utc))
        with self.assertRaisesRegex(ValueError, 'source/config'):
            m.validate_budget(self.value, m.FIT, 900, self.now, 'b'*64)
        with self.assertRaises(ValueError):
            m.validate_budget(self.value, m.FIT, 901, self.now)
        with self.assertRaisesRegex(ValueError, 'selected profile'):
            m.validate_budget(self.value, m.FIT, 900, self.now, profile_sha256='b'*64)
        self.inputs['credit']['balanceSummary']['estimatedBalance']['value'] = 20
        self.refresh()
        with self.assertRaisesRegex(ValueError, 'verified credit'):
            self.check()

    def test_original_compute_money_ceiling_still_exhausts_after_resize(self):
        self.qualified_fixture()
        self.now = datetime(2026, 10, 3, 0, 0, tzinfo=timezone.utc)
        self.inputs['observed_at_utc'] = self.now.isoformat()
        self.refresh(m.BURST)
        with self.assertRaisesRegex(ValueError, 'original burst compute'):
            self.check()


    def test_both_rate_branches_admit_above60_below75_without_other_changes(self):
        old_spec = importlib.util.spec_from_file_location('frozen_azure_v3_daily', PROJECT/m.V3_PATH)
        old = importlib.util.module_from_spec(old_spec)
        old_spec.loader.exec_module(old)
        old.ROOT = self.root
        for qualified in (False, True):
            with self.subTest(qualified=qualified):
                self.row = None
                if qualified:
                    self.qualified_fixture()
                self.now = datetime(2026, 10, 1, 22 if qualified else 20, 0, tzinfo=timezone.utc)
                self.inputs['observed_at_utc'] = self.now.isoformat()
                self.refresh(seconds=21780)
                result = self.check()
                amount = result['rolling24h_spend_upper_usd']+result['future_full_hosts_bound_usd']
                self.assertGreater(amount, 60)
                self.assertLess(amount, 75)
                self.assertEqual(result['rolling24h_cap_usd'], 75)
                self.assertEqual(result['deadline_epoch'], 1791153913)
                self.assertEqual(result['storage_other_reserve_usd'], 15)
                self.assertEqual(result['per_job_charge_usd'], 0)
                self.assertFalse(result['host_or_source_admission_conferred'])
                legacy = {k:v for k,v in self.value.items() if k != 'daily_cap_authority'}
                legacy.update(schema=old.SCHEMA, kind=old.KIND, checker_sha256=m.V3_SHA)
                with self.assertRaisesRegex(ValueError, 'rolling24h'):
                    old.validate_budget(legacy, m.FIT, 21780, self.now, self.source_sha)

    def test75_still_blocks_above_new_daily_cap(self):
        self.qualified_fixture()
        self.now = datetime(2026, 10, 2, 3, 0, tzinfo=timezone.utc)
        self.inputs['observed_at_utc'] = self.now.isoformat()
        self.refresh(seconds=21780)
        with self.assertRaisesRegex(ValueError, 'USD75'):
            self.check()

    def test_approval_and_frozen_source_pins_fail_closed(self):
        approval = self.root/m.DAILY_AUTHORITY_PATH
        original = approval.read_bytes()
        approval.unlink()
        with self.assertRaisesRegex(ValueError, 'regular canonical'):
            self.check()
        approval.write_bytes(original+b' ')
        with self.assertRaisesRegex(ValueError, 'SHA256 drift'):
            self.check()
        approval.write_bytes(original)
        self.value['daily_cap_authority']['sha256'] = 'b'*64
        with self.assertRaisesRegex(ValueError, 'authority reference'):
            self.check()
        self.refresh()
        parent = self.root/m.V3_PATH
        parent.write_bytes(parent.read_bytes()+b' ')
        with self.assertRaisesRegex(ValueError, 'SHA256 drift'):
            self.check()

    def test_explicit_v5_schema_authority_closure_and_unchanged_legacy_policy(self):
        result = self.check()
        pins = result['source_evidence_sha256']
        self.assertEqual(pins[m.DAILY_AUTHORITY_PATH], m.DAILY_AUTHORITY_SHA)
        self.assertEqual(pins[m.V3_PATH], m.V3_SHA)
        self.assertEqual(pins['cloud/host_hours_azure_v2.py'], m.PARENT_SHA)
        self.assertEqual(pins['cloud/host_hours_azure_signed_v1.py'], self.value['checker_sha256'])
        self.assertEqual(self.value['schema'], 'azure-host-hours-budget-v5')
        self.assertEqual(self.value['daily_cap_authority'], dict(path=m.DAILY_AUTHORITY_PATH, sha256=m.DAILY_AUTHORITY_SHA))
        policy = json.loads((self.root/'cloud/owner-dispatch-budget-v1.json').read_text())
        self.assertEqual(policy['hosts']['azure-f16']['daily_fit_reservation_cap'], 36)
        self.assertEqual(m.parent().HOSTS, fixtures.m.HOSTS)
        self.value['schema'] = 'azure-host-hours-budget-v3'
        with self.assertRaisesRegex(ValueError, 'schema'):
            self.check()


if __name__ == '__main__':
    unittest.main()
