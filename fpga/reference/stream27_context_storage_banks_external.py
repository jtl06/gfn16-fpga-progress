"""Ports-only storage2 descriptor faults; feed ingress must actually be open.

The earlier unsubmitted external mode in fault.py omitted feed_mode, so its
descriptor mutations would not reach ingress. That draft remains unexecuted;
this explicit successor uses exact production RTL and asserts ready/denied PRE.
"""
import argparse
import copy
from datetime import datetime, timezone
import json
from pathlib import Path
from . import stream27_context_storage_banks_fault as parent

ROOT = parent.ROOT
SELF = 'reference/stream27_context_storage_banks_external.py'
CPP = 'rtl/tb/stream27_context_storage2_external.cpp'
ID = 's4-p16-c2-storage2-aw8-external-q1-v2'


def role():
    manifest, files = parent.role('oracle')
    footer = json.loads((parent.NORMAL / 'manifest.json').read_text())['steps'][0]['expected_stdout']
    files[CPP] = (ROOT / CPP).read_bytes()
    files['lineage/' + SELF] = (ROOT / SELF).read_bytes()
    manifest['build']['cpp_source'] = CPP
    manifest['sources'] = {name: parent.sha(data) for name, data in files.items()}
    manifest['steps'] = [dict(name='storage2-external',argv=['{exe}'],expected_returncode=0,
        expected_stdout=footer+'C2_STORAGE_EXTERNAL_PASS bad_base=1 stale_generation=1 full32_index=1 global_abort=3 recovered_reads=1024 peer_recovery=0\n',expected_stderr='')]
    manifest['storage2_fault'].update(mode='external-feed-v2', actual_feed_ingress=True,
        preserved_unsubmitted_v1_draft=True, production_rtl_unchanged=True)
    return manifest, files


def prepare(output):
    from fpga.tools import candidate_ladder, native_class_package_v2 as package
    out = Path(output).resolve()
    parent.native.need(out.is_relative_to(ROOT) and not out.exists(), 'EXTERNAL_FRESH')
    parent.native.need(not any((ROOT / x).exists() for x in ('queue/PAUSE','docs/briefs/PAUSE')), 'EXTERNAL_PAUSE')
    manifest, files = role()
    source = out / 'source/fpga'
    source.mkdir(parents=True)
    for name, data in files.items():
        path=source/name;path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as stream:stream.write(data)
    manifest['source_root']=str(source)
    parent.native.dump(out/'manifest.json',manifest)
    parent.native.dump(out/'host-hours.json',candidate_ladder.budget_from_hourly())
    template=json.loads((parent.NORMAL/'global-ticket.json').read_text())
    variants=[]
    for pair, old in zip(('01','23'),template['packages']):
        worker='s4-p16-c2-storage2-external-'+pair+'-v2';packet=out/('packet-'+pair)
        r=package.prepare(out/'manifest.json',source,old['profile'],worker,'run',packet,out/'host-hours.json')
        ticket=json.loads((packet/'ticket.json').read_text());v=copy.deepcopy(old)
        v.update(archive=str(packet/'package.tar.gz'),sha256=r['archive_sha256'],ticket_sha256=r['ticket_sha256'],
            manifest_sha256=parent.sha((packet/'manifest.json').read_bytes()),worker_id=worker,native_root=ticket['native_root'])
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
