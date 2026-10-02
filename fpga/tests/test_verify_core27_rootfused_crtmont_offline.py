"""G4 offline tamper tests; no saved executable, simulator or full-N arithmetic."""
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import shutil
import tarfile
import tempfile
import unittest
from unittest.mock import patch
from fpga.reference import verify_core27_rootfused_crtmont_offline as v

BASE=Path(__file__).resolve().parents[1]/'results/throughput-20260929'
AW5=BASE/'core27-prefetch-r2-rootfused-crtmont-aw5-v1'
AW16=BASE/'core27-prefetch-r2-rootfused-crtmont-aw16-v1'


class G4OfflineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parent,cls.normal=v.helpers()
        cls.report=json.loads((AW5/'report.json').read_text())
        cls.manifest=json.loads((AW5/'approved-manifest.json').read_text())
        cls.order=v.source_contract(cls.report['sources'],cls.parent,cls.normal)
        cls.members=cls.normal.archive_members(AW5/'sources.tar.gz',cls.report['sources'])
        cls.generated=cls.normal.archive_members(AW5/'generated-sources.tar.gz',cls.report['generated_source_sha256'])

    def test_actual_aw5_passes_without_native_execution(self):
        with patch('subprocess.run',side_effect=AssertionError('no native')),patch('subprocess.Popen',side_effect=AssertionError('no native')):
            r=v.verify(AW5)
        self.assertEqual((r['operations'],r['readbacks'],len(r['abort_labels'])),(568,561,20))
        self.assertEqual((r['source_members'],r['generated_members']),(65,122))
        self.assertIn('fresh ordinary-integer',r['vector_oracle'])

    def test_actual_aw16_binds_parent_without_local_big_arithmetic(self):
        with patch.object(self.normal,'radix_integer',side_effect=AssertionError('no full-N oracle')):
            r=v.verify(AW16)
        self.assertEqual((r['operations'],r['readbacks'],r['generated_members']),(12,10,130))
        self.assertEqual(r['matched_cycle_delta'],{'crt':-45,'cycles':-45,'all_other_fields_identical':True})
        self.assertIn('previously verified',r['vector_oracle'])

    def test_source_closure_missing_extra_and_drift_rejected(self):
        for change in ('missing','extra','candidate','ancestor'):
            pins=dict(self.report['sources'])
            if change=='missing':pins.pop('reference/__init__.py')
            elif change=='extra':pins['reference/extra.py']='0'*64
            elif change=='candidate':pins['rtl/kernel/'+v.TOP+'.sv']='0'*64
            else:pins['rtl/kernel/'+v.PARENT_TOP+'.sv']='0'*64
            with self.subTest(change=change),self.assertRaises(ValueError):v.source_contract(pins,self.parent,self.normal)

    def test_all_semantic_source_deltas_fail_closed(self):
        for name in ('rtl/kernel/'+v.TOP+'.sv','rtl/tb/'+v.BENCH+'.cpp','rtl/tb/'+v.BENCH+'_threaded.cpp',
                     'rtl/kernel/genefer_ntt_banked27_prefetch_r2_orient8_rootfused_engine.sv'):
            members=dict(self.members);members[name]+=b'\n'
            with self.subTest(name=name),self.assertRaises(ValueError):v.source_delta(members,self.parent)

    def test_metadata_resource_and_scope_drift(self):
        for name,value in [('scope','ancestor'),('model_threads',2),('aw',7),('scratch_reservation_bytes',0),('status','failed')]:
            r=deepcopy(self.report);r[name]=value
            with self.subTest(name=name),self.assertRaises(ValueError):v.metadata(r,self.manifest,v.MANIFEST_SHA,self.order)
        r=deepcopy(self.report);r['limits']['physical_cores']=[[0,0],[0,0]]
        with self.assertRaises(ValueError):v.metadata(r,self.manifest,v.MANIFEST_SHA,self.order)

    def test_exact_commands_threads_flags_and_candidate_paths(self):
        for old,new in [('--threads','--threads-bad'),('2','4'),('-GNTT_LANES=64','-GNTT_LANES=16'),
                        (' '.join(v.FLAGS),'-std=c++17'),(v.SNAPSHOT+'/rtl/kernel/'+v.TOP+'.sv',v.SNAPSHOT+'/rtl/kernel/'+v.PARENT_TOP+'.sv')]:
            r=deepcopy(self.report);steps={x['name']:x for x in r['steps']};cmd=steps['build']['command'];cmd[cmd.index(old)]=new
            with self.subTest(old=old),self.assertRaises(ValueError):v.commands(r,steps,self.order)

    def test_generated_thread_identity_and_flags(self):
        cpp='V'+v.TOP+'.cpp';mk='V'+v.TOP+'.mk';log=(AW5/'build.log').read_text()
        for name,old,new in [(cpp,b'return 1;',b'return 2;'),(mk,b'-Werror=return-type',b'-Wno-error=return-type')]:
            generated=dict(self.generated);self.assertIn(old,generated[name]);generated[name]=generated[name].replace(old,new)
            with self.subTest(name=name),self.assertRaises(ValueError):v.generated_contract(generated,log)
        with self.assertRaises(ValueError):v.generated_contract(self.generated,log.replace('-DCORE27_PREFETCH_R2_RUNTIME_THREADS=1','-DCORE27_PREFETCH_R2_RUNTIME_THREADS=2'))

    def test_aw5_ordinary_integer_expected_digit_mutant(self):
        raw=(AW5/'vectors-aw5.txt').read_text();lines=raw.splitlines();i=next(i for i,x in enumerate(lines) if x.startswith('RUN '))+1
        values=lines[i].split();values[0]='1' if values[0]!='1' else '2';lines[i]=' '.join(values)
        with self.assertRaisesRegex(ValueError,'integer oracle'):
            v.audit_vectors('\n'.join(lines)+'\n',(AW5/'test-segment0.log').read_text(),5,self.normal)

    def test_candidate_crt_counter_not_restored_or_ignored(self):
        log=(AW5/'test-segment0.log').read_text();self.assertIn('crt=19',log)
        with self.assertRaises(ValueError):v.audit_vectors((AW5/'vectors-aw5.txt').read_text(),log.replace('crt=19','crt=64',1),5,self.normal)

    def test_manifest_and_dependency_identity_required(self):
        with self.assertRaises(ValueError):v.verify(AW5,'0'*64)
        with patch.object(v,'ROOT_AUDITOR_SHA','0'*64),self.assertRaises(ValueError):v.helpers()

    def copied(self,temporary):
        root=Path(temporary)/'archive';shutil.copytree(AW5,root);return root

    def test_resealed_report_metric_change_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=self.copied(d);r=json.loads((root/'report.json').read_text());r['metrics'][0]['cycles']+=1
            (root/'report.json').write_text(json.dumps(r))
            with self.assertRaises(ValueError):v.verify(root)

    def test_resealed_probe_mutant_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=self.copied(d);p=root/'probe.log';p.write_text(p.read_text().replace('"model_threads":1','"model_threads":2'))
            r=json.loads((root/'report.json').read_text());h=v.sha(p);r['artifacts']['probe.log']=h
            next(x for x in r['steps'] if x['name']=='probe')['sha256']=h
            (root/'report.json').write_text(json.dumps(r))
            with self.assertRaisesRegex(ValueError,'runtime'):v.verify(root)

    def test_artifact_omission_and_unindexed_source_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=self.copied(d);(root/'unreviewed.py').write_text('raise AssertionError')
            with self.assertRaisesRegex(ValueError,'unindexed'):v.verify(root)
        with tempfile.TemporaryDirectory() as d:
            root=self.copied(d);(root/'segment0.txt').unlink()
            with self.assertRaises(ValueError):v.verify(root)

    def test_parent_vector_and_metric_pins_cannot_be_resealed(self):
        with tempfile.TemporaryDirectory() as d:
            root=self.copied(d);p=root/'parent-metrics.json';p.write_text(p.read_text()+'\n')
            r=json.loads((root/'report.json').read_text());r['artifacts'][p.name]=v.sha(p);(root/'report.json').write_text(json.dumps(r))
            with self.assertRaisesRegex(ValueError,'pinned parent'):v.verify(root)

    def test_duplicate_archive_members_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'bad.tar.gz';raw=b'data'
            with tarfile.open(p,'w:gz') as t:
                for _ in range(2):info=tarfile.TarInfo('x');info.size=len(raw);t.addfile(info,io.BytesIO(raw))
            with self.assertRaises(ValueError):self.normal.archive_members(p,{'x':hashlib.sha256(raw).hexdigest()})


if __name__=='__main__':unittest.main()
