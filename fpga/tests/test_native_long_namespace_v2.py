"""Actual generated globals, host/source admission and inherited FD regression."""
import hashlib
import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
from fpga.tools import native_long_class_v1 as old
from fpga.tools import native_long_class_v2 as runtime
from fpga.tools import native_long_package_v3 as package
from fpga.tools import native_long_stage_v3 as stage
from fpga.tools import native_profile_variants_v7 as variants

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'results/throughput-20260929/native-long-duration-v3'


class LongNamespaceTests(unittest.TestCase):
    def test_preserved_failure_and_shared_live_namespace(self):
        prior = old.parent('gcp-c4d-static23-v1')
        self.assertIsNot(prior.load_manifest.__globals__, prior.__dict__)
        for name in runtime.SELECTIONS:
            value = runtime.parent(name)
            for function in ('load_manifest', 'execute', 'check_sources', 'tools_for'):
                self.assertIs(getattr(value, function).__globals__, value.__dict__)
            self.assertEqual(set(value.PROFILES), {'gfn16-pilot-c4d'})
            self.assertEqual(Path(value.__file__).name, 'native_long_class_v2.py')
            self.assertEqual(value.SELF, 'tools/native_long_class_v2.py')
            value.LEASE_FDS = (101, 102)
            self.assertEqual(value.execute.__globals__['LEASE_FDS'], (101, 102))

    def test_actual_unpacked_source_load_manifest_with_mocked_host_only(self):
        packet = DATA / 't5b-packet23'
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve(); root = base / 'capture/source/fpga'
            shutil.copytree(packet / 'capture/source/fpga', root)
            output = base / 'output'; output.mkdir()
            manifest = json.loads((packet / 'manifest.json').read_text())
            manifest.update(source_root=str(root), output_parent=str(output))
            path = base / 'manifest.json'; path.write_text(json.dumps(manifest))
            value = runtime.parent(manifest['cpu_profile'])
            selected = dict(runtime.profile(manifest['cpu_profile']), base=str(base))
            value.PROFILES = {'gfn16-pilot-c4d': selected}
            value.__file__ = str(root / value.SELF)
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            # Exercise the real full source/host/SELF gate; no HDL/native code.
            with patch.object(value.socket, 'gethostname', return_value='gfn16-pilot-c4d'):
                accepted, _, _ = value.load_manifest(path, digest)
                self.assertEqual(accepted, manifest)
            with patch.object(value.socket, 'gethostname', return_value='wrong-host'):
                with self.assertRaisesRegex(ValueError, 'explicit approved native host'):
                    value.load_manifest(path, digest)
            value.__file__ = str(root / 'tools/native_long_class_v1.py')
            with patch.object(value.socket, 'gethostname', return_value='gfn16-pilot-c4d'):
                with self.assertRaisesRegex(ValueError, 'launcher inside pinned snapshot'):
                    value.load_manifest(path, digest)

    def test_actual_dual_package_and_strict_budget_preserved(self):
        manifests = []
        for pair in ('01', '23'):
            directory = DATA / ('t5b-packet' + pair)
            receipt = json.loads((directory / 'preparation.json').read_text())
            _, ticket, manifest, _ = stage.worker().inspect_archive(directory / 'package.tar.gz', receipt['archive_sha256'], receipt['ticket_sha256'])
            self.assertEqual(ticket['max_seconds'], 10800)
            self.assertEqual(manifest['sources']['tools/native_long_class_v2.py'], package.EXECUTOR_SHA)
            for key, value in [('remaining_after_reserves_usd', float('inf')), ('source_receipt_sha256', 'x'*64),
                               ('planning_usd_per_hour', True), ('remaining_after_reserves_usd', 1000)]:
                budget = dict(ticket['budget']); budget[key] = value
                with self.assertRaises(ValueError): package.worker().budget_check(budget)
            manifests.append(manifest)
        for key in ('sources', 'build', 'probe', 'steps', 'runtime_duration'):
            self.assertEqual(manifests[0][key], manifests[1][key])

    def test_exact_framework_successor_matches_but_not_changed_role_or_shape(self):
        loaded = []
        for path in (DATA.parent / 'native-long-duration-v2/t5b-packet23', DATA / 't5b-packet23'):
            loaded.append(dict(manifest=json.loads((path/'manifest.json').read_text()),
                               budget=json.loads((path/'ticket.json').read_text())['budget'], source_root=path/'capture/source/fpga'))
        variants.match_variants(loaded)
        for kind in ('compiled', 'outcome', 'duration', 'unknown-control'):
            altered = copy.deepcopy(loaded)
            manifest = altered[1]['manifest']
            if kind == 'compiled': manifest['sources'][manifest['build']['cpp_source']] = '0' * 64
            elif kind == 'outcome': manifest['steps'][0]['expected_returncode'] = 1
            elif kind == 'duration': manifest['runtime_duration']['shape']['model_command_seconds'] += 1
            else: manifest['sources']['tools/native_long_class_v2.py'] = '0' * 64
            with self.assertRaises(ValueError): variants.match_variants(altered)


if __name__ == '__main__': unittest.main()
