"""Captured storage2 whole normals with the private term-payload MLAB seam.

Same frozen actual benchmark/oracle/probe/calendars. Only new queue dependency
selects corrected paired unit v3; prior unsubmitted whole roles retained.
AW8 waits own paired term unit;
full waits own AW8. No inherited field placement, clock or long qualification.
"""
import argparse
import copy
from datetime import datetime,timezone
import json
from pathlib import Path
from . import stream27_context_term_mlab_bind as binder

ROOT=binder.ROOT
SELF='reference/stream27_context_term_mlab_whole_native_v2.py'
BASE=ROOT/'results/throughput-20260929/trackS-c2-storage2-native-v1'
PINS={'aw8':'2a0c70c0e14844f667ce1f39bc7a45e37572b0a46c5ee597649b7d469beb0940'}
IDS={s:'s4-p16-c2-term-mlab-'+s+'-normal-q1-v2' for s in ('aw8','full')}


def role(stage):
    binder.captured.need(stage in IDS,'MLAB_WHOLE_GEOMETRY')
    base=BASE/(stage+'-normal');manifest=json.loads((base/'manifest.json').read_text())
    if stage in PINS:binder.captured.need(binder.captured.sha((base/'manifest.json').read_bytes())==PINS[stage],'MLAB_CAPTURE_PIN')
    files={}
    for name,pin in manifest['sources'].items():
        raw=(base/'source/fpga'/name).read_bytes();binder.captured.need(binder.captured.sha(raw)==pin,'MLAB_WHOLE_SOURCE:'+name);files[name]=raw
    parent=json.loads((base/'production-bundle.json').read_text());source=binder.bind(parent,enabled=1)
    for name in parent['rtl_sources']:files.pop('rtl/'+name)
    files.update({'rtl/'+name:text.encode() for name,text in source['files'].items()})
    old,new=parent['top'],source['top']
    if stage=='full':
        observer='rtl/'+manifest['build']['top']+'.sv'
        files[observer]=binder.captured.binder.parent.re_identifier(files[observer].decode(),old,new).encode()
        sv=['rtl/'+name for name in source['rtl_sources']]+[observer]
    else:
        header='rtl/tb/s4_host_contexts_config_v1.h';text=files[header].decode()
        binder.captured.need(text.count(old)==2,'MLAB_WHOLE_AW8_DUT_IDENTIFIER')
        files[header]=text.replace(old,new).encode();manifest['build']['top']=new
        sv=['rtl/'+name for name in source['rtl_sources']]
    manifest['build']['sv_sources']=sv
    for name in (binder.SELF,SELF):files['lineage/'+name]=(ROOT/name).read_bytes()
    manifest['sources']={name:binder.captured.sha(data) for name,data in files.items()}
    manifest.update(source_root='UNBOUND',output_parent='UNBOUND',test_role='normal')
    manifest['storage2'].update(production_top=new,production_generated_sha256=source['generated_sha256'])
    manifest['term_mlab']=dict(source['term_mlab'],source_parent_manifest_sha256=binder.captured.sha((base/'manifest.json').read_bytes()),
        source_parent_directory=str(base),production_top=new,production_generated_sha256=source['generated_sha256'],
        normal_steps_preserved=True,native_qualified=False,promotion_allowed=False)
    snapshot={name:pin for name,pin in manifest['sources'].items() if name.endswith('.sv')}
    manifest['rtl_readiness']=dict(schema='gfn16-candidate-rtl-ready-v1',candidate_id=IDS[stage].removesuffix('-q1-v1'),
        source_snapshot=snapshot,candidate_source_sha256=binder.captured.sha(json.dumps(snapshot,sort_keys=True,separators=(',',':')).encode()),
        rtl_ready_at_utc=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'))
    return manifest,files,source


def prepare(output,stage):
    from fpga.tools import candidate_ladder,native_class_package_v2 as package
    out=Path(output).resolve();binder.captured.need(out.is_relative_to(ROOT) and not out.exists(),'MLAB_WHOLE_FRESH')
    binder.captured.need(not any((ROOT/x).exists() for x in ('queue/PAUSE','docs/briefs/PAUSE')),'MLAB_WHOLE_PAUSE')
    manifest,files,bundle=role(stage);source=out/'source/fpga';source.mkdir(parents=True)
    for name,data in files.items():
        p=source/name;p.parent.mkdir(parents=True,exist_ok=True)
        with p.open('xb') as stream:stream.write(data)
    manifest['source_root']=str(source);binder.captured.dump(out/'manifest.json',manifest)
    binder.captured.dump(out/'production-bundle.json',bundle)
    binder.captured.dump(out/'host-hours.json',candidate_ladder.budget_from_hourly())
    template=json.loads((BASE/(stage+'-normal')/'global-ticket.json').read_text());variants=[]
    for pair,old in zip(('01','23'),template['packages']):
        worker='s4-p16-c2-term-mlab-'+stage+'-'+pair+'-v2';packet=out/('packet-'+pair)
        r=package.prepare(out/'manifest.json',source,old['profile'],worker,'run',packet,out/'host-hours.json')
        t=json.loads((packet/'ticket.json').read_text());v=copy.deepcopy(old)
        v.update(archive=str(packet/'package.tar.gz'),sha256=r['archive_sha256'],ticket_sha256=r['ticket_sha256'],
            manifest_sha256=binder.captured.sha((packet/'manifest.json').read_bytes()),worker_id=worker,native_root=t['native_root'])
        variants.append(v)
    logical={k:copy.deepcopy(template[k]) for k in ('schema','owner','priority','kind','needs','tool_identity','resources',
        'minimum_ram_gib','minimum_ram_rationale','est_minutes','promotion_bound')}
    logical.update(id=IDS[stage],created=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),test_role='normal',packages=variants,
        rtl_readiness=manifest['rtl_readiness'],after=['s4-p16-c2-term-mlab-unit-normal-q1-v3'] if stage=='aw8' else [IDS['aw8']],on='PASS_expected_contracts')
    binder.captured.dump(out/'global-ticket.json',logical)
    return dict(id=IDS[stage],ticket=str(out/'global-ticket.json'),status='prepared_not_native')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--stage',choices=('aw8','full'),required=True);a=p.parse_args()
    print(json.dumps(prepare(a.output,a.stage),indent=2))
