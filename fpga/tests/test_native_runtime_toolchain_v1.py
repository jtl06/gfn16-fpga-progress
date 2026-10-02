import hashlib
from pathlib import Path
import tempfile
import unittest
from fpga.tools import native_runtime_toolchain_v1 as runtime


class RuntimeSchema(unittest.TestCase):
    def test_explicit_isolated_tool_paths_and_module_dependencies(self):
        with tempfile.TemporaryDirectory(prefix='native-runtime-schema-') as tmp:
            root = Path(tmp).resolve()
            module = root/'module.so';module.write_bytes(b'isolated dependency fixture')
            optional = root/'optional-link';optional.symlink_to('unused-os-component')
            profile = dict(verilator_dir='/isolated/verilator/bin',compiler_path='/isolated/bin/compiler',
                compiler_alias='/isolated/bin/g++',python_path='/isolated/python/bin/python3',
                make_path='/isolated/deps/bin/make',env_path='/isolated/bin:/isolated/deps/bin:/usr/bin:/bin',
                python_module_paths=[str(root)],toolchain_files_sha256={str(module):hashlib.sha256(module.read_bytes()).hexdigest()},
                toolchain_symlinks={str(optional):'unused-os-component'})
            checked = runtime.verify_files(profile)
            self.assertEqual(checked['regular_files'],1)
            self.assertEqual(checked['symlinks'],1)
            self.assertEqual(runtime.configure(profile)['tool_paths']['make'],'/isolated/deps/bin/make')
            module.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'drift'):
                runtime.verify_files(profile)

    def test_ambiguous_paths_modules_without_inventory_and_link_changes_fail(self):
        for update in (dict(compiler_alias='g++'),dict(env_path=':/usr/bin'),
                       dict(python_module_paths=['/unadmitted/modules'])):
            with self.subTest(update=update),self.assertRaises(ValueError):
                runtime.configure(dict(verilator_dir='/usr/bin')|update)
        with tempfile.TemporaryDirectory(prefix='native-runtime-links-') as tmp:
            path=Path(tmp).resolve()/'link';path.symlink_to('other')
            with self.assertRaisesRegex(ValueError,'symlink'):
                runtime.verify_files(dict(verilator_dir='/usr/bin',toolchain_symlinks={str(path):'expected'}))


if __name__=='__main__':unittest.main()
