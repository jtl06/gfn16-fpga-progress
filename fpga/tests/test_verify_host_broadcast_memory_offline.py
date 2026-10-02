"""Corrupt-receipt contracts only; not RTL or a claim about an actual gate."""
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest

from fpga.reference import verify_host_broadcast_memory_offline as v

ROOT=Path(__file__).resolve().parents[1]


def fixture():
    plan=json.loads((ROOT/v.PLAN).read_text());pins,order=v.approved_sources(plan)
    oracle,footer=v.expected(8,1);profile=dict(aw=8,field=1,p=104857601,q=4190109697)
    manifest=dict(status='prepared_not_executed',source_root=str(v.SOURCE),sources=pins,
        compiled_source_order=order,plan_sha256=v.PLAN_SHA,profile=profile,expected_counts=oracle['counts'],
        archive_sha256='a'*64,runner_coverage_annotation=v.COVERAGE_NOTE)
    scratch='/dev/shm/gfn16-host-broadcast-memory-test';exe=str(v.SOURCE.parent.parent/'aw8-p1-test'/('V'+v.TOP))
    flags='-std=c++17 -DHOST_BROADCAST_AW=8 -DHOST_BROADCAST_P=104857601u -DHOST_BROADCAST_Q=4190109697u'
    argv=['verilator','--cc','--exe','--build','-j','2','--threads','1','--top-module',v.TOP,
        '-GAW=8','-GP=104857601','-GQ=4190109697','-CFLAGS',flags,'--Mdir',scratch+'/build',*[str(v.SOURCE/n) for n in order]]
    commands={'verilator-version':['verilator','--version'],'g++-version':['g++','--version'],
        'build':argv,'probe':[exe,'--runtime-probe'],'normal':[exe]}
    cases=v.case_matrix(8)
    for case in cases:commands['reject-'+'-'.join(map(str,case))]=[exe,'--illegal',*map(str,case)]
    report=dict(status='passed_host_memory_pair',scope='Standalone paired host-memory equivalence; no completed NTT operation',
        profile=profile,sources=pins,compiled_source_order=order,plan_sha256=v.PLAN_SHA,
        expected_counts=oracle['counts'],normal_counts=oracle['counts'],runner_coverage_annotation=v.COVERAGE_NOTE,
        illegal_cases=[list(c) for c in cases],scratch=scratch,compiler_temporary_directory=scratch+'/tmp',executable=exe,
        limits=dict(memory_max_bytes=6*v.GiB,cpu_max=['200000','100000'],affinity=[0,2],physical_cores=[[0,0],[0,1]]),
        compile_workers=2,model_threads=1,scratch_reservation_bytes=768*v.MiB,scratch_free_floor_bytes=2*v.GiB,
        durable_reservation_bytes=64*v.MiB,durable_free_floor_bytes=10*v.GiB,host_memory_floor_bytes=4*v.GiB,
        command_timeout_seconds=1800,lock_wait_timeout_seconds=1800,
        tool_executable_sha256={'/usr/bin/python':'1'*64,'/usr/bin/g++':'2'*64,'/usr/bin/verilator':'3'*64},python_version='recorded')
    report['steps']=[]
    for index,(name,command) in enumerate(commands.items()):
        case=cases[index-5] if index>=5 else None
        report['steps'].append(dict(name=name,command=command,returncode=-6 if case else 0,error=None,
            assertion_case=list(case) if case else None,seconds=1.0))
    return report,manifest,pins,order,oracle,footer


def diagnostic(case,absolute=False):
    who,kind,payload,quarter=case
    filename=(str(v.SOURCE/'rtl/kernel')+'/' if absolute else '')+v.CHILD+'.sv:395'
    hierarchy=f'TOP.{v.TOP}.instances[{0 if who=="baseline" else 1}].{who}.dut.child.memories[{quarter*16}]'
    return (f'EXPECT_CANONICAL_ASSERT instance={who} kind={kind} payload={payload} quarter={quarter}\n'
        f'[0] %Fatal: {filename}: Assertion failed in {hierarchy}: noncanonical NTT27 data write\n')


