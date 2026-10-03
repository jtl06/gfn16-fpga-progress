"""Declared real-shell source transfers, not synthesized graph completeness.

Rebinds the existing compute inventory to the active host/ACK clone, then
declares loader, CDC and custom/vendor interfaces. The old single-clock
virtual-I/O project checker cannot admit this multiple-clock/QIP project.
"""
import copy
import hashlib
import json
from pathlib import Path
from . import stream27_r15_all_shell_bind_v2 as source

ROOT = source.ROOT
SELF = 'reference/stream27_r15_real_shell_inventory_v1.py'
COMPUTE = 'results/throughput-20260929/trackS-r15-compute-physical-v1/physical-12000-v1/structural-inventory.json'
PROJECT = 'results/throughput-20260929/trackS-r15-real-pcie-shell-v2/physical-source-v4/project'


def sha(raw):
    return hashlib.sha256(raw.encode() if isinstance(raw, str) else raw).hexdigest()


def need(ok, why):
    if not ok:
        raise ValueError('R15_REAL_INVENTORY_' + why)


def build(bundle, project=ROOT/PROJECT):
    project = Path(project).resolve()
    need(project.is_relative_to(ROOT), 'BOUNDED_PROJECT')
    manifest = json.loads((project/'manifest.json').read_bytes())
    real = bundle['r15_real_shell']
    need(manifest['source_sha256'] == bundle['generated_sha256'] and
         manifest['top'] == bundle['top'] and manifest['core_parameters'] == {} and
         manifest['r15_real_shell']['effective_parameters'] == real['effective_parameters'],
         'EXACT_CORRECTED_PROJECT')
    need(real['aperture_wiring']['registered_response_credit_only'], 'REGISTERED_CREDIT')
    prior = json.loads((ROOT/COMPUTE).read_bytes())
    need(len(prior['transfers']) == 26, 'PINNED_COMPUTE_ROSTER')
    old_host = 'rtl/' + prior['identity']['top'] + '.sv'
    host = 'rtl/' + bundle['r15_host_port_instrumentation']['parent_top'] + '_r15_host_ports_v1.sv'
    ack = 'rtl/genefer_stream27_r15_host_image_ack_v1.sv'
    edits = bundle['r15_host_port_instrumentation']['edits']

    def remap(value):
        if isinstance(value, dict):
            return {k: remap(v) for k, v in value.items()}
        if isinstance(value, list):
            return [remap(v) for v in value]
        if not isinstance(value, str):
            return value
        value = value.replace(old_host, host).replace(
            'rtl/genefer_stream27_host_image_rowwrite_v1.sv', ack)
        for before, after in edits:
            value = value.replace(before, after)
        return value

    spec = remap(copy.deepcopy(prior))
    spec['exclusions'] = [x for x in spec['exclusions'] if x['kind'] != 'external_virtual_io']
    spec['identity'] = {k: manifest[k] for k in ('top', 'device', 'clock_period_ns', 'seed')}
    spec['identity']['parameters'] = {}
    spec['sources'] = {'rtl/'+n: h for n, h in bundle['generated_sha256'].items()}
    spec['settings'] = dict(manifest['control_sha256'], **{'manifest.json': sha((project/'manifest.json').read_bytes())})
    spec['blocks'] += ['pcie_application', 'command_CDC', 'core_executor',
                       'direct_loader', 'response_CDC', 'reset_session_fence',
                       'dma_aperture', 'vendor_HIP_interconnect']
    app = 'rtl/' + real['application_component_top'] + '.sv'
    endpoint = 'rtl/genefer_stream27_r15_pcie_avmm_v1.sv'
    fifo = 'rtl/genefer_stream27_r15_async_fifo_v1.sv'
    executor = 'rtl/genefer_stream27_r15_core_transport_v1.sv'
    loader = 'rtl/genefer_stream27_r15_raw_loader_v1.sv'
    guard = 'rtl/genefer_stream27_r15_direct_write_guard_v1.sv'
    reset = 'rtl/genefer_stream27_r15_link_reset_v2.sv'
    aperture = 'rtl/genefer_stream27_r15_dma_aperture_v1.sv'
    board = 'rtl/' + bundle['top'] + '.sv'
    direct = 'rtl/' + bundle['r15_shell_application']['component_top'] + '.sv'

    def anchor(file, text):
        return dict(source=file, text=text)

    def stage(name, owner, edge, file, payload, valid, metadata, text, domain):
        return dict(id=name, owner=owner, edge=edge, kind='flop', source=file,
                    payload=payload, valid=valid, metadata=metadata, anchors=[text],
                    alignment='same_accepted_edge', clock_domain=domain)

    def transfer(name, producer, consumer, signals, anchors, reason, stages=()):
        spec['transfers'].append(dict(id=name, producer=producer, consumer=consumer,
            signals=signals, registered_stages=list(stages), control_reconvergence=[],
            exception=dict(kind='phase_local_control', reason=reason,
                           contract_anchors=[anchor(*a) for a in anchors])))

    transfer('pcie_packet_to_command_FIFO', 'pcie_application', 'command_CDC',
        ['command_push_data512', 'command_push_valid', 'command_push_ready'],
        [(app, '.wr_valid(command_push_valid),.wr_data(command_push_data),.wr_ready(command_push_ready),')],
        'Complete packet is held under backpressure and written only on actual ready/valid. Bounded8 entries, not N-sized staging.',
        [stage('pcie_held_command', 'pcie_application', 0, endpoint, ['cmd_data512'], 'cmd_valid',
               ['full56', 'session', 'lease', 'context', 'op'], 'cmd_data<=q;cmd_valid<=1;', 'pcie250'),
         stage('command_FIFO_write', 'command_CDC', 1, fifo, ['data512'], 'push',
               ['wbin', 'wgray'], 'always_ff @(posedge wr_clk)if(push)data[wbin[ADDR_W-1:0]]<=wr_data;', 'pcie250')])
    transfer('command_FIFO_to_core_executor', 'command_CDC', 'core_executor',
        ['command_pop_data512', 'command_pop_valid', 'command_pop_ready', 'Gray_pointer'],
        [(app, '.cmd_valid(command_pop_valid),.cmd_data(command_pop_data),.cmd_ready(command_pop_ready),.cmd_empty(!command_pop_valid),'),
         (fifo, 'assign rd_valid=rst_n && rd_release[1] && rd_enable && !empty;')],
        'Asynchronous payload is stable by held write slot and synchronized Gray pointer. Stage labels are ordinal, NOT a fixed cross-clock latency or an arithmetic stall.',
        [stage('command_Gray_read_sync', 'command_CDC', 0, fifo, ['wgray_r1', 'wgray_r2'], 'rd_release', [],
               'wgray_r1<=wgray;wgray_r2<=wgray_r1;', 'core12ns'),
         stage('executor_held_command', 'core_executor', 1, executor, ['held512'], 'state_EXECUTE',
               ['full56', 'session', 'lease', 'context', 'op'],
               'IDLE:if(cmd_valid && cmd_ready)begin held<=cmd_data;state<=EXECUTE;wait_count<=0;end', 'core12ns')])
    transfer('executor_to_direct_transaction', 'core_executor', 'direct_loader',
        ['dc_owner56', 'dc_session', 'dc_lease', 'dc_context', 'dc_index', 'dc_word', 'dc_begin', 'dc_commit'],
        [(executor, 'assign dc_commit=execute_good && op==COMMIT_LOAD && current_token && cmd_empty;'),
         (loader, '.commit_valid,.transport_empty(transport_empty && ack_count==(AW+1)\'(N) && !image_ack_expected),'),
         (guard, 'applied_count==(AW+3)\'(WORDS) && transport_empty && core_idle && profile_ok;')],
        'Raw N+32 ordered words, core-issued prospective full56 owner/session/lease, actual write ACK and empty-transport COMMIT. Retained PROFILE computation starts later, not pre-COMMIT hardware validation.')
    transfer('direct_loader_to_physical_shadow_ACK', 'direct_loader', 'shadow_images',
        ['image_write', 'image_context', 'image_address', 'image_data32', 'image_ready', 'image_ack'],
        [(ack, 'assign host_write_ready=host_fire;'),
         (ack, 'if(load_we)begin ram_we=1;ram_wa=host_addr[ROW_W-1:0];ram_w=write_data;end'),
         (loader, 'if(active && !cancel_ok && image_ack!=image_ack_expected)local_error<=1;')],
        'Selected idle context has its own physical image banks; actual port arbitration determines host_fire. Readiness is NOT ACK feedback. Held lease/context plus previous accepted write owns ACK; no residue staging or port-exclusivity inference from address alone.',
        [stage('physical_write_ACK', 'shadow_images', 0, ack, ['host_write_ack_d'], 'allow_access', [],
               'else host_write_ack_d<=host_fire && load_we;', 'core12ns')])
    transfer('committed_config_START_and_descriptor', 'core_executor', 'host_control',
        ['start_contexts', 'command_index32', 'command_generation8', 'command_double', 'command_context'],
        [(executor, 'assign start_contexts=execute_good && op==START_JOB && start_good ? start_mask:2\'b0;'),
         (executor, 'else if((busy & start_mask)==start_mask)respond(8\'d0,256\'b0);'),
         (direct, '.command_valid(command_valid && rst_n && dc_link_drained && !dc_error),')],
        'START checks BOTH idle and selected committed records/latest global lease, then ACKs admitted busy/generation. Functional descriptor ready/accept and typed underflow remain; PCIe backpressure never stalls active math. No public PROFILE-ready ACK is invented.')
    transfer('canonical_A_to_coherent_response', 'copy_publication', 'core_executor',
        ['read_data96', 'read_owner56', 'read_context', 'read_index32', 'read_valid', 'FINAL_status'],
        [(executor, 'if(read_context!=ctx || read_owner!=owner)begin sticky_error<=1;respond(8\'d2,256\'b0);end'),
         (executor, 'else respond(8\'d0,{read_data,index,8\'b0,read_owner[55:32],read_owner[31:0],session,(32\'h52314100|32\'(ctx))});')],
        'Only published idle canonical signed96 A with full56/session/context/index is exported. Host completes owned export after a FINAL coherent error fence; no raw B or repeated canonical finalization.')
    transfer('coherent_response_to_response_FIFO', 'core_executor', 'response_CDC',
        ['response_push_data512', 'response_push_valid', 'response_push_ready'],
        [(app, '.wr_valid(response_push_valid),.wr_data(response_push_data),.wr_ready(response_push_ready),'),
         (executor, 'assign resp_valid=state==RESPOND && link_ready;')],
        'Coherent snapshot is immutable under response stall; a later unrelated fault cannot revoke an already captured response. Common reset ends session authority.',
        [stage('executor_coherent_snapshot', 'core_executor', 0, executor, ['resp_data512'], 'state_RESPOND',
               ['session', 'full56_A', 'context', 'status'], "resp_data<='0;resp_data[3:0]<=op;resp_data[15:8]<=status;resp_data[16]<=ctx;", 'core12ns'),
         stage('response_FIFO_write', 'response_CDC', 1, fifo, ['data512'], 'push', ['wbin', 'wgray'],
               'always_ff @(posedge wr_clk)if(push)data[wbin[ADDR_W-1:0]]<=wr_data;', 'core12ns')])
    transfer('response_FIFO_to_PCIe_export', 'response_CDC', 'pcie_application',
        ['response_pop_data512', 'response_pop_valid', 'response_pop_ready', 'export_record256'],
        [(app, '.resp_valid(response_pop_valid),.resp_data(response_pop_data),.resp_ready(response_pop_ready),.protocol_error);')],
        'CDC response credit and owned canonical32-byte output framing remain. Valid/dont-care masks are not a throughput or automatic reconnect guarantee.',
        [stage('response_Gray_read_sync', 'response_CDC', 0, fifo, ['wgray_r1', 'wgray_r2'], 'rd_release', [],
               'wgray_r1<=wgray;wgray_r2<=wgray_r1;', 'pcie250'),
         stage('PCIe_received_snapshot', 'pcie_application', 1, endpoint, ['snapshot512'], 'resp_valid',
               ['status', 'session', 'context', 'lease'], 'snapshot<=resp_data;waiting<=0;', 'pcie250')])
    transfer('common_reset_session_to_domains', 'reset_session_fence', 'command_CDC',
        ['common_reset_n', 'pcie_reset_n', 'core_reset_n', 'session32', 'pcie_ready', 'core_ready'],
        [(reset, "else session_counter<=session_counter+32'd1;"),
         (reset, 'assign common_reset_n=external_reset_n && bootstrap[1] && !recovery_pending && !session_exhausted;'),
         (app, '.external_reset_n(board_perst_n && hip_reset_n && pll_locked),')],
        'PERST/HIP reset-status/PLL-lock only. Bilateral FIFO reset and per-domain synchronized release precede session reuse. No proven DLLdrop/retrain/FLR/VFIO/software common-reset delivery.',
        [stage('domain_reset_ready_sync', 'reset_session_fence', 0, reset,
               ['core_ready_p1', 'core_ready_p2'], 'common_reset_n', [],
               'core_ready_p1<=core_release[1];core_ready_p2<=core_ready_p1;', 'pcie250')])
    transfer('aperture_fault_to_ordered_ABORT', 'dma_aperture', 'pcie_application',
        ['external_fault_valid', 'external_fault_ready', 'protocol_error', 'ordered_ABORT'],
        [(aperture, 'wire response_credit=(rd_expected!=0);'),
         (endpoint, 'if(external_fault_accept)fault();'),
         (app, '.external_fault_valid,.external_fault_ready,')],
        'Registered outstanding-read credit removes the known downstream WAITREQUEST feedback SCC. Minimum downstream response is one edge. Origin fault joins existing ordered one-ABORT mechanism; offered downstream VALID may drain or require common reset, never fake completion.')
    transfer('vendor_full64_DMA_to_aperture', 'vendor_HIP_interconnect', 'dma_aperture',
        ['DMA_address64', 'DMA_data256', 'byteenable32', 'burstcount5', 'ready', 'read_credit'],
        [(aperture, 'input logic [63:0] wr_address,'),
         (aperture, 'input logic [63:0] rd_address,'),
         (board, '.pcie_refclk(clk_pcie1)')],
        'Actual generated full64 wires enter custom aperture BEFORE address adaptation. Five exact QIP trees/source map and aperture_wiring proof bind this trusted vendor boundary; no HIP native simulation or exhaustive vendor connectivity proof.')
    transfer('vendor_BAR2_to_control_offset', 'vendor_HIP_interconnect', 'pcie_application',
        ['BAR2_hit', 'BAR2_address_low12', 'control_read', 'control_write'],
        [(app, '.ctrl_address({52\'b0,ctrl_address}),.ctrl_read,.ctrl_write,.ctrl_writedata,.ctrl_byteenable,')],
        'Actual trusted HIP BAR2 hit gates Read/Write; aligned host BAR base may have nonzero high bits. Pinned source proof validates low12 offset, not arbitrary full64 DMA range equivalence or board/link behavior.')
    spec['clock_domains'] = dict(core_period_ns=12, hip_period_ns=4,
        board_osc_period_ns=10, pcie_reference_period_ns=10,
        edge_labels='Local sequential stage ordering only; no fixed cross-domain latency',
        actual_constraints=real['base_sdc']+real['cdc_sdc'],
        vendor_exceptions='Captured vendor HIP/transceiver SDC plus explicit application asynchronous/Gray/reset constraints; not zero-exception compute inheritance')
    spec['limitations'] = [x for x in spec['limitations'] if 'compute-only' not in x]
    spec['limitations'] += [
        'Declared source inventory, not QIP-elaborated/synthesized netlist completeness, timing proof, native Design Assistant signoff or physical admission.',
        'Source-locked real system has empty board-top HDL parameters; effective source constants include AW16/all six flags/EPOCH0/0. No compute clock/fault/native inheritance.',
        'Custom application and aperture own gates remain required; vendor HIP simulation, board/reset-release, automatic reconnect, host GL/rollback and programming are unqualified.']
    spec['exclusions'] += [dict(kind='inside_single_macroblock',
        endpoints=['vendor_HIP_interconnect PHY/DMA/Qsys internal graph'],
        reason='Actual five QIP roots and335-member source projection are hash-bound separately; internal vendor register/pin/routing coverage requires native elaboration and physical evidence, not custom source anchors.')]
    spec['source_owner_binding'] = dict(producer=SELF,
        producer_sha256=sha((ROOT/SELF).read_bytes()),
        central_source=dict(path=source.SELF, sha256=sha((ROOT/source.SELF).read_bytes())),
        compute_inventory=dict(path=COMPUTE, sha256=sha((ROOT/COMPUTE).read_bytes())),
        project_manifest_sha256=sha((project/'manifest.json').read_bytes()),
        retained_compute_transfers=26, native_or_physical_qualification_inherited=False,
        old_single_clock_source_inventory_checker_applicable=False)
    check_anchors(spec, project)
    return spec


