"""R9 source-exact physical snapshot; settings variants remain queue data."""
import argparse
import copy
import importlib.util
import json
import re
from pathlib import Path

from . import stream27_context_storage_combo_registerederror_bind as candidate
from .stream27_context_storage_combo_physical import ROOT, sha, need, read, encoded

PARENT = ROOT/'results/throughput-20260929/trackS-c2-storage-combo-directbound-physical-v1/physical-16000-v1'
GENERATOR = ROOT/'reference/stream27_context_storage_combo_registerederror_bind.py'
PIN = '3a507134f0a68fa393653ca1f8c7ac6e7fe7288d1f5ad0e7e36dc9657cf2a865'


def build(role, gate):
    need(sha(GENERATOR.read_bytes()) == PIN, 'frozen R9 generator')
    role = Path(role).resolve()
    # Own native owner already captured both pure emissions. Reuse their exact
    # bytes; the existing provisional guard independently regenerates both.
    small = read(role/'production-bundle.json')
    full = read(role.parent/'full-normal/production-bundle.json')
    need(small['geometry']['n']==256 and full['geometry']['n']==65536,'own captured geometries')
    for bundle in (small,full):
        need(bundle['source_sha256']['reference/stream27_context_storage_combo_registerederror_bind.py']==PIN,'captured generator pin')
        need(bundle['generated_sha256']=={n:sha(t.encode()) for n,t in bundle['files'].items()},'captured complete map')
    native = read(role/'manifest.json')
    need(read(role/'production-bundle.json')['files'] == small['files'], 'own AW8 production map')
    params = dict(native['build']['parameters'], AW=16)
    need(params == dict(full['parameters'], EPOCH_SEED0=65534, EPOCH_SEED1=42), 'actual compiled parameters')
    parent = read(PARENT/'project/manifest.json')
    need(len(full['files']) == len(small['files']) == 55, 'source55')
    need(full['geometry'] == parent['geometry'], 'warm/cold geometry unchanged, publication separately counted')
    controls = {}
    for name, pin in parent['control_sha256'].items():
        raw = (PARENT/'project'/name).read_bytes()
        need(sha(raw) == pin, 'immutable parent control '+name)
        controls[name] = raw
    qsf = '\n'.join(line for line in controls['probe.qsf'].decode().splitlines()
                    if not line.startswith('set_global_assignment -name SYSTEMVERILOG_FILE '))+'\n'
    qsf = qsf.replace(parent['top'], full['top'])
    qsf += 'set_parameter -name ERROR_AGGREGATION_REGISTERED 1\n'
    qsf += ''.join('set_global_assignment -name SYSTEMVERILOG_FILE rtl/'+name+'\n' for name in full['files'])
    controls['probe.qsf'] = qsf.encode()
    manifest = copy.deepcopy(parent)
    metadata = copy.deepcopy(full['context_registered_error'])
    metadata.pop('reversal_records')  # Source binder owns exact reversible recipe, not a second giant manifest.
    manifest.update(status='prepared_R9_registered_error_own_AW8_provisional', top=full['top'],
        core_parameters=params, source_sha256=full['generated_sha256'],
        generator_source_sha256=full['source_sha256'],
        control_sha256={name:sha(raw) for name,raw in controls.items()},
        native_normal_id=gate, native_role_manifest_sha256=sha((role/'manifest.json').read_bytes()),
        context_registered_error=metadata,
        notes=['R9 protected R7 ancestry plus signed33 bound and registered global fault aggregation.',
               'Registered-source early safety barrier; coherent full56-owner publication proposal/drain adds1edge/job,2edges/equal pair. CopyN+4. Warm I213/8459 unchanged.',
               'Own actual AW8 normal plus exact geometry proof. Full/fault/long native evidence is separate and not inherited.',
               '13ns primary and12ns seed2 Azure4/32GiB Balanced settings are experiments, not predicted closure. No optional base-ENA split.'])
    spec = read(PARENT/'structural-inventory.json')
    old_arith = next(x for x in parent['source_sha256'] if x.startswith('genefer_stream27_threefield_carry_aw'))
    old_warm = next(x for x in parent['source_sha256'] if x.startswith('genefer_stream27_warm_contexts_aw'))
    new_arith = next(x for x in full['files'] if x.startswith('genefer_stream27_threefield_carry_aw'))
    new_warm = next(x for x in full['files'] if x.startswith('genefer_stream27_warm_contexts_aw'))
    host = 'rtl/'+full['top']+'.sv'
    arith = 'rtl/'+new_arith
    warm = 'rtl/'+new_warm
    renames = {'rtl/'+parent['top']+'.sv':host, 'rtl/'+old_arith:arith, 'rtl/'+old_warm:warm}
    def remap(value):
        if isinstance(value, dict):
            out = {k:remap(v) for k,v in value.items()}
            if out.get('source') == host:
                for key in ('text',):
                    if key in out and out[key] != 'assign error=local_error || child_error || canon_error;':
                        out[key] = re.sub(r'(?<![\w.])error\b', 'safety_error', out[key])
                if 'anchors' in out:
                    out['anchors'] = [re.sub(r'(?<![\w.])error\b', 'safety_error', a) for a in out['anchors']]
            if out.get('source') == arith:
                if 'text' in out:
                    out['text']=out['text'].replace('!out_error','!error_barrier').replace('.cancel(out_error)', '.cancel(error_barrier)')
                if 'anchors' in out:
                    out['anchors']=[a.replace('!out_error','!error_barrier').replace('.cancel(out_error)', '.cancel(error_barrier)') for a in out['anchors']]
            return out
        if isinstance(value, list):
            return [remap(v) for v in value]
        return renames.get(value, value) if isinstance(value, str) else value
    spec = remap(spec)
    # New-job publication state clear is inserted between the two old anchors.
    for transfer in spec['transfers']:
        for anchor in transfer.get('exception', {}).get('contract_anchors', []):
            if anchor['source'] == host and 'jobs<=start_contexts;cycles<=0;' in anchor['text']:
                anchor['text'] = anchor['text'].replace(
                    'published<=published & ~start_contexts;\n',
                    'published<=published & ~start_contexts;\n    publish_pending<=0;publish_context<=0;publish_owner<=0;\n')
    pub = next(t for t in spec['transfers'] if t['id'] == 'copy_to_shadow_publication')
    pub['signals'] += ['publish_pending', 'publish_context', 'publish_owner', 'safety_error']
    pub['registered_stages'] = [dict(id='coherent_publication_proposal', owner='host_control', edge=0,
        kind='flop', source=host, payload=['publish_owner'], valid='publish_pending', metadata=['publish_context'],
        anchors=['publish_pending<=1;publish_context<=canonical_owner;',
                 'publish_owner<=live_owner[canonical_owner*56+:56];'], alignment='same_accepted_edge')]
    pub['exception'] = dict(kind='phase_local_control',
        reason='Nth exact commit proposes full56 owner/context. NEXT edge verifies held lease, complete counts, no extra ack and registered-source safety barrier before publication; adds1edge/job, not a one-edge whole-image copy.',
        contract_anchors=[dict(source=host,text=x) for x in (
            '.commit_owner(live_owner[canonical_owner*56+:56]),',
            candidate.PUB_PROPOSAL.strip(), candidate.PUB_DRAIN.strip())])
    fault = next(t for t in spec['transfers'] if t['id'] == 'prospective_fault_to_sticky_origin')
    fault['signals'] += ['local_fault_now','local_fault_q','field_error','error_barrier','child_error_barrier','safety_error']
    fault['registered_stages'] = [dict(id='local_fault_capture',owner='arithmetic_control',edge=0,
        kind='flop',source=arith,payload=['local_fault_q'],valid='local_fault_q',metadata=[],
        anchors=['else if(local_fault_now)local_fault_q<=1;'],alignment='same_accepted_edge'),
        dict(id='global_registered_report',owner='arithmetic_control',edge=1,kind='flop',source=arith,
        payload=['out_error'],valid='out_error',metadata=[],anchors=['if(fault_pending)out_error<=1;'],
        alignment='same_accepted_edge')]
    fault['exception'] = dict(kind='phase_local_control',
        reason='Raw prospective diagnostics remain combinational into unchanged field controller or local_fault_q at origin edge. Global out_error samples registered field_error/local_fault_q one edge later. Early barrier is OR of registered sticky sources and blocks host eligibility immediately after origin capture; no raw-pending source FF is invented. Public error may lag1edge; publication has separate coherent drain.',
        contract_anchors=[dict(source=arith,text=x) for x in (
            candidate.LOCAL_DECL.strip(), candidate.LOCAL_FF.strip(), candidate.ARITH_SUMMARY.strip(),
            'if(fault_pending)out_error<=1;')]+[
            dict(source=warm,text='assign error_barrier=local_error || child_barrier;'),
            dict(source=host,text='assign safety_error=local_error || child_error_barrier || canon_error;'),
            dict(source=host,text='assign error=local_error || child_error || canon_error;')]+[
            dict(source='rtl/'+name,text=candidate.FIELD_SET) for name in full['files']
            if name.startswith('genefer_stream27_shared_warm_aw')])
    spec['identity'].update(top=manifest['top'], parameters=params)
    spec['sources'] = {'rtl/'+name:pin for name,pin in manifest['source_sha256'].items()}
    spec['settings'] = dict(manifest['control_sha256'], **{'manifest.json':sha(encoded(manifest))})
    proof = dict(schema='fit-provisional-aw8-geometry-v1',generator=dict(path=str(GENERATOR),sha256=PIN),
                 kwargs=dict(p=16,contexts=2,enabled=1),native_n=256,fit_n=65536)
    files = {'rtl/'+name:text.encode() for name,text in full['files'].items()}
    files.update(controls)
    return manifest,files,spec,proof


