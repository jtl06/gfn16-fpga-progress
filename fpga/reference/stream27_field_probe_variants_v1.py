"""Canonical P8 S-M1 and P16-a source-only physical probe generator.

Frozen P2 is preserved. S-M1 changes storage only; P16-a changes parallelism
only. Lazy arithmetic, merged roots and registered-fault semantics are NOT
silently composed into these attribution baselines.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import tarfile
from . import stream27_field_physical_probe_v1 as parent
from .stream27_field_compile_param_v1 import compile_transform,topology
from .stream27_sm1_source_v1 import verify as verify_sm1
from .stream_ntt_model import FIELDS,bit_reverse
from .stream_ntt_schedule import m20k

ROOT=Path(__file__).resolve().parents[1]
ANCESTORS={'reference/stream27_field_physical_probe_v1.py':'840217940cbb01f797f7e74c8bd5d3a4c58f7bea901e05dbb524291d5116ebb5',
    'rtl/kernel/genefer_stream27_row_arithmetic_v2.sv':'0feab680b40e97dc2a0d190fc4ed355248ed41706a13d5f665e8281978c2bbbb'}


def sha(raw):return hashlib.sha256(raw).hexdigest()


def verify_ancestors():
    for path,pin in ANCESTORS.items():
        if sha((ROOT/path).read_bytes())!=pin:raise ValueError('probe ancestor drift '+path)
    return verify_sm1()


def multiplier_source():
    verify_ancestors()
    raw=(ROOT/'rtl/kernel/genefer_stream27_row_arithmetic_v2.sv').read_text()
    source=raw.split('\nmodule genefer_stream27_add8_v2',1)[0]
    source=source.replace('genefer_stream27_mul8_v2','genefer_stream27_mulp_probe_v1')
    source=source.replace('parameter logic [31:0] P=', 'parameter int LANES=8,\n    parameter logic [31:0] P=',1)
    source=source.replace('[215:0]','[LANES*27-1:0]').replace('logic [7:0] lane_valid;','logic [LANES-1:0] lane_valid;')
    source=source.replace('lane_valid!={8{slot_pipe[3]}}','lane_valid!={LANES{slot_pipe[3]}}').replace('lane<8;','lane<LANES;')
    return source


def accounting(n,parallelism,rom_ledger,small_registers):
    stages=topology(n,parallelism)['stages']+topology(n,parallelism,inverse=True)['stages']
    depths=Counter()
    for stage in stages:
        if stage['shuffle_depth_per_buffer']:depths[stage['shuffle_depth_per_buffer']]+=parallelism
    # Depth1 was already a register in the parent. All2..32 arrays were M20K in P2.
    short_arrays=sum(count for depth,count in depths.items() if 2<=depth<=32)
    short_words=sum(depth*count for depth,count in depths.items() if depth<=32)
    depth_memory=sum(count*m20k(depth,38) for depth,count in depths.items() if depth>1 and (not small_registers or depth>32))
    root_memory=sum(m20k(r['period'],r['width']) for r in rom_ledger if r['direction'] in ('forward','inverse'))
    io_memory=sum(m20k(r['period'],r['width']) for r in rom_ledger if r['direction'] not in ('forward','inverse'))
    aw=n.bit_length()-1
    return dict(measured=False,delay_FIFO_count=sum(depths.values()),delay_depth_histogram=dict(sorted(depths.items())),
        small_M20K_arrays_replaced=short_arrays if small_registers else 0,
        short_register_words=short_words if small_registers else depths.get(1,0),
        short_declared_register_bits=(short_words if small_registers else depths.get(1,0))*38,
        additional_register_data_bits=(short_words-depths.get(1,0))*38 if small_registers else 0,
        register_data_reset=False,declared_token_bits=38,parent_P2_implemented_token_bits=36,
        delay_M20K_legal_tiling_proxy=depth_memory,transform_root_M20K_legal_tiling_proxy=root_memory,
        IO_root_M20K_legal_tiling_proxy=io_memory,total_M20K_legal_tiling_proxy=depth_memory+root_memory+io_memory,
        forward_inverse_butterfly_units=aw*parallelism,standalone_multiplier_units=3*parallelism,DSP_proxy=(aw+3)*parallelism,
        root_ROM_bits=sum(r['period']*r['width'] for r in rom_ledger),
        caution='Legal-rectangle memory proxies, not inference/packing measurements. S-M1 logic ramstyle and explicit shift chains must be confirmed by synthesis; no lazy/merged savings credited.')


def compile_probe(n=32,field=0,parallelism=8,small_registers=True,*,allow_full_constants=False):
    verify_ancestors()
    if n>256 and not allow_full_constants:raise ValueError('explicit full modular-power ROM authority required')
    aw=n.bit_length()-1;pw=parallelism.bit_length()-1
    if n!=1<<aw or not 5<=aw<=16 or parallelism not in (8,16) or field not in (0,1,2):raise ValueError('probe geometry')
    rows=n//parallelism;prime,generator=FIELDS[field];files={};roms=[];ledger=[];deps=set();transforms=[]
    for inverse in (False,True):
        result=compile_transform(n,field,parallelism,inverse=inverse,small_registers=small_registers,
            emit_numeric_roms=True,allow_large_root_tables=allow_full_constants)
        source=result['source'];transforms.append(result);deps.update(result['source_dependencies'])
        for item in result['rom_ledger']:
            if not item['file']:continue
            words=tuple(int(word,16) for word in result['rom_files'][item['file']].splitlines())
            module=item['file'].removesuffix('.hex')+'_embedded_p2_v1'
            roms.append(parent.embedded_rom(module,words,27))
            pattern=r'genefer_stream27_root_rom_prefetch #\(\.PERIOD\('+str(item['period'])+r'\),\s*'+r"\.FIRST_ROOT\(27'd"+str(item['first_R_root'])+r'\),\.HEX_FILE\("'+re.escape(item['file'])+r'"\)\)'
            source,count=re.subn(pattern,module,source)
            if count!=1:raise ValueError('unique embedded root anchor')
            ledger.append(dict(module=module,period=len(words),width=27,words_sha256=sha(result['rom_files'][item['file']].encode()),
                parent_hex=item['file'],direction='inverse' if inverse else 'forward'))
        files[result['module']+'.sv']=source
    psi=pow(generator,(prime-1)//(2*n),prime);rootnames=[];width=27*parallelism
    for inverse in (False,True):
        # Preserve P8 root module/file identity for exact isolated S-M1 diff.
        name=f'genefer_stream27_p2_{"untwist" if inverse else "twist"}_aw{aw}_f{field}_rom_v1'
        if parallelism==16:name=name.replace('_p2_','_p16a_')
        words=[]
        for row in range(rows):
            values=[]
            for lane in range(parallelism):
                index=bit_reverse(lane,pw)*rows+row
                value=(pow(psi,-index,prime)*pow(n,-1,prime)*(1<<64) if inverse else pow(psi,index,prime)*(1<<32))%prime
                values.append(value)
            words.append(sum(value<<(lane*27) for lane,value in enumerate(values)))
        roms.append(parent.embedded_rom(name,words,width));rootnames.append(name)
        ledger.append(dict(module=name,period=rows,width=width,
            words_sha256=sha(''.join(f'{word:0{(width+3)//4}x}\n' for word in words).encode()),
            direction='fused_untwist_normalize' if inverse else 'twist'))
    rom_file=f'genefer_stream27_{"p2" if parallelism==8 else "p16a"}_initialized_roms_aw{aw}_f{field}_v1.sv'
    files[rom_file]='// Exact modular-power ROM constants; no numeric NTT performed.\n'+'\n'.join(roms)
    old_name,source=parent._top(aw,field,transforms[0]['module'],transforms[1]['module'],*rootnames)
    profile='sm1' if small_registers else 'baseline'
    top=f'genefer_stream27_field_probe_aw{aw}_p{parallelism}_f{field}_{profile}_v1'
    source=source.replace(old_name,top)
    if parallelism==16:
        source=source.replace('[215:0]','[431:0]').replace('logic [7:0] range_lanes;','logic [15:0] range_lanes;')
        source=source.replace('lane<8;','lane<16;').replace(f'logic [{aw-4}:0] output_row',f'logic [{aw-5}:0] output_row')
        source=source.replace(f'localparam int T={n//8},ROW_W={aw-3},COUNT_W={aw-2};',f'localparam int T={rows},ROW_W={aw-4},COUNT_W={aw-3};')
        source=source.replace('genefer_stream27_mul8_v2 #(','genefer_stream27_mulp_probe_v1 #(.LANES(16),')
        files['genefer_stream27_mulp_probe_v1.sv']=multiplier_source()
    else:deps.add('rtl/kernel/genefer_stream27_row_arithmetic_v2.sv')
    files[top+'.sv']=source
    compiled={Path(p).name:(ROOT/p).read_text() for p in sorted(deps)};compiled.update(files)
    first=14+sum(t['topology']['first_output_edge'] for t in transforms)
    return dict(top=top,files=compiled,geometry=dict(n=n,aw=aw,p=parallelism,rows=rows,field=field,prime=prime,
        contexts=1,generation_bits=8,payload_bits=1,data_bits=27),variant=profile,
        calendar=dict(first_input_accept=0,first_physical_output=first-1,first_terminal_sample=first,
            last_terminal_sample=first+rows-1,next_nonoverlap_start=first+rows),
        rom_ledger=ledger,resource_basis=accounting(n,parallelism,ledger,small_registers),
        omitted=list(parent.OMITTED),fault_contract='Exact legacy P2 same-edge pending-fault suppression, unchanged; r17 registered-fault successor NOT included.',
        full_N_numeric_NTT_performed=False,physical_fit_qualified=False,promotion_allowed=False)


def prepare(destination,*,n=65536,field=0,parallelism=8,small_registers=True,allow_full_constants=False):
    if (ROOT/'docs/briefs/PAUSE').exists():raise ValueError('brief PAUSE')
    destination=Path(destination).resolve()
    if destination.exists():raise ValueError('fresh probe output')
    bundle=compile_probe(n,field,parallelism,small_registers,allow_full_constants=allow_full_constants)
    qsf=['set_global_assignment -name FAMILY "Arria 10"','set_global_assignment -name DEVICE '+parent.DEVICE,
        'set_global_assignment -name TOP_LEVEL_ENTITY '+bundle['top'],
        'set_global_assignment -name PROJECT_OUTPUT_DIRECTORY output_files','set_global_assignment -name NUM_PARALLEL_PROCESSORS 4',
        'set_global_assignment -name SEED 1','set_global_assignment -name SDC_FILE probe.sdc']
    qsf+=['set_global_assignment -name SYSTEMVERILOG_FILE rtl/'+name for name in bundle['files']]
    qsf+=['set_parameter -name AW '+str(bundle['geometry']['aw'])]
    qsf+=['set_instance_assignment -name VIRTUAL_PIN ON -to {'+pin+'}' for pin in parent.PORTS]
    controls={'probe.qsf':'\n'.join(qsf)+'\n','probe.qpf':'PROJECT_REVISION = "probe"\n','probe.sdc':parent.SDC,'run.tcl':parent.RUN_TCL}
    manifest={key:value for key,value in bundle.items() if key!='files'}
    manifest.update(status='prepared_provisional_physical_probe_not_executed',edition='pro',device=parent.DEVICE,
        compile_processors=4,seed=1,clock_period_ns=10,address_width=bundle['geometry']['aw'],
        bitstream_generation=False,allowed_stages=['syn','fit','sta'],
        source_sha256={name:sha(text.encode()) for name,text in bundle['files'].items()},
        control_sha256={name:sha(text.encode()) for name,text in controls.items()},
        ancestor_sha256=ANCESTORS,dispatch_owner='main only; no launch or worker-policy change by generator')
    project=destination/'project';(project/'rtl').mkdir(parents=True)
    for name,text in bundle['files'].items():(project/'rtl'/name).write_text(text)
    for name,text in controls.items():(project/name).write_text(text)
    (project/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    closure={str(p.relative_to(project)):sha(p.read_bytes()) for p in project.rglob('*') if p.is_file()}
    receipt=dict(status='prepared_source_only',project_manifest_sha256=closure['manifest.json'],project_sha256=closure,
        geometry=bundle['geometry'],resource_basis=bundle['resource_basis'],calendar=bundle['calendar'],
        fault_contract=bundle['fault_contract'],full_N_numeric_NTT_performed=False,promotion_allowed=False)
    (destination/'preparation.json').write_text(json.dumps(receipt,indent=2)+'\n')
    with tarfile.open(destination/'source.tar.gz','x:gz') as archive:
        for name in sorted(closure):archive.add(project/name,arcname='project/'+name,recursive=False)
        archive.add(destination/'preparation.json',arcname='preparation.json',recursive=False)
    return receipt


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--p',type=int,choices=(8,16),default=8);parser.add_argument('--baseline',action='store_true')
    parser.add_argument('--full-constant-roms',action='store_true');args=parser.parse_args()
    report=prepare(args.output,parallelism=args.p,small_registers=not args.baseline,allow_full_constants=args.full_constant_roms)
    print(json.dumps({k:report[k] for k in ('status','project_manifest_sha256','geometry','resource_basis','calendar')},indent=2))
