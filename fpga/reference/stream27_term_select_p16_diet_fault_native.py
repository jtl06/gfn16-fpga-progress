"""Source-specific actual private/factored term fault pair, not inherited PASS."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
from . import stream27_term_select_p16_diet_native as native
from . import stream27_term_select_p16_diet_bind as binding
from . import stream27_term_select_fault_native as oracle

ROOT=native.ROOT
SELF='reference/stream27_term_select_p16_diet_fault_native.py'
TOP=oracle.TOP+'_p16_diet_v1'
CPP='rtl/tb/stream27_term_select_p16_diet_faults.cpp'
ID='s4-p16-diet-term-select-aw8-f1-faults-q1-r3'
NORMAL_ID='s4-p16-diet-term-select-aw8-f1-normal-q1-r2'
need,sha,dump=native.need,native.sha,native.dump


def role():
    b=native.field_bundle();info=b['term_select']
    parent=native.donor.prepare(256,16,paired=False,contexts=1,canonical_pipe_stages=1,
        corr_serial_bfs=2,comm_stage_shared_mlab=1,mont_factored=1)
    m,files=oracle.role();oldinfo=m['term_select']['binding'];new=info['new_term'];diag=new+'_fault_probe_v1'
    term=b['files'][new+'.sv'];term=binding.once(term,'module '+new+' #','module '+diag+' #')
    term=binding.once(term,'input logic clk,rst_n,quarantine,','input logic clk,rst_n,quarantine,debug_drop_select,')
    term=binding.once(term,'wire product_slot,product_error,product_pending,data_select_slot;',
        'wire product_slot,product_error,product_pending,data_select_slot,data_select_slot_raw;\n'
        '    assign data_select_slot=data_select_slot_raw && !debug_drop_select;')
    term=binding.once(term,'.data_select_slot(data_select_slot));','.data_select_slot(data_select_slot_raw));')
    term=binding.once(term,binding.frozen.TERM_ASSERT,'')
    wrapper=files['rtl/'+oracle.TOP+'.sv'].decode()
    wrapper=binding.identifier(wrapper,oracle.TOP,TOP)
    wrapper=binding.identifier(wrapper,oldinfo['parent_term'],info['parent_term'])
    wrapper=binding.identifier(wrapper,oldinfo['new_term']+'_fault_probe_v1',diag)
    roots=[n for n in b['files'] if n.startswith('genefer_stream27_shared_term_roots_') and '_f1_' in n]
    need(len(roots)==1,'P16_DIET_TERM_FAULT_ROOT');need(roots[0][:-3]+' term_roots (' in wrapper,'P16_DIET_TERM_FAULT_ACTUAL_ROOT_NAME')
    arith=[n for n in parent['files'] if 'row_arithmetic_param_v1_p16_diet_v1' in n]
    need(len(arith)==1,'P16_DIET_TERM_FAULT_ACTUAL_ARITH')
    rtl={info['parent_term']+'.sv':parent['files'][info['parent_term']+'.sv'],arith[0]:parent['files'][arith[0]],
         roots[0]:b['files'][roots[0]],diag+'.sv':term,TOP+'.sv':wrapper,
         info['new_mul']+'.sv':b['files'][info['new_mul']+'.sv'],binding.FACTORED+'.sv':b['files'][binding.FACTORED+'.sv']}
    files={n:raw for n,raw in files.items() if not(n.startswith('rtl/') and n.endswith('.sv'))}
    files.update({'rtl/'+n:text.encode() for n,text in rtl.items()})
    header=files[oracle.HEADER].decode()
    need(header.count('V'+oracle.TOP)==2,'P16_DIET_TERM_FAULT_MODEL_HEADER_REFERENCES')
    files[oracle.HEADER]=header.replace('V'+oracle.TOP,'V'+TOP).encode()
    files[CPP]=files.pop(oracle.CPP).decode().replace('S4_TERM_SELECT','S4_P16_DIET_TERM_SELECT').encode()
    for name in b['source_dependencies']+[SELF,native.SELF,oracle.SELF,oracle.CPP]:files['lineage/'+name]=(ROOT/name).read_bytes()
    for step in m['steps']:
        step['name']='private-diet-'+step['name'];step['expected_stdout']=step['expected_stdout'].replace('S4_TERM_SELECT','S4_P16_DIET_TERM_SELECT')
        step['expected_stderr']=step['expected_stderr'].replace('S4_TERM_SELECT','S4_P16_DIET_TERM_SELECT')
    m.update(sources={n:sha(raw) for n,raw in files.items()},
        build=dict(top=TOP,sv_sources=['rtl/'+n for n in rtl],cpp_source=CPP,parameters={},cflags=['-std=c++17','-O2','-Werror=return-type']),
        term_select=dict(binding=info,production_geometry=b['geometry'],
            scope='Actual private P16/factored term and real root pair; direct-weight/fault/reset/stop/origin and exact41 after baseline. No sevenflag/whole/clock qualification.'))
    return m,files


def prepare(output,budget):
    from fpga.tools import native_class_package_v2 as package
    output=Path(output).resolve();need(not output.exists() and not any((ROOT/n).exists() for n in ('docs/briefs/PAUSE','queue/PAUSE')),'P16_DIET_TERM_FAULT_FRESH_PAUSE')
    m,files=role();source=output/'input/source/fpga';source.mkdir(parents=True)
    for name,raw in files.items():
        path=source/name;path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as stream:stream.write(raw)
    manifest=output/'input/manifest.json';dump(manifest,m)
    profile='gcp-c4d-static01-v1';worker=ID+'-01';packet=output/'packet-01'
    r=package.prepare(manifest,source,profile,worker,'run',packet,Path(budget).resolve())
    variant=dict(profile=profile,worker_id=worker,archive=str(packet/'package.tar.gz'),sha256=r['archive_sha256'],ticket_sha256=r['ticket_sha256'],
        manifest_sha256=sha((packet/'manifest.json').read_bytes()),native_root=r['native_root'],runner='tools/native_class_package_v2.py',runner_sha256=sha((ROOT/'tools/native_class_package_v2.py').read_bytes()),
        stager=str(ROOT/'tools/native_package_v3.py'),stager_sha256=sha((ROOT/'tools/native_package_v3.py').read_bytes()),
        stager_dependencies=[dict(path=str(ROOT/'tools/native_package_v2.py'),sha256=sha((ROOT/'tools/native_package_v2.py').read_bytes()))],max_seconds=3700)
    ticket=dict(schema='gfn16-global-ticket-v1',id=ID,owner='term-select',created=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),
        priority='P1',kind='sim',needs='verilator',tool_identity='gcp-c4d-verilator5032-gcc15-python314-v1',resources=dict(cores=2,threads=1,ram_gib=8,scratch_gib=4),minimum_ram_gib=4,
        minimum_ram_rationale='Existing4GiB actual term/root pair envelope; no peak claim.',est_minutes=10,promotion_bound=False,test_role='deliberate_fault',packages=[variant],after=[NORMAL_ID],on='PASS_expected_contracts')
    dump(output/'global-ticket-v1.json',ticket);return dict(status='fault_source_prepared_not_submitted',id=ID,ticket=str(output/'global-ticket-v1.json'))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--budget',type=Path,required=True)
    a=p.parse_args();print(json.dumps(prepare(a.output,a.budget),indent=2))
