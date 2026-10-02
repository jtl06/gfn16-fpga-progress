"""Source/config-only A-a whole chain; reuse frozen roles and shared packager.

Hardware block admission probe -> unchanged AW5/AW8 command corpus -> retained
AW16 representative corpus. No Python disguised as HDL, dispatch or fit.
"""
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from fpga.reference import radix22_aa_whole_source_v1 as s

ROOT=s.ROOT
SELF='reference/radix22_aa_whole_prepare_v1.py'
TEST='tests/test_radix22_aa_whole_prepare_v1.py'
PARENTS={5:('artifacts/anext-point-whole-aw5-role-v1','11340a6819c863139bff8b50564d44a0b5d1df3b2eaa8b154f969a0e42d7aeeb'),
         8:('artifacts/anext-point-whole-aw8-role-v1','5e688cbd1de473b445a216642a6b63d79b3ca676b6821dab317802ef8e29a7ef'),
         16:('artifacts/anext-point-representative-aw16-role-v1','98ae80e62e95f70d08acf1d03af9bb9fdf84003852d900afaecce769d358c84a')}


def sha(raw):return hashlib.sha256(raw).hexdigest()


def role(kind):
    s.verify();generated=s.expected()
    if kind=='block-aw5-f0':
        m,files=s.probe.role(5,0);m=copy.deepcopy(m)
        old=s.probe.source.TARGET
        m['build']['top']=s.PROBE_TOP
        m['build']['sv_sources']=[s.BLOCK if x==old else s.PROBE_SV if x==s.probe.SV else x for x in m['build']['sv_sources']]+[s.field.RAM]
        m['build']['cpp_source']=s.PROBE_CPP
        m['steps']=[dict(name='full32-block-admission-normal',argv=['{exe}'],expected_returncode=0,
            expected_stdout='AA_POINTDATA27_BLOCK_PASS aw=5 field=104857601 blocks=16 offsets=2 e0_to_e1=1 forward=direct-small highword_cases=48\n',expected_stderr='')]
    else:
        aw={'whole-aw5':5,'whole-aw8':8,'representative-aw16':16}[kind]
        name,pin=PARENTS[aw];parent=ROOT/name
        s.need(s.sha(parent/'manifest.json')==pin,'exact frozen whole-role manifest')
        m=json.loads((parent/'manifest.json').read_text());files={}
        for name,pin in m['sources'].items():
            raw=(parent/'source/fpga'/name).read_bytes();s.need(sha(raw)==pin,'frozen whole source '+name);files[name]=raw
        m['build']['sv_sources']=[s.rename(x) for x in m['build']['sv_sources']]+[s.field.RAM]
        m['build']['top']=s.CORE
        m['build']['cpp_source']=s.FULL_CPP if aw==16 else s.CPP
        for step in m['steps']:
            step['name']='aa-pointdata27-'+kind
            step['validator']['source']=s.FULL_OUTPUT if aw==16 else s.OUTPUT
        m['aa_parent_manifest_sha256']=PARENTS[aw][1]
    for name,text in generated.items():files[name]=text.encode()
    for name in (s.SELF,s.TEST,SELF,TEST,s.field.RAM):files[name]=(ROOT/name).read_bytes()
    m['sources']={name:sha(raw) for name,raw in files.items()}
    m['aa_whole']=dict(candidate='A-next-pointdata27-v1',range_contract=s.range_contract(),
        delta='ONE RAM leaf27 plus unique module/bench/validator names; control/math/ports/full32 hardware admission unchanged',
        expected_point_parent_cycle_delta=0,field_independent_receipt_sha256='2054bbf6f521fb24f692bd2e10f7dd714e46446122448903d830abefc714151e',
        field_scope_NOT_whole_qualification=True,whole_native_executed=False,area_or_clock_promotion=False,
        no_F3_upper_cancel_merge=True,ordinary_whole_oracle_inputs_bytes_unchanged=True)
    m['scope']='ONE separately named frozen point+RAM27 whole area experiment; initialized canonical payloads via preserved full32 block gate, no arithmetic/profile/ABI change or promotion.'
    s.need(all(x in files for x in [*m['build']['sv_sources'],m['build']['cpp_source']]),'compiled closure')
    return m,files


def save(path,value):
    with Path(path).open('x') as stream:json.dump(value,stream,indent=2);stream.write('\n')


