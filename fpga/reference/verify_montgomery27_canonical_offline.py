"""Read-only standalone-helper evidence audit. No runner/generator imports.

Never executes saved binaries. Checks ordinary-integer vector products and
token timing independently, then binds logs to pinned bench/RTL/build evidence.
Compiler execution and unarchived remote tool binaries remain trusted.
"""
import argparse
from collections import deque
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
import tarfile

TOP='genefer_montgomery_mul27_canonical_pipe'
SOURCE='/home/jtl/gfn-fpga-lab/agent-work/mont27-canonical/snapshot-v2/fpga'
MANIFEST_SHA='9af45c9423eeadc3b9ead5f5c0755e3392907b481104e3fdea6c1cd2d40d5faa'
FIELDS=((104857601,4190109697),(69206017,4225761281),(67239937,4227727361))
PINS={
 'rtl/kernel/genefer_montgomery_mul27_sparse_pipe.sv':'501d0ce309a3915f7aed0f3bde14ba1ee8d56ddc5f6abef1f2f5bb572d64db4b',
 'rtl/kernel/genefer_montgomery_mul27_canonical_pipe.sv':'1d29fffb22b5ab9414d83b2cdde4d4068d605b51d60bda6d7b5d47688e181352',
 'rtl/tb/montgomery27_canonical_pipe.cpp':'2dc07481ff42f258542d8576743e74b4de2d4c4c1232f5d9199dca97a7a29d84',
 'reference/montgomery27_canonical_structure.py':'9e98101e421ef347a46e2cfed4e928b92783dad5433c00232b8f9fd394f33e42',
 'reference/montgomery27_canonical_regression.py':'69bcb38673f0cf33ddb139b3962774428322c9d67422ff1cf28868f3728c9011',
}


def require(ok,message):
    if not ok:raise ValueError(message)


def digest(data):return hashlib.sha256(data).hexdigest()
def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def relative(name):
    require(isinstance(name,str) and name and not name.startswith('/') and '\\' not in name and
            str(PurePosixPath(name))==name and '..' not in PurePosixPath(name).parts,'unsafe relative name')
    return name


def file(root,name):
    path=root/relative(name)
    require(path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(root.resolve()),'missing/unsafe artifact')
    require(not any(p.is_symlink() for p in path.parents if p!=root and p.is_relative_to(root)),'symlink artifact parent')
    return path


def archive(path,pins):
    require(pins and all(re.fullmatch('[0-9a-f]{64}',h) for h in pins.values()),'archive hash table')
    for name in pins:relative(name)
    with tarfile.open(path) as tar:
        members=tar.getmembers()
        require(len(members)==len(pins) and {m.name for m in members}==set(pins),'archive membership')
        require(all(m.isfile() for m in members) and sum(m.size for m in members)<=128<<20,'archive type/size')
        data={}
        for m in members:
            content=tar.extractfile(m).read();require(digest(content)==pins[m.name],'archive member hash: '+m.name)
            data[m.name]=content
    return data


