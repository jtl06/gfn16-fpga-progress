"""Private source/settings feasibility, not installed-region legality.

Reads a frozen project; never writes RTL, preserves partitions, guesses boxes,
executes Quartus or submits a twin. Native grid/capacity/DRC remain mandatory.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re


def sha(raw):return hashlib.sha256(raw).hexdigest()


def source_hierarchy(project):
    project=Path(project).resolve();qsf=(project/'probe.qsf').read_text()
    top=re.findall(r'^set_global_assignment -name TOP_LEVEL_ENTITY (\w+)$',qsf,re.M)
    paths=re.findall(r'^set_global_assignment -name SYSTEMVERILOG_FILE (\S+)$',qsf,re.M)
    assert len(top)==1 and len(paths)==len(set(paths))
    assert 'set_global_assignment -name DEVICE 10AX115N4F40E3SG\n' in qsf
    assert 'set_parameter -name P 16\n' in qsf
    sources={name:(project/name).read_bytes() for name in paths};modules={}
    for name,raw in sources.items():
        for module in re.findall(r'^module\s+(\w+)\b',raw.decode(),re.M):
            assert module not in modules
            modules[module]=(name,raw.decode())
    def child(module,instance):
        text=modules[module][1]
        found=re.findall(r'^\s*(genefer_\w+)\s+(?:#\([^\n]+\)\s+)?'+re.escape(instance)+r'\s*\(',text,re.M)
        assert len(found)==1 and found[0] in modules,(module,instance,found)
        return found[0]
    arithmetic=child(child(top[0],'engine'),'arithmetic')
    fields=[]
    for i in range(3):
        module=child(arithmetic,'field'+str(i))
        fields.append(dict(hierarchy='engine|arithmetic|field'+str(i),module=module,
            source=modules[module][0],sha256=sha(sources[modules[module][0]])))
    text=modules[arithmetic][1]
    assert 'for(genvar b=0;b<P;b=b+1)begin: arithmetic' in text
    units={name:child(arithmetic,name) for name in ('crt','carry')}
    central=[f'engine|arithmetic|arithmetic[{i}].{name}' for i in range(16) for name in units]
    return dict(top=top[0],production_sv_count=len(paths),device='10AX115N4F40E3SG',
        project=str(project),qsf_sha256=sha(qsf.encode()),sdc_sha256=sha((project/'probe.sdc').read_bytes()),
        source_sha256={n:sha(raw) for n,raw in sources.items()},fields=fields,
        central_members=central,central_modules=units,
        invalid_central_parent='engine|arithmetic includes all three fields; never use it as a separate spine region',
        retained_transport_register_members=None,native_region_boxes=None,native_capacity=None,
        source_label='R13' if top[0]=='genefer_stream27_host_contexts_aw16_p16_protected_relay13_v1' else 'NOT_R13_UNLESS_EXACT_CORE_HANDOFF',
        installed_option_values_validated=False,native_grid_validated=False,region_DRC_PASS=False,
        settings_artifact_eligible=False,twin_submitted=False,baseline_gate=False)


def permitted_delta(old,new,legal_lines):
    """Exact optimization-preserving append-only QSF comparator."""
    assert new==old+''.join(line+'\n' for line in legal_lines)
    allowed={'PLACE_REGION','RESERVE_PLACE_REGION','CORE_ONLY_PLACE_REGION','REGION_NAME',
             'FLOATING_REGION','ATTRACTION_GROUP'}
    for line in legal_lines:
        match=re.fullmatch(r'set_instance_assignment -name (\w+) (.+)',line)
        assert match and match[1] in allowed
        assert not any(word in line for word in ('PARTITION','PRESERVE','SDC','CLOCK','FALSE_PATH','MULTICYCLE'))
    # A caller still needs exact installed values and native legality proof.
    return True


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('project',type=Path);a=p.parse_args()
    print(json.dumps(source_hierarchy(a.project),indent=2))
