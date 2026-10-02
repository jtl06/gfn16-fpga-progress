"""Read-only whole-core receipt and independent radix-integer vector audit.

Never imports or executes a simulator or project vector generator. Supports
AW1/5/7/16 and exact reset-boundary segmentation. Math is ordinary Python
integers, separate from the RTL's RNS/NTT/CRT/carry implementation.
"""
import argparse
from collections import Counter
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import tarfile

PINS={
 'rtl/kernel/genefer_ntt_banked27_rootpipe_engine.sv':'cab41579a4b96793f52c31a2864f74aeab3d023f23b50f5c8acce368f07d1967',
 'rtl/kernel/genefer_square_core27_stream_rootpipe.sv':'fa62aa4846c175d9bba2fe4375e566b2965bf175c6be061018b460cfb6412c5f',
 'rtl/kernel/genefer_ntt_banked27_host_rootpipe_engine.sv':'b78bde6ba663161f61f347465992d39e1590ba999be024ed208588005f3b485a',
 'rtl/tb/square_core27_stream_rootpipe.cpp':'61a52de98207a5f7109f587f279cfad9057c5ef0e978ad2ee95dac3accae64e5',
 'rtl/tb/square_core27_stream_rootpipe_threaded.cpp':'8e4ebc896b4e3014ca2db8b1cba3da55d01660f395cfc797f4cf980b5a183ca1',
 'reference/square_core27_rootpipe_structure.py':'be3b91a232fbb10ae9cdc95a92d6f044a76a825e9a2be689c68d8b9b36812bf1',
 'reference/square_core27_rootpipe_regression.py':'57e506800da41444495d7b6171336936f0a8a69ed695a6342acb6d698c0f2420'}
FIELDS=('cycles','conversion','roots','ntt','crt','carry','passes','base','cache_before','root_loads','root_hits','readback')

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def require(value,message):
    if not value:raise ValueError(message)

def radix_integer(words,base):
    """Small Horner blocks combined as integers; avoids quadratic full-N powers."""
    @lru_cache(None)
    def power(count):return pow(base,count)
    def block(start,end):
        if end-start<=64:
            value=0
            for word in reversed(words[start:end]):value=value*base+word
            return value
        middle=(start+end)//2
        return block(start,middle)+power(middle-start)*block(middle,end)
    return block(0,len(words))

