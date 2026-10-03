"""Private source-locked real shell; native application and vendor scopes differ.

Enabled source is exactly the actually generated guarded AW16 system. This
closes source wiring and constraints, not FPGA fit/clock/board qualification.
"""
import copy
import hashlib
import json
import re
from pathlib import Path
from .stream27_r15_pcie_application_bind_v4 import application
from . import stream27_r15_board_glue_v2 as board
from . import stream27_r15_board_constraints_v1 as constraints
from .stream27_r15_generated_clock_proof_v1 import proof as clock_proof
from .stream27_r15_bar2_offset_proof_v1 import proof as bar_proof

ROOT=Path(__file__).resolve().parents[1]
SELF='reference/stream27_r15_pcie_shell_bind_v1.py'
BASE=ROOT/'results/throughput-20260929/r15-pcie-system-generation-v2-artifacts'
INPUT='results/throughput-20260929/trackS-r15-real-pcie-shell-v2/system-source-v2/input-manifest.json'
INPUT_PIN='adeeb37d0dd13a7c023586b01c1ab9ea4bbaeb7a21ae059821ad70ca44e19979'
COLLECTION_PIN='da96974cfbb57fd537e6f2fa4cdcf4c2187b94fe6158b0a4f5cd6f62d9f0281e'
GUARD='rtl/kernel/genefer_stream27_r15_dma_aperture_v1.sv'
GUARD_PIN='244ec8e67e8f61dddc3cb7c91f82ebe17fb92de2252a13fd3e55fccbc90fd644'


def sha(raw):return hashlib.sha256(raw).hexdigest()


def observed_sources():
    raw=(BASE/'full-collection.json').read_bytes()
    if sha(raw)!=COLLECTION_PIN:raise ValueError('R15_SHELL_COLLECTION_PIN')
    collection=json.loads(raw);files={}
    for row in collection['files']:
        name=row['path'];path=BASE/name
        if Path(name).is_absolute() or '..' in Path(name).parts or path.is_symlink() or not path.is_file():
            raise ValueError('R15_SHELL_VENDOR_REGULAR_FILE')
        data=path.read_bytes()
        if len(data)!=row['size'] or sha(data)!=row['sha256']:raise ValueError('R15_SHELL_VENDOR_DRIFT '+name)
        files[name]=row['sha256']
    if len(files)!=345:raise ValueError('R15_SHELL_VENDOR_CARDINALITY')
    roots=sorted(p for p in files if p.endswith('.qip'))
    if len(roots)!=5:raise ValueError('R15_SHELL_FIVE_GENERATED_QIP_ROOTS')
    return files,roots


def aperture_wiring():
    path=BASE/board.GENERATED;raw=path.read_bytes();text=raw.decode()
    # Whitespace-insensitive port binding: direct full64 HIP address wires
    # enter the guard. Generated width adaptation is strictly downstream.
    bindings={'wr_address':'pcie_dma_rd_master_address','rd_address':'pcie_dma_wr_master_address',
      'fault_valid':'aperture_fault_valid','fault_ready':'app_aperture_fault_ready',
      'external_fault_valid':'aperture_fault_valid','external_fault_ready':'app_aperture_fault_ready'}
    for port,wire in bindings.items():
        if len(re.findall(r'\.'+port+r'\s*\(\s*'+wire+r'\s*\)',text))!=1:
            raise ValueError('R15_SHELL_GUARD_BINDING '+port)
    for wire in ('pcie_dma_rd_master_address','pcie_dma_wr_master_address'):
        if not re.search(r'wire\s+\[63:0\]\s+'+wire+r'\s*;',text):raise ValueError('R15_SHELL_FULL64_BEFORE_GUARD')
    return dict(schema='r15-aperture-generated-wiring-v1',generated_top_sha256=sha(raw),
      bindings=bindings,full64_before_guard=True,guard_sha256=GUARD_PIN,
      fault_tail='Previously offered downstream VALID remains stable until accepted or reset; a pre-fault accepted host read still stalled downstream can require common reset, without fake completion.',
      vendor_functional_simulation=False)


def warnings():
    raw=(ROOT/board.RECEIPT).read_bytes()
    if sha(raw)!=board.RECEIPT_PIN:raise ValueError('R15_SHELL_GENERATION_RECEIPT')
    report=json.loads(json.loads(raw)['stdout']);records=[]
    for result in report['results']:
        if type(result['returncode']) is not int or result['returncode']!=0:raise ValueError('R15_SHELL_GENERATION_FAILURE')
        for stream in ('stdout','stderr'):
            for line in result.get(stream,'').splitlines():
                if re.search(r'\bError:',line):raise ValueError('R15_SHELL_GENERATION_ERROR')
                if not re.search(r'\bWarning:',line):continue
                if 'Quartus project not specified' in line or 'does not support specifying an output directory' in line:
                    disposition='Generation-location warning; actual private outputs and project are hash-closed, never inferred from requested output directory.'
                elif 'pcie.cra' in line:
                    disposition='Optional unused CRA interface is tied inactive in closed board wiring; no CRA software access or clocking claim.'
                elif 'Reconfiguration profile' in line or 'hssi_rx_pld_pcs_interface_hd_chnl_hrdrstctl_en' in line:
                    disposition='Retained installed vendor PHY-profile warning. No profile refresh or vendor patch; native synthesis and later physical/link qualification must resolve actual applicability. Not a warning-free or hardware-ready claim.'
                else:raise ValueError('R15_SHELL_UNKNOWN_GENERATION_WARNING '+line)
                records.append(dict(raw=line,disposition=disposition))
    return dict(scope='source-owner generation diagnostic classification, not independent signoff',
                warnings=records,warning_free=False,vendor_profile_runtime_qualified=False)


