"""Immutable bounded A10 AW5 native packets, source preparation only.

Seven separately admitted builds: three field controls, three typed arithmetic
RTL mutations, and a whole-G4-lineage E2E-1 PRP chain/control comparator. Uses
the frozen aethia native launcher as-is. No SSH, native compiler, fit or dispatch.
"""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import shutil
import tarfile
from fpga.reference import a10_banked_engine_generate_v1 as gen
from fpga.reference import core27_crtmont_prp_e2e_v1 as prp
from fpga.reference import merged_negacyclic27_model as math

ROOT=gen.ROOT/'fpga'
REMOTE='/home/jtl/gfn-fpga-lab/agent-work/a10-banked-aw5-v1'
SELF='reference/a10_banked_aw5_prepare_v1.py'
TEST='tests/test_a10_banked_aw5_prepare_v1.py'
LAUNCHER='tools/native_source_gate_v1.py'
BENCH='rtl/tb/a10_banked_engine_aw5_v1.cpp'
PRP_BENCH='rtl/tb/a10_core_prp_aw5_v1.cpp'
HELPERS=['reference/a10_banked_engine_generate_v1.py','reference/a10_packed_root_lookup_v1.py',
         'reference/merged_negacyclic27_issue_model_v1.py','reference/merged_negacyclic27_model.py',
         'reference/stream_ntt_schedule.py','reference/stream_ntt_model.py',
         'reference/core27_crtmont_prp_e2e_v1.py',
         'reference/__init__.py',SELF,TEST,'tests/test_a10_banked_engine_generate_v1.py',BENCH,PRP_BENCH,LAUNCHER]
NEW_RTL=['rtl/kernel/'+name+'.sv' for name in [gen.ENGINE,gen.HOST,gen.CORE,
         'genefer_a10_profile3_v1','genefer_a10_canonical_butterfly_v1']]
ENGINE_SV=['rtl/kernel/'+name+'.sv' for name in ['genefer_montgomery_mul27_sparse_pipe',
        'genefer_sdp_ram32','genefer_ntt_banked27_engine','genefer_a10_profile3_v1',
        'genefer_a10_canonical_butterfly_v1',gen.ENGINE,gen.HOST]]
WHOLE_EXTRA=['rtl/kernel/'+name+'.sv' for name in ['genefer_digit_reduce27_pipe','genefer_mod64_pipe',
        'genefer_crt3_27_mont_pipe','genefer_sp_ram','genefer_div_recip_narrow',
        'genefer_carry_prefix_stream_pipe','genefer_div_recip_precision','genefer_carry_prefix_stream_precision',gen.CORE]]
LOOKUP_SV='rtl/kernel/a10_packed_lookup_aw5_bound_v1.sv'

def need(ok,message):
    if not ok:raise ValueError(message)

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def source_guard():
    gen.source_guard()
    _,parents=prp.parent_sources() # Exact audited G4 source/project/audit identity.
    for name,source in gen.sources().items():
        need((gen.ROOT/name).read_text()==source,'A10_GENERATED_DELTA_DRIFT '+name)
    need((ROOT/PRP_BENCH).read_text()==gen.e2e_cpp(),'A10_E2E_DRIVER_DELTA_DRIFT')
    need(sha(ROOT/LAUNCHER)==prp.LAUNCHER_SHA,'A10_FROZEN_NATIVE_LAUNCHER')
    return parents

