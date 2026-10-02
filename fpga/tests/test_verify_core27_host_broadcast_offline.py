"""Native receipt contracts and ordinary-integer audits, no RTL execution."""
from copy import deepcopy
import json
from pathlib import Path, PurePosixPath
import unittest

from fpga.reference import verify_core27_host_broadcast_offline as v

ROOT=Path(__file__).resolve().parents[1]
RESULTS=ROOT/'results/throughput-20260929'


def source_fixture():
    original=json.loads((RESULTS/'core27-prefetch-r2-fault-seed-v1/approved-manifest.json').read_text())['sources']
    return dict(original,**v.EXTRA_PINS,**{v.RUNNER:v.RUNNER_SHA})


def fixture(aw=5):
    normal=v.normal_helpers();pins=source_fixture();order=v.source_contract(pins,normal)
    manifest=dict(status='prepared_not_executed',sources=pins,target=str(PurePosixPath(v.SNAPSHOT).parent),
                  top=v.TOP,supported_aw=[1,5,7,16],archive_sha256='a'*64)
    scratch='/dev/shm/gfn16-prefetch-r2-host-broadcast-test'
    exe=str(PurePosixPath(v.SNAPSHOT).parent.parent/'aw5-test'/('V'+v.TOP))
    argv=['verilator','--cc','--exe','--build','-j','2','--threads','1','--top-module',v.TOP,
        f'-GAW={aw}','-GNTT_LANES=64','--Mdir',scratch+'/build',*[v.SNAPSHOT+'/'+name for name in order],
        v.SNAPSHOT+'/rtl/tb/'+v.BENCH+'_threaded.cpp']
    command={'verilator-version':['verilator','--version'],'compiler-version':['g++','--version'],
             'build':argv,'probe':[exe,'--runtime-probe']}
    for i in range(2 if aw==16 else 1):command['test-segment'+str(i)]=[exe,str(PurePosixPath(exe).parent/f'segment{i}.txt'),'profile']
    report=dict(status='passed',top=v.TOP,scope='Single-profile normal format2 host-broadcast whole-core simulation',
        aw=aw,n=1<<aw,ntt_lanes=64,model_threads=1,compile_workers=2,sources=pins,compiled_source_order=order,
        manifest_sha256='b'*64,scratch=scratch,compiler_temporary_directory=scratch+'/tmp',executable=exe,
        scratch_reservation_bytes=768<<20,scratch_free_floor_bytes=2<<30,durable_reservation_bytes=64<<20,
        durable_free_floor_bytes=10<<30,host_memory_floor_bytes=4<<30,command_timeout_seconds=1800,lock_wait_timeout_seconds=1800,
        limits=dict(affinity=[0,2],memory_max_bytes=6<<30,cpu_max=['200000','100000'],physical_cores=[[0,0],[0,1]]),
        tool_executable_sha256={'/usr/bin/python':'1'*64,'/usr/bin/verilator':'2'*64,'/usr/bin/g++':'3'*64},python_version='recorded',
        steps=[dict(name=k,command=argv,returncode=0,error=None,seconds=1.0) for k,argv in command.items()])
    return report,manifest,order


