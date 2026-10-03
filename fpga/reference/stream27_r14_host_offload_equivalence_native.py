"""PRIVATE AUTHOR comparison contracts for exact R14 host-offload twins.

Packet-body comparison, not canonical-footer qualification. Full-size payload
conversion/finalization is worker-only. RTL and host endpoint code have their
own authors; this fixture cannot independently review itself.
"""
import hashlib
import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import socket
import sys

from fpga.reference import stream27_host_offload_model_v1 as model

ROOT = Path(__file__).resolve().parents[1]
SELF = 'reference/stream27_r14_host_offload_equivalence_native.py'
CPP = 'rtl/tb/stream27_r14_host_offload_equivalence.cpp'
SV = 'rtl/tb/stream27_r14_host_offload_equivalence.sv'
BASE = ROOT/'results/throughput-20260929/trackS-r14-host-offload-equivalence-v1'
MODEL_PIN = 'f9fab4b5a3042046bc90ab2c719a3ae84c1c0504e4a14609b2ddc5b11b6358c5'
CHIP_PIN = 'd40c8bf31af7261a4efec1af50debf682beb92c6046bb77c37dc7ca34d7fce03'
HOST_HEADER = 'rtl/tb/stream27_host_offload_host_v2.h'
HOST_PIN = '7679e85713662635476124b0bad2e91954a08d8a27dd3f25db127b23da9d0720'
MODEL_CLOSURE = ('reference/stream27_host_offload_model_v1.py',
                 'reference/stream27_signed_boundary_oracle.py',
                 'reference/stream27_blockcarry_param_model_v1.py',
                 'reference/stream27_canonical_image_model_v1.py',
                 'reference/stream_ntt_blockwrap2_proposal.py', 'reference/stream_ntt_model.py')
PARENT = ROOT/'results/throughput-20260929/trackS-c2-protected-relay13-native-v1/aw8-normal'
PARENT_PIN = '6ec75aba4707785bc817817fb9fab4fabe87823a6b5c7dadcdff77ea711ca7b4'
FULL_PARENT = ROOT/'results/throughput-20260929/trackS-c2-protected-relay13-native-v1/full-normal'
FULL_PARENT_PIN = 'd39a6e7a7054aa59f1b2cd66cdb25013e69a1af56c562ecb575b2c3829bda51d'
TOP = 'genefer_stream27_r14_b_equivalence_aw8_v1'
NORMAL_ID = 's4-r14-b-equivalence-aw8-normal-q1-v1'
KEYS = {'label', 'n', 'p', 'context', 'base', 'generation', 'epoch_seed',
        'count', 'input_owner', 'owner', 'input', 'cold', 'profile',
        'raw_twin', 'raw_b', 'canonical_twin', 'canonical_host', 'reference'}


def need(ok, label):
    if not ok:
        raise ValueError('R14_B_EQ_'+label)


def worker_numeric(n):
    if n > 256:
        need(sys.platform.startswith('linux') and
             socket.gethostname().split('.')[0] in ('aethia', 'gfn16-pilot-c4d'),
             'FULL_PAYLOAD_ADMITTED_LINUX_ONLY')


def hex_payload(value, words, label):
    need(type(value) is str and len(value) == 8*words and
         re.fullmatch('[0-9a-f]+', value) is not None, 'EXACT_BODY_'+label)
    return bytes.fromhex(value)


def words32(raw):
    return tuple(int.from_bytes(raw[j:j+4], 'little') for j in range(0, len(raw), 4))


def wire_bytes(values):
    return b''.join((v & 0xffffffff).to_bytes(4, 'little') for v in values)


