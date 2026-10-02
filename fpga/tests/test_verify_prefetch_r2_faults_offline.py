"""Offline receipt-contract tests only; never execute a model or runner."""
from copy import deepcopy
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest

from fpga.reference import verify_prefetch_r2_faults_offline as v

FPGA=Path(__file__).resolve().parents[1]
CONTROL=FPGA/'results/throughput-20260929/core27-prefetch-r2-aw16-v1'


def vector(name):
    index,digit=(0,1636) if name=='seed-domain' else (256,1)
    label='fusion-'+name+'-impulse';words=[0]*65536;expected=[0]*65536
    words[index]=digit;expected[2*index]=digit**2
    return (f'65536\nLOAD {label} 1000000000\n'+' '.join(map(str,words))+
        f'\nRUN {label} 0\n'+' '.join(map(str,expected))+'\n').encode()


def fixture():
    control=json.loads((CONTROL/'report.json').read_text())
    out=v.PARENT/'fault-seed-test';scratch='/dev/shm/gfn16-prefetch-r2-fault-test'
    old=str(v.CONTROL/('V'+v.TOP));new=str(out/('V'+v.TOP+'-seed-domain'));vec=str(out/'directed-cold-aw16.txt')
    build=list(next(s['command'] for s in control['steps'] if s['name']=='build'))
    build[build.index('--Mdir')+1]=scratch+'/build'
    build[build.index(str(v.SOURCE/v.ROM))]=str(out/'mutant-root-profile27-r2.sv')
    commands={'verilator-version':['verilator','--version'],'g++-version':['g++','--version'],
        'control-probe':[old,'--runtime-probe'],'fresh-control':[old,vec,'profile'],
        'build-mutant':build,'mutant-probe':[new,'--runtime-probe'],'targeted-mutant':[new,vec,'profile']}
    report=dict(status='passed_targeted_semantic_rejection',mutation='seed-domain',
        scope='One AW16 phase0 fusion mutation, directed cold impulse square only',control_root=str(v.CONTROL),
        control_report_sha256=v.CONTROL_SHA,manifest_sha256=v.MANIFEST_SHA,harness_sha256=v.HARNESS_SHA,
        sources=deepcopy(control['sources']),tool_executable_sha256=deepcopy(control['tool_executable_sha256']),
        tool_version=control['tool_version'],compiler_version=control['compiler_version'],
        scratch=scratch,compiler_temporary_directory=scratch+'/tmp',
        limits=dict(memory_max_bytes=6*v.GiB,cpu_max=['200000','100000'],affinity=[0,2],physical_cores=[[0,0],[0,1]]),
        durable_reservation_bytes=32*v.MiB,durable_free_floor_bytes=10*v.GiB,
        scratch_reservation_bytes=512*v.MiB,scratch_free_floor_bytes=2*v.GiB,host_memory_floor_bytes=4*v.GiB,
        command_timeout_seconds=1800,
        steps=[dict(name=name,command=commands[name],returncode=1 if name=='targeted-mutant' else 0,
                    error=None,seconds=0.5) for name in v.STEPS])
    return report,control


