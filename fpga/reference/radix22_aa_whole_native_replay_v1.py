"""Owner read-only whole RAM27 evidence replay; no ELF/HDL/vendor execution.

Uses the existing generic gate, then checks the preserved package, generated
files, ELF bytes, static caps and pure scalar/output contracts. Independent
promotion replay remains separate. No native worker polling or dispatch.
"""
import gzip
import hashlib
import json
from pathlib import Path
import tarfile
from fpga.tools import native_gate_receipt_v1 as g
from fpga.reference import radix22_aa_whole_source_v1 as s
from fpga.reference import radix22_aa_whole_output_v1 as small
from fpga.reference import radix22_aa_whole_representative_output_v1 as representative

ROOT=s.ROOT
IDS=('aa-pointdata27-block-aw5-f0-q1-v1','aa-pointdata27-whole-aw5-q1-v1',
     'aa-pointdata27-whole-aw8-q1-v1','aa-pointdata27-representative-aw16-q1-v1')


def unpack(path):
    result={}
    with tarfile.open(path,'r:gz') as archive:
        for member in archive:
            g.relative(member.name)
            s.need(member.isfile() and not member.issparse() and member.name not in result,'regular unique archive member')
            with archive.extractfile(member) as stream:result[member.name]=stream.read()
    return result


def sha(raw):return hashlib.sha256(raw).hexdigest()


def limits(report,done):
    cap=report['limits'];props=done['result']['properties']
    s.need(cap['memory_max_bytes']==8<<30 and cap['swap_max_bytes']==0 and cap['cpu_max']==['200000','100000']
           and len(set(map(tuple,cap['physical_cores'])))==2 and len(cap['affinity'])==2
           and report['compile_workers']==2 and report['model_threads']==1,'actual distinct2cores/8GiB/noSwap/model1/j2')
    s.need(props['MainPID']=='0' and props['ControlGroup']=='' and props['Result']=='success' and props['SubState']=='exited'
           and props['ExecMainStatus']=='0' and props['InvocationID']==done['dispatch']['invocation']
           and props['RuntimeMaxUSec']=='1h 1min 40s' and props['TimeoutStopUSec']=='15s'
           and props['MemoryMax']==str(8<<30) and props['MemorySwapMax']=='0' and props['CPUQuotaPerSecUSec']=='2s',
           'same invocation finite terminal/caps, not observation timeout')