def packet(value, expected):
    """Match actual converted input and BOTH actual raw-final arrays."""
    n = expected['n']
    worker_numeric(n)  # Before full-size decode/conversion/finalization.
    need(type(value) is dict and set(value) == KEYS, 'PACKET_KEYS')
    integers = ('n', 'p', 'context', 'base', 'generation', 'epoch_seed',
                'count', 'input_owner', 'owner')
    need(all(type(value[k]) is int for k in integers), 'INTEGER_METADATA')
    need(type(value['label']) is str and all(value[k] == expected[k]
         for k in ('label', 'n', 'p', 'context', 'base', 'generation', 'epoch_seed', 'count')),
         'SOURCE_BOUND_JOB_METADATA')
    need(n in (256, 65536) and value['p'] == 16 and value['context'] in (0, 1) and
         0 <= value['generation'] < 256 and 0 <= value['epoch_seed'] < 65536 and
         1 <= value['count'] < 1 << 32, 'GEOMETRY_OWNER_WIDTH')
    initial_owner = (value['epoch_seed'] << 8) | value['generation']
    final_owner = ((value['count']-1) << 24) | (
        ((value['epoch_seed']+value['count']-1) & 65535) << 8) | value['generation']
    need(value['input_owner'] == initial_owner and value['owner'] == final_owner and
         0 <= value['owner'] < 1 << 56, 'COMPLETE_CONTEXT_ORDINAL_EPOCH_GENERATION')
    setup = model.profile(n, 16, value['base'], value['generation'])
    profile = hex_payload(value['profile'], 8, 'PROFILE')
    need(profile == model.profile_payload_bytes(setup), 'EXACT_RECIP96_LIMIT77_PROFILE')
    original = words32(hex_payload(value['input'], n+32, 'ORIGINAL_INPUT'))
    digits = tuple(model.signed32(w) for w in original[:n])
    c0 = tuple(model.signed32(w) for w in original[n:n+16])
    c1 = tuple(model.signed32(w) for w in original[n+16:])
    cold = hex_payload(value['cold'], 3*n+96, 'HOST_CONVERTED_INPUT')
    raw_twin = hex_payload(value['raw_twin'], n+32, 'ACTUAL_TWIN_RAW')
    raw_b = hex_payload(value['raw_b'], n+32, 'ACTUAL_B_RAW')
    need(raw_twin == raw_b, 'B_AND_ONCHIP_RAW_BODY_BIT_IDENTICAL')
    canonical_twin = hex_payload(value['canonical_twin'], n, 'TWIN_CANONICAL')
    canonical_host = hex_payload(value['canonical_host'], n, 'HOST_CANONICAL')
    independent = hex_payload(value['reference'], n, 'INDEPENDENT_REFERENCE')
    previous = model.worker_numeric
    try:
        model.worker_numeric = worker_numeric
        converted = model.prepare_cold(digits, c0, c1, setup,
                                      context=value['context'], epoch=value['epoch_seed'])
        need(cold == model.cold_payload_bytes(converted), 'EXACT_COLD_REVERSE4_AND_UNSCALED_C1')
        final = model.decode_final_payload(raw_b, setup,
                                          context=value['context'], owner=value['owner'])
        result = model.finalize(final, expected_context=value['context'],
                                expected_owner=value['owner'])
    finally:
        model.worker_numeric = previous
    finalized = wire_bytes(result.digits)
    need(finalized == canonical_host == canonical_twin == independent,
         'ACTUAL_RAW_HOST_ONCHIP_INDEPENDENT_BIT_IDENTICAL')
    if expected['label']=='prp':
        need(n==256 and digits==(1,)+(0,)*255 and c0==c1==(0,)*16,
             'PRP_INITIAL_ONE_NO_EXPECTED_RELOAD')
        exponent=value['base']**256
        need(value['count']==exponent.bit_length(),'PRP_COMPLETE_B256_EXPONENT_LEADING_BIT')
        residue=pow(2,exponent,value['base']**256+1);reference=[]
        for j in range(256):reference.append(residue%value['base']);residue//=value['base']
        need(residue==0 and independent==wire_bytes(reference),'PRP_INDEPENDENT_POW_REFERENCE_ALL_WORDS')
    need(result.special is expected['special'], 'SPECIAL_SCOPE')
    if expected['special']:
        need(result.digits == (-1,) + (0,)*(n-1), 'SAME_DUT_SPECIAL_MINUS_ONE')
    return dict(context=value['context'], owner=value['owner'], count=value['count'],
                label=value['label'], special=result.special,
                input_sha256=hashlib.sha256(wire_bytes(original)).hexdigest(),
                cold_sha256=hashlib.sha256(cold).hexdigest(),
                profile_sha256=hashlib.sha256(profile).hexdigest(),
                raw_sha256=hashlib.sha256(raw_b).hexdigest(),
                canonical_sha256=hashlib.sha256(finalized).hexdigest())


