"""Build A4b's isolated project and explicit pre-fit transfer inventory only.

No vendor execution. The result is deliberately BLOCKED until native exhaustive
cross-block coverage and supported Design Assistant evidence are available.
"""
import hashlib
import json
from pathlib import Path
import shutil
from fpga.reference.track_a4_core_source_v4 import verify
from fpga.tools.prefit_structural_guard_v1 import evaluate,SCHEMA,file_digest

ROOT=Path(__file__).resolve().parents[1]
PARENT='results/throughput-20260929/track-a4-p4-provisional-fit-stage-v1/project'
PARENT_PIN='7fe6e4558f4bc425d3ddd91b350edba0ed99eea235f307c3a03cefff8ca4e7ff'
TICKET='docs/briefs/replies/2026-10-01-B20260930A-A4-core-registered-admission-ticket-v4.json'
TICKET_PIN='e3ca5d1132ae238e4ec23a0404ecc4e0ec5c1901d6bfc2a01a3a8458f86cc7b5'

def stage(name,owner,source,edge,payload,valid,metadata,anchor):
    return dict(id=name,owner=owner,source='rtl/'+source,kind='flop',edge=edge,
        payload=payload,valid=valid,metadata=metadata,anchors=[anchor],alignment='same_accepted_edge')

def inventory(manifest):
    cold='genefer_track_a4_cold_prefill_v1.sv';transfer='genefer_track_a4_field_transfer_v2.sv';backend='genefer_track_a4_square_backend_v4.sv'
    blocks=['host','cold_prefill','field_transfer','field_lanes','post','crt','carry','backend']
    entries=[]
    def add(name,producer,consumer,signals,stages,**extra):
        entries.append(dict(id=name,producer=producer,consumer=consumer,signals=signals,registered_stages=stages,**extra))
    add('image_to_cold_payload','host','cold_prefill',['effective_words','response_valid','tag','mask','generation'],[
        stage('cold_source','cold_prefill',cold,0,['source_words'],['capture_valid[0]'],['source_tag','latched_generation'],
            'for(int lane=0;lane<16;lane=lane+1)source_words[lane*32+:32]<=image_read_words[lane*33+:32];'),
        stage('cold_destination','cold_prefill',cold,1,['destination_words'],['capture_valid[1]'],['destination_tag','latched_generation'],
            'if(capture_valid[0])destination_words<=source_words;')])
    write_stages=[
        stage('field_write_source','field_transfer',transfer,0,['source_write_words[f]'],['request_write[0]'],['source_write_offset','source_write_mask'],
            'if(write_en)source_write_words[f*512+:512]<=write_words[f*512+:512];'),
        stage('field_write_destination','field_lanes',transfer,1,['destination_write_words[f]'],['request_write[1]'],['destination_write_offset','destination_write_mask'],
            'if(request_write[0])destination_write_words[f*512+:512]<=source_write_words[f*512+:512];')]
    add('cold_residues_to_fields','cold_prefill','field_lanes',['prefill_words','prefill_write','offset','mask'],write_stages)
    add('normal_and_patch_to_fields','post','field_lanes',['normal_or_patch_words','post_write','offset','mask'],write_stages)
    add('field_responses_to_crt','field_lanes','crt',['three_field_words','valid','offsets','masks'],[
        stage('return_source','field_transfer',transfer,0,['response_source_words[f]'],['response_valid[0]'],['response_source_masks','response_source_offsets'],
            'if(&field_read_valid)response_source_words[f*512+:512]<=field_read_words[f*512+:512];'),
        stage('return_destination','post',transfer,1,['response_destination_words[f]'],['response_valid[1]'],['response_destination_masks','response_destination_offsets'],
            'if(response_valid[0])response_destination_words[f*512+:512]<=response_source_words[f*512+:512];')])
    add('crt_coefficients_to_carry','crt','carry',['coefficient','valid','offset'],[
        stage('crt_output','crt','genefer_crt3_27_mont_pipe.sv',0,['coefficient'],['out_valid'],['parallel crt_tag[15]'],
            'if(valid_pipe[14])coefficient<=centered_work;'),
        stage('carry_divider_input','carry','genefer_div_recip_precision.sv',1,['magnitude'],['valid[0]'],['payloads[0]'],
            "magnitude<=MAG_W'(value<0 ? $unsigned(-value) : $unsigned(value));")])
    add('carry_digits_to_image','carry','host',['post_image_words','valid','offset','mask'],[
        stage('image_source','backend',backend,0,['image_source_words'],['image_write_valid[0]'],['image_source_offset','image_source_mask'],
            'if(post_image_write)begin image_source_words<=post_image_words;image_source_offset<=post_image_offset;image_source_mask<=post_image_mask;end'),
        stage('image_destination','backend',backend,1,['image_destination_words'],['image_write_valid[1]'],['image_destination_offset','image_destination_mask'],
            'if(image_write_valid[0])begin image_destination_words<=image_source_words;image_destination_offset<=image_source_offset;image_destination_mask<=image_source_mask;end')])
    add('carry_boundary_to_image','carry','host',['boundary_low','boundary_high','boundary_valid'],[
        stage('boundary_source','backend',backend,0,['low_source','high_source'],['image_boundary_valid[0]'],[],
            'if(post_boundary)begin low_source<=post_low;high_source<=post_high;end'),
        stage('boundary_destination','backend',backend,1,['low_destination','high_destination'],['image_boundary_valid[1]'],[],
            'if(image_boundary_valid[0])begin low_destination<=low_source;high_destination<=high_source;end')])
    add('operation_config','host','backend',['base','generation'],[
        stage('host_operation','host','genefer_track_a4_control_fsm_v2.sv',0,['base_reg'],['setup_valid'],['generation'],
            'base_reg<=new_base;limit_reg<=bus.setup_coefficient_limit;'),
        stage('backend_operation','backend',backend,1,['base_reg'],['begin_square accepted IDLE'],['generation_reg'],
            'state<=prefilled ? NTT_START : COLD_START;base_reg<=base;generation_reg<=generation;was_prefilled<=prefilled;')])
    add('ntt_admission_control','backend','field_lanes',['start_ntt'],[
        stage('ntt_admission','backend',backend,0,['ntt_admission'],['ntt_admission'],['operation_latched base/generation'],
            'NTT_START:if(admit_ntt)begin ntt_admission<=1;state<=NTT_LAUNCH;end')],
        exception=dict(kind='phase_local_control',reason='Isolated one-edge non-payload admission token; field payload paths have two stages. Current raw ownership rejects source transfers; cancellation follows the edge. Native RAM-access boundary gate required; no complete physical closure asserted.',contract_anchors=[dict(source='rtl/'+backend,text='wire start_ntt=ntt_admission && !fault && !cancel;')]),
        control_reconvergence=[dict(signal='image_legal -> prefill_write -> transfer_quiet',sink='field RAM block-port enable',registered_barrier='ntt_admission')])
    return dict(schema=SCHEMA,scope='whole_core',identity=dict(top=manifest['top'],device=manifest['device'],parameters={'AW':16},clock_period_ns=10.0,seed=1),
        sources={'rtl/'+name:pin for name,pin in manifest['source_sha256'].items()},settings={},blocks=blocks,transfers=entries,
        exclusions=[dict(kind='external_virtual_io',endpoints=['host command/response top-level pins'],reason='Pinned virtual I/O and SDC exclusions; not board timing.'),
            dict(kind='external_reset',endpoints=['rst_n'],reason='Pinned asynchronous reset constraint; does not exclude operational fault/valid nets.'),
            dict(kind='inside_single_macroblock',endpoints=['host word/canonical service inside host'],reason='Not a host-to-field transfer; local host source review/native gates remain separate.')],
        coverage_claim='declared_source_inventory_not_netlist_completeness',
        unresolved_native_coverage=['Image correction/shadow fanout into patch reducers; enumerate exact post-synthesis endpoints.',
            'Registered child-error/global-cancel fanout and field-transfer protocol-fault reconvergence need exhaustive native crossing capture.',
            'Stage source anchors record intent, not physical register retention/location or netlist coverage.'])

