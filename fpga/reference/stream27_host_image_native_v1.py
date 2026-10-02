"""Source-bound finite paired idle-T5b host-image contracts; no HDL invocation."""
import hashlib
import json
from pathlib import Path

from fpga.reference import stream27_host_image_model_v1 as model

ROOT = Path(__file__).resolve().parents[1]
TOP = 'genefer_stream27_host_image_ports_pair_v1'
SV = 'rtl/kernel/genefer_stream27_host_image_ports_v1.sv'
PAIR = 'rtl/tb/' + TOP + '.sv'
CPP = 'rtl/tb/stream27_host_image_ports_v1.cpp'
RAM = 'rtl/kernel/genefer_sdp_ram32.sv'
MODEL = 'reference/stream27_host_image_model_v1.py'
T5B_MANIFEST = 'results/throughput-20260929/core27-t5b-provisional64-aws-fit-v1/manifest.json'
T5B_MANIFEST_SHA = '1a1a67980f1744be70c0b089dcdf7e20c4cdd8714cbac26bd5798c28abbcc011'
T5B_TOP = 'genefer_square_core27_stream_prefetch_r2_host_broadcast_orient8_rootfused_crtmont_prefill_pipe_v1'
T5B_TOP_SHA = '704f7fed433d724dbc8e56c7b725824ec36cce78d6ce8f021307837d2a96b8e7'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def parent_pins(root=ROOT):
    path = Path(root)/T5B_MANIFEST
    model.need(path.is_file() and not path.is_symlink() and sha(path.read_bytes()) == T5B_MANIFEST_SHA,
               'HOST_IMAGE_T5B_MANIFEST_DRIFT')
    value = json.loads(path.read_text())
    pins = value['source_sha256']
    model.need(value['top'] == T5B_TOP and value['core_parameters'] == {'NTT_LANES': 64} and
               len(pins) == 16 and pins[T5B_TOP + '.sv'] == T5B_TOP_SHA and
               pins['genefer_sdp_ram32.sv'] == '993567fb68fdc216b9ff04489d1810f743b86564434e4b48261ad606b25d53b0' and
               all(Path(name).name == name and name.endswith('.sv') for name in pins),
               'HOST_IMAGE_ACTUAL_T5B_CLOSURE')
    return {'rtl/kernel/' + name: pin for name, pin in pins.items()}


T5B_PINS = parent_pins()
PINS = dict(T5B_PINS, **{
    T5B_MANIFEST: T5B_MANIFEST_SHA,
    SV: '2d1dbcd3d923323481b920d1354127306cf19253ee98ad60c0a87626cb1ba11e',
    PAIR: 'd06eb673fecd6404f632cb3be80da7cae037707a9d67a65e858e713c66dab799',
    CPP: '85f05c8de95e2c9e0acfec84538c70e7f57c198f9292beaa2fa75ccd6b9050f1',
    MODEL: 'cdff1c82e7df40541785cdcc2df5c91e92effd463284ec05f8c43f566d381d54',
})


def verify(root=ROOT):
    model.need(parent_pins(root) == T5B_PINS, 'HOST_IMAGE_PARENT_MAP_DRIFT')
    for name, pin in PINS.items():
        path = Path(root)/name
        model.need(path.is_file() and not path.is_symlink() and sha(path.read_bytes()) == pin,
                   'HOST_IMAGE_SOURCE_DRIFT ' + name)
    return dict(PINS)


def contracts(aw, p):
    model.need(type(aw) is int and aw in (5, 8) and type(p) is int and p in (8, 16),
               'HOST_IMAGE_NATIVE_SMALL_GEOMETRY')
    counts = model.native_counts(aw, p)
    positive = f'HOST_IMAGE_PORTS_PASS aw={aw} p={p} ' + ' '.join(f'{k}={v}' for k, v in counts.items()) + ' read_edge=E0\n'
    return dict(counts=counts,
                normal=dict(returncode=0, stdout=positive, stderr=''),
                negative=dict(returncode=1, stdout='', stderr='HOST_IMAGE_NEGATIVE_ORACLE_REJECT\n'))


def validate(stdout, stderr, returncode, config, assets):
    model.need(set(config) == {'aw', 'p', 'negative'} and type(config['negative']) is bool and assets == {},
               'HOST_IMAGE_NATIVE_CONFIG')
    expected = contracts(config['aw'], config['p'])['negative' if config['negative'] else 'normal']
    model.need(type(stdout) is str and type(stderr) is str and type(returncode) is int and
               (stdout, stderr, returncode) == (expected['stdout'], expected['stderr'], expected['returncode']),
               'HOST_IMAGE_NATIVE_TYPED_OUTPUT')
    return dict(status='PASS_expected_contracts', aw=config['aw'], p=config['p'],
                negative=config['negative'], promotion_allowed=False,
                scope='Paired idle scalar host component only; T5b start remains zero.')
