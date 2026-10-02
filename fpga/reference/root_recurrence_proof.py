"""Read-only schedule/root-recurrence feasibility proof; no RTL candidate.

Run only on aethia. The independently reconstructed logical butterfly addresses
are the oracle for the proposed compressed seed/routing/recurrence schedule.
"""
from pathlib import Path
import argparse,hashlib,json,math,resource,socket,time

FIELDS=[(104857601,3),(69206017,5),(67239937,10)]
MAX_LG=16
R=1<<32

def bank(a,k):
    b=0
    while a:b^=a&((1<<k)-1);a>>=k
    return b

def inverse_bank(b,row,k):
    high=row<<k
    return high|(b^bank(high,k))

def insert_zero(a,p):return (a&((1<<p)-1))|((a>>p)<<(p+1))
def remove_bit(a,p):return (a&((1<<p)-1))|((a>>(p+1))<<p)
def rol(a,r,k):return ((a<<r)|(a>>(k-r)))&((1<<k)-1)

def generic_base(g,s,k):
    fixed=[j for j in range(MAX_LG) if j!=s and not(j<k and j!=s%k)]
    return sum(((g>>i)&1)<<j for i,j in enumerate(fixed))

def common_exponent(g,s,k,lg):
    if s<k:return 0
    h=(g>>1)&((1<<(s-k))-1)
    return (((g&1)<<(s%k))|(h<<k))<<(lg-1-s)

def period(s,k):return 1 if s<k else 1<<(s-k+1)

def seed_count(s,k):return min(1<<(k-1),1<<s)*min(4,period(s,k))

def powers(x,n,p):
    a=[1]*n
    for i in range(1,n):a[i]=a[i-1]*x%p
    return a

