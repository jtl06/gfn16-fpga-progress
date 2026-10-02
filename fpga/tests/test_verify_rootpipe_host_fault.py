from copy import deepcopy
import hashlib
import io
from pathlib import Path
import tarfile
import tempfile
import unittest

from fpga.reference import verify_rootpipe_host_fault as check

DIAGNOSTIC='[0] %Fatal: genefer_square_core27_stream_rootpipe.sv:288: Assertion failed in TOP.genefer_square_core27_stream_rootpipe.unnamedblk3: residue mask skew'

def fixture():
    sources={f'source{i}':'sha' for i in range(29)}
    tools={'python':'one','g++':'two','verilator':'three'}
    common={'sources':sources,'tool_executable_sha256':tools,'tool_version':'verilator pinned',
        'compiler_version':'compiler pinned','python_version':'python pinned'}
    sv=[str(check.SOURCE/check.HOST)]+[str(check.SOURCE/f'rtl/kernel/module{i}.sv') for i in range(14)]
    argv=['verilator','--cc','--exe','--build','-j','2','--threads','1','--top-module',check.TOP,
        '-GAW=7','-GNTT_LANES=64','--Mdir',str(check.CONTROL/'build-aw7'),*sv,
        str(check.SOURCE/'rtl/tb/square_core27_stream_rootpipe_threaded.cpp')]
    control={**common,'steps':[{'name':'build-aw7','command':argv}]}
    report={'status':'passed','scope':'AW7 host-quarter integration mutant only',
        'control_report_sha256':check.CONTROL_SHA,'tool_sha256':check.RUNNER_SHA,
        'source_sha256':sources,'tool_executable_sha256':tools,
        'tool_version':common['tool_version'],'compiler_version':common['compiler_version'],'python_version':common['python_version'],
        'durable_output':str(check.OUTPUT),'scratch':'/dev/shm/gfn16-rootpipe-host-fault-test',
        'compiler_temporary_directory':'/dev/shm/gfn16-rootpipe-host-fault-test/tmp',
        'limits':{'cpu_max':['200000','100000'],'memory_max_bytes':6*check.GiB,
            'affinity':[0,2],'physical_cores':[[0,0],[0,1]]},
        'scratch_reservation_bytes':512*check.MiB,'scratch_free_floor_bytes':2*check.GiB,
        'durable_reservation_bytes':32*check.MiB,'durable_free_floor_bytes':10*check.GiB,'host_memory_floor_bytes':4*check.GiB}
    old=str(check.CONTROL/'build-aw7'/('V'+check.TOP));new=str(check.OUTPUT/check.EXE);vec=str(check.OUTPUT/'vectors-aw7.txt')
    commands={'verilator-version':['verilator','--version'],'compiler-version':['g++','--version'],
        'control-probe':[old,'--runtime-probe'],'control':[old,vec,'cache'],
        'mutant-probe':[new,'--runtime-probe'],'reject-host-quarter':[new,vec,'cache']}
    build=list(argv);build[build.index('--Mdir')+1]=report['scratch']+'/build';build[build.index(str(check.SOURCE/check.HOST))]=str(check.OUTPUT/'mutant-host-quarter.sv')
    commands['build-mutant']=build
    report['steps']=[{'name':name,'failure':None,'expected_rejection':name=='reject-host-quarter',
        'returncode':-6 if name=='reject-host-quarter' else 0,'seconds':1.0,'command':commands[name]} for name in check.STEPS]
    return report,control


class HostFaultOfflineTests(unittest.TestCase):
    def test_complete_metadata_and_exact_build_delta(self):
        report,control=fixture();steps=check.report_contract(report,control)
        check.command_contract(report,control,steps)

    def test_incomplete_and_resource_error_rejected(self):
        for change in ('status','error','returncode','failure'):
            report,control=fixture()
            if change=='status':report['status']='failed_or_incomplete'
            elif change=='error':report['error']='disk floor'
            elif change=='returncode':report['steps'][-1]['returncode']=-9
            else:report['steps'][4]['failure']='host memory floor'
            with self.subTest(change=change),self.assertRaises(ValueError):check.report_contract(report,control)

    def test_source_tools_tmpfs_and_limits_are_pinned(self):
        for change in ('source','tool','tmp','memory','affinity'):
            report,control=fixture();report=deepcopy(report)
            if change=='source':report['source_sha256']['source0']='changed'
            elif change=='tool':report['tool_executable_sha256']['g++']='changed'
            elif change=='tmp':report['compiler_temporary_directory']='/tmp'
            elif change=='memory':report['limits']['memory_max_bytes']=7*check.GiB
            else:report['limits']['affinity']=[0,1]
            with self.subTest(change=change),self.assertRaises(ValueError):check.report_contract(report,control)

    def test_wrong_exe_vector_or_second_source_delta_rejected(self):
        for change in ('exe','vector','extra-source'):
            report,control=fixture();steps=check.report_contract(report,control)
            if change=='exe':steps['reject-host-quarter']['command'][0]='wrong-model'
            elif change=='vector':steps['control']['command'][1]='wrong-vector'
            else:steps['build-mutant']['command'].append('extra.sv')
            with self.subTest(change=change),self.assertRaises(ValueError):check.command_contract(report,control,steps)

    def test_mutation_is_one_exact_assignment_only(self):
        original='reset: read_group<=0;\nread_group<=host_group;\n'
        check.exact_mutation(original,original.replace('read_group<=host_group;','read_group<=0;'))
        for changed in (original,original.replace('read_group<=','other<=')+'extra',original.replace('read_group<=host_group;','read_group<=1;')):
            with self.assertRaises(ValueError):check.exact_mutation(original,changed)

    def test_exact_fatal_and_real_termination_required(self):
        self.assertTrue(check.semantic_rejection(-6,DIAGNOSTIC))
        for code in (0,-9,137,-11,True):self.assertFalse(check.semantic_rejection(code,DIAGNOSTIC))
        for output in ('expected residue mask skew',DIAGNOSTIC.replace(':288:',':287:'),
            DIAGNOSTIC.replace('TOP.genefer','TOP.other'),DIAGNOSTIC+'\n'+DIAGNOSTIC,
            DIAGNOSTIC+'\nPASS n=128'):
            self.assertFalse(check.semantic_rejection(1,output))

    def test_archive_hash_members_and_no_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'test.tar.gz';payload=b'valid source';digest=hashlib.sha256(payload).hexdigest()
            with tarfile.open(path,'w:gz') as tar:
                entry=tarfile.TarInfo('source.cpp');entry.size=len(payload);tar.addfile(entry,io.BytesIO(payload))
            self.assertEqual(check.archive_members(path,{'source.cpp':digest}),{'source.cpp':payload})
            with self.assertRaises(ValueError):check.archive_members(path,{'source.cpp':'wrong'})
            with self.assertRaises(ValueError):check.archive_members(path,{'other.cpp':digest})
            with tarfile.open(path,'w:gz') as tar:
                entry=tarfile.TarInfo('source.cpp');entry.type=tarfile.SYMTYPE;entry.linkname='/elsewhere';tar.addfile(entry)
            with self.assertRaises(ValueError):check.archive_members(path,{'source.cpp':digest})


if __name__=='__main__':unittest.main()
