"""Synthetic evidence tests and ordinary-integer tests; no RTL/tools executed."""
import copy
import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest

from reference import verify_core27_prefetch_r2_offline as v

FPGA=Path(__file__).resolve().parents[1]
MANIFEST=FPGA/'results/throughput-20260929/core27-prefetch-r2-stage-v1/manifest.json'


def metric(label,aw,base,warm=False,read=True):
    n=1<<aw;ntt,setup=v.schedule(aw);words=(2*aw+2)*257
    row=dict(conversion=(n+15)//16+6,roots=0 if warm else words+5,ntt=ntt,
             carry=(n+15)//16+51,passes=2,base=base,profile_before=int(warm),
             profile_loads=int(not warm),profile_hits=int(warm),profile_words=0 if warm else words,
             seed_setup=setup,readback=int(read))
    row['crt']=(n+15)//16+62+max(0,97-row['roots']-ntt)
    row['cycles']=sum(row[k] for k in ('conversion','roots','ntt','crt','carry'))
    return label+' '+' '.join(k+'='+str(row[k]) for k in v.FIELDS)


def basic(aw=1):
    n=1<<aw;base=2*n+5
    one='1'+' 0'*(n-1);two='2'+' 0'*(n-1)
    raw=f'{n}\nLOAD a {base}\n{one}\nRUN a0 0\n{one}\nRUN a1 1\n{two}\n'
    log=metric('a0',aw,base)+'\n'+metric('a1',aw,base,True)+f'\nPASS n={n} squares=2 readbacks=2 aborts=0\n'
    return raw,log


def tar_bytes(path,data):
    with tarfile.open(path,'w:gz') as tar:
        for name,payload in data.items():
            member=tarfile.TarInfo(name);member.size=len(payload)
            tar.addfile(member,io.BytesIO(payload))


def fixture(root):
    """Synthetic AW7 report exercises verifier plumbing, not model correctness."""
    aw=7;n=1<<aw;base=2*n+5;one='1'+' 0'*(n-1)
    raw=f'{n}\nLOAD a {base}\n{one}\n';log=''
    for index in range(12):
        read=index not in (9,10)
        raw+=f'{"RUN" if read else "RUN_NOREAD"} a{index} 0\n{one}\n'
        log+=metric('a'+str(index),aw,base,index!=0,read)+'\n'
    log+=f'PASS n={n} squares=12 readbacks=10 aborts=0\n'
    for base in (2*n+5,1000000000):
        for at in (n-16,n-1):raw+=f'BADDIGIT_AT {base} {base} {at}\n'
    remote=v.SNAPSHOT.rsplit('/snapshot-v1/fpga',1)[0]+'/synthetic-aw7'
    scratch='/dev/shm/gfn16-prefetch-r2-synthetic'
    sources=json.loads(MANIFEST.read_text())['sources']
    tar_bytes(root/'sources.tar.gz',{name:(FPGA/name).read_bytes() for name in sources})
    generated={'V'+v.TOP+'.cpp':('unsigned V'+v.TOP+'::threads() const { return 1; }').encode(),
               'V'+v.TOP+'.h':b'// synthetic model header',
               'V'+v.TOP+'.mk':b'// synthetic makefile'}
    tar_bytes(root/'generated-sources.tar.gz',generated)
    (root/('V'+v.TOP)).write_bytes(b'\x7fELF synthetic executable; never run')
    (root/'vectors-aw7.txt').write_text(raw);(root/'segment0.txt').write_text(raw)
    command=['verilator','--cc','--exe','--build','-j','2','--threads','1','--top-module',v.TOP,
             '-GAW=7','-GNTT_LANES=64','--Mdir',scratch+'/build',
             *[v.SNAPSHOT+'/rtl/kernel/'+name+'.sv' for name in v.RTL_PINS],
             v.SNAPSHOT+'/rtl/tb/square_core27_stream_prefetch_r2_threaded.cpp']
    stages=[('verilator-version',['verilator','--version'],'Verilator synthetic\n'),
            ('compiler-version',['g++','--version'],'g++ synthetic\n'),('build',command,'synthetic build\n'),
            ('probe',[remote+'/V'+v.TOP,'--runtime-probe'],json.dumps(dict(context_threads=1,model_threads=1,expected_threads=1))),
            ('test-segment0',[remote+'/V'+v.TOP,remote+'/segment0.txt','profile'],log)]
    steps=[]
    for name,argv,text in stages:
        path=root/(name+'.log');path.write_text(text)
        steps.append(dict(name=name,command=argv,returncode=0,error=None,seconds=1.0,log=path.name,sha256=v.sha(path)))
    rows,_=v.audit_vectors(raw,log,aw)
    report=dict(status='passed',aw=aw,n=n,ntt_lanes=64,model_threads=1,compile_workers=2,sources=sources,
                tool_executable_sha256={'/tool/python':'0'*64,'/tool/g++':'1'*64,'/tool/verilator':'2'*64},
                tool_version='Verilator synthetic',compiler_version='g++ synthetic',python_version='synthetic',
                generated_source_sha256={name:v.digest(data) for name,data in generated.items()},scratch=scratch,
                compiler_temporary_directory=scratch+'/tmp',
                executable=remote+'/V'+v.TOP,executable_sha256=v.sha(root/('V'+v.TOP)),steps=steps,
                vectors=dict(sha256=v.digest(raw.encode()),squares=12,readbacks=10,fermat_chains=[],fusion_invalid_final_row_cases=4),
                segments=[dict(index=0,start=1,end=len(raw.splitlines()),sha256=v.digest(raw.encode()))],metrics=rows,
                limits=dict(affinity=[0,2],memory_max_bytes=6<<30,cpu_max=['200000','100000'],physical_cores=[[0,0],[0,1]]),
                scratch_reservation_bytes=512<<20,scratch_free_floor_bytes=2<<30,
                durable_reservation_bytes=64<<20,durable_free_floor_bytes=10<<30,
                host_memory_floor_bytes=4<<30,command_timeout_seconds=1800,
                artifacts={p.name:v.sha(p) for p in root.iterdir()})
    (root/'report.json').write_text(json.dumps(report))
    return report


