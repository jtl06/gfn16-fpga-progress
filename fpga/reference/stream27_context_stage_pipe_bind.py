"""Private zero-edge shared GEN transport; original stage authority unchanged."""
from copy import deepcopy
import hashlib,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SELF='reference/stream27_context_stage_pipe_bind.py'
LEAF='rtl/kernel/genefer_stream27_stage_owner_pipe_compact_v1.sv'
MODULE='genefer_stream27_stage_owner_pipe_compact_v1'
DECL='logic [5:0] slot_pipe,start_pipe;logic [GEN_W-1:0] generation_pipe[0:5];'
NEWDECL='logic [5:0] slot_pipe,start_pipe;wire [GEN_W-1:0] delayed_generation;'
ADVANCE='  wire accept=row_slot && !stop && !local_error;\n'
INSTANCE='''  genefer_stream27_stage_owner_pipe_compact_v1 #(.GEN_W(GEN_W),.PIPE_WORDS(6),.FRAME_T(FRAME_T)) owner_pipe
   (.clk,.rst_n,.advance(!stop),.in_slot_valid(accept),.frame_start(row_start),
    .generation_in(row_generation),.generation_out(delayed_generation));
'''
SHIFT='''     generation_pipe[0]<=row_generation;
     for(int k=1;k<6;k=k+1)generation_pipe[k]<=generation_pipe[k-1];
'''
def sha(raw):return hashlib.sha256(raw).hexdigest()
def bind(bundle,enabled=0):
    assert type(enabled) is int and enabled in (0,1)
    b=deepcopy(bundle)
    if not enabled:return b
    assert b['parameters'].get('CONTEXTS')==2
    names=[n for n in b['files'] if re.fullmatch(r'genefer_stream28_merged_(?:ct|gs)_aw\d+_p16_f[012]_v1_shared_comm_mlab_v1\.sv',n)]
    assert len(names) in (2,6)
    geometries=[re.search(r'localparam int STAGES=(\d+),FRAME_T=(\d+),PAIRS=8;',b['files'][n]).groups() for n in names]
    assert len(set(geometries))==1
    stages,frame_t=map(int,geometries[0])
    # Strongest small-geometry proof: the entire bundle stays byte/default exact.
    if frame_t<6:return b
    old_files=deepcopy(b['files']);old_pins=deepcopy(b.get('generated_sha256',{}))
    for n in names:
        s=b['files'][n]
        assert s.count(DECL)==s.count(ADVANCE)==s.count(SHIFT)==s.count('generation_pipe[5]')==stages
        t=s.replace(DECL,NEWDECL).replace(ADVANCE,ADVANCE+INSTANCE).replace(SHIFT,'').replace('generation_pipe[5]','delayed_generation')
        # Literal reverse covers cadence/slot/start/error/owner/accept/data too.
        reverse=t.replace(NEWDECL,DECL).replace(INSTANCE,'').replace('delayed_generation','generation_pipe[5]')
        needle='     slot_pipe<={slot_pipe[4:0],accept};start_pipe<={start_pipe[4:0],accept && row_start};\n'
        assert reverse.count(needle)==stages
        reverse=reverse.replace(needle,needle+SHIFT)
        assert reverse==s
        b['files'][n]=t
    b['files'][MODULE+'.sv']=(ROOT/LEAF).read_text()
    b['rtl_sources']=[n for n in b['files'] if n.endswith('.sv')]
    b['generated_sha256']={n:sha(s.encode()) for n,s in b['files'].items()}
    deps=list(b.get('source_dependencies',[]))
    for n in (SELF,LEAF):
        if n not in deps:deps.append(n)
    b['source_dependencies']=deps;b['source_sha256']={n:sha((ROOT/n).read_bytes()) for n in deps}
    b['stage_owner_pipe_compact']=dict(enabled=True,changed=names,frame_t=frame_t,pipe_words=6,added_edges=0,
      owner_bits=25,full_owner_records=2,private_color_words=6,parent_generated_sha256=old_pins,
      cadence_and_fault_authority='literal unchanged',invalid_generation_is_authority=False)
    assert b['parameters']==bundle['parameters'] and b['geometry']==bundle['geometry']
    assert all(b['files'][n]==s for n,s in old_files.items() if n not in names)
    return b
