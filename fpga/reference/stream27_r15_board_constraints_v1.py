"""Pinned community PCIe1 pin/clock inputs; no board or timing qualification.

This emits only observed board assignments. Generated IP clocks/exceptions and
the actual application CDC constraints must be added and closed separately.
"""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REFERENCE='config/r15-pcie-reference-v1.json'


def pins():
    r=json.loads((ROOT/REFERENCE).read_bytes())
    if r['commit']!='dc125eab3ea1d2c3e4fa62543868977a0142e019':
        raise ValueError('R15_BOARD_REFERENCE_CHANGED')
    c=r['clocks'];p=r['pcie1']
    lines=['# Community PCIe1 pin reference; physical board identity unverified.',
           '# No VIRTUAL_PIN assignments and no invented package/pin substitutions.']
    def location(name,pin):lines.append(f'set_location_assignment PIN_{pin} -to {{{name}}}')
    def io(name,standard):lines.append(f'set_instance_assignment -name IO_STANDARD {{{standard}}} -to {{{name}}}')
    location('clk_u59',c['board_core_source']['positive_pin']);io('clk_u59',c['board_core_source']['io_standard'])
    location('clk_pcie1',c['pcie_reference']['positive_pin'])
    location('clk_pcie1(n)',c['pcie_reference']['negative_pin']);io('clk_pcie1',c['pcie_reference']['io_standard'])
    location('pcie1_perstn',p['perst_n']['pin']);io('pcie1_perstn',p['perst_n']['io_standard'])
    for direction in ('rx','tx'):
        for lane in range(8):
            name=f'pcie1_{direction}[{lane}]'
            location(name,p[direction+'_positive'][lane])
            location(name+'(n)',p[direction+'_negative'][lane]);io(name,p['serial_io_standard'])
    return '\n'.join(lines)+'\n'


def base_clocks():
    return '''# Physical board inputs only, both100MHz; NEVER rewrite to12ns.
create_clock -name board_osc_100 -period 10.000 [get_ports {clk_u59}]
create_clock -name pcie_ref_100 -period 10.000 [get_ports {clk_pcie1}]
# Generated HIP/IOPLL SDC owns derived clocks. No fabricated kernel_clk.
# This fragment alone is NOT complete CDC/reset/I/O timing admission.
'''
