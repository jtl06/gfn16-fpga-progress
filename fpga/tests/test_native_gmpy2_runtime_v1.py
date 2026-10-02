"""Bounded dependency topology/hash tests; no native import, install or network."""
import io
import stat
import unittest
import warnings
import zipfile

from fpga.tools import native_gmpy2_runtime_v1 as r


def archive(extra=None):
    files = {'gmpy2/__init__.py':b'not executed', 'gmpy2/gmpy2.cpython-314-x86_64-linux-gnu.so':b'not ELF; fixture only',
        'gmpy2.libs/libgmp-fixture.so':b'fixture',
        'gmpy2-2.3.1.dist-info/METADATA':b'Name: gmpy2\nVersion: 2.3.1\n',
        'gmpy2-2.3.1.dist-info/WHEEL':b'Root-Is-Purelib: false\nTag: cp314-cp314-manylinux_2_17_x86_64\n'}
    if extra:
        files.update(extra)
    result = io.BytesIO()
    with zipfile.ZipFile(result, 'w') as zipped:
        for name, content in files.items():
            zipped.writestr(name, content)
    return result.getvalue()


class RuntimeWheelTests(unittest.TestCase):
    def test_exact_native_package_topology_and_metadata(self):
        files = r.wheel_files(archive())
        self.assertEqual(len(files), 5)
        self.assertIn('gmpy2.libs/libgmp-fixture.so', files)
        self.assertEqual(r.WHEEL_SHA, '8749196c8bcd51612d989f5e509ea77d5c97c40b57eda9a863938facbe2b9eab')

    def test_unsafe_topology_absolute_and_parent_members_refused(self):
        for name in ('../escaped', '/absolute', 'gmpy2/../escape', 'different/__init__.py', 'gmpy2\\escaped'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                r.wheel_files(archive({name:b'bad'}))

    def test_symlink_and_duplicate_members_refused(self):
        for mode in (stat.S_IFLNK | 0o777, stat.S_IFIFO | 0o600):
            raw = io.BytesIO(archive())
            with zipfile.ZipFile(raw, 'a') as zipped:
                entry = zipfile.ZipInfo('gmpy2/unsafe'); entry.external_attr = mode << 16
                zipped.writestr(entry, b'unsafe')
            with self.assertRaises(ValueError):
                r.wheel_files(raw.getvalue())
        raw = io.BytesIO(archive())
        with zipfile.ZipFile(raw, 'a') as zipped, warnings.catch_warnings():
            warnings.simplefilter('ignore', UserWarning)
            zipped.writestr('gmpy2/__init__.py', b'duplicate')
        with self.assertRaises(ValueError):
            r.wheel_files(raw.getvalue())

    def test_normal_directory_entries_do_not_mutate_topology(self):
        raw = io.BytesIO(archive())
        with zipfile.ZipFile(raw, 'a') as zipped:
            zipped.writestr('gmpy2/', b'')
            zipped.writestr('gmpy2.libs/', b'')
        self.assertEqual(len(r.wheel_files(raw.getvalue())), 5)

    def test_wrong_version_or_pure_platform_cannot_import(self):
        for extra in ({'gmpy2-2.3.1.dist-info/METADATA':b'Name: gmpy2\nVersion: 2.3.0\n'},
                      {'gmpy2-2.3.1.dist-info/WHEEL':b'Root-Is-Purelib: true\nTag: py3-none-any\n'}):
            with self.assertRaises(ValueError):
                r.wheel_files(archive(extra))


if __name__ == '__main__':
    unittest.main()
