"""Static branch/ABI/source checks. Native flags-off equivalence is separate."""
import hashlib,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
TRUNK='rtl/kernel/genefer_track_a_trunk_v1.sv'
PARENT='rtl/kernel/genefer_square_core27_stream_prefetch_r2_host_broadcast_orient8_rootfused_crtmont_prefill_pipe_v1.sv'
PARENT_SHA='704f7fed433d724dbc8e56c7b725824ec36cce78d6ce8f021307837d2a96b8e7'
PULSE_PORTS=('clk rst_n load_we read_en start host_addr write_data base double_bit '
 'read_valid read_data busy done error cycles conversion_cycles root_cycles ntt_cycles '
 'crt_cycles carry_cycles carry_passes profile_cache_valid profile_loads profile_hits '
 'profile_words_loaded seed_setup_cycles').split()

def branch(blockcarry=False,merged=False,lookahead=False):
    if any(type(x) is not bool for x in (blockcarry,merged,lookahead)):raise ValueError('boolean flags only')
    if lookahead:raise ValueError('A_TRUNK_LOOKAHEAD_BRANCH_NOT_PORTED')
    if merged and not blockcarry:raise ValueError('A_TRUNK_MERGED_REQUIRES_BLOCK_ABI')
    return dict(child='genefer_anext_core_v1' if merged else 'genefer_track_a4_core_v4' if blockcarry else Path(PARENT).stem,
                host_abi='command_ready_response_valid' if blockcarry else 'T5b_pulse_load_read_start',
                inherited_parent_cycle_equivalence=not blockcarry,wrapper_registers=0,
                native_flags_off_validated=False)

def verify(text=None):
    raw=(ROOT/PARENT).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=PARENT_SHA:raise ValueError('promoted parent drift')
    text=(ROOT/TRUNK).read_text() if text is None else text
    baseline=text.split('generate if(!USE_BLOCKCARRY)begin: baseline',1)[1].split('end else begin: command_host',1)[0]
    m=re.search(r'#\(\.AW\(AW\),\.NTT_LANES\(NTT_LANES\)\) dut \((.*?)\);',baseline,re.S)
    if not m:raise ValueError('direct baseline instance missing')
    ports=[p.strip() for p in m[1].split(',')]
    if ports!=['.'+p for p in PULSE_PORTS]:raise ValueError('baseline port identity changed')
    if re.search(r'\balways(?:_ff|_comb|_latch)?\b',text):raise ValueError('wrapper must not insert state or dynamic routing')
    if text.count(Path(PARENT).stem)!=1:raise ValueError('unique unchanged parent instance')
    for token in ('A_TRUNK_LOOKAHEAD_BRANCH_NOT_PORTED','A_TRUNK_MERGED_REQUIRES_BLOCK_ABI','A_TRUNK_BLOCK_LANES64_REQUIRED'):
        if text.count(token)!=1:raise ValueError('unsupported branch guard missing')
    return dict(status='PASS_source_contract_only',supported_flags=['000','100','110'],
                pulse_ports=PULSE_PORTS,parent_sha256=PARENT_SHA,wrapper_registers=0,
                native_flags_off_validated=False,promotion_allowed=False)
