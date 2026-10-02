"""Normal full-size matched-base test of the shared canonical register flag.

Same dense signed image and two dependent host jobs as the frozen full test;
only finalization becomes9N/10N. No coordinator full-N arithmetic execution.
"""
import argparse
import ast
import hashlib
import json
from pathlib import Path
from fpga.reference import stream27_host_chain_full_native_v1 as old

ROOT=old.ROOT
SELF='reference/stream27_host_chain_canonpipe_native_v1.py'
TEST='tests/test_stream27_host_chain_canonpipe_native_v1.py'
IDENTIFIER='s4-aw16-p8-canon-pipe-host-normal-q1-v1'
DEPENDENCY='s4-canon-pipe-aw8-p8-normal-q1-v1'
BASE=604832956


def counts():
    c=old.counts()
    c['canonical_cycles']+=6*old.N
    c['candidate_cycles']+=6*old.N
    return c


def validate(stdout,stderr,returncode,config,assets):
    import re
    old.need(config==dict(aw=16,p=8,base=BASE,canonical_pipe_stages=1,mode='normal') and assets=={},'S4_CANON_PIPE_FULL_CONFIG')
    prefix='S4_CANON_PIPE_HOST_PASS aw=16 p=8 '+' '.join(f'{k}={v}' for k,v in counts().items())+' t5b_wait_edges='
    match=re.fullmatch(re.escape(prefix)+r'([1-9][0-9]*)\n',stdout,re.ASCII)
    old.need(returncode==0 and stderr=='' and bool(match),'S4_CANON_PIPE_FULL_TYPED_NORMAL')
    wait=int(match.group(1));old.need(9<=wait<=9*(20*old.N+100000),'S4_CANON_PIPE_FULL_T5B_BOUND')
    return dict(status='PASS_expected_contracts',base=BASE,canonical_pipe_stages=1,counts=counts(),
        measured_t5b_wait_edges=wait,scope='Exact fullN9ops/two final images, all131072 signed96 T5b/reference words; new canonical register flag; not PRP/1000/physical clock/promotion.')


def role():
    from fpga.reference import stream27_host_chain_param_v3 as core
    m,files=old.role()
    b=core.prepare(old.N,old.P,paired=True,contexts=1,allow_full_constants=True,canonical_pipe_stages=1)
    standalone=core.prepare(old.N,old.P,paired=False,contexts=1,allow_full_constants=True,canonical_pipe_stages=1)
    old.need(all(b['files'].get(name)==text for name,text in standalone['files'].items()),'S4_CANON_PIPE_FULL_PAIR_JOIN')
    files={name:raw for name,raw in files.items() if not name.endswith('.sv')}
    files.update({'rtl/'+name:text.encode() for name,text in b['files'].items()})
    for path in b['source_dependencies']:
        files['lineage/'+path]=(ROOT/path).read_bytes()
    files[SELF]=(ROOT/SELF).read_bytes();files[TEST]=(ROOT/TEST).read_bytes()
    s=files[old.CPP].decode()
    changes=[('(special?7u:6u)','(special?10u:9u)'),('c.canonical==12*N','c.canonical==18*N'),('S4_FULL_HOST_PASS aw=16 p=8','S4_CANON_PIPE_HOST_PASS aw=16 p=8')]
    for before,after in changes:
        old.need(s.count(before)==(2 if before=='(special?7u:6u)' else 1),'S4_CANON_PIPE_FULL_BENCH_ANCHOR')
        s=s.replace(before,after)
    files[old.CPP]=s.encode()
    header=f'''#include <cstdint>
#include "V{b['top']}.h"
using DUT=V{b['top']};
constexpr unsigned AW=16,P=8,N=65536,BASE={BASE};
constexpr uint64_t FIRST_DIGIT=16652,INTERVAL=16653,CARRY_DONE=24847,EXPECTED_CYCLES={counts()['candidate_cycles']},T5B_WAIT_LIMIT=20*N+100000;
'''
    files[old.HEADER]=header.encode()
    m['sources']={name:old.sha(raw) for name,raw in files.items()}
    m['build'].update(top=b['top'],sv_sources=['rtl/'+name for name in b['rtl_sources']],
        parameters=dict(AW=16,P=8,CONTEXTS=1,EPOCH_SEED=65534,CANONICAL_PIPE_STAGES=1))
    m['steps']=[dict(name='canonical-pipe-full-host-normal',argv=['{exe}'],expected_returncode=0,
        validator=dict(source=SELF,function='validate',config=dict(aw=16,p=8,base=BASE,canonical_pipe_stages=1,mode='normal'),assets={}))]
    m['full_host'].update(base=BASE,counts=counts(),geometry=b['geometry'],host_contract=b['host_contract'],
        cycle_contract=b['cycle_contract'],generated_sha256=b['generated_sha256'],source_sha256=b['source_sha256'],
        standalone_top=standalone['top'],standalone_generated_sha256=standalone['generated_sha256'],
        candidate_root_sha256=old.sha(standalone['files'][standalone['top']+'.sv'].encode()),
        physical_source_manifest=None,physical_source_manifest_sha256=None,
        shared_delta='Only final canonical signed-value register boundary and explicit build flag; all warm/CRT/carry/field/FIFO arithmetic bytes preserved.',
        scope='Normal-first matched604832956 canonical-register whole-host candidate; old physical fit is baseline only, not inherited.')
    return m,files


def prepare(output,budget,revision=1):
    raw=(ROOT/old.SELF).read_text()
    node=next(x for x in ast.parse(raw).body if isinstance(x,ast.FunctionDef) and x.name=='prepare')
    body=''.join(raw.splitlines(keepends=True)[node.lineno-1:node.end_lineno])
    changes=[("'s4-aw16-p8-full-host-'+pair+'-v1'","'s4-aw16-p8-canon-pipe-host-'+pair+'-v1'"),
        ("owner='canonical-native-bench'","owner='stream-core'"),
        ('promotion_bound=False, packages=variants,',"promotion_bound=False, test_role='normal', packages=variants,")]
    for before,after in changes:
        old.need(body.count(before)==1,'S4_CANON_PIPE_FULL_PACKAGE_ANCHOR');body=body.replace(before,after)
    old.need(type(revision) is int and revision in (1,2),'S4_CANON_PIPE_FULL_REVISION')
    if revision==2:
        body=body.replace("'s4-aw16-p8-canon-pipe-host-'+pair+'-v1'", "'s4-aw16-p8-canon-pipe-host-'+pair+'-v2'")
    ns=dict(vars(old));ns.update(role=role,IDENTIFIER=IDENTIFIER if revision==1 else IDENTIFIER[:-1]+'2',
        DEPENDENCY=DEPENDENCY if revision==1 else DEPENDENCY[:-1]+'2')
    exec(compile(body,'[canonical register normal packaging]','exec'),ns)
    return ns['prepare'](output,budget)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--budget',type=Path,required=True)
    p.add_argument('--revision',type=int,choices=(1,2),default=1)
    a=p.parse_args();r=prepare(a.output,a.budget,a.revision);print(json.dumps(dict(status=r['status'],id=IDENTIFIER if a.revision==1 else IDENTIFIER[:-1]+'2',base=BASE,canonical_pipe_stages=1)))
