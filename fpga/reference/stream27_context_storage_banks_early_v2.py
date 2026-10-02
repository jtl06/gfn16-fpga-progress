"""Early-cache diagnostic successor: keep original F1/F2 shared term leaf.

V1 actual lint failure is preserved. Only F0 uses the added diagnostic clone;
normal production53 and arithmetic are unchanged. Observe the actual premature
token PRE, and require registered global rejection before publication.
"""
import argparse
import copy
from datetime import datetime, timezone
import json
from pathlib import Path
from . import stream27_context_storage_banks_fault as parent

ROOT=parent.ROOT
SELF='reference/stream27_context_storage_banks_early_v2.py'
ID='s4-p16-c2-storage2-aw8-early-cache-q1-v2'


def role():
    manifest, files=parent.role('early-cache')
    normal, original=parent.role('oracle')
    term='rtl/genefer_stream27_term_context_param_v1_contexts_v1_storage2_v1.sv'
    files[term]=original[term]
    manifest['build']['sv_sources'].append(term)
    cpp=files[parent.CPP].decode()
    cpp=parent.native.binder.parent.once(cpp,'static void storage_early_cache(DUT& d){\n    storage_job(d);bool failed=false;',
        'static void storage_early_cache(DUT& d){\n    storage_job(d);bool failed=false,observed=false;')
    cpp=parent.native.binder.parent.once(cpp,
        'clear(d);edge(d);need(!d.done&&!d.canonical_ready&&!d.read_valid,"C2_STORAGE_EARLY_CACHE_NO_PUBLICATION");',
        '''clear(d);d.clk=0;d.eval();
        if(STORAGE(seed_running)&&STORAGE(term_cache_ready)&&!observed){
            need(!STORAGE(term_producer__DOT__product_slot),"C2_STORAGE_EARLY_CACHE_ACTUAL_PREMATURE_TOKEN");
            observed=true;
        }
        d.clk=1;d.eval();need(!d.done&&!d.canonical_ready&&!d.read_valid,"C2_STORAGE_EARLY_CACHE_NO_PUBLICATION");''')
    cpp=parent.native.binder.parent.once(cpp,'need(failed,"C2_STORAGE_EARLY_CACHE_DIAGNOSTIC_NOT_DETECTED");',
        'need(observed&&failed,"C2_STORAGE_EARLY_CACHE_DIAGNOSTIC_NOT_DETECTED");')
    cpp=cpp.replace('duplicate_cache_rejected=1','premature_cache_rejected=1')
    files[parent.CPP]=cpp.encode()
    files['lineage/'+SELF]=(ROOT/SELF).read_bytes()
    manifest['sources']={name:parent.sha(data) for name,data in files.items()}
    manifest['steps'][0]['expected_stdout']=manifest['steps'][0]['expected_stdout'].replace(
        'duplicate_cache_rejected=1','premature_cache_rejected=1')
    manifest['storage2_fault'].update(preserved_failed_v1_id='s4-p16-c2-storage2-aw8-early-cache-q1-v1',
        original_shared_term_retained_for_f1_f2=True, actual_PRE_token_observed=True,
        diagnostic_scope='Premature full-owner cache token seen before E4 product, registered global rejection; not a specific duplicate-error-source claim')
    parent.native.need(len(manifest['build']['sv_sources'])==54 and
        all(files[name]==original[name] for name in normal['build']['sv_sources']
            if name not in manifest['storage2_fault']['diagnostic_rtl_delta']), 'EARLY_V2_COMPLETE_SHARED_CLOSURE')
    return manifest,files


def prepare(output):
    from fpga.tools import candidate_ladder,native_class_package_v2 as package
    out=Path(output).resolve()
    parent.native.need(out.is_relative_to(ROOT) and not out.exists(),'EARLY_V2_FRESH')
    parent.native.need(not any((ROOT/x).exists() for x in ('queue/PAUSE','docs/briefs/PAUSE')),'EARLY_V2_PAUSE')
    manifest,files=role();source=out/'source/fpga';source.mkdir(parents=True)
    for name,data in files.items():
        p=source/name;p.parent.mkdir(parents=True,exist_ok=True)
        with p.open('xb') as stream:stream.write(data)
    manifest['source_root']=str(source);parent.native.dump(out/'manifest.json',manifest)
    parent.native.dump(out/'host-hours.json',candidate_ladder.budget_from_hourly())
    template=json.loads((parent.NORMAL/'global-ticket.json').read_text());variants=[]
    for pair,old in zip(('01','23'),template['packages']):
        worker='s4-p16-c2-storage2-early-cache-'+pair+'-v2';packet=out/('packet-'+pair)
        r=package.prepare(out/'manifest.json',source,old['profile'],worker,'run',packet,out/'host-hours.json')
        t=json.loads((packet/'ticket.json').read_text());v=copy.deepcopy(old)
        v.update(archive=str(packet/'package.tar.gz'),sha256=r['archive_sha256'],ticket_sha256=r['ticket_sha256'],
            manifest_sha256=parent.sha((packet/'manifest.json').read_bytes()),worker_id=worker,native_root=t['native_root'])
        variants.append(v)
    logical={k:copy.deepcopy(template[k]) for k in ('schema','owner','priority','kind','needs','tool_identity','resources',
        'minimum_ram_gib','minimum_ram_rationale','est_minutes','promotion_bound')}
    logical.update(id=ID,created=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),test_role='deliberate_fault',
        packages=variants,after=[parent.native.IDS['aw8']],on='PASS_expected_contracts')
    parent.native.dump(out/'global-ticket.json',logical)
    return dict(id=ID,ticket=str(out/'global-ticket.json'),status='source_prepared_not_native')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    print(json.dumps(prepare(a.output),indent=2))
