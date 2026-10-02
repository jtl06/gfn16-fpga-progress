"""Aethia-only event-controller simulation; not an arithmetic/NTT gate."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import signal
import subprocess
import tarfile
import time


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--compile-lock',type=Path,required=True)
    args=ap.parse_args()
    if platform.node().split('.')[0]!='aethia':
        raise SystemExit('RTL simulation restricted to aethia')
    root=Path(__file__).resolve().parents[1]
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    rtl=root/'rtl/kernel/genefer_ntt_pair_schedule.sv'
    bench=root/'rtl/tb/ntt_pair_schedule.cpp'
    source_files=[rtl,bench,Path(__file__)]
    hashes={str(p.relative_to(root)):sha(p) for p in source_files}
    report=dict(status='running',host=platform.node(),sources=hashes,steps=[],builds=[],
                scope='Fixed-latency group event/tag controller only; no NTT datapath, arithmetic, banking or physical result.')
    def save():
        (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    def run(name,command,diagnostic=None):
        begin=time.monotonic()
        p=subprocess.Popen(command,cwd=root,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                           text=True,start_new_session=True)
        timed_out=False
        try: log,_=p.communicate(timeout=900)
        except subprocess.TimeoutExpired:
            timed_out=True;os.killpg(p.pid,signal.SIGKILL);log,_=p.communicate()
        path=out/(name+'.log');path.write_text(log)
        passed=not timed_out and (p.returncode==0 if diagnostic is None else p.returncode==1 and diagnostic in log)
        report['steps'].append(dict(name=name,command=command,returncode=p.returncode,
                                    passed=passed,seconds=time.monotonic()-begin,
                                    log_sha256=sha(path),diagnostic=diagnostic,timed_out=timed_out))
        save();print(name,'PASS' if passed else 'FAIL',flush=True)
        if not passed:raise RuntimeError(name+': '+log[-2500:])
    def build(name,source,aw):
        if shutil.disk_usage(out).free<10<<30:raise RuntimeError('disk below10GiB')
        directory=out/name
        run(name,['flock','--timeout','600',str(args.compile_lock),
                  'verilator','--cc','--exe','--build','-j','2',
                  '--top-module','genefer_ntt_pair_schedule','--Mdir',str(directory),
                  f'-GGROUP_AW={aw}','-CFLAGS',f'-DGROUP_AW={aw}',str(source),str(bench)])
        exe=directory/'Vgenefer_ntt_pair_schedule'
        report['builds'].append(dict(name=name,group_aw=aw,source_sha256=sha(source),
                                    executable_sha256=sha(exe),executable=str(exe)))
        return str(exe)
    save()
    try:
        for aw in (1,4,16):
            exe=build(f'build-aw{aw}',rtl,aw);run(f'normal-aw{aw}',[exe])
        mutations=[
            ('root-tag',"GROUP_AW'(tick>>1)","GROUP_AW'((tick>>1)+TW'(1))",'root tag mismatch'),
            ('hold-phase','hold_first=read_b;','hold_first=read_a;','event mismatch'),
            ('early-commit',"tick>=TW'(14)","tick>=TW'(12)",'event mismatch'),
            ('early-done',"tick==twice_groups+TW'(12)","tick==twice_groups+TW'(10)",'active contract'),
            ('reset-busy','busy<=0;done<=0;error<=0;','busy<=1;done<=0;error<=0;','reset leaked events'),
            ('inflight-start','if(!busy) begin','if(!busy || start) begin','active contract'),
        ]
        original=rtl.read_text()
        for name,old,new,diagnostic in mutations:
            if original.count(old)!=1:raise ValueError('ambiguous mutation '+name)
            path=out/(name+'.sv');path.write_text(original.replace(old,new))
            exe=build('build-'+name,path,4);run('reject-'+name,[exe],diagnostic)
        if hashes!={str(p.relative_to(root)):sha(p) for p in source_files}:
            raise RuntimeError('source changed during gate')
        with tarfile.open(out/'source-snapshot.tar.gz','w:gz') as archive:
            for p in source_files:archive.add(p,arcname=str(p.relative_to(root)))
        report.update(status='passed',sources_rechecked=True,
                      source_archive_sha256=sha(out/'source-snapshot.tar.gz'))
    except BaseException as exc:
        report.update(status='failed',error=repr(exc));raise
    finally:save()


if __name__=='__main__':main()
