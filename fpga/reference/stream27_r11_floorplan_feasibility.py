"""Read-only exact R11 region-membership source audit, not legal floorplanning.

Installed assignment/device checks and a bounded smoke remain separate gates.
No project creation, QSF edit, fitter launch or hard coordinate guess here.
"""
import hashlib
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
PROJECT=ROOT/'results/throughput-20260929/trackS-c2-storage-combo-transport11-physical-v1/physical-12000-v1/project'


def sha(raw):return hashlib.sha256(raw).hexdigest()


def audit():
    qsf=(PROJECT/'probe.qsf').read_text()
    assert 'set_global_assignment -name DEVICE 10AX115N4F40E3SG\n' in qsf
    top=re.findall(r'^set_global_assignment -name TOP_LEVEL_ENTITY (\w+)$',qsf,re.M)
    assert len(top)==1
    paths=re.findall(r'^set_global_assignment -name SYSTEMVERILOG_FILE (\S+)$',qsf,re.M)
    assert len(paths)==len(set(paths))==58
    source={path:(PROJECT/path).read_bytes() for path in paths}
    modules={}
    for path,raw in source.items():
        for name in re.findall(r'^module\s+(\w+)\b',raw.decode(),re.M):
            assert name not in modules
            modules[name]=(path,raw.decode())
    def child(parent,instance):
        text=modules[parent][1]
        found=re.findall(r'^\s*(genefer_\w+)\s+#\([^\n]+\)\s+'+re.escape(instance)+r'\s*\(',text,re.M)
        assert len(found)==1,(parent,instance,found)
        assert found[0] in modules
        return found[0]
    engine=child(top[0],'engine');arithmetic=child(engine,'arithmetic')
    fields=[]
    for i in range(3):
        module=child(arithmetic,'field'+str(i))
        fields.append(dict(path='engine|arithmetic|field'+str(i),module=module,
                           source_file=modules[module][0],sha256=sha(source[modules[module][0]])))
    text=modules[arithmetic][1]
    assert 'for(genvar b=0;b<P;b=b+1)begin: arithmetic' in text
    assert re.search(r'genefer_crt3_27_mont_pipe\s+crt\s*\(',text)
    assert re.search(r'genefer_stream27_blockcarry_lane_localbase_v1\s+#\([^\n]+\)\s+carry\s*\(',text)
    assert 'set_parameter -name P 16\n' in qsf
    central=[f'engine|arithmetic|arithmetic[{i}].{unit}' for i in range(16) for unit in ('crt','carry')]
    transport=[name for name in ('crt_transport_slot','crt_transport_start','crt_transport_double',
        'crt_transport_data','crt_transport_tag','crt_transport_base','crt_transport_reciprocal','crt_transport_limit',
        'crt_tag','crt_double','doubled_valid','doubled_start','doubled_row','doubled_data','doubled_context',
        'carry_epoch','carry_generation','carry_context') if re.search(r'\b'+name+r'\b',text)]
    # Constraining the enclosing arithmetic instance to the central region
    # includes all three fields, not a disjoint fourth member group.
    field_paths={f['path'] for f in fields}
    assert all(not any(p==f or p.startswith(f+'|') for f in field_paths) for p in central)
    return dict(schema='r11-floorplan-source-feasibility-v1',status='SOURCE_HIERARCHY_CONFIRMED_NATIVE_REGIONS_NOT_VALIDATED',
        project=str(PROJECT.relative_to(ROOT)),qsf_sha256=sha(qsf.encode()),top=top[0],
        source_sha256={p:sha(r) for p,r in source.items()},
        device='10AX115N4F40E3SG',production_rtl_count=58,three_field_instances=fields,
        central_instance_members=central,central_transport_register_bases=transport,
        central_warning='Do NOT assign engine|arithmetic wholesale to central spine: it also owns all3 fields. Exact post-SYN retained register collections needed.',
        region_shapes=None,resource_grid_observed=False,installed_assignments_validated=False,
        fitted_hierarchy_confirmed=False,capacity_by_region=None,DRC_smoke_pass=False,
        optional_ticket_submitted=False,physical_benefit=None,
        blockers=['No prior R10 region set exists','Native assignment option/geometry validation pending',
                  'Current Azure saved-layout diagnostics scratch blocked; no resource-safe native smoke launch authorized yet',
                  'No installed region semantic validation yet; closed settings API has no region flag, but a fresh source-identical QSF snapshot is possible after native checks'],
        baseline_gate=False,source_mutation=False)


if __name__=='__main__':print(json.dumps(audit(),indent=2))