def check_geometry(lg,lanes):
    n=1<<lg;k=lanes.bit_length();banks=2*lanes;groups=max(1,n//banks)
    stages=[];count=0
    for s in range(lg):
        p=s%k;shift=lg-1-s;rotation=shift%k;distinct=min(lanes,1<<s);rows=[];seen=set()
        for g in range(groups):
            base=generic_base(g,s,k);bb=bank(base,k);ori=(bb>>p)&1
            rootbase=(base&((1<<s)-1))<<shift
            assert rootbase==common_exponent(g,s,k,lg)
            permutation=[];exponents=[]
            for lane in range(min(lanes,n//2)):
                lo=insert_zero(lane,p);bu=lo|(ori<<p);bv=bu^(1<<p)
                # Reconstruct addresses from physical bank + actual RAM row,
                # without using the candidate compressed root formula.
                rowu=(base|((((bu>>p)&1)^ori)<<s))>>k
                rowv=(base|((((bv>>p)&1)^ori)<<s))>>k
                u=inverse_bank(bu,rowu,k);v=inverse_bank(bv,rowv,k)
                assert u<n and v<n and (u^(1<<s))==v and not(u&(1<<s))
                assert u not in seen and v not in seen;seen.update([u,v])
                t=(u&((1<<s)-1))<<shift
                j=(lane^bb)&((1<<s)-1) if s<k else lane^remove_bit(bb,p)
                variable=j if s<k else insert_zero(j,p)
                assert j<distinct and not(rootbase&(variable<<shift))
                assert t==rootbase+(variable<<shift)
                rootbank=rol(variable,rotation,k)^bank(rootbase,k)
                assert rootbank==bank(t,k)
                permutation.append(j);exponents.append(t);count+=1
            assert len(set(exponents))==distinct
            rows.append((permutation,exponents))
        assert seen==set(range(n))
        stages.append(rows)
    point=[];seen=set()
    for g in range(max(1,n//lanes)):
        base=g*lanes;bb=bank(base,k);half=(bb>>(k-1))&1;row=base>>k
        permutation=[];addresses=[]
        for lane in range(min(lanes,n)):
            a=inverse_bank(lane+half*lanes,row,k)
            j=lane^(bb&(lanes-1))
            assert a==base+j and a<n and a not in seen;seen.add(a)
            permutation.append(j);addresses.append(a)
        point.append((permutation,addresses))
    assert seen==set(range(n))
    return stages,point,count

def recurrence_rows(seeds,step,groups,p,rinv,repeat=None,wrong_latency=False):
    """At edge g, output from edge g-4 is already registered (at g-1).

    This explicitly models direct result bypass, not a separate state-register
    write sampled on the same edge. Root values here are the current operands;
    multiplying them by step prepares the same context four groups later.
    """
    pending={}
    for g in range(groups):
        q=g if repeat is None else g%repeat
        if q<4:current=seeds[q%len(seeds)]
        else:current=pending.pop(g-1 if not wrong_latency else g-2)
        yield current
        pending[g+3]=[x*step*rinv%p for x in current]
        # Products crossing a reseed boundary are intentionally discarded.
        for old in [x for x in pending if x<g-1]:del pending[old]

def check_field(lg,lanes,p,generator,geometry):
    n=1<<lg;k=lanes.bit_length();stages,point,_=geometry;rinv=pow(R,-1,p);mont=R%p
    psi_max=pow(generator,(p-1)//(2<<MAX_LG),p)
    psi=pow(psi_max,1<<(MAX_LG-lg),p);omega=psi*psi%p
    assert pow(psi,n,p)==p-1 and pow(omega,n,p)==1
    checks=0;seed_checks=0;common_checks=0
    for inv in [False,True]:
        alpha=pow(omega,-1,p) if inv else omega
        alpha_max=pow(psi_max,2,p)
        if inv:alpha_max=pow(alpha_max,-1,p)
        table=[x*mont%p for x in powers(alpha,n//2,p)]
        for s,rows in enumerate(stages):
            shift=lg-1-s;distinct=min(lanes,1<<s);t=period(s,k)
            variable=[j if s<k else insert_zero(j,s%k) for j in range(distinct)]
            seed=[pow(alpha,v<<shift,p)*mont%p for v in variable]
            for j,v in enumerate(variable):
                assert seed[j]==pow(alpha_max,v<<(MAX_LG-1-s),p)*mont%p;seed_checks+=1
            contexts=min(4,t)
            common=[pow(alpha,common_exponent(q,s,k,lg),p)*mont%p for q in range(contexts)]
            direct=[[c*x*rinv%p for x in seed] for c in common]
            step=mont if t<=4 else pow(alpha,1<<(k+shift+1),p)*mont%p
            generated=recurrence_rows(direct,step,len(rows),p,rinv,t)
            factors=recurrence_rows([[c] for c in common],step,len(rows),p,rinv,t)
            for g,((indices,exponents),roots,c) in enumerate(zip(rows,generated,factors)):
                assert c[0]==pow(alpha,common_exponent(g,s,k,lg),p)*mont%p;common_checks+=1
                for j,e in zip(indices,exponents):
                    assert roots[j]==table[e]
                    assert c[0]*seed[j]*rinv%p==table[e]
                    checks+=2
    for post in [False,True]:
        alpha=pow(psi,-1,p) if post else psi
        scale=pow(n,-1,p) if post else mont
        table=[x*scale%p for x in powers(alpha,n,p)]
        used=min(lanes,n);contexts=min(4,len(point))
        seeds=[[table[q*lanes+j] for j in range(used)] for q in range(contexts)]
        step=pow(alpha,4*lanes,p)*mont%p
        generated=recurrence_rows(seeds,step,len(point),p,rinv)
        for (indices,addresses),roots in zip(point,generated):
            for j,a in zip(indices,addresses):assert roots[j]==table[a];checks+=1
        # Post roots stay ordinary: ordinary seed times a Montgomery step
        # remains ordinary, unlike multiplying by an unencoded step.
        if post:assert table[0]==pow(n,-1,p)
    return {'root_checks':checks,'common_checks':common_checks,'size_independent_seed_checks':seed_checks}

def resources(lanes):
    k=lanes.bit_length();bf=sum(seed_count(s,k) for s in range(MAX_LG))*2
    point_fixed=8*lanes
    point_all=2*sum(min(4*lanes,1<<lg) for lg in range(1,MAX_LG+1))
    result={'lanes':lanes,'extra_montgomery_pipelines_per_field':lanes,
            'extra_montgomery_pipelines_three_fields':3*lanes,
            'butterfly_seed_words':bf,'fixed_N_point_seed_words':point_fixed,
            'all_runtime_N_point_seed_words':point_all,
            'active_seed_register_bits':4*lanes*27,'double_buffer_seed_register_bits':8*lanes*27,
            'seed_ROM_read_ports':1,'old_root_words_per_field':3*(1<<MAX_LG),
            'old_root_bits_per_field':3*(1<<MAX_LG)*32,'stage_seed_words':[]}
    factor_bf=2*sum(min(lanes,1<<s)+min(4,period(s,k)) for s in range(MAX_LG))
    factor_point_fixed=2*(lanes+4)
    factor_point_all=2*sum(min(lanes,1<<lg)+min(4,max(1,(1<<lg)//lanes)) for lg in range(1,MAX_LG+1))
    result['common_factor_alternative']={
        'extra_montgomery_pipelines_per_field':lanes+1,
        'extra_montgomery_pipelines_three_fields':3*(lanes+1),
        'active_seed_register_bits':(lanes+4)*27,
        'double_buffer_seed_register_bits':2*(lanes+4)*27,
        'fixed_N_seed_words_including_steps':factor_bf+factor_point_fixed+34,
        'all_runtime_N_seed_words_including_steps':factor_bf+factor_point_all+64,
        'unprefetched_full_N_square_seed_extra_clocks':factor_bf+factor_point_fixed+4*MAX_LG+4,
        'extra_root_alignment_clocks_without_lookahead':3,
        'full_N_square_extra_alignment_clocks_without_lookahead':3*(2*MAX_LG+2)}
    result['unprefetched_full_N_square_extra_clocks']=bf+point_fixed+4*MAX_LG+4
    for scope,point,constants in [('fixed_N',point_fixed,34),('all_runtime_N',point_all,64)]:
        words=bf+point+constants
        result[scope]={'words_including_conservative_steps':words,'bits27':words*27,
                       'capacity_estimate_512x32_blocks_per_field':math.ceil(words/512),
                       'not_a_fit_or_port_replication_estimate':True}
    g=(1<<MAX_LG)//(2*lanes)
    for s in range(MAX_LG):
        u=seed_count(s,k)
        result['stage_seed_words'].append({'s':s,'period':period(s,k),'seed_reads':u,
            'conservative_unprefetched_extra_clocks':u+2,
            'prefetch_fits_inside_previous_full_N_stage':u+1<=g})
    return result

def counterexamples(lanes):
    lg=16;k=lanes.bit_length();p,gen=FIELDS[0];mont=R%p;rinv=pow(R,-1,p)
    psi=pow(gen,(p-1)//(2<<lg),p);alpha=psi*psi%p;s=k
    right=common_exponent(1,s,k,lg)
    wrong=(1% (1<<(s-k)))<<(k+lg-1-s)
    assert right!=wrong
    s=k+2;t=period(s,k);shift=lg-1-s;step=pow(alpha,1<<(k+shift+1),p)*mont%p
    root=mont
    for _ in range(t//4):root=root*step*rinv%p
    assert root!=mont and root==(p-mont)%p
    stages,point,_=check_geometry(lg,lanes)
    xor_example=next(({'stage':s,'group':g,'lane':i,'required_seed_index':j}
        for s,rows in enumerate(stages) for g,(indices,_) in enumerate(rows)
        for i,j in enumerate(indices) if j!=i and s>=k),None)
    assert xor_example
    plain=pow(1<<lg,-1,p);wrong_post=plain*mont%p;assert plain!=wrong_post
    correct_g4=mont*step*rinv%p;assert correct_g4!=mont
    return {'missing_parity':{'stage':k,'group':1,'expected_exponent':right,'wrong_exponent':wrong},
            'missing_reseed':{'stage':k+2,'group':t,'expected':mont,'wrong':root},
            'missing_lane_xor':xor_example,'post_wrong_Montgomery_scale':{'expected':plain,'wrong':wrong_post},
            'four_context_state_write_hazard':{'group':4,'expected':correct_g4,'stale_state':mont,
                'reason':'At edge4, a separate state<=result write cannot be read by the edge4 consumer; bypass result from edge3 or use at least5 contexts.'}}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    if socket.gethostname()!='aethia':raise RuntimeError('aethia only')
    resource.setrlimit(resource.RLIMIT_AS,(6<<30,6<<30))
    root=Path(__file__).resolve().parents[1];out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    sources=[Path(__file__),root/'rtl/kernel/genefer_ntt_banked_wide_engine.sv',root/'rtl/kernel/genefer_montgomery_mul27_sparse_pipe.sv']
    report={'status':'running','host':socket.gethostname(),'scope':'Python proof only; no RTL, synthesis, fit, or measured-throughput claim',
            'sources':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},'checks':[],
            'resources':[resources(w) for w in [16,64]],'counterexamples':[]}
    started=time.monotonic()
    try:
        for lanes in [16,64]:
            for lg in range(1,17):
                geometry=check_geometry(lg,lanes)
                fields=[]
                for p,generator in FIELDS:fields.append({'p':p,**check_field(lg,lanes,p,generator,geometry)})
                row={'lanes':lanes,'lg':lg,'butterfly_geometry_checks':geometry[2],'fields':fields}
                report['checks'].append(row);print('PASS',row,flush=True)
            report['counterexamples'].append({'lanes':lanes,**counterexamples(lanes)})
        report['status']='passed_python_proof_not_RTL'
    except BaseException as exc:report['status']='failed';report['error']=repr(exc);raise
    finally:
        report['seconds']=time.monotonic()-started
        (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':main()