def audit_vectors(raw,log,aw):
    lines=raw.splitlines();n=int(lines[0]);require(n==1<<aw,'vector size')
    metrics=[]
    for line in log.splitlines():
        if ' cycles=' not in line:continue
        label,*items=line.split();pairs=[item.split('=') for item in items]
        require(tuple(pair[0] for pair in pairs)==FIELDS,'metric field contract')
        row={key:int(value) for key,value in pairs};row.update(case=label,aw=aw,n=n);metrics.append(row)
    cache=0;x=None;i=1;j=0;aborts=[];commands=Counter();names=set();cold=warm=0;bases=set()
    while i<len(lines):
        words=lines[i].split();i+=1;command=words[0];commands[command]+=1
        if command in ('LOAD','LOAD_KEEP'):
            base=int(words[2]);bases.add(base);digits=list(map(int,lines[i].split()));i+=1
            require(len(digits)==n,'load width');modulus=pow(base,n)+1
            x=radix_integer(digits,base)%modulus
            if command=='LOAD':cache=0
        elif command in ('RUN','RUN_NOREAD'):
            name=words[1];bit=int(words[2]);require(name not in names and bit in (0,1),'case/bit identity');names.add(name)
            require(x is not None,'run without valid loaded/recovered state')
            expected=list(map(int,lines[i].split()));i+=1;require(len(expected)==n,'expected width')
            x=(x*x*(1<<bit))%modulus
            canonical_minus_one=expected==[-1]+[0]*(n-1)
            require(canonical_minus_one or all(0<=digit<base for digit in expected),'noncanonical expected digits')
            require(radix_integer(expected,base)%modulus==x,'independent integer oracle: '+name)
            row=metrics[j];j+=1
            require((row['case'],row['base'],row['cache_before'])==(name,base,cache),'transaction/cache order')
            require(row['readback']==int(command=='RUN'),'readback coverage')
            require(row['cycles']==sum(row[k] for k in ('conversion','roots','ntt','crt','carry')),'phase accounting')
            expected_ntt=3*((n+63)//64+9)+2*aw*(max(1,n//128)+10)+10
            require(row['ntt']==expected_ntt,'NTT schedule')
            require((row['root_loads'],row['root_hits'],row['roots'])==((0,4,0) if cache==15 else (4,0,4*(n+2))),'cache counters')
            require(2*n+4<base<=1000000000,'base range')
            if cache==15:warm+=1
            else:cold+=1
            if aw==1 and cache==15:require(row['crt']==98,'N2 warm backpressure reservation')
            cache=15
        elif command=='ABORT':aborts.append(words[1]);cache=0;x=None
        elif command in ('BADBASE','BADDIGIT','BADDIGIT_AT'):cache=0;x=None
        else:raise ValueError('unexpected vector command: '+command)
    require(j==len(metrics),'extra/missing metrics')
    footer=f'PASS n={n} squares={j} readbacks={commands["RUN"]} aborts={len(aborts)}'
    require(log.splitlines().count(footer)==1,'terminal coverage footer')
    return metrics,{'operations':j,'readbacks':commands['RUN'],'no_readback_operations':commands['RUN_NOREAD'],
        'abort_labels':aborts,'cold_runs':cold,'warm_runs':warm,'bases':sorted(bases),'commands':dict(commands)}

def verify(root):
    report=json.loads((root/'report.json').read_text());require(report['status']=='passed','incomplete gate')
    require(report['ntt_lanes']==64 and report['model_threads']==1,'lane/thread profile')
    require(len(report['aw'])==len(set(report['aw'])) and set(report['aw'])<={1,5,7,16},'AW profile')
    for name,digest in report['artifacts'].items():
        path=root/name;require(not Path(name).is_absolute() and path.resolve().is_relative_to(root.resolve()),'unsafe artifact path')
        require(sha(path)==digest,'artifact hash: '+name)
    archive=root/'sources.tar.gz';require(sha(archive)==report['source_archive_sha256'],'source archive hash')
    with tarfile.open(archive) as tar:
        require(set(tar.getnames())==set(report['sources']) and len(tar.getmembers())==len(report['sources']),'archive membership')
        for name,digest in report['sources'].items():
            require(tar.getmember(name).isfile(),'non-file source member')
            require(hashlib.sha256(tar.extractfile(name).read()).hexdigest()==digest,'source hash: '+name)
        for name,digest in PINS.items():require(report['sources'][name]==digest,'qualified source pin: '+name)
    steps={step['name']:step for step in report['steps']}
    require(len(steps)==len(report['steps']),'duplicate steps')
    for step in steps.values():
        require(step['returncode']==0 and step['error'] is None,'failed command')
        require(step['log'] in report['artifacts'],'unindexed step log')
        require(sha(root/step['log'])==step['sha256'],'step log changed')
    builds={row['aw']:row for row in report['builds']}
    require(len(builds)==len(report['builds']) and set(builds)==set(report['aw']),'build coverage')
    results=[];all_metrics=[]
    expected_steps={'verilator-version','compiler-version'}
    for aw in report['aw']:
        build=builds[aw];exe=root/f'build-aw{aw}'/'Vgenefer_square_core27_stream_rootpipe'
        require(sha(exe)==build['sha256'],'model hash')
        expected_steps.update((f'build-aw{aw}',f'probe-aw{aw}'))
        build_command=steps[f'build-aw{aw}']['command']
        for flag,value in (('--threads','1'),('-j','2'),('--top-module','genefer_square_core27_stream_rootpipe')):
            require(build_command.count(flag)==1 and build_command[build_command.index(flag)+1]==value,'build option: '+flag)
        require(f'-GAW={aw}' in build_command and '-GNTT_LANES=64' in build_command,'build AW/lanes')
        probe=steps[f'probe-aw{aw}'];require(probe['command']==[build['executable'],'--runtime-probe'],'runtime probe argv')
        require(json.loads((root/probe['log']).read_text())=={'context_threads':1,'model_threads':1,'expected_threads':1},'thread probe')
        vector=root/f'vectors-aw{aw}.txt';raw=vector.read_bytes();lines=raw.splitlines(keepends=True)
        require(sha(vector)==report['vectors'][str(aw)]['sha256'],'original vector hash')
        segments=[s for s in report['segments'] if s['aw']==aw]
        require([s['index'] for s in segments]==list(range(len(segments))) and segments,'segment index coverage')
        reconstructed=lines[0];metrics=[];combined=Counter();aborts=[];cold=warm=0;bases=set()
        for segment in segments:
            index=segment['index'];piece=root/f'aw{aw}-segment{index}.txt';payload=piece.read_bytes()
            expected_steps.add(f'test-aw{aw}-segment{index}')
            require(sha(piece)==segment['sha256'],'segment hash')
            require(payload==lines[0]+b''.join(lines[segment['start']:segment['end']]),'segment byte contract')
            reconstructed+=b''.join(payload.splitlines(keepends=True)[1:])
            step=steps[f'test-aw{aw}-segment{index}'];remote_piece=str(Path(build['executable']).parent.parent/piece.name)
            require(step['command']==[build['executable'],remote_piece,'cache'],'test executable/vector/cache argv')
            rows,summary=audit_vectors(payload.decode(),(root/step['log']).read_text(),aw)
            metrics+=rows;combined.update(summary['commands']);aborts+=summary['abort_labels']
            cold+=summary['cold_runs'];warm+=summary['warm_runs'];bases.update(summary['bases'])
        require(reconstructed==raw,'segments omit/duplicate original bytes')
        require(len({m['case'] for m in metrics})==len(metrics),'duplicate transaction ids')
        info=report['vectors'][str(aw)]
        require(len(metrics)==info['squares'] and sum(m['readback'] for m in metrics)==info['readbacks'],'profile total coverage')
        if aw in (1,5):require(set(('conversion','root','ntt','crt','carry','root0','root1','root2','root3'))<=set(aborts),'base reset phases missing')
        if aw==5:require(all(aborts.count(x)==2 for x in ('convert-m1','convert-0','convert-p1')) and aborts.count('crt-active')==1,'stream/conversion abort coverage')
        for chain in info['fermat_chains']:
            exponent=pow(chain['base'],1<<aw)
            require(pow(2,exponent,exponent+1)==int(chain['residue_hex'],16),'direct Fermat oracle')
        all_metrics+=metrics
        results.append({'aw':aw,'n':1<<aw,'operations':len(metrics),'readbacks':info['readbacks'],
            'no_readback_operations':combined['RUN_NOREAD'],'abort_labels':aborts,'cold_runs':cold,'warm_runs':warm,
            'bases':sorted(bases),'commands':dict(combined),'ntt_cycles':sorted({m['ntt'] for m in metrics}),
            'cycle_range':[min(m['cycles'] for m in metrics),max(m['cycles'] for m in metrics)]})
    require(all_metrics==report['metrics'],'reported metrics differ from raw logs')
    require(set(steps)==expected_steps,'unexpected/missing command stages')
    return {'status':'verified','report_sha256':sha(root/'report.json'),'source_archive_sha256':sha(archive),
        'artifacts':len(report['artifacts']),'source_members':len(report['sources']),'profiles':results,
        'verifier_sha256':sha(__file__),'method':'Fresh independent Python radix-integer squareDup oracle, exact artifacts/sources/segments/argv/logs/cycle/cache/readback/reset checks; no simulation',
        'limitation':'Only reported AW profiles; no board, physical timing or full GFN16 PRP qualification. Intermediate NOREAD states are checked by the final chain readback, not individually.'}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('roots',type=Path,nargs='+')
    args=parser.parse_args()
    print(json.dumps([verify(root) for root in args.roots],indent=2))