def validate(stdout, stderr, returncode, config, assets):
    need(type(config) is dict and set(config) == {'packets', 'footer'} and assets == {}, 'CONFIG')
    expected = config['packets']
    need(type(expected) is list and len(expected) > 0 and
         all(type(p) is dict and set(p) == {'label', 'n', 'p', 'context', 'base',
             'generation', 'epoch_seed', 'count', 'special'} for p in expected),
         'SOURCE_BOUND_EXPECTED_PACKETS')
    for p in expected:
        worker_numeric(p['n'])
    need(hashlib.sha256(Path(model.__file__).read_bytes()).hexdigest() == MODEL_PIN, 'FROZEN_MODEL')
    need(type(stdout) is str and type(stderr) is str and type(returncode) is int and
         returncode == 0 and stderr == '' and stdout.endswith('\n') and
         len(stdout) < 64*1024*1024, 'ACTUAL_OUTPUT')
    lines = stdout.splitlines()
    need(len(lines) == len(expected)+1 and lines[-1] == config['footer'] and
         all(line.startswith('R14_B_EQ_PACKET ') for line in lines[:-1]), 'NO_FOOTER_ONLY_PROOF')
    rows = [packet(json.loads(line.removeprefix('R14_B_EQ_PACKET ')), p)
            for line, p in zip(lines[:-1], expected)]
    return dict(status='PASS_expected_contracts', packets=rows,
                exact_actual_input_output_bodies=True, actual_trimmed_B_core_required=True,
                host_C_and_frozen_model_checked=True, private_fixture_author=True,
                independent_review=False, clock_or_area_claim=False,
                transport_or_host_GL_implemented=False, promotion_allowed=False)


CONTROL_CASES=('empty-commit','partial-commit','skipped-index','noncanonical-residue',
 'generation-width','base-range','limit-upper-bits','startup-generation','startup-epoch',
 'reciprocal-mismatch','limit-mismatch','partial-start','reset-partial-requires-begin',
 'reset-complete-requires-reload','rebegin-requires-new-body','old-load-forbidden',
 'old-read-forbidden','begin-while-busy','raw-receiver-not-ready','boundary-receiver-not-ready')


def validate_controls(stdout,stderr,returncode,config,assets):
    need(config=={'chip_cases':list(CONTROL_CASES),'host_cases':11} and assets=={},'CONTROL_CONFIG')
    need(type(returncode) is int and returncode==0 and stderr=='','CONTROL_ACTUAL_EXIT')
    wanted=['R14_B_HOST_ATOMIC_PASS final_cases=6 cold_cases=5']+[
        'R14_B_CONTROL_CASE '+n+' abort=1 quiet=24' for n in CONTROL_CASES]+[
        'R14_B_CONTROL_PASS chip_cases=20 host_cases=11 quiet_edges=480 reset_recovery=1 public_pins_only=1']
    need(stdout=='\n'.join(wanted)+'\n','CONTROL_TYPED_EXTENT')
    return dict(status='PASS_expected_contracts',private_fixture_author=True,independent_review=False,
        actual_public_pin_chip_cases=20,host_atomic_cases=11,quiet_edges=480,
        reset_recovery_scope='reset-clears-staging/loaded/authority, reload required; not arithmetic checkpoint rollback',
        clock_or_area_claim=False,transport_or_host_GL_implemented=False,promotion_allowed=False)


def sha(raw):
    return hashlib.sha256(raw.encode() if isinstance(raw, str) else raw).hexdigest()


def once(text, before, after):
    need(text.count(before) == 1, 'SOURCE_ANCHOR:'+before[:60])
    return text.replace(before, after, 1)


def ports(text):
    """Preserve original declaration widths and directions; no ABI guessing."""
    rows = []; prefix = None
    for item in text.split(','):
        item = item.strip()
        if not item:
            continue
        match = re.search(r'(\w+)\s*$', item)
        need(match is not None, 'PORT_DECLARATION')
        name = match.group(1); candidate = item[:match.start()].strip()
        if candidate:
            need(candidate.startswith(('input logic', 'output logic')), 'PORT_DIRECTION')
            prefix = candidate
        need(prefix is not None, 'PORT_PREFIX')
        rows.append((name, prefix))
    need(len(rows) == len({n for n, p in rows}), 'UNIQUE_PORTS')
    return rows


