"""Paired unit successor: POST pending is not a sampled fault.

V2 normal paired old/new exactly but rejected the ordinary POST-edge calendar
pending diagnostic while its PRE-edge inputs still named the sampled row/seed.
Retain PRE pending checks and both PRE/POST lockstep; reject POST registered
out_error only. No production RTL, latency, reference or fault masks changed.
"""
import argparse
import copy
from datetime import datetime,timezone
import json
from pathlib import Path
from . import stream27_context_term_mlab_native as parent

ROOT=parent.ROOT
SELF='reference/stream27_context_term_mlab_native_v3.py'
NORMAL_ID='s4-p16-c2-term-mlab-unit-normal-q1-v3'


def role(mode='normal'):
    manifest,files=parent.role(mode)
    cpp=files[parent.CPP].decode()
    cpp=parent.binding.captured.binder.parent.once(cpp,
        'need(!(d.old_status&24u),"TERM_MLAB_NORMAL_POST_FAULT");',
        'need(!(d.old_status&8u),"TERM_MLAB_NORMAL_POST_REGISTERED_FAULT");')
    files[parent.CPP]=cpp.encode()
    sv=manifest['build']['sv_sources']
    old='rtl/genefer_montgomery_mul27_sparse_pipe.sv'
    new='rtl/genefer_stream27_montgomery_factored_v1.sv'
    parent.binding.captured.need(old in sv and new in files,'MLAB_UNIT_FACTORED_IMPORT')
    manifest['build']['sv_sources']=[new if name==old else name for name in sv]
    files['lineage/'+SELF]=(ROOT/SELF).read_bytes()
    manifest['sources']={name:parent.binding.captured.sha(data) for name,data in files.items()}
    manifest['term_mlab_unit']['preserved_unstarted_v1']=True
    manifest['term_mlab_unit']['actual_factored_multiply_closure']=True
    manifest['term_mlab_unit']['preserved_failed_v2']='s4-p16-c2-term-mlab-unit-normal-q1-v2'
    manifest['term_mlab_unit']['POST_pending_not_sampled']=True
    return manifest,files


def prepare(output,mode='normal'):
    from fpga.tools import candidate_ladder,native_class_package_v2 as package
    out=Path(output).resolve();parent.binding.captured.need(out.is_relative_to(ROOT) and not out.exists(),'MLAB_UNIT_V2_FRESH')
    parent.binding.captured.need(not any((ROOT/x).exists() for x in ('queue/PAUSE','docs/briefs/PAUSE')),'MLAB_UNIT_V2_PAUSE')
    manifest,files=role(mode);source=out/'source/fpga';source.mkdir(parents=True)
    for name,data in files.items():
        p=source/name;p.parent.mkdir(parents=True,exist_ok=True)
        with p.open('xb') as stream:stream.write(data)
    manifest['source_root']=str(source);parent.binding.captured.dump(out/'manifest.json',manifest)
    parent.binding.captured.dump(out/'host-hours.json',candidate_ladder.budget_from_hourly())
    from . import stream27_context_storage_banks_fault as captured_fault
    template=json.loads((captured_fault.NORMAL/'global-ticket.json').read_text());variants=[]
    identifier='s4-p16-c2-term-mlab-unit-'+mode+'-q1-v3'
    for pair,old in zip(('01','23'),template['packages']):
        worker='s4-p16-c2-term-mlab-'+mode+'-'+pair+'-v3';packet=out/('packet-'+pair)
        r=package.prepare(out/'manifest.json',source,old['profile'],worker,'run',packet,out/'host-hours.json')
        t=json.loads((packet/'ticket.json').read_text());v=copy.deepcopy(old)
        v.update(archive=str(packet/'package.tar.gz'),sha256=r['archive_sha256'],ticket_sha256=r['ticket_sha256'],
            manifest_sha256=parent.binding.captured.sha((packet/'manifest.json').read_bytes()),worker_id=worker,native_root=t['native_root'])
        variants.append(v)
    logical={k:copy.deepcopy(template[k]) for k in ('schema','owner','priority','kind','needs','tool_identity','resources',
        'minimum_ram_gib','minimum_ram_rationale','est_minutes','promotion_bound')}
    logical.update(id=identifier,created=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),test_role=manifest['test_role'],packages=variants)
    if mode=='faults':logical.update(after=[NORMAL_ID],on='PASS_expected_contracts')
    parent.binding.captured.dump(out/'global-ticket.json',logical)
    return dict(id=identifier,ticket=str(out/'global-ticket.json'),status='prepared_not_native')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--mode',choices=('normal','faults'),default='normal');a=p.parse_args()
    print(json.dumps(prepare(a.output,a.mode),indent=2))
