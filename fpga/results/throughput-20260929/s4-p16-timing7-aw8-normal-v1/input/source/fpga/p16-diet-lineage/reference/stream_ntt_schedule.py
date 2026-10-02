"""Track S1 literal radix-2 MDC ordering/storage model, NOT RTL qualification.

Garrido2013 Fig3/4/5 and eq4: strided parallel input, P/2 BF/stage,
P FIFO buffers at each temporal shuffle. No radix2^k complex-rotation savings
are assumed for a modular NTT. Natural carry I/O requires adapters.
Only the token/port schedule and standalone transform arithmetic are modeled;
carry II, complete recurrence initialization and full dependent-square timing
are not qualified. Existing stream_ntt_model.py remains unchanged.
"""
from collections import deque
from dataclasses import dataclass
from math import ceil
import json
import hashlib
from pathlib import Path

from .stream_ntt_model import geometry, bit_reverse, FIELDS, ModelMismatch


SOURCES = {
    'garrido2013': 'https://liu.diva-portal.org/smash/get/diva2%3A602884/FULLTEXT01.pdf',
    'mitre2014': 'https://www.mitre.org/sites/default/files/publications/parallel-extensions-fft-13-3317.pdf',
    'he1996': 'https://lup.lub.lu.se/search/publication/07e09b27-06af-489d-9230-eec81f625e2d',
    'arria10_memory': 'https://www.intel.com/programmable/technical-pdfs/683461.pdf',
}
# Arria10 handbook table8 simple-dual-port; no arbitrary bit-budget packing.
SDP_CONFIGS = ((16384,1),(8192,2),(4096,4),(4096,5),(2048,8),
               (2048,10),(1024,16),(1024,20),(512,32),(512,40))


def dimensions(n, parallel):
    aw = geometry(n)
    if type(parallel) is not int or parallel < 2 or parallel > n or parallel & (parallel-1):
        raise ValueError('power-of-two parallelism2..N required')
    return aw, parallel.bit_length()-1, n//parallel


def index_of(cycle, lane, lane_bits, time_bits):
    return sum(((lane >> j)&1) << b for j,b in enumerate(lane_bits)) + sum(
        ((cycle >> j)&1) << b for j,b in enumerate(time_bits))


@dataclass(frozen=True)
class Token:
    index: int
    value: int | None = None


