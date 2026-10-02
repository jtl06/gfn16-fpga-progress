"""Independent stdlib-only archive/integer/D4 review; never executes native code."""
import argparse
from collections import deque
import gzip
import hashlib
import json
from pathlib import Path
import re
import tarfile

MANIFEST='8fcafdd702e7ffb4c42c692c7c49e8fe04c70c69dea213e402c47315d1274f57'
FIELDS=[104857601,69206017,67239937]
VECTORS={5:'c2208723b1ec08ca955810865588c008070e3390a6004734f9ef861c40ae64fe',16:'6066596729a9a1fa9650859d2e343719134eb7abb5553cba8f5c7ff1388e63ec'}


def need(ok,why):
    if not ok:raise ValueError(why)


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def archive(path,pins):
    seen={}
    with tarfile.open(path,'r:gz') as tar:
        for member in tar:
            name=member.name
            need(member.isfile() and name not in seen and not Path(name).is_absolute() and '..' not in Path(name).parts,'unsafe archive')
            seen[name]=hashlib.sha256(tar.extractfile(member).read()).hexdigest()
    need(seen==pins,'exact archive closure')
    return len(seen)


def oracle(text,aw):
    lines=text.splitlines();need(lines[0]==f'SBRED1 {aw} 8 16 9178','vector header')
    n=1<<aw;k=2*n+192;minimum=max(2*n+5,(2*k+2)//3+1)
    queue=deque([None]*4);residues=[0]*3;payload=0
    counts=dict(aw=aw,blocks=8,events=0,accepted=0,responses=0,errors=0,bubbles=0,resets=0,output_idle=0)
    typed=dict(accepted_good=0,accepted_error=0,discarded_good=0,discarded_error=0,negative_zero_inputs=0,c0_inputs=0,c1_inputs=0,int_min_rejections=0)
    for tick,line in enumerate(lines[1:]):
        row=list(map(int,line.split()));need(len(row)==12,'vector row width')
        rst,valid,kind,base,word,tag,ev,ee,*tail=row
        need(rst in (0,1) and valid in (0,1) and kind in (0,1) and 0<=base<1<<32 and 0<=word<1<<32 and 0<=tag<1<<16,'wire range')
        outvalid=outerror=0
        if not rst:
            for old in queue:
                if old is not None:typed['discarded_error' if old[0] else 'discarded_good']+=1
            queue=deque([None]*4);residues=[0]*3;payload=0;counts['resets']+=1
        else:
            old=queue.popleft();value=word-(1<<32) if word&(1<<31) else word
            legal=minimum<=base<=1000000000 and abs(value)<=(k if kind else base-1)
            queue.append((not legal,[value%p for p in FIELDS],tag) if valid else None)
            if valid:
                counts['accepted']+=1;typed['accepted_good' if legal else 'accepted_error']+=1
                typed['c1_inputs' if kind else 'c0_inputs']+=1
                typed['int_min_rejections']+=int(value==-(1<<31) and not legal)
                typed['negative_zero_inputs']+=int(value<0 and legal and any(value%p==0 for p in FIELDS))
            else:counts['bubbles']+=1
            if old is not None:
                outerror=int(old[0]);outvalid=1-outerror;payload=old[2]
                if outvalid:residues=old[1]
        need([ev,ee,*tail]==[outvalid,outerror,*residues,payload],f'independent integer/D4/hold mismatch {tick}')
        counts['events']+=1;counts['responses']+=outvalid;counts['errors']+=outerror;counts['output_idle']+=int(not(outvalid or outerror))
    need(all(x is None for x in queue),'D4 drained')
    counts.update(before_checks=2*counts['events'],edge_checks=counts['events'],field_checks=3*counts['events'])
    need(counts['responses']==typed['accepted_good']-typed['discarded_good'] and counts['errors']==typed['accepted_error']-typed['discarded_error'],'independent acceptance conservation')
    return counts,typed


def review(folder):
    folder=Path(folder);r=json.loads((folder/'report.json').read_text());aw=r['aw']
    need(aw in (5,16) and r['status']=='passed_signed_boundary_component_profile','successful scoped profile')
    need(sha(folder/'approved-manifest.json')==r['manifest_sha256']==MANIFEST,'manifest pin')
    m=json.loads((folder/'approved-manifest.json').read_text());need(r['sources']==m['sources'] and r['compiled']==m['compiled'] and r['bench']==m['bench'],'source and command closure')
    for name,h in r['artifacts'].items():
        p=folder/name;need(p.is_file() and not p.is_symlink() and p.resolve().is_relative_to(folder.resolve()) and sha(p)==h,'artifact hash: '+name)
    sources=archive(folder/'sources.tar.gz',r['sources']);generated=archive(folder/'generated-sources.tar.gz',r['generated_source_sha256'])
    raw=gzip.decompress((folder/'model.gz').read_bytes());exe=r['executable_identity']
    need(hashlib.sha256(raw).hexdigest()==exe['executable_sha256'] and len(raw)==exe['raw_bytes'] and sha(folder/'model.gz')==exe['gzip_sha256'] and (folder/'model.gz').stat().st_size==exe['gzip_bytes'],'compressed binary identity')
    need(sha(folder/'vectors.txt')==VECTORS[aw]==r['vectors']['sha256'],'exact input vectors')
    counts,typed=oracle((folder/'vectors.txt').read_text(),aw)
    need(counts==r['coverage'] and all(r['vectors'][k]==v for k,v in counts.items()),'all coverage counters')
    need(all(r['vectors']['typed_coverage'][k]==v for k,v in typed.items()),'typed arithmetic/reset conservation')
    text=(folder/'test.log').read_text();footers=re.findall(r'^SIGNED_BOUNDARY_PASS (.*)$',text,re.M)
    need(len(footers)==1,'unique typed footer');fields=[p.split('=',1) for p in footers[0].split()]
    need(len(fields)==len({x[0] for x in fields}) and {k:int(v) for k,v in fields}==counts,'footer exact counters')
    need(not any(s in text for s in ('%Error','%Fatal','MISMATCH')),'no native failure log')
    probe=dict(context_threads=1,model_threads=1,expected_threads=1)
    need(json.loads((folder/'probe.log').read_text())==r['probe']==probe,'runtime thread probe')
    need([s['name'] for s in r['steps']]==['verilator-version','compiler-version','build','probe','test'],'native step sequence')
    for step in r['steps']:need(step['returncode']==0 and step['error'] is None and sha(folder/step['log'])==step['sha256'],'native step status')
    build=['verilator','--cc','--exe','--build','-j','2','--threads','1','--top-module',r['top'],f'-GAW={aw}','-CFLAGS',f'-std=c++17 -Werror=return-type -DSBRED_AW={aw}','--Mdir',r['scratch']+'/build',*[m['target']+'/'+name for name in r['compiled']],m['target']+'/'+r['bench']]
    need(r['steps'][2]['command']==build and r['steps'][3]['command']==[r['executable'],'--runtime-probe'] and r['steps'][4]['command']==[r['executable'],str(Path(m['target']).parent.parent/f'aw{aw}-v1/vectors.txt')],'exact native commands')
    limits=r['limits'];quota,period=map(int,limits['cpu_max'])
    need(limits['affinity']==[4,6] and len({tuple(x) for x in limits['physical_cores']})==2 and limits['memory_max']<=4*(1<<30) and quota<=2*period and r['compile_workers']==2 and r['model_threads']==1,'recorded aggregate resource guards')
    return dict(status='PASS_independent_archived_signed_boundary_profile_review',aw=aw,report_sha256=sha(folder/'report.json'),artifacts=len(r['artifacts']),source_members=sources,generated_members=generated,coverage=counts,typed_arithmetic_checks=typed,executable_raw_sha256=exe['executable_sha256'],manifest_sha256=MANIFEST,scope='D4 signed c0/c1 all-three-field reduction component only; no compiled mutation/field integration/physical qualification',limitations=['No native executable/HDL/compiler executed by reviewer.','Toolchain and cgroup measurements remain archived worker attestations.','Native bench checked every recorded field and held invalid/error output; offline ordinary integer and D4 oracle independently replayed vectors, not a hardware rerun.'])


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('folders',nargs='+');a=p.parse_args()
    print(json.dumps([review(x) for x in a.folders],indent=2))