class HostBroadcastOfflineTests(unittest.TestCase):
    def test_pinned_source_closure_and_reviewed_hashes(self):
        report,manifest,pins,order,oracle,_=fixture()
        self.assertEqual(len(pins),14)
        for name,wanted in pins.items():self.assertEqual(v.sha(ROOT/name),wanted)
        steps=v.report_contract(report,manifest,pins,order,oracle);v.commands(report,steps,order)

    def test_exact_matrix_size_order_and_unique_roles(self):
        self.assertEqual([len(v.case_matrix(aw)) for aw in (1,5,8,16)],[12,18,30,30])
        for aw in (1,5,8,16):self.assertEqual(len(v.case_matrix(aw)),len(set(v.case_matrix(aw))))
        for change in ('missing','duplicate','order','role','extra'):
            r,m,p,o,e,_=fixture()
            if change=='missing':r['steps'].pop()
            elif change=='duplicate':r['illegal_cases'][-1]=r['illegal_cases'][0]
            elif change=='order':r['steps'][-1],r['steps'][-2]=r['steps'][-2],r['steps'][-1]
            elif change=='role':r['steps'][-1]['assertion_case']=None
            else:r['steps'].append(deepcopy(r['steps'][-1]))
            with self.subTest(change=change),self.assertRaises(ValueError):v.report_contract(r,m,p,o,e)

    def test_incomplete_resources_typedexit_and_footer_counts_rejected(self):
        for change in ('status','error','resource','seconds','signal','bool-exit','counter','threads','annotation'):
            r,m,p,o,e,_=fixture();r=deepcopy(r)
            if change=='status':r['status']='failed_or_incomplete'
            elif change=='error':r['steps'][-1]['error']='disk guard'
            elif change=='resource':r['limits']['affinity']=[0,1]
            elif change=='seconds':r['steps'][0]['seconds']=float('inf')
            elif change=='signal':r['steps'][-1]['returncode']=-9
            elif change=='bool-exit':r['steps'][-1]['returncode']=True
            elif change=='counter':r['normal_counts']['edges']-=1
            elif change=='threads':r['model_threads']=8
            else:r['runner_coverage_annotation']='old plan authorizes all runs'
            with self.subTest(change=change),self.assertRaises(ValueError):v.report_contract(r,m,p,o,e)

    def test_compile_parameter_source_model_and_command_identity(self):
        for change in ('extra-sv','width','macro','source','executable','illegal-argv'):
            r,m,p,o,e,_=fixture();steps=v.report_contract(r,m,p,o,e)
            if change=='extra-sv':steps['build']['command'].append('extra.sv')
            elif change=='width':steps['build']['command'][10]='-GAW=16'
            elif change=='macro':steps['build']['command'][14]=steps['build']['command'][14].replace('_AW=8','_AW=5')
            elif change=='source':steps['build']['command'][-1]='wrong.cpp'
            elif change=='executable':steps['normal']['command'][0]='wrong-executable'
            else:steps[list(steps)[-1]]['command'][-1]='0'
            with self.subTest(change=change),self.assertRaises(ValueError):v.commands(r,steps,o)

    def test_exact_all30_fatals_and_optional_matching_trailer(self):
        for case in v.case_matrix(8):
            for absolute in (False,True):
                text=diagnostic(case,absolute);self.assertTrue(v.rejection(-6,text,case))
                location=(str(v.SOURCE/'rtl/kernel')+'/' if absolute else '')+v.CHILD+'.sv:395'
                self.assertTrue(v.rejection(134,text+f'%Error: {location}: Verilog $stop\nAborting...\n',case))

    def test_wrong_bank_instance_line_payload_and_generic_failure_rejected(self):
        case=('candidate','vector','highbit',3);text=diagnostic(case)
        for code in (0,True,False,2,3,-9,-11,137):self.assertFalse(v.rejection(code,text,case))
        for bad in (text.replace('memories[48]','memories[0]'),text.replace('instances[1]','instances[0]'),
                    text.replace('.candidate.','.baseline.'),text.replace(':395',':396'),
                    text.replace('payload=highbit','payload=p'),text+'PASS\n',text+text,
                    text+'%Error: wrong.sv:395: Verilog $stop\n','std::bad_alloc\n','MISSING_CANONICAL_ASSERTION\n'):
            self.assertFalse(v.rejection(-6,bad,case))

    def test_generated_make_and_actual_compile_flags(self):
        r,m,p,o,e,_=fixture();steps=v.report_contract(r,m,p,o,e);flags=v.commands(r,steps,o)
        top='V'+v.TOP
        members={top+'.cpp':f'unsigned {top}::threads() const {{ return 1; }}'.encode(),top+'.h':b'header',
            top+'.mk':('VM_USER_CFLAGS = \\\n\t'+flags+' \\\n\n# next section\n').encode()}
        log='g++ '+flags+' -c -o host_broadcast_memory_pair.o '+str(v.SOURCE/'rtl/tb/host_broadcast_memory_pair.cpp')+'\n'
        v.generated_contract(members,log,flags)
        for changed in (log.replace('_AW=8','_AW=5'),log+log,log.replace('-std=c++17','-std=c++11')):
            with self.assertRaises(ValueError):v.generated_contract(members,changed,flags)
        bad=dict(members);bad[top+'.mk']=bad[top+'.mk'].replace(b'_AW=8',b'_AW=5')
        with self.assertRaises(ValueError):v.generated_contract(bad,log,flags)

    def test_archive_missing_extra_duplicate_link_and_hash_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'test.tgz';pins={'source.sv':hashlib.sha256(b'source').hexdigest()}
            for kind in ('normal','duplicate','link','extra'):
                with tarfile.open(path,'w:gz') as tar:
                    for name in (['source.sv','source.sv'] if kind=='duplicate' else ['source.sv','extra'] if kind=='extra' else ['source.sv']):
                        entry=tarfile.TarInfo(name)
                        if kind=='link':entry.type=tarfile.SYMTYPE;entry.linkname='/unsafe';tar.addfile(entry)
                        else:entry.size=6;tar.addfile(entry,io.BytesIO(b'source'))
                if kind=='normal':
                    self.assertEqual(v.archive_members(path,pins),{'source.sv':b'source'})
                    with self.assertRaises(ValueError):v.archive_members(path,{'source.sv':'0'*64})
                else:
                    with self.assertRaises(ValueError):v.archive_members(path,pins)

    def test_footer_oracle_is_expected_trace_not_rtl_observation(self):
        result,footer=v.expected(8,1)
        self.assertIn('edges=3656 read_words=3970 written_words=2021',footer)
        self.assertEqual(result['trace_sha256'],'12707d4e80fea7444dabf382085b9e4902058b6b85bab4d99d55623fe0d7723e')
        self.assertIn('no RTL execution',result['scope'])


if __name__=='__main__':unittest.main()
