"""Model-only common front PAYLOAD feasibility; no emitted/replaced RTL.

Source register semantics, including rejected-token occupancy and public hold,
are modeled independently from numeric admission. Literal owner sharing fails
the existing isolated lane-tag fault contract. An independent full-origin
checker is a necessary design condition, NOT a supplied hardware/oracle guard.
"""
import argparse
import hashlib
import json
from pathlib import Path
import random
import sys

ROOT=Path(__file__).resolve().parents[1]
PRIMES=(104857601,69206017,67239937)
BUNDLE='results/throughput-20260929/trackS-c2-timing-v1/full-normal-v1/production-bundle.json'
BUNDLE_PIN='1a83f078d22add706906e292acde286f7d73da276efb10dd5b1015b769f7a8d3'
SOURCES=('rtl/kernel/genefer_digit_reduce27_pipe.sv',
         'rtl/kernel/genefer_stream27_signed_boundary_reduce27_pipe.sv',
         'rtl/kernel/genefer_stream27_signed_boundary_inputreg_v1.sv')


class Digit:
    def __init__(self,p,width):
        self.p=p;self.width=width;self.good=[0]*3;self.bad=[0]*3
        self.tags=[0x31415926 & ((1<<width)-1)]*3;self.s=[123,456,789]
        self.valid=self.error=0;self.residue=self.payload=0

    def step(self,valid,word,payload,reset=False):
        if reset:
            self.good=[0]*3;self.bad=[0]*3;self.valid=self.error=0;self.residue=self.payload=0
            return self.view()
        g,b,t,s=self.good[:],self.bad[:],self.tags[:],self.s[:]
        legal=0<=word<=999999999 or word==0xffffffff
        normalized=self.p-1 if word==0xffffffff else word
        self.valid,self.error=g[2],b[2]
        if g[2]:self.residue=s[2]-self.p if s[2]>=self.p else s[2]
        if g[2] or b[2]:self.payload=t[2]
        if valid:self.tags[0]=payload & ((1<<self.width)-1)
        if g[0] or b[0]:self.tags[1]=t[0]
        if g[1] or b[1]:self.tags[2]=t[1]
        if valid and legal:self.s[0]=normalized-8*self.p if normalized>=8*self.p else normalized
        if g[0]:self.s[1]=s[0]-4*self.p if s[0]>=4*self.p else s[0]
        if g[1]:self.s[2]=s[1]-2*self.p if s[1]>=2*self.p else s[1]
        self.good=[int(valid and legal)]+g[:2];self.bad=[int(valid and not legal)]+b[:2]
        return self.view()

    def view(self):return (self.valid,self.error,self.residue,self.payload)


class Owner:
    """No arithmetic authority: occupied includes legal AND rejected tokens."""
    def __init__(self,width,latency=3):
        self.width=width;self.latency=latency;self.slots=[0]*latency
        self.tags=[0x27182818 & ((1<<width)-1)]*latency;self.out_slot=0;self.payload=0

    def step(self,valid,payload,reset=False):
        if reset:self.slots=[0]*self.latency;self.out_slot=0;self.payload=0;return (0,0)
        slots,tags=self.slots[:],self.tags[:]
        self.out_slot=slots[-1]
        if slots[-1]:self.payload=tags[-1]
        if valid:self.tags[0]=payload & ((1<<self.width)-1)
        for i in range(1,self.latency):
            if slots[i-1]:self.tags[i]=tags[i-1]
        self.slots=[int(valid)]+slots[:-1]
        return self.out_slot,self.payload


