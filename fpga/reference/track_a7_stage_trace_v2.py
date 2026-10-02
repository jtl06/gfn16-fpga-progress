"""A7 reporting successor: total every order and retain the tight tail witness.

Frozen v1 parser, physical trace checks and bound computation are unchanged.
This is event-only analysis, not an RTL interlock or numeric NTT mutation.
"""
from .track_a7_stage_trace_v1 import *
from .track_a7_stage_trace_v1 import analyze as _parent_analyze


def analyze(n,events):
    result=_parent_analyze(n,events)
    transitions=result['transitions']
    names=sorted({name for t in transitions for name in t['orders']})
    result['totals_per_square']={str(run):{
        name:sum(t['orders'][name]['memory_only_recoverable'] for t in transitions if t['run']==run)
        for name in names} for run in sorted({t['run'] for t in transitions})}
    result['threshold_met']=any(max(row.values())>=600 for row in result['totals_per_square'].values())
    return result


def missing_interlock_witness(n=256):
    require(n==256,'A7_DIRECTED_TAIL_GEOMETRY')
    writes={(bank,row):group+7 for group in range(2)
            for bank,row in enumerate(stage_rows(n,7,group)) if row>=0}
    hazards=[dict(kind='A7_MISSING_INTERLOCK_RAW',n=n,from_stage=7,to_stage=6,
                  bank=bank,row=row,read_edge=group+2,required_after=writes[bank,row])
             for group in range(2) for bank,row in enumerate(stage_rows(n,6,group))
             if row>=0 and group+2<=writes[bank,row]]
    require(hazards,'A7_HAZARD_WITNESS_ABSENT')
    return max(hazards,key=lambda h:(h['required_after']-h['read_edge'],-h['bank']))


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('trace',type=Path)
    parser.add_argument('--preparation',type=Path,required=True)
    args=parser.parse_args();text=args.trace.read_text();n,events=parse(text)
    preparation=json.loads(args.preparation.read_text())
    verify_native_metrics(text,preparation['profiles'][str(n.bit_length()-1)]['vector_lineage'])
    print(json.dumps(analyze(n,events),indent=2))


if __name__=='__main__':main()
