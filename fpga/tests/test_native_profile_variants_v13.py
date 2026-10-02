"""Exact ordinal family, real dual packets, and unchanged existing identities."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from fpga.tools import native_profile_variants_v12 as old
from fpga.tools import native_profile_variants_v13 as new

ROOT = Path(__file__).resolve().parents[1]
POSITIVE = ROOT / 'results/throughput-20260929/native-ordinal-duration-v1/packet-positive01'


def packet(path):
    return dict(manifest=json.loads((path / 'manifest.json').read_text()),
                budget=json.loads((path / 'ticket.json').read_text())['budget'],
                source_root=path / 'capture/source/fpga')


class OrdinalIdentityTests(unittest.TestCase):
    def test_six_actual_packets_match_only_their_role_with_full_duration(self):
        roles = [
            (POSITIVE, ROOT / 'artifacts/s4-ordinal-p16-positive-gcp23-v1'),
            tuple(ROOT / f'artifacts/s4-ordinal-p16-negative-gcp{pair}-v1' for pair in ('01', '23')),
            tuple(ROOT / f'artifacts/s4-ordinal-p8-negative-gcp{pair}-v1' for pair in ('01', '23')),
        ]
        fingerprints = []
        for paths in roles:
            variants = [packet(p) for p in paths]
            result = new.match_variants(variants)
            fingerprints.append(result['functional_sha256'])
            for item, value in zip(variants, result['variants']):
                self.assertEqual(value['identity']['runtime_duration'], item['manifest']['runtime_duration'])
                for control in new.REQUIRED:
                    self.assertNotIn(control, value['identity']['sources'])
                self.assertFalse(result['fresh_budget_admission_conferred'])
        self.assertEqual(len(set(fingerprints)), 3)

    def test_exact_source_shape_outcome_and_placement_negatives(self):
        for kind in ('control', 'missing', 'host', 'profile', 'phase', 'budget', 'shape',
                     'contract', 'steps', 'probe', 'compiled', 'asset', 'root'):
            item = packet(POSITIVE); m = item['manifest']
            if kind == 'control': m['sources']['tools/native_ordinal_package_v1.py'] = '0' * 64
            elif kind == 'missing': del m['sources']['tools/native_ordinal_class_v1.py']
            elif kind == 'host': m['host'] = 'gfn16-azure-sim-f32'
            elif kind == 'profile': m['cpu_profile'] = 'gcp-c4d-static24g01-v1'
            elif kind == 'phase': m['phase'] = 'lint'
            elif kind == 'budget': item['budget']['provider'] = 'azure'
            elif kind == 'shape': m['runtime_duration']['shape']['model_command_seconds'] = 3301
            elif kind == 'contract': m['runtime_duration']['contract_sha256'] = '0' * 64
            elif kind == 'steps': m['steps'][0]['expected_returncode'] = 99
            elif kind == 'probe': m['probe']['expected_json']['model_threads'] = 2
            elif kind == 'compiled': m['sources'][m['build']['cpp_source']] = '0' * 64
            elif kind == 'asset':
                m['steps'][0]['validator'] = dict(source='tools/native_ordinal_duration_v1.py', assets={})
            else: item['source_root'] = None
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                new.functional_fingerprint(**item)

    def test_unknown_role_and_helper_sources_remain_identity(self):
        item = packet(POSITIVE); base = new.functional_fingerprint(**item)
        for name in ('tools/not_a_known_control.py', 'lineage/role-data.json'):
            changed = copy.deepcopy(item); changed['manifest']['sources'][name] = 'a' * 64
            result = new.functional_fingerprint(**changed)
            self.assertIn(name, result['identity']['sources'])
            self.assertNotEqual(base['sha256'], result['sha256'])

    def test_actual_control_bytes_not_only_declared_pin(self):
        item = packet(POSITIVE)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            for name in new.REQUIRED:
                target = root / name; target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((item['source_root'] / name).read_bytes())
            (root / 'tools/native_ordinal_class_v1.py').write_text('changed')
            item['source_root'] = root
            with self.assertRaisesRegex(ValueError, 'source-closed control'):
                new.functional_fingerprint(**item)

    def test_existing_retained_native_pass_identities_byte_unchanged(self):
        checked = 0
        for path in sorted((ROOT / 'queue/done').glob('*.json')):
            ticket = json.loads(path.read_text())
            if ticket.get('dependency_gate', {}).get('status') != 'PASS_expected_contracts':
                continue
            p = ticket.get('package')
            if not p or p['runner'] == 'tools/native_ordinal_package_v1.py':
                continue
            directory = Path(p['archive']).parent
            if not (directory / 'manifest.json').is_file():
                continue
            item = packet(directory)
            self.assertEqual(old.functional_fingerprint(**item), new.functional_fingerprint(**item), path.name)
            checked += 1
        self.assertGreaterEqual(checked, 100)


if __name__ == '__main__':
    unittest.main()
