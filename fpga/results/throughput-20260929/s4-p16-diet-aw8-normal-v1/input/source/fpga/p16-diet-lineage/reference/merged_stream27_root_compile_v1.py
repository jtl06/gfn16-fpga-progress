"""Source-only packed S-M2 root library. No HDL/native/fit/deployment command.

Full-size modular power constants explicitly permitted by --allow-full-constants;
no full-size numeric NTT. Bare descriptors are sufficient for probe integration.
"""
import argparse
import hashlib
import json
from pathlib import Path

from fpga.reference import merged_stream27_model_v1 as model
from fpga.reference import merged_negacyclic27_model as arithmetic

ROOT = Path(__file__).resolve().parents[1]
ROOT_HELPER = 'rtl/kernel/genefer_stream27_compact_root_prefetch_v1.sv'
FINAL_HELPER = 'rtl/kernel/genefer_stream27_merged_final_gs_pair_v1.sv'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def embedded_root(name, entry, words, frame_ticks):
    """Exact helper-source delta: specialize defaults, replace only ROM init.

    The generated Quartus probe needs no working-directory HEX lookup. No
    change to row gathering/static bypass/one-read calendar is permitted.
    """
    source=(ROOT/ROOT_HELPER).read_text()
    replacements={
        'module genefer_stream27_compact_root_prefetch_v1 #(':f'module {name} #(',
        'parameter int WIDTH=27,':f'parameter int WIDTH={entry["width"]},',
        'parameter int FRAME_T=4,':f'parameter int FRAME_T={frame_ticks},',
        'parameter int ADDRESS_BITS=1,':f'parameter int ADDRESS_BITS={entry["address_bits"]},',
        "parameter logic [MAP_W-1:0] ADDRESS_ROW_POSITIONS='0,":
            f'parameter logic [MAP_W-1:0] ADDRESS_ROW_POSITIONS={max(1,entry["address_bits"]*max(1,frame_ticks.bit_length()-1))}\'h{entry["row_map_hex"]},',
        "parameter logic [WIDTH-1:0] FIRST_ROOT='0,":f'parameter logic [WIDTH-1:0] FIRST_ROOT={entry["width"]}\'h{entry["first_word_hex"]},',
        'parameter string HEX_FILE=""':'parameter string HEX_FILE="EMBEDDED_SOURCE_ONLY"',
        'initial if(HEX_FILE!="")$readmemh(HEX_FILE,roots);':
            'initial begin\n'+''.join(f"            roots[{k}]={entry['width']}'h{word:0{(entry['width']+3)//4}x};\n" for k,word in enumerate(words))+'        end',
    }
    for before,after in replacements.items():
        if source.count(before)!=1:raise ValueError('S_M2_EMBEDDED_SOURCE_DELTA_ANCHOR:'+before)
        source=source.replace(before,after)
    return source


