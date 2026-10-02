"""Existing P16-a canonical/unmerged AW6 source role for the shared queue.

No new generator, dispatcher or RTL policy. Reuse exact frozen P2-derived
P16 baseline compilation. Local arithmetic is limited to N64 schoolbook;
full-N project inputs remain immutable source/constant evidence only.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

from .stream27_field_probe_variants_v1 import compile_probe

ROOT=Path(__file__).resolve().parents[1]
PARENT='artifacts/stream27-p16a-aw16-p16-f0-prepared-v1'
PARENT_SHA='580c88ff54eed23edf605abd59ac00cb1a609bb8384990399e51de23c7ea28ec'
PINS={
    'reference/stream27_field_compile_param_v1.py':'3da78f91f62c11d1b7496062d6c260057456c75485fa71e71925b456f4c1a433',
    'reference/stream27_field_probe_variants_v1.py':'6ae132e0fe15b67c29b2fc7f1166be8fafee71a3fdfc21186702e88d8149cd00',
    'reference/stream27_field_physical_probe_v1.py':'840217940cbb01f797f7e74c8bd5d3a4c58f7bea901e05dbb524291d5116ebb5',
    'reference/stream27_field_compile.py':'c31f0295c891f02d2d96311e8ccc2f3c1d73e8fb9b0112fc4f2d80d3e972b53d',
    'reference/stream27_field_plan.py':'6103899b2488d4dc96aedfe2549db291045badb7e38f5885de20c7f721a4f032'}
CALENDAR=dict(first_input_accept=0,first_physical_output=93,first_terminal_sample=94,
              last_terminal_sample=97,next_nonoverlap_start=98)
BENCH='rtl/tb/stream27_p16a_aw6_v1.cpp'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def need(ok, why):
    if not ok:raise ValueError(why)


def footer_counts():
    """Event-only oracle independent of RTL/compiler, no NTT."""
    counts=dict(events=0,physical=0,eligible=0,resets=0,aborts=0,faults=0)
    cases=[(-1,-1,-1,-1)]*6
    cases += [(tick,-1,-1,-1) for tick in range(99)]
    cases += [(-1,tick,-1,-1) for tick in range(99)]
    cases += [(-1,-1,tick,-1) for tick in range(99)]
    cases += [(-1,-1,-1,tick) for tick in range(4)]
    for reset,cancel,disable,bad in cases:
        counts['events']+=109;counts['resets']+=1
        if reset>=0:counts['resets']+=1;counts['aborts']+=1
        if bad>=0:counts['faults']+=1
        for tick in range(93,97):
            if (reset>=0 and tick>=reset) or bad>=0:continue
            counts['physical']+=1
            counts['eligible']+=int((cancel<0 or tick<cancel) and (disable<0 or tick<disable))
    return counts


def verify_parent():
    project=ROOT/PARENT/'project'
    need(sha(project/'manifest.json')==PARENT_SHA,'P16A_PARENT_MANIFEST')
    m=json.loads((project/'manifest.json').read_text())
    for path,pin in PINS.items():need(sha(ROOT/path)==pin,'P16A_COMPILER_DRIFT '+path)
    need(m['geometry']['p']==16 and m['geometry']['data_bits']==27 and m['variant']=='baseline',
         'P16A_EXACT_CANONICAL_BASELINE')
    for name,pin in m['source_sha256'].items():need(sha(project/'rtl'/name)==pin,'P16A_PARENT_RTL '+name)
    for name,pin in m['control_sha256'].items():need(sha(project/name)==pin,'P16A_PARENT_CONTROL '+name)
    need(len(m['source_sha256'])==10,'P16A_PARENT_10_RTL')
    return m


def prepare(destination):
    need(not (ROOT/'docs/briefs/PAUSE').exists(),'brief PAUSE')
    destination=Path(destination).resolve();need(not destination.exists(),'P16A_FRESH_OUTPUT')
    parent=verify_parent()
    bundle=compile_probe(64,0,16,False)
    need(bundle['calendar']==CALENDAR,'P16A_DISTINCT_P2_CALENDAR')
    need(bundle['geometry']['contexts']==1 and bundle['geometry']['data_bits']==27,'P16A_GEOMETRY')
    source=destination/'inputs/fpga';source.mkdir(parents=True)
    names=[]
    for name,text in bundle['files'].items():
        target=source/'rtl'/name;target.parent.mkdir(exist_ok=True)
        target.write_text(text);names.append('rtl/'+name)
    need(len(names)==10,'P16A_NATIVE_10_RTL')
    (source/'rtl/tb').mkdir();shutil.copyfile(ROOT/BENCH,source/BENCH)
    (source/'lineage').mkdir()
    shutil.copyfile(ROOT/PARENT/'project/manifest.json',source/'lineage/parent-project-manifest.json')
    shutil.copyfile(ROOT/PARENT/'preparation.json',source/'lineage/parent-preparation.json')
    provenance=dict(ancestor_sha256=PINS,parent_manifest_sha256=PARENT_SHA,
        geometry=bundle['geometry'],calendar=bundle['calendar'],fault_contract=bundle['fault_contract'],
        native_RTL_sha256={name:hashlib.sha256(text.encode()).hexdigest() for name,text in bundle['files'].items()},
        omitted=bundle['omitted'],parent_RTL_files=len(parent['source_sha256']),
        full_N_numeric_NTT_performed=False,promotion_allowed=False)
    (source/'lineage/native-source-provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
    counts=footer_counts()
    footer='P16A_AW6_PASS '+' '.join(f'{key}={value}' for key,value in counts.items())+'\n'
    manifest=dict(schema='native-source-gate-v1',status='prepared_not_executed',
        host='UNBOUND_NO_DISPATCH',source_root=str(source),output_parent=str(destination/'UNBOUND_OUTPUT'),
        sources={str(p.relative_to(source)):sha(p) for p in sorted(source.rglob('*')) if p.is_file()},
        build=dict(top=bundle['top'],sv_sources=names,cpp_source=BENCH,parameters={'AW':6},
                   cflags=['-std=c++17','-O2','-Werror=return-type']),
        probe=dict(argv=['{exe}','--runtime-probe'],expected_json=dict(context_threads=1,model_threads=1,expected_threads=1)),
        steps=[dict(name='square-control',argv=['{exe}'],expected_returncode=0,expected_stdout=footer,expected_stderr=''),
               dict(name='negative-comparator',argv=['{exe}','--negative-comparator'],expected_returncode=1,
                    expected_stdout='',expected_stderr='P16A_DATA_MISMATCH tick=93 lane=0\n'),
               dict(name='negative-calendar',argv=['{exe}','--negative-calendar'],expected_returncode=1,
                    expected_stdout='',expected_stderr='P16A_SLOT_MISMATCH tick=93 physical occupied rows\n')],
        scope='P16-a AW6 canonical/unmerged physical datapath only; P2 legacy fault contract; not lazy/merged/SM1/warm/full-core',
        lint_baseline_policy='Shared r38 class gate; no per-line style baseline.')
    (destination/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    receipt=dict(status='prepared_unbound_P16a_AW6_not_executed',manifest_sha256=sha(destination/'manifest.json'),
        source_count=len(manifest['sources']),RTL_files=10,parent_manifest_sha256=PARENT_SHA,
        calendar=CALENDAR,expected_counts=counts,harness_sha256=sha(ROOT/BENCH),
        requires='Shared admitted native_class_package/global_queue and fresh budgets/resources; no owner self-launch',
        no_claims='No native/HDL/vendor execution, full-N numerical NTT, warm-field/control/correction or physical timing qualification.')
    (destination/'preparation.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('destination',type=Path)
    args=parser.parse_args();print(json.dumps(prepare(args.destination),indent=2))
