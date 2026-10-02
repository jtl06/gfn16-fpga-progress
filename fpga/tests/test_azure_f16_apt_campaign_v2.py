"""Pure lifecycle tests: no systemd, package or host mutations."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch


SOURCE = Path(__file__).parents[1] / 'cloud/azure-f16-apt-campaign-v2.py'
spec = importlib.util.spec_from_file_location('f16_apt', SOURCE)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def prior():
    return dict(boot_id='initial', units={u: dict(UnitFileState='enabled' if u in m.TIMERS or u == 'unattended-upgrades.service' else 'static',
        ActiveState='active' if u in m.TIMERS or u == 'unattended-upgrades.service' else 'inactive') for u in m.UNITS},
        unit_paths={d+'/'+u: None for d in ('/etc/systemd/system','/run/systemd/system') for u in m.UNITS},
        enabled_links={'original-link': 'original-target'}, apt_config_sha256={'config': 'exact'},
        package_state=dict(stdout='unchanged'), active_package_processes=[])


class Root:
    def __init__(self, before, restored=False): self.before, self.restored = before, restored
    def __truediv__(self, name):
        class File:
            def exists(inner): return self.restored if name == 'restored.json' else False
            def read_text(inner): return json.dumps(self.before)
        return File()


class CampaignTests(unittest.TestCase):
    def test_original_deadline_or_overdue_next_boot(self):
        before = prior()
        self.assertFalse(m.restoration_due(before,m.DEADLINE-1,'initial'))
        self.assertTrue(m.restoration_due(before,m.DEADLINE,'initial'))
        self.assertFalse(m.restoration_due(before,m.DEADLINE-100,'later-boot'))
        self.assertTrue(m.restoration_due(before,m.DEADLINE+1,'later-boot'))

    def test_suspend_never_stops_services(self):
        before = prior(); after = copy.deepcopy(before)
        for u in m.UNITS: after['units'][u]['UnitFileState']='masked'
        for u in m.TIMERS: after['units'][u]['ActiveState']='inactive'
        for p in after['unit_paths']:
            if p.startswith('/etc/'): after['unit_paths'][p]='/dev/null'
        with patch.object(m,'ROOT',Root(before)), patch.object(m,'snapshot',side_effect=[before,after]), patch.object(m,'save') as save, patch.object(m,'require',return_value={}) as run:
            self.assertEqual(m.suspend()['status'],'PASS_future_unattended_launches_suspended')
            calls=[c.args[0] for c in run.call_args_list]
            self.assertEqual(calls[0],['/usr/bin/systemctl','stop',*m.TIMERS])
            self.assertEqual(calls[1],['/usr/bin/systemctl','mask',*m.UNITS])
            self.assertEqual(save.call_count,2)

    def test_active_package_transaction_blocks_before_write(self):
        before = prior(); before['active_package_processes']=[dict(executable='dpkg')]
        with patch.object(m,'ROOT',Root(before)), patch.object(m,'snapshot',return_value=before), patch.object(m,'save') as save, patch.object(m,'require') as run:
            with self.assertRaises(AssertionError): m.suspend()
            save.assert_not_called(); run.assert_not_called()

    def test_restore_unmasks_all_before_start_and_never_stops_package_services(self):
        before = prior(); paths={p: '/dev/null' if p.startswith('/etc/') else None for p in before['unit_paths']}
        with patch.object(m,'ROOT',Root(before)), patch.object(m,'current_boot_id',return_value='initial'), patch.object(m,'unit_paths',return_value=paths), patch.object(m,'snapshot',return_value=before), patch.object(m,'save'), patch.object(m.time,'time',return_value=m.DEADLINE), patch.object(m,'require',return_value={}) as run:
            result=m.restore(); self.assertEqual(result['status'],'PASS_prior_unattended_unit_states_restored')
            calls=[c.args[0] for c in run.call_args_list]
            self.assertEqual(calls[:5],[['/usr/bin/systemctl','unmask',u] for u in m.UNITS])
            self.assertFalse(any(c[1]=='stop' and any(u in c for u in m.SERVICES) for c in calls))

    def test_early_changed_boot_does_not_restore(self):
        with patch.object(m,'ROOT',Root(prior())), patch.object(m,'current_boot_id',return_value='changed-before-deadline'), patch.object(m.time,'time',return_value=m.DEADLINE-1), patch.object(m,'require') as run:
            self.assertEqual(m.restore()['status'],'not_due_before_original_deadline')
            run.assert_not_called()

    def test_restore_is_idempotent(self):
        with patch.object(m,'ROOT',Root(prior(),restored=True)), patch.object(m,'require') as run:
            self.assertEqual(m.restore()['status'],'already_restored'); run.assert_not_called()

    def test_unknown_mask_drift_preserved(self):
        before = prior(); paths={p: '/dev/null' if p.startswith('/etc/') else None for p in before['unit_paths']}
        paths['/etc/systemd/system/apt-daily.timer']='user-override'
        with patch.object(m,'ROOT',Root(before)), patch.object(m,'current_boot_id',return_value='initial'), patch.object(m,'unit_paths',return_value=paths), patch.object(m.time,'time',return_value=m.DEADLINE), patch.object(m,'require') as run:
            with self.assertRaises(AssertionError): m.restore()
            run.assert_not_called()


if __name__ == '__main__': unittest.main()