class Boundary:
    def __init__(self,p,inputreg=True):
        self.p=p;self.inputreg=inputreg;self.mag=Digit(p,28)
        self.slot=0;self.capture=(0,2,False,0)
        self.valid=self.error=0;self.residue=self.payload=0

    def step(self,valid,correction,base,high,owner,reset=False,quarantine=False):
        if reset:
            self.slot=0;self.valid=self.error=0;self.residue=self.payload=0
            self.mag.step(False,0,0,reset=True);return self.view()
        mv,me,mr,mp=self.mag.view()
        self.valid,self.error=mv,me
        if mv:self.residue=self.p-mr if (mp>>27) and mr else mr
        if mv or me:self.payload=mp & ((1<<27)-1)
        if self.inputreg:
            admitted=self.slot;word,b,h,o=self.capture
            self.slot=int(valid and not quarantine)
            if valid and not quarantine:self.capture=(correction,base,high,owner)
        else:admitted=valid;word,b,h,o=correction,base,high,owner
        k=2*65536+24*16
        floor=max(2*65536+5,(2*k+2)//3+1)
        legal=floor<=b<=1000000000 and abs(word)<=(k if h else b-1)
        magnitude=abs(word) if legal else 0x80000000
        self.mag.step(admitted,magnitude,((word<0)<<27)|o)
        return self.view()

    def view(self):return (self.valid,self.error,self.residue,self.payload)


def join(outputs):
    good=[v[0] for v in outputs];bad=[v[1] for v in outputs]
    all_good=all(good)
    pending=any(bad) or (any(good) and not all_good)
    if all_good:pending |= any(v[3]!=outputs[0][3] for v in outputs[1:])
    return all_good,bool(pending)


def locked_sources():
    raw=(ROOT/BUNDLE).read_bytes();b=json.loads(raw);files=b['files']
    if hashlib.sha256(raw).hexdigest()!=BUNDLE_PIN:raise ValueError('FRONT_TIMING58_BUNDLE')
    for path in SOURCES:
        name=path.rsplit('/',1)[1]
        if files[name]!=(ROOT/path).read_text():raise ValueError('FRONT_SOURCE_'+name)
    for f in range(3):
        source=files[f'genefer_stream27_shared_warm_aw16_p16_f{f}_v1_timing_c2_v1.sv']
        for text in ('.in_valid(accepted)', '.payload_in({digit_generation,frame_start,digit_row})',
                     '.in_valid(boundary_slot)', '.quarantine(stop)', '.payload_in(boundary_owner)'):
            if text not in source:raise ValueError('FRONT_ACCEPT_SOURCE_'+text)
    return dict(bundle=BUNDLE,bundle_sha256=hashlib.sha256(raw).hexdigest(),sources={
        path:hashlib.sha256((ROOT/path).read_bytes()).hexdigest() for path in SOURCES},
        geometry=b['geometry'],parameters=b['parameters'])


def storage_compatibility():
    """Existing pure source binder only: no source generation/write/job."""
    sys.path.insert(0,str(ROOT.parent))
    from fpga.reference import stream27_context_storage_timing_bind as storage
    b=json.loads((ROOT/BUNDLE).read_bytes());c=storage.bind(b,enabled=1)
    def front(text):
        start=text.index(' logic [LANES-1:0] digit_valid,digit_error,boundary_valid,boundary_error;')
        end=text.index(' wire small_twist_slot,',start)
        return text[start:end]
    field_pairs=[v for v in c['storage_contract']['changed'] if v['parent'].startswith('genefer_stream27_shared_warm_')]
    if len(field_pairs)!=3:raise ValueError('FRONT_STORAGE_FIELDS')
    for pair in field_pairs:
        if front(b['files'][pair['parent']])!=front(c['files'][pair['candidate']]):
            raise ValueError('FRONT_STORAGE_CHANGED')
    return dict(unchanged_front_regions=3,unchanged_geometry=b['geometry']==c['geometry'],
        unchanged_leaf_bodies=all(b['files'][p.rsplit('/',1)[1]]==c['files'][p.rsplit('/',1)[1]] for p in SOURCES),
        helper=storage.SELF,helper_sha256=hashlib.sha256((ROOT/storage.SELF).read_bytes()).hexdigest(),
        scope='Pure exact timing58-to-storage2 binder comparison; no inherited native or physical qualification.')


def checks(seed=0x6a09e667,cycles=512):
    rng=random.Random(seed);events=0;numeric=0;rejected=0;quiet=0;published=0
    for p in PRIMES:
        for kind in ('digit','boundary'):
            width,latency=(38,3) if kind=='digit' else (27,5)
            lanes=[Digit(p,width) if kind=='digit' else Boundary(p) for _ in range(16)]
            shared=Owner(width,latency);history={};held=0
            for edge in range(cycles):
                reset=edge in (0,61,62,203);cancel=edge in (23,59,60,201,202,407)
                quarantine=kind=='boundary' and edge in (31,32,88,89)
                valid=bool(rng.randrange(4)) and not cancel
                owner=rng.getrandbits(width);expected_occupied=valid and not quarantine
                if reset:history={}
                elif expected_occupied:history[edge]=(owner,[])
                outputs=[]
                for lane in lanes:
                    if kind=='digit':
                        corpus=(0,1,p-1,p,999999999,0xffffffff)
                        if edge%8:corpus += (0xfffffffe,1000000000)
                        word=rng.choice(corpus)
                        out=lane.step(valid,word,owner,reset=reset)
                        legal=word<=999999999 or word==0xffffffff
                        value=p-1 if word==0xffffffff else word%p
                    else:
                        base=rng.choice((604832956,999999937));high=bool(rng.getrandbits(1))
                        limit=2*65536+24*16 if high else base-1
                        corpus=(-limit,limit,-1,0,1)
                        if edge%8:corpus += (limit+1,-limit-1)
                        word=rng.choice(corpus)
                        out=lane.step(valid,word,base,high,owner,reset=reset,quarantine=quarantine)
                        legal=abs(word)<=limit;value=word%p
                    outputs.append(out)
                    if not reset and expected_occupied:history[edge][1].append((legal,value))
                occupied,payload=shared.step(expected_occupied,owner,reset=reset)
                expected=history.get(edge-latency) if not reset else None
                if occupied != bool(expected):raise ValueError('OCCUPIED_CALENDAR')
                if expected:held=expected[0]
                if payload!=held and not reset:raise ValueError('PUBLIC_OWNER_HOLD')
                if reset:held=0
                for lane,out in enumerate(outputs):
                    if out[3]!=payload:raise ValueError('OWNER_EQUIVALENCE')
                    if bool(out[0] or out[1])!=bool(expected):raise ValueError('REJECTED_ORIGIN')
                    if expected:
                        legal,value=expected[1][lane]
                        if bool(out[0])!=legal or bool(out[1])==legal:raise ValueError('LANE_AUTHORITY')
                        if legal and out[2]!=value:raise ValueError('NUMERIC_RESIDUE')
                        numeric+=int(legal);rejected+=int(not legal)
                slot,pending=join(outputs)
                # Leaf tails are NOT flushed by quarantine/cancel. Immediate
                # outer eligibility kill is separate from raw occupancy.
                commit=slot and not pending and not cancel and not quarantine and not reset
                if (cancel or quarantine or reset) and commit:raise ValueError('IMMEDIATE_PUBLICATION_KILL')
                quiet+=int(occupied and not commit);published+=int(commit);events+=1
    return dict(events=events,valid_numeric_outputs=numeric,rejected_lane_tokens=rejected,
        occupied_but_unpublished_edges=quiet,seed=seed,per_kind_per_prime_edges=cycles,
        model_eligible_normal_edges=published,source_register_model_only=True)


def corruption_counterexample(width=38):
    old=[Digit(PRIMES[0],width) for _ in range(16)];shared=Owner(width)
    for leaf in old:leaf.step(True,7,5)
    shared.step(True,5)
    for leaf in old:leaf.step(False,0,0)
    shared.step(False,0)
    old[-1].tags[1]^=1;shared.tags[1]^=1
    for leaf in old:leaf.step(False,0,0)
    shared.step(False,0)
    old_out=[leaf.step(False,0,0) for leaf in old];_,tag=shared.step(False,0)
    shared_out=[(v,e,r,tag) for v,e,r,unused in old_out]
    return dict(isolated_old_lane_tag_pending=join(old_out)[1],
        shared_tag_corruption_pending_without_independent_origin=join(shared_out)[1],
        old_expected_owner=5,actual_shared_corrupted_owner=tag,
        verdict='NO_GO_LITERAL_SHARING: common corruption bypasses lane-equality guard. Independent origin integrity or a separately authorized fault ABI is required; parity alone misses even-bit faults.')


def analyze():
    source=locked_sources();result=checks();counterexample=corruption_counterexample()
    if not counterexample['isolated_old_lane_tag_pending'] or counterexample['shared_tag_corruption_pending_without_independent_origin']:
        raise ValueError('COUNTEREXAMPLE_NOT_ESTABLISHED')
    return dict(status='MODEL_FUNCTIONAL_GO_FAULT_EQUIVALENCE_NO_GO',source=source,checks=result,
        storage2_compatibility=storage_compatibility(),
        source_metadata_budget=dict(outer_payload_width=38,outer_common_register_bits_per_lane=4*38,
            boundary_private_sign_register_bits_per_lane=4,boundary_core_common_bits_per_lane=5*27,
            timing58_boundary_common_bits_per_lane=6*27,actual_report_outer_lanes=48,
            actual_report_boundary_lanes=48,compact_parent_declared_common_bits=48*(4*38+5*27),
            timing58_declared_common_bits=48*(4*38+6*27),
            report_outer_FF_per_lane=274,report_boundary_magnitude_FF_per_lane=234,
            report_boundary_parent_FF_per_lane=56,
            limitation='Declaration budget agrees with total fitted subtree FF shape, not a bit-named removable physical FF inventory or ALM/LAB saving. Timing58 ingress owner27 perlane is source-only relative to compact PLACE report.'),
        corruption_counterexample=counterexample,
        seam='One field-local occupied owner/row transport shared outside reducers[LANES], with independent full-origin integrity; leave every numeric/sign/high/base/sentinel/legal/error/valid path private. Storage2 changes only A/B+term stores, not these front bodies.',
        contract='D3 digit andD5 timing58 boundary remain unchanged/II1. Tags include rejected origins, outputs reset0 and hold without occupancy; reset flushes all token validity but not numeric dirt. Cancel/quarantine suppress new captures/commit immediately, admitted tails continue raw. Join preserves lane-valid divergence and every numeric error; no shared-valid substitution.',
        blocker='The literal shared transport alone loses the existing per-lane tag-comparison fault authority. No RTL authorized until an implementable independent origin check with preservation/nonmerge evidence closes that gap.',
        no_RTL_native_fit_or_area_clock_claim=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    with args.output.open('x') as out:json.dump(analyze(),out,indent=2);out.write('\n')