def bind(bundle, *, pcie_shell=0):
    if type(pcie_shell) is not int or pcie_shell not in (0,1):
        raise ValueError('R15_PCIE_FLAG')
    if not pcie_shell:
        return copy.deepcopy(bundle)
    raw=(ROOT/INPUT).read_bytes()
    if sha(raw)!=INPUT_PIN:raise ValueError('R15_SHELL_GENERATION_INPUT_PIN')
    captured=json.loads(raw);b=application(bundle)
    if b['parameters']!=captured['parameters'] or b['top']!=captured['component_top']:
        raise ValueError('R15_REAL_SHELL_NOT_READY_FOR_UNCAPTURED_PARAMETERS')
    app_sources={p:sha(b['files'][p].encode()) for p in b['rtl_sources']}
    if len(app_sources)!=70 or any(captured['files'].get('rtl/'+p)!=h for p,h in app_sources.items()):
        raise ValueError('R15_SHELL_LITERAL_CAPTURED_APPLICATION')
    files,roots=observed_sources();board_text,board_record=board.emit()
    guard=(ROOT/GUARD).read_bytes()
    if sha(guard)!=GUARD_PIN:raise ValueError('R15_SHELL_GUARD_PIN')
    # Bind the ACTUAL generated user-source copies, not merely an equal local
    # helper output disconnected from QIP compilation.
    compiled={}
    for name,pin in dict(app_sources,**{Path(GUARD).name:GUARD_PIN}).items():
        matches=[p for p,h in files.items() if p.startswith('ip/') and p.endswith('/synth/'+name) and h==pin]
        if len(matches)!=1:raise ValueError('R15_SHELL_GENERATED_CUSTOM_COPY '+name)
        compiled[name]=matches[0]
    b['files'][Path(GUARD).name]=guard.decode();b['files'][board.TOP+'.sv']=board_text
    b['top']=board.TOP;b['parameters']={};b['rtl_sources']=list(b['files'])
    b['generated_sha256']={p:sha(t.encode()) for p,t in b['files'].items()}
    extra=[SELF,GUARD,INPUT,board.RECEIPT,'reference/stream27_r15_board_glue_v1.py',
      'reference/stream27_r15_board_glue_v2.py','reference/stream27_r15_board_constraints_v1.py',
      'reference/stream27_r15_generated_clock_proof_v1.py','reference/stream27_r15_bar2_offset_proof_v1.py',
      'config/r15-pcie-reference-v1.json','synthesis/r15_application_cdc_v1.sdc','synthesis/r15_application_cdc_v1.qsf']
    for p in extra:
        b['source_dependencies'].append(p);b['source_sha256'][p]=sha((ROOT/p).read_bytes())
    b['r15_host_link']['real_pcie_ip_ready']=True
    b['r15_real_shell']=dict(schema='r15-real-shell-source-v1',status='SOURCE_CLOSED_NATIVE_AND_PHYSICAL_GATES_SEPARATE',
      parameter_binding='source-locked-qsys',effective_parameters=captured['effective_parameters'],
      application_component_top=captured['component_top'],application_sources=app_sources,
      guard_sources={Path(GUARD).name:GUARD_PIN},board_sources={board.TOP+'.sv':sha(board_text.encode())},
      board_static_proof=board_record,aperture_wiring=aperture_wiring(),
      vendor_root=str(BASE),vendor_sources=files,qip_roots=roots,generated_custom_copies=compiled,
      generation_receipt=dict(path=board.RECEIPT,sha256=board.RECEIPT_PIN),
      generation_input=dict(path=INPUT,sha256=INPUT_PIN),generated_entrypoint='private_project.qsf',
      clock_proof=clock_proof(BASE,'r15_pcie_system_v2'),bar2_proof=bar_proof(BASE,'r15_pcie_system_v2'),
      generation_diagnostics=warnings(),pin_qsf=constraints.pins(),base_sdc=constraints.base_clocks(),
      cdc_sdc=(ROOT/'synthesis/r15_application_cdc_v1.sdc').read_text(),
      cdc_qsf=(ROOT/'synthesis/r15_application_cdc_v1.qsf').read_text(),
      vendor_simulation_ready=False,fit_qualified=False,board_qualified=False,
      native_application_gate_required=True,native_aperture_gate_required=True,
      compute_only_audit_search_inheritance=False,automatic_link_retrain_or_FLR_recovery=False)
    return b
