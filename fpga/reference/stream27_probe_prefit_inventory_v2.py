"""r47 additive source-port ledger; no exhaustive graph or timing claim.

Every port of the three top-level arithmetic instances is mapped either to
declared sequential transfer stages or an explicit bounded justification.
Native DA and early-placement top100 timing are separate mandatory checks.
"""
import copy
import re
from pathlib import Path
from .stream27_probe_prefit_inventory_v1 import inventory as prior


def bindings(text,instance):
    marker=instance+' (';assert text.count(marker)==1
    body=text.split(marker,1)[1].split(');',1)[0]
    pairs=re.findall(r'\.([A-Za-z_][A-Za-z_0-9]*)(?:\(([^()]*)\))?',body)
    result={key:(value if '(' in re.search(r'\.'+key+r'(?:\([^()]*\))?',body)[0] else key) for key,value in pairs}
    assert len(result)==len(pairs)
    return result


def validate_ports(spec,top_text):
    for instance in ('forward_transform','pointwise_square','inverse_transform'):
        actual=bindings(top_text,instance);groups=[x for x in spec['source_port_groups'] if x['instance']==instance]
        flattened={}
        for group in groups:
            assert group['reason'] and group['basis'] in ('registered_transfer','justified_control','external_virtual_io','clock_reset','intentionally_unconnected_output')
            for port,value in group['bindings'].items():
                assert port not in flattened
                flattened[port]=value
        assert flattened==actual,(instance,set(actual)-set(flattened))
    return sum(len(bindings(top_text,x)) for x in ('forward_transform','pointwise_square','inverse_transform'))