class MathLogTests(unittest.TestCase):
    def test_all_supported_schedules(self):
        for aw in (1,5,7,16):
            rows,summary=v.audit_vectors(*basic(aw),aw)
            self.assertEqual((len(rows),summary['cold_runs'],summary['warm_runs']),(2,1,1))

    def test_wrong_math_and_equivalent_noncanonical_digits(self):
        raw,log=basic()
        for wrong in ('3 0','11 -1'):
            with self.assertRaisesRegex(ValueError,'oracle|noncanonical'):
                v.audit_vectors(raw.replace('2 0\n',wrong+'\n'),log,1)

    def test_every_counter_contract(self):
        raw,log=basic();line=log.splitlines()[0]
        for key in v.FIELDS:
            value=int(line.split(key+'=')[1].split()[0])
            changed=log.replace(key+'='+str(value),key+'='+str(value+1),1)
            with self.subTest(key=key),self.assertRaises(ValueError):v.audit_vectors(raw,changed,1)

    def test_footer_extra_metrics_and_garbage_rejected(self):
        raw,log=basic()
        for changed in (log.rsplit('PASS',1)[0],log+log.splitlines()[-1]+'\n',log+'unrecognized\n',log.replace('ntt=','NTT=')):
            with self.assertRaises(ValueError):v.audit_vectors(raw,changed,1)

    def test_abort_clears_cache_and_requires_reload(self):
        raw,log=basic()
        one='1 0';raw='2\nLOAD first 9\n1 0\nABORT convert-0 1\nLOAD_KEEP recovered 9\n1 0\nRUN a0 0\n1 0\n'
        log=metric('a0',1,9)+'\nPASS n=2 squares=1 readbacks=1 aborts=1\n'
        _,info=v.audit_vectors(raw,log,1);self.assertEqual(info['abort_labels'],['convert-0'])
        with self.assertRaises(ValueError):v.audit_vectors(raw.replace('LOAD_KEEP recovered 9\n1 0\n',''),log,1)
        with self.assertRaises(ValueError):v.audit_vectors(raw.replace('convert-0','unsupported'),log,1)

    def test_noread_chain_must_end_observed(self):
        raw,log=basic()
        raw=raw.replace('RUN a0','RUN_NOREAD a0');log=log.replace('readback=1','readback=0',1).replace('readbacks=2','readbacks=1')
        v.audit_vectors(raw,log,1)
        with self.assertRaises(ValueError):v.audit_vectors(raw.replace('RUN a1','RUN_NOREAD a1'),log.replace('readback=1','readback=0').replace('readbacks=1','readbacks=0'),1)

    def test_bad_input_vectors_must_really_be_invalid(self):
        raw,log=basic()
        for extra in ('BADBASE 9','BADDIGIT 9 1','BADDIGIT_AT 9 9 2'):
            with self.assertRaises(ValueError):v.audit_vectors(raw+extra+'\n',log,1)


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.report=fixture(self.root)

    def tearDown(self):self.temp.cleanup()

    def save(self): (self.root/'report.json').write_text(json.dumps(self.report))

    def test_complete_synthetic_receipt(self):
        result=v.verify(self.root,MANIFEST)
        self.assertEqual(result['status'],'verified_normal_profile');self.assertEqual(result['operations'],12)

    def test_unapproved_manifest_and_fresh_rehash_cannot_adopt_sources(self):
        alternate=self.root/'manifest.json';alternate.write_text(MANIFEST.read_text()+'\n')
        with self.assertRaisesRegex(ValueError,'pre-import manifest'):v.verify(self.root,alternate)
        self.report['sources']['reference/core27_prefetch_r2_regression.py']='f'*64;self.save()
        with self.assertRaisesRegex(ValueError,'pre-import manifest'):v.verify(self.root,MANIFEST)

    def test_artifact_drift(self):
        (self.root/'segment0.txt').write_text('corrupted')
        with self.assertRaisesRegex(ValueError,'artifact hash'):v.verify(self.root,MANIFEST)

    def test_compiled_closure_and_threads_rejected(self):
        original=copy.deepcopy(self.report)
        for flag,value in (('--threads','8'),('-GAW=7','-GAW=5'),('--top-module','wrong')):
            self.report=copy.deepcopy(original);command=self.report['steps'][2]['command'];index=command.index(flag)
            command[index if flag.startswith('-G') else index+1]=value;self.save()
            with self.assertRaisesRegex(ValueError,'compiled source'):v.verify(self.root,MANIFEST)

    def test_rehashed_probe_mismatch(self):
        path=self.root/'probe.log';path.write_text('{"context_threads":8,"model_threads":1,"expected_threads":1}')
        self.report['artifacts'][path.name]=v.sha(path);self.report['steps'][3]['sha256']=v.sha(path);self.save()
        with self.assertRaisesRegex(ValueError,'runtime context'):v.verify(self.root,MANIFEST)

    def test_report_metrics_cannot_diverge_from_log(self):
        self.report['metrics'][0]['conversion']+=1;self.save()
        with self.assertRaisesRegex(ValueError,'metrics vs raw'):v.verify(self.root,MANIFEST)

    def test_segment_holes_and_duplicate_steps(self):
        self.report['segments'][0]['start']=2;self.save()
        with self.assertRaisesRegex(ValueError,'segment partition'):v.verify(self.root,MANIFEST)
        self.report['segments'][0]['start']=1;self.report['steps'].append(self.report['steps'][-1]);self.save()
        with self.assertRaisesRegex(ValueError,'duplicate command'):v.verify(self.root,MANIFEST)

    def test_extra_generated_archive_member_rejected(self):
        path=self.root/'generated-sources.tar.gz'
        tar_bytes(path,{'extra.cpp':b'bad'})
        self.report['artifacts'][path.name]=v.sha(path);self.save()
        with self.assertRaisesRegex(ValueError,'archive membership'):v.verify(self.root,MANIFEST)

    def test_unsafe_names_and_symlink_artifact(self):
        for name in ('../escape','/tmp/absolute','a//b','a/./b','a\\b'):
            with self.assertRaises(ValueError):v.safe_name(name)
        (self.root/'linked').symlink_to(self.root/'segment0.txt')
        with self.assertRaises(ValueError):v.local_file(self.root,'linked')

    def test_nonfinite_negative_or_unbounded_duration_rejected(self):
        for duration in (float('nan'),float('inf'),-0.1,1801.1,True,'1'):
            self.report['steps'][0]['seconds']=duration;self.save()
            with self.subTest(duration=duration),self.assertRaisesRegex(ValueError,'step duration'):
                v.verify(self.root,MANIFEST)

    def test_compiler_temp_outside_private_scratch_rejected(self):
        self.report['compiler_temporary_directory']='/tmp';self.save()
        with self.assertRaisesRegex(ValueError,'compiler temporary directory'):v.verify(self.root,MANIFEST)


if __name__=='__main__':unittest.main()
