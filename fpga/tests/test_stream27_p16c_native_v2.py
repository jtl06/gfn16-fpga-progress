import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
from fpga.reference import stream27_p16c_native_v2 as p


class P16CPortableTests(unittest.TestCase):
    def test_harness_only_transport_delta(self):
        self.assertEqual(p.verify_bench()['parent_sha256'],p.PARENT_BENCH)

    def test_calendar_or_probe_change_refused(self):
        for before,after in [('FIRST=85','FIRST=84'),('expected_threads\\":1','expected_threads\\":2')]:
            with tempfile.TemporaryDirectory() as folder:
                root=Path(folder);(root/'rtl/tb').mkdir(parents=True)
                for name in ('stream27_p16c_aw6_v1.cpp','stream27_p16c_aw6_v2.cpp'):
                    shutil.copyfile(p.ROOT/'rtl/tb'/name,root/'rtl/tb'/name)
                target=root/'rtl/tb/stream27_p16c_aw6_v2.cpp'
                text=target.read_text();self.assertIn(before,text);target.write_text(text.replace(before,after))
                with patch.object(p,'ROOT',root),self.assertRaises(ValueError):p.verify_bench()

    def test_independent_event_footer(self):
        self.assertEqual(p.footer_counts(),dict(events=28583,physical=766,eligible=66,resets=374,aborts=91))

    def test_closed_unbound_packet_has_no_host_authority(self):
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder)/'packet';result=p.prepare(out);m=json.loads((out/'manifest.json').read_text())
            self.assertEqual(result['unchanged_rtl_files'],13);self.assertEqual(result['source_count'],17)
            self.assertEqual(m['host'],'UNBOUND_NO_DISPATCH')
            self.assertEqual(m['build']['parameters'],{'AW':6,'CONTEXTS':1})
            self.assertIn('-Werror=return-type',m['build']['cflags'])
            root=out/'inputs/fpga'
            self.assertEqual({str(x.relative_to(root)):p.sha(x) for x in root.rglob('*') if x.is_file()},m['sources'])
            self.assertEqual(m['probe']['expected_json'],dict(context_threads=1,model_threads=1,expected_threads=1))
            self.assertEqual(m['steps'][0]['expected_stdout'],'P16C_AW6_PASS events=28583 physical=766 eligible=66 resets=374 aborts=91\n')
            self.assertNotIn('lint_baseline',m)
            with self.assertRaisesRegex(ValueError,'fresh'):p.prepare(out)


if __name__=='__main__':unittest.main()
