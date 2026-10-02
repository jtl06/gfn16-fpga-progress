"""Additive v4 source successor for the v3 native UNOPTFLAT failure.

Arithmetic, events and edge calendars are unchanged. Only the protocol's
process-level dependency partition changes; native elaboration remains a gate.
The frozen v3 sources, snapshots and failed report are retained.
"""
import hashlib
from pathlib import Path
import re

from .stream27_field_square_warm_v3_compile import prepare as parent_bundle
from .stream27_field_square_warm_v3_compile import replay_small_overlap

TOP='genefer_stream27_field_square_aw5_warm_v4'
PROTOCOL='rtl/kernel/genefer_stream27_epoch_protocol_v4.sv'
PARENT_COMPILER_SHA='4214b28ef30be215311f64abf5e5d3fa0f3bdc3d3471c736a2d7810403868c79'
PARENT_PROTOCOL_SHA='bd2d94fcc95b20f0e3fff7a612e512df45c386273ba63533a5e4ad0153ad64a8'


def _without_comments(source):
    return re.sub(r'//[^\n]*|/\*.*?\*/','',source,flags=re.S)


def comb_blocks(source):
    """Read conservative procedural cones, not an HDL parser or native lint.

    Entire always_comb processes are dependency units, matching the missed v3
    hazard. This bounded checker extracts begin/end-balanced blocks in these
    exact sources. Native warning-fatal elaboration must still confirm them.
    """
    source=_without_comments(source);blocks=[]
    for match in re.finditer(r'\balways_comb\s+begin\b',source):
        depth=1;end=None
        for token in re.finditer(r'\bbegin\b|\bend\b',source[match.end():]):
            depth+=1 if token.group()=='begin' else -1
            if depth==0:
                end=match.end()+token.end();break
        if end is None:raise ValueError('WARM_COMB_UNBALANCED')
        blocks.append(source[match.start():end])
    return tuple(blocks)


def dependency_contract(protocol_source,wrapper_source):
    """Fail closed if any whole lookup process reads a returned fault cone."""
    blocks=comb_blocks(protocol_source)
    metadata=('correction_base','pointwise_epoch','sink_epoch')
    forbidden=('external_fault_pending','quarantine','stop','out_error','bad',
               'fault_pending','correction_accept','pointwise_accept','commit_enable')
    metadata_blocks=[]
    for name in metadata:
        writers=[block for block in blocks if re.search(r'\b'+name+r'\s*=',block)]
        if len(writers)!=1:raise ValueError('WARM_METADATA_WRITER: '+name)
        for signal in forbidden:
            if re.search(r'\b'+signal+r'\b',writers[0]):
                raise ValueError('WARM_LOOKUP_FAULT_DEPENDENCY: '+name+' <- '+signal)
        metadata_blocks.append(writers[0])
    if len(set(metadata_blocks))!=1:raise ValueError('WARM_LOOKUP_METADATA_PARTITION')
    if len(blocks)!=2:raise ValueError('WARM_PROTOCOL_COMB_PARTITION')
    bad_blocks=[block for block in blocks if re.search(r'\bbad\s*=',block)]
    if len(bad_blocks)!=1 or bad_blocks[0]==metadata_blocks[0]:
        raise ValueError('WARM_CHECK_METADATA_PARTITION')
    wrapper_blocks=comb_blocks(wrapper_source)
    digit=[block for block in wrapper_blocks if re.search(r'\bdigit_admission_bad\s*=',block)]
    if len(digit)!=1:raise ValueError('WARM_DIGIT_WRITER')
    for signal in ('epoch_correction_base','admission_bad','epoch_pending',
                   'fault_pending','accepted','accepted_start','frame_accept'):
        if re.search(r'\b'+signal+r'\b',digit[0]):raise ValueError('WARM_CANDIDATE_FEEDBACK: '+signal)
    if 'wire raw_frame_begin=in_slot_valid && frame_start && !stop && !digit_admission_bad;' not in wrapper_source:
        raise ValueError('WARM_RAW_FRAME_CANDIDATE')
    return dict(status='passed_bounded_source_partition_not_native_lint',
                lookup_processes=1,validation_processes=1,
                metadata_outputs=list(metadata),forbidden_lookup_inputs=list(forbidden),
                candidate='raw digit-only frame_begin; independent of correction validation',
                return_path='lookup -> wrapper range/join checks -> external fault -> accept gates only',
                added_edges=0,same_edge_fault_quarantine=True)


def prepare():
    root=Path(__file__).resolve().parents[1]
    parent=parent_bundle();files=dict(parent['files']);old_top=parent['top']
    if parent['source_sha256']['reference/stream27_field_square_warm_v3_compile.py']!=PARENT_COMPILER_SHA:
        raise ValueError('WARM_V3_FROZEN_COMPILER_DRIFT')
    if parent['source_sha256']['rtl/kernel/genefer_stream27_epoch_protocol_v3.sv']!=PARENT_PROTOCOL_SHA:
        raise ValueError('WARM_V3_FROZEN_PROTOCOL_DRIFT')
    source=files.pop(old_top+'.sv')
    if source.count('module '+old_top+' (')!=1 or source.count('genefer_stream27_epoch_protocol_v3 #(')!=1:
        raise ValueError('WARM_V4_SOURCE_ANCHORS')
    source=source.replace('module '+old_top+' (','module '+TOP+' (').replace(
        'genefer_stream27_epoch_protocol_v3 #(','genefer_stream27_epoch_protocol_v4 #(')
    files[TOP+'.sv']=source
    dependencies=list(parent['source_dependencies'])+[
        'reference/stream27_field_square_warm_v4_compile.py',PROTOCOL]
    rtl_sources=[p for p in parent['rtl_sources'] if p not in
                 (old_top+'.sv','rtl/kernel/genefer_stream27_epoch_protocol_v3.sv')]
    rtl_sources += [PROTOCOL,TOP+'.sv']
    checks=dependency_contract((root/PROTOCOL).read_text(),source)
    return dict(parent,files=files,source_dependencies=dependencies,rtl_sources=rtl_sources,top=TOP,
                source_sha256={p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in dependencies},
                generated_sha256={p:hashlib.sha256(s.encode()).hexdigest() for p,s in files.items()},
                parent_top=old_top,dependency_contract=checks,
                failure_report_sha256='58f32401e8bb81bc2b55084757e6a1e3a89edaff36a635a38fb56cc9d91a9838',
                repair_scope='process partition only; unchanged arithmetic/reset/calendar; native elaboration pending')