def prepare(output):
    output=Path(output).resolve();assert not output.exists() and not (ROOT/'docs/briefs/PAUSE').exists()
    assert file_digest(ROOT/PARENT/'manifest.json')==PARENT_PIN and file_digest(ROOT/TICKET)==TICKET_PIN
    verify();ticket=json.loads((ROOT/TICKET).read_text());parent=json.loads((ROOT/PARENT/'manifest.json').read_text())
    compiled=[p for p in ticket['native_sources'] if p.endswith('.sv')]
    for p in compiled:assert file_digest(ROOT/p)==ticket['source_sha256'][p]
    project=output/'project';(project/'rtl').mkdir(parents=True)
    for p in compiled:shutil.copyfile(ROOT/p,project/'rtl'/Path(p).name)
    for name,pin in parent['control_sha256'].items():
        raw=(ROOT/PARENT/name).read_bytes();assert hashlib.sha256(raw).hexdigest()==pin
        if name=='probe.qsf':raw=raw.replace(b'genefer_track_a4_core_v3',b'genefer_track_a4_core_v4').replace(b'genefer_track_a4_square_backend_v3',b'genefer_track_a4_square_backend_v4')
        (project/name).write_bytes(raw)
    manifest=dict(status='source_only_A4b_project_not_dispatched',top='genefer_track_a4_core_v4',device=parent['device'],clock_period_ns=10.0,seed=1,
        core_parameters={'AW':16},source_sha256={Path(p).name:file_digest(ROOT/p) for p in compiled},
        control_sha256={name:file_digest(project/name) for name in parent['control_sha256']},
        parent_manifest_sha256=PARENT_PIN,source_ticket_sha256=TICKET_PIN,compile_processors=6,bitstream_generation=False,promotion_allowed=False,
        note='No fit launch authority; shared source/vendor pre-fit and budget/slot gates still mandatory. Isolated v4 admission cut only.')
    (project/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    spec=inventory(manifest);spec['settings']=dict(manifest['control_sha256'],**{'manifest.json':file_digest(project/'manifest.json')})
    result=evaluate(project,spec)
    (output/'inventory.json').write_text(json.dumps(spec,indent=2)+'\n')
    (output/'source-check.json').write_text(json.dumps(result,indent=2)+'\n')
    return result