def commutator(frames, lane_position, depth, *, wrong_phase=False):
    """Fig4 twoL-FIFO cell for each pair of lanes separated at lane_position.

    Every physical FIFO has exactly one read and one write per tick; read-old
    before write is assumed. Each cell delays its output by L ticks while
    interchanging the lane bit with time bit log2L. No hidden frame store.
    RAM/register read latency beyond this ideal FIFO is a separate RTL issue.
    """
    width = len(frames[0]); count = len(frames)
    if depth < 1 or depth & (depth-1) or count % (2*depth):
        raise ValueError('shuffle depth must divide frame in2L groups')
    pairs = [(lane, lane^(1<<lane_position)) for lane in range(width)
             if not lane & (1<<lane_position)]
    queues = [(deque([None]*depth), deque([None]*depth)) for _ in pairs]
    output = []
    for tick in range(count+depth):
        incoming = frames[tick] if tick < count else [None]*width
        result = [None]*width
        phase = ((tick//depth)&1) ^ bool(wrong_phase)
        for (upper,lower),(upper_q,lower_q) in zip(pairs,queues):
            delayed_upper = upper_q.popleft(); delayed_lower = lower_q.popleft()
            upper_q.append(delayed_lower if phase else incoming[upper])
            lower_q.append(incoming[lower])
            result[upper] = delayed_upper
            result[lower] = incoming[upper] if phase else delayed_lower
        if tick >= depth:
            if any(token is None for token in result):
                raise ModelMismatch('commutator-valid', 'missing token in frame')
            output.append(result)
    return output


def _wire_reorder(frames, old_bits, new_bits):
    position = {b:j for j,b in enumerate(old_bits)}
    return [[frame[sum(((lane>>j)&1)<<position[b] for j,b in enumerate(new_bits))]
             for lane in range(len(frame))] for frame in frames]


def _period(values):
    period = 1
    while period < len(values):
        if all(value == values[i%period] for i,value in enumerate(values)):
            return period
        period *= 2
    return len(values)


def transform(n, parallel, *, inverse=False, values=None, field=0,
              butterfly_edges=5, wrong_shuffle_stage=None):
    """Actual ordered tokens and modular radix2 butterflies for one frame.

    DIF input: index=bit_reverse(lane,log2P)*(N/P)+cycle.
    DIF output slot: cycle*P+lane; natural frequency=bit_reverse(slot,AW).
    DIT reverses this: contiguous bit-reversed slots in, strided natural digits
    out. Square can connect DIF to DIT without a spectral reorder buffer.
    Uniform BF latency is accounted separately from literal FIFO ticks.
    """
    aw,p,t = dimensions(n,parallel)
    if type(butterfly_edges) is not int or butterfly_edges < 0:
        raise ValueError('explicit nonnegative butterfly edge latency')
    if values is not None and len(values) != n:
        raise ValueError('frame length')
    if field not in (0,1,2):
        raise ValueError('field0..2')
    modulus,generator = FIELDS[field]
    omega = pow(generator,(modulus-1)//n,modulus)
    if inverse: omega = pow(omega,-1,modulus)
    lane_bits = list(range(p)) if inverse else list(range(aw-1,aw-p-1,-1))
    time_bits = list(range(p,aw)) if inverse else list(range(aw-p))
    frames = [[Token(index_of(c,l,lane_bits,time_bits),
                     None if values is None else values[index_of(c,l,lane_bits,time_bits)]%modulus)
               for l in range(parallel)] for c in range(t)]
    stages=[]; shuffle_latency=0
    for number,bit in enumerate(range(aw) if inverse else range(aw-1,-1,-1)):
        depth=0; old_lane_bit=None
        if bit not in lane_bits:
            position=time_bits.index(bit); depth=1<<position
            old_lane_bit=min(lane_bits) if inverse else max(lane_bits)
            lane_position=lane_bits.index(old_lane_bit)
            frames=commutator(frames,lane_position,depth,wrong_phase=number==wrong_shuffle_stage)
            lane_bits[lane_position],time_bits[position]=bit,old_lane_bit
            shuffle_latency+=depth
        position=lane_bits.index(bit)
        pairs=[(l,l^(1<<position)) for l in range(parallel) if not l&(1<<position)]
        root_traces=[[] for _ in pairs]
        for cycle,frame in enumerate(frames):
            for lane,token in enumerate(frame):
                expected=index_of(cycle,lane,lane_bits,time_bits)
                if token.index != expected:
                    raise ModelMismatch('stage-token-order', f'stage{number} cycle{cycle} lane{lane}')
            for port,(lower,upper) in enumerate(pairs):
                a,b=frame[lower],frame[upper]
                if a.index^(1<<bit) != b.index:
                    raise ModelMismatch('butterfly-pair',f'stage{number}')
                exponent=(a.index & ((1<<bit)-1))*(n>>(bit+1))
                root_traces[port].append(exponent)
                if a.value is not None:
                    weight=pow(omega,exponent,modulus)
                    if inverse:
                        product=b.value*weight%modulus
                        av,bv=(a.value+product)%modulus,(a.value-product)%modulus
                    else:
                        av,bv=(a.value+b.value)%modulus,(a.value-b.value)*weight%modulus
                    frame[lower],frame[upper]=Token(a.index,av),Token(b.index,bv)
        unique={tuple(trace) for trace in root_traces}
        rom_streams=[]
        for trace in sorted(unique):
            period=_period(trace)
            if len(set(trace)) == 1:
                rom_streams.append(dict(period=1,constant_exponent=trace[0],stored_words=0))
            else:
                rom_streams.append(dict(period=period,constant_exponent=None,stored_words=period))
        stages.append(dict(stage=number,target_index_bit=bit,parallel_butterflies=parallel//2,
            lane_bits=list(lane_bits),time_bits=list(time_bits),commutator_replaced_lane_bit=old_lane_bit,
            shuffle_depth_per_buffer=depth,shuffle_buffer_count=parallel if depth else 0,
            shuffle_words=parallel*depth,shuffle_latency=depth,
            max_reads_per_fifo_per_tick=1 if depth else 0,max_writes_per_fifo_per_tick=1 if depth else 0,
            root_read_consumers_per_tick=parallel//2,unique_root_streams=rom_streams,
            butterfly_edges=butterfly_edges))
    final_bits=list(range(aw-1,aw-p-1,-1)) if inverse else list(range(p))
    frames=_wire_reorder(frames,lane_bits,final_bits)
    expected=[[(bit_reverse(l,p)*t+c) if inverse else c*parallel+l
                for l in range(parallel)] for c in range(t)]
    if [[token.index for token in frame] for frame in frames] != expected:
        raise ModelMismatch('terminal-order','unexpected stream mapping')
    output=None
    if values is not None:
        output=[0]*n
        for frame in frames:
            for token in frame: output[token.index]=token.value
        if inverse: output=[v*pow(n,-1,modulus)%modulus for v in output]
    return dict(n=n,parallel=parallel,frame_ticks=t,direction='DIT' if inverse else 'DIF',
        stages=stages,output_values=output,
        output_indices=expected,core_delay_words=sum(s['shuffle_words'] for s in stages),
        fifo_first_output_latency=shuffle_latency,
        modeled_first_output_latency=shuffle_latency+aw*butterfly_edges,
        status='literal_token_and_standalone_radix2_model_not_RTL')


def m20k(depth,width):
    """Discrete legal SDP rectangle tiling; one read+one write port, no inference claim."""
    if type(depth) is not int or type(width) is not int or depth<1 or width<1:
        raise ValueError('positive integer RAM shape')
    return min(ceil(depth/d)*ceil(width/w) for d,w in SDP_CONFIGS)


def wrap2_recurrence(n, parallel, c1, field=0, *, multiplier_edges=3,
                     contexts=4, wrong_step=False):
    """Answers-r2 correction generator: P DSPs/field, seed+update SAME pipes.

    s=lane+P*m, frequency=bit_reverse(s,AW). Registered multiplier output
    after edge k+3 cannot feed a new accepted operation until edge k+4.
    Four contexts therefore advance m->m+4, using trailing_ones(m//4)
    rather than naively using the one-step table. Each tick executes exactly
    one multiplication per lane, including the first4 seed batches.
    Constants need Montgomery scaling in RTL; arithmetic here is ordinary mod.
    """
    aw,p,t=dimensions(n,parallel)
    if field not in (0,1,2) or type(c1) is not int:
        raise ValueError('integer correction and field0..2 required')
    if type(multiplier_edges) is not int or multiplier_edges<0:
        raise ValueError('nonnegative registered multiplier latency')
    if type(contexts) is not int or contexts<1 or contexts&(contexts-1):
        raise ValueError('power-of-two recurrence contexts')
    prime,generator=FIELDS[field];psi=pow(generator,(prime-1)//(2*n),prime);omega=psi*psi%prime
    outputs={};ready={};multiplications=0;table={}
    for tick in range(t):
        row=[]
        if tick >= contexts and contexts <= multiplier_edges:
            raise ModelMismatch('recurrence-feedback', 'registered product unavailable before same-edge reuse')
        if tick>=contexts:
            group=tick//contexts-1;trailing=0
            while group&1:trailing+=1;group>>=1
            exponent=(bit_reverse(tick,aw-p)-bit_reverse(tick-contexts,aw-p))%n
            if trailing in table and table[trailing]!=exponent:
                raise ModelMismatch('recurrence-step-table','delta not trailing-ones dependent')
            table[trailing]=exponent
            factor=pow(omega,exponent,prime)
            if wrong_step and trailing==0:factor=(factor+1)%prime
        for lane in range(parallel):
            if tick<contexts:
                value=(c1%prime)*psi*pow(omega,bit_reverse(lane+parallel*tick,aw),prime)%prime
            else:
                prior=tick-contexts
                if ready[prior]>=tick:
                    raise ModelMismatch('recurrence-feedback','consumer reused not-yet-visible product')
                value=outputs[prior][lane]*factor%prime
            row.append(value);multiplications+=1
        outputs[tick]=row;ready[tick]=tick+multiplier_edges
    for cycle,row in outputs.items():
        for lane,value in enumerate(row):
            expected=(c1%prime)*psi*pow(omega,bit_reverse(lane+parallel*cycle,aw),prime)%prime
            if value!=expected:raise ModelMismatch('wrap2-generator',f'cycle{cycle},lane{lane}')
    batches=min(contexts,t)
    return dict(status='exact_arithmetic_and_registered_dependency_model_not_RTL',
        multipliers_per_field=parallel,contexts_per_lane=contexts,
        seed_batches=batches,seed_multiplier_operations=parallel*batches,
        total_multiplier_operations=multiplications,first_weight_after_first_issue=multiplier_edges,
        all_seed_contexts_ready_after_first_issue=batches-1+multiplier_edges,
        conservative_initialization_barrier_ticks=batches-1+multiplier_edges,
        steady_weight_vectors_per_tick=1,update_step_table_by_trailing_ones=table,
        output_weights=[outputs[m] for m in range(t)],
        note='Charge first seed issue after c1/split readiness; no extra twiddle-generation DSP is required for this proved4-context recurrence.')


def adapter(n, parallel, *, to_strided=True, frames=3):
    """Literal natural<->MDC token converter with checked oneR/oneW banking.

    bank=(high_chunk XOR low_index_bits); address=frame%2*T+index//P.
    Two full-frame pages are a conservative implementable storage assignment,
    NOT Garrido's N-N/P sufficient input-reordering circuit. A single-page alias
    is refused by the token lifecycle check. Writes and reads at a tick use
    distinct ports; zero extra RAM register delay is an explicit lower bound.
    """
    _,p,t=dimensions(n,parallel)
    if type(frames) is not int or not 1 <= frames <= 16:
        raise ValueError('bounded frame count1..16')
    if n == parallel:
        permutation=[bit_reverse(l,p) for l in range(parallel)]
        if sorted(permutation)!=list(range(parallel)):
            raise ModelMismatch('adapter-wire','lane permutation is not bijective')
        return dict(direction='natural_to_strided' if to_strided else 'strided_to_natural',
            first_output_latency_lower_bound=0,peak_live_words_read_after_write=0,
            allocated_words_conservative=0,physical_banks=0,depth_per_bank=0,
            max_reads_per_bank_per_tick=0,max_writes_per_bank_per_tick=0,
            same_tick_input_forwarding_assumed=False,registered_RAM_latency_not_modeled=False,
            paper_input_reorder_sufficient_words=n-t,paper_reorder_circuit_not_implemented=True,
            frames_checked=frames,status='zero_memory_fixed_lane_bit_reversal',
            lane_permutation=permutation)
    def natural(c,l):return c*parallel+l
    def strided(c,l):return bit_reverse(l,p)*t+c
    source,target=(natural,strided) if to_strided else (strided,natural)
    latency=max(
        (index//parallel if to_strided else index%t) -
        (index%t if to_strided else index//parallel) for index in range(n))
    memory={}; peak=0; deliveries=0
    for tick in range(frames*t+latency):
        write_banks=[]; read_banks=[]
        if tick<frames*t:
            frame,cycle=divmod(tick,t)
            for lane in range(parallel):
                index=source(cycle,lane);bank=(index//t)^(index%parallel)
                address=(frame%2)*t+index//parallel;slot=(bank,address)
                if slot in memory:raise ModelMismatch('adapter-overwrite','live token aliased')
                memory[slot]=(frame,index);write_banks.append(bank)
        peak=max(peak,len(memory))
        out=tick-latency
        if 0<=out<frames*t:
            frame,cycle=divmod(out,t)
            for lane in range(parallel):
                index=target(cycle,lane);bank=(index//t)^(index%parallel)
                slot=(bank,(frame%2)*t+index//parallel)
                if memory.pop(slot,None)!=(frame,index):
                    raise ModelMismatch('adapter-order','missing/wrong frame token')
                deliveries+=1;read_banks.append(bank)
        if len(set(write_banks))!=len(write_banks) or len(set(read_banks))!=len(read_banks):
            raise ModelMismatch('adapter-port','more than one access of a type per bank')
    if memory or deliveries!=frames*n:raise ModelMismatch('adapter-drain','lost tokens')
    return dict(direction='natural_to_strided' if to_strided else 'strided_to_natural',
        first_output_latency_lower_bound=latency,peak_live_words_read_after_write=peak,
        allocated_words_conservative=2*n,physical_banks=parallel,depth_per_bank=2*t,
        max_reads_per_bank_per_tick=1,max_writes_per_bank_per_tick=1,
        same_tick_input_forwarding_assumed=True,registered_RAM_latency_not_modeled=True,
        paper_input_reorder_sufficient_words=n-t,paper_reorder_circuit_not_implemented=True,
        frames_checked=frames,status='literal_token_port_model_not_registered_RAM_RTL')


def resource_and_interval(n=65536, parallel=8, *, butterfly_edges=5,
                          multiplier_edges=3, crt_edges=16, carry_first_edges=1):
    """Explicit conservative modeled scenario, not a measured complete square.

    Carry is an optimistic declared II=P-points/tick service with unresolved
    divide/prefix/commit implementation. Exact carry includes one whole-frame
    boundary barrier. wrap2 provisional digits omit it; correction readiness
    includes a separately declared3-edge split. Adapter fusion not credited.
    """
    aw,p,t=dimensions(n,parallel)
    for label,value in (('multiplier_edges',multiplier_edges),('crt_edges',crt_edges),
                        ('carry_first_edges',carry_first_edges)):
        if type(value) is not int or value < 0:
            raise ValueError('explicit nonnegative '+label)
    fwd=transform(n,parallel,butterfly_edges=butterfly_edges)
    inv=transform(n,parallel,inverse=True,butterfly_edges=butterfly_edges)
    incoming=adapter(n,parallel); outgoing=adapter(n,parallel,to_strided=False)
    all_stages=fwd['stages']+inv['stages']
    # Coalesce same-depth FIFOs at a stage: all share circular pointers, unlike
    # adapter banks which require independently addressed reads/writes.
    delay_m20k=3*sum(m20k(s['shuffle_depth_per_buffer'],parallel*27)
                     for s in all_stages if s['shuffle_buffer_count'] and s['shuffle_depth_per_buffer']>32)
    delay_mlab=3*sum(ceil(parallel*27/20) for s in all_stages
                    if s['shuffle_buffer_count'] and s['shuffle_depth_per_buffer']<=32)
    root_rom_m20k=3*sum(m20k(stream['stored_words'],27) for s in all_stages
                        for stream in s['unique_root_streams'] if stream['stored_words'])
    nonconstant_root_ports=3*sum(sum(stream['stored_words']>0 for stream in s['unique_root_streams'])
                               for s in all_stages)
    adapter_m20k_per_field=2*parallel*m20k(2*t,27) if n>parallel else 0
    bf=3*2*aw*(parallel//2)
    bfm=3*2*((aw-p)*parallel+p*(parallel//2))
    transform_latency=fwd['modeled_first_output_latency']+inv['modeled_first_output_latency']
    first_coefficient=incoming['first_output_latency_lower_bound']+transform_latency+outgoing['first_output_latency_lower_bound']+3*multiplier_edges+crt_edges
    exact_interval=first_coefficient+t+carry_first_edges
    wrap_interval=first_coefficient+carry_first_edges
    correction_ready=first_coefficient+t-1+carry_first_edges+3
    next_pointwise=wrap_interval+incoming['first_output_latency_lower_bound']+multiplier_edges+fwd['modeled_first_output_latency']
    wrap_generator=wrap2_recurrence(n,parallel,1,multiplier_edges=multiplier_edges,
                                   contexts=1<<(multiplier_edges.bit_length()))
    wrap_init=wrap_generator['conservative_initialization_barrier_ticks']
    root=Path(__file__).resolve().parents[1]
    source_paths=('reference/stream_ntt_schedule.py','reference/stream_ntt_model.py',
        'rtl/kernel/genefer_ntt_banked27_engine.sv','rtl/kernel/genefer_montgomery_mul27_sparse_pipe.sv',
        'rtl/kernel/genefer_root_recurrence27.sv')
    pins={name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in source_paths}
    return dict(status='partial_S1_conservative_scenario_not_go_for_RTL',n=n,parallel=parallel,
        source_sha256=pins,
        stages=fwd['stages'],inverse_stages=inv['stages'],adapters=[incoming,outgoing],
        resources=dict(mdc_butterfly_units_three_fields_two_pipes=bf,
            mdf_sdf_alternative_butterfly_units_three_fields_two_pipes=bfm,
            mdf_sdf_count_topology_not_implemented=True,
            mdf_sdf_butterfly_alms_scaled_estimate_not_fit=375*bfm,
            butterfly_dsp_conservative_one_per_unit=bf,
            butterfly_alms_scaled_estimate_not_fit=375*bf,
            twist_square_untwist_modular_multipliers_three_fields=3*3*parallel,
            crt_dsp_estimate_six_per_lane=6*parallel,
            carry_dsp_scaled_258_at_P16_estimate=ceil(258*parallel/16),
            optional_wrap2_term_and_weight_recurrence_dsp_three_fields=2*3*parallel,
            answers_r2_wrap2_seed_and_term_recurrence_dsp_three_fields=3*parallel,
            wrap2_ROM_alternative_term_dsp_three_fields=3*parallel,
            root_recurrence_nonconstant_stream_multiplier_ports=nonconstant_root_ports,
            twist_untwist_recurrence_multiplier_ports_three_fields=2*3*parallel,
            root_recurrence_interleaved_states_required_per_port=multiplier_edges+1,
            delay_m20k_coalesced_deep_estimate=delay_m20k,delay_mlab_shallow_estimate=delay_mlab,
            delay_mlab_ALM_cost_estimate=10*delay_mlab,
            root_rom_M20K_unoptimized_per_unique_port_estimate=root_rom_m20k,
            adapters_M20K_six_residue_adapters_conservative=3*adapter_m20k_per_field,
            core_delay_words_three_fields_two_pipes=3*(fwd['core_delay_words']+inv['core_delay_words']),
            shared_32bit_input_adapter_M20K_alternative=parallel*m20k(2*t,32) if n>parallel else 0,
            output_three_27bit_adapters_M20K=3*parallel*m20k(2*t,27) if n>parallel else 0,
            paper_input_reorder_sufficient_words=n-t,
            twist_untwist_wrap2_ROM_ports_and_storage_unbudgeted=True,
            conversion_CRT_carry_control_ALMs_and_other_RAM_unbudgeted=True),
        timing=dict(frame_ticks=t,ideal_two_frame_bound=2*t,
            mathematical_core_shuffle_latency_each=t-1,
            butterfly_edges_declared=butterfly_edges,multiplier_edges_declared=multiplier_edges,
            first_coefficient_lower_bound_with_unfused_adapters=first_coefficient,
            exact_carry_interval_scenario=exact_interval,wrap2_interval_scenario=wrap_interval,
            wrap2_correction_ready_scenario=correction_ready,next_pointwise_scenario=next_pointwise,
            wrap2_margin_scenario=next_pointwise-correction_ready,
            wrap2_initialization_barrier_ticks_charged=wrap_init,
            wrap2_margin_after_initialization_scenario=next_pointwise-correction_ready-wrap_init,
            wrap2_seed_batches=wrap_generator['seed_batches'],
            exact_carry_streaming_II_P_not_proved=True,complete_square_cycle_qualified=False),
        sources=SOURCES,limitations=[
            'MDC != MDF: P/2 perstage versus P in temporal feedback stages; no borrowed complex +/-j rotation savings for NTT.',
            '375ALM/BF and6DSP/CRT are prior-source scaling estimates, not a fit of this topology.',
            'N-P words apply only to strided MDC core; conservative natural carry adapters allocate2N each.',
            'Paper N-N/P input-reorder storage is a sufficiency result, not a general adapter lower bound; its circuit is not implemented here.',
            'M20K shape tiling respects SDP width/depth/ports but synchronous RAM read delay, old-data hazards and mapping remain RTL gates.',
            'ROM model keeps distinct root streams perstage; constants may require modular multiplier logic. Existing recurrence uses4 contexts for3-edge registered multiplier feedback; new generator timing is unqualified.',
            'Answers-r2 wrap2 generator uses a trailing-ones step table with4 seed contexts and m->m+4; oneDSP/lane includes seed multiplication. Initialization barrier is charged, but RTL/root reset/stall behavior remains unqualified.',
            'Carry service/II and wrap2 split arithmetic/rounding bound are not implemented here; reported intervals are explicit scenarios, not verified2T/3T.',
            'Potential shared input adapter and carry/output-order fusion are alternatives requiring new schedule proof, not silently credited savings.'])


if __name__=='__main__':
    print(json.dumps([resource_and_interval(parallel=p) for p in (8,16)],indent=2))