def replay(id):
    s.need(id in IDS,'exact experiment role');done_path=ROOT/'queue/done'/(id+'.json')
    done=json.loads(done_path.read_text());p=done['package'];root=Path(done['result']['evidence']);native=root/'output/native'
    report=json.loads((native/'report.json').read_text());manifest=json.loads((native/'approved-manifest.json').read_text())
    s.need(g.sha(Path(p['archive']))==p['sha256'],'selected package hash')
    package=unpack(p['archive'])
    for name,pin in (('manifest.json',p['manifest_sha256']),('ticket.json',p['ticket_sha256'])):
        s.need(sha(package[name])==pin,'selected manifest/ticket identity')
    s.need(package['manifest.json']==(native/'approved-manifest.json').read_bytes()
           and package['ticket.json']==(root/'ticket.json').read_bytes(),'selected approved bytes')
    ticket=json.loads(package['ticket.json'])
    contract=g.make_contract(done['candidate_id'],(native/'approved-manifest.json').resolve())
    receipt=g.validate_result(contract,(native/'report.json').resolve(),id=id)
    s.need(receipt['report_sha256']==done['result']['queue_report']['report_sha256']
           and receipt['contract_sha256']==done['dependency_gate']['contract_sha256']
           and receipt['manifest_sha256']==ticket['manifest_sha256'],'actual source-bound gate/report identity')
    sources=unpack(native/'sources.tar.gz')
    for name,pin in manifest['sources'].items():
        s.need(sha(sources[name])==pin and package['capture/source/fpga/'+name]==sources[name],'package/source member '+name)
    for name,pin in ticket['tools'].items():
        key=name if name.startswith(('cloud/','results/','docs/','queue/')) else 'tools/'+name
        s.need(manifest['sources'][key]==pin,'exact selected shared helper/profile '+key)
    generated=unpack(native/'generated-sources.tar.gz')
    s.need({name:sha(raw) for name,raw in generated.items()}==report['generated_source_sha256'],'generated source map')
    model=gzip.decompress((native/'model.gz').read_bytes())
    s.need(model[:4]==b'\x7fELF' and sha(model)==report['executable_sha256'],'ELF bytes (not executed)')
    dispatcher=json.loads((root/'dispatcher-inventory.json').read_text())['files']
    for name,pin in dispatcher.items():s.need(g.sha(root/name)==pin,'dispatcher evidence pin '+name)
    limits(report,done)
    if done['selected_variant'].startswith('gcp-'):
        profile=json.loads(sources['cloud/gcp-native-thread-profiles-v1.json'])
        expected_hashes=set(profile['hashes'].values())
    else:
        profile=json.loads(sources['cloud/azure-burst16-memory8-profiles-v1.json'])
        observation=json.loads(sources[profile['toolchain_observation_path']])
        s.need(sha(sources[profile['toolchain_observation_path']])==profile['toolchain_observation_sha256'],'actual Azure tool observation')
        expected={observation['paths'][name]:pin for name,pin in observation['hashes'].items() if name!='compiler_alias'}
        s.need(report['tool_sha256']==expected,'actual tool binary paths/hashes')
        expected_hashes=set(expected.values())
    s.need(set(report['tool_sha256'].values())==expected_hashes,'actual binary hashes bound to selected admitted profile')
    for key in ('lint_admission','build_admission'):
        v=report[key];s.need(v['returncode']==0 and not v['fatal_class_counts'] and not v['unknown_class_counts'] and not v['error_streams'],'style-only class gate')
    s.need(len(manifest['steps'])==1,'one exact whole role outcome')
    step=manifest['steps'][0];row=report['steps'][-1]
    stdout=(native/row['log']).read_text();stderr=(native/row['stderr_log']).read_text()
    if 'validator' in step:
        spec=step['validator'];s.need(sources[spec['source']]==(ROOT/spec['source']).read_bytes(),'pure validator source identity')
        output=representative if id==IDS[-1] else small
        assets={name:sources[path].decode() for name,path in spec['assets'].items()}
        value=output.validate(stdout,stderr,row['returncode'],spec['config'],assets)
        s.need(value==report['validations'][step['name']],'same source-bound scalar/footer replay')
        keys=('cold','load','latency','total','prefill','root','ntt','post')
        summary=dict(footer=value['footer'],distinct_phases=[dict(zip(keys,row)) for row in sorted({tuple(row[k] for k in keys) for row in value['metrics']})])
    else:summary=dict(exact_stdout=stdout,highword_cases=48,actual_returncode=row['returncode'])
    return dict(id=id,done_sha256=g.sha(done_path),selected_profile=done['selected_variant'],
        invocation=done['dispatch']['invocation'],evidence=str(root),package_sha256=p['sha256'],manifest_sha256=receipt['manifest_sha256'],
        report_sha256=receipt['report_sha256'],gate_sha256=done['dependency_gate']['sha256'],artifacts=len(report['artifacts']),
        sources=len(manifest['sources']),generated=len(generated),executable_sha256=report['executable_sha256'],
        ordered_commands=len(report['steps']),dispatcher_files=len(dispatcher),package_members=len(package),native_seconds=report['seconds'],
        peak_memory_bytes=int(done['result']['properties']['MemoryPeak']),lint_styles=report['lint_admission']['class_counts'],
        build_styles=report['build_admission']['class_counts'],summary=summary)


def consume(require_all=False):
    s.need(g.sha(g.__file__)=='131d4e6b9cafd424935094c3ec50ef81d7c2e8024efae6a5d37ce20d0c5a29d3','shared gate source pin')
    finished=[id for id in IDS if (ROOT/'queue/done'/(id+'.json')).exists()]
    s.need(not require_all or finished==list(IDS),'all actual whole gates required')
    return dict(status='PASS_same_owner_read_only_actual_terminal_gates',source_pins=s.verify(),range_contract=s.range_contract(),
        roles=[replay(id) for id in finished],pending=[id for id in IDS if id not in finished],
        full_N_numeric_or_HDL_vendor_rerun_on_Mac=False,remote_calls=0,independent_promotion_review=False,
        earlier_inspection_failures=['capture.files is integer count, not mapping','ticket.tools binds helper/profile hashes, not binary path descriptors'],
        failures_scope='Owner read-only introspection schema errors before receipt creation; not worker failures or evidence edits.')


if __name__=='__main__':
    import argparse
    q=argparse.ArgumentParser();q.add_argument('--require-all',action='store_true');a=q.parse_args()
    print(json.dumps(consume(a.require_all),indent=2))
