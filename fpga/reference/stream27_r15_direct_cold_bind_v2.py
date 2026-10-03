"""R15 direct loader successor: global host-authority containment.

Preserves the v1 captured generator and all arithmetic. A loader fault masks
external success/admission immediately; already admitted private core work may
drain internally until common reset. This is not a field-pipeline flush claim.
"""
import hashlib
from pathlib import Path
from .stream27_r15_direct_cold_bind import bind as parent_bind

ROOT=Path(__file__).resolve().parents[1]
SELF='reference/stream27_r15_direct_cold_bind_v2.py'


def bind(bundle, *, direct_cold=0, pcie_shell=0):
    b=parent_bind(bundle,direct_cold=direct_cold,pcie_shell=pcie_shell)
    if not direct_cold:return b
    old=b['top'];new=old+'_contained_v2';text=b['files'][old+'.sv']
    edits=[]
    def edit(a,z):
        nonlocal text
        if text.count(a)!=1:raise ValueError('R15_CONTAINMENT_ANCHOR '+a[:50])
        text=text.replace(a,z,1);edits.append((a,z))
    edit('module '+old+' #','module '+new+' #')
    edit(' wire candidate_read_valid;wire [1:0] candidate_canonical_ready;',
         ' wire candidate_read_valid;wire [1:0] candidate_canonical_ready;\n'
         ' wire candidate_command_ready,candidate_command_accept;\n'
         ' wire [1:0] candidate_operation_accept,candidate_done,candidate_warm_done,candidate_busy;\n'
         ' wire host_authority=rst_n && dc_link_drained && !dc_error && !core_error;\n'
         ' assign command_ready=candidate_command_ready && host_authority;\n'
         ' assign command_accept=candidate_command_accept && host_authority;\n'
         ' assign operation_accept=candidate_operation_accept & {2{host_authority}};\n'
         ' assign done=candidate_done & {2{host_authority}};\n'
         ' assign warm_done=candidate_warm_done & {2{host_authority}};\n'
         ' assign busy=candidate_busy & {2{host_authority}};')
    edit('assign read_valid=candidate_read_valid && dc_link_drained && !dc_error;',
         'assign read_valid=candidate_read_valid && host_authority;')
    edit('assign canonical_ready=candidate_canonical_ready & {2{dc_link_drained && !dc_error}};',
         'assign canonical_ready=candidate_canonical_ready & {2{host_authority}};')
    # Do not use core_error/command_ready in this incoming predicate: preserve
    # parent combinational authority without creating a feedback SCC.
    edit('  .error(core_error),.read_valid(candidate_read_valid),.canonical_ready(candidate_canonical_ready),',
         '  .command_valid(command_valid && rst_n && dc_link_drained && !dc_error),\n'
         '  .command_ready(candidate_command_ready),.command_accept(candidate_command_accept),\n'
         '  .operation_accept(candidate_operation_accept),.done(candidate_done),\n'
         '  .warm_done(candidate_warm_done),.busy(candidate_busy),\n'
         '  .error(core_error),.read_valid(candidate_read_valid),.canonical_ready(candidate_canonical_ready),')
    reverse=text
    for a,z in reversed(edits):reverse=reverse.replace(z,a,1)
    if reverse!=b['files'][old+'.sv']:raise ValueError('R15_CONTAINMENT_REVERSAL')
    del b['files'][old+'.sv']
    b['rtl_sources'].remove(old+'.sv')
    b['files'][new+'.sv']=text;b['rtl_sources'].append(new+'.sv');b['top']=new
    b['generated_sha256']={k:hashlib.sha256(v.encode()).hexdigest() for k,v in b['files'].items()}
    b['source_dependencies'].append(SELF)
    b['source_sha256'][SELF]=hashlib.sha256((ROOT/SELF).read_bytes()).hexdigest()
    b['r15_direct_cold']['global_fault_containment']={
        'masked':['read_valid','canonical_ready','command_ready','command_accept','operation_accept','done','warm_done','busy'],
        'descriptor_ingress':'Blocked after global loader fault; already accepted private tails can drain.',
        'counters_payload':'Diagnostic/dont-care without authority, not zeroized.',
        'edits':edits,'exact_v1_reversal':True}
    return b
