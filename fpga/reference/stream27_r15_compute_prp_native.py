"""Own lean/protected R15 N256 full-exponent numeric twin, separate builds.

Frozen small whole-integer oracle/driver mechanics only; no old execution or
fault/GL/clock qualification. Both source maps and calendars are own R15.
"""
import argparse
import json
from pathlib import Path
from fpga.reference.stream27_context_storage_combo_registerederror_native import sha,need,dump,runtime_before_model

ROOT=Path(__file__).resolve().parents[1]
SELF='reference/stream27_r15_compute_prp_native.py'
CPP='rtl/tb/stream27_context_lean_prp.cpp'
HEADER='rtl/tb/stream27_context_lean_prp_config.h'
ASSET='reference-assets/r10-healthy-prp-n256.json'
RECIPE=ROOT/'results/throughput-20260929/trackS-c2-lean-warmprogress-native-v1/prp-normal-v2'
RECIPE_PIN='8e782fba3fdf145b0c0783e5b5f47fc647b03c85074add1a453e4896e5249508'
CPP_PIN='04e2025323cd23860e4d677af229137a6ac66a7ca5039b7bb2046e61d83d4e70'
ORACLE_PIN='b9956fff4658b8af2e778a796cbff8526c5fec951844c0fe15933793d8caf95f'
HEADER_PIN='b4661a0c7578bc372824642f763a47d3952324b5ad00f0d59ba1c9c0c4dcf2d3'
CAPTURES={
 'lean':('trackS-r15-compute-native-v1/aw8-normal-v2','9ab2753162446e0b0f1ab569ec80dd9ddcccf1580accc1d320baf6b3b2870ed7'),
 'protected':('trackS-r15-compute-protected-twin-native-v1/aw8-normal','8765d20f613eaea5ed78874705851b33d4ab9321910a0dedb4d4d5c05eb9764b'),
}
LABELS=dict(lean='lean build; host GL assumed (unimplemented)',protected='protected R15 verification twin; host GL assumed (unimplemented)')
BASES=(599,600,7552,768,989233152,999999998,999999999,1000000000)
I,C,FIRST=215,214,(204,311)


def config(branch,mode='normal'):
    need(branch in CAPTURES and mode in ('normal','negative-comparator','negative-schedule'),'R15_PRP_LITERAL_CONFIG')
    return dict(family='R15-compute',branch=branch,mode=mode,oracle_sha256=ORACLE_PIN)


def validate(stdout,stderr,rc,config,assets):
    branch,mode=config.get('branch'),config.get('mode')
    need(config==globals()['config'](branch,mode) and set(assets)=={'oracle'} and
         sha(assets['oracle'].encode())==ORACLE_PIN,'R15_PRP_FROZEN_CONFIG_ORACLE')
    label=LABELS[branch];oracle=json.loads(assets['oracle'])
    need(oracle['schema']=='gfn16-r10-healthy-prp-n256-v1' and oracle['n']==256 and oracle['p']==16 and
         [r['base'] for r in oracle['cases']]==list(BASES),'R15_PRP_ORACLE_DOMAIN')
    if mode!='normal':
        need(type(rc) is int and rc==1 and stdout==label+'\n' and
             stderr=='A_PRP_RESIDUE_MISMATCH case=0 digit=0\n','R15_PRP_HOST_CONTROL_SENSITIVITY')
        return dict(status='PASS_expected_contracts',branch=branch,mode=mode,promotion_allowed=False,
          scope='Own same-build host comparator/schedule sensitivity, not RTL fault protection.')
    need(type(rc) is int and rc==0 and stderr=='' and stdout.endswith('\n'),'R15_PRP_NORMAL_EXIT')
    lines=stdout.splitlines();need(len(lines)==12 and lines[0]==label,'R15_PRP_LABELED_EXTENT')
    rows=[]
    for index,line in enumerate(lines[1:11]):
        need(line.startswith('A_CONTEXT_PRP_RESULT '),'R15_PRP_ROW_GRAMMAR')
        row=json.loads(line.removeprefix('A_CONTEXT_PRP_RESULT '))
        need(set(row)=={'case','base','steps','doubles','done_edge','sentinel','digits'},'R15_PRP_ROW_KEYS')
        wanted=oracle['cases'][index] if index<8 else dict(base=BASES[index-8],steps=1,doubles=0,
          expected_digits=oracle['sentinel']['expected_digits'])
        for k,v in (('case',index),('base',wanted['base']),('steps',wanted['steps']),('doubles',wanted['doubles'])):
            need(type(row[k]) is int and row[k]==v,'R15_PRP_FULL_EXPONENT_IDENTITY')
        need(row['sentinel'] is (index>=8) and row['digits']==wanted['expected_digits'] and
             len(row['digits'])==256 and all(type(v) is int for v in row['digits']),'R15_PRP_ALL_SIGNED96_DIGITS')
        counts=[r['steps'] for r in oracle['cases'][index-index%2:index-index%2+2]] if index<8 else [1,1]
        need(type(row['done_edge']) is int and FIRST[index%2]+(wanted['steps']-1)*I+C<
             row['done_edge']<max(counts)*I+33*256+10000,'R15_PRP_OWN_BOUNDED_PUBLICATION')
        rows.append(row)
    need((sum(r['steps'] for r in rows),sum(r['doubles'] for r in rows))==(41091,15137) and lines[-1]==
         'A_CONTEXT_PRP_PASS cases=8 sentinel_cases=2 squares=41091 doubles=15137 signed96_words=2560 interval=215',
         'R15_PRP_COMPLETE_FOOTER')
    return dict(status='PASS_expected_contracts',branch=branch,cases=8,sentinel_cases=2,squares=41091,
      doubles=15137,signed96_words=2560,interval=I,host_GL_implemented=False,protected_fault_credit=False,
      promotion_allowed=False,scope='Own full b^256 exponent numeric outputs and same-DUT special -1, no primality/full-N/GL/fault/clock claim.')


