"""Independent whole-core grouped compact-row orient8 evidence audit, never an RTL runner.

Native candidate identities, commands and source closure are checked directly.
Only the frozen independent R2 vector/integer audit is reused; no candidate
receipt is rewritten to impersonate an ancestor. No saved binary is executed.
"""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
import shlex

NORMAL_SHA='63e4c7ba0fed1bb203956b5fd28f595dc2a4a957ba905f4160ad8e96961eea6f'
INTEGER_SHA='785100ed9ae507e04c086a893fd401db189a847cdbc9e428e6ee6f9ed5de9920'
BASE_MAP_SHA='0ba6a60b369d099b5ed8a2f49b14fa059072789dddf5120146f0640fa1a3ea73'
OLD_TOP='genefer_square_core27_stream_prefetch_r2_host_broadcast'
TOP=OLD_TOP+'_orient8_rowcompact'
OLD_HOST='genefer_ntt_banked27_prefetch_r2_host_broadcast_engine'
HOST='genefer_ntt_banked27_prefetch_r2_host_broadcast_orient8_rowcompact_engine'
OLD_ENGINE='genefer_ntt_banked27_prefetch_r2_engine'
ENGINE='genefer_ntt_banked27_prefetch_r2_orient8_rowcompact_engine'
OLD_BENCH='square_core27_stream_prefetch_r2_host_broadcast'
BENCH=OLD_BENCH+'_orient8_rowcompact'
RUNNER='reference/core27_prefetch_r2_rowcompact_regression.py'
RUNNER_SHA='4c5866ba5b35d24e520933dc44901a74c5deaab2b8d34053c7ee36cd686a2cf8'
SNAPSHOT='/home/jtl/gfn-fpga-lab/agent-work/core27-prefetch-r2-rowcompact/snapshot-v1/fpga'
EXTRA_PINS={
 "rtl/kernel/genefer_ntt_banked27_prefetch_r2_orient8_engine.sv": "e6d524b36eb26f791617bbafdd440f18fe2ef0abe08aba3a26c9aa896b0ea138",
 "rtl/kernel/genefer_ntt_banked27_prefetch_r2_host_broadcast_orient8_engine.sv": "03a3c3183bace1ec37e6f9c81462ca4debe90625b093e054f71af55b050fd68d",
 "rtl/kernel/genefer_square_core27_stream_prefetch_r2_host_broadcast_orient8.sv": "5e02a3d2795c3b554990092ce98e651b7b236ec07a59b2ffbb8e51f67c7215cd",
 "rtl/tb/square_core27_stream_prefetch_r2_host_broadcast_orient8.cpp": "2690d44c6321870e93cc7aae46ee7e32092a01e5af0202efe2256237446f2249",
 "rtl/tb/square_core27_stream_prefetch_r2_host_broadcast_orient8_threaded.cpp": "9d4a811a96ff6cb670d7eba39f08674fc05b7aa01bb8bbbfcb2676e520c85e8d",
 "reference/prefetch_r2_orient8_structure.py": "8e9a3134b8d6d867d4dcd77349067c25eb419e78d14402fb74a728d1bfdea08f",
 "rtl/kernel/genefer_ntt_banked27_tiled_engine.sv": "d3dbaa6fe626e7e926b589f92b84959381b6c7aff74cb21a2d9f1d8d25353af0",
 "reference/core27_prefetch_r2_orient8_regression.py": "c77142630432dccdc11c7570f026a1658ba7bbeb4031840798d600732c59f0e0",
 "reference/prefetch_r2_rowcompact_structure.py": "51dae93dbc4792d2ae7550dba8afa1babfd66d8b98019749754d0e62a0b37e17",
 "rtl/kernel/genefer_ntt_banked27_prefetch_r2_orient8_rowcompact_engine.sv": "604dc89eb87c8126372e468d7a9e130e8cc483a4c02e8f3e3b9ac189e230e6a9",
 "rtl/kernel/genefer_ntt_banked27_prefetch_r2_host_broadcast_orient8_rowcompact_engine.sv": "446e9878d69e6b3d2237b714dc141b6bdaf04439664022f3b17afe32ae1106ac",
 "rtl/kernel/genefer_square_core27_stream_prefetch_r2_host_broadcast_orient8_rowcompact.sv": "5199a28f5a739fe007172a9a1d206406d7c41103bcadac854993583f1d96d01a",
 "rtl/tb/square_core27_stream_prefetch_r2_host_broadcast_orient8_rowcompact.cpp": "d8753d2c0d724a97b9c505a3a4734be3469914012f641fc8e76390a4bae1cf49",
 "rtl/tb/square_core27_stream_prefetch_r2_host_broadcast_orient8_rowcompact_threaded.cpp": "50fc55c271067305741ec9be74aecf9e4ed6cd7f81045788b6b34a3c8d4c3a62"
}
VECTOR_SHA={
 1:'0f4a674ed168b123b57df4beced18993d635b6db4afc94b83e9a264027daf740',
 5:'a5b46cb2f52ce817bed3de90a91dfc6fb038b30215edc7d861514d1106919edd',
 7:'314d1c51d3354450ce66fd7c29dbac91e311073a001b1c8558d9dad73da75cac',
 16:'3449c1e3e1d7c0820842ecb30295b963b4aa81af6b27be8e38b7c87f2bd39f3d'}
