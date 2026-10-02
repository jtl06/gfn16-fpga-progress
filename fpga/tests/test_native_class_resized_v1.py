"""Source-only resized-host binding; no remote calls or HDL execution."""
import copy
import hashlib
import json
import unittest
from datetime import datetime, timezone
from unittest.mock import patch
from fpga.tests.test_native_shared_v1 import SharedNativeTests
from fpga.tools import native_class_package_v5 as p, native_class_v3 as c, native_package_v7 as s


class ResizedPackageTests(SharedNativeTests):
    def setUp(self):
        super().setUp()
        original = p.base.meter
        def fixed_meter():
            module = original()
            validate = module.validate_budget
            def fixed(value, host, max_seconds=3715, now=None, **kwargs):
                return validate(value, host, max_seconds,
                                now=now or datetime(2026, 10, 1, 9, 12, tzinfo=timezone.utc), **kwargs)
            module.validate_budget = fixed
            return module
        guard = patch.object(p.base, 'meter', side_effect=fixed_meter)
        guard.start(); self.addCleanup(guard.stop)

    def value(self):
        profile = c.profile('azure-burst16-static01-v1')
        return p.base.meter().make_budget(profile['host'], 3715,
            'results/throughput-20260929/azure-sim-resize-r49-v1/provider-inputs-v2.json',
            '92634d6972ae482b6a9a403092ca08e4f3c42d84f36b6446fda1148db06b6e75',
            p.source_identity(self.m), profile['profile_sha256'],
            transition_path='results/throughput-20260929/azure-sim-resize-r49-v1/rate-transition-v1.json',
            transition_sha256='c4923266e1fabaeeca7cbf6e5f2444455c299accf5ed89c122927c47ed56ac92')

    def test_actual_transition_package_closure_and_safe_stager(self):
        value = self.value(); budget = self.root/'azure.json'; budget.write_text(json.dumps(value))
        out = self.root/'resized'
        result = p.prepare(self.manifest, self.source, 'azure-burst16-static01-v1',
                           'resized-smoke', 'run', out, budget)
        manifest = json.loads((out/'manifest.json').read_text())
        self.assertEqual(p.source_identity(manifest), value['source_sha256'])
        for name in ('tools/native_class_v3.py', 'tools/native_class_v2.py',
                     'tools/native_static_v4.py', 'tools/native_class_package_v3.py',
                     'cloud/azure-burst16-static-profiles-v1.json', 'cloud/host_hours_azure_v3.py'):
            self.assertEqual(manifest['sources'][name], hashlib.sha256((out/'capture/source/fpga'/name).read_bytes()).hexdigest())
        inspected = s.worker().inspect_archive(out/'package.tar.gz', result['archive_sha256'], result['ticket_sha256'])
        self.assertEqual(inspected[3]['host'], 'gfn16-azure-sim-f32')
        with self.assertRaises(ValueError):
            s.worker().inspect_archive(out/'package.tar.gz', '0'*64, result['ticket_sha256'])

    def test_source_profile_provider_and_transition_rejection(self):
        profile = c.profile('azure-burst16-static01-v1'); value = self.value()
        p.binding(value, profile, self.m)
        for field, replacement in [('source_sha256','0'*64), ('provider','gcp'), ('transition',None)]:
            changed = copy.deepcopy(value); changed[field] = replacement
            with self.assertRaises(ValueError): p.binding(changed, profile, self.m)
        changed = copy.deepcopy(profile); changed['profile_sha256'] = '0'*64
        with self.assertRaises(ValueError): p.binding(value, changed, self.m)

    def test_all_resize_profiles_and_outer_lock_hook(self):
        self.assertEqual(len(c.SELECTIONS), 29)
        for pair in ('01','23','45','67','89','1011','1213','1415'):
            parent = c.parent('azure-burst16-static'+pair+'-v1')
            self.assertTrue(callable(parent.guard_protected))
            self.assertTrue(callable(parent.guard_toolchain))
        self.assertIn('execute_with_parent', c.execute.__code__.co_names)


if __name__ == '__main__': unittest.main()
