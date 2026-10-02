"""Private explicit post-write forwarding hypothesis; paired normal/fault only.

No read latency, collision waiver, authority or arithmetic changes. Actual SYN
must establish inference; source correctness is not mapping evidence.
"""
import argparse
import copy
from datetime import datetime,timezone
import json
from pathlib import Path
from . import stream27_context_term_mlab_native_v4 as parent

binding=parent.binding
ROOT=parent.ROOT
SELF='reference/stream27_context_term_mlab_forward_native.py'
LEAF='rtl/kernel/genefer_stream27_term_payload_mlab_forward_v1.sv'
OLD='genefer_stream27_term_payload_mlab_v1'
NEW='genefer_stream27_term_payload_mlab_forward_v1'
NORMAL_ID='s4-p16-c2-term-mlab-forward-unit-normal-q1-v1'


def role(mode='normal'):
    manifest,files=parent.role(mode)
    old='rtl/'+OLD+'.sv';new='rtl/'+NEW+'.sv'
    binding.captured.need(old in files and old in manifest['build']['sv_sources'],'MLAB_FORWARD_ACTUAL_LEAF')
    files.pop(old);files[new]=(ROOT/LEAF).read_bytes()
    for name,raw in list(files.items()):
        if name.endswith('.sv') and name!=new:
            files[name]=binding.captured.binder.parent.re_identifier(raw.decode(),OLD,NEW).encode()
    manifest['build']['sv_sources']=[new if name==old else name for name in manifest['build']['sv_sources']]
    files['lineage/'+SELF]=(ROOT/SELF).read_bytes()
    manifest['sources']={name:binding.captured.sha(raw) for name,raw in files.items()}
    manifest['term_mlab_unit']['candidate_sha256']=binding.captured.sha(files['rtl/'+binding.NEW+'.sv'])
    manifest['term_mlab_unit']['parent_ram_sha256']=manifest['term_mlab_unit']['ram_sha256']
    manifest['term_mlab_unit']['ram_sha256']=binding.captured.sha(files[new])
    manifest['term_mlab_forward']=dict(no_rw_check=False,read_latency=0,
        pre_old_post_new_defined=True,explicit_reset_write_guard_retained=True,
        leaf_sha256=binding.captured.sha(files[new]),
        actual_mapping_established=False,promotion_allowed=False)
    return manifest,files


def prepare(output,mode='normal'):
    from fpga.tools import candidate_ladder,native_class_package_v2 as package
    out=Path(output).resolve();binding.captured.need(out.is_relative_to(ROOT) and not out.exists(),'MLAB_V4_FRESH')
    binding.captured.need(not any((ROOT/x).exists() for x in ('queue/PAUSE','docs/briefs/PAUSE')),'MLAB_V4_PAUSE')
    manifest,files=role(mode);source=out/'source/fpga';source.mkdir(parents=True)
    for name,data in files.items():
        p=source/name;p.parent.mkdir(parents=True,exist_ok=True)
        with p.open('xb') as stream:stream.write(data)
    manifest['source_root']=str(source);binding.captured.dump(out/'manifest.json',manifest)
    binding.captured.dump(out/'host-hours.json',candidate_ladder.budget_from_hourly())
    from . import stream27_context_storage_banks_fault as captured_fault
    template=json.loads((captured_fault.NORMAL/'global-ticket.json').read_text());variants=[]
    identifier='s4-p16-c2-term-mlab-forward-unit-'+mode+'-q1-v1'
    for pair,old in zip(('01','23'),template['packages']):
        worker='s4-p16-c2-term-mlab-forward-'+mode+'-'+pair+'-v1';packet=out/('packet-'+pair)
        r=package.prepare(out/'manifest.json',source,old['profile'],worker,'run',packet,out/'host-hours.json')
        t=json.loads((packet/'ticket.json').read_text());v=copy.deepcopy(old)
        v.update(archive=str(packet/'package.tar.gz'),sha256=r['archive_sha256'],ticket_sha256=r['ticket_sha256'],
            manifest_sha256=binding.captured.sha((packet/'manifest.json').read_bytes()),worker_id=worker,native_root=t['native_root'])
        variants.append(v)
    logical={k:copy.deepcopy(template[k]) for k in ('schema','owner','priority','kind','needs','tool_identity','resources',
        'minimum_ram_gib','minimum_ram_rationale','est_minutes','promotion_bound')}
    logical.update(id=identifier,created=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),test_role=manifest['test_role'],packages=variants)
    if mode=='faults':logical.update(after=[NORMAL_ID],on='PASS_expected_contracts')
    binding.captured.dump(out/'global-ticket.json',logical)
    return dict(id=identifier,ticket=str(out/'global-ticket.json'),status='prepared_not_native')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--mode',choices=('normal','faults'),default='normal');a=p.parse_args()
    print(json.dumps(prepare(a.output,a.mode),indent=2))
