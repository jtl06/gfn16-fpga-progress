"""Extra full-size chains on the frozen, already-gated streaming simulator.

No compilation or RTL modification. Execute RTL only on aethia. This extends
coverage, not a production PRP test or proof of the entire input domain.
"""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import random
import re
import subprocess
import time

GATE_SHA='c931027c88e0ce3b73de9b1cd110d33fb3d375b6c24fcf38680a82b1c754f7f9'
CORE_SHA='75eb580540fc6a7939f824182d244123e03e3b780e65e57722352564b145b648'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digits(value,base,n):
    if n<2 or n&(n-1) or not 0<=value<=base**n:
        raise ValueError('noncanonical value/size')
    if value==base**n:
        return [-1]+[0]*(n-1)
    powers={k:pow(base,k) for k in (1<<j for j in range(n.bit_length()))}
    def split(x,size):
        if size==1:return [x]
        half=size//2;high,low=divmod(x,powers[half])
        return split(low,half)+split(high,half)
    return split(value,n)


def vectors(path,n=65536,rounds=32):
    if type(rounds) is not int or rounds<2 or rounds>256:
        raise ValueError('bounded chain length2..256 required')
    cases=[]
    configurations=((604832956,930001),(604832956,930019),
                    (1000000000,930037),(2*n+6,930053))
    with path.open('x') as f:
        f.write(str(n)+'\n')
        for index,(base,seed) in enumerate(configurations):
            rng=random.Random(seed);modulus=pow(base,n)+1
            initial=rng.getrandbits(modulus.bit_length())%modulus
            value=initial;double_exponent=0;bits=[];checks=0
            label=f'long{index}-b{base}-seed{seed}'
            f.write(f'{"LOAD" if index==0 else "LOAD_KEEP"} {label} {base}\n')
            f.write(' '.join(map(str,digits(value,base,n)))+'\n')
            for step in range(rounds):
                bit=step if step<2 else rng.randrange(2)
                bits.append(bit);double_exponent=2*double_exponent+bit
                value=(value*value*(2 if bit else 1))%modulus
                readback=(step+1)%8==0 or step+1==rounds
                checks+=readback
                f.write(f'{"RUN" if readback else "RUN_NOREAD"} {label}-s{step}-d{bit} {bit}\n')
                f.write(' '.join(map(str,digits(value,base,n)))+'\n')
            # Independent exponent-form check of the sequential oracle logic.
            direct=pow(initial,1<<rounds,modulus)*pow(2,double_exponent,modulus)%modulus
            if direct!=value:raise AssertionError('chain oracle disagrees with direct modular exponentiation')
            cases.append(dict(label=label,base=base,seed=seed,operations=rounds,
                              readbacks=checks,double_bits=bits,direct_pow_checked=True,
                              final_integer_sha256=hashlib.sha256(value.to_bytes((value.bit_length()+7)//8 or 1,'big')).hexdigest()))
    return dict(n=n,cases=cases,squares=sum(x['operations'] for x in cases),
                readbacks=sum(x['readbacks'] for x in cases),sha256=sha(path))


def validate_log(log,metadata):
    expected=f"PASS n={metadata['n']} squares={metadata['squares']} readbacks={metadata['readbacks']} aborts=0"
    if log.splitlines()[-1:]!=[expected]:raise ValueError('missing exact completion counts')
    metrics=[]
    for line in log.splitlines():
        if ' cycles=' not in line:continue
        case=line.split()[0]
        values={k:int(v) for k,v in re.findall(r'(\w+)=(\d+)',line)}
        if values['cycles']!=sum(values[k] for k in ('conversion','roots','ntt','crt','carry')):
            raise ValueError('phase accounting mismatch')
        metrics.append(dict(case=case,**values))
    labels=[f"{c['label']}-s{i}-d{bit}" for c in metadata['cases'] for i,bit in enumerate(c['double_bits'])]
    if [x['case'] for x in metrics]!=labels:raise ValueError('missing/reordered operation metrics')
    if sum(x['readback'] for x in metrics)!=metadata['readbacks']:raise ValueError('readback mismatch')
    expected_rows=[(c['base'],int((j+1)%8==0 or j+1==c['operations']))
                   for c in metadata['cases'] for j in range(c['operations'])]
    for i,row in enumerate(metrics):
        if (row.get('base'),row.get('readback'))!=expected_rows[i]:
            raise ValueError('case radix/checkpoint mismatch')
        expected_cache=(0,4,0,4*(metadata['n']+2)) if i==0 else (15,0,4,0)
        if tuple(row[k] for k in ('cache_before','root_loads','root_hits','roots'))!=expected_cache:
            raise ValueError('unexpected cache ownership/reload')
    return metrics


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gate',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if not platform.node().split('.')[0].startswith('aethia'):
        raise SystemExit('RTL runtime restricted to aethia')
    if sha(args.gate)!=GATE_SHA:raise ValueError('wrong frozen gate')
    gate=json.loads(args.gate.read_text())
    if gate['status']!='passed' or gate['sources']['rtl/kernel/genefer_square_core27_stream.sv']!=CORE_SHA:
        raise ValueError('wrong core/gate status')
    builds=[b for b in gate['builds'] if b['name']=='build-aw16']
    if len(builds)!=1:raise ValueError('ambiguous model')
    build=builds[0];exe=Path(build['executable']);root=Path(build['configuration']['cwd'])
    def verify():
        if sha(exe)!=build['executable_sha256']:raise ValueError('executable changed')
        for name,h in gate['sources'].items():
            if sha(root/name)!=h:raise ValueError('gate source changed: '+name)
    verify();args.output.mkdir(parents=True,exist_ok=False)
    report=dict(status='running',gate_sha256=GATE_SHA,core_sha256=CORE_SHA,
                runner_sha256=sha(Path(__file__)),executable_sha256=sha(exe),
                sources=gate['sources'],new_compilation=False,timeout_seconds=3600)
    def save():
        (args.output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    save()
    try:
        probe=subprocess.run([str(exe),'--runtime-probe'],capture_output=True,text=True,timeout=30,check=True)
        observed=json.loads(probe.stdout)
        if observed!={'context_threads':8,'model_threads':8,'expected_threads':8}:
            raise ValueError('thread contract mismatch')
        report['runtime_probe']=observed
        metadata=vectors(args.output/'vectors.txt');report['vectors']=metadata;save()
        start=time.monotonic()
        with (args.output/'simulation.log').open('x') as log:
            run=subprocess.run([str(exe),str(args.output/'vectors.txt'),'cache'],stdout=log,stderr=subprocess.STDOUT,timeout=3600)
        report['seconds']=time.monotonic()-start;report['returncode']=run.returncode
        if run.returncode:raise ValueError('RTL simulation failed')
        logpath=args.output/'simulation.log'
        report['metrics']=validate_log(logpath.read_text(),metadata)
        verify()
        if sha(args.gate)!=GATE_SHA or sha(Path(__file__))!=report['runner_sha256']:
            raise ValueError('gate/runner changed during execution')
        if sha(args.output/'vectors.txt')!=metadata['sha256']:raise ValueError('vectors changed')
        report.update(status='passed',log_sha256=sha(logpath),sources_rechecked=True)
    except BaseException as exc:
        report.update(status='failed',error=repr(exc));save();raise
    save();print(json.dumps({k:report[k] for k in ('status','seconds','executable_sha256')},indent=2))


if __name__=='__main__':main()
