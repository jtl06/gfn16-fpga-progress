"""External F2 asset import tests: scalar arithmetic only, no HDL/full NTT."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fpga.reference import root_lookahead_field_data_v3 as data
from fpga.reference import root_lookahead_field_host_v3 as host
from fpga.reference import root_lookahead_field_import_v3 as importer


class FieldImport(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.vector, self.receipt = self.root / 'vectors.txt', self.root / 'receipt.json'
        data.generate(5, 0, 'gcp-c4d-static23-v1', self.vector, self.receipt)

    def tearDown(self):
        self.temp.cleanup()
        host._profile_id = None
        host._last_limits = None

    def validate(self):
        return importer.validate_assets(self.vector, self.receipt, importer.sha(self.vector),
                                         importer.sha(self.receipt), 5, 0)

    def change_receipt(self, key, value):
        meta = json.loads(self.receipt.read_text())
        meta[key] = value
        self.receipt.write_text(json.dumps(meta))

    def change_vector(self, transform):
        self.vector.write_text(transform(self.vector.read_text()))
        meta = json.loads(self.receipt.read_text())
        meta.update(vector_sha256=importer.sha(self.vector), vector_bytes=self.vector.stat().st_size)
        self.receipt.write_text(json.dumps(meta))

    def test_scalar_asset_validates_without_inferred_native_execution(self):
        value = self.validate()
        self.assertFalse(value['full_transform_recomputed_by_importer'])
        self.assertTrue(value['outer_reference_execution_not_inferred'])
        self.assertFalse(value['native_RTL_executed'])

    def test_exact_asset_pin_and_regular_path_fail_closed(self):
        with self.assertRaisesRegex(ValueError, 'exact hash'):
            importer.validate_assets(self.vector, self.receipt, '0'*64,
                                     importer.sha(self.receipt), 5, 0)
        link = self.root / 'link.txt'
        link.symlink_to(self.vector)
        with self.assertRaisesRegex(ValueError, 'canonical regular'):
            importer.validate_assets(link, self.receipt, importer.sha(self.vector),
                                     importer.sha(self.receipt), 5, 0)

    def test_schema_type_source_profile_and_native_claim_mutants_reject(self):
        original = self.receipt.read_text()
        for key, value in [('schema', 'wrong'), ('cases', True),
                           ('frozen_arithmetic_parent_sha256', '0'*64),
                           ('native_RTL_executed', True), ('configured_static_profile', 'unknown'),
                           ('full_numeric_limits', {'fake': True}), ('source_hashes', {})]:
            with self.subTest(key=key):
                self.receipt.write_text(original)
                self.change_receipt(key, value)
                with self.assertRaises(ValueError):
                    self.validate()

    def test_header_rows_canonical_words_and_inputs_reject_even_when_repinned(self):
        original_vector, original_receipt = self.vector.read_text(), self.receipt.read_text()
        def replace_token(text, row, index, value):
            lines = text.splitlines()
            tokens = lines[row].split(' ')
            tokens[index] = value
            lines[row] = ' '.join(tokens)
            return '\n'.join(lines)+'\n'
        mutants = [lambda text: text.replace('F2FIELD2 5', 'F2FIELD2 8', 1),
                   lambda text: text+'\n',
                   lambda text: replace_token(text, 1, 0, '0'),
                   lambda text: replace_token(text, 2, 0, '01'),
                   lambda text: replace_token(text, 3, 0, '104857601'),
                   lambda text: replace_token(text, 2, 0, '2'),
                   lambda text: replace_token(text, 7, 0, '2'),
                   lambda text: replace_token(text, 20, 0, '1')]
        for index, mutation in enumerate(mutants):
            with self.subTest(index=index):
                self.vector.write_text(original_vector)
                self.receipt.write_text(original_receipt)
                self.change_vector(mutation)
                with self.assertRaises(ValueError):
                    self.validate()

    def test_no_full_numeric_function_called_by_import_validation(self):
        with (patch.object(importer.field, 'corpus', side_effect=AssertionError('no transform')),
              patch.object(importer.field, 'phases', side_effect=AssertionError('no transform')),
              patch.object(importer.field, 'cyclic', side_effect=AssertionError('no transform'))):
            self.validate()

    def test_aw16_preparation_rejects_small_asset_before_creating_output(self):
        output = self.root / 'role'
        with self.assertRaises(ValueError):
            importer.prepare(output, self.vector, self.receipt, importer.sha(self.vector),
                             importer.sha(self.receipt))
        self.assertFalse(output.exists())

    def test_prepare_bookkeeping_with_explicit_asset_validation_stub(self):
        # Exercises source closure/build/step construction, not AW16 data
        # qualification. Actual large data must pass the unmocked validator.
        output = self.root / 'role'
        with patch.object(importer, 'validate_assets', return_value={'test_stub': True}):
            result = importer.prepare(output, self.vector, self.receipt, importer.sha(self.vector),
                                      importer.sha(self.receipt))
        manifest = json.loads((output / 'role-manifest.json').read_text())
        self.assertEqual(manifest['build']['parameters']['AW'], 16)
        self.assertEqual(manifest['build']['runtime_threads'], 1)
        self.assertEqual(manifest['probe']['expected_json'],
                         dict(context_threads=1, model_threads=1, expected_threads=1))
        self.assertEqual(manifest['steps'][0]['validator']['config']['aw'], 16)
        self.assertEqual(manifest['steps'][1]['expected_returncode'], 1)
        self.assertEqual(manifest['steps'][1]['expected_stderr'], 'F2_FIELD_INTEGER_ORACLE\n')
        source = output / 'source/fpga'
        old = json.loads((importer.PARENT / importer.MANIFEST).read_text())
        for name, pin in old['sources'].items():
            self.assertEqual(importer.sha(source/name), pin)
        self.assertEqual(manifest['sources'],
                         {p.relative_to(source).as_posix(): importer.sha(p)
                          for p in source.rglob('*') if p.is_file()})
        self.assertTrue(result['reference_execution_requires_external_dispatcher_gate'])
        self.assertFalse(result['full_transform_recomputed_by_importer'])
        self.assertFalse(result['native_RTL_executed'])
        with (patch.object(importer, 'validate_assets', return_value={'test_stub': True}),
              self.assertRaisesRegex(ValueError, 'fresh canonical')):
            importer.prepare(output, self.vector, self.receipt, importer.sha(self.vector),
                             importer.sha(self.receipt))

    def test_prepare_rechecks_copied_asset_pins(self):
        # A changed file between validation and copy is not silently re-pinned.
        output = self.root / 'changed-role'
        vector_pin, receipt_pin = importer.sha(self.vector), importer.sha(self.receipt)
        original_copy = importer.shutil.copyfile
        def changed_copy(source, target, **kwargs):
            if Path(source) == self.vector:
                self.vector.write_text('changed after validation\n')
            return original_copy(source, target, **kwargs)
        with (patch.object(importer, 'validate_assets', return_value={'test_stub': True}),
              patch.object(importer.shutil, 'copyfile', side_effect=changed_copy),
              self.assertRaisesRegex(ValueError, 'copy exact hash')):
            importer.prepare(output, self.vector, self.receipt, vector_pin, receipt_pin)
        self.assertFalse((output / 'role-manifest.json').exists())


if __name__ == '__main__':
    unittest.main()