def check_anchors(spec, project):
    """Source presence/uniqueness only; real-mode project guard is separate."""
    project = Path(project).resolve()
    texts = {n: (project/n).read_text() for n in spec['sources']}
    for n, h in spec['sources'].items():
        need(sha(texts[n]) == h, 'SOURCE_DRIFT:'+n)
    ids = [t['id'] for t in spec['transfers']]
    need(len(ids) == len(set(ids)), 'UNIQUE_TRANSFERS')
    for t in spec['transfers']:
        need(t['producer'] in spec['blocks'] and t['consumer'] in spec['blocks'], 'BLOCKS')
        for s in t['registered_stages']:
            for a in s['anchors']:
                need(texts[s['source']].count(a) == 1, 'STAGE_ANCHOR:'+t['id']+':'+a)
        for a in t.get('exception', {}).get('contract_anchors', []):
            need(texts[a['source']].count(a['text']) == 1, 'CONTRACT_ANCHOR:'+t['id']+':'+a['text'])
    for x in spec['exclusions']:
        for a in x.get('contract_anchors', []):
            need(texts[a['source']].count(a['text']) == 1, 'EXCLUSION_ANCHOR')
    return dict(declared_transfers=len(ids), source_anchor_findings=[],
                fit_allowed=False, source_only=True, netlist_complete=False)
