"""Declared source crossing inventory for P16-c/P8-b cold physical probes.

This is not mapped-netlist completeness or fit permission. Native DA and
crossing coverage remain mandatory; control exceptions are explicit contracts.
"""
import hashlib
import json
from pathlib import Path


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inventory(project):
    project=Path(project).resolve();m=json.loads((project/'manifest.json').read_text())
    assert m['core_parameters']=={'AW':16,'CONTEXTS':1}
    assert m['top'] in ('genefer_stream27_p16c_physical_aw16_p16_f0_v1','genefer_stream27_p8b_physical_aw16_p8_f0_v1')
    p16='p16c' in m['top'];top='rtl/'+m['top']+'.sv'
    bf='rtl/'+('genefer_ntt_lazy28_butterfly_v1.sv' if p16 else 'genefer_ntt_banked27_engine.sv')
    mul='rtl/genefer_montgomery_mul27_sparse_pipe.sv'
    ct=next('rtl/'+name for name in m['source_sha256'] if '_merged_ct_' in name)
    gs=next('rtl/'+name for name in m['source_sha256'] if '_merged_gs_' in name)
    square=next('rtl/'+name for name in m['source_sha256'] if '_square_p' in name)
    def stage(id,owner,source,edge,payload,valid,metadata,anchor):
        assert (project/source).read_text().count(anchor)==1,(source,anchor)
        return dict(id=id,owner=owner,source=source,kind='flop',edge=edge,payload=payload,valid=valid,
                    metadata=metadata,anchors=[anchor],alignment='same_accepted_edge')
    ct_output=stage('CT_final_arithmetic_output','CT',bf,0,['stage15.bf[*].y0/y1'],['out_valid'],
        ['CT.stage15.slot_pipe[5]','CT.stage15.start_pipe[5]','CT.stage15.generation_pipe[5]'],
        "y0<=gs_pipe[4] ? prefix_pipe[4] : prefix_pipe[4]+canonical_product;" if p16 else
        'y0<=dif_pipe[4] ? prefix_pipe[4] : post_sum_reduced;')
    square_input=stage('square_product_capture','canonicalizer_square',mul,1,['multiplier[*].ab_s1'],
        ['multiplier[*].valid_pipe[0]','square.slot_pipe[0]'],['square.start_pipe[0]','square.generation_pipe[0]'],
        'if(in_valid)ab_s1<=lhs27*rhs27;')
    square_output=stage('square_modular_output','canonicalizer_square',mul,0,['multiplier[*].result'],
        ['multiplier[*].out_valid','square.slot_pipe[3]'],['square.start_pipe[3]','square.generation_pipe[3]'],
        'if(hi_s3>=mp_hi)result<=hi_s3-mp_hi;')
    gs_input=stage('GS_initial_butterfly_capture','GS',bf,1,['GS.stage0.bf[*].pre_v','GS.stage0.bf[*].prefix_pipe[0]'],
        ['GS.stage0.bf[*].pre_valid'],['GS.stage0.slot_pipe[0]','GS.stage0.start_pipe[0]','GS.stage0.generation_pipe[0]'],
        'if(in_valid)begin pre_v<=gs ? gs_diff_fold : v;pre_w<=w;end' if p16 else
        'pre_v<=dif ? (u>=v ? u-v : u+P-v) : v;')
    controller=stage('registered_controller_error','controller',top,0,['controller_error'],['controller_error'],[],
        '(inv_slot && inv_generation!=active_generation)))controller_error<=1;')
    transfers=[dict(id='CT_canonicalizer_square',producer='CT',consumer='canonicalizer_square',
        signals=['fwd_data','fwd_slot','fwd_start','fwd_generation'],registered_stages=[ct_output,square_input],
        combinational_work='P16-c one-P canonicalizer followed by canonical multiplier input product; P8-b canonical wire identity.'),
        dict(id='square_GS',producer='canonicalizer_square',consumer='GS',
        signals=['square_data','square_slot','square_start','square_generation'],registered_stages=[square_output,gs_input],
        combinational_work='Zero extension for P16-c and GS first butterfly pre-add/subtract; P8-b canonical27 wire.')]
    for block,path,pending in [('CT',ct,'child_pending[0]'),('canonicalizer_square',square,'child_pending[1]'),('GS',gs,'child_pending[2]')]:
        transfers.append(dict(id=block+'_fault_to_controller',producer=block,consumer='controller',
            signals=[pending,'child_error'],registered_stages=[controller],
            exception=dict(kind='phase_local_control',reason='Nonpayload origin-fault diagnostic samples the sticky controller_error at this edge; registered stop suppresses the following edge. No two-register payload-transfer claim is made for this fault path.',
                contract_anchors=[dict(source=top,text='wire stop=controller_error;'),
                                  dict(source=path,text='assign out_error=aggregate_error;' if block!='canonicalizer_square' else 'assign fault_pending=out_error || (!quarantine && mismatch);')]),
            control_reconvergence=[dict(signal=pending+' -> controller_error -> stop',sink='child quarantine/occupied-valid capture',registered_barrier='registered_controller_error')]))
    for block,path in [('CT',ct),('canonicalizer_square',square),('GS',gs)]:
        transfers.append(dict(id='controller_quarantine_'+block,producer='controller',consumer=block,
            signals=['controller_error','stop','quarantine'],registered_stages=[controller],
            exception=dict(kind='phase_local_control',reason='Registered sticky stop is a control authority, not a pipelined payload. Its fanout and reconvergence must be captured in native mapped coverage; source inventory alone does not certify path depth.',
                contract_anchors=[dict(source=top,text='wire stop=controller_error;'),dict(source=path,text='wire stop=quarantine || aggregate_error;' if block!='canonicalizer_square' else 'wire mismatch=lane_valid!={8{slot_pipe[3]}};' if not p16 else 'wire mismatch=lane_valid!={16{slot_pipe[3]}};')]),
            control_reconvergence=[dict(signal='registered stop',sink=block+' valid/enables',registered_barrier='registered_controller_error')]))
    return dict(schema='prefit-structural-inventory-v1',scope='component_probe',
        identity=dict(top=m['top'],device=m['device'],parameters=m['core_parameters'],clock_period_ns=m['clock_period_ns'],seed=m['seed']),
        sources={'rtl/'+n:h for n,h in m['source_sha256'].items()},
        settings={**m['control_sha256'],'manifest.json':sha(project/'manifest.json')},
        blocks=['CT','canonicalizer_square','GS','controller'],transfers=transfers,
        exclusions=[dict(kind='external_virtual_io',endpoints=['all top ports except clk'],reason='Virtual I/O probe; no board timing is asserted.'),
            dict(kind='external_reset',endpoints=['rst_n'],reason='Pinned false path reset constraint does not exclude operational fault/valid nets.'),
            dict(kind='inside_single_macroblock',endpoints=['CT/GS internal butterfly,root,commutator stages'],reason='Declared macroblock inventory, not a proof that internal graph or fanout is safe. Native synthesis/DA and timing analysis still required.')],
        coverage_claim='declared_source_inventory_not_netlist_completeness',
        unresolved_native_coverage=['Enumerate actual surviving CT-to-square and square-to-GS payload/valid/generation paths.',
            'Enumerate child_pending/error and registered controller stop fanout/reconvergence; phase-local exceptions are not a timing waiver.',
            'Top owner-generation and physical done/output_row controls require complete mapped graph accounting.',
            'No native complete-crossing mechanism result is attached; fit must stay blocked.'])


if __name__=='__main__':
    import sys
    assert len(sys.argv)==2
    print(json.dumps(inventory(sys.argv[1]),indent=2))