def vector_audit(text,p,q):
    require((p,q) in FIELDS,'valid arithmetic field required')
    R=1<<32;rinv=pow(R,-1,p);rows=[];pending=deque();checked=canceled=holds=0;branches=[0,0];bit26=False
    for clock,line in enumerate(text.splitlines()):
        require(re.fullmatch(r'[01] [01] \d+ \d+ \d+',line),'vector row syntax')
        reset,valid,a,b,value=map(int,line.split());rows.append((reset,valid,a,b))
        require(0<=a<R and 0<=b<R and value==a*b*rinv%p,'independent integer vector oracle')
        if not reset:canceled+=len(pending);pending.clear()
        elif valid:
            require(a<p and b<p,'noncanonical arithmetic vector')
            t=a*b;m=(t%R)*q%R;branches[int(t<m*p)]+=1
            pending.append((clock+3,value))
        if pending and pending[0][0]==clock:
            _,v=pending.popleft();checked+=1;bit26|=bool(v&(1<<26))
        else:holds+=1
    require(not pending and checked>1000 and min(branches)>0 and bit26,'pipeline/correction/top-bit coverage')
    # Audit directed coverage without invoking or reproducing the PRNG.
    cursor=0
    def expect(row):
        nonlocal cursor
        require(cursor<len(rows) and rows[cursor]==row,'directed vector/reset schedule')
        cursor+=1
    def valid_random():
        nonlocal cursor
        require(cursor<len(rows) and rows[cursor][:2]==(1,1),'reset refill schedule');cursor+=1
    expect((0,1,R-1,R-1))
    edges=sorted({0,1,2,p//2-1,p//2,p//2+1,p-3,p-2,p-1,(1<<26)-1,1<<26,(1<<26)+1,R%p})
    for a in edges:
        for b in edges:expect((1,1,a,b))
    for index in range(30000):
        require(cursor<len(rows) and rows[cursor][:2]==(int(index%251!=250),int(index%7!=6)),'random bubble/reset schedule');cursor+=1
    for age in range(4):
        expect((0,0,R-1,R-1));expect((1,1,p-1,p-1))
        for _ in range(age):expect((1,0,R-1,R-1))
        expect((0,1,R-1,R-1))
        for _ in range(5):expect((1,0,R-1,R-1))
        for _ in range(8):valid_random()
    for depth in range(1,5):
        for j in range(depth):expect((1,1,p-1-j,p-2-j))
        expect((0,1,R-1,R-1))
        for _ in range(8):valid_random()
    for _ in range(8):expect((1,0,R-1,R-1))
    require(cursor==len(rows),'extra/missing vector rows')
    result=dict(p=p,q=q,checked=checked,canceled=canceled,hold_checks=holds,cycles=len(rows),
                correction_branch_accepts=branches,reset_ages=[0,1,2,3],reset_occupancies=[1,2,3,4],
                result_bit26_witness=True,random_rows=30000)
    require((checked,canceled,holds,len(rows))==(25527,333,4767,30294),'fixed normal coverage')
    return result


def check_assertion(step,log,message,source):
    require(type(step['returncode']) is int and step['returncode'] in (-6,1,134),'assertion process status')
    require(step['expected_assertion']==message,'typed assertion role')
    lines=[i+1 for i,s in enumerate(source.splitlines()) if '$fatal(1,"'+message+'");' in s]
    require(len(lines)==1,'assertion source anchor')
    # Independent grammar: primary assertion, optional matching $stop trailer,
    # optional Aborting. A second unrelated fatal/error is never accepted.
    names={TOP+'.sv',SOURCE+'/rtl/kernel/'+TOP+'.sv'}
    output=[line for line in log.splitlines() if line]
    require(output,'missing assertion diagnostic')
    match=re.fullmatch(r'\[\d+\] %(?:Error|Fatal): (.+):(\d+): Assertion failed in TOP\.'+
                       re.escape(TOP)+r'(?:\.\w+)*: (.+)',output[0])
    require(match and match[1] in names and int(match[2])==lines[0] and match[3]==message,'exact assertion diagnostic')
    tail=output[1:]
    if tail and tail[0].startswith('%Error:'):
        trailer=re.fullmatch(r'%Error: (.+):(\d+): Verilog \$stop',tail.pop(0))
        require(trailer and trailer[1] in names and int(trailer[2])==lines[0],'mismatched stop trailer')
    if tail and tail[0]=='Aborting...':tail.pop(0)
    require(not tail,'extra assertion diagnostic')


def verify(root):
    root=Path(root);report=json.loads(file(root,'report.json').read_text());require(report.get('status')=='passed_standalone_helper','incomplete helper gate')
    require(report['sources']==PINS,'qualified five-source map')
    manifest=file(root,'approved-manifest.json');require(sha(manifest)==MANIFEST_SHA==report['manifest_sha256'],'approved manifest identity')
    approved=json.loads(manifest.read_text())
    require(approved['status']=='prepared_not_executed' and approved['sources']==PINS and approved['source_root']==SOURCE,'pre-import manifest contents')
    require(report['fields']==[list(f) for f in FIELDS],'normal field profile')
    for name,value in {'stages':4,'initiation_interval':1,'compile_workers':2,'model_threads':1,'radix_bits':32,
                       'durable_reservation_bytes':32<<20,'durable_free_floor_bytes':10<<30,
                       'scratch_reservation_bytes':512<<20,'scratch_free_floor_bytes':2<<30,'host_memory_floor_bytes':4<<30,
                       'command_timeout_seconds':300,'lock_wait_timeout_seconds':900}.items():
        require(type(report[name]) is int and report[name]==value,'configuration: '+name)
    limits=report['limits'];cpu=limits['cpu_max']
    require(limits['affinity']==[0,2] and 0<int(limits['memory_max_bytes'])<=6<<30 and len(cpu)==2 and
            0<int(cpu[0])<=2*int(cpu[1]) and len(limits['physical_cores'])==2 and
            len({tuple(c) for c in limits['physical_cores']})==2,'execution resource limits')
    scratch=report['scratch'];require(PurePosixPath(scratch).parent==PurePosixPath('/dev/shm') and
            PurePosixPath(scratch).name.startswith('gfn16-mont27-canonical-') and
            report['compiler_temporary_directory']==scratch+'/tmp','private compiler scratch')
    artifacts=report['artifacts']
    for name,h in artifacts.items():require(re.fullmatch('[0-9a-f]{64}',h) and sha(file(root,name))==h,'artifact hash: '+name)
    sources=archive(file(root,'sources.tar.gz'),PINS);rtl=sources['rtl/kernel/'+TOP+'.sv'].decode()
    steps={s['name']:s for s in report['steps']};require(len(steps)==len(report['steps']),'duplicate command role')
    for step in steps.values():
        duration=step['seconds'];require(type(duration) in (int,float) and math.isfinite(duration) and 0<=duration<=301,'command duration')
        require(step['error'] is None,'command timeout/resource/error')
        require(step['log']==step['name']+'.log' and artifacts.get(step['log'])==step['sha256'],'step log identity')
    expected_steps=set();expected_artifacts={'sources.tar.gz','approved-manifest.json'}
    def normal(name,command):
        expected_steps.add(name);require(name in steps,'missing command: '+name);step=steps[name]
        require(step['command']==command,'command argv: '+name)
        require(type(step['returncode']) is int and step['returncode']==0 and step['expected_assertion'] is None,'normal role status: '+name)
        return (root/step['log']).read_text()
    for tool in ('verilator','g++'):
        log=normal(tool+'-version',[tool,'--version']);require(log==report[tool+'_version'] and log.strip(),'tool version record')
    tool_pins=report['tool_executable_sha256']
    require(len(tool_pins)==3 and all(Path(p).is_absolute() and re.fullmatch('[0-9a-f]{64}',h) for p,h in tool_pins.items()) and report['python_version'],'tool hash/version metadata')
    build_specs=[(f'p{i+1}',p,q) for i,(p,q) in enumerate(FIELDS)]+[
        ('unsupported-modulus',3,4294967295),('invalid-inverse',FIELDS[0][0],FIELDS[0][1]^2)]
    builds={b['name']:b for b in report['builds']};require(len(builds)==5 and len(report['builds'])==5 and set(builds)=={b[0] for b in build_specs},'build role coverage')
    remote_root=None;generated_count=0;model_hashes={}
    for name,p,q in build_specs:
        b=builds[name];require(type(b['p']) is int and type(b['q']) is int and (b['p'],b['q'])==(p,q),'build P/Q role')
        command=['verilator','--cc','--exe','--build','-j','2','--threads','1','--top-module',TOP,
                 '--Mdir',scratch+'/'+name,f'-GP={p}',f'-GQ={q}',SOURCE+'/rtl/kernel/'+TOP+'.sv',SOURCE+'/rtl/tb/montgomery27_canonical_pipe.cpp']
        normal('build-'+name,command)
        exe='V'+TOP+'-'+name;require(b['executable']==exe and sha(file(root,exe))==b['sha256'],'model hash/name')
        model_hashes[name]=b['sha256'];expected_artifacts.update((exe,name+'-generated.tar.gz'))
        generated=archive(file(root,name+'-generated.tar.gz'),b['generated_sources']);generated_count+=len(generated)
        require(all('/' not in k and Path(k).suffix in ('.cpp','.h','.mk','.dat') for k in generated),'generated file roles')
        require(all('V'+TOP+suffix in generated for suffix in ('.cpp','.h','.mk')),'generated model closure')
        require(re.search(r'unsigned\s+V'+TOP+r'::threads\(\) const\s*\{\s*return 1;\s*\}',generated['V'+TOP+'.cpp'].decode()),'compiled thread identity')
        # Executable commands carry the original durable directory, independent
        # of where this read-only archive has been copied locally.
        test_name='probe-'+name if name.startswith('p') else 'reject-'+name
        require(test_name in steps,'missing execution role')
        remote=PurePosixPath(steps[test_name]['command'][0]);require(remote.name==exe and remote.is_absolute(),'remote model path')
        require(remote.parent.parent==PurePosixPath(SOURCE).parent.parent,'remote evidence scope')
        if remote_root is None:remote_root=remote.parent
        require(remote.parent==remote_root,'model evidence directory skew')
    summaries=[]
    require(set(report['vectors'])=={str(p) for p,_ in FIELDS},'vector field roles')
    for i,(p,q) in enumerate(FIELDS):
        name=f'p{i+1}';exe=str(remote_root/('V'+TOP+'-'+name));vector=f'vectors-{name}.txt';expected_artifacts.add(vector)
        payload=file(root,vector).read_text();summary=vector_audit(payload,p,q)
        require(report['vectors'][str(p)]=={**summary,'sha256':sha(root/vector)},'vector coverage metadata')
        probe=json.loads(normal('probe-'+name,[exe,'--runtime-probe']))
        require(probe==dict(context_threads=1,model_threads=1,expected_threads=1) and all(type(v) is int for v in probe.values()),'runtime thread probe')
        log=normal('normal-'+name,[exe,str(remote_root/vector),str(p)])
        footer='PASS P={p} checked={checked} canceled={canceled} hold_checks={hold_checks} cycles={cycles}'.format(**summary)
        require(log.strip()==footer,'normal arithmetic/timing/hold footer')
        for label,a,b in (('lhs-P',p,1),('rhs-P',1,p),('wide-lhs',1<<27,1),('wide-rhs',1,0xffffffff)):
            key='reject-'+name+'-'+label;expected_steps.add(key);require(key in steps,'missing input-domain rejection')
            step=steps[key];require(step['command']==[exe,'reject',str(p),str(a),str(b)],'input rejection argv')
            check_assertion(step,(root/step['log']).read_text(),'noncanonical Montgomery27 input',rtl)
        summaries.append(summary)
    for name,p,_,message in [('unsupported-modulus',3,4294967295,'unsupported sparse Montgomery27 modulus'),
                             ('invalid-inverse',FIELDS[0][0],FIELDS[0][1]^2,'invalid sparse Montgomery inverse')]:
        key='reject-'+name;expected_steps.add(key);step=steps[key]
        require(step['command']==[str(remote_root/('V'+TOP+'-'+name)),'reject',str(p)],'parameter rejection argv')
        check_assertion(step,(root/step['log']).read_text(),message,rtl)
    require(set(steps)==expected_steps,'unexpected/missing command role')
    expected_artifacts.update(step['log'] for step in steps.values())
    require(set(artifacts)==expected_artifacts,'unexpected/missing durable artifact role')
    return dict(status='verified_standalone_helper',valid_arithmetic_fields=3,normal_outputs=sum(s['checked'] for s in summaries),
                canceled_tokens=sum(s['canceled'] for s in summaries),hold_checks=sum(s['hold_checks'] for s in summaries),
                vector_edges=sum(s['cycles'] for s in summaries),input_assertion_rejections=12,parameter_assertion_rejections=2,
                field_summaries=summaries,source_members=5,generated_members=generated_count,artifacts=len(artifacts),
                report_sha256=sha(root/'report.json'),approved_manifest_sha256=MANIFEST_SHA,verifier_sha256=sha(__file__),
                model_sha256=model_hashes,tool_executable_sha256=tool_pins,
                limitation='Only three legal-field helper models establish arithmetic/latency evidence; the two invalid-parameter models only establish assertion rejection. No NTT/core integration, physical timing/resource or PRP claim. Compiler execution and unarchived remote tool binaries remain trusted; this audit executes no binaries.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('roots',type=Path,nargs='+')
    args=parser.parse_args();print(json.dumps([verify(root) for root in args.roots],indent=2))