class WholeHostBroadcastOfflineTests(unittest.TestCase):
    def test_exact43_sources_and_native16_compiled_closure(self):
        normal=v.normal_helpers();pins=source_fixture();order=v.source_contract(pins,normal)
        self.assertEqual(len(pins),43);self.assertEqual(len(order),16)
        for name,value in pins.items():self.assertEqual(v.sha(ROOT/name),value)
        self.assertIn('rtl/kernel/'+v.TOP+'.sv',order)
        self.assertNotIn('rtl/kernel/'+v.OLD_TOP+'.sv',order)
        self.assertNotIn('rtl/kernel/'+v.OLD_HOST+'.sv',order)
        for change in ('omit','extra','ancestor','candidate'):
            bad=dict(pins)
            if change=='omit':bad.pop('reference/__init__.py')
            elif change=='extra':bad['reference/extra.py']='0'*64
            elif change=='ancestor':bad['reference/build_cache.py']='0'*64
            else:bad['rtl/kernel/'+v.HOST+'.sv']='0'*64
            with self.subTest(change=change),self.assertRaises(ValueError):v.source_contract(bad,normal)

    def test_exact_core_host_and_bench_source_deltas(self):
        members={name:(ROOT/name).read_bytes() for name in source_fixture()};v.source_delta(members)
        for name in ('rtl/kernel/'+v.TOP+'.sv','rtl/kernel/'+v.HOST+'.sv','rtl/tb/'+v.BENCH+'.cpp','rtl/tb/'+v.BENCH+'_threaded.cpp'):
            changed=dict(members);changed[name]+=b'\n'
            with self.subTest(name=name),self.assertRaises(ValueError):v.source_delta(changed)

    def test_native_manifest_metadata_and_commands(self):
        for aw in (1,5,7,16):
            report,manifest,order=fixture(aw)
            steps=v.metadata(report,manifest,'b'*64,order);remote=v.commands(report,steps,order)
            self.assertEqual(remote.name,'V'+v.TOP)

    def test_reject_wrong_top_manifest_pending_failed_and_resource_metadata(self):
        for change in ('top','manifest','incomplete','error','bool-exit','memory','threads','segments'):
            r,m,order=fixture()
            if change=='top':r['top']=v.OLD_TOP
            elif change=='manifest':m['top']=v.OLD_TOP
            elif change=='incomplete':r['status']='running'
            elif change=='error':r['steps'][2]['error']='disk floor'
            elif change=='bool-exit':r['steps'][0]['returncode']=False
            elif change=='memory':r['limits']['memory_max_bytes']=7<<30
            elif change=='threads':r['model_threads']=8
            else:r['steps'].append(deepcopy(r['steps'][-1]))
            with self.subTest(change=change),self.assertRaises(ValueError):v.metadata(r,m,'b'*64,order)

    def test_native_build_rejects_old_wrapper_extra_source_or_wrong_size(self):
        for change in ('oldtop','oldhost','oldbench','width','extra','probe'):
            r,m,order=fixture();steps=v.metadata(r,m,'b'*64,order)
            if change=='oldtop':steps['build']['command'][9]=v.OLD_TOP
            elif change=='oldhost':steps['build']['command']=[x.replace('/'+v.HOST+'.sv','/'+v.OLD_HOST+'.sv') for x in steps['build']['command']]
            elif change=='oldbench':steps['build']['command'][-1]=v.SNAPSHOT+'/rtl/tb/'+v.OLD_BENCH+'_threaded.cpp'
            elif change=='width':steps['build']['command'][10]='-GAW=16'
            elif change=='extra':steps['build']['command'].append('extra.sv')
            else:steps['probe']['command'][0]='wrong'
            with self.subTest(change=change),self.assertRaises(ValueError):v.commands(r,steps,order)

    def test_frozen_baseline_vector_metric_pins_all_profiles(self):
        for aw in (1,5,7,16):
            root=RESULTS/f'core27-prefetch-r2-aw{aw}-v1';report=json.loads((root/'report.json').read_text())
            self.assertEqual(v.sha(root/'report.json'),v.BASELINE_REPORT_SHA[aw])
            self.assertEqual(v.sha(root/f'vectors-aw{aw}.txt'),v.VECTOR_SHA[aw])
            self.assertEqual(v.map_sha(report['metrics']),v.METRIC_SHA[aw])

    def test_reused_independent_integer_audit_and_reset_coverage(self):
        normal=v.normal_helpers()
        for aw,operations,readbacks,aborts in ((1,529,522,9),(5,568,561,20),(7,12,10,0)):
            root=RESULTS/f'core27-prefetch-r2-aw{aw}-v1'
            # Audit original archived raw vectors/logs directly as tests of the
            # reusable pure parser, not as candidate receipts or candidate PASS.
            raw=(root/f'vectors-aw{aw}.txt').read_text();log=(root/'test-segment0.log').read_text()
            metrics,coverage=normal.audit_vectors(raw,log,aw)
            self.assertEqual((len(metrics),coverage['commands']['RUN'],len(coverage['abort_labels'])),(operations,readbacks,aborts))
            self.assertEqual(v.map_sha(metrics),v.METRIC_SHA[aw])
            n=1<<aw;self.assertEqual(coverage['invalid_at'][-4:],[(b,b,i) for b in (2*n+5,10**9) for i in sorted({max(0,n-16),n-1})])

    def test_plain_integer_wrong_expected_word_and_old_conversion_rejected(self):
        normal=v.normal_helpers();root=RESULTS/'core27-prefetch-r2-aw1-v1'
        raw=(root/'vectors-aw1.txt').read_text();log=(root/'test-segment0.log').read_text()
        lines=raw.splitlines()
        for i,line in enumerate(lines):
            if line.startswith('RUN '):
                words=lines[i+1].split();words[0]='1' if words[0]!='1' else '0';lines[i+1]=' '.join(words);break
        with self.assertRaises(ValueError):normal.audit_vectors('\n'.join(lines)+'\n',log,1)
        with self.assertRaises(ValueError):normal.audit_vectors(raw,log.replace('conversion=7','conversion=10',1),1)

    def test_fullN_expected_R2_timing_not_oldprefetch(self):
        normal=v.normal_helpers();ntt,setup=normal.schedule(16)
        self.assertEqual((ntt,setup),(20558,815))
        warm=4096+6+ntt+4096+62+4096+51
        self.assertEqual((warm,warm+(2*16+2)*257+5),(32965,41708))

    def test_generated_newtop_and_bench_compilation_identity(self):
        top='V'+v.TOP;source=v.SNAPSHOT+'/rtl/tb/'+v.BENCH+'_threaded.cpp'
        members={top+'.cpp':f'unsigned {top}::threads() const {{ return 1; }}'.encode(),top+'.h':b'header',
            top+'.mk':('VM_USER_CFLAGS = \\\n\n# next section\n'+source).encode()}
        log='g++ -Os -c -o '+v.BENCH+'_threaded.o '+source+'\n'
        v.generated_contract(members,log)
        for changed in (log+log,log.replace(source,source.replace(v.BENCH,v.OLD_BENCH)),
                        log.replace('-Os','-Os -DCORE27_PREFETCH_R2_RUNTIME_THREADS=8')):
            with self.assertRaises(ValueError):v.generated_contract(members,changed)


if __name__=='__main__':unittest.main()
