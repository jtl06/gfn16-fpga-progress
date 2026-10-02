"""Offline AWS proposal guards. No downloads, compiler or native execution."""
import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from fpga.tools import aws_sim_profile_plan_v1 as p

INVENTORY = Path(__file__).resolve().parents[1]/'docs/briefs/replies/2026-10-01-aws-simulation-readonly-inventory-v1.json'
INVENTORY_SHA = 'ade6d1d222e9a635f7ebf45ba9e1bcc926512efb21b1433fba56117645c3bd7c'


class AwsSimulationPlanTests(unittest.TestCase):
    def setUp(self):
        self.observation = json.loads(INVENTORY.read_text())

    def test_actual_observation_emits_only_unadmitted_proposal(self):
        result = p.load_proposal(INVENTORY, INVENTORY_SHA)
        self.assertEqual(result['package']['sha256'], p.DEB_SHA)
        self.assertEqual(result['profile']['cpus'], [4,5])
        self.assertEqual(result['profile']['resource_caps']['memory_bytes'], 4<<30)
        self.assertEqual(result['profile']['clean_environment']['CXX'], '/usr/bin/x86_64-linux-gnu-g++-13')
        self.assertEqual(result['profile']['clean_environment']['VERILATOR_ROOT'], p.TOOL_ROOT+'/usr/share/verilator')
        for key in ('installed', 'native_execution', 'queue_admission', 'promotion_allowed'):
            self.assertFalse(result[key])
        self.assertTrue(result['installation_plan']['approval_required'])
        self.assertTrue(all(row['sha256'] is None for row in result['profile']['pending_tools'].values()))

    def test_wrong_package_version_hash_origin_size_rejected(self):
        for old,new in (('Version: 5.020-1','Version: 5.032-1'),
                        (p.DEB_SHA,'0'*64), ('Origin: Ubuntu','Origin: foreign'),
                        ('Size: 6940528','Size: 1')):
            bad = copy.deepcopy(self.observation)
            bad['apt']['verilator']['show']['stdout'] = bad['apt']['verilator']['show']['stdout'].replace(old,new)
            with self.subTest(new=new), self.assertRaisesRegex(ValueError,'package identity'):
                p.proposal(bad)

    def test_foreign_host_abi_root_inventory_rejected(self):
        for field,value in (('host','gfn16-pilot-c4'),('uid',0),('os_release','Ubuntu22.04')):
            bad = copy.deepcopy(self.observation); bad[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                p.proposal(bad)

    def test_tool_hash_drift_and_default_alias_rejected(self):
        for path,digest in p.KNOWN_TOOLS.values():
            bad = copy.deepcopy(self.observation)
            next(row for row in bad['files'] if row['path'] == path)['sha256'] = '0'*64
            with self.subTest(path=path), self.assertRaisesRegex(ValueError,'installed tool pin'):
                p.proposal(bad)
        bad = copy.deepcopy(self.observation)
        next(row for row in bad['files'] if row['path'] == '/usr/bin/g++')['resolved'] = '/usr/bin/g++-15'
        with self.assertRaisesRegex(ValueError,'aliases'):
            p.proposal(bad)

    def test_existing_tool_does_not_silently_become_admitted(self):
        bad = copy.deepcopy(self.observation); bad['candidate_files'][0]['exists'] = True
        with self.assertRaisesRegex(ValueError,'known-path absence'):
            p.proposal(bad)

    def test_smt_or_fit_overlap_rejected(self):
        for peer in (0,4):
            bad = copy.deepcopy(self.observation)
            target = next(row for row in bad['cpus'] if row['cpu'] == 5)
            source = next(row for row in bad['cpus'] if row['cpu'] == peer)
            target['package'],target['core'] = source['package'],source['core']
            with self.subTest(peer=peer), self.assertRaisesRegex(ValueError,'physical-core pair'):
                p.proposal(bad)

    def test_reproducible_plan_and_external_evidence_pin(self):
        self.assertEqual(p.proposal(self.observation),p.proposal(copy.deepcopy(self.observation)))
        with self.assertRaisesRegex(ValueError,'pinned observation'):
            p.load_proposal(INVENTORY,'0'*64)
        with patch.object(p,'sha',side_effect=[INVENTORY_SHA,'0'*64]):
            with self.assertRaisesRegex(ValueError,'frozen comparison source drift'):
                p.load_proposal(INVENTORY,INVENTORY_SHA)

    def test_frozen_hosts_and_no_process_execution(self):
        from fpga.tools.native_source_gate_v1 import PROFILES
        self.assertEqual(set(PROFILES),{'aethia','gfn16-pilot-c4'})
        source = Path(p.__file__).read_text()
        for token in ('subprocess','os.system','Popen','apt-get install'):
            self.assertNotIn(token,source)


if __name__ == '__main__':
    unittest.main()