def symbolic_ledger(aw=16):
    need(type(aw) is int and 1<=aw<=16,'A10_LEDGER_AW')
    n=1<<aw;g=max(1,(n+127)//128);point=(n+63)//64+7
    transform=aw*(g+9)
    ntt=2*transform+point+6
    return dict(status='derived_source_only_not_native_measured',n=n,
        transform_engine_cycles=transform,point_engine_cycles=point,
        transform_drain_edges=8*aw,point_drain_edges=7,
        transform_stage_setup_edges=aw,seed_setup_cycles=0,
        controller_start_plus_registered_done_consume_per_phase=2,phases=3,ntt_cycles=ntt,
        cold_header_words=4,cold_root_phase_cycles=9,
        normalization_extra_pipes_per_field=64,normalization_extra_pipes_three_fields=192,
        removed_recurrence_pipes_three_fields=192,
        arithmetic_DSP_net_change='source pipe counts cancel only; physical mapping unmeasured',
        root_M20K_three_fields_proxy=582 if aw==16 else 0,
        no_physical_fit_clock_or_native_cycle_promotion=True)

def mutate(kind,contents):
    files=dict(contents);delta={}
    engine='rtl/kernel/'+gen.ENGINE+'.sv'
    if kind=='root':
        s=files[LOOKUP_SV]
        pattern=r"assign ct_s4_q=27'h([0-9a-f]+);"
        matches=list(re.finditer(pattern,s));need(len(matches)==3,'A10_MUTANT_ROOT_SCOPE')
        m=matches[0];before=m.group(0);after=f"assign ct_s4_q=27'h{(int(m.group(1),16)+1)%math.FIELDS[0].p:07x};"
        files[LOOKUP_SV]=s[:m.start()]+after+s[m.end():];delta=dict(file=LOOKUP_SV,before=before,after=after)
    elif kind=='normalization':
        before='.normalization(normalization),';after=".normalization(normalization+32'd1),"
        files[engine]=gen.once(files[engine],before,after);delta=dict(file=engine,before=before,after=after)
    elif kind=='form':
        before='.gs(bf_in_valid[lane] && active_inverse),';after='.gs(bf_in_valid[lane]),'
        files[engine]=gen.once(files[engine],before,after);delta=dict(file=engine,before=before,after=after)
    else:need(kind=='normal','A10_MUTANT_KIND')
    return files,delta

def predict_typed_negative(kind):
    """Small independent index prediction only; never native/fault promotion."""
    need(kind in ('root','normalization','form'),'A10_MUTANT_KIND')
    f=math.FIELDS[0];psi=math.psi_for(32,f);p=f.p;ri=pow(f.r,-1,p)
    for trial in range(2):
        a=[1]+[0]*31 if trial==0 else [0]*31+[p-1]
        expected=math.direct_spectrum(a,f);data=list(a)
        for s in range(4,-1,-1):
            for start in range(0,32,2<<s):
                exp=math.bit_reverse((32>>(s+1))+(start>>(s+1)),5)
                w=pow(psi,exp,p)*f.r%p
                if kind=='root' and s==4:w=(w+1)%p
                for j in range(start,start+(1<<s)):
                    u,v=data[j],data[j+(1<<s)]
                    if kind=='form':data[j],data[j+(1<<s)]=(u+v)%p,(u-v)*w*ri%p
                    else:
                        t=v*w*ri%p;data[j],data[j+(1<<s)]=(u+t)%p,(u-t)%p
        for j,(actual,wanted) in enumerate(zip(data,expected)):
            if actual!=wanted:return f'A10_NUMERIC_{kind.upper()}_MISMATCH phase=forward index={j}\n'
        if kind=='normalization':
            # Impulse square has exact coefficient0=1. Before last normalized
            # GS upper multiplication it is N*R^-1; wrong scale changes index0.
            scale=math.normalization_constant(32,f)
            need((32*ri%p)*(scale+1)*ri%p!=1,'A10_MUTANT_NORMALIZATION_WITNESS')
            return 'A10_NUMERIC_NORMALIZATION_MISMATCH phase=inverse index=0\n'
    raise ValueError('A10_MUTANT_NOT_CAUGHT_BY_SMALL_CORPUS')

def native_manifest(case,pins,field=0,kind='normal',whole=False):
    remote=REMOTE+'/'+case
    f=math.FIELDS[field]
    if whole:
        build=dict(top=gen.CORE,sv_sources=ENGINE_SV+[LOOKUP_SV]+WHOLE_EXTRA,cpp_source=PRP_BENCH,
                   parameters=dict(AW=5,NTT_LANES=64),cflags=['-std=c++17','-Werror=return-type'])
        steps=[dict(name='prp-normal',argv=['{exe}','{root}/prp-aw5.txt'],expected_returncode=0,expected_stderr=''),
               dict(name='prp-negative-comparator',argv=['{exe}','{root}/prp-aw5.txt','--negative-comparator'],
                    expected_returncode=1,expected_stderr='E2E_RESIDUE_MISMATCH case=0 digit=0\n')]
    else:
        build=dict(top=gen.HOST,sv_sources=ENGINE_SV+[LOOKUP_SV],cpp_source=BENCH,
                   parameters=dict(AW=5,LANES=64,HOST_LANES=16,P=f.p,Q=f.q),
                   cflags=['-std=c++17','-Werror=return-type',f'-DA10_P={f.p}',f'-DA10_G={f.generator}'])
        if kind=='normal':
            steps=[dict(name='engine-normal',argv=['{exe}'],expected_returncode=0,expected_stderr='',
                        expected_stdout=f'A10_ENGINE_PASS aw=5 field={f.p} cases=5 operations=15 residues=480 cycles=540 profile_words=4\n')]
        else:
            steps=[dict(name='typed-'+kind,argv=['{exe}','--fault-'+kind],expected_returncode=1,expected_stdout='',
                        expected_stderr=predict_typed_negative(kind))]
    return dict(schema='native-source-gate-v1',status='prepared_not_executed',host='aethia',
        source_root=remote+'/snapshot-v1/fpga',output_parent=remote,sources=pins,build=build,
        probe=dict(argv=['{exe}','--runtime-probe'],expected_json=dict(context_threads=1,model_threads=1,expected_threads=1)),
        steps=steps,parent_manifest_sha256=prp.PARENT_MANIFEST_SHA,parent_audit_sha256=prp.AUDIT_SHA,
        scope='Additive canonical A10 AW5 source exploration; not original G4 RTL, wholecore fit, production or clock promotion',
        profile=dict(format=3,words=4,input_domain='ordinary/R^0',square_domain='R^-1',output_domain='ordinary/R^0',
                     output_order='natural after inverse; bitreverse odd-frequency after forward',
                     integer_doubling='unchanged after centered CRT; never folded into roots'),
        source_only_ledger=symbolic_ledger(5))

def archive(path,source,pins):
    with path.open('xb') as raw,gzip.GzipFile(filename='',mode='wb',fileobj=raw,mtime=0) as zipped:
        with tarfile.open(fileobj=zipped,mode='w') as tar:
            for name in sorted(pins):
                data=(source/name).read_bytes();need(hashlib.sha256(data).hexdigest()==pins[name],'A10_ARCHIVE_SOURCE_DRIFT')
                info=tarfile.TarInfo('fpga/'+name);info.size=len(data);info.mode=0o644;info.mtime=0
                tar.addfile(info,io.BytesIO(data))

def prepare(output):
    need(not(ROOT/'docs/briefs/PAUSE').exists(),'brief PAUSE')
    output=Path(output).resolve();need(not output.exists(),'A10_FRESH_OUTPUT_ONLY')
    parent_pins=source_guard()
    files={name:(ROOT/name).read_text() for name in sorted(set(HELPERS+NEW_RTL+ENGINE_SV+WHOLE_EXTRA))}
    # Keep original G4 source pins in closure for delta replay, not compilation.
    for name in parent_pins:files.setdefault(name,(ROOT/name).read_text())
    # Capture the parent project's own source copies and audit evidence so its
    # source-admission helper can replay in the immutable snapshot, not only live.
    for name in ['manifest.json','probe.qsf']:
        relative=prp.PARENT+'/'+name;files[relative]=(ROOT/relative).read_text()
    for name in parent_pins:
        relative=prp.PARENT+'/rtl/'+Path(name).name;files[relative]=(ROOT/relative).read_text()
    files[prp.AUDIT]=(ROOT/prp.AUDIT).read_text()
    compiled=gen.lookup_binding()
    files[LOOKUP_SV]='\n'.join(c['source'] for c in compiled['compiled'])+'\n'+compiled['source']
    files['prp-aw5.txt'],oracle=prp.corpus()
    files['prp-oracle.json']=json.dumps(oracle,indent=2)+'\n'
    output.mkdir(parents=True)
    cases=[(f'engine-f{f}',f,'normal',False) for f in range(3)]+[(f'engine-f0-{kind}',0,kind,False)
        for kind in ['root','normalization','form']]+[('whole-e2e1',0,'normal',True)]
    packets=[]
    for case,field,kind,whole in cases:
        source=output/case/'source/fpga';source.mkdir(parents=True)
        contents,delta=mutate(kind,files)
        pins={}
        for name,text in contents.items():
            dest=source/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(text)
            pins[name]=sha(dest)
        manifest=native_manifest(case,pins,field,kind,whole)
        path=output/case/'manifest.json';path.write_text(json.dumps(manifest,indent=2)+'\n')
        archive_path=output/case/'source.tar.gz';archive(archive_path,source,pins)
        manifest_sha=sha(path)
        packets.append(dict(case=case,field=field,kind=kind,whole=whole,mutation=delta,
            source_files=len(pins),source_bytes=sum((source/n).stat().st_size for n in pins),
            source_sha256=pins,manifest_sha256=manifest_sha,archive_sha256=sha(archive_path),
            source_root=manifest['source_root'],output_parent=manifest['output_parent'],
            command=['/usr/bin/python3.14','-I','-B',manifest['source_root']+'/'+LAUNCHER,
                     '--manifest',manifest['output_parent']+'/manifest.json','--manifest-sha256',manifest_sha,
                     '--output',manifest['output_parent']+'/native-v1']))
    source_guard()
    report=dict(status='prepared_source_only_not_executed',schema='a10-banked-aw5-packet-v1',packets=packets,
        dispatch_order='engine-f0 first exploratory elaboration, then remaining cases only after main admission',
        frozen_parent_pins=parent_pins,generator_sha256=sha(ROOT/'reference/a10_banked_engine_generate_v1.py'),
        lookup_generator_sha256=sha(ROOT/'reference/a10_packed_root_lookup_v1.py'),
        generated_lookup_source_sha256=hashlib.sha256(files[LOOKUP_SV].encode()).hexdigest(),
        generated_lookup_tables=[c['root_table_sha256'] for c in compiled['compiled']],
        limitations=['No HDL/Verilator/native invocation on Mac; no remote staging/dispatch.',
            'Native launcher uses exact aethia profile CPU4/6 200% 4GiB noSwap and shared compile lock.',
            'Root/data E0/E1/E2/E7/E8 and all cycle counts are source-derived pending native evidence.',
            '194M20K/field packed lookup at AW16 is legal-tiling proxy, not ROM inference or fit.',
            'Canonical27 only; no lazy28/28x28 qualification or streaming integration.'],
        bounds=dict(CPUs=[4,6],CPUQuota='200%',MemoryMax='4G',MemorySwapMax='0',
            command_seconds=1800,overall_seconds=3600,outer_seconds=3700,TimeoutStopSec=10,KillMode='control-group'),
        full_N_numeric_NTT_performed=False,HDL_or_native_performed=False,promotion_allowed=False,
        symbolic_aw16=symbolic_ledger(16),whole_ntt_source_delta_vs_parent=20558-symbolic_ledger(16)['ntt_cycles'],
        cold_profile_source_delta_vs_parent=8743-9,
        oracle=dict(engine='independent direct polynomial evaluation + schoolbook negacyclic coefficients, 64-bit exact bounds',
                    whole='unchanged E2E-1 Python pow bigint expected residues/certificates',
                    multiply_bound=(max(f.p for f in math.FIELDS)-1)**2,accumulate='reduce every term before next product addition'),
        exact_next_gate='Main reads engine/controller/generator/header/normalizer/bench/closure, admits engine-f0; capture first native elaboration/control result before broad fault matrix.')
    (output/'preparation.json').write_text(json.dumps(report,indent=2)+'\n')
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    print(json.dumps(prepare(p.parse_args().output),indent=2))
