"""Read-only continuous native evidence replay; NO full-N integer arithmetic.

Native admitted GMP recomputation is retained and pinned. Locally only metadata,
byte hashes, phase arithmetic and existing canonical digit arrays are compared.
"""
import gzip
import hashlib
import json
import tarfile
from pathlib import Path,PurePosixPath
from fpga.reference.anext_soak_output_v1 import normalise,CORE_SHA
from fpga.reference.core27_t5b_soak_v1 import reference
from fpga.reference.anext_soak_source_v1 import verify as source_verify

ROOT=Path(__file__).resolve().parents[1]
JOB='anext-soak-continuous-aw16-q1-v2'
REPORT_SHA='d0accac2acef9bdb943e024dfd74c24d325b42b7e2238ce4a31d0506b3598c84'
GATE_SHA='6084c76bfeae243b1b9ce374dd3cedc6e57773c6d1f7db3506729330d83a87be'
MANIFEST_SHA='96c4d20f5b7f01fae248ea99d5e26b49e738d3d37ad79ba8c59e0b4079be0dad'
SHORT_REPORT_SHA='e81bd3ba94cb3c50c81e11ff32c8aa8a2bb186b92b464c4ee54ad3683cb7b56a'
def digest(data):return hashlib.sha256(data).hexdigest()
def need(value,message):
    if not value:raise ValueError(message)
def read(path,pin=None):
    data=Path(path).read_bytes();need(pin is None or digest(data)==pin,'evidence byte pin '+str(path));return data
def archive(path,pins):
    saved={}
    with tarfile.open(path,'r:gz') as t:
        for m in t:
            need(m.isfile() and not PurePosixPath(m.name).is_absolute() and '..' not in PurePosixPath(m.name).parts and m.name not in saved,'safe unique regular archive')
            data=t.extractfile(m).read();need(m.name in pins and digest(data)==pins[m.name],'exact archive member '+m.name);saved[m.name]=data
    need(set(saved)==set(pins),'complete archive closure');return saved

