"""Replay AW5 whole-core stdout against exact command vectors, no native work."""
import argparse
import hashlib
import json
from pathlib import Path
import re

VECTOR_SHA = '5236ca15281ec76d3f048b85c11d530818897f5ec7c9655050ca9284670154ec'
FIELDS = ('index','cold','load','double','latency','total','prefill','root','ntt','post','seed')
COUNTS = dict(aw=5, commands=404, squares=14, cold_squares=8, profile_loads=4, readbacks=256, hold_checks=808)


def need(ok, why):
    if not ok: raise ValueError(why)


def tokens(line, prefix, fields):
    need(line.startswith(prefix+' '), 'typed output line')
    pairs = [token.split('=',1) for token in line[len(prefix)+1:].split()]
    need(all(len(pair)==2 and re.fullmatch('[0-9]+',pair[1]) for pair in pairs) and
         tuple(pair[0] for pair in pairs)==tuple(fields), 'unique ordered integer output fields')
    return {name:int(value) for name,value in pairs}


def parse(output, vectors):
    need(hashlib.sha256(vectors.encode()).hexdigest()==VECTOR_SHA, 'exact AW5 whole-integer corpus')
    vector_lines=vectors.splitlines(); need(vector_lines[0]=='A4CORE1 5 404' and len(vector_lines)==405, 'AW5 vector geometry')
    commands=[list(map(int,line.split())) for line in vector_lines[1:]]
    need(all(len(row)==10 for row in commands), 'exact command fields')
    expected=[dict(index=index,cold=row[8],load=row[9],double=row[4]) for index,row in enumerate(commands) if row[0]==5]
    lines=output.splitlines(); need(len(lines)==15, 'fourteen square rows and one footer only')
    rows=[tokens(line,'A4_CORE_SQUARE',FIELDS) for line in lines[:-1]]
    footer=tokens(lines[-1],'A4_CORE_PASS',tuple(COUNTS)+('ticks','max_latency'))
    need(all(footer[name]==value for name,value in COUNTS.items()), 'complete command/readback/profile/hold coverage')
    need(len(expected)==len(rows)==14 and footer['ticks']>0 and footer['max_latency']>0, 'positive complete native measurements')
    hypotheses=[]
    for row,operation in zip(rows,expected):
        need({name:row[name] for name in operation}==operation, 'ordered vector-bound square identity')
        need(row['latency']>0 and row['total']>0 and row['ntt']>0 and row['post']>0 and
             bool(row['prefill'])==bool(row['cold']) and row['latency']<=footer['max_latency'], 'measured phase/profile sanity')
        prediction=dict(post=64,prefill=12*row['cold'],total=row['root']+row['ntt']+68+14*row['cold'],latency=row['total']+2)
        differences={name:dict(measured=row[name],source_hypothesis=value) for name,value in prediction.items() if row[name]!=value}
        if differences:hypotheses.append(dict(index=row['index'],differences=differences))
    return dict(status='replayed_aw5_functional_footer_schedule_review_required',footer=footer,metrics=rows,
        source_schedule_hypotheses_match=not hypotheses,source_schedule_discrepancies=hypotheses,
        vector_sha256=VECTOR_SHA,promotion_allowed=False,
        scope='AW5 real whole-square arithmetic/output/response-hold/reset bench only; full fault matrix and whole-core fit excluded.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output-log',type=Path,required=True);parser.add_argument('--vectors',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(parse(args.output_log.read_text(),args.vectors.read_text()),indent=2))
