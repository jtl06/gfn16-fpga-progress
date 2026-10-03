# SPDX-License-Identifier: Apache-2.0
"""Synthetic XML contracts only; no client/project execution or acceptance."""
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

from fpga.host.r15_anonymous_platform import ManifestError, render_app_info


class AnonymousPlatformTests(unittest.TestCase):
    def fields(self):
        # Fictitious values, not a PrimeGrid app_info template.
        return dict(app_name='offline_fixture_app', version_num=17,
                    api_version='1.2.3', platform='offline_fixture_platform',
                    executable='fixture_binary', cmdline='--label="A&B<C>"',
                    plan_class='', avg_ncpus=1, support_files=[('helper.dat', 'helper')],
                    enabled=True)

    def reject(self, **changes):
        fields = self.fields()
        fields.update(changes)
        with self.assertRaises(ManifestError):
            render_app_info(**fields)

    def test_default_off_and_exact_true(self):
        fields = self.fields()
        del fields['enabled']
        with self.assertRaises(ManifestError):
            render_app_info(**fields)
        self.reject(enabled=1)

    def test_exact_explicit_fields_and_file_references(self):
        raw = render_app_info(**self.fields())
        root = ET.fromstring(raw)
        self.assertEqual(root.tag, 'app_info')
        self.assertEqual(root.findtext('app/name'), 'offline_fixture_app')
        version = root.find('app_version')
        self.assertEqual(version.findtext('version_num'), '17')
        self.assertEqual(version.findtext('api_version'), '1.2.3')
        self.assertEqual(version.findtext('platform'), 'offline_fixture_platform')
        self.assertEqual(version.findtext('cmdline'), '--label="A&B<C>"')
        self.assertIsNotNone(version.find('file_ref/main_program'))
        self.assertEqual(version.findall('file_ref')[1].findtext('open_name'), 'helper')
        self.assertEqual([node.findtext('name') for node in root.findall('file_info')],
                         ['fixture_binary', 'helper.dat'])
        self.assertIsNone(root.find('.//coproc'))
        self.assertIsNone(root.find('.//workunit'))
        self.assertIsNone(root.find('.//result'))

    def test_escaping_is_not_xml_injection(self):
        fields = self.fields()
        fields['cmdline'] = '</cmdline><coproc><type>fake</type></coproc>'
        root = ET.fromstring(render_app_info(**fields))
        self.assertEqual(root.findtext('app_version/cmdline'), fields['cmdline'])
        self.assertIsNone(root.find('.//coproc'))

    def test_no_io_and_deterministic(self):
        with patch('builtins.open', side_effect=AssertionError('no files')):
            self.assertEqual(render_app_info(**self.fields()),
                             render_app_info(**self.fields()))

    def test_names_refuse_path_traversal_percent_and_controls(self):
        for bad in ('', '..', 'a..b', '/tmp/a', '../a', 'a/b', 'a\\b', 'a%20b',
                    'a\x00', 'a\n', 'a b', 'a' * 128):
            for field in ('app_name', 'platform', 'executable'):
                with self.subTest(field=field, bad=bad):
                    self.reject(**{field: bad})

    def test_versions_and_cpu_counts_are_not_guessed_or_coerced(self):
        for bad in (True, -1, 2147483648, '17', 1.5):
            self.reject(version_num=bad)
        for bad in ('', '8.2', 'guess', '1.2.3\n', '1.2.' + '3' * 12, True):
            self.reject(api_version=bad)
        for bad in (True, 0, -1, 65, 1 << 10000, float('nan'), float('inf'), '1'):
            self.reject(avg_ncpus=bad)

    def test_file_ref_shape_and_alias_conflicts(self):
        for bad in (None, (), [['helper.dat', 'helper']], [('a',)],
                    [('a', 'helper'), ('b', 'helper')],
                    [('a', 'h1'), ('a', 'h2')], [('fixture_binary', 'h')],
                    [('a', 'fixture_binary')], [('a', '../bad')]):
            self.reject(support_files=bad)

    def test_unknown_or_missing_deployment_fields_refuse(self):
        fields = self.fields()
        fields['coproc'] = {'type': 'invented_fpga', 'count': 1}
        with self.assertRaises(TypeError):
            render_app_info(**fields)
        for key in self.fields().keys() - {'enabled'}:
            fields = self.fields()
            del fields[key]
            with self.assertRaises(TypeError):
                render_app_info(**fields)

    def test_invalid_xml_text(self):
        for bad in ('\x00', '\n', '\ud800', '\ufffe', 'a' * 256, None):
            self.reject(cmdline=bad)
            self.reject(plan_class=bad)

    def test_pinned_client_byte_buffers_are_respected(self):
        self.reject(cmdline='\u00e9' * 128)
        self.reject(plan_class='p' * 64)
        self.reject(plan_class='\u00e9' * 32)


if __name__ == '__main__':
    unittest.main()
