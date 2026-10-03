"""Exact R15 application component description, not generated vendor IP.

All Avalon addresses are byte/SYMBOL addresses. The system generator must
decode the full upstream64 address before these narrowed relative ports.
Generating this description alone does not prove that decoder or real I/O.
"""
import re


def component(bundle):
    if not bundle.get('r15_shell_application') or bundle['parameters'].get('PCIE_SHELL')!=1:
        raise ValueError('R15_QSYS_REQUIRES_APPLICATION')
    top=bundle['top']
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*',top):
        raise ValueError('R15_QSYS_TOP_IDENTIFIER')
    lines=['package require -exact qsys 26.1',
      'set_module_property NAME r15_application_v1',
      'set_module_property VERSION 1.0',
      'set_module_property INTERNAL false',
      'set_module_property EDITABLE false',
      'set_module_property INSTANTIATE_IN_SYSTEM_MODULE true',
      'add_fileset synthesis_fileset QUARTUS_SYNTH ""',
      f'set_fileset_property synthesis_fileset TOP_LEVEL {top}']
    for name in bundle['rtl_sources']:
        if not re.fullmatch(r'[A-Za-z0-9_.]+\.sv',name):
            raise ValueError('R15_QSYS_FLAT_RTL_PATH')
        lines.append(f'add_fileset_file {{{name}}} SYSTEM_VERILOG PATH {{rtl/{name}}}')
    for name,value in bundle['parameters'].items():
        if not re.fullmatch(r'[A-Z][A-Z0-9_]*',name) or type(value) is not int or value<0:
            raise ValueError('R15_QSYS_PARAMETER')
        lines += [f'add_parameter {name} INTEGER {value}',
                  f'set_parameter_property {name} HDL_PARAMETER true',
                  f'set_parameter_property {name} ALLOWED_RANGES {{{value}}}']
    for name,port in [('pcie_clock','pcie_clk'),('core_clock','core_clk')]:
        lines += [f'add_interface {name} clock sink',
                  f'add_interface_port {name} {port} clk Input 1']
    lines += ['add_interface hip_reset reset sink',
              'set_interface_property hip_reset associatedClock pcie_clock',
              'set_interface_property hip_reset synchronousEdges DEASSERT',
              'add_interface_port hip_reset hip_reset_n reset_n Input 1']
    for name,port in [('board_reset','board_perst_n'),('pll_status','pll_locked')]:
        lines += [f'add_interface {name} conduit end',
                  f'add_interface_port {name} {port} export Input 1']
    buses={
      'control':('ctrl',12,32,[('read','Input',1),('write','Input',1),('writedata','Input',32),
                  ('byteenable','Input',4),('waitrequest','Output',1),('readdata','Output',32),('readdatavalid','Output',1)]),
      'cold':('cold',22,256,[('write','Input',1),('writedata','Input',256),('byteenable','Input',32),
                  ('burstcount','Input',5),('waitrequest','Output',1)]),
      'export':('export',23,256,[('read','Input',1),('burstcount','Input',5),
                  ('waitrequest','Output',1),('readdata','Output',256),('readdatavalid','Output',1)])}
    for name,(prefix,address_width,data_width,ports) in buses.items():
        lines += [f'add_interface {name} avalon end']
        props={'associatedClock':'pcie_clock','associatedReset':'hip_reset',
          'addressUnits':'SYMBOLS','bitsPerSymbol':'8','burstcountUnits':'WORDS',
          'constantBurstBehavior':'false','readLatency':'0','readWaitTime':'0','writeWaitTime':'0',
          'maximumPendingReadTransactions':('0' if name=='cold' else '1'),
          'isMemoryDevice':'false','isNonVolatileStorage':'false'}
        for k,v in props.items():lines.append(f'set_interface_property {name} {k} {v}')
        lines.append(f'add_interface_port {name} {prefix}_address address Input {address_width}')
        for role,direction,width in ports:
            lines.append(f'add_interface_port {name} {prefix}_{role} {role} {direction} {width}')
    return '\n'.join(lines)+'\n'
