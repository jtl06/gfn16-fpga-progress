"""Additive owner replay distinguishes candidate pins from launcher inputs.

V1 demanded whole manifest equality before host binding added its immutable
runner/admission/budget inputs. Candidate/RTL/CPP/profile bytes were identical.
No native contract or source is changed, and no successful job is repeated.
"""
import argparse
import ast
import json
from pathlib import Path
from . import stream27_threefield_carry_param_replay_v1 as parent
from . import stream27_threefield_carry_param_native_v1 as native
from fpga.tools import global_queue_v1 as queue

PARENT_SHA='3bd62613b623723342037a52df0ba15018412ddfb7c3f069d589d6a73b02aea2'

def candidate_source_join(expected,selected):
    native.need(all(selected.get(name)==pin for name,pin in expected.items()),'S4_PARAM_CANDIDATE_SOURCE_REEMIT')
    return len(expected)

def source_join(manifest,expected,done,aw,p):
    original=native.ROOT/f'results/throughput-20260929/s4-param-carry-aw{aw}-p{p}-native-v1/input/manifest.json'
    original=json.loads(original.read_text())
    native.need(original['sources']==expected['sources'] and original['carry_param']==expected['carry_param'],'S4_PARAM_ORIGINAL_CANDIDATE_REEMIT')
    count=candidate_source_join(expected['sources'],manifest['sources'])
    native.need(manifest['carry_param']==expected['carry_param'],'S4_PARAM_CARRY_PROFILE_REEMIT')
    # The immutable known-control policy removes only exact reviewed launcher
    # additions. Unexpected HDL/CPP/reference/validator sources change identity.
    selected=queue.functional_identity(done['package'])
    originals=[row for row in done['packages'] if row['profile'].startswith('gcp-c4d-static')]
    native.need(len(originals)==2 and all(queue.functional_identity(row)==selected for row in originals),'S4_PARAM_SOURCE_BOUND_FUNCTIONAL_IDENTITY')
    return dict(candidate_sources=count,selected_sources=len(manifest['sources']),functional_sha256=selected,
        delta='Exact reviewed launcher/admission/budget inputs only; zero candidate changes/missing sources.')

def replay(aw,p):
    path=native.ROOT/'reference/stream27_threefield_carry_param_replay_v1.py';raw=path.read_text()
    native.need(native.sha(raw.encode())==PARENT_SHA,'S4_PARAM_REPLAY_FROZEN_PARENT')
    node=next(node for node in ast.parse(raw).body if isinstance(node,ast.FunctionDef) and node.name=='replay')
    text=''.join(raw.splitlines(keepends=True)[node.lineno-1:node.end_lineno])
    old="native.need(manifest['sources']==expected['sources'] and manifest['carry_param']==expected['carry_param'],'S4_PARAM_FROZEN_SOURCE_REEMIT')"
    native.need(text.count(old)==1,'S4_PARAM_REPLAY_ANCHOR');text=text.replace(old,'join=source_join(manifest,expected,done,aw,p)')
    namespace=dict(vars(parent));namespace['source_join']=source_join
    exec(compile(text,str(path)+'[candidate/launcher exact join]','exec'),namespace)
    result=namespace['replay'](aw,p)
    done=json.loads((native.ROOT/'queue/done'/f"{result['id']}.json").read_text());manifest=json.loads((Path(done['package']['archive']).parent/'manifest.json').read_text())
    expected,_=parent.prepare.role(aw,p);result['source_join']=source_join(manifest,expected,done,aw,p)
    result['owner_replay_successor']='V2; preserved V1 local source-map equality failure, not a DUT/typed native failure.'
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--aw',type=int,choices=(5,8),required=True);parser.add_argument('--p',type=int,choices=(8,16),required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();result=replay(args.aw,args.p)
    with args.output.open('x') as stream:json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps(result,indent=2))
