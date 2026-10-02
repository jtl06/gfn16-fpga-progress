"""Read-only retained native evidence; no local full-N integer recomputation."""
import gzip,json,hashlib
from pathlib import Path
from fpga.reference.anext_soak_owner_replay_v1 import archive
from fpga.reference.anext_upper_qualification_v3 import verify,CORE
from fpga.reference.anext_upper_soak_output_v1 import normalise
from fpga.reference.core27_t5b_soak_v1 import reference
from fpga.reference.anext_upper_small_prp_v1 import validate as prp_validate
ROOT=Path(__file__).resolve().parents[1]
def sha(raw):return hashlib.sha256(raw).hexdigest()
def need(ok,why):
    if not ok:raise ValueError(why)
def read(path,pin=None):
    raw=path.read_bytes();need(pin is None or sha(raw)==pin,'pinned native bytes '+str(path));return raw
def replay(kind):
    need(kind in ('prp','short','pilot'),'finite observed qualification')
    job=f'anext-upper-{kind}-q1-v1';e=ROOT/f'queue/evidence/{job}';p=e/'attempt-0/collected/output/native'
    done=json.loads(read(ROOT/f'queue/done/{job}.json'));gate_raw=read(e/'gate-receipt.json',done['dependency_gate']['sha256']);g=json.loads(gate_raw)
    r=json.loads(read(p/'report.json',g['report_sha256']));m=json.loads(read(p/'approved-manifest.json',g['manifest_sha256']))
    need(g['status']=='PASS_expected_contracts' and r['sources']==m['sources'],'machine gate/source closure')
    props=done['result']['properties'];need(props['Result']=='success' and props['ExecMainStatus']=='0' and props['MainPID']=='0' and not props['ControlGroup'],'authoritative terminal')
    for n,h in r['artifacts'].items():read(p/n,h)
    src=archive(p/'sources.tar.gz',r['sources']);gen=archive(p/'generated-sources.tar.gz',r['generated_source_sha256'])
    elf=gzip.decompress(read(p/'model.gz'));need(elf[:4]==b'\x7fELF' and sha(elf)==r['executable_sha256'],'native executable')
    role=ROOT/f'artifacts/anext-upper-qualification-{kind}-role-v3';rm=json.loads(read(role/'manifest.json'))
    need(m['build']==rm['build'] and m['probe']==rm['probe'] and m['steps']==rm['steps'],'actual finite source contract')
    need(all(m['sources'].get(n)==h for n,h in rm['sources'].items()),'all role source pins')
    verify();need(m['sources']['rtl/kernel/genefer_anext_upper_core_v1.sv']==CORE,'exact upper candidate')
    need(r['probe']==dict(context_threads=1,model_threads=1,expected_threads=1) and r['compile_workers']==2 and r['model_threads']==1,'actual serial probe')
    need(r['limits']['affinity'] in ([0,1],[2,3]) and r['limits']['memory_max_bytes']==24<<30 and r['limits']['swap_max_bytes']==0,'GCP24 caps')
    for k in ('lint_admission','build_admission'):
        need(not r[k]['fatal_class_counts'] and not r[k]['unknown_class_counts'] and not r[k]['error_streams'],'class-qualified source')
    results=[];ref=reference();malformed=0
    for step in m['steps']:
        run=next(x for x in r['steps'] if x['name']==step['name']);need(type(run['returncode']) is int and run['returncode']==step['expected_returncode'] and run['error'] is None,'typed native rc')
        out=read(p/run['log'],run['sha256']).decode();err=read(p/run['stderr_log'],run['stderr_sha256']).decode()
        assets={k:src[n].decode() for k,n in step['validator']['assets'].items()};cfg=step['validator']['config']
        if kind=='prp':
            value=prp_validate(out,err,run['returncode'],cfg,assets);need(value==r['validations'][step['name']],'native PRP validator result')
            result={'mode':cfg['mode'],'cases':len(value['cases']),'cycles':sum(x['cycles'] for x in value['cases'])}
            checker=lambda text:prp_validate(text,err,run['returncode'],cfg,assets)
        else:
            oracle=json.loads(assets['oracle']);converted,metrics=normalise(out,oracle,ref)
            value=ref.validate_rows(converted,err,run['returncode'],cfg,oracle)
            native=r['validations'][step['name']]
            need(native['candidate_core_sha256']==CORE and native['native_anext_metrics']==metrics and native['donor_provenance_unchanged'],'separate candidate/donor provenance')
            need(native['donor_reference_validation']['independent_gmpy2_boundary_replay'] is True,'retained admitted native GMP replay')
            def checker(text):
                c,_=normalise(text,oracle,ref);return ref.validate_rows(c,err,run['returncode'],cfg,oracle)
            result={k:value[k] for k in ('operations','doubles','readbacks','cycles') if k in value}
            result.update(negative=cfg['negative'],prefill_cold=metrics['cold_prefill'],prefill_warm=metrics['warm_prefill'])
        for bad in (out+'extra\n',out.rstrip('\n'),out.partition('\n')[2]):
            try:checker(bad)
            except (ValueError,AssertionError,KeyError):malformed+=1
            else:raise ValueError('malformed native output accepted')
        result.update(seconds=run['seconds']);results.append(result)
    return dict(status='PASS_owner_upper_qualification_native_replay',kind=kind,job=job,report_sha256=g['report_sha256'],gate_sha256=sha(gate_raw),manifest_sha256=g['manifest_sha256'],
        source_role_sha256=sha(read(role/'manifest.json')),candidate_core_sha256=CORE,invocation=props['InvocationID'],artifacts=len(r['artifacts']),sources=len(src),generated=len(gen),executable_sha256=r['executable_sha256'],results=results,
        malformed_output_negatives=malformed,native_peak_bytes=int(props['MemoryPeak']),local_full_N_integer_computations=0,local_HDL_execution=False,promotion_allowed=False)
if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('kind',choices=('prp','short','pilot'));print(json.dumps(replay(p.parse_args().kind),indent=2))
