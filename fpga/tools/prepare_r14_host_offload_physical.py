"""Materialize one frozen R14 physical source project; never submit a job."""
import argparse
import importlib.util
import json
from pathlib import Path
from fpga.reference import stream27_host_offload_physical_v1 as source
from fpga.reference import stream27_host_offload_chip_v1 as chip


def prepare(output,role,gate):
    out=Path(output).resolve();role=Path(role).resolve()
    chip.need(out.is_relative_to(chip.ROOT) and not out.exists(),'FRESH_PHYSICAL_DESTINATION')
    chip.need(not (chip.ROOT/'docs/briefs/PAUSE').exists(),'PAUSE')
    native=json.loads((role/'manifest.json').read_text())
    small=chip.prepare(256,host_offload=1)
    chip.need(all(native['sources']['rtl/'+name]==pin for name,pin in small['generated_sha256'].items()),'EXACT_OWN_AW8_SOURCE_ROLE')
    m,files,spec=source.build()
    m.update(native_normal_id=gate,native_role_manifest_sha256=chip.sha((role/'manifest.json').read_bytes()))
    spec['settings']['manifest.json']=chip.sha(source.encoded(m))
    for name,raw in files.items():
        p=out/'project'/name;p.parent.mkdir(parents=True,exist_ok=True)
        with p.open('xb') as f:f.write(raw)
    (out/'project/manifest.json').write_bytes(source.encoded(m))
    loader=importlib.util.spec_from_file_location('r14_structural',chip.ROOT/'tools/prefit_structural_guard_v1.py')
    checker=importlib.util.module_from_spec(loader);loader.loader.exec_module(checker)
    result=checker.source_inventory(out/'project',spec)
    (out/'structural-inventory.json').write_bytes(source.encoded(spec))
    (out/'source-structural-result.json').write_bytes(source.encoded(result))
    chip.need(not result['findings'],'SOURCE_STRUCTURAL_FINDINGS:'+repr(result['findings']))
    proof=dict(schema='fit-provisional-aw8-geometry-v1',generator=dict(path=str(chip.ROOT/chip.SELF),sha256=source.PIN),
        kwargs=dict(host_offload=1),native_n=256,fit_n=65536)
    (out/'provisional-geometry.json').write_bytes(source.encoded(proof))
    return dict(project=str(out/'project'),source_count=66,transfers=30,source_findings=result['findings'],
        status='prepared_not_submitted',matched_equivalence_pending=True,
        manifest_sha256=chip.sha(source.encoded(m)))


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output',required=True);ap.add_argument('--normal-role',required=True);ap.add_argument('--gate',required=True)
    a=ap.parse_args();print(json.dumps(prepare(a.output,a.normal_role,a.gate),indent=2))
