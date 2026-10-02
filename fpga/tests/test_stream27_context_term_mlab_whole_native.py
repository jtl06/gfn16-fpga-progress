import json
import unittest
from fpga.reference import stream27_context_term_mlab_whole_native as native


class TermMlabWholeNativeTests(unittest.TestCase):
    def test_both_complete_contracts_and_sources(self):
        for stage in ('aw8','full'):
            m,files,bundle=native.role(stage)
            parent=json.loads((native.BASE/(stage+'-normal')/'manifest.json').read_text())
            self.assertEqual(m['steps'],parent['steps'])
            self.assertEqual(m['probe'],parent['probe'])
            self.assertEqual(m['build']['parameters'],parent['build']['parameters'])
            self.assertEqual(len(bundle['files']),54)
            self.assertEqual(len(m['build']['sv_sources']),54 if stage=='aw8' else 55)
            self.assertFalse(m['term_mlab']['no_rw_check'])
            self.assertFalse(m['term_mlab']['native_qualified'])
            self.assertEqual(files[m['build']['cpp_source']],(native.BASE/(stage+'-normal')/'source/fpga'/parent['build']['cpp_source']).read_bytes())

    def test_full_observer_has_identifier_only_change(self):
        m,files,bundle=native.role('full')
        base=native.BASE/'full-normal';old=json.loads((base/'production-bundle.json').read_text())['top']
        path='rtl/'+m['build']['top']+'.sv'
        expected=native.binder.captured.binder.parent.re_identifier((base/'source/fpga'/path).read_text(),old,bundle['top']).encode()
        self.assertEqual(files[path],expected)


if __name__=='__main__':unittest.main()
