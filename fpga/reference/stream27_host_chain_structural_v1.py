"""Declared source transfer inventory for the real 49-RTL whole P8 core.

This is source evidence, not complete netlist connectivity or a clock proof.
Registered edge indexes describe transfer stages; they never claim that two
flops lie inside one STA register-to-register edge. Phase-dependent RAM reads
can occur later than the listed minimum transfer edge, as explicitly noted.
"""
import hashlib
import json
from pathlib import Path
from fpga.tools.prefit_structural_guard_v1 import source_inventory,identities

ROOT=Path(__file__).resolve().parents[1]
PROJECT='artifacts/s4-p8-whole-host-aw16-source-v1/project'
PROJECT_PIN='762d765ac2518e19005ca5503e8f6110f55059f8bfdf54200c41894075f113ce'
CHECKER_PIN='9494570410b0cfb083ae0d383164cf773bf7f8e8298e2b81dca7580914383979'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def stage(name,owner,edge,source,payload,valid,metadata,anchors,kind='flop',note=None):
    value=dict(id=name,owner=owner,edge=edge,source='rtl/'+source,payload=payload,valid=valid,metadata=metadata,
               anchors=anchors,kind=kind,alignment='same_accepted_edge')
    if note:value['scope_note']=note
    return value


def prepare(destination):
    destination=Path(destination).resolve();project=ROOT/PROJECT
    if destination.exists() or (ROOT/'docs/briefs/PAUSE').exists():raise ValueError('S4_WHOLE_STRUCTURE_FRESH_PAUSE')
    if sha(project/'manifest.json')!=PROJECT_PIN or sha(ROOT/'tools/prefit_structural_guard_v1.py')!=CHECKER_PIN:
        raise ValueError('S4_WHOLE_STRUCTURE_SOURCE_DRIFT')
    m=json.loads((project/'manifest.json').read_text());host=m['top']+'.sv'
    arith='genefer_stream27_threefield_carry_aw16_p8_param_v1_signed.sv'
    warm='genefer_stream27_warm_chain_aw16_p8_param_v1.sv'
    canonical='genefer_stream27_chain_canonical_aw16_p8_param_v1.sv'
    setup='genefer_stream27_blockcarry_setup_param_v1.sv'
    lane='genefer_stream27_blockcarry_lane_param_v1.sv'
    small='genefer_stream27_blockcarry_small_cell.sv'
    reduce='genefer_digit_reduce27_pipe.sv';crt='genefer_crt3_27_mont_pipe.sv'
    image='genefer_stream27_canonical_image_v1.sv';ram='genefer_sdp_ram32.sv'
    blocks=['host_image','host_control','field0','field1','field2','CRT','carry','setup','arithmetic_control','warm_control','canonical_control','canonical_image']
    transfers=[]
    def add(name,producer,consumer,signals,stages,exception=None):
        value=dict(id=name,producer=producer,consumer=consumer,signals=signals,registered_stages=stages)
        if exception:value['exception']=exception
        transfers.append(value)
    def digit_stage(name,owner,edge):
        return stage(name,owner,edge,small,['digit'],'out_valid',['payload_out / offset'],
                     ['out_valid<=in_valid && legal;','if(legal)digit<=digit_next[31:0];','payload_out<=payload_in;'])
    def ram_stage(name,owner,edge,note):
        return stage(name,owner,edge,ram,['read_data'],'caller qualified registered read-response or processing state',
                     ['caller address/bank held or captured with request'],
                     ['(* ramstyle="M20K, no_rw_check" *) logic [31:0] mem [0:DEPTH-1];','if(rst_n && read_en) read_data<=mem[read_addr];'],
                     kind='registered_ram_output',note=note)
    for f in range(3):
        field=f'field{f}';source=f'genefer_stream27_shared_warm_aw16_p8_f{f}_v1_signed_host_v3_valid_start_v4.sv'
        add('cold_to_'+field,'host_image',field,['source_data','source_valid','source_row','job_generation/epoch'],[
            stage('cold_source_ff', 'host_control',0,host,['source_data'],'source_valid',['source_row','latched job_generation/job_epoch'],
                  ['source_data[32*lane+:32]<=row_read_data[32*NATURAL+:32];','source_valid<=row_read_valid && !error;','if(row_read_valid)source_row<=request_row_d;']),
            stage(field+'_digit_reduce_s1',field,1,reduce,['s1'],'good[0]',['tag1'],
                  ['if(rst_n && in_valid && legal)s1<=first_difference[29:0];','if(rst_n && in_valid)tag1<=payload_in;',"good<={good[1:0],in_valid && legal};bad<={bad[1:0],in_valid && !legal};"])])
        add(field+'_to_CRT',field,'CRT',[f'r{f+1}','joined','epoch/generation/row'],[
            stage('CRT_input','CRT',0,crt,['r1_pipe[0]','r2_input','r3_input'],'valid_pipe[0]',['wrapper crt_tag[0], crt_double[0]'],
                  ['r1_pipe[0]<=r1[26:0];r2_input<=r2[26:0];r3_input<=r3[26:0];','valid_pipe<={valid_pipe[13:0],in_valid};']),
            stage('CRT_centered','CRT',15,crt,['coefficient'],'out_valid',['wrapper crt_tag[15], crt_double[15]'],
                  ['out_valid<=valid_pipe[14];','if(valid_pipe[14])coefficient<=centered_work;'])])
        add(field+'_fault_to_arithmetic',field,'arithmetic_control',['registered field error','origin pending diagnostic'],[
            stage(field+'_origin_error',field,0,source,['controller_error'],'rst_n',['fault context at origin'],['controller_error<=1;']),
            stage('arithmetic_origin_error','arithmetic_control',1,arith,['out_error'],'rst_n',['registered quarantine status'],['if(fault_pending)out_error<=1;'])])
        add('carried_digit_to_'+field,'carry',field,['digit_data','digit_valid','digit_epoch/generation','natural-to-physical static routing'],[
            digit_stage('carry_digit','carry',0),
            stage(field+'_feedback_reduce','field'+str(f),1,reduce,['s1'],'good[0]',['tag1: incremented physical epoch/generation/row/start'],
                  ['if(rst_n && in_valid && legal)s1<=first_difference[29:0];','if(rst_n && in_valid)tag1<=payload_in;',"good<={good[1:0],in_valid && legal};bad<={bad[1:0],in_valid && !legal};"])])
        add('carried_boundary_to_'+field,'carry',field,['next_c0/next_c1','next_epoch/generation','signed33 full-pair final wrap'],[
            stage('carry_boundary','carry',0,lane,['boundary_low','boundary_high'],'boundary_valid',['caller next_epoch/next_generation from latched carry owner'],
                  ["boundary_low<=boundary_digit;boundary_high<=32'(high_sum);boundary_valid<=1;"]),
            stage(field+'_boundary_signed_reduce',field,5,'genefer_stream27_signed_boundary_reduce27_pipe.sv',['residue'],'out_valid',['payload_out'],
                  ['out_valid<=magnitude_valid;','if(magnitude_valid || magnitude_error)payload_out<=magnitude_payload[PAYLOAD_W-1:0];'])])
    add('CRT_to_carry','CRT','carry',['coefficient_data','coefficient_valid/start/row','conditional double'],[
        stage('CRT_centered','CRT',0,crt,['coefficient'],'out_valid',['crt_tag[15], crt_double[15]'],['out_valid<=valid_pipe[14];','if(valid_pipe[14])coefficient<=centered_work;']),
        stage('coefficient_double_ff','arithmetic_control',1,arith,['doubled_data'],'doubled_valid',['doubled_row','doubled_start'],
              ['doubled_data[96*b+:96]<=crt_double[15] ? crt_coefficient[b]<<<1 : crt_coefficient[b];','doubled_valid<=(&crt_valid) && !out_error;','doubled_row<=crt_tag[15][ROW_W-1:0];'])])
    add('host_config_to_setup','host_control','setup',['job_base','job_generation','begin_setup'],[
        stage('job_config','host_control',0,host,['job_base'],'accepted idle start',['job_generation'],['job_base<=base;','job_generation<=job_generation+8\'d1;']),
        stage('setup_config','setup',1,setup,['accepted_base'],'setup state DIVIDE/CHECK',['out_generation'],['accepted_base<=base;','out_generation<=generation;'])])
    add('setup_to_carry','setup','carry',['base','reciprocal96','coefficient_limit77','begin_block'],[
        stage('lane_config','carry',0,lane,['base_reg','reciprocal_reg','limit_reg'],'state ACTIVE',['operation-latched configuration'],
              ['state<=ACTIVE;base_reg<=base;reciprocal_reg<=reciprocal;limit_reg<=coefficient_limit;'])],
        dict(kind='operation_latched_configuration',reason='One shared exact setup qualifies base/reciprocal/bound before lane begin. Each lane latches all three atomically; source control forbids setup mutation while the chain is active. This is not streamed-data timing inheritance.',
             contract_anchors=[dict(source='rtl/'+warm,text='.begin_setup(begin_setup && !active)'),dict(source='rtl/'+lane,text='reciprocal_reg<=reciprocal;limit_reg<=coefficient_limit;')]))
    add('FIFO_control_to_arithmetic','host_control','arithmetic_control',['command index32/generation8/double','feed_push','feed_pop'],[
        stage('descriptor_storage','host_control',0,host,['feed_index','feed_double'],'feed_count!=0',['feed_generation','feed_read pointer'],
              ['feed_index[feed_write]<=command_index;feed_generation[feed_write]<=command_generation;feed_double[feed_write]<=command_double;']),
        stage('accepted_frame_double','arithmetic_control',1,arith,['bank_double'],'frame_accept',['bank_epoch','bank_generation','bank_base'],['bank_base[epoch_in[0]]<=base_in;bank_double[epoch_in[0]]<=double_in;'])])
    add('arithmetic_status_to_warm','arithmetic_control','warm_control',['child_error','completion and admission status'],[
        stage('arithmetic_origin_error','arithmetic_control',0,arith,['out_error'],'rst_n',['registered quarantine status'],['if(fault_pending)out_error<=1;']),
        stage('warm_origin_error','warm_control',1,warm,['local_error'],'rst_n',['chain_error_code'],['if(count_bad || collision || child_error || command_bad)local_error<=1;'])])
    add('last_carry_to_canonical_RAM','carry','canonical_image',['digit_data','final row validity/full32 ordinal','natural row address'],[
        digit_stage('carry_digit','carry',0),ram_stage('canonical_RAM_read_q','canonical_image',1,'Raw row is first written to real canonical RAM; only after true-last drain does the serial canonical controller read it. Edge1 is the minimum sequential read barrier, NOT a one-cycle load-to-finalize claim. Normal/special whole costs remain6N/7N.')])
    add('last_boundary_to_canonical','carry','canonical_control',['next_c0/next_c1','boundary_sequence','next_epoch/generation'],[
        stage('carry_boundary','carry',0,lane,['boundary_low','boundary_high'],'boundary_valid',['caller next owner'],["boundary_low<=boundary_digit;boundary_high<=32'(high_sum);boundary_valid<=1;"]),
        stage('final_corrections','canonical_control',1,canonical,['final_c0','final_c1'],'metadata_ready',['full32 final_sequence','physical final_epoch','chain_generation'],['final_c0<=next_c0;final_c1<=next_c1;metadata_ready<=1;'])])
    add('canonical_to_host_image','canonical_image','host_image',['signed96 canonical read_data','read_valid/address','copy_fire/commit'],[
        stage('canonical_read_response','canonical_image',0,image,['read_data'],'read_valid',['read_address_out'],['read_data<=$signed({{64{ram_q[read_bank_d][31]}},ram_q[read_bank_d]});','read_valid<=1;read_address_out<=read_address_d;']),
        ram_stage('host_shadow_read_q','host_image',1,'Canonical response commits every word to separate real host RAM before publication. A later accepted scalar/row request reads that RAM q. Edge1 is a minimum storage/read barrier, not same-edge write+read; caller arbitration forbids collisions, and N copy+h/d costs remain separately counted.')])
    spec=dict(schema='prefit-structural-inventory-v1',scope='whole_core',
              identity=dict(top=m['top'],device=m['device'],parameters=m['core_parameters'],clock_period_ns=10,seed=1),
              sources={'rtl/'+name:pin for name,pin in m['source_sha256'].items()},settings={**m['control_sha256'],'manifest.json':PROJECT_PIN},
              blocks=blocks,transfers=transfers,
              exclusions=[dict(kind='external_virtual_io',reason='Virtual host/control/status pins are not board I/O timing or throughput sign-off.',endpoints=['external scalar host','external FIFO control producer','external diagnostics']),
                          dict(kind='external_reset',reason='Asynchronous reset-release/board distribution is not signed off by this source inventory; no false path was added to this project.',endpoints=['rst_n','asynchronous reset pins']),
                          dict(kind='inside_single_macroblock',reason='Each field contains its exact shared CT/GS/small correction/term-cache pipeline. Their internal timing and placement remain physical report work, not inferred from registered transfer declarations.',endpoints=['field0 internals','field1 internals','field2 internals']),
                          dict(kind='inside_single_macroblock',reason='Phase-local counters, descriptor admission, true-last selector and publication/control wiring stay within their named controllers; no timing completeness claim.',endpoints=['host_control internals','arithmetic_control internals','warm_control internals','canonical_control internals','canonical_image serial fold internals'])],
              coverage_claim='declared_source_inventory_not_netlist_completeness')
    result=source_inventory(project,spec)
    if result['findings']:raise ValueError('S4_WHOLE_DECLARED_STRUCTURE_FINDINGS:'+repr(result['findings']))
    destination.mkdir();(destination/'inventory.json').write_text(json.dumps(spec,indent=2)+'\n')
    r=dict(status='PASS_declared_whole_source_inventory_only',**identities(spec),project_manifest_sha256=PROJECT_PIN,
           inventory_sha256=sha(destination/'inventory.json'),checker_sha256=CHECKER_PIN,compiled_sv=49,
           transfers=len(transfers),source_inventory=result,fit_allowed=False,
           limitations=['Not mapped crossing completeness or STA','ActualfullNnative and ordinary fit-owner resources/budget/horizon admission remain pending','No field exemption/wholeclock/area/promotion inheritance'],promotion_allowed=False)
    (destination/'source-preparation.json').write_text(json.dumps(r,indent=2)+'\n');return r


if __name__=='__main__':
    import sys
    print(json.dumps(prepare(sys.argv[1]),indent=2))
