"""Private per-stage E5/E6 GEN transport; byte-exact reverse of all authority."""
from copy import deepcopy
import hashlib,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SELF='reference/stream27_context_stage_pipe_bind_v2.py'
LEAF='rtl/kernel/genefer_stream27_stage_owner_pipe_compact_v2.sv'
MODULE='genefer_stream27_stage_owner_pipe_compact_v2'
ADVANCE='  wire accept=row_slot && !stop && !local_error;\n'
def sha(raw):return hashlib.sha256(raw).hexdigest()
def stage(text,frame_t):
    match=re.search(r'logic \[([56]):0\] slot_pipe,start_pipe;logic \[GEN_W-1:0\] generation_pipe\[0:([56])\];',text)
    assert match and match[1]==match[2]
    last=int(match[1]);depth=last+1
    assert text.count('generation_pipe[0]<=row_generation;')==1
    assert text.count(ADVANCE)==1 and text.count('generation_pipe['+str(last)+']')==1
    if frame_t<depth:return text,depth,False
    declaration=match[0];newdecl=f'logic [{last}:0] slot_pipe,start_pipe;wire [GEN_W-1:0] delayed_generation;'
    instance=f'''  {MODULE} #(.GEN_W(GEN_W),.PIPE_WORDS({depth}),.FRAME_T(FRAME_T)) owner_pipe
   (.clk,.rst_n,.advance(!stop),.in_slot_valid(accept),.frame_start(row_start),
    .generation_in(row_generation),.generation_out(delayed_generation));
'''
    shift=f'''     generation_pipe[0]<=row_generation;
     for(int k=1;k<{depth};k=k+1)generation_pipe[k]<=generation_pipe[k-1];
'''
    assert text.count(shift)==1
    out=text.replace(declaration,newdecl).replace(ADVANCE,ADVANCE+instance).replace(shift,'').replace(f'generation_pipe[{last}]','delayed_generation')
    reverse=out.replace(newdecl,declaration).replace(instance,'').replace('delayed_generation',f'generation_pipe[{last}]')
    needle=f'     slot_pipe<={{slot_pipe[{last-1}:0],accept}};start_pipe<={{start_pipe[{last-1}:0],accept && row_start}};\n'
    assert reverse.count(needle)==1
    assert reverse.replace(needle,needle+shift)==text
    return out,depth,True
def bind(bundle,enabled=0):
    assert type(enabled) is int and enabled in (0,1)
    b=deepcopy(bundle)
    if not enabled:return b
    assert b['parameters'].get('CONTEXTS')==2
    names=[n for n in b['files'] if re.fullmatch(r'genefer_stream28_merged_(?:ct|gs)_aw\d+_p16_f[012]_v1_shared_comm_mlab_v1(?:_c2_inputreg_v1)?\.sv',n)]
    assert len(names) in (2,6)
    counts={6:0,7:0};changed=[];fallbacks={6:0,7:0}
    for n in names:
        original=b['files'][n]
        match=re.search(r'localparam int STAGES=(\d+),FRAME_T=(\d+),PAIRS=8;',original)
        assert match;stages,frame_t=map(int,match.groups())
        parts=re.split(r'(?= if\(1\)begin: stage\d+\n)',original)
        assert len(parts)==stages+1
        pieces=[parts[0]];depths=[];mutated=False
        for i,piece in enumerate(parts[1:]):
            assert piece.startswith(f' if(1)begin: stage{i}\n')
            new,depth,applied=stage(piece,frame_t)
            pieces.append(new);depths.append(depth);counts[depth]+=1
            if not applied:fallbacks[depth]+=1
            mutated|=applied
        expected=[6]*stages
        if n.endswith('_c2_inputreg_v1.sv'):expected[-1]=7
        assert depths==expected,'Never omit or mis-time final GS stage'
        if mutated:b['files'][n]=''.join(pieces);changed.append(n)
    if not changed:return b
    b['files'][MODULE+'.sv']=(ROOT/LEAF).read_text()
    b['rtl_sources']=[n for n in b['files'] if n.endswith('.sv')]
    b['generated_sha256']={n:sha(s.encode()) for n,s in b['files'].items()}
    deps=list(b.get('source_dependencies',[]));pins=deepcopy(b.get('source_sha256',{}))
    for n in (SELF,LEAF):
        if n not in deps:deps.append(n)
        pins[n]=sha((ROOT/n).read_bytes())
    b['source_dependencies']=deps;b['source_sha256']=pins
    b['stage_owner_pipe_compact_v2']=dict(changed=changed,depth_counts=counts,literal_fallback_counts=fallbacks,
      added_edges=0,owner_records_per_stage=2,parent_generated_sha256=bundle['generated_sha256'],
      invalid_generation_is_authority=False,authority_reverse='literal exact')
    assert b['parameters']==bundle['parameters'] and b['geometry']==bundle['geometry']
    assert all(b['files'][n]==s for n,s in bundle['files'].items() if n not in changed)
    return b
