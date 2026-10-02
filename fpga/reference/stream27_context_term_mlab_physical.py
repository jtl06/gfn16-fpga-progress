"""Source-matched MLAB term field/SYN proposal; no dispatch/whole route.

Use the actual storage2 FF project as the one-change comparator, not a compact
tag or timing lineage. Native exact54 whole-source PASS remains launch guard.
"""
import argparse
import json
from pathlib import Path
import re
from . import stream27_context_term_mlab_whole_native_v2 as native

ROOT=native.ROOT
SELF='reference/stream27_context_term_mlab_physical.py'
BASE=ROOT/'results/throughput-20260929/trackS-c2-storage2-native-v1'
NORMAL=ROOT/'results/throughput-20260929/trackS-c2-term-mlab-v1/full-normal-v2'


def build(stage):
    native.binder.captured.need(stage in ('syn','field'),'TERM_MLAB_PHYSICAL_STAGE')
    parent_path=BASE/('syn-project' if stage=='syn' else 'field-project')
    parent=json.loads((parent_path/'manifest.json').read_text())
    original=json.loads((BASE/'full-normal/production-bundle.json').read_text())
    source=json.loads((NORMAL/'production-bundle.json').read_text())
    manifest=json.loads((NORMAL/'manifest.json').read_text())
    sha=native.binder.captured.sha
    native.binder.captured.need(parent['source_sha256']==original['generated_sha256'],'TERM_MLAB_EXACT_FF_COMPARATOR')
    native.binder.captured.need(len(source['files'])==54 and source['term_mlab']['no_rw_check'] is False,'TERM_MLAB_EXACT54')
    for name,pin in parent['control_sha256'].items():
        native.binder.captured.need(sha((parent_path/name).read_bytes())==pin,'TERM_MLAB_CONTROL:'+name)
    for name,pin in parent['source_sha256'].items():
        native.binder.captured.need(sha((parent_path/'rtl'/name).read_bytes())==pin,'TERM_MLAB_FF_RTL:'+name)
    for name,pin in source['generated_sha256'].items():
        native.binder.captured.need(manifest['sources']['rtl/'+name]==pin,'TERM_MLAB_NORMAL_SOURCE:'+name)
    oldtop=parent['top'];top=source['top'] if stage=='syn' else oldtop+'_term_mlab_v1'
    native.binder.captured.need(top+'.sv' in source['files'],'TERM_MLAB_PHYSICAL_TOP')
    qsf=(parent_path/'probe.qsf').read_text()
    qsf=native.binder.captured.binder.parent.once(qsf,'TOP_LEVEL_ENTITY '+oldtop,'TOP_LEVEL_ENTITY '+top)
    qsf=re.sub(r'^set_global_assignment -name SYSTEMVERILOG_FILE rtl/\S+\n','',qsf,flags=re.M)
    qsf+=''.join('set_global_assignment -name SYSTEMVERILOG_FILE rtl/'+name+'\n' for name in source['rtl_sources'])
    files={'rtl/'+name:text.encode() for name,text in source['files'].items()}
    files.update({name:(parent_path/name).read_bytes() for name in ('probe.qpf','probe.sdc','run.tcl')})
    files['probe.qsf']=qsf.encode()
    result=dict(parent)
    result.update(status='prepared_not_native',top=top,source_sha256=source['generated_sha256'],
        control_sha256={name:sha(files[name]) for name in ('probe.qsf','probe.qpf','probe.sdc','run.tcl')},
        native_normal_id=native.IDS['full'],native_role_manifest_sha256=sha((NORMAL/'manifest.json').read_bytes()),
        term_mlab=dict(parent_project=str(parent_path),parent_manifest_sha256=sha((parent_path/'manifest.json').read_bytes()),
            parent_job='s4-p16-c2-storage2-whole-syn-v1' if stage=='syn' else 's4-p16-c2-storage2-field-f0-v1',
            source_bound_native_id=native.IDS['full'],ramstyle='MLAB',native_mapping_measured=False,
            no_rw_check=False,whole_route_released=False,promotion_allowed=False))
    return result,files


def prepare(output,stage):
    out=Path(output).resolve();native.binder.captured.need(out.is_relative_to(ROOT) and not out.exists(),'TERM_MLAB_PHYSICAL_FRESH')
    manifest,files=build(stage);out.mkdir(parents=True)
    for name,data in files.items():
        p=out/name;p.parent.mkdir(parents=True,exist_ok=True)
        with p.open('xb') as stream:stream.write(data)
    native.binder.captured.dump(out/'manifest.json',manifest)
    return dict(project=str(out),stage=stage,status='source_prepared_not_native',actual_native_required=native.IDS['full'])


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--stage',choices=('syn','field'),required=True);a=p.parse_args()
    print(json.dumps(prepare(a.output,a.stage),indent=2))
