"""Finite source-bound real-RAM host pair contracts; no square/clock claim."""
from pathlib import Path
from fpga.reference import anext_cancel_distribution_v1 as gen

ROOT=gen.ROOT
TOP='genefer_anext_cancel_host_pair_v1'
PAIR='rtl/tb/'+TOP+'.sv'
CPP='rtl/tb/anext_cancel_host_pair_v1.cpp'
COMMON={
    'rtl/kernel/genefer_track_a4_control_contract_v1.sv':'60283c4d0b309a62e8f2dee37a5e504f8907ec1917375c5214bcddaa3241b987',
    'rtl/kernel/genefer_track_a4_control_fsm_v2.sv':'343d392e1b69f4230e3a59029aafd3355e8139b502589ff56c7b1fbe1bf49d03',
    'rtl/kernel/genefer_track_a4_setup_v1.sv':'23d2a6832dc589fd8782cc7ed3f90980be1018b833d1a94714ab34058915da25',
    'rtl/kernel/genefer_track_a4_canonical_cell_v1.sv':'cce93ddf7c7318e3297b88dc89d900ab4f0bcaa394be8bec141160ace080ac5c',
    'rtl/kernel/genefer_track_a4_canonical_controller_v2.sv':'f8d8e523ac934dfd3df2b697fe03be14250a584da2aaca761779feaf03f3fbba',
    'rtl/kernel/genefer_sdp_ram32.sv':'993567fb68fdc216b9ff04489d1810f743b86564434e4b48261ad606b25d53b0',
}
PINS=dict(gen.PARENTS,**COMMON,**{
    gen.TARGETS['word']:'6f2e705eb8e039e6a7b1b614223d58bc836d9ccd5ca9221cd4e3628d30202cb6',
    gen.TARGETS['image']:'ab3c84b08d522ebcd8e1b882f20c51f35e3ae817918f70299b4a0f1bc66ada09',
    gen.TARGETS['shell']:'1f5d878f6ffbdb9d745b36ed5926a7ee1a4d417ea8b9dee418b8991c70e220c7',
    'reference/anext_cancel_distribution_v1.py':'77537400a19764fdecb6fec4b7fe04e6c02e247d35cb8c4449b1830399fa51e7',
    PAIR:'90e4b5c79ec223861dc6056d6acb1eeb0c6730a661914d7904ff6bc900208d37',
    CPP:'eec3ea3d070a0a74533aa6f6df7372bb2caab27e2ce00fde61d86de43053567c',
})
SV_SOURCES=[*COMMON,'rtl/kernel/genefer_track_a4_digit_image_v1.sv',
    'rtl/kernel/genefer_track_a4_host_word_v1.sv','rtl/kernel/genefer_track_a4_host_shell_v2.sv',
    gen.TARGETS['word'],gen.TARGETS['image'],gen.TARGETS['shell'],PAIR]


def verify():
    for name,pin in PINS.items():
        path=ROOT/name
        gen.need(path.is_file() and not path.is_symlink() and gen.sha(path.read_bytes())==pin,
                 'ANEXT_CANCEL_NATIVE_SOURCE_PIN '+name)
    gen.guard()
    for kind,name in gen.TARGETS.items():
        gen.need((ROOT/name).read_text()==gen.source(kind),'ANEXT_CANCEL_NATIVE_LITERAL_DELTA')


def counts(aw):
    gen.need(type(aw) is int and aw in (5,8),'ANEXT_CANCEL_NATIVE_GEOMETRY')
    n=1<<aw;t=n//16
    return dict(commands=7*n+29,readbacks=n+12,error_responses=4,explicit_hold_checks=14*n+61,
        host_cases=6,cancel_seams=4,ram_words=17*n,image_read_words=28*t+192,
        image_faults=7,image_cancels=8,image_ram_words=20*n,ticks=67*n+5*t+1139,max_latency=max(100,2*n+12))


def contracts(aw):
    normal=f'ANEXT_CANCEL_HOST_PAIR_PASS aw={aw} '+' '.join(f'{k}={v}' for k,v in counts(aw).items())+'\n'
    return dict(normal=dict(returncode=0,stdout=normal,stderr=''),
                negative=dict(returncode=1,stdout='',stderr='ANEXT_CANCEL_HOST_NEGATIVE_ORACLE_REJECT\n'))


def validate(stdout,stderr,returncode,config,assets):
    gen.need(set(config)=={'aw','negative'} and type(config['negative']) is bool and assets=={},
             'ANEXT_CANCEL_NATIVE_VALIDATOR_CONFIG')
    expected=contracts(config['aw'])['negative' if config['negative'] else 'normal']
    gen.need(type(stdout) is str and type(stderr) is str and type(returncode) is int and
             (stdout,stderr,returncode)==(expected['stdout'],expected['stderr'],expected['returncode']),
             'ANEXT_CANCEL_NATIVE_TYPED_OUTPUT')
    return dict(status='PASS_expected_contracts',aw=config['aw'],negative=config['negative'],
        promotion_allowed=False,scope='Paired real host/setup/canonical/RAM only. No square backend or whole reset/clock qualification.')