def role(branch='lean',controls=False):
    need(branch in CAPTURES and type(controls) is bool,'R15_PRP_LITERAL_ROLE')
    capture=ROOT/'results/throughput-20260929'/CAPTURES[branch][0]
    raw=(capture/'manifest.json').read_bytes();need(sha(raw)==CAPTURES[branch][1],'R15_PRP_OWN_CAPTURE_PIN')
    m=json.loads(raw);b=json.loads((capture/'production-bundle.json').read_bytes())
    f={n:(capture/'source/fpga'/n).read_bytes() for n in m['sources']}
    need(all(sha(f[n])==pin for n,pin in m['sources'].items()),'R15_PRP_OWN_CAPTURE_CLOSURE')
    g=b['geometry'];flags=b['r15_all']['flags']
    need((g['n'],g['warm_interval'],g['carry_done'])==(256,I,C) and len(b['files'])==60 and
         flags==dict(FIXED_SCHEDULE=1,LEAN_BUILD=int(branch=='lean'),PROGRESS_WATCHDOG=1,STORAGE_TO_RAM=1,DIRECT_COLD=0,PCIE_SHELL=0) and
         m['build']['parameters']==dict(b['parameters'],EPOCH_SEED0=65534,EPOCH_SEED1=42),'R15_PRP_OWN_GRAPH_PARAMETERS')
    need(sha((RECIPE/'manifest.json').read_bytes())==RECIPE_PIN,'R15_PRP_FROZEN_MECHANICS')
    cpp,header,oracle=((RECIPE/'source/fpga'/n).read_bytes() for n in (CPP,HEADER,ASSET))
    need((sha(cpp),sha(header),sha(oracle))==(CPP_PIN,HEADER_PIN,ORACLE_PIN),'R15_PRP_CPP_HEADER_ORACLE_PINS')
    old=json.loads((RECIPE/'production-bundle.json').read_bytes())['top'];text=header.decode()
    need(text.count(old)==2 and text.count('INTERVAL=214,CARRY_DONE=214')==1 and
         text.count('FIRST[2]={204,311}')==1,'R15_PRP_HEADER_ONLY_TOP_I_LABEL_DELTA')
    text=text.replace(old,b['top']).replace('INTERVAL=214,CARRY_DONE=214','INTERVAL=215,CARRY_DONE=214')
    text=text.replace(LABELS['lean'],LABELS[branch])
    runtime_before_model(cpp.decode());f.update({CPP:cpp,HEADER:text.encode(),ASSET:oracle,SELF:(ROOT/SELF).read_bytes()})
    m['build']['cpp_source']=CPP
    modes=('negative-comparator','negative-schedule') if controls else ('normal',)
    m['steps']=[dict(name='r15-'+branch+'-prp-'+mode,argv=['{exe}']+([] if mode=='normal' else ['--'+mode]),
      expected_returncode=0 if mode=='normal' else 1,validator=dict(source=SELF,function='validate',
      config=config(branch,mode),assets=dict(oracle=ASSET))) for mode in modes]
    identifier='s4-r15-compute-'+branch+'-prp-'+('controls' if controls else 'normal')+'-q1-v1'
    m['r15_prp']=dict(production_top=b['top'],production_generated_sha256=b['generated_sha256'],
      own_capture_sha256=CAPTURES[branch][1],flags=flags,branch=branch,cpp_sha256=CPP_PIN,oracle_sha256=ORACLE_PIN,
      interval=I,carry_done=C,first=list(FIRST),separately_compiled=True,publication_fence=1,copy_edges=260,
      no_ancestor_result_clock_protection_GL_credit=True,promotion_allowed=False)
    m['sources']={n:sha(v) for n,v in f.items()};snapshot={n:p for n,p in m['sources'].items() if n.endswith('.sv')}
    m.update(source_root='UNBOUND',output_parent='UNBOUND',test_role='deliberate_fault' if controls else 'normal',
      rtl_readiness=dict(schema='gfn16-candidate-rtl-ready-v1',candidate_id=identifier.removesuffix('-q1-v1'),
      source_snapshot=snapshot,candidate_source_sha256=sha(json.dumps(snapshot,sort_keys=True,separators=(',',':')).encode()),
      rtl_ready_at_utc=m['rtl_readiness']['rtl_ready_at_utc']))
    return m,f,b,identifier


def freeze(branch='lean',controls=False):
    m,f,b,id=role(branch,controls);out=ROOT/'results/throughput-20260929/trackS-r15-compute-prp-native-v1'/(branch+'-'+('controls' if controls else 'normal'))
    need(not out.exists(),'R15_PRP_FRESH_OUTPUT');source=out/'source/fpga';source.mkdir(parents=True)
    for n,v in f.items():
        p=source/n;p.parent.mkdir(parents=True,exist_ok=True)
        with p.open('xb') as stream:stream.write(v)
    m['source_root']=str(source);dump(out/'manifest.json',m);dump(out/'production-bundle.json',b)
    return dict(id=id,manifest=str(out/'manifest.json'),status='SOURCE_NOT_NATIVE')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--branch',choices=tuple(CAPTURES),default='lean');p.add_argument('--controls',action='store_true')
    a=p.parse_args();print(json.dumps(freeze(a.branch,a.controls),indent=2))