BASELINE_REPORT_SHA={
 1:'5d639efd939a184651645af6d04557ec01609bab80bd72ccd3b7bf3cd173e954',
 5:'155f9f9bc77555dd60f36a5d9cb8b882c981b3aed8cd0bd3083e8fe9876a19ea',
 7:'e32a3584680da7fc00b5ff953a87fb91c0f2232fee82cadf8ea9abc22b48e926',
 16:'c871241aeca6b8c0e592aa757a785887d495859ddc5381c5e7e0ec055e6d5487'}
METRIC_SHA={
 1:'970e142db989ee986a6cc876e7efc9970bc679c1122fdf72b7515f69fd661ecb',
 5:'620e7775e98b5214fc4dda4c9b6d2db7d66f2b604b35ddc13387c82926dae08c',
 7:'8398d37f2576367623180f84a3ead14f73f5fca6084e65ccf0f6d86a76b9a994',
 16:'af2a491c671a4618d1a79601673ece642be9c28c3d3c191400643d404a76bda8'}


def require(value,message):
    if not value:raise ValueError(message)


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def map_sha(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def normal_helpers():
    directory=Path(__file__).resolve().parent
    require(sha(directory/'verify_core27_prefetch_r2_offline.py')==NORMAL_SHA and
            sha(directory/'verify_square_core27_rootpipe_offline.py')==INTEGER_SHA,'independent oracle/dependency pins')
    if __package__:
        from . import verify_core27_prefetch_r2_offline as normal
    else:
        raise ValueError('use python -m fpga.reference.verify_core27_rowcompact_offline')
    require(Path(normal.__file__).resolve()==directory/'verify_core27_prefetch_r2_offline.py','independent oracle path')
    return normal


def source_contract(pins,normal):
    require(isinstance(RUNNER_SHA,str) and re.fullmatch('[0-9a-f]{64}',RUNNER_SHA),'reviewed runner pin pending')
    new=dict(EXTRA_PINS);new[RUNNER]=RUNNER_SHA
    require(len(pins)==58 and all(pins.get(name)==value for name,value in new.items()),'exact fifteen-source addition to frozen43 closure')
    original={name:value for name,value in pins.items() if name not in new}
    require(len(original)==43 and map_sha(original)==BASE_MAP_SHA,'exact frozen host-broadcast43 closure')
    for name,value in normal.SOURCE_PINS.items():require(original.get(name)==value,'known frozen ancestor identity')
    replacements={normal.TOP:TOP,'genefer_ntt_banked27_prefetch_r2_host_engine':HOST,OLD_ENGINE:ENGINE}
    order=['rtl/kernel/'+replacements.get(name,name)+'.sv' for name in normal.RTL_PINS]
    require(len(order)==len(set(order))==16 and all(name in pins for name in order),'candidate sixteen-kernel closure')
    require(all('rtl/kernel/'+name+'.sv' not in order for name in (OLD_TOP,OLD_HOST,OLD_ENGINE)),'ancestors excluded from compiled closure')
    return order


ROW_DECLARE_OLD="    logic [RW-1:0] row_tag [0:6][0:BANKS-1];\n"
ROW_DECLARE_NEW="    // Compact common rows, locally replicated for sixteen physical banks.\n    // All row selectors describe the RAM read seven register edges earlier.\n    // Preserved local tags bound write-row bus fanout without new latency.\n    localparam int ROW_TAG_BANKS=16,ROW_TAG_GROUPS=(BANKS+ROW_TAG_BANKS-1)/ROW_TAG_BANKS;\n    logic [RW-1:0] issue_row_base,issue_row_toggle;\n    assign issue_row_base=state==BF_READ && issue_fire ? RW'(base_addr>>KW) :\n                          state==MUL_READ && issue_fire ? RW'(point_base>>KW) : '0;\n    assign issue_row_toggle=state==BF_READ && issue_fire ? RW'(stage_toggle_mask>>KW) : '0;\n    for(genvar group=0;group<ROW_TAG_GROUPS;group=group+1) begin : row_tags\n        (* preserve, dont_merge *) logic [RW-1:0] base_pipe [0:6],toggle_pipe [0:6];\n        (* preserve, dont_merge *) logic [PW-1:0] pairing_pipe [0:6];\n        (* preserve, dont_merge *) logic [6:0] orientation_pipe;\n        always_ff @(posedge clk or negedge rst_n) begin\n            if(!rst_n) begin\n                orientation_pipe<=0;\n                for(int t=0;t<7;t=t+1) begin\n                    base_pipe[t]<=0;toggle_pipe[t]<=0;pairing_pipe[t]<=0;\n                end\n            end else begin\n                base_pipe[0]<=issue_row_base;toggle_pipe[0]<=issue_row_toggle;\n                pairing_pipe[0]<=pairing;orientation_pipe<={orientation_pipe[5:0],orientation};\n                for(int t=1;t<7;t=t+1) begin\n                    base_pipe[t]<=base_pipe[t-1];toggle_pipe[t]<=toggle_pipe[t-1];\n                    pairing_pipe[t]<=pairing_pipe[t-1];\n                end\n            end\n        end\n    end\n"
ROW_RESET_OLD="            for(int t=0;t<7;t=t+1) for(int b=0;b<BANKS;b=b+1) row_tag[t][b]<=0;\n"
ROW_RESET_NEW=""
ROW_SHIFT_OLD="            for(int b=0;b<BANKS;b=b+1) begin\n                row_tag[0][b]<=data_ra[b];\n                for(int t=1;t<7;t=t+1) row_tag[t][b]<=row_tag[t-1][b];\n            end\n"
ROW_SHIFT_NEW=""
ROW_BF_OLD="                data_we[bank]=1;data_wa[bank]=row_tag[6][bank];data_w[bank]=bf_write_option[pairing];\n"
ROW_BF_NEW="                data_we[bank]=1;\n                data_wa[bank]=row_tags[bank/ROW_TAG_BANKS].base_pipe[6] |\n                    ((1'(bank>>row_tags[bank/ROW_TAG_BANKS].pairing_pipe[6])^\n                      row_tags[bank/ROW_TAG_BANKS].orientation_pipe[6]) ?\n                     row_tags[bank/ROW_TAG_BANKS].toggle_pipe[6] : RW'(0));\n                data_w[bank]=bf_write_option[pairing];\n"
ROW_MUL_OLD="                data_we[bank]=1;data_wa[bank]=row_tag[6][bank];data_w[bank]=product[bank%LANES];\n"
ROW_MUL_NEW="                data_we[bank]=1;data_wa[bank]=row_tags[bank/ROW_TAG_BANKS].base_pipe[6];data_w[bank]=product[bank%LANES];\n"
ROW_SHADOW="    // synthesis translate_off\n    // Native simulation compares every compute write against the original\n    // per-bank address-age pipeline. This shadow is absent from synthesis.\n    logic [RW-1:0] legacy_row_tag [0:6][0:BANKS-1];\n    always_ff @(posedge clk or negedge rst_n) begin\n        if(!rst_n) begin\n            for(int t=0;t<7;t=t+1) for(int b=0;b<BANKS;b=b+1) legacy_row_tag[t][b]<=0;\n        end else begin\n            for(int b=0;b<BANKS;b=b+1) begin\n                legacy_row_tag[0][b]<=data_ra[b];\n                for(int t=1;t<7;t=t+1) legacy_row_tag[t][b]<=legacy_row_tag[t-1][b];\n                if(data_we[b] && (state==BF_READ || state==BF_DRAIN || state==MUL_READ || state==MUL_DRAIN) &&\n                   data_wa[b]!==legacy_row_tag[6][b]) $fatal(1,\"compact row write address mismatch\");\n            end\n        end\n    end\n    // synthesis translate_on\n"

def source_delta(members):
    def text(name):return members[name].decode()
    old=text('rtl/kernel/'+OLD_TOP+'.sv')
    require(old.count('module '+OLD_TOP+' #(')==1 and old.count(OLD_HOST+' #(')==1,'unique top/host source anchors')
    want=old.replace('module '+OLD_TOP+' #(','module '+TOP+' #(').replace(OLD_HOST+' #(',HOST+' #(')
    require(text('rtl/kernel/'+TOP+'.sv')==want,'whole-core delta differs from exact wrapper substitution')
    original=text('rtl/tb/'+OLD_BENCH+'.cpp');require(original.count('V'+OLD_TOP)==2,'bench model anchor count')
    require(text('rtl/tb/'+BENCH+'.cpp')==original.replace('V'+OLD_TOP,'V'+TOP),'bench semantic delta')
    original=text('rtl/tb/'+OLD_BENCH+'_threaded.cpp')
    require(original.count('V'+OLD_TOP)==1 and original.count('#include "'+OLD_BENCH+'.cpp"')==1,'thread wrapper anchors')
    want=original.replace('V'+OLD_TOP,'V'+TOP).replace('#include "'+OLD_BENCH+'.cpp"','#include "'+BENCH+'.cpp"')
    require(text('rtl/tb/'+BENCH+'_threaded.cpp')==want,'thread wrapper delta')
    original=text('rtl/kernel/'+OLD_HOST+'.sv')
    require(original.count('module '+OLD_HOST+' #(')==1 and original.count(OLD_ENGINE+' #(')==1,'host/engine anchors')
    require(text('rtl/kernel/'+HOST+'.sv')==original.replace('module '+OLD_HOST+' #(','module '+HOST+' #(').replace(OLD_ENGINE+' #(',ENGINE+' #('),'host engine substitution')
    original=text('rtl/kernel/'+OLD_ENGINE+'.sv')
    tile='''    // Same-edge replicas: eight arithmetic lanes per driver, no new latency.
    localparam int ORIENT_TILE_LANES=8,ORIENT_TILES=(LANES+ORIENT_TILE_LANES-1)/ORIENT_TILE_LANES;
    for(genvar tile=0;tile<ORIENT_TILES;tile=tile+1) begin : orientation_tiles
        (* preserve, dont_merge *) logic orientation_q;
        always_ff @(posedge clk or negedge rst_n) begin
            if(!rst_n) orientation_q<=0;
            else orientation_q<=orientation;
        end
    end
'''
    anchor='    for(genvar lane=0;lane<LANES;lane=lane+1) begin : arithmetic'
    changes=[('module '+OLD_ENGINE+' #(','module '+ENGINE+' #('),
        ('logic orientation,orientation_d,point_half,point_half_d,low_stage_d;',
         'logic orientation,point_half,point_half_d,low_stage_d;'),(anchor,tile+anchor),
        ('assign u=orientation_d ?','assign u=orientation_tiles[lane/ORIENT_TILE_LANES].orientation_q ?'),
        ('assign v=orientation_d ?','assign v=orientation_tiles[lane/ORIENT_TILE_LANES].orientation_q ?'),
        ('orientation_d<=0;point_half_d<=0;','point_half_d<=0;'),
        ('orientation_d<=orientation;point_half_d<=point_half;','point_half_d<=point_half;')]
    want=original
    for old,new in changes:
        require(want.count(old)==1,'unique orientation source anchor')
        want=want.replace(old,new)
    # Literal compact-tag reconstruction, independently embedded here.
    # Candidate source/model modules are hashed but never imported or executed.
    for old,new in ((ROW_DECLARE_OLD,ROW_DECLARE_NEW),(ROW_RESET_OLD,ROW_RESET_NEW),
                    (ROW_SHIFT_OLD,ROW_SHIFT_NEW),(ROW_BF_OLD,ROW_BF_NEW),(ROW_MUL_OLD,ROW_MUL_NEW)):
        require(want.count(old)==1,'unique compact-row source anchor')
        want=want.replace(old,new)
    anchor='    always_comb begin\n        root_read_count=0;'
    require(want.count(anchor)==1,'unique shadow insertion anchor')
    want=want.replace(anchor,ROW_SHADOW+anchor)
    require(text('rtl/kernel/'+ENGINE+'.sv')==want,'exact orientation8 plus grouped compact-row/shadow delta')


def vector_coverage(root,report,steps,remote,normal):
    """Native segment/coverage checks plus independently recomputed squareDup."""
    aw=report['aw'];n=1<<aw;name=f'vectors-aw{aw}.txt'
    raw=normal.local_file(root,name).read_bytes();lines=raw.splitlines(keepends=True)
    require(normal.digest(raw)==report['vectors']['sha256']==VECTOR_SHA[aw],'complete identical frozen vector suite')
    parts=report['segments'];require(parts and [p['index'] for p in parts]==list(range(len(parts))),'segment index coverage')
    require(len(parts)==(2 if aw==16 else 1),'exact frozen profile segmentation')
    rebuilt=lines[0];next_start=1;all_metrics=[];totals=Counter();aborts=[];invalid=[];runs=[];cold=warm=0;bases=set()
    for part in parts:
        index,start,end=part['index'],part['start'],part['end'];segment=f'segment{index}.txt'
        require(type(start) is int and type(end) is int and start==next_start and start<end<=len(lines),'contiguous segment partition')
        payload=normal.local_file(root,segment).read_bytes()
        require(normal.digest(payload)==part['sha256'] and payload==lines[0]+b''.join(lines[start:end]),'exact segment bytes/hash')
        if index:require(lines[start].startswith(b'LOAD '),'cannot split live LOAD_KEEP/NO_READ chain')
        rebuilt+=b''.join(lines[start:end]);next_start=end
        step=f'test-segment{index}'
        require(step in steps and steps[step]['command']==[str(remote),str(remote.parent/segment),'profile'],'candidate segment command')
        rows,coverage=normal.audit_vectors(payload.decode(),normal.local_file(root,steps[step]['log']).read_text(),aw)
        all_metrics+=rows;totals.update(coverage['commands']);aborts+=coverage['abort_labels'];invalid+=coverage['invalid_at'];runs+=coverage['runs']
        cold+=coverage['cold_runs'];warm+=coverage['warm_runs'];bases.update(coverage['bases'])
    require(rebuilt==raw and next_start==len(lines),'segment omission/duplication')
    require(len({r['case'] for r in all_metrics})==len(all_metrics),'duplicate case across segments')
    require(all_metrics==report['metrics'] and map_sha(all_metrics)==METRIC_SHA[aw],'exact raw/report/baseline metric identity')
    info=report['vectors'];require(info['seed']==20260929 and len(all_metrics)==info['squares'] and totals['RUN']==info['readbacks'],'reported seed/coverage')
    require((len(all_metrics),totals['RUN'],len(aborts))=={1:(529,522,9),5:(568,561,20),7:(12,10,0),16:(12,10,0)}[aw],'complete normal operation/readback/abort coverage')
    last=[(b,b,i) for b in (2*n+5,1000000000) for i in sorted({max(0,n-16),n-1})]
    require(info['fusion_invalid_final_row_cases']==4 and invalid[-4:]==last,'four final-row canonical-boundary errors')
    if aw in (1,5):require({'conversion','root','ntt','crt','carry','root0','root1','root2','root3'}<=set(aborts),'reset-phase coverage')
    if aw==5:
        require(all(aborts.count(x)==2 for x in ('convert-m1','convert-0','convert-p1')) and aborts.count('crt-active')==1,'conversion/carry active boundaries')
        require(all(aborts.count('profile-'+x)==1 for x in ('lastavailable','consumed','commit','check')),'profile boundary resets')
    require([c['base'] for c in info['fermat_chains']]==([2*n+6,2*n+7] if aw in (1,5) else []),'small Fermat chain cases')
    for chain in info['fermat_chains']:
        b=chain['base'];exponent=pow(b,n);selected=[r for r in runs if r['case'].startswith(f'fermat-b{b}-s')]
        require([r['bit'] for r in selected]==list(map(int,bin(exponent)[2:])) and len(selected)==chain['steps'],'Fermat exponent sequence')
        require(selected and selected[-1]['residue']==int(chain['residue_hex'],16)==pow(2,exponent,exponent+1),'independent Fermat integer result')
    if aw==16:require({r['cycles'] for r in all_metrics}=={32965,41708},'R2 full-N warm/cold cycle identity')
    return dict(operations=len(all_metrics),readbacks=totals['RUN'],no_readback_operations=totals['RUN_NOREAD'],
        cold_runs=cold,warm_runs=warm,abort_labels=aborts,bases=sorted(bases),segments=len(parts),
        final_row_invalid_cases=4,baseline_report_sha256=BASELINE_REPORT_SHA[aw],baseline_metrics_sha256=METRIC_SHA[aw])


def metadata(report,manifest,manifest_sha,order):
    require(report.get('status')=='passed' and 'error' not in report,'failed/incomplete profile')
    require(report['top']==TOP and report['scope']=='Single-profile normal format2 grouped compact-row host-broadcast whole-core simulation','candidate top/scope')
    aw=report['aw'];require(type(aw) is int and aw in (1,5,7,16),'explicit AW profile')
    require(manifest['status']=='prepared_not_executed' and manifest['sources']==report['sources'] and
        manifest['target']==str(PurePosixPath(SNAPSHOT).parent) and manifest['top']==TOP and
        manifest['supported_aw']==[1,5,7,16] and re.fullmatch('[0-9a-f]{64}',manifest['archive_sha256']),'approved native snapshot')
    require(report['manifest_sha256']==manifest_sha and report['compiled_source_order']==order,'manifest/compiled closure binding')
    for name,wanted in {'n':1<<aw,'ntt_lanes':64,'model_threads':1,'compile_workers':2,
        'scratch_reservation_bytes':768<<20,'scratch_free_floor_bytes':2<<30,'durable_reservation_bytes':64<<20,
        'durable_free_floor_bytes':10<<30,'host_memory_floor_bytes':4<<30,
        'command_timeout_seconds':1800,'lock_wait_timeout_seconds':1800}.items():
        require(type(report[name]) is int and report[name]==wanted,'geometry/resource contract: '+name)
    limits=report['limits'];cpu=limits['cpu_max']
    require(limits['affinity']==[0,2] and 0<int(limits['memory_max_bytes'])<=6<<30 and len(cpu)==2 and
        0<int(cpu[0])<=2*int(cpu[1]) and int(cpu[1])>0 and len(limits['physical_cores'])==2 and
        len({tuple(x) for x in limits['physical_cores']})==2,'CPU/memory execution contract')
    names=['verilator-version','compiler-version','build','probe']+['test-segment'+str(i) for i in range(2 if aw==16 else 1)]
    require([s['name'] for s in report['steps']]==names,'exact stage order/coverage')
    for step in report['steps']:
        require(type(step['returncode']) is int and step['returncode']==0 and step['error'] is None,'unsuccessful command')
        require(type(step['seconds']) in (int,float) and math.isfinite(step['seconds']) and 0<=step['seconds']<=1801,'bounded duration')
    tools=report['tool_executable_sha256']
    require(len(tools)==3 and all(Path(p).is_absolute() and '..' not in Path(p).parts and
        re.fullmatch('[0-9a-f]{64}',h) for p,h in tools.items()),'recorded tool identities')
    require(isinstance(report['python_version'],str) and report['python_version'],'recorded Python version')
    scratch=PurePosixPath(report['scratch'])
    require(scratch.parent==PurePosixPath('/dev/shm') and scratch.name.startswith('gfn16-prefetch-r2-rowcompact-') and
            '..' not in scratch.parts and report['compiler_temporary_directory']==str(scratch/'tmp'),'isolated scratch identity')
    return {s['name']:s for s in report['steps']}


def commands(report,steps,order):
    scratch=report['scratch'];aw=report['aw']
    expected=['verilator','--cc','--exe','--build','-j','2','--threads','1','--top-module',TOP,
        f'-GAW={aw}','-GNTT_LANES=64','--Mdir',scratch+'/build',
        *[SNAPSHOT+'/'+name for name in order],SNAPSHOT+'/rtl/tb/'+BENCH+'_threaded.cpp']
    require(steps['build']['command']==expected,'native candidate compiler argv')
    require(steps['verilator-version']['command']==['verilator','--version'] and
            steps['compiler-version']['command']==['g++','--version'],'tool-version argv')
    remote=PurePosixPath(report['executable'])
    require(remote.is_absolute() and '..' not in remote.parts and remote.name=='V'+TOP and
        remote.parent.parent==PurePosixPath(SNAPSHOT).parent.parent,'durable candidate executable path')
    require(steps['probe']['command']==[str(remote),'--runtime-probe'],'candidate probe command')
    return remote


def generated_contract(generated,log,aw=None):
    top='V'+TOP
    require(all(top+x in generated for x in ('.cpp','.h','.mk')),'generated new-top closure')
    require(all('/' not in name and Path(name).suffix in ('.cpp','.h','.mk','.dat') for name in generated),'generated member types')
    require(re.search(r'unsigned\s+'+top+r'::threads\(\) const\s*\{\s*return 1;\s*\}',generated[top+'.cpp'].decode()),'generated model thread count')
    make=generated[top+'.mk'].decode();source=SNAPSHOT+'/rtl/tb/'+BENCH+'_threaded.cpp'
    require(source in make,'generated bench source rule')
    match=re.search(r'^VM_USER_CFLAGS = \\\n(.*?)(?=\n#|\Z)',make,re.M|re.S)
    require(match is not None and not shlex.split(match[1].replace('\\\n',' ')),'unexpected generated user compiler flags')
    if aw==16:
        require(any(b'compact row write address mismatch' in payload for name,payload in generated.items()
                    if name.endswith('.cpp')),'full-size generated compact-row shadow check missing')
    rows=[shlex.split(line) for line in log.splitlines() if source in line and ' -c ' in line]
    require(len(rows)==1 and source in rows[0],'actual new-bench compilation evidence')
    require(not any(t.startswith('-DCORE27_PREFETCH_R2_RUNTIME_THREADS') or t.startswith('-UCORE27_PREFETCH_R2_RUNTIME_THREADS')
                    for t in rows[0]),'unexpected runtime-thread override')


def verify(root,approved_manifest_sha):
    root=Path(root).resolve();normal=normal_helpers()
    manifest_path=normal.local_file(root,'approved-manifest.json')
    require(isinstance(approved_manifest_sha,str) and re.fullmatch('[0-9a-f]{64}',approved_manifest_sha) and
            sha(manifest_path)==approved_manifest_sha,'externally approved manifest hash')
    manifest=json.loads(manifest_path.read_text());report=json.loads(normal.local_file(root,'report.json').read_text())
    order=source_contract(report['sources'],normal)
    steps=metadata(report,manifest,approved_manifest_sha,order);remote=commands(report,steps,order)
    artifacts=report['artifacts'];aw=report['aw'];count=2 if aw==16 else 1
    wanted={'approved-manifest.json','sources.tar.gz','generated-sources.tar.gz','V'+TOP,f'vectors-aw{aw}.txt',
            *[name+'.log' for name in steps],*[f'segment{i}.txt' for i in range(count)]}
    require(set(artifacts)==wanted,'exact native artifact roles')
    for name,value in artifacts.items():require(sha(normal.local_file(root,name))==value,'artifact hash: '+name)
    for name,step in steps.items():require(step['log']==name+'.log' and artifacts[step['log']]==step['sha256'],'step log binding')
    members=normal.archive_members(root/'sources.tar.gz',report['sources']);source_delta(members)
    generated=normal.archive_members(root/'generated-sources.tar.gz',report['generated_source_sha256'])
    generated_contract(generated,(root/'build.log').read_text(),aw)
    require(sha(root/('V'+TOP))==report['executable_sha256'],'candidate binary identity')
    for step,key in (('verilator-version','tool_version'),('compiler-version','compiler_version')):
        require(report[key] and report[key]==(root/(step+'.log')).read_text().strip(),'tool version record')
    probe=json.loads((root/'probe.log').read_text())
    require(probe=={'context_threads':1,'model_threads':1,'expected_threads':1} and
        all(type(value) is int for value in probe.values()),'runtime model/context probe')
    coverage=vector_coverage(root,report,steps,remote,normal)
    return dict(status='verified_normal_profile',scope='Native grouped compact-row orient8 whole-core normal profile only',aw=aw,n=1<<aw,
        **coverage,compact_row_shadow_source_verified=True,
        full_size_generated_shadow_message_present=aw==16,native_inflight_reset_qualified=False,
        reset_coverage_limit='Frozen ABORT ntt reaches initial seed/setup; it does not prove BF/MUL in-flight tag cancellation.',
        artifacts=len(artifacts),source_members=len(members),compiled_kernels=16,generated_members=len(generated),
        report_sha256=sha(root/'report.json'),manifest_sha256=approved_manifest_sha,runner_sha256=RUNNER_SHA,
        verifier_sha256=sha(__file__),integer_audit_sha256=NORMAL_SHA,radix_helper_sha256=INTEGER_SHA,
        executable_sha256=report['executable_sha256'],source_archive_sha256=sha(root/'sources.tar.gz'),
        limitation='Only this normal AW profile; no in-flight BF/MUL reset or new integration mutation qualification, fit/clock/board or full PRP claim. No binary executed. Expected vectors freshly checked by ordinary-integer arithmetic; NOREAD intermediate states validated by their later readback. Tool binary identities and prepared-tar hash remain provenance records, not offline reexecution/remote attestation.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('root',type=Path)
    parser.add_argument('--manifest-sha',required=True);args=parser.parse_args()
    print(json.dumps(verify(args.root,args.manifest_sha),indent=2))