def comparison_shell(bundle, parent, top=TOP):
    host = parent['top']; text = parent['files'][host+'.sv']
    header = text[text.index('module '+host+' #('):text.index(');')]
    head, body = header.split(') (', 1)
    head = once(head, 'module '+host+' #(', 'module '+top+' #(')
    head = once(head, 'parameter int AW=', 'parameter int HOST_OFFLOAD=1,AW=')
    original = ports(body)
    from . import stream27_host_offload_chip_v1 as chip
    off = ports(chip.PORTS)
    combined = original + [('b_'+n, p) for n, p in original if n not in ('clk', 'rst_n')] + off
    declarations = [p+' '+n for n, p in combined]
    declarations += ['output logic eq_twin_raw_valid,eq_twin_capture,eq_twin_context,eq_twin_boundary,eq_twin_boundary_context',
                     'output logic [AW-$clog2(P)-1:0] eq_twin_row',
                     'output logic [P*32-1:0] eq_twin_data,eq_twin_c0,eq_twin_c1',
                     'output logic [55:0] eq_twin_owner,eq_twin_live,eq_twin_boundary_owner,eq_twin_boundary_live',
                     'output logic dbg_setup_done,dbg_setup_context',
                     'output logic [1:0] dbg_config_valid',
                     'output logic [63:0] dbg_base',
                     'output logic [191:0] dbg_reciprocal',
                     'output logic [153:0] dbg_limit',
                     'output logic [15:0] dbg_generation']
    new_head = head+') (\n '+',\n '.join(declarations)+');'
    param_names = list(parent['parameters']) + ['EPOCH_SEED0', 'EPOCH_SEED1']
    need(len(param_names) == len(set(param_names)), 'ACTUAL_PARENT_FLAGS_AND_EPOCHS')
    common = ','.join('.'+n+'('+n+')' for n in param_names)
    twin_inputs = []
    for n, p in off:
        twin_inputs.append('.'+n+'('+('' if p.startswith('output') else
                           "1'b1" if n in ('off_raw_ready', 'off_boundary_ready') else "'0")+')')
    twin = bundle['top']+' #(.HOST_OFFLOAD(0),'+common+') twin (\n '+',\n '.join(
        ['.'+n+'('+n+')' for n, p in original]+twin_inputs)+');'
    on = bundle['top']+' #(.HOST_OFFLOAD(1),'+common+') b (\n '+',\n '.join(
        ['.'+n+'('+(''+n if n in ('clk', 'rst_n') else 'b_'+n)+')' for n, p in original]+
        ['.'+n+'('+n+')' for n, p in off])+');'
    template = (ROOT/SV).read_text()
    need(template.count('@HEADER@') == template.count('@TWINS@') == 1, 'PASSIVE_SHELL_TEMPLATE')
    result = template.replace('@HEADER@', new_head).replace('@TWINS@', twin+'\n'+on)
    need(not re.search(r'\b(always|always_ff|always_comb|initial|force)\b', result), 'PASSIVE_TWIN_ONLY')
    return result