def prepare(output, role, gate):
    out = Path(output).resolve()
    need(out.is_relative_to(ROOT) and not out.exists(), 'fresh R9 physical output')
    manifest,files,spec,proof = build(role,gate)
    for name,raw in files.items():
        path = out/'project'/name
        path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as stream:
            stream.write(raw)
    (out/'project/manifest.json').write_bytes(encoded(manifest))
    loader=importlib.util.spec_from_file_location('r9_structure',ROOT/'tools/prefit_structural_guard_v1.py')
    checker=importlib.util.module_from_spec(loader);loader.loader.exec_module(checker)
    for name,value in [('structural-inventory.json',spec),('provisional-geometry.json',proof)]:
        (out/name).write_bytes(encoded(value))
    for transfer in spec['transfers']:
        for anchor in transfer.get('exception',{}).get('contract_anchors',[]):
            need(files[anchor['source']].decode().count(anchor['text'])==1,
                 'exact exception anchor '+transfer['id']+': '+repr(anchor['text']))
    result=checker.source_inventory(out/'project',spec)
    need(not result['findings'],'source structural findings: '+repr(result['findings']))
    return dict(project=str(out/'project'),source_count=55,crossings=len(spec['transfers']),
        structural_sha256=sha(encoded(spec)),provisional_sha256=sha(encoded(proof)),source_findings=result['findings'])


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--native-role',type=Path,required=True)
    p.add_argument('--native-gate',required=True)
    a=p.parse_args()
    print(json.dumps(prepare(a.output,a.native_role,a.native_gate),indent=2))