class FusionFaultOfflineTests(unittest.TestCase):
    def test_metadata_and_exact_build_delta(self):
        report,control=fixture();steps=v.report_contract(report,control)
        self.assertEqual(v.command_contract(report,control,steps),'V'+v.TOP+'-seed-domain')

    def test_incomplete_resource_and_exit_errors_rejected(self):
        for change in ('status','error','step-error','signal','boolean','duration','missing-step'):
            report,control=fixture()
            if change=='status':report['status']='failed_or_inconclusive'
            elif change=='error':report['error']='disk floor'
            elif change=='step-error':report['steps'][4]['error']='host memory floor'
            elif change=='signal':report['steps'][-1]['returncode']=-6
            elif change=='boolean':report['steps'][-1]['returncode']=True
            elif change=='duration':report['steps'][0]['seconds']=float('nan')
            else:report['steps'].pop()
            with self.subTest(change=change),self.assertRaises(ValueError):v.report_contract(report,control)

    def test_pins_sources_tools_and_resources_rejected(self):
        for change in ('harness','source','tool','scratch','memory','smt','reserve'):
            report,control=fixture()
            if change=='harness':report['harness_sha256']='wrong'
            elif change=='source':report['sources'][v.ROM]='wrong'
            elif change=='tool':report['tool_executable_sha256']['extra']='wrong'
            elif change=='scratch':report['compiler_temporary_directory']='/tmp'
            elif change=='memory':report['limits']['memory_max_bytes']=7*v.GiB
            elif change=='smt':report['limits']['physical_cores']=[[0,0],[0,0]]
            else:report['durable_reservation_bytes']=0
            with self.subTest(change=change),self.assertRaises(ValueError):v.report_contract(report,control)

    def test_command_model_vector_second_delta_and_flags_rejected(self):
        for change in ('model','vector','extra-source','threads','rom'):
            report,control=fixture();steps=v.report_contract(report,control)
            if change=='model':steps['targeted-mutant']['command'][0]='wrong'
            elif change=='vector':steps['targeted-mutant']['command'][1]='wrong'
            elif change=='extra-source':steps['build-mutant']['command'].append('extra.sv')
            elif change=='threads':steps['build-mutant']['command'][7]='8'
            else:steps['build-mutant']['command'][14]='wrong.sv'
            with self.subTest(change=change),self.assertRaises(ValueError):v.command_contract(report,control,steps)

    def test_independent_integer_and_crt_witnesses(self):
        for name,wrong,word in (('seed-domain',41972152391961575983,961575983),('step-domain',1<<64,709551616)):
            info,roots=v.directed_oracle(name,vector(name))
            self.assertEqual(info['wrong_centered_coefficient'],wrong)
            self.assertEqual(info['wrong_first_digit'],word)
            self.assertEqual(len(roots),3)
            self.assertTrue(all(r['correct']!=r['mutant'] for r in roots))

    def test_vector_scope_and_oracle_corruption_rejected(self):
        payload=vector('seed-domain')
        for changed in (payload.replace(b'RUN ',b'RUN_NOREAD '),payload.replace(b'2676496',b'2676497'),
                        payload.replace(b'1636',b'1637'),payload+b'RUN extra 0\n',payload.replace(b'1000000000',b'999999999')):
            with self.assertRaises(ValueError):v.directed_oracle('seed-domain',changed)

    def test_exact_mutation_frozen_ancestor_and_no_second_delta(self):
        original=(FPGA/v.ROM).read_bytes()
        for name,(old,new) in v.MUTATIONS.items():
            changed=original.replace(old.encode(),new.encode())
            v.exact_mutation(original,changed,name)
            for bad in (original,changed+b'\n',changed.replace(b'module ',b'module wrong_')):
                with self.assertRaises(ValueError):v.exact_mutation(original,bad,name)
            with self.assertRaises(ValueError):v.exact_mutation(original+b'\n',changed,name)

    def test_positive_and_semantic_rejection_exactly_bound(self):
        _,control=fixture();info,_=v.directed_oracle('seed-domain',vector('seed-domain'))
        row=dict(control['metrics'][0],case=info['label'],base=info['base'])
        metric=row['case']+' '+' '.join(k+'='+str(row[k]) for k in v.FIELDS)
        positive=metric+'\nPASS n=65536 squares=1 readbacks=1 aborts=0\n'
        self.assertEqual(v.positive_log(positive,info,control['metrics'][0]),(metric,row))
        bad=metric+'\nsquare mismatch fusion-seed-domain-impulse index=0 got_low=961575983 expected=2676496\n'
        self.assertTrue(v.semantic_rejection(1,bad,info,metric))
        for code in (0,True,-6,-9,137):self.assertFalse(v.semantic_rejection(code,bad,info,metric))
        for changed in (bad.replace('961575983','1'),bad.replace('index=0','index=1'),bad+'PASS n=65536\n',
                        bad.replace('4102','4105'),'std::bad_alloc\n','%Fatal: coefficient bound\n'):
            self.assertFalse(v.semantic_rejection(1,changed,info,metric))
        for changed in (positive.replace('readbacks=1','readbacks=0'),positive.replace('4102','4105'),positive+'extra\n'):
            with self.assertRaises(ValueError):v.positive_log(changed,info,control['metrics'][0])

    def test_archive_members_hashes_duplicates_and_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'archive.tgz';payload=b'pinned';pins={'source.sv':v.digest(payload)}
            def make(kind):
                with tarfile.open(path,'w:gz') as tar:
                    for _ in range(2 if kind=='duplicate' else 1):
                        m=tarfile.TarInfo('source.sv')
                        if kind=='link':m.type=tarfile.SYMTYPE;m.linkname='/external';tar.addfile(m)
                        else:m.size=len(payload);tar.addfile(m,io.BytesIO(payload))
            make('normal');self.assertEqual(v.archive_members(path,pins),{'source.sv':payload})
            with self.assertRaises(ValueError):v.archive_members(path,{'source.sv':'bad'})
            for kind in ('duplicate','link'):
                make(kind)
                with self.assertRaises(ValueError):v.archive_members(path,pins)

    def test_artifact_corruption_and_outside_path_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();path=root/'evidence.log';path.write_bytes(b'original')
            pins={'evidence.log':v.digest(b'original')};v.artifact_files(root,pins)
            path.write_bytes(b'altered')
            with self.assertRaises(ValueError):v.artifact_files(root,pins)
            with self.assertRaises(ValueError):v.artifact_files(root,{'../outside':'irrelevant'})

    def test_actual_archived_seed_fault(self):
        root=FPGA/'results/throughput-20260929/core27-prefetch-r2-fault-seed-v1'
        if not root.exists():self.skipTest('retained result archive unavailable')
        self.assertEqual(v.sha(root/'report.json'),'154dc308b2dc393969cc8cc7c7b1e3661c6d00a080a1c093d3e6916cd8b0352e')
        result=v.verify(root,CONTROL)
        self.assertEqual(result['status'],'verified')
        self.assertEqual((result['durable_artifacts'],result['source_archive_members'],result['generated_archive_members']),(14,39,141))
        self.assertEqual(result['observed_wrong_word'],961575983)


if __name__=='__main__':unittest.main()
