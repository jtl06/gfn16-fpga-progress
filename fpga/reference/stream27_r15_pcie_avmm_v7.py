"""Private additive external aperture-fault conduit over immutable endpoint v6.

Synchronous PCIe-domain valid/ready acceptance latches the existing sticky fault
and orders one ABORT after prior issued commands. No core-NBA/flush guarantee.
"""
from pathlib import Path
from . import stream27_r15_pcie_avmm_native_v1 as original

ROOT=original.ROOT
CAPTURE=ROOT/'results/throughput-20260929/trackS-r15-pcie-avmm-native-v6/normal-v6/source/fpga'/original.RTL
PARENT_SHA='0d7da30e13d687442541a8e3d1721ea069ffc3b1fd715b977a0e0cab4bf6f373'
SELF='reference/stream27_r15_pcie_avmm_v7.py'


def source():
    import hashlib
    raw=CAPTURE.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=PARENT_SHA:raise ValueError('R15_AVMM_V7_FROZEN_PARENT')
    text=raw.decode()
    changes=[
      (' output logic protocol_error\n',
       ' input logic external_fault_valid,\n output logic external_fault_ready,\n output logic protocol_error\n'),
      (' wire ctrl_active=ctrl_read||ctrl_write;',
       ' assign external_fault_ready=!reset && link_ready;\n wire external_fault_accept=external_fault_valid && external_fault_ready;\n wire ctrl_active=ctrl_read||ctrl_write;'),
      ('   if(resp_valid)begin',
       '   if(external_fault_accept)fault();\n   if(resp_valid)begin'),
      ('resp_data[15:8]==0 && resp_data[95:64]!=0 && resp_data[63:32]==waiting_session',
       'resp_data[15:8]==0 && !protocol_error && !held_violation && !external_fault_valid && resp_data[95:64]!=0 && resp_data[63:32]==waiting_session'),
      ('resp_data[15:8]==0?reg_read(read_address,resp_data):32\'b0',
       'resp_data[15:8]==0 && !protocol_error && !held_violation && !external_fault_valid?reg_read(read_address,resp_data):32\'b0'),
      ('if(resp_data[15:8]==0 && !protocol_error && !held_violation &&',
       'if(resp_data[15:8]==0 && !protocol_error && !held_violation && !external_fault_valid &&'),
      ('if(!cmd_valid && !waiting && !held_violation && !resp_valid)begin',
       'if(!cmd_valid && !waiting && !held_violation && !resp_valid && !external_fault_valid)begin'),
    ]
    # The A32 predicate anchor must be handled before the longer BEGIN edit,
    # whose prefix would otherwise be counted as another A32 anchor.
    changes[3],changes[5]=changes[5],changes[3]
    for before,after in changes:
        if text.count(before)!=1:raise ValueError('R15_AVMM_V7_UNIQUE_ANCHOR')
        text=text.replace(before,after,1)
    text=text.replace('abort_due||resp_valid||cmd_valid||waiting',
                      'abort_due||resp_valid||external_fault_valid||cmd_valid||waiting')
    return text.encode()