def compile_roots(n=32, p=8, field=0, *, allow_full_constants=False, embed_roms=True):
    model.source_guard()
    layout = model.root_layout(n, p, field, emit_words=True, allow_full_constants=allow_full_constants)
    source = []
    modules = []
    for entry in layout['entries']:
        name = f'merged_stream27_root_{entry["direction"].lower()}_aw{n.bit_length()-1}_p{p}_f{field}_s{entry["stage"]}_v1'
        row_w = max(1, (n // p).bit_length() - 1)
        map_w = max(1, row_w * entry['address_bits'])
        mapping = sum(position << (k * row_w) for k, position in enumerate(entry['row_positions']))
        width = entry['width']
        first = f'{entry["first_word"]:0{(width+3)//4}x}'
        descriptor={**{k:v for k,v in entry.items() if k!='first_word'},
                    'first_word_hex':first,'module':name,'row_map_hex':f'{mapping:x}'}
        if embed_roms:
            words=tuple(int(x,16) for x in layout['files'][entry['file']].splitlines()) if entry['file'] else (entry['first_word'],)
            source.append(embedded_root(name,descriptor,words,n//p))
        else:
            source.append(f'''// Packed unique roots in stream index order; distribute by root_stream_for_pair.
module {name} (
  input logic clk,rst_n,in_slot_valid,frame_start,
  output logic [{width-1}:0] root);
  genefer_stream27_compact_root_prefetch_v1 #(
    .WIDTH({width}),.FRAME_T({n//p}),.ADDRESS_BITS({entry['address_bits']}),
    .ADDRESS_ROW_POSITIONS({map_w}'h{mapping:x}),
    .FIRST_ROOT({width}'h{first}),.HEX_FILE("{entry['file'] or ''}")) source (
    .clk,.rst_n,.in_slot_valid,.frame_start,.root);
endmodule
''')
        modules.append(descriptor)
    name = f'merged_stream27_root_library_aw{n.bit_length()-1}_p{p}_f{field}_v1.sv'
    files = {**layout['files'], name: '\n'.join(source)}
    return dict(profile=model.PROFILE, n=n, p=p, field=field, files=files, modules=modules,
                compiled_sv_files=[name],root_data_files=sorted(layout['files']),embedded_roms=embed_roms,
                canonical_data_width=27, source_dependencies=[ROOT_HELPER, FINAL_HELPER,
                    'rtl/kernel/genefer_ntt_banked27_engine.sv', 'rtl/kernel/genefer_montgomery_mul27_sparse_pipe.sv'],
                final_upper_scale=arithmetic.normalization_constant(n, arithmetic.FIELDS[field]),
                final_pair_module='genefer_stream27_merged_final_gs_pair_v1',
                root_M20K_tiling_proxy=layout['packed_transform_root_M20K_proxy'],
                final_normalization_extra_sparse_pipes=p//2,
                default_doubling='post_CRT_integer; no folded2x selected in this source',
                root_latency='one synchronous next-row prefetch; row0 constant; accepted row always owns current word',
                final_pair_latency='source-design k+5 (k+3 upper multiplier plus two registers); native alignment gate pending',
                lazy2P_supported=False, contexts=1, full_N_numeric_NTT_performed=False,
                native_or_fit_qualification=False)


def prepare(output, n=65536, p=8, field=0, *, allow_full_constants=False):
    model.need(not (ROOT/'docs/briefs/PAUSE').exists(), 'brief PAUSE')
    output = Path(output).resolve()
    model.need(not output.exists(), 'S_M2_FRESH_OUTPUT')
    bundle = compile_roots(n, p, field, allow_full_constants=allow_full_constants)
    output.mkdir(parents=True)
    for name, text in bundle['files'].items():
        (output/name).write_text(text)
    dependencies = {name: sha((ROOT/name).read_bytes()) for name in bundle['source_dependencies']}
    sources = {name: sha((ROOT/name).read_bytes()) for name in [
        'reference/merged_stream27_root_compile_v1.py', 'reference/merged_stream27_model_v1.py',
        'tests/test_merged_stream27_model_v1.py', 'tests/test_merged_stream27_root_compile_v1.py']}
    result = {**{k:v for k,v in bundle.items() if k != 'files'}, 'status':'prepared_source_only_S_M2_roots_not_executed',
              'source_sha256':sources, 'source_dependencies_sha256':dependencies,
              'generated_sha256':{name:sha(text.encode()) for name,text in bundle['files'].items()},
              'generated_file_count':len(bundle['files']),
              'generated_bytes':sum(len(text.encode()) for text in bundle['files'].values()),
              'root_module_interface':'clk,rst_n,in_slot_valid,frame_start -> packed root; stream selection topology.root_stream_for_pair',
              'required_next_gate':'Probe compiler binding + native small frame/cancel/reset/dense continuity and upper/lower k+5 alignment.',
              'promotion_allowed':False}
    (output/'manifest.json').write_text(json.dumps(result, indent=2)+'\n')
    return result


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--n',type=int,default=65536)
    parser.add_argument('--p',type=int,choices=(8,16),default=8)
    parser.add_argument('--field',type=int,choices=(0,1,2),default=0)
    parser.add_argument('--allow-full-constants',action='store_true')
    args=parser.parse_args()
    print(json.dumps(prepare(args.output,args.n,args.p,args.field,allow_full_constants=args.allow_full_constants),indent=2))