def replay():
    evidence=ROOT/f'queue/evidence/{JOB}';p=evidence/'attempt-0/collected/output/native'
    report=json.loads(read(p/'report.json',REPORT_SHA));manifest=json.loads(read(p/'approved-manifest.json',MANIFEST_SHA))
    gate=json.loads(read(evidence/'gate-receipt.json',GATE_SHA));done=json.loads(read(ROOT/f'queue/done/{JOB}.json'))
    need(gate['status']=='PASS_expected_contracts' and gate['report_sha256']==REPORT_SHA and gate['manifest_sha256']==MANIFEST_SHA,'actual gate bindings')
    properties=done['result']['properties']
    need(properties['InvocationID']=='f521556cacef4ae6a5c673d3e505e329' and properties['MainPID']=='0' and properties['ExecMainStatus']=='0' and properties['Result']=='success' and properties['ControlGroup']=='','authoritative terminal')
    for name,pin in report['artifacts'].items():read(p/name,pin)
    need(report['sources']==manifest['sources'],'source map binding')
    sources=archive(p/'sources.tar.gz',report['sources']);generated=archive(p/'generated-sources.tar.gz',report['generated_source_sha256'])
    exe=gzip.decompress(read(p/'model.gz'));need(exe[:4]==b'\x7fELF' and digest(exe)==report['executable_sha256'],'actual ELF identity')
    limits=report['limits'];need(limits['affinity']==[2,3] and limits['physical_cores']==[[0,2],[0,3]] and limits['memory_max_bytes']==24<<30 and limits['swap_max_bytes']==0 and limits['cpu_max']==['200000','100000'],'actual admitted caps')
    need(report['probe']==dict(context_threads=1,model_threads=1,expected_threads=1) and report['compile_workers']==2 and report['model_threads']==1,'real serial model probe')
    for name in ('lint_admission','build_admission'):
        a=report[name];need(not a['fatal_class_counts'] and not a['unknown_class_counts'] and not a['malformed_diagnostics'] and not a['error_streams'],'class-qualified lint/build')
    for name in ('reference/anext_soak_output_v1.py','reference/anext_composition_contract_v1.py','reference/core27_t5b_soak_v1.py','reference/core27_crtmont_soak_v1.py','reference/anext_soak_source_v1.py','rtl/tb/anext_soak_v1.cpp'):
        need(digest(read(ROOT/name))==manifest['sources'][name],'frozen replay/source contract')
    source_verify();need(manifest['sources']['rtl/kernel/genefer_anext_core_v1.sv']==CORE_SHA,'old direct candidate, not point successor')
    step=manifest['steps'][0];need(len(manifest['steps'])==1 and step['argv'][-1]=='{root}/donor/reference/continuous.txt','actual continuous argv despite opaque step name')
    run=report['steps'][-1];need(type(run['returncode']) is int and run['returncode']==0 and run['error'] is None,'actual model success')
    stdout=read(p/run['log'],run['sha256']).decode();stderr=read(p/run['stderr_log'],run['stderr_sha256']).decode()
    oracle=json.loads(sources[step['validator']['assets']['oracle']]);ref=reference()
    converted,metrics=normalise(stdout,oracle,ref);rows=ref.validate_rows(converted,stderr,0,{'negative':'none'},oracle)
    native=report['validations'][run['name']];nv=native['donor_reference_validation']
    need(native['native_anext_metrics']==metrics and native['candidate_core_sha256']==CORE_SHA and native['donor_provenance_unchanged'] is True,'native A-next phase/provenance result')
    need(nv['independent_gmpy2_boundary_replay'] is True and nv['uninterrupted_1000_square_rtl'] is True and nv['auxiliary_reference_runtime']['runtime_manifest_sha256']=='84fb40c8e6452d4b660d9302e83584dd3c4761aa6219495e57f2df582401cf0b','actual admitted native GMP replay')
    need((rows['operations'],rows['doubles'],rows['readbacks'],rows['cycles'])==(1000,488,11,21913089),'continuous1000 exact counts')
    need((metrics['cold_prefill'],metrics['warm_prefill'])==(10,990),'read-induced cold transitions')
    footer=json.loads(stdout.splitlines()[-1].partition(' ')[2])
    need(footer['resets']==1 and footer['loaded_digits']==65536 and footer['cache_cold']==1 and footer['cache_warm']==999,'retained state footer')
    # Mutate existing logs only; no new expected integers are calculated.
    lines=stdout.splitlines();bad=[]
    for key,value in [('resets',2),('loaded_digits',655360),('operations',999),('warm_prefill',999)]:
        f=dict(footer);f[key]=value;bad.append('\n'.join(lines[:-1]+['ANEXT_SOAK_PASS '+json.dumps(f)])+'\n')
    bad.extend([stdout+'extra\n','\n'.join(lines[1:])+'\n','\n'.join(lines[:-1])+'\n'])
    first=json.loads(lines[0].partition(' ')[2]);first['digits'][0]=(first['digits'][0]+1)%oracle['plan']['profile']['base']
    bad.append('\n'.join(['ANEXT_SOAK_CHECK '+json.dumps(first)]+lines[1:])+'\n')
    rejected=0
    for text in bad:
        try:
            c,_=normalise(text,oracle,ref);ref.validate_rows(c,'',0,{'negative':'none'},oracle)
        except (ValueError,AssertionError,KeyError):rejected+=1
        else:raise ValueError('malformed full-chain fixture accepted')
    # Reuse actual short negative witnesses with exact same model/driver, not a
    # fabricated new1000-run negative or a native arithmetic mutation claim.
    short=ROOT/'queue/evidence/anext-soak-short-aw16-q1-v2/attempt-0/collected/output/native'
    sr=json.loads(read(short/'report.json',SHORT_REPORT_SHA));sm=json.loads(read(short/'approved-manifest.json'));negatives=[]
    for name in manifest['build']['sv_sources']+[manifest['build']['cpp_source']]:need(sm['sources'][name]==manifest['sources'][name],'matched negative model/source')
    for s in sm['steps'][1:]:
        cfg=s['validator']['config'];observed=next(x for x in sr['steps'] if x['name']==s['name'])
        need(type(observed['returncode']) is int and observed['returncode']==1,'typed native short negative')
        assets=ROOT/'artifacts/anext-soak-short-aw16-role-v1/source/fpga'/s['validator']['assets']['oracle']
        o=json.loads(read(assets,sm['sources'][s['validator']['assets']['oracle']]))
        c,_=normalise(read(short/observed['log'],observed['sha256']).decode(),o,ref)
        checked=ref.validate_rows(c,read(short/observed['stderr_log'],observed['stderr_sha256']).decode(),1,cfg,o);negatives.append(checked)
    return dict(status='PASS_owner_continuous1000_native_evidence_replay',report_sha256=REPORT_SHA,gate_sha256=GATE_SHA,
        manifest_sha256=MANIFEST_SHA,invocation=properties['InvocationID'],local_log_contract=rows,
        retained_native_reference_validation=nv,
        phase_counts=dict(cold_prefill=10,warm_prefill=990,root_loads=1,root_hits=999,resets=1,loaded_digits=65536),
        artifact_files=len(report['artifacts']),source_files=len(sources),generated_files=len(generated),executable_sha256=report['executable_sha256'],
        native_tool_sha256=report['tool_sha256'],native_model_seconds=run['seconds'],native_packet_seconds=report['seconds'],
        native_peak_bytes=int(properties['MemoryPeak']),negative_log_fixtures=rejected,matched_short_native_negative_witnesses=negatives,
        native_reference_recomputed=True,local_full_n_integer_computations=0,local_RTL_executions=0,
        candidate_core_sha256=CORE_SHA,promotion_allowed=False,independent_review_required=True,
        scope='Actual retained-state original A-next1000 squares.11 complete canonical checkpoints, no model reset/reload/reseed between operations. Native admittedGMP validation retained; local replay only compares preserved arrays and metadata. Does not qualify point successor or board/fullPRP timing.')

if __name__=='__main__':print(json.dumps(replay(),indent=2))
