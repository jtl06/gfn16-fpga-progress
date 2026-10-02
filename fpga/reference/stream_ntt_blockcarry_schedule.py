"""S1 successor: stream27-blockcarry evaluation, NOT an adopted RTL profile.

Preserves frozen stream_ntt_schedule/model/proposal. Literal DIF/DIT ordering,
small correction transforms, split-carry feedback tokens and segmented4-context
term recurrence are checked. Cycle/area decision is explicitly model-only:
new one-edge bounded carry cell and physical queue implementation need RTL gates.
"""
from collections import deque
from math import ceil
from pathlib import Path
import hashlib
import json

from . import stream_ntt_blockwrap2_proposal as arithmetic
from .stream_ntt_schedule import transform, dimensions, m20k, commutator, index_of
from .stream_ntt_model import FIELDS, bit_reverse, ModelMismatch, centered_crt
from ..synthesis.summarize import read_probe


FROZEN_SCHEDULE_SHA='03c1c855e0f6e31f0fcb85d32ed2e604a935e482dfa725d7207e635cb1e963cc'
_old=Path(__file__).with_name('stream_ntt_schedule.py')
if hashlib.sha256(_old.read_bytes()).hexdigest()!=FROZEN_SCHEDULE_SHA:
    raise ValueError('frozen S1 schedule dependency drift')


