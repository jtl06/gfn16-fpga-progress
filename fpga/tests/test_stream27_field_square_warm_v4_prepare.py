"""Successor packaging checks; arithmetic/calendar semantics stay in v3 tests."""
import hashlib
import json
from pathlib import Path
import tarfile
import tempfile
import unittest

from fpga.reference.stream27_field_square_warm_v4_prepare import prepare, TOP, BENCH
from fpga.reference.stream27_field_square_warm_v3_vectors import corpus


class WarmV4Preparation(unittest.TestCase):
    def test_bench_only_module_and_footer_names_change(self):
        root=Path(__file__).resolve().parents[1]
        old=(root/'rtl/tb/stream27_field_square_warm_v3.cpp').read_text()
        expected=old.replace('Vgenefer_stream27_field_square_aw5_warm_v3',
                             'Vgenefer_stream27_field_square_aw5_warm_v4').replace(
                             'FIELD_WARM_V3_','FIELD_WARM_V4_')
        self.assertEqual(expected,(root/BENCH).read_text())

    def test_closed_sources_unchanged_corpus_and_isolated_mutants(self):
        with tempfile.TemporaryDirectory() as temp:
            output=Path(temp)/'packet'
            report=prepare(output,'aethia')
            self.assertEqual(report['status'],'prepared_not_executed')
            self.assertEqual(set(report['snapshots']),{'control','wrong_cache_bank','stale_commit'})
            vector_text,metadata=corpus()
            self.assertEqual(report['vectors'],metadata)
            snapshots={}
            for role,snapshot in report['snapshots'].items():
                manifest=json.loads((output/report['manifests'][role]['path']).read_text())
                self.assertEqual(manifest['build']['top'],TOP)
                self.assertEqual(manifest['build']['cpp_source'],BENCH)
                self.assertIn('/stream27-field-square-warm-v4/',manifest['source_root'])
                self.assertNotIn('rtl/kernel/genefer_stream27_epoch_protocol_v3.sv',manifest['build']['sv_sources'])
                self.assertIn('rtl/kernel/genefer_stream27_epoch_protocol_v4.sv',manifest['build']['sv_sources'])
                source=output/role/'source/fpga'
                actual={p.relative_to(source).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
                        for p in source.rglob('*') if p.is_file()}
                self.assertEqual(actual,manifest['sources'])
                self.assertEqual(actual,snapshot['sources'])
                self.assertEqual((source/'field-square-warm-v3.txt').read_text(),vector_text)
                with tarfile.open(output/snapshot['archive']) as archive:
                    members=archive.getmembers()
                    self.assertTrue(all(member.isfile() for member in members))
                    archived={m.name.removeprefix('fpga/'):hashlib.sha256(archive.extractfile(m).read()).hexdigest()
                              for m in members}
                    self.assertEqual(len(members),len(actual))
                    self.assertEqual(archived,actual)
                snapshots[role]=actual
            control=snapshots['control']
            for role in ('wrong_cache_bank','stale_commit'):
                self.assertEqual(set(control),set(snapshots[role]))
                self.assertEqual([name for name in control if control[name]!=snapshots[role][name]],[TOP+'.sv'])
            with self.assertRaisesRegex(ValueError,'fresh preparation output'):
                prepare(output,'aethia')


if __name__=='__main__':unittest.main()
