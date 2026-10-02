import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from fpga.tools.build_identity_v1 import admit_cached_elf, build_identity, sha
from fpga.tools.native_source_gate_v1 import PROFILES

ROOT = Path(__file__).resolve().parents[1]
DONOR = ROOT/'results/throughput-20260929/track-a4-blocklane-gcp-aw5-v1'
REPORT_SHA = 'd0827812b3a65daf377c7e8cf055c561a862598f6fda585fe08959c8cc83f94b'


class BuildIdentityTests(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads((DONOR/'approved-manifest.json').read_text())
        self.profile = copy.deepcopy(PROFILES['gfn16-pilot-c4'])
        self.review = DONOR/'independent-review-v1.json'
        self.review_sha = sha(self.review)

    def admit(self, manifest=None, profile=None, donor=DONOR, report_sha=REPORT_SHA,
              review=None, review_sha=None):
        return admit_cached_elf(manifest or self.manifest, profile or self.profile,
                                donor, report_sha, review or self.review,
                                review_sha or self.review_sha)

    def test_actual_reviewed_donor_is_read_only_admitted(self):
        result = self.admit()
        self.assertEqual(result['executable_sha256'],
                         'ba28f3c56111b181cc702082598937b1ba14e476c8e19181056698258a3973a4')
        self.assertFalse(result['promotion_allowed'])
        self.assertEqual(result['build_key'], build_identity(self.manifest, self.profile)['build_key'])

    def test_map_order_independent_but_compile_order_matters(self):
        other = copy.deepcopy(self.manifest)
        other['sources'] = dict(reversed(list(other['sources'].items())))
        self.assertEqual(build_identity(other, self.profile), build_identity(self.manifest, self.profile))
        other['build']['sv_sources'].reverse()
        with self.assertRaisesRegex(ValueError, 'build identity'):
            self.admit(manifest=other)

    def test_source_harness_rom_parameters_flags_host_tool_changes_miss(self):
        variants = []
        for name in self.manifest['sources']:
            changed = copy.deepcopy(self.manifest)
            changed['sources'][name] = '0'*64
            variants.append(changed)
        for change in ('parameter', 'flag', 'host', 'path'):
            changed = copy.deepcopy(self.manifest)
            if change == 'parameter': changed['build']['parameters']['AW'] = 8
            if change == 'flag': changed['build']['cflags'].append('-O3')
            if change == 'host': changed['host'] = 'aethia'
            if change == 'path': changed['source_root'] += '-changed'
            variants.append(changed)
        for changed in variants:
            with self.subTest(changed=changed['host']), self.assertRaises(ValueError):
                self.admit(manifest=changed)
        self.profile['hashes']['compiler'] = '0'*64
        with self.assertRaisesRegex(ValueError, 'toolchain'):
            self.admit()

    def test_runtime_selection_does_not_change_build(self):
        changed = copy.deepcopy(self.manifest)
        changed['steps'] = [dict(name='new-approved-runtime', argv=['{exe}', '--new-case'])]
        self.assertEqual(build_identity(changed, self.profile), build_identity(self.manifest, self.profile))
        # This grants only build reuse, not permission to run these new commands.
        self.assertFalse(self.admit(manifest=changed)['promotion_allowed'])

    def test_identity_is_detached(self):
        identity = build_identity(self.manifest, self.profile)
        self.manifest['build']['parameters']['AW'] = 8
        self.assertEqual(identity['identity']['build']['parameters']['AW'], 5)

    def test_review_pin_required(self):
        with self.assertRaisesRegex(ValueError, 'independent review'):
            self.admit(review_sha='0'*64)

    def test_artifact_corruption_and_symlink_rejected(self):
        for mode in ('corrupt', 'symlink'):
            with tempfile.TemporaryDirectory() as tmp:
                donor = Path(tmp)/'donor'
                shutil.copytree(DONOR, donor)
                target = donor/'model.gz'
                if mode == 'corrupt': target.write_bytes(b'not a model')
                else:
                    target.unlink()
                    target.symlink_to(DONOR/'model.gz')
                with self.subTest(mode=mode), self.assertRaises(ValueError):
                    self.admit(donor=donor)

    def test_failed_donor_rejected_even_if_rehashed(self):
        with tempfile.TemporaryDirectory() as tmp:
            donor = Path(tmp)/'donor'
            shutil.copytree(DONOR, donor)
            path = donor/'report.json'
            report = json.loads(path.read_text())
            report['status'] = 'failed_native_commands'
            path.write_text(json.dumps(report))
            with self.assertRaisesRegex(ValueError, 'successful donor'):
                self.admit(donor=donor, report_sha=sha(path))


if __name__ == '__main__':
    unittest.main()
