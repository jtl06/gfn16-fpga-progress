"""Mechanical matched registered-I/O wrapper from exact ANSI child sources.

This is a physical probe, not a cycle-compatible public adapter: non-clock/
reset inputs cross one register and outputs cross one further register. No
ready/valid, payload qualification, or child algorithm is rewritten.
"""
import hashlib
import re

CHILDREN={
 'genefer_ntt_banked27_prefetch_r2_host_broadcast_orient8_rootfused_engine':'b3d06d1e5f90e4944fdf88ff264cb7edbd73d0daf9f46ccf93389ab4889d9e3f',
 'genefer_ntt_banked27_prefetch_r2_host_broadcast_orient8_rootfused_lookahead_v1_engine':'e2f5120d9d9ba0c1ebe377dab6d8882d80e523528df8e99a833b38661cb015ee'}

def need(ok,why):
    if not ok:raise ValueError(why)

def interface(raw):
    need(type(raw) is bytes,'exact child source bytes')
    text=raw.decode('utf-8');start=text.index('module ');end=text.index('\n);',start)+3
    header=text[start:end];match=re.fullmatch(r'module (\w+) #\((.*?)\) \((.*?)\n\);',header,re.S)
    need(match is not None,'exact supported parameterized ANSI header')
    child,parameters,declarations=match.groups()
    need(CHILDREN.get(child)==hashlib.sha256(raw).hexdigest(),'exact qualified child source')
    params=re.findall(r'\b([A-Za-z_][A-Za-z_0-9]*)\s*=',parameters)
    need(params==['AW','LANES','HOST_LANES','P','Q'],'exact declared child parameters')
    ports=[]
    for line in declarations.strip().splitlines():
        parsed=re.fullmatch(r'\s*(input|output) logic\s*(\[[^\]]+\])?\s*([A-Za-z_0-9,]+),?\s*',line)
        need(parsed is not None,'supported logic port declaration only')
        direction,width,names=parsed.groups()
        for name in names.rstrip(',').split(','):
            need(re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*',name),'simple scalar/packed port identifier')
            ports.append(dict(name=name,direction=direction,width=width or ''))
    need(len({p['name'] for p in ports})==len(ports),'unique ports')
    need(all(any(p==dict(name=n,direction='input',width='') for p in ports) for n in ('clk','rst_n')),'direct clock/reset inputs')
    return dict(child=child,header=header,parameters=params,ports=ports)

def generate(raw,wrapper):
    need(type(wrapper) is str and re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*',wrapper),'wrapper module identifier')
    data=interface(raw);need(wrapper not in CHILDREN,'separate additive wrapper name')
    ports=data['ports'];inputs=[p for p in ports if p['direction']=='input' and p['name'] not in ('clk','rst_n')]
    outputs=[p for p in ports if p['direction']=='output']
    lines=['// Matched registered-I/O physical probe; source-only until native gate.',
           '// Request latency +1 edge; externally captured response latency +1 edge.',
           data['header'].replace('module '+data['child']+' #(','module '+wrapper+' #(',1)]
    for port in inputs+outputs:
        prefix,suffix=('launch_','_q') if port['direction']=='input' else ('child_','_d')
        lines.append('    logic '+(port['width']+' ' if port['width'] else '')+prefix+port['name']+suffix+';')
    lines.append('    always_ff @(posedge clk or negedge rst_n) begin : registered_probe_boundary')
    lines.append('        if (!rst_n) begin')
    for p in inputs:lines.append("            launch_"+p['name']+"_q <= '0;")
    for p in outputs:lines.append("            "+p['name']+" <= '0;")
    lines.append('        end else begin')
    for p in inputs:lines.append('            launch_'+p['name']+'_q <= '+p['name']+';')
    for p in outputs:lines.append('            '+p['name']+' <= child_'+p['name']+'_d;')
    lines.extend(['        end','    end'])
    lines.append('    '+data['child']+' #('+', '.join('.'+name+'('+name+')' for name in data['parameters'])+') child (')
    bindings=[]
    for p in ports:
        name=p['name'];signal=name if name in ('clk','rst_n') else ('launch_'+name+'_q' if p['direction']=='input' else 'child_'+name+'_d')
        bindings.append('        .'+name+'('+signal+')')
    lines.extend([',\n'.join(bindings),'    );','endmodule',''])
    source='\n'.join(lines)
    receipt=dict(schema='registered-probe-recipe-v1',child=data['child'],child_sha256=hashlib.sha256(raw).hexdigest(),
        wrapper=wrapper,wrapper_sha256=hashlib.sha256(source.encode()).hexdigest(),parameters=data['parameters'],ports=ports,
        source_register_anchors=['launch_'+p['name']+'_q' for p in inputs],
        destination_register_anchors=[p['name'] for p in outputs],
        hierarchy_instance='child',clock='clk',reset='rst_n',request_added_edges=1,response_added_edges=1,
        qualification='source-only mechanical boundary; no native, physical, or drop-in interface claim')
    return source,receipt