def role(stage='aw8'):
    from . import stream27_host_offload_chip_v1 as chip
    need(stage in ('aw8', 'full', 'fullspecial', 'special', 'controls', 'prp'), 'EXPLICIT_STAGE')
    small = stage not in ('full','fullspecial')
    n = 256 if small else 65536
    top = TOP if small else TOP.replace('aw8', 'full')
    donor, donor_pin = (PARENT, PARENT_PIN) if small else (FULL_PARENT, FULL_PARENT_PIN)
    need(sha(Path(chip.__file__).read_bytes()) == CHIP_PIN and
         sha((ROOT/HOST_HEADER).read_bytes()) == HOST_PIN and
         sha((donor/'manifest.json').read_bytes()) == donor_pin, 'FROZEN_CHIP_HOST_PARENT')
    parent = chip.prepare(n, host_offload=0)
    b = chip.prepare(n, host_offload=1)
    need(len(parent['files']) == 58 and len(b['files']) == 66 and
         all(b['files'][n] == t for n, t in parent['files'].items()), 'OFF_EXACT_PARENT_58_ON66_RETAINED')
    manifest = json.loads((donor/'manifest.json').read_bytes())
    files = {name:(donor/'source/fpga'/name).read_bytes() for name in manifest['sources']}
    need(all(sha(files[n]) == p for n, p in manifest['sources'].items()), 'FROZEN_PARENT_CAPTURE')
    files.update({'rtl/'+n:t.encode() for n, t in b['files'].items()})
    shell = 'rtl/tb/'+Path(SV).name
    files[shell] = comparison_shell(b, parent, top).encode()
    header = 'rtl/tb/s4_host_contexts_config_v1.h' if small else 'rtl/tb/s4_p16_two_context_full_config.h'
    old = manifest['build']['top']; text = files[header].decode()
    need(text.count(old) == 2, 'EXACT_MODEL_ALIAS')
    files[header] = text.replace(old, top).encode()
    donor_cpp = manifest['build']['cpp_source']
    driver = files[donor_cpp].decode()
    anchor = ('static void edge(DUT& d){d.clk=0;d.eval();d.clk=1;d.eval();}' if small else
              'static void edge(DUT& d){d.clk=0;d.eval();d.clk=1;d.eval();d.clk=0;d.eval();}')
    hooked = 'static void eq_pre(DUT& d);\nstatic void eq_read(DUT& d,unsigned c,unsigned address);\n'+anchor.replace('d.clk=1;', 'eq_pre(d);d.clk=1;')
    driver = once(driver, anchor, hooked)
    read = ('need(d.read_data[0]==uint32_t(expected)&&d.read_data[1]==high&&d.read_data[2]==high,"S4_HOST_CONTEXT_SIGNED96_VALUE ctx="+std::to_string(ctx)+" address="+std::to_string(address));' if small else ' return actual;')
    replacement = read+'\n    eq_read(d,ctx,address);' if small else ' eq_read(d,ctx,address);\n'+read
    driver = once(driver, read, replacement)
    original_driver = once(once(driver, replacement, read), hooked, anchor)
    need(original_driver.encode() == files[donor_cpp], 'DONOR_DRIVER_HOOK_REVERSAL')
    files['rtl/tb/stream27_r14_twin_driver.cpp'] = driver.encode()
    for source_name in (SELF, CPP, HOST_HEADER, *MODEL_CLOSURE, *b['source_dependencies']):
        raw = (ROOT/source_name).read_bytes()
        files[source_name] = raw
    files['lineage/'+SV] = (ROOT/SV).read_bytes()
    if stage == 'special':
        from fpga.reference.stream27_two_context_whole_programs import programs
        vectors=programs(n=256,p=16,kind='sentinel',counts=(3,5))
        h=files[header].decode()
        h=once(h,'KIND="dense"','KIND="sentinel"')
        h=once(h,'EXPECT_CAPTURE_COPY=true','EXPECT_CAPTURE_COPY=false')
        h=once(h,'CANON_PASSES=9','CANON_PASSES=10')
        h=once(h,'COUNTS[2]={3,14}','COUNTS[2]={3,5}')
        for name,key,size in (('INITIAL','initial_digits',256),('C0','initial_c0',16),('C1','initial_c1',16),('EXPECTED',None,256)):
            rows=[v[key] if key else v['dependent_steps'][-1]['canonical_signed32'] for v in vectors['contexts']]
            replacement='constexpr int32_t '+name+f'[2][{size}]='+json.dumps(rows,separators=(',',':')).replace('[','{').replace(']','}')+';'
            h,count=re.subn(r'constexpr int32_t '+name+r'\[2\]\['+str(size)+r'\]=.*?;',lambda m:replacement,h)
            need(count==1,'SPECIAL_HEADER_'+name)
        files[header]=h.encode()
        cpp=files[CPP].decode()
        cpp=once(cpp,'&&!info.special','&&info.special')
        cpp=once(cpp,'\\"label\\":\\"dense\\"','\\"label\\":\\"sentinel\\"')
        cpp=cpp.replace('counts=3/14','counts=3/5')
        files[CPP]=cpp.encode()
        files['reference-assets/r14-special-vectors.json']=json.dumps(vectors,sort_keys=True).encode()
        files['reference/stream27_two_context_whole_programs.py']=(ROOT/'reference/stream27_two_context_whole_programs.py').read_bytes()
    if not small:
        cpp = files[CPP].decode()
        declarations = '''\nstatic constexpr unsigned COUNTS[2]={COUNT,COUNT},FIRST[2]={204,204+INTERVAL/2};
static std::array<Image,2> INITIAL,EXPECTED;
static constexpr int32_t C0[2][16]={},C1[2][16]={};
static unsigned launched(unsigned age,unsigned c){return age<FIRST[c]?0:std::min(COUNT,1u+(age-FIRST[c])/INTERVAL);}
static unsigned completed(unsigned age,unsigned c){return age<FIRST[c]+CARRY_DONE+1?0:std::min(COUNT,1u+(age-FIRST[c]-CARRY_DONE-1)/INTERVAL);}
'''
        cpp = once(cpp, '#include <vector>\n', '#include <vector>\n'+declarations)
        cpp = once(cpp, 'clear_b(d);prepare_packets();collecting_twin=true;',
                   's4_full_reference::self_check();INITIAL={initial(0),initial(1)};EXPECTED=INITIAL;\n'+
                   ' for(unsigned c=0;c<2;c++)for(unsigned k=0;k<COUNT;k++)EXPECTED[c]=s4_full_reference::square(EXPECTED[c],BASES[c],BITS[c][k]);\n'+
                   ' clear_b(d);prepare_packets();collecting_twin=true;')
        cpp = once(cpp, '  run(d);', '  run(d,3,INITIAL,EXPECTED);')
        cpp = once(cpp, ' d.b_warm_count=uint64_t(COUNTS[0])|(uint64_t(COUNTS[1])<<32);',
                   ' d.b_warm_count=uint64_t(COUNTS[0])|(uint64_t(COUNTS[1])<<32);\n'+
                   ' d.b_double_bit=(BITS[0][0]?1u:0u)|(BITS[1][0]?2u:0u);\n'+
                   ' d.b_double_mask=uint64_t(BITS[0][1]<<1)|(uint64_t(BITS[1][1]<<1)<<32);')
        cpp = once(cpp, 'for(unsigned age=1;age<std::max(COUNTS[0],COUNTS[1])*INTERVAL+33*N+10000;age++)',
                   'for(unsigned age=1;age<MAX_EDGES;age++)')
        cpp = cpp.replace('R14_B_EQ_NORMAL_PASS n=256 contexts=2 counts=3/14',
                          'R14_B_EQ_NORMAL_PASS n=65536 contexts=2 counts=2/2')
        files[CPP] = cpp.encode()
    if stage=='fullspecial':
        h=once(files[header].decode(),'COUNT=2','COUNT=1')
        h=once(h,'BITS[2][2]={{0,1},{1,0}}','BITS[2][2]={{0,0},{0,0}}')
        files[header]=h.encode()
        cpp=files[CPP].decode()
        cpp=once(cpp,'INITIAL={initial(0),initial(1)};EXPECTED=INITIAL;',
                 'INITIAL={Image(N,0),Image(N,0)};INITIAL[0][N/2]=INITIAL[1][N/2]=1;EXPECTED=INITIAL;')
        cpp=once(cpp,'&&!info.special','&&info.special')
        cpp=once(cpp,'\\"label\\":\\"dense\\"','\\"label\\":\\"sentinel\\"')
        cpp=cpp.replace('counts=2/2','counts=1/1');files[CPP]=cpp.encode()
        driver=files['rtl/tb/stream27_r14_twin_driver.cpp'].decode()
        driver=once(driver,'lane64(d.canonical_cycles,ctx)==9*N','lane64(d.canonical_cycles,ctx)==10*N')
        driver=once(driver,'age>result.warm[ctx]+9*N+N','age>result.warm[ctx]+10*N+N')
        files['rtl/tb/stream27_r14_twin_driver.cpp']=driver.encode()
    need(files[CPP].decode().count('DUT d(&context)') == 1 and
         files[CPP].decode().index('gfn16_runtime::configure(context,argc,argv)') <
         files[CPP].decode().index('DUT d(&context)'), 'ACTUAL_RUNTIME_BEFORE_SINGLE_DUT')
    manifest['build'].update(top=top, cpp_source=CPP,
        sv_sources=['rtl/'+n for n in b['files']] + [shell],
        parameters=dict(manifest['build']['parameters'], HOST_OFFLOAD=1))
    bases, counts = ((1009,2017),(3,5) if stage=='special' else (3,14)) if small else ((604832956,999999937),(1,1) if stage=='fullspecial' else (2,2))
    if stage=='prp':
        values=[];bits=[];counts=[]
        for base in bases:
            exponent=base**256;bits.append(bin(exponent)[2:]);counts.append(len(bits[-1]))
            residue=pow(2,exponent,base**256+1);digits=[]
            need(residue!=base**256,'PRP_ORDINARY_REFERENCE')
            for j in range(256):digits.append(residue%base);residue//=base
            need(residue==0,'PRP_ALL256_WORDS');values.append(digits)
        h=files[header].decode();h=once(h,'COUNTS[2]={3,14}',f'COUNTS[2]={{{counts[0]},{counts[1]}}}')
        for name,rows,size in (('INITIAL',[[1]+[0]*255]*2,256),('C0',[[0]*16]*2,16),
                               ('C1',[[0]*16]*2,16),('EXPECTED',values,256)):
            text='constexpr int32_t '+name+f'[2][{size}]='+json.dumps(rows,separators=(',',':')).replace('[','{').replace(']','}')+';'
            h,replacements=re.subn(r'constexpr int32_t '+name+r'\[2\]\['+str(size)+r'\]=.*?;',lambda m:text,h)
            need(replacements==1,'PRP_HEADER_'+name)
        h+='\n#define R14_PRP 1\nstatic constexpr const char* PRP_BITS[2]={'+','.join(json.dumps(s) for s in bits)+'};\n'
        files[header]=h.encode();cpp=files[CPP].decode()
        cpp=once(cpp,'\\"label\\":\\"dense\\"','\\"label\\":\\"prp\\"')
        cpp=cpp.replace('counts=3/14',f'counts={counts[0]}/{counts[1]}');files[CPP]=cpp.encode()
        files['reference-assets/r14-prp-n256.json']=json.dumps(dict(n=256,bases=bases,exponent='b^256',
            leading_bit_included=True,counts=counts,bits=bits,initial=[1]+[0]*255,expected=values),sort_keys=True).encode()
    expected = [dict(label='sentinel' if stage in ('special','fullspecial') else 'prp' if stage=='prp' else 'dense', n=n, p=16, context=c, base=bases[c],
                     generation=1, epoch_seed=(65534,42)[c], count=counts[c], special=stage in ('special','fullspecial'))
                for c in range(2)]
    manifest['steps'] = [dict(name='r14-host-offload-'+stage+'-actual-twin-normal', argv=['{exe}'],
        expected_returncode=0, validator=dict(source=SELF, function='validate',
        config=dict(packets=expected, footer=f'R14_B_EQ_NORMAL_PASS n={n} contexts=2 counts={counts[0]}/{counts[1]} raw_actual=1 cold_actual=1 independent_reference=1'), assets={}))]
    if stage=='controls':
        manifest['steps']+= [dict(name='r14-host-offload-public-controls',argv=['{exe}','--controls'],
            expected_returncode=0,validator=dict(source=SELF,function='validate_controls',
            config=dict(chip_cases=list(CONTROL_CASES),host_cases=11),assets={}))]
    manifest['source_root'] = manifest['output_parent'] = 'UNBOUND'
    manifest['sources'] = {n:sha(raw) for n, raw in files.items()}
    snapshot = {n:p for n, p in manifest['sources'].items() if n.endswith('.sv')}
    manifest['test_role'] = 'deliberate_fault' if stage=='controls' else 'normal'
    manifest['rtl_readiness'] = dict(schema='gfn16-candidate-rtl-ready-v1', candidate_id=NORMAL_ID,
        source_snapshot=snapshot, candidate_source_sha256=sha(json.dumps(snapshot,sort_keys=True,separators=(',',':'))),
        rtl_ready_at_utc=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'))
    manifest['r14_b_equivalence'] = dict(author='p16_independent_reviewer', independent_review=False,
        chip_source_sha256=CHIP_PIN, host_header_sha256=HOST_PIN, parent_manifest_sha256=donor_pin,
        production_source_retained=True, actual_ON_and_OFF_compiled=True, passive_observer=True,
        actual_cold_and_raw_output_bodies_required=True, no_footer_only_proof=True,
        arbitrary_fault_or_transport_or_GL_claim=False, promotion_allowed=False)
    return manifest, files, b


def dump(path, value):
    with Path(path).open('x') as out:
        json.dump(value, out, indent=2); out.write('\n')


def prepare_normal(stage='aw8', version=2):
    from fpga.tools import candidate_ladder, native_class_package_v2 as package
    need(stage in ('aw8','full','fullspecial','special','controls','prp') and type(version) is int and version >= 2, 'ADDITIVE_SUCCESSOR_ONLY')
    logical_id=f's4-r14-b-equivalence-{stage}-'+('faults' if stage=='controls' else 'normal')+f'-q1-v{version}'
    out = BASE/f'{stage}-normal-v{version}'
    need(not out.exists() and not any((ROOT/p).exists() for p in ('queue/PAUSE','docs/briefs/PAUSE')), 'FRESH_UNPAUSED')
    manifest, files, b = role(stage); source = out/'source/fpga'; source.mkdir(parents=True)
    manifest['rtl_readiness']['candidate_id']=logical_id
    manifest['rtl_readiness']['rtl_ready_at_utc']='2026-10-03T00:05:00Z'
    for name, raw in files.items():
        target = source/name; target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as stream: stream.write(raw)
    manifest['source_root'] = str(source.resolve())
    dump(out/'manifest.json', manifest); dump(out/'production-bundle.json', b)
    dump(out/'host-hours.json', candidate_ladder.budget_from_hourly()); variants=[]
    for pair in ('01','23'):
        profile='gcp-c4d-static'+pair+'-v1'; worker=f's4-r14-b-eq-{stage}-normal-{pair}-v{version}'; packet=out/('packet-'+pair)
        result=package.prepare(out/'manifest.json',source,profile,worker,'run',packet,out/'host-hours.json')
        ticket=json.loads((packet/'ticket.json').read_bytes())
        variants.append(dict(archive=str(packet/'package.tar.gz'),sha256=result['archive_sha256'],
            ticket_sha256=result['ticket_sha256'],manifest_sha256=sha((packet/'manifest.json').read_bytes()),
            worker_id=worker,profile=profile,native_root=ticket['native_root'],runner='tools/native_class_package_v2.py',
            runner_sha256=sha((ROOT/'tools/native_class_package_v2.py').read_bytes()),
            stager=str(ROOT/'tools/native_package_v4.py'),stager_sha256=sha((ROOT/'tools/native_package_v4.py').read_bytes()),
            stager_dependencies=[dict(path=str(ROOT/n),sha256=sha((ROOT/n).read_bytes())) for n in
                                 ('tools/native_package_v3.py','tools/native_package_v2.py')],max_seconds=3700))
    logical=dict(schema='gfn16-global-ticket-v1',id=logical_id,owner='p16-reviewer-private-b-author',
        created=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),priority='P1',kind='sim',needs='verilator',
        tool_identity='gcp-c4d-verilator5032-gcc15-python314-v1',allowed_hosts=['gfn16-pilot-c4d','aethia'],
        resources=dict(cores=2,threads=1,ram_gib=8,scratch_gib=4),minimum_ram_gib=4,
        minimum_ram_rationale='Bounded dual actual twins; desired8/min4, unmeasured sufficiency retains OOM/timeout.',
        est_minutes=45 if stage in ('full','fullspecial') else 15,promotion_bound=False,test_role=manifest['test_role'],rtl_readiness=manifest['rtl_readiness'],packages=variants)
    dump(out/'global-ticket.json',logical)
    return dict(id=logical_id,ticket=str(out/'global-ticket.json'),status='PREPARED_NOT_NATIVE',compiled_sv=67)


if __name__ == '__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--stage',choices=('aw8','full','fullspecial','special','controls','prp'),default='aw8')
    parser.add_argument('--version',type=int,default=2);args=parser.parse_args()
    print(json.dumps(prepare_normal(args.stage,args.version), indent=2))
