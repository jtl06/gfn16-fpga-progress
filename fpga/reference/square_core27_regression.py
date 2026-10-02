"""Independent whole-integer oracle for autonomous RTL squareDup. Aethia only."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import platform
import random
import re
import subprocess
import resource
from math import prod
from .rns_reference import RNSPrime,RADIX
import time


def pack(digits,base):
    """Divide-and-conquer radix conversion, independent of RNS/NTT/carry RTL."""
    if len(digits)==1:return digits[0]
    half=len(digits)//2
    return pack(digits[:half],base)+pow(base,half)*pack(digits[half:],base)


def unpack(value,base,n):
    if n==1:return [value]
    half=n//2
    high,low=divmod(value,pow(base,half))
    return unpack(low,base,half)+unpack(high,base,half)


def write_vectors(path,aw,seed,prefix_carry=False):
    n=1<<aw;rng=random.Random(seed+aw);lines=[str(n)];case_count=0;readback_count=0;fermat_chains=[]
    def load(label,base,digits,keep=False):
        command="LOAD_KEEP" if keep else "LOAD"
        lines.extend((f"{command} {label} {base}"," ".join(map(str,digits))))
    def scenario(label,base,digits,bits,keep=False,readback_each=True):
        nonlocal case_count,readback_count
        load(label,base,digits,keep)
        modulus=pow(base,n)+1;x=pack(digits,base)%modulus
        for step,bit in enumerate(bits):
            x=x*x*(2 if bit else 1)%modulus
            expected=[-1]+[0]*(n-1) if x==modulus-1 else unpack(x,base,n)
            checked=readback_each or step==len(bits)-1
            command="RUN" if checked else "RUN_NOREAD"
            lines.extend((f"{command} {label}-s{step}-d{bit} {bit}"," ".join(map(str,expected))))
            case_count+=1
            readback_count+=int(checked)
        return x
    lines.extend(("BADBASE 0","BADBASE 1","BADBASE 1000000001",
                  "BADDIGIT 1000000000 -2","BADDIGIT 1000000000 1000000000"))
    for bad_at in (range(n) if aw<=5 else (0,n-1)):
        lines.append(f"BADDIGIT_AT 1000000000 -2 {bad_at}")
    minimum_base=2*n+5 if prefix_carry else 2
    lines.append(f"BADDIGIT {minimum_base} {minimum_base}")
    if prefix_carry:lines.extend((f"BADBASE {2*n+4}",f"BADBASE {2*n+3}","BADBASE 2"))
    if aw<=5:
        for base in (minimum_base,minimum_base+1,97,604832956,1000000000):
            patterns={"zero":[0]*n,"one":[1]+[0]*(n-1),"minusone":[-1]+[0]*(n-1),
                "max":[base-1]*n,"alternating":[(base-1)*(i%2) for i in range(n)],
                "high":[0]*(n-1)+[base-1],"random":[rng.randrange(base) for _ in range(n)]}
            for name,digits in patterns.items():scenario(f"b{base}-{name}",base,digits,(0,1,1))
        if aw==1:
            for base in (minimum_base,minimum_base+1):
                for x in range(base**n+1):
                    digits=[-1]+[0]*(n-1) if x==base**n else unpack(x,base,n)
                    scenario(f"exhaust-b{base}-x{x}",base,digits,(0,1))
        for phase in ("conversion","root","ntt","crt","carry","root0","root1","root2","root3"):
            load("abort-"+phase,97,[rng.randrange(97) for _ in range(n)])
            lines.append(f"ABORT {phase} 1")
            # Reset from ABORT must invalidate any partially or fully filled
            # phase cache; reload data without another reset and run immediately.
            scenario("recovered-"+phase,97,[rng.randrange(97) for _ in range(n)],(0,1),keep=True)
        scenario("after-aborts",97,[rng.randrange(97) for _ in range(n)],(0,1))
        for base in (minimum_base,604832956,1000000000,97):
            scenario(f"no-reset-b{base}",base,[rng.randrange(base) for _ in range(n)],(0,1),keep=True)
        even_base=minimum_base+(minimum_base%2)
        for base in (even_base,even_base+1):
            exponent=pow(base,n);bits=tuple(map(int,bin(exponent)[2:]))
            residue=scenario(f"fermat-b{base}",base,[1]+[0]*(n-1),bits,keep=True)
            direct=pow(2,exponent,exponent+1)
            if residue!=direct:raise AssertionError("Fermat squareDup chain disagrees with direct pow")
            fermat_chains.append({"base":base,"steps":len(bits),"residue_hex":hex(direct)})
    else:
        base=604832956
        scenario("full-random",base,[rng.randrange(base) for _ in range(n)],(0,1,1,0,1))
        scenario("full-minusone",base,[-1]+[0]*(n-1),(1,0))
        scenario("full-max-b1000000000",1000000000,[999999999]*n,(0,1),keep=True)
    if aw<=5:
        for base in (104857603,69206019,67239939,1000000000):
            edges=[-1,0,1,67239936,67239937,67239938,69206016,69206017,
                   104857600,104857601,134217727,134217728,999999999]
            valid=[x for x in edges if x<base]
            scenario(f"reduce27-boundaries-b{base}",base,[valid[i%len(valid)] for i in range(n)],(0,1),keep=True)
    chain_base=97 if aw<=5 else 604832956
    chain_bits=(0,1,1,0,1,0,0,1) if aw<=5 else (0,1,1)
    scenario("no-host-chain",chain_base,[rng.randrange(chain_base) for _ in range(n)],
             chain_bits,keep=True,readback_each=False)
    path.write_text("\n".join(lines)+"\n")
    return {"squares":case_count,"readbacks":readback_count,"seed":seed,"fermat_chains":fermat_chains,"sha256":hashlib.sha256(path.read_bytes()).hexdigest()}


def collect_metrics(output):
    metrics=[]
    pattern=re.compile(r"^(\S+) cycles=(\d+) conversion=(\d+) roots=(\d+) ntt=(\d+) crt=(\d+) carry=(\d+) passes=(\d+)(?: base=(\d+))?(?: cache_before=(\d+) root_loads=(\d+) root_hits=(\d+))?(?: readback=(\d+))?$")
    for path in sorted(output.glob("test-aw*.log")):
        aw=int(path.stem.removeprefix("test-aw"))
        for line in path.read_text().splitlines():
            match=pattern.fullmatch(line)
            if match:
                values=dict(zip(("cycles","conversion","roots","ntt","crt","carry","passes"),map(int,match.groups()[1:8])))
                if values["cycles"]!=sum(values[k] for k in ("conversion","roots","ntt","crt","carry")):
                    raise RuntimeError("phase accounting mismatch in log "+line)
                cache_before=int(match[10]) if match[10] else None
                metrics.append({"aw":aw,"n":1<<aw,"base":int(match[9]) if match[9] else None,"case":match[1],
                    "cache_before":cache_before,"root_cache_warm":cache_before==15 if cache_before is not None else None,
                    "root_loads":int(match[11]) if match[11] else None,"root_hits":int(match[12]) if match[12] else None,
                    "readback":bool(int(match[13])) if match[13] is not None else None,**values})
    return metrics


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--aw',type=int,nargs='+',default=[1,5,16])
    ap.add_argument('--lanes',type=int,choices=[16,64],nargs='+',default=[16,64])
    ap.add_argument('--seed',type=int,default=20260929)
    ap.add_argument('--mutations',action='store_true')
    a=ap.parse_args()
    if platform.node()!='aethia' or platform.system()!='Linux':raise RuntimeError('aethia only')
    resource.setrlimit(resource.RLIMIT_AS,(6<<30,6<<30))
    root=Path(__file__).resolve().parents[1];out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    names=['genefer_montgomery_mul32_pipe','genefer_montgomery_mul27_sparse_pipe',
           'genefer_digit_reduce27_pipe','genefer_sdp_ram32','genefer_ntt_banked27_engine',
           'genefer_ntt_banked27_host_engine','genefer_mod64_pipe','genefer_crt3_27_pipe',
           'genefer_carry_transfer_tree','genefer_sp_ram','genefer_div_recip_narrow',
           'genefer_carry_prefix_vector_pipe_v2','genefer_square_core27']
    sources=[root/'rtl/kernel'/f'{name}.sv' for name in names]
    cpp=root/'rtl/tb/square_core27.cpp';top='genefer_square_core27'
    fields=[(104857601,3),(69206017,5),(67239937,10)]
    basis=[RNSPrime(f'P27_{i}',p,pow(p,-1,RADIX),RADIX%p,RADIX*RADIX%p,g) for i,(p,g) in enumerate(fields)]
    assert RADIX==1<<32
    for prime in basis:
        prime.validate()
        for aw in range(1,17):prime.primitive_root(2<<aw)
    maximum=2*65536*999999999**2
    assert prod(p.p for p in basis)>2*maximum
    for label,attribute in [('P','p'),('Q','q'),('R2','r2'),('G','generator')]:
        line=next(line for line in sources[-1].read_text().splitlines() if f'{label}[0:2]' in line)
        actual=list(map(int,re.findall(r"32'd(\d+)",line)))
        assert actual==[getattr(p,attribute) for p in basis],(label,actual)
    report={'status':'running','host':platform.node(),'ancestor_sha256':'c6dad925fe58c17074722aabfee1d757232552465ecf0026fcc078373e08d5db',
        'radix_bits':32,'profiles':[[w,16] for w in a.lanes],'max_doubled_coefficient':maximum,
        'crt_modulus':prod(p.p for p in basis),'steps':[],'vectors':{},'metrics':[],
        'sources':{str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources+[cpp,Path(__file__),root/'reference/rns_reference.py']}}
    def run(name,command,reject=False):
        then=time.monotonic()
        r=subprocess.run(command,cwd=root,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=600)
        (out/f'{name}.log').write_text(r.stdout)
        report['steps'].append(dict(name=name,command=command,returncode=r.returncode,seconds=time.monotonic()-then,rejection=reject))
        print(name,r.returncode,r.stdout[-900:],flush=True)
        if not reject and r.returncode:raise RuntimeError(name+' failed')
        diagnostics=['mismatch','accepted','quarantine','lane skew','word skew','noncanonical','unsupported sparse','invalid sparse']
        if reject and (r.returncode==0 or not any(x in r.stdout for x in diagnostics)):raise RuntimeError(name+' mutation escaped')
    def build(name,w,aw,selected=None):
        directory=out/name
        options=['-CFLAGS','-O0'] if 'mutant' in name else []
        run(name,['verilator','--cc','--exe','--build','-j','2','--top-module',top,'--Mdir',str(directory),
                  f'-GAW={aw}',f'-GNTT_LANES={w}',*options,*map(str,selected or sources),str(cpp)])
        return str(directory/f'V{top}')
    try:
        for aw in a.aw:
            path=out/f'vectors-aw{aw}.txt';report['vectors'][str(aw)]=write_vectors(path,aw,a.seed,True)
        for w in a.lanes:
            for aw in a.aw:
                name=f'w{w}-aw{aw}';exe=build('build-'+name,w,aw)
                run('test-'+name,[exe,str(out/f'vectors-aw{aw}.txt'),'cache'])
        exe=build('build-unsupported-profile',32,1)
        run('test-unsupported-profile',[exe,'reject-profile'])
        if a.mutations:
            path=out/'mutation-vectors.txt';write_vectors(path,5,a.seed,True)
            defects=[
                ('raw-truncate',".digit(carry_words[h][31:0])",".digit({5'b0,carry_words[h][26:0]})"),
                ('convert-radix',".rhs(R2[f])",".rhs(32'd1)"),
                ('conversion-word',".digit(carry_words[h][31:0])",".digit(carry_words[0][31:0])"),
                ('root-order',".GENERATOR(G[f])",".GENERATOR(32'd1)"),
                ('inverse-phase',"step==3 ? 2'd2 : 2'd3","step==3 ? 2'd1 : 2'd3"),
                ('double',"double_reg ? (coefficient_words[h] <<< 1) : coefficient_words[h]","coefficient_words[h]"),
                ('coefficient-row',"AW'(issue_count) : AW'(write_count);","AW'(issue_count) : AW'(write_count+IO_STEP);"),
                ('digit-base',"carry_words[h]>=$signed({64'd0,base_reg})","carry_words[h]>$signed({64'd0,base_reg})"),
                ('cache-reset',"root_phases_loaded<=0; root_cache_hits<=0; root_cache_valid<=0;","root_phases_loaded<=0; root_cache_hits<=0; root_cache_valid<=15;"),
                ('cache-reload',"ROOT_CACHE && root_cache_valid[0]","1'b0"),
                ('immediate-start',"IDLE: if(start) begin","IDLE: if(start && !done) begin"),
                ('reducer-error',"assign reduction_error[f]=|reduce_error_words[f];",
                    "assign reduction_error[f]=(|reduce_error_words[f]) || (state==CONVERT && convert_input_valid);"),
                ('wrong-r2',"32'd45971250,32'd50081300,32'd63576045","32'd45971250,32'd50081300,32'd63576046"),
            ]
            for name,old,new in defects:
                text=sources[-1].read_text()
                if text.count(old)!=1:raise RuntimeError('mutation anchor '+name)
                changed=out/f'mutant-{name}.sv';changed.write_text(text.replace(old,new))
                exe=build('build-mutant-'+name,16,5,[*sources[:-1],changed])
                run('reject-'+name,[exe,str(path),'cache'],True)
            # Atomic-profile regression: replacing only CRT with the frozen31
            # implementation must not silently produce a valid27 result.
            oldcrt=root/'rtl/kernel/genefer_crt3_pipe.sv'
            changed=out/'mutant-old-crt.sv';changed.write_text(sources[-1].read_text().replace('genefer_crt3_27_pipe crt','genefer_crt3_pipe crt'))
            exe=build('build-mutant-old-crt',16,5,[*sources[:-1],oldcrt,changed])
            run('reject-old-crt',[exe,str(path),'cache'],True)
            # A64/16-specific fault must move real nonzero host quarters; N128
            # supplies eight16-word beats, unlike a single-quarter tiny test.
            host=sources[5];old="read_group<=host_group;"
            if host.read_text().count(old)!=1:raise RuntimeError('host quarter mutation anchor')
            changed=out/'mutant-host-quarter.sv';changed.write_text(host.read_text().replace(old,"read_group<=0;"))
            quarter_vectors=out/'mutation-host-quarter-vectors.txt';write_vectors(quarter_vectors,7,a.seed,True)
            selected=[changed if p==host else p for p in sources]
            exe=build('build-mutant-host-quarter',64,7,selected)
            run('reject-host-quarter',[exe,str(quarter_vectors),'cache'],True)
        report['status']='passed'
    except BaseException as error:report.update(status='failed',error=repr(error));raise
    finally:
        for w in a.lanes:
            for aw in a.aw:
                log=out/f'test-w{w}-aw{aw}.log'
                if not log.exists():continue
                for line in log.read_text().splitlines():
                    if ' cycles=' not in line:continue
                    values={k:int(v) for k,v in re.findall(r'(cycles|conversion|roots|ntt|crt|carry|passes|base|cache_before|root_loads|root_hits|readback)=(\d+)',line)}
                    report['metrics'].append(dict(ntt_lanes=w,io_lanes=16,aw=aw,case=line.split()[0],**values))
        (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':main()
