"""Immutable T5b qualification queue packet; no native/cloud execution."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import tarfile
from . import core27_prefill_pipe_v1_structure as design
from . import core27_prefill_pipe_v1_gates as gates
from . import core27_prefill_pipe_v1_mutations as mutations
from . import core27_prefill_pipe_qualification_v1 as recipe

ROOT=design.ROOT
SELF='reference/core27_prefill_pipe_qualification_prepare_v1.py'
RUNNER='tools/native_t5b_qualification_v1.py'
TEST='tests/test_core27_prefill_pipe_qualification_v1.py'
NATIVE_BASE='/home/jtl/gfn-fpga-lab/agent-work/core27-t5b-qualification-v1'
NATIVE_ROOT=NATIVE_BASE+'/snapshot-v1/fpga'
ORIGINAL='artifacts/core27-t5b-pipe-v1-preparation/aw5-normal-manifest.json'
ORIGINAL_SHA='7a082142f666db4600442522bc67565b0f64edd04f1765a663ed422fa247ce39'
PREREQUISITES={
 'core27-t5b-aw5-normal-aethia-v1':('4d85a1fec652a5ab19e871b9ddaa7295124761e07023f4085233ecd062109308','8df384b768a02eaa38b9a58292850a076860922d7e1d8bb82b22c68ac7b31f0c'),
 'core27-t5b-aw5-targeted-aethia-v1':('149b08859601029dc3381e9ca3aa9f5d6bfb8a05503172d091ff24c86360c1ef','d3a1ed7ef0f451a7c7c502650afa8af455e5a99b8a17b1f1e66b49a205b7dbc1'),
 'core27-t5b-aw16-normal-aethia-v1':('96257f0e110aae95a69b971034eb83ed8abc80c186cc7cd759e70b22a48f6551','55b2819c8496a850c556aa7d72ec4865c51482047a621190b82dea2dc4068a89')}


def digest(data):return hashlib.sha256(data).hexdigest()


def sources(root=ROOT):
    root=Path(root);design.validate(root);gates.validate(root)
    raw=(root/ORIGINAL).read_bytes()
    if digest(raw)!=ORIGINAL_SHA:raise ValueError('frozen native control manifest')
    prior=json.loads(raw);content={}
    for name,pin in prior['sources'].items():
        data=(root/name).read_bytes()
        if digest(data)!=pin:raise ValueError('frozen T5b native source drift '+name)
        content[name]=data
    for name in (SELF,RUNNER,TEST,'reference/core27_prefill_pipe_qualification_v1.py',recipe.AW16_BENCH):content[name]=(root/name).read_bytes()
    if content[recipe.AW16_BENCH].decode()!=recipe.aw16_harness(root):raise ValueError('exact AW16 harness delta')
    content[recipe.AW16_VECTOR]=(root/recipe.AW16_VECTOR).read_bytes()
    if digest(content[recipe.AW16_VECTOR])!=recipe.AW16_VECTOR_SHA:raise ValueError('frozen AW16 integer-oracle vector')
    prerequisites={}
    for directory,pins in PREREQUISITES.items():
        for name,pin in zip(('report.json','independent-review-v1.json'),pins):
            relative='results/throughput-20260929/'+directory+'/'+name;data=(root/relative).read_bytes()
            if digest(data)!=pin:raise ValueError('qualified native prerequisite '+relative)
            content[relative]=data;prerequisites[relative]=pin
    control,mutants,contracts=recipe.shared_mutants(root)
    for role,overlay in [('shared-control',control),*mutants.items()]:
        for name,text in overlay.items():content['roles/'+role+'/'+name]=text.encode()
    return prior,content,contracts,prerequisites


def packet(root=ROOT):
    prior,content,contracts,prerequisites=sources(root)
    pins={name:digest(raw) for name,raw in sorted(content.items())}
    kernels=[name for name in prior['build']['sv_sources'] if '/tb/' not in name and name!=mutations.CORE]
    def manifest(role,aw,steps):
        sv=[('roles/'+role+'/'+name if name==mutations.CARRY and role!='aw16-anchor' else name) for name in kernels]
        bridge=('roles/'+role+'/' if role!='aw16-anchor' else '')+mutations.BRIDGE
        sv+=[bridge,mutations.OBSERVER]
        return dict(schema='native-source-gate-v1',status='prepared_not_executed',host='aethia',source_root=NATIVE_ROOT,output_parent=NATIVE_BASE,sources=pins,
            build=dict(top=gates.TAIL,sv_sources=sv,cpp_source=recipe.AW16_BENCH if aw==16 else 'rtl/tb/core27_prefill_pipe_tail_v1.cpp',
                parameters=dict(AW=aw,NTT_LANES=64),cflags=['-std=c++17','-Werror=return-type']),
            probe=dict(argv=['{exe}','--runtime-probe'],expected_json=dict(context_threads=1,model_threads=1,expected_threads=1)),steps=steps)
    roles={};control_steps=[]
    for name,contract in contracts.items():
        command=contract['argv'];mode=command[1]
        step=recipe.step(5,mode,9 if name=='late_host_error' else None,'final' if name=='late_host_error' else None,name='control-'+name.replace('_','-'))
        control_steps.append(step)
        mutant=dict(step,name='mutant-'+name.replace('_','-'),expected_returncode=-6)
        mutant.pop('expected_stdout');mutant.pop('expected_stderr')
        roles[name]=manifest(name,5,[mutant])
    roles['shared-control']=manifest('shared-control',5,control_steps)
    anchor,groups=recipe.full_matrix();roles['aw16-anchor']=manifest('aw16-anchor',16,anchor)
    encoded={role:(json.dumps(m,indent=2)+'\n').encode() for role,m in roles.items()}
    role_files={role:dict(manifest=role+'-manifest.json',sha256=digest(raw)) for role,raw in encoded.items()}
    bundle=dict(schema='t5b-qualification-v1',status='prepared_not_executed',host='aethia',source_root=NATIVE_ROOT,output_parent=NATIVE_BASE,
        sources=pins,roles=role_files,mutations=list(mutations.NAMES),contracts=contracts,prerequisites=prerequisites,
        shared_control_guard_removal='T5_EMIT_SIGNED32_REPRESENTATION',reuse_build=roles['aw16-anchor']['build'],reuse_groups=groups,
        full_matrix_cases=93,anchor_cases=9,reuse_cases=84,
        queue_priority=['anchor','reuse:host-error-middle','reuse:carry-error-middle','reuse:reset-middle','mutants',
            'reuse:host-error-final','reuse:carry-error-final','reuse:reset-final','reuse:host-error-first','reuse:carry-error-first','reuse:reset-first','reuse:base-reload'],
        bounds=dict(host='aethia',cpus=[4,6],cpu_percent=200,memory_bytes=4*(1<<30),swap_bytes=0,model_threads=1,
            compile_workers=2,compile_lock='/home/jtl/gfn-fpga-lab/agent-work/square-core/fpga/artifacts/compile.lock',
            command_seconds=1800,invocation_seconds=3600,outer_seconds=3700,stop_grace_seconds=15),
        reuse_admission='Exact successful reviewed anchor report SHA and independent review SHA must be supplied after anchor completion; no speculative executable identity is accepted.',
        reuse_scope='Same immutable production RTL, observer, AW16 harness, build configuration, tools and ELF only. No AW5/normal model reuse. One group per invocation; fresh process per case.',
        limitation='Queue preparation only. No native/cloud/fit execution or qualification from recipes. Failure preserves all outputs and stops; no retry or aggregate promotion.')
    return content,encoded,bundle


def prepare(output,root=ROOT):
    root=Path(root);output=Path(output).resolve()
    if (root/'docs/briefs/PAUSE').exists():raise ValueError('brief PAUSE')
    if output.exists():raise ValueError('fresh qualification stage')
    content,roles,bundle=packet(root)
    # All derivations and input validation precede destination creation.
    output.mkdir(parents=True);source=output/'source/fpga';source.mkdir(parents=True)
    for name,data in content.items():
        p=source/name;p.parent.mkdir(parents=True,exist_ok=True)
        with p.open('xb') as stream:stream.write(data)
    for role,data in roles.items():
        with (output/(role+'-manifest.json')).open('xb') as stream:stream.write(data)
    bundle_bytes=(json.dumps(bundle,indent=2)+'\n').encode()
    with (output/'manifest.json').open('xb') as stream:stream.write(bundle_bytes)
    with (output/'source.tar.gz').open('xb') as raw:
        with gzip.GzipFile(filename='',mode='wb',fileobj=raw,mtime=0) as compressed:
            with tarfile.open(fileobj=compressed,mode='w') as archive:
                for name in sorted(content):
                    info=tarfile.TarInfo('fpga/'+name);info.size=len(content[name]);info.mode=0o644
                    with (source/name).open('rb') as stream:archive.addfile(info,stream)
    if packet(root)!=(content,roles,bundle):raise ValueError('preparation input drift; preserve failed stage')
    report=dict(status='prepared_not_executed',manifest_sha256=digest(bundle_bytes),archive_sha256=digest((output/'source.tar.gz').read_bytes()),
        archive_bytes=(output/'source.tar.gz').stat().st_size,source_files=len(content),role_manifests=bundle['roles'],
        source_root=NATIVE_ROOT,output_parent=NATIVE_BASE,mutants=8,shared_control_builds=1,
        full_N_matrix=93,late_final_anchor=9,remaining_reuse=84,reuse_groups=list(bundle['reuse_groups']),
        dispatch='main-only after independent packet admission; anchor executable/report is unknown until actual passing native build, then review seals reuse')
    with (output/'preparation.json').open('x') as stream:json.dump(report,stream,indent=2);stream.write('\n')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    print(json.dumps(prepare(args.output),indent=2))
