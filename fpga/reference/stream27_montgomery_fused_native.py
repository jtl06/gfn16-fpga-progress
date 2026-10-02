"""P5 fused CT/GS normal scalar preparation; no field/generator changes."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
from fpga.reference import stream27_l3_factored_native_v1 as package_helper
from fpga.reference import lazy28_butterfly_v1 as donor
from fpga.reference import stream27_montgomery_fused_model as model
ROOT=donor.ROOT;SELF='reference/stream27_montgomery_fused_native.py'
TOP='genefer_stream27_fused_lazy28_butterfly_v1';RAW='genefer_stream27_montgomery28x27_raw_pipe_v1'
RTL='rtl/kernel/'+TOP+'.sv';CPP='rtl/tb/stream27_montgomery_fused_normal.cpp'
DONOR_CPP='rtl/tb/lazy28_butterfly_v1.cpp'
CPP_PIN='c211ef0116251ea88bd835bd3c889bed8ad44fb7e57eb8847b77c03f999c3fb3'
DONOR_PIN='2ec079ea95939d105e325654d3ee2148c2f9d7af95a29a9971f67f58d87d1449'
READY='results/throughput-20260929/stream27-l3-fused-source-v1/rtl-ready.json'
TOP2='genefer_stream27_fused_sign_lazy28_butterfly_v1';RAW2='genefer_stream27_montgomery28x27_raw_sign_pipe_v1'
RTL2='rtl/kernel/'+TOP2+'.sv';CPP2='rtl/tb/stream27_montgomery_fused_sign_normal.cpp'
READY2='results/throughput-20260929/stream27-l3-fused-sign-source-v1/rtl-ready.json'
sha=package_helper.s.sha;need=model.need
def raw_source():
    package_helper.verify_pins()
    t=(ROOT/package_helper.s.RTL).read_text().split('endmodule',1)[0]+'endmodule\n'
    sites=[('genefer_stream27_montgomery_factored_core_v1',RAW),
      ('output logic [31:0] result','output logic signed [27:0] result_raw'),
      ('wire [31:0] t_hi={9\'b0,hi_s3},mp_hi={5\'b0,mp_hi_s3};',''),
      ('out_valid<=0;result<=0;','out_valid<=0;result_raw<=0;'),
      ('if(t_hi>=mp_hi)result<=t_hi-mp_hi;\n                else result<=t_hi+P-mp_hi;',
       "result_raw<=$signed({5'b0,hi_s3})-$signed({1'b0,mp_hi_s3});")]
    for before,after in sites:
        need(t.count(before)==1,'P5_RAW_UNIQUE_SITE '+before);t=t.replace(before,after,1)
    return '// Signed raw REDC, private to fused butterfly; NOT a drop-in normalized leaf.\n'+t
BF='''// P5/L3b: public lazy unsigned28, private signed28 raw Montgomery residue.
// E0->E5, II1. ModP residues preserved; internal representatives may differ byP.
module genefer_stream27_fused_lazy28_butterfly_v1 #(
 parameter logic [31:0] P=32'd104857601,Q=32'd4190109697,parameter int TAG_W=32
)(input logic clk,rst_n,in_valid,gs,input logic [27:0] u,v,input logic [26:0] w,
 input logic [TAG_W-1:0] in_tag,output logic out_valid,output logic [27:0] y0,y1,
 output logic [TAG_W-1:0] out_tag);
 localparam logic [28:0] TWO_P=29'(P)<<1;
 localparam logic signed [28:0] P29=$signed({2'b0,P[26:0]});
 localparam logic signed [29:0] P30=$signed({3'b0,P[26:0]}),TWO_P30=P30<<<1;
 logic pre_valid,product_valid;
 logic [27:0] pre_v,prefix_pipe[0:4];logic [26:0] pre_w;
 logic signed [27:0] product_raw;
 logic [TAG_W-1:0] tag_pipe[0:4];logic [4:0] gs_pipe;
 wire [27:0] ct_u=u>=28'(P) ? u-28'(P) : u;
 wire [28:0] gs_sum={1'b0,u}+{1'b0,v},gs_diff={1'b0,u}+TWO_P-{1'b0,v};
 wire [27:0] gs_sum_fold=28'(gs_sum>=TWO_P ? gs_sum-TWO_P : gs_sum);
 wire [27:0] gs_diff_fold=28'(gs_diff>=TWO_P ? gs_diff-TWO_P : gs_diff);
 wire signed [28:0] raw29=$signed({product_raw[27],product_raw});
 wire signed [29:0] ct_total=$signed({2'b0,prefix_pipe[4]})+$signed({{2{product_raw[27]}},product_raw})+P30;
 wire signed [28:0] ct_diff=$signed({1'b0,prefix_pipe[4]})-raw29;
 wire signed [28:0] gs_biased=raw29+P29;
 genefer_stream27_montgomery28x27_raw_pipe_v1 #(.P(P),.Q(Q)) multiplier(
  .clk,.rst_n,.in_valid(pre_valid),.lhs(pre_v),.rhs(pre_w),.out_valid(product_valid),.result_raw(product_raw));
 always_ff @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin
   pre_valid<=0;pre_v<=0;pre_w<=0;gs_pipe<=0;out_valid<=0;y0<=0;y1<=0;out_tag<=0;
   for(int k=0;k<5;k=k+1)begin prefix_pipe[k]<=0;tag_pipe[k]<=0;end
  end else begin
   // synthesis translate_off
   if(in_valid && ({1'b0,u}>=TWO_P || {1'b0,v}>=TWO_P || {5'b0,w}>=P))$fatal(1,"P5_BFLY_INPUT_RANGE");
   if(product_valid && (raw29<=-P29 || raw29>=P29))$fatal(1,"P5_RAW_RESULT_RANGE");
   // synthesis translate_on
   pre_valid<=in_valid;
   if(in_valid)begin pre_v<=gs ? gs_diff_fold : v;pre_w<=w;end
   prefix_pipe[0]<=gs ? gs_sum_fold : ct_u;tag_pipe[0]<=in_tag;
   for(int k=1;k<5;k=k+1)begin prefix_pipe[k]<=prefix_pipe[k-1];tag_pipe[k]<=tag_pipe[k-1];end
   gs_pipe<={gs_pipe[3:0],gs};out_valid<=product_valid;
   if(product_valid)begin
    y0<=gs_pipe[4] ? prefix_pipe[4] : 28'(ct_total>=TWO_P30 ? ct_total-P30 : ct_total);
    y1<=gs_pipe[4] ? 28'(gs_biased) : 28'(ct_diff<0 ? ct_diff+P29 : ct_diff);
    out_tag<=tag_pipe[4];
   end
  end
 end
 // synthesis translate_off
 initial if(TAG_W<1)$fatal(1,"P5_TAG_WIDTH");
 // synthesis translate_on
endmodule
'''
def rtl(variant=1):
    need(variant in (1,2),'P5_VARIANT')
    if variant==1:return raw_source()+'\n'+BF
    text=BF.replace(TOP,TOP2).replace(RAW,RAW2)
    sites=[(' localparam logic signed [29:0] P30=$signed({3\'b0,P[26:0]}),TWO_P30=P30<<<1;\n',''),
      (" wire signed [29:0] ct_total=$signed({2'b0,prefix_pipe[4]})+$signed({{2{product_raw[27]}},product_raw})+P30;",
       " wire signed [28:0] ct_sum=$signed({1'b0,prefix_pipe[4]})+raw29;"),
      ("28'(ct_total>=TWO_P30 ? ct_total-P30 : ct_total)","28'(ct_sum<0 ? ct_sum+P29 : ct_sum)")]
    for before,after in sites:
        need(text.count(before)==1,'P5_SIGN_UNIQUE_SITE');text=text.replace(before,after,1)
    return '// CT signed29 prefix±raw, sign-only correction; first variant remains frozen.\n'+raw_source().replace(RAW,RAW2)+'\n'+text
def cpp(variant=1):
    need(variant in (1,2),'P5_VARIANT')
    t=(ROOT/DONOR_CPP).read_text();need(sha(t.encode())==CPP_PIN,'P5_FROZEN_CPP_PIN')
    t=t.replace('genefer_ntt_lazy28_butterfly_v1',TOP if variant==1 else TOP2)
    old='require(d.y0==expected.y0&&d.y1==expected.y1,"LAZY_BFLY_VALUE_MISMATCH");'
    need(t.count(old)==1,'P5_CPP_MODULAR_COMPARE_SITE')
    t=t.replace(old,'require(d.y0%P==expected.y0%P&&d.y1%P==expected.y1%P,"P5_BFLY_MODULAR_VALUE_MISMATCH");')
    return t.replace('LAZY_BFLY_PASS','P5_FUSED_BFLY_PASS' if variant==1 else 'P5_FUSED_SIGN_BFLY_PASS')
def verify(variant=1):
    need(sha((ROOT/'reference/lazy28_butterfly_v1.py').read_bytes())==DONOR_PIN,'P5_FROZEN_CORPUS_PIN')
    r,c=(RTL,CPP) if variant==1 else (RTL2,CPP2)
    need((ROOT/r).read_text()==rtl(variant) and (ROOT/c).read_text()==cpp(variant),'P5_EXACT_SOURCE_AND_NORMAL_CPP')
def write_source(variant=1):
    r,c,ready=(RTL,CPP,READY) if variant==1 else (RTL2,CPP2,READY2)
    for path,text in ((r,rtl(variant)),(c,cpp(variant))):
        need(not (ROOT/path).exists(),'P5_FRESH_SOURCE')
        with (ROOT/path).open('x') as f:f.write(text)
    now=datetime.now(timezone.utc).isoformat().replace('+00:00','Z');snapshot={r:sha((ROOT/r).read_bytes())}
    path=ROOT/ready;path.parent.mkdir(parents=True,exist_ok=True)
    package_helper.dump(path,dict(schema='gfn16-candidate-rtl-ready-v1',candidate_id='stream27-l3-fused-v1' if variant==1 else 'stream27-l3-fused-sign-v1',
      candidate_source_sha256=sha(json.dumps(snapshot,sort_keys=True,separators=(',',':')).encode()),
      rtl_ready_at_utc=now,source_snapshot=snapshot))
    verify(variant);return now
def validate(stdout,stderr,rc,config,assets):
    variant=config.get('variant',1)
    need(set(config)==({'p'} if variant==1 else {'p','variant'}) and variant in (1,2) and config['p'] in model.FIELDS and not assets,'P5_NORMAL_CONFIG')
    p=config['p'];_,c=donor.corpus(p)
    marker='P5_FUSED_BFLY_PASS' if variant==1 else 'P5_FUSED_SIGN_BFLY_PASS'
    expected=f'{marker} p={p} '+' '.join(f'{k}={v}' for k,v in c.items())+'\n'
    need(rc==0 and stdout==expected and stderr=='','P5_TYPED_NORMAL_RESULT')
    return dict(status='PASS_expected_contracts',**c,latency=5,II=1,comparison='modP equality with legal unsigned28<2P',
       raw_domain='signed28 strictly(-P,P),private multiplier-to-output use only',promotion_allowed=False)
def role(p,variant=1):
    verify(variant);corpus,counts=donor.corpus(p);asset=f'rtl/tb/p5-fused-normal-{p}.txt'
    r,c,ready,top=(RTL,CPP,READY,TOP) if variant==1 else (RTL2,CPP2,READY2,TOP2)
    config=dict(p=p)
    if variant==2:config['variant']=2
    paths=(r,c,SELF,'reference/stream27_l3_factored_native_v1.py','reference/stream27_l3_factored_model_v1.py',
      'reference/stream27_montgomery_fused_model.py','reference/lazy28_butterfly_v1.py','reference/__init__.py',ready)
    files={path:(ROOT/path).read_bytes() for path in paths};files[asset]=corpus.encode()
    m=dict(schema='native-source-gate-v1',status='prepared_not_executed',
      source_root='/not-a-dispatch-path/p5-fused/fpga',output_parent='/not-a-dispatch-path/p5-fused/output',
      sources={n:sha(raw) for n,raw in files.items()},
      build=dict(top=top,sv_sources=[r],cpp_source=c,parameters=dict(P=p,Q=(2-p)%(1<<32),TAG_W=32),
                 cflags=['-std=c++17','-O2','-Werror=return-type',f'-DTEST_P={p}']),
      probe=dict(argv=['{exe}','--runtime-probe'],expected_json=dict(context_threads=1,model_threads=1,expected_threads=1)),
      steps=[dict(name='fused-ct-gs-normal-values-tags-latency',argv=['{exe}',asset],expected_returncode=0,
        validator=dict(source=SELF,function='validate',config=config,assets={}))],test_role='normal',
      rtl_readiness=json.loads((ROOT/ready).read_text()),
      scope='Isolated P5 fused butterfly, residues modP plus exact unsigned28 range/latency/tag/reset/hold; no bitwise lazy-representative equality or field/clock/area claim.')
    return m,files
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--write-source',action='store_true');p.add_argument('--p',type=int,choices=tuple(model.FIELDS))
    p.add_argument('--output',type=Path);p.add_argument('--budget',type=Path);p.add_argument('--variant',type=int,choices=(1,2),default=1);a=p.parse_args()
    if a.write_source:print(write_source(a.variant))
    else:print(package_helper.prepare(a.output,a.p,a.budget,role_builder=lambda field:role(field,a.variant),
       family='stream27-l3-fused' if a.variant==1 else 'stream27-l3-fused-sign'))