def minimum_base(n,p):
    dimensions(n,p)
    if n<32 or n//p<2 or p not in (8,16):
        raise ValueError('AW5..16 and P8/P16 with at least2digits/block required')
    K=2*n+24*p
    return max(2*n+5,(2*K+2)//3+1)


def small_tables(state,field):
    """Two literal spatial P-point DIFs; bit-reversed outputs fixed-wired back.

    A/B frames reuse the same P/2 butterfly units perstage on adjacent ticks;
    no extra full-N transform, reorder RAM or global lane crossbar.
    """
    n=len(state.digits);p=len(state.c0);T=n//p;prime,g=FIELDS[field]
    psi=pow(g,(prime-1)//(2*n),prime);width=p.bit_length()-1
    output=[]
    for coefficients in (state.c0,state.c1):
        vector=[c*pow(psi,k*T,prime)%prime for k,c in enumerate(coefficients)]
        result=transform(p,p,values=vector,field=field,butterfly_edges=5)['output_values']
        output.append(tuple(result[bit_reverse(j,width)] for j in range(p)))
    expected=arithmetic.correction_tables(state,field)
    if tuple(output)!=expected:raise ModelMismatch('small-transform-order','A/B correction tables')
    return tuple(output)


def segmented_term(n,p,B,field,*,wrong_frequency=False,contexts=4):
    """One multiplier/lane includes B[k] seed products and m->m+4 updates.

    k=bit_reverse(lane+P*m,AW) modP. R2's constant-c1 recurrence is NOT reused
    across changed B[k]: the first4 positions after each coefficient change
    reseed with static psi*omega^frequency constants. No division by oldB.
    Every logical tick is one multiplication/lane;3-edge registered feedback
    is only reused4ticks later. All P table coefficients must already be ready.
    """
    aw,_,T=dimensions(n,p)
    if len(B)!=p:raise ValueError('P-entry B table')
    if contexts!=4:raise ModelMismatch('term-feedback','this schedule requires4contexts')
    prime,g=FIELDS[field];psi=pow(g,(prime-1)//(2*n),prime);omega=psi*psi%prime
    R=pow(2,32,prime);Rinv=pow(R,-1,prime)
    rows=[];indices=[];seed_ops=0;update_ops=0
    for m in range(T):
        row=[];indexrow=[]
        for lane in range(p):
            slot=lane+p*m;j=bit_reverse(slot,aw);k=j%p
            if m<contexts or k!=indices[m-contexts][lane]:
                frequency=slot if wrong_frequency else j
                weight=psi*pow(omega,frequency,prime)%prime
                value=B[k]*(weight*R%prime)*Rinv%prime;seed_ops+=1
            else:
                oldj=bit_reverse(lane+p*(m-contexts),aw)
                factor=pow(omega,(j-oldj)%n,prime)
                value=rows[m-contexts][lane]*(factor*R%prime)*Rinv%prime;update_ops+=1
            expected=B[k]*psi*pow(omega,j,prime)%prime
            if value!=expected:raise ModelMismatch('segmented-term','wrong frequency/segment seed')
            row.append(value);indexrow.append(k)
        rows.append(row);indices.append(indexrow)
    return dict(rows=rows,table_indices=indices,multipliers_per_field=p,
        seed_operations=seed_ops,update_operations=update_ops,total_operations=n,
        startup_first_product_edges=3,all_initial_contexts_ready_edges=min(4,T)-1+3,
        seed_constant_ROM_entries=4*p*p if n>=p*p*4 else n,
        segment_reseeding=True,steady_vectors_per_tick=1,
        note='New registered generator model; no drift, inversion of B or unbudgeted second twiddle DSP.')


def split_carry_tokens(coefficients,base,p,*,first_input_edge=0,wrong_lane=False):
    """Literal streamed split normalization along each contiguous block.

    Divider1 II1/edge+11 -> divider2 nextedge/edge+11 -> y pre-add register
    -> bounded small-carry feedback register. Only the small[-2,3] value feeds
    back, NOT the wide divider quotient. This ONE-edge cell is a new hardware
    proposal: software ordering is checked, physical timing is unqualified.
    Broad boundary normalization retains the full two-radix adjustment.
    """
    n=len(coefficients);_,pw,T=dimensions(n,p)
    if base<minimum_base(n,p):raise ValueError('base below explicit blockcarry qualification minimum')
    proof=arithmetic.bound_proof(n,p,base)
    if proof['doubled_coefficient_bound']>=1<<77 or proof['serial_carry_abs_bound']>=1<<47:
        raise ValueError('frozen77/47-bit divider magnitude contracts insufficient')
    if any(type(x) is not int or abs(x)>proof['doubled_coefficient_bound'] for x in coefficients):
        raise ModelMismatch('coefficient-bound','outside blockcarry bound')
    digits=[0]*n;boundaries=[0]*p;previous=[deque(maxlen=2) for _ in range(p)];small=[0]*p
    events=[];parts_latency=23;first_digit_edge=first_input_edge+parts_latency+2
    for cycle in range(T):
        for lane in range(p):
            block=bit_reverse(lane,pw);index=block*T+cycle
            q,r0=divmod(coefficients[index],base);q2,r1=divmod(q,base)
            history=previous[lane]
            y=r0+(history[-1][1] if history else 0)+(history[-2][2] if len(history)>1 else 0)
            c,d=divmod(y+small[lane],base)
            if not -2<=c<=3:raise ModelMismatch('small-carry','feedback domain escaped')
            small[lane]=c;history.append((r0,r1,q2));digits[index]=d
            edge=first_digit_edge+cycle
            events.append((edge,lane,index,d))
            if cycle==T-1:
                raw0=r1+history[-2][2]+c;raw1=q2
                adjust,low=divmod(raw0,base)  # Do NOT replace with one +/-base step.
                boundaries[block]=low+base*(raw1+adjust)
    result=arithmetic._finish(digits,base,p,boundaries)
    expected,expected_boundaries=arithmetic.carry_serial(coefficients,base,p)
    if result!=expected or tuple(boundaries)!=expected_boundaries:
        raise ModelMismatch('split-carry-stream','serial block oracle mismatch')
    mapping=[]
    for lane in range(p):
        block=bit_reverse(lane,pw);target=(block+1)%p
        target_lane=lane if wrong_lane else bit_reverse(target,pw)
        if target_lane!=bit_reverse(target,pw):raise ModelMismatch('boundary-wire','wrong target lane')
        mapping.append(dict(source_lane=lane,source_block=block,target_block=target,
                            target_lane=target_lane,sign=-1 if target==0 else 1))
    return dict(state=result,events=events,boundary_wire=mapping,parts_latency_edges=23,
        preadd_register_edges=1,small_feedback_register_edges=1,
        first_digit_edge=first_digit_edge,last_digit_edge=first_digit_edge+T-1,
        boundaries_ready_edge=first_digit_edge+T-1+2,
        modeled_vectors_per_tick=1,feedback_cell_RTL_timing_qualified=False,
        register_buffers_per_lane=dict(previous_r1=1,previous_q2=2,small_carry=1,y=1),
        full_frame_carry_RAM_required=False,
        reciprocal_setup_cycles=97,reciprocal_setup_per_square=False)


def joined_square(state,double_bit=0,*,wrong_lane=False,allow_full_size=False):
    """Literal DIF→term+square→DIT + small transforms + streamed split carry."""
    n=len(state.digits);p=len(state.c0)
    if double_bit not in (0,1):raise ValueError('double_bit0/1')
    if n>4096 and not (allow_full_size and n==65536):
        raise ValueError('local gate N<=4096; fullN requires explicit bounded executor authorization')
    residues=[]
    for field,(prime,g) in enumerate(FIELDS):
        psi=pow(g,(prime-1)//(2*n),prime)
        R=pow(2,32,prime);Rinv=pow(R,-1,prime)
        mont=lambda a,b:a*b*Rinv%prime
        # Data remain ordinary residues, all static twist/BF/recurrence roots
        # are MontgomeryR constants. Pointwise Mont square alone contributes
        # R^-1; fuse recovery into final untwist/N constant with R^2, not R.
        twisted=[mont(d,pow(psi,i,prime)*R%prime) for i,d in enumerate(state.digits)]
        fwd=transform(n,p,values=twisted,field=field)
        A,B=small_tables(state,field);terms=segmented_term(n,p,B,field)
        spectrum=[]
        for slot,value in enumerate(fwd['output_values']):
            cycle,lane=divmod(slot,p);k=terms['table_indices'][cycle][lane]
            corrected=(value+A[k]+terms['rows'][cycle][lane])%prime
            spectrum.append(mont(corrected,corrected))
        inv=transform(n,p,inverse=True,values=spectrum,field=field)
        # Frozen software transform normalized byN; physical DIT is unscaled.
        # Restore its unscaled value explicitly before the single fused mul.
        residues.append([mont(value*n%prime,pow(psi,-i,prime)*pow(n,-1,prime)*R*R%prime)
                         for i,value in enumerate(inv['output_values'])])
        if fwd['output_indices']!=[[c*p+l for l in range(p)] for c in range(n//p)]:
            raise ModelMismatch('junction-order','DIF/DIT spectral adapter would be required')
    coefficients=[centered_crt(row)*(1<<double_bit) for row in zip(*residues)]
    return split_carry_tokens(coefficients,state.base,p,wrong_lane=wrong_lane)


def timed_transform(n,p,*,inverse=False,start=0,epoch=0):
    """Literal tagged commutator execution plus registered stage-edge events.

    Frame arrays below are SOFTWARE OBSERVERS, not proposed hardware storage.
    Actual shuffle storage is the frozen two-FIFO cell. A BF consumes every
    pair at one edge and produces at edge+5; downstream accepts next edge.
    A shuffle consumes dense rows, emits afterL, then downstream accepts next
    edge. Single-frame phase restart and drain are explicit; a following frame
    may enter this same stage only after both shuffle queues have drained.
    """
    aw,pw,T=dimensions(n,p)
    lane_bits=list(range(pw)) if inverse else list(range(aw-1,aw-pw-1,-1))
    time_bits=list(range(pw,aw)) if inverse else list(range(aw-pw))
    rows=[[(epoch,index_of(c,l,lane_bits,time_bits)) for l in range(p)] for c in range(T)]
    edge=start;stages=[]
    for number,bit in enumerate(range(aw) if inverse else range(aw-1,-1,-1)):
        incoming=edge;depth=0
        if bit not in lane_bits:
            pos=time_bits.index(bit);depth=1<<pos
            replaced=min(lane_bits) if inverse else max(lane_bits)
            lane_pos=lane_bits.index(replaced)
            rows=commutator(rows,lane_pos,depth)
            lane_bits[lane_pos],time_bits[pos]=bit,replaced
            edge+=depth+1
        lane_pos=lane_bits.index(bit)
        for c,row in enumerate(rows):
            for lane,(tag,index) in enumerate(row):
                if tag!=epoch or index!=index_of(c,lane,lane_bits,time_bits):
                    raise ModelMismatch('timed-stage-order',str((epoch,number,c,lane)))
                if not lane&(1<<lane_pos) and index^(1<<bit)!=row[lane^(1<<lane_pos)][1]:
                    raise ModelMismatch('timed-BF-pair',str(number))
        stages.append(dict(stage=number,input_first_edge=incoming,
            input_last_edge=incoming+T-1,shuffle_drained_edge=incoming+T-1+depth,
            butterfly_first_accept=edge,butterfly_last_output=edge+T-1+5,
            FIFO_depth=depth,FIFO_count=p if depth else 0,ports_per_FIFO='1R/1W',
            next_epoch_min_spacing=T+depth))
        edge+=6
    final_bits=list(range(aw-1,aw-pw-1,-1)) if inverse else list(range(pw))
    position={b:j for j,b in enumerate(lane_bits)}
    rows=[[row[sum(((lane>>j)&1)<<position[b] for j,b in enumerate(final_bits))]
           for lane in range(p)] for row in rows]
    expected=[[bit_reverse(l,pw)*T+c if inverse else c*p+l for l in range(p)] for c in range(T)]
    if [[token[1] for token in row] for row in rows]!=expected:
        raise ModelMismatch('timed-terminal-order','fixed final wiring')
    return dict(rows=rows,first_next_accept_edge=edge,stages=stages)


def joined_events(n,p,*,extra_correction_delay=0):
    """Two dependent epochs with literal queued transforms and tagged joins.

    Three residue fields share valid/tag geometry (each owns separate data
    FIFOs). The pointwise wait FIFO stores a COMPLETE three-field vector.
    Carry feedback is a one-edge bounded state machine in this model, not a
    wide-divider feedback. No physical cell clock qualification is asserted.
    """
    aw,pw,T=dimensions(n,p)
    fwd=timed_transform(n,p,start=8,epoch=0)
    X=fwd['first_next_accept_edge']-1
    # X producer -> two modadd stages -> square multiplier -> inverse consumer.
    inverse_start=X+1+2+4
    inv=timed_transform(n,p,inverse=True,start=inverse_start,epoch=0)
    first_digit=inv['first_next_accept_edge']+4+16+12+12+1
    interval=first_digit+1
    boundary=first_digit+T-1+2
    # Signed normalize/register + twist: first spatial-small-DFT accept is
    # boundary+10. A and B are two adjacent frames in the SAME P/2/stage FFT.
    small_A=timed_transform(p,p,start=boundary+10,epoch=0)
    small_B=timed_transform(p,p,start=boundary+11,epoch=1)
    for old,new in zip(small_A['stages'],small_B['stages']):
        if new['input_first_edge']<=old['shuffle_drained_edge']:
            raise ModelMismatch('small-frame-ownership','shared A/B spatial pipeline collision')
    tables=small_B['first_next_accept_edge']+extra_correction_delay
    init_ready=tables+1+min(4,T)-1+3
    next_X=interval+X
    wait=max(0,init_ready-next_X)
    # Epoch1 forward takes epoch0 carry digits nextedge; only pointwise waits.
    fwd1=timed_transform(n,p,start=interval+8,epoch=1)
    for old,new in zip(fwd['stages'],fwd1['stages']):
        if new['input_first_edge']<=old['shuffle_drained_edge']:
            raise ModelMismatch('frame-ownership','undrained forward FIFO reuse')
    inv1=timed_transform(n,p,inverse=True,start=interval+inverse_start+wait,epoch=1)
    for old,new in zip(inv['stages'],inv1['stages']):
        if new['input_first_edge']<=old['shuffle_drained_edge']:
            raise ModelMismatch('frame-ownership','undrained inverse FIFO reuse')
    queue=deque();max_points=0;context_ready=[None]*4
    term_first_consume=next_X+wait+1
    # Four seeds issued immediately once tables are ready; products edge+3.
    for c in range(min(4,T)):context_ready[c]=tables+1+c+3
    for tick in range(T+wait):
        if tick<T:queue.append(fwd1['rows'][tick])
        max_points=max(max_points,len(queue)*p)
        if tick>=wait and tick-wait<T:
            m=tick-wait;consumer=term_first_consume+m;row=queue.popleft()
            if row!=[(1,m*p+l) for l in range(p)]:
                raise ModelMismatch('pointwise-tag','FIFO joined wrong epoch/slot')
            if context_ready[m%4] is None or context_ready[m%4]>=consumer:
                raise ModelMismatch('term-feedback-edge','product not available before consumer')
            # Current context serves output and one m+4 update/reseed. At most
            # one multiplication per lane; changed B[k] uses static seed factor.
            if m+4<T:context_ready[m%4]=consumer+3
    if queue:raise ModelMismatch('pointwise-drain','pending complete vector')
    for c,row in enumerate(inv['rows']):
        for lane,(_,index) in enumerate(row):
            if index!=bit_reverse(lane,pw)*T+c:
                raise ModelMismatch('carry-forward-wire','block order changed')
            if (first_digit+c)+1!=interval+c:
                raise ModelMismatch('carry-feedback-edge','not nextedge dense input')
    if n>=p*p:
        for m in range(T):
            if len({bit_reverse(m*p+l,aw)%p for l in range(p)})!=1:
                raise ModelMismatch('correction-table-port','fullN table needs unexpected multiport')
    # max_points includes the transparent current row even when wait=0.
    stored_points=max_points if wait>=T else max(0,max_points-p)
    return dict(interval=interval+wait,unwaited_interval=interval,first_digit=first_digit,
        boundary_ready=boundary,tables_ready=tables,term_initialization_ready=init_ready,
        next_X=next_X,wait=wait,pointwise_stored_points=stored_points,
        pointwise_stored_bits=stored_points*3*27,
        epochs_checked=2,logical_rows_checked=4*T,tagged_tokens_checked=4*n,
        term_contexts_per_lane=4,term_multiplier_issues_per_lane_per_tick=1,
        correction_table_read='jmodP broadcast perfield at fullN; generic lane-local reads for smallN',
        transform_stage_events=dict(forward=fwd['stages'],inverse=inv['stages']),
        small_transform_stage_events=dict(A=small_A['stages'],B=small_B['stages']),
        scope='literal commutator queues + joined valid/tag events; arithmetic checked independently')


def model(n=65536,p=8,base=1_000_000_000):
    aw,pw,T=dimensions(n,p);minimum=minimum_base(n,p)
    if base<minimum:raise ValueError('unqualified base')
    proof=arithmetic.bound_proof(n,p,base)
    fwd=transform(n,p);inv=transform(n,p,inverse=True)
    # Actual registered producer output can be accepted only at the next edge.
    # Every shuffle boundary is separately charged1consumer edge.
    temporal=aw-pw;shuffle=T-1
    forward_to_pointwise=4+4+6*aw+shuffle+temporal
    inverse_to_untwist=6*aw+shuffle+temporal
    interval=forward_to_pointwise+2+4+inverse_to_untwist+4+16+12+12+1+1
    first_carry=interval-1
    boundary_ready=first_carry+T-1+2
    # Signed correction normalization(3edges+sign register), twist and two
    # adjacent small-DFT frames. Tables are fixed-rewired to natural jmodP.
    tables_ready=boundary_ready+6*pw+11
    term_initialization_ready=tables_ready+1+min(4,T)-1+3
    next_X=interval+forward_to_pointwise-1
    wait=max(0,term_initialization_ready-next_X)
    final_interval=interval+wait
    events=joined_events(n,p)
    if (events['interval'],events['first_digit'],events['tables_ready'],events['wait'])!=(final_interval,first_carry,tables_ready,wait):
        raise ModelMismatch('timing-crosscheck','scalar summary disagrees with queued event execution')
    stages=fwd['stages']+inv['stages']
    delay_ram=3*sum(m20k(s['shuffle_depth_per_buffer'],p*27) for s in stages
                   if s['shuffle_depth_per_buffer']>32)
    delay_mlab=3*sum(ceil(p*27/20) for s in stages if 0<s['shuffle_depth_per_buffer']<=32)
    root_rom=3*sum(m20k(q['stored_words'],27) for s in stages
                  for q in s['unique_root_streams'] if q['stored_words'])
    io_rom=6*m20k(T,p*27)  # Twist + fused untwist/scale, three fields.
    bf=3*2*aw*(p//2);small_bf=3*pw*(p//2)
    root=Path(__file__).resolve().parents[1]
    crt_project=root/'results/throughput-20260929/crt27-montgomery16-aws-fit-v3'
    crt=read_probe(crt_project)
    if not crt['fit_success'] or (crt['alms_needed'],crt['alms_placed'],crt['dsp_blocks_needed'],crt['ram_blocks'])!=(11257,12790,96,0):
        raise ValueError('source-backed CRT16 scaling anchor mismatch')
    crt_area=ceil(crt['alms_needed']*p/16)
    # One full frozen BF's375ALM used as conservative proxy for standalone
    # modular multipliers. This is NOT a synth estimate or packed-needed fit.
    main_multipliers=9*p;term_multipliers=3*p;small_twist_multipliers=3*p
    carry_area=ceil(29500*p/16)
    scaled_area=375*(bf+small_bf+main_multipliers+term_multipliers+small_twist_multipliers)+crt_area+carry_area+10*delay_mlab
    # Reducers are compare/subtract pipelines, NOT DSP multipliers. Charge the
    # much larger375ALM BF proxy for each of3P digit +3P shared signed-boundary
    # reducers, and separately reserve25K for unmeasured valid/control/base logic.
    reducer_allowance=375*6*p;control_allowance=25000
    planning_area=scaled_area+reducer_allowance+control_allowance
    seed_rom=3*m20k(4*p,p*27)
    recurrence_factor_rom=3*m20k(max(1,aw-pw-2),p*27)
    readback_ram=p*m20k(T,32)
    wait_points=events['pointwise_stored_points']
    wait_ram=m20k(ceil(wait_points/p),3*p*27) if wait_points else 0
    all_ram=delay_ram+root_rom+io_rom+seed_rom+recurrence_factor_rom+readback_ram+wait_ram
    all_dsp=bf+small_bf+main_multipliers+term_multipliers+small_twist_multipliers+6*p+ceil(258*p/16)
    known_files=('reference/stream_ntt_blockcarry_schedule.py','reference/stream_ntt_schedule.py',
        'reference/stream_ntt_blockwrap2_proposal.py','reference/stream_ntt_model.py',
        'rtl/kernel/genefer_div_recip_precision.sv','rtl/kernel/genefer_digit_reduce27_pipe.sv',
        'rtl/kernel/genefer_crt3_27_mont_pipe.sv')
    pins={f:hashlib.sha256((root/f).read_bytes()).hexdigest() for f in known_files}
    pins['results/throughput-20260929/crt27-montgomery16-aws-fit-v3/output_files/probe.fit.summary']=hashlib.sha256((crt_project/'output_files/probe.fit.summary').read_bytes()).hexdigest()
    return dict(profile='stream27-blockcarry',status='S1_evaluation_not_adopted_not_RTL_GO',
        n=n,p=p,base=base,minimum_supported_base=minimum,proof=proof,source_sha256=pins,
        lane_order=dict(input_and_inverse_output='index=bit_reverse(lane,log2P)*T+cycle',
            forward_output_and_inverse_input='slot=cycle*P+lane;frequency=bit_reverse(slot,AW)',
            junction_adapter_required=False,carry_to_forward_wire='identity physical lane; natural block index is bit_reverse(lane,log2P)',
            boundary_to_nextblock_wire='lane_out=bit_reverse((bit_reverse(lane_in,log2P)+1)modP,log2P); final sign negative'),
        queued_events=events,
        timing=dict(steady_interval_scenario=final_interval,interval_without_correction_wait=interval,
            ideal_two_frame_bound=2*T,first_carry_digit_relative_start=first_carry,
            boundary_split_ready=boundary_ready,small_tables_ready=tables_ready,
            term_four_context_initialization_ready=term_initialization_ready,
            next_forward_first_X_ready=next_X,correction_margin=next_X-term_initialization_ready,
            correction_wait_ticks=wait,reciprocal_setup_cold_only=97,
            cold_first_digit_including_nonoverlapped_setup=97+first_carry,
            producer_consumer_nextedge_charged=True,carry_feedback_cell_II1_modeled_not_RTL_proved=True,
            physical_ram_registered_latency_alignment_not_qualified=True),
        buffers=dict(transform_FIFO_words=6*(n-p),deep_delay_M20K=delay_ram,
            shallow_delay_MLAB=delay_mlab,root_ROM_M20K_estimate=root_rom,
            IO_twist_untwist_ROM_M20K_estimate=io_rom,
            correction_seed_constants_ROM_M20K_estimate=seed_rom,
            correction_update_factor_ROM_M20K_estimate=recurrence_factor_rom,
            small_A_B_table_register_words=6*p,term_recurrence_context_register_words=12*p,
            carry_history_register_words=5*p,small_transform_pipeline_words=2*p*pw*3,
            full_frame_natural_order_adapter_words=0,full_frame_carry_staging_words=0,
            optional_readback_digit_RAM_M20K=readback_ram,
            pointwise_gate_FIFO_points=wait_points,
            pointwise_gate_FIFO_bits=wait_points*3*27,
            pointwise_gate_FIFO_M20K=wait_ram,
            all_listed_M20K_including_ROM_delay_readback=all_ram,
            note='No carry/adaptor frame RAM in denseII1 model. All FIFO ports are1R/1W; widths/depths tiled using legal SDP configurations. Readback and reset/drain semantics remain separate.'),
        resources=dict(main_butterfly_units=bf,small_transform_butterfly_units=small_bf,
            main_twist_square_untwist_modmul_units=main_multipliers,
            correction_term_modmul_units=term_multipliers,small_transform_twist_modmul_units=small_twist_multipliers,
            CRT_needed_ALM_scaled_component_anchor=crt_area,CRT_DSP_scaled_component_anchor=6*p,
            CRT_anchor_class='16lane component fit only;151.81MHz report is NOT streaming/whole-core clock',
            carry_ALM_scaled_prior_16lane_estimate=carry_area,
            all_listed_logic_ALM_proxy_subtotal=scaled_area,
            remaining_margin_to_300K_for_reducers_controls=300000-scaled_area,
            reducer_ALM_planning_allowance=reducer_allowance,
            control_valid_base_ALM_planning_allowance=control_allowance,
            total_ALM_planning_estimate=planning_area,
            remaining_margin_to_300K_after_allowances=300000-planning_area,
            carry_DSP_scaled_prior_estimate=ceil(258*p/16),
            ROM_strategy_DSP_proxy=all_dsp,
            device_DSP_capacity=1518,device_M20K_capacity=2713,
            DSP_margin=1518-all_dsp,M20K_margin=2713-all_ram,
            area_estimate_not_fitted_needed_ALMs=True),
        decision=dict(cycle_target_20K_met=final_interval<=20000,
            scaled_area_subtotal_below_300K=scaled_area<=300000,
            planning_area_below_300K=planning_area<=300000,
            DSP_device_capacity_met=all_dsp<=1518,M20K_device_capacity_met=all_ram<=2713,
            evaluation='conditional_S1_model_GO_P8_only' if final_interval<=20000 and planning_area<=300000 and all_dsp<=1518 and all_ram<=2713 else 'no_go_at_current_scaled_cost',
            S1_GO_for_RTL=False,
            recommendation='P8 may proceed to a separately authorized S3 implementation gate after S1 tests; P16 park under current area scaling.',
            S3_risks_not_S1_algorithm_blockers=['New bounded six-state carry cell target-clock physical timing.',
                'Signed boundary reducer, reset/abort, setup and valid/tag implementation must match the modeled edge contracts.',
                'Actual carry/control area and ROM/FIFO inference; BF375ALM and reserve allowances are estimates, not packed fit results.',
                'Registered FIFO alignment and exact native full-size vector gate before architecture qualification.']),
        limitations=['All counts are model/scaled resource proxies except the explicitly labeled CRT16 component anchor.',
            'Root ROM is one scenario; selective stage recurrence trades RAM for extra DSP/ALM and initialization.',
            'One-modmul term generator must reseed when B[jmodP] changes; naive constant-c1 recurrence is insufficient.',
            'Montgomery: ordinary data with R-weighted roots; pointwise square contributes R^-1 and final untwist/N constant carries R^2. No extra conversion multiplier.',
            'Timed tags are observers; implementation uses ordered counters/frame ownership. Cold base/reciprocal setup is97clocks once, not per square.',
            'No new clock, fitted resources, board behavior or PRP throughput has been measured.'])


if __name__=='__main__':
    print(json.dumps([model(p=p) for p in (8,16)],indent=2))
