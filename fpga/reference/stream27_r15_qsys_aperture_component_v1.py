"""Exact full-address guard interfaces; never narrow before validation."""


def component():
    lines=['package require -exact qsys 26.1',
      'set_module_property NAME r15_dma_aperture_v1',
      'set_module_property VERSION 1.0',
      'set_module_property INTERNAL false',
      'set_module_property EDITABLE false',
      'set_module_property INSTANTIATE_IN_SYSTEM_MODULE true',
      'add_fileset synthesis_fileset QUARTUS_SYNTH ""',
      'set_fileset_property synthesis_fileset TOP_LEVEL genefer_stream27_r15_dma_aperture_v1',
      'add_fileset_file genefer_stream27_r15_dma_aperture_v1.sv SYSTEM_VERILOG PATH {rtl/genefer_stream27_r15_dma_aperture_v1.sv}',
      'add_interface clock clock sink',
      'add_interface_port clock clk clk Input 1',
      'add_interface reset reset sink',
      'set_interface_property reset associatedClock clock',
      'set_interface_property reset synchronousEdges DEASSERT',
      'add_interface_port reset reset reset Input 1',
      'add_interface fault conduit end',
      'set_interface_property fault associatedClock clock',
      'set_interface_property fault associatedReset reset',
      'add_interface_port fault fault_valid valid Output 1',
      'add_interface_port fault fault_ready ready Input 1',
      # Diagnostic output only. The authoritative fault handshake is above.
      'add_interface diagnostic conduit end',
      'add_interface_port diagnostic protocol_error export Output 1',
      'set_interface_property diagnostic ENABLED false']
    for name,prefix,master,write in [('write_in','wr',False,True),
        ('write_out','down_wr',True,True),('read_in','rd',False,False),
        ('read_out','down_rd',True,False)]:
        lines.append(f'add_interface {name} avalon '+('start' if master else 'end'))
        props={'associatedClock':'clock','associatedReset':'reset','addressUnits':'SYMBOLS',
          'bitsPerSymbol':'8','burstcountUnits':'WORDS','constantBurstBehavior':'false',
          'maximumPendingReadTransactions':'0' if write else '1'}
        if not master:props.update(readLatency='0',readWaitTime='0',writeWaitTime='0',
            isMemoryDevice='false',isNonVolatileStorage='false')
        for k,v in props.items():lines.append(f'set_interface_property {name} {k} {v}')
        ports=[('address',64,True),('burstcount',5,True),
               ('write' if write else 'read',1,True),('waitrequest',1,False)]
        ports += [('writedata',256,True),('byteenable',32,True)] if write else [
            ('readdata',256,False),('readdatavalid',1,False)]
        for role,width,request in ports:
            direction='Output' if master==request else 'Input'
            lines.append(f'add_interface_port {name} {prefix}_{role} {role} {direction} {width}')
    return '\n'.join(lines)+'\n'