def inventory(project):
    project=Path(project).resolve();spec=copy.deepcopy(prior(project));top='rtl/'+spec['identity']['top']+'.sv';text=(project/top).read_text()
    ct=next(n for n in spec['sources'] if '_merged_ct_' in n)
    gs=next(n for n in spec['sources'] if '_merged_gs_' in n)
    final='rtl/genefer_stream27_merged_final_gs_pair_v1.sv'
    gen_anchor=text.split('if(accepted_start)begin',1)[1].split('\n',1)[0]
    gen_anchor='if(accepted_start)begin'+gen_anchor
    ct_text=(project/ct).read_text();stage0=ct_text.split(' if(1)begin: stage0',1)[1].split(' if(1)begin: stage1',1)[0]
    stage0=' if(1)begin: stage0'+stage0
    spec['transfers'].append(dict(id='controller_owner_to_CT',producer='controller',consumer='CT',
        signals=['active_generation','accepted_generation'],registered_stages=[
            dict(id='operation_owner_latch',owner='controller',source=top,kind='flop',edge=0,
                payload=['active_generation'],valid=['accepted_start'],metadata=[],anchors=[gen_anchor],alignment='same_accepted_edge'),
            dict(id='CT_stage0_owner_capture',owner='CT',source=ct,kind='flop',edge=1,
                payload=['stage0.generation_pipe[0]'],valid=['stage0.slot_pipe[0]'],metadata=['stage0.start_pipe[0]'],
                anchors=[stage0],alignment='same_accepted_edge')],
        qualification='For rows after frame-start, stored owner propagates from row0 operation latch. Row0 itself bypasses from external virtual generation_in and is separately excluded as ingress, not falsely delayed one edge.'))
    spec['transfers'].append(dict(id='GS_completion_to_controller',producer='GS',consumer='controller',
        signals=['inv_slot','inv_generation'],registered_stages=[
            dict(id='GS_final_physical_row',owner='GS',source=final,kind='flop',edge=0,
                payload=['final_pair[*].upper_delay[1]','final_pair[*].lower_pipeline.y1'],valid=['lower_valid','upper_valid_delay[1]'],
                metadata=['GS.stage15.slot_pipe[5]','GS.stage15.start_pipe[5]','GS.stage15.generation_pipe[5]'],
                anchors=['if(upper_valid_delay[0])upper_delay[1]<=upper_delay[0];'],alignment='same_accepted_edge'),
            dict(id='controller_physical_completion',owner='controller',source=top,kind='flop',edge=1,
                payload=['output_row','busy','done'],valid=['inv_slot && !stop'],metadata=['active_generation comparison'],
                anchors=["if(output_row==ROW_W'(T-1))begin busy<=0;done<=1;end"],alignment='same_accepted_edge')],
        control_reconvergence=[dict(signal='inv_slot gated by registered aggregate/controller errors',sink='done/busy/output_row',registered_barrier='controller_physical_completion')]))
    groups=[]
    def group(instance,ports,basis,reason,transfer=None):
        actual=bindings(text,instance)
        groups.append(dict(instance=instance,bindings={p:actual[p] for p in ports},basis=basis,reason=reason,
                           declared_transfer=transfer))
    for instance in ('forward_transform','pointwise_square','inverse_transform'):
        group(instance,['clk','rst_n'],'clock_reset','Shared source clock and explicitly constrained asynchronous reset; this does not excuse operational cancellation or fault fanout.')
        group(instance,['quarantine'],'justified_control','Registered controller_error is the sticky stop authority. Its fanout/reconvergence is included in the early-placement screen, not waived as reset.',
              'controller_quarantine_'+{'forward_transform':'CT','pointwise_square':'canonicalizer_square','inverse_transform':'GS'}[instance])
    group('forward_transform',['data_in'],'external_virtual_io','Already-canonical external field residue after zero-extension/wiring only. No internal source register or board-I/O timing is claimed.')
    group('forward_transform',['in_slot_valid','frame_start'],'justified_control','Physical frame admission derives from operation busy/remaining state and external start; local CT valid/start registers capture it at the sampling edge. No extra two-edge admission delay is invented.')
    group('forward_transform',['generation_in'],'registered_transfer','Row0 external generation bypass is virtual ingress; following rows use registered operation owner captured by CT stage0 metadata.', 'controller_owner_to_CT')
    for instance in ('forward_transform','inverse_transform'):
        group(instance,['context_enabled','live_generation'],'external_virtual_io','Current cancellation/live-generation inputs are virtual external controls. Physical rows remain present; internal advisory eligibility is intentionally unused, and top terminal eligibility checks current values immediately.')
        group(instance,['out_eligible'],'intentionally_unconnected_output','Advisory intermediate eligibility is not a physical-slot gate. Top recomputes current enabled/live-generation/active-generation eligibility; no registered sink commit is modeled.')
    for instance,ports,transfer in [
        ('forward_transform',['data_out','out_slot_valid','out_frame_start','generation_out'],'CT_canonicalizer_square'),
        ('pointwise_square',['data_in','in_slot_valid','frame_start','generation_in'],'CT_canonicalizer_square'),
        ('pointwise_square',['data_out','out_slot_valid','out_frame_start','generation_out'],'square_GS'),
        ('inverse_transform',['data_in','in_slot_valid','frame_start','generation_in'],'square_GS')]:
        group(instance,ports,'registered_transfer','Payload and occupied slot/start/generation move on the same accepted edge through the explicitly inventoried producer/sink registers.',transfer)
    for instance,block in [('forward_transform','CT'),('pointwise_square','canonicalizer_square'),('inverse_transform','GS')]:
        group(instance,['out_error','fault_pending'],'justified_control','Sticky child error and current origin-fault diagnostic are distinct. Controller captures fault now, registered stop suppresses following work; current diagnostic is not treated as already registered.',block+'_fault_to_controller')
    group('inverse_transform',['out_slot_valid','generation_out'],'registered_transfer','Final registered physical slot and generation feed controller completion/owner checks and external outputs. Controller samples drain and mismatch on the next edge.', 'GS_completion_to_controller')
    group('inverse_transform',['out_frame_start'],'external_virtual_io','Registered inverse start is forwarded to the virtual out_frame_start flag; it is not captured by the row-counter controller and no such sink is invented.')
    group('inverse_transform',['data_out'],'external_virtual_io','Final normalized data registers drive virtual external output. No hidden full-field sink/writeback/CRT stage is claimed.')
    spec['source_port_groups']=groups
    spec['source_port_count']=validate_ports(spec,text)
    spec['current_policy']='r47: source registered-port/exceptions inventory, native postsynthesis Design Assistant, early-placed top100 setup cross-block screen. Exhaustive graph is later diagnostic only.'
    spec['unresolved_native_coverage']=['Source-port grouping is not native placed depth proof. Native DA High/Critical findings and earlyplaced top100 singlecycle interblock setup paths still gate fit.']
    return spec