def prepare(output):
    from fpga.tools import native_class_package_v2 as package
    from fpga.cloud import host_hours_admit_v1 as meter
    s.need(s.sha(package.__file__)=='03b6a81aa7d465487da97f854a79e9e43a19c9c637db6178587cfac02476f604'
           and s.sha(meter.__file__)=='6fd1904025f4d76557497dba2eac2a5514b419a799c8616b177bc696f051379a','shared source/package/accounting pins')
    output=Path(output).resolve()
    s.need(not output.exists() and output.parent.is_dir() and not any((ROOT/x).exists() for x in ('docs/briefs/PAUSE','queue/PAUSE')),'fresh one-candidate output/no PAUSE')
    s.verify();output.mkdir();hours=meter.admit('gcp-c4d',3715);save(output/'host-hours.json',hours)
    budget=dict(provider='gcp',observed_at=hours['observed_at_utc'],total_allowance_usd=100,planning_usd_per_hour=hours['hourly_rate_usd'],
                remaining_after_reserves_usd=hours['remaining_total_after_storage_usd'],actual_billing=False,source_receipt_sha256=sha((output/'host-hours.json').read_bytes()))
    save(output/'budget.json',budget);jobs=[];prior=None
    for kind in ('block-aw5-f0','whole-aw5','whole-aw8','representative-aw16'):
        m,files=role(kind);case=output/kind;src=case/'source/fpga';src.mkdir(parents=True)
        for name,raw in files.items():
            path=src/name;path.parent.mkdir(parents=True,exist_ok=True)
            with path.open('xb') as stream:stream.write(raw)
        save(case/'manifest.json',m);variants=[]
        for pair in ('01','23'):
            profile='gcp-c4d-static'+pair+'-v1';worker='aa-pointdata27-'+kind+'-'+pair+'-v1';packet=case/('packet-'+pair)
            r=package.prepare(case/'manifest.json',src,profile,worker,'run',packet,output/'budget.json')
            variants.append(dict(archive=str(packet/'package.tar.gz'),sha256=r['archive_sha256'],ticket_sha256=r['ticket_sha256'],
                manifest_sha256=sha((packet/'manifest.json').read_bytes()),profile=profile,worker_id=worker,native_root=r['native_root'],
                runner='tools/native_class_package_v2.py',runner_sha256=s.sha(package.__file__),stager=str(ROOT/'tools/native_package_v4.py'),
                stager_sha256=s.sha(ROOT/'tools/native_package_v4.py'),
                stager_dependencies=[dict(path=str(ROOT/'tools'/name),sha256=s.sha(ROOT/'tools'/name)) for name in ('native_package_v3.py','native_package_v2.py')],max_seconds=3700))
        qid='aa-pointdata27-'+kind+'-q1-v1'
        q=dict(schema='gfn16-global-ticket-v1',id=qid,candidate_id='aa-pointdata27-whole-v1',owner='radix22-sol',priority='P2',kind='sim',needs='verilator',
            created=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),tool_identity='gcp-c4d-verilator5032-gcc15-python314-v1',
            resources=dict(cores=2,threads=1,ram_gib=8,scratch_gib=4),est_minutes=10,promotion_bound=False,packages=variants,
            source_gate=dict(range_contract_sha256=sha(json.dumps(s.range_contract(),sort_keys=True).encode()),only_RAM27_and_namespace_delta=True,
                             preserved_full32_block_bad_word_hardware=True,no_F3_upper_cancel_merge=True,source_exploration_only=True))
        if prior:q.update(after=[prior],on='PASS_expected_contracts')
        save(case/'global-ticket.json',q);jobs.append(dict(id=qid,path=str(case/'global-ticket.json'),producer_sha256=sha((case/'global-ticket.json').read_bytes()),packages=variants));prior=qid
    result=dict(schema='aa-pointdata27-whole-chain-source-v1',status='source_prepared_ONE_whole_area_candidate_four_roles_NOT_dispatched',
                source_pins=s.verify(),range_contract=s.range_contract(),jobs=jobs,normal_corpus_bytes_unchanged=True,
                expected_point_parent_cycle_delta=0,native_executed=False,vendor_executed=False,whole_fit_prepared=False,
                unmeasured_whole_area_or_clock_saving=False,full_N_numeric_or_HDL_vendor_on_Mac=False,promotion_allowed=False)
    save(output/'preparation.json',result);return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(prepare(args.output),indent=2))
