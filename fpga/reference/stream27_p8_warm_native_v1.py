"""P8 one-field native contracts, frozen reference and measured-RTL binding.

Locally this module only emits sources/constants. No full-N numeric transform,
HDL, compiler or executable is run by preparation or source tests.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIT_PROJECT = 'artifacts/stream27-s4-aw16-p8-warm-sizing-aws-v3/project'
FIT_MANIFEST = FIT_PROJECT + '/manifest.json'
FIT_RECEIPT = 'queue/fit-r54-controller-v6/terminal/s4-p8-warm-sizing/receipt.json'
FIT_TERMINAL = 'queue/fit-r54-controller-v6/terminal/s4-p8-warm-sizing/evidence/project'
BENCH = 'rtl/tb/stream27_shared_warm_aw8_v1.cpp'
REFERENCE = 'rtl/tb/stream27_shared_reference_ntt_v1.h'
BENCH_PARENT = 'reference/stream27_shared_warm_full_native_v1.py'
CPP = 'rtl/tb/stream27_p8_warm_native_v1.cpp'
HEADER = 'rtl/tb/s4_full_config_v1.h'
PINS = {
    FIT_MANIFEST: '958a2223caf1a20e02714520f3efe85ab71a7b36de64c0198a88e0cba800c662',
    FIT_RECEIPT: '34ae4f0514a80303a19001e3f438e23872def4a27f042a29926d973fa162cc7a',
    'reference/stream27_shared_field_v1.py': '4e7f7dab9ed263bf63866cbbec74590d9fb6da8d4794b06e0138a7456075d9b3',
    'reference/stream27_shared_field_source_v1.py': '9a447cf96a88236714a68d4bbfb9edef152c063d48dcb5357cfdba31766ae0a4',
    BENCH_PARENT: '54ef59929f3f994f626c4b3c373cbc6cc03270e0821cbd5c8953f21d86672cc4',
    BENCH: '722fef508f9e99d03b282e59c4f47d4c8b8d468dd23a672930929f199cecbb2c',
    REFERENCE: 'c7837ba92829293131efda704dfdde347708641bf9aff46dccbcb87b825ba390',
}


def need(ok, tag):
    if not ok: raise ValueError(tag)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def verify(root=ROOT):
    root = Path(root)
    for name, pin in PINS.items():
        path = root/name
        need(path.is_file() and not path.is_symlink() and sha(path.read_bytes()) == pin,
             'P8_WARM_SOURCE_DRIFT ' + name)
    measured = json.loads((root/FIT_MANIFEST).read_text())
    need(measured['top'] == 'genefer_stream27_shared_warm_aw16_p8_f0_v1' and
         measured['core_parameters'] == dict(AW=16, P=8, CONTEXTS=1) and
         len(measured['source_sha256']) == 23, 'P8_WARM_MEASURED_CONFIGURATION')
    for name, pin in measured['source_sha256'].items():
        need(Path(name).name == name and name.endswith('.sv'), 'P8_WARM_MEASURED_NAME')
        for project in (FIT_PROJECT, FIT_TERMINAL):
            path = root/project/'rtl'/name
            need(path.is_file() and not path.is_symlink() and sha(path.read_bytes()) == pin,
                 'P8_WARM_MEASURED_RTL_DRIFT ' + name)
    for name, pin in measured['preparation_source_sha256'].items():
        path = root/name
        need(path.is_file() and not path.is_symlink() and sha(path.read_bytes()) == pin,
             'P8_WARM_MEASURED_DEPENDENCY_DRIFT ' + name)
    return measured


def role_arguments(aw, field):
    need(type(aw) is int and type(field) is int and
         ((aw == 8 and field in range(3)) or (aw == 16 and field == 0)), 'P8_WARM_ROLE')
    return 1 << aw


def counts(aw, field):
    n = role_arguments(aw, field); rows = n//8
    return dict(cases=9, frames=9, physical_rows=9*rows, physical_words=9*n,
                eligible_rows=7*rows, commits=7*rows, peak_owners=2)


def footer(aw, field):
    return f'S4_P8_WARM_PASS aw={aw} p=8 field={field} ' + ' '.join(
        f'{key}={value}' for key, value in counts(aw, field).items()) + '\n'


def contracts(aw, field):
    return dict(counts=counts(aw, field),
                normal=dict(returncode=0, stdout=footer(aw, field), stderr=''),
                negative=dict(returncode=1, stdout='', stderr='S4_P8_WARM_NEGATIVE_ORACLE_REJECT\n'))


def validate(stdout, stderr, returncode, config, assets):
    need(set(config) == {'aw', 'field', 'negative'} and type(config['negative']) is bool and assets == {},
         'P8_WARM_NATIVE_CONFIG')
    expected = contracts(config['aw'], config['field'])['negative' if config['negative'] else 'normal']
    need(type(stdout) is str and type(stderr) is str and type(returncode) is int and
         (stdout, stderr, returncode) == (expected['stdout'], expected['stderr'], expected['returncode']),
         'P8_WARM_TYPED_OUTPUT')
    return dict(status='PASS_expected_contracts', aw=config['aw'], p=8, field=config['field'],
                negative=config['negative'], promotion_allowed=False,
                scope='One canonical P8 field component. No three-field CRT/carry, host/PRP, board or clock promotion.')


def emitted_bundle(aw, field):
    """Frozen source emitter only, including explicit measured full-size join."""
    n = role_arguments(aw, field); measured = verify()
    from fpga.reference import stream27_shared_field_v1 as generator
    bundle = generator.prepare(n, 8, field, mode='warm', contexts=1, allow_full_constants=True)
    need(bundle['parameters'] == dict(AW=aw, P=8, CONTEXTS=1, FIELD=field) and
         bundle['mode'] == 'warm' and not bundle['full_N_numeric_NTT_performed'], 'P8_WARM_EXACT_EMITTER')
    for name, pin in bundle['source_sha256'].items():
        need(name in measured['preparation_source_sha256'] and
             pin == measured['preparation_source_sha256'][name], 'P8_WARM_EMITTER_DEPENDENCY ' + name)
    if aw == 16:
        need(bundle['top'] == measured['top'] and bundle['geometry'] == measured['geometry'] and
             bundle['generated_sha256'] == measured['source_sha256'], 'P8_WARM_EXACT_MEASURED_23_RTL')
    return bundle, measured


def compile_bench(bundle, field):
    """Keep frozen vectors/reference/tests; add role label and typed control."""
    from fpga.reference import stream27_shared_warm_full_native_v1 as parent
    text, header = parent.compile_bench(bundle, field)
    aw = bundle['parameters']['AW']; role_arguments(aw, field)
    changes = [
        ('using Image=std::array<uint32_t,N>;',
         'static bool negative_oracle=false;\nusing Image=std::array<uint32_t,N>;'),
        ('need(argc==1,"S4_ARGUMENTS");ref_self_check();Counts counts;',
         'negative_oracle=argc==2 && std::string(argv[1])=="--negative-oracle";\n'
         '        need(argc==1 || negative_oracle,"S4_ARGUMENTS");ref_self_check();Counts counts;'),
        ('for(unsigned lane=0;lane<P;++lane)\n                need(unpack(d.data_out,lane)==physical->expected[reverse4(lane)*T+row],',
         'for(unsigned lane=0;lane<P;++lane){\n                need(unpack(d.data_out,lane)==physical->expected[reverse4(lane)*T+row],'),
        ('++counts.physical;counts.words+=P;counts.eligible+=enabled && live;',
         '// After real DUT/reference equality, flip one LOCAL expected word only.\n'
         '                if(negative_oracle && counts.cases==0 && row==0 && lane==0){\n'
         '                    const uint32_t wrong=physical->expected[reverse4(lane)*T+row]^1u;\n'
         '                    need(unpack(d.data_out,lane)==wrong,"S4_P8_WARM_NEGATIVE_ORACLE_REJECT");\n'
         '                }\n            }\n'
         '            ++counts.physical;counts.words+=P;counts.eligible+=enabled && live;'),
        ('std::cout<<"S4_SHARED_AW16_PASS cases="',
         f'need(!negative_oracle,"S4_P8_WARM_NEGATIVE_ORACLE_MISSED");\n'
         f'        std::cout<<"S4_P8_WARM_PASS aw={aw} p=8 field={field} cases="'),
    ]
    for old, new in changes:
        need(text.count(old) == 1, 'P8_WARM_BENCH_DELTA_ANCHOR ' + old[:45])
        text = text.replace(old, new)
    return text, header
