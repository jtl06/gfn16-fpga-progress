"""Source-bound actual-leaf reset contracts; no whole reset/clock assertion."""
from fpga.reference import anext_field_reset_release_v1 as model
from fpga.tests import test_anext_field_reset_probe_v1 as probe

ROOT=model.ROOT
SELF='reference/anext_field_reset_native_v1.py'
TEST_HELPER='tests/test_anext_field_reset_probe_v1.py'
PINS=dict(model.PINS,**probe.PINS,**{
    'reference/anext_field_reset_release_v1.py':'d67159efce7c67052a56b6fdf6e9f43bb48e793cd5a5333b67576b6c65eb4a59',
    TEST_HELPER:'261ecb8bc008f9bbc4640748fcffc942ebc8434e4b59817ee48383aaf437fafa',
    model.DIAGNOSIS:model.DIAGNOSIS_SHA,
    'results/throughput-20260929/anext-field-reset-release-source-v1/contract-v1.json':'828e49be75553be19e045cfb3718eb9a1ca8df87063eef3aea07d53d92ed7a7b',
})


def verify():
    model.guard();probe.source_guard()
    for name,pin in PINS.items():
        path=ROOT/name
        model.need(path.is_file() and not path.is_symlink() and model.sha(path.read_bytes())==pin,
                   'ANEXT_RESET_NATIVE_SOURCE_PIN '+name)


def validate(stdout,stderr,returncode,config,assets):
    model.need(set(config)=={'aw','case'} and assets=={},'ANEXT_RESET_NATIVE_CONFIG')
    role=probe.role_config(config['aw'])
    matches=[row for row in role['cases'] if row['name']==config['case']]
    model.need(len(matches)==1,'ANEXT_RESET_NATIVE_FINITE_CASE')
    expected=matches[0]
    model.need(type(stdout) is str and type(stderr) is str and type(returncode) is int and
        (stdout,stderr,returncode)==(expected['expected_stdout'],expected['expected_stderr'],expected['expected_exit']),
        'ANEXT_RESET_NATIVE_TYPED_OUTPUT')
    return dict(status='PASS_expected_contracts',aw=config['aw'],case=config['case'],
        geometry=role['geometry'],calendar=role['calendar'],promotion_allowed=False,
        scope='Reset helper plus actual transfer/blockroute/RAM/Mont/ROM leaves only. Probecollector is not real enginecache/header/wholeoperation or physical signoff.')
