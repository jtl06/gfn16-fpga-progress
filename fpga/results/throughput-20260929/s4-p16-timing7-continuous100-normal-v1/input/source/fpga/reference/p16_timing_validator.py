"""Exact final P16 timing normal footer and flags; no parent PASS reuse."""
import re
COUNTS=dict(jobs=2,operations=9,feed_descriptors=7,true_final_rows=8192,paired_reads=131072,copied_words=131072,partial_reads=1,canonical_cycles=1179648,image_copy_cycles=131078,candidate_cycles=1395173,fifo_peak=4,full_exchanges=3,backpressure_edges=25376)
FLAGS=dict(CANONICAL_PIPE_STAGES=1,CORR_SERIAL_BFS=2,COMM_STAGE_SHARED_MLAB=1,MONT_FACTORED=1,BOUNDARY_INPUTREG=1,DESCRIPTOR_FIFO_FF=1,QUARANTINE_REPLICAS=1,FINAL_GS_INPUTREG=1,CANONICAL_LOCALBASE=1,CARRY_LOCALBASE=1,TERM_SELECT_TOKEN=1)
def validate(stdout,stderr,returncode,config,assets):
 if config!=dict(aw=16,p=16,base=604832956,flags=FLAGS,counts=COUNTS) or assets!={}:raise ValueError('P16_TIMING_CONFIG')
 prefix='S4_P16_TIMING_HOST_PASS aw=16 p=16 '+' '.join(f'{k}={v}' for k,v in COUNTS.items())+' t5b_wait_edges='
 match=re.fullmatch(re.escape(prefix)+r'([1-9][0-9]*)\n',stdout,re.ASCII)
 if returncode!=0 or stderr!='' or not match:raise ValueError('P16_TIMING_TYPED_NORMAL')
 wait=int(match.group(1))
 if not 9<=wait<=9*(20*65536+100000):raise ValueError('P16_TIMING_T5B_BOUND')
 return dict(status='PASS_expected_contracts',flags=FLAGS,counts=COUNTS,measured_t5b_wait_edges=wait,scope='Own wholeP16 timing full9 normal; no PRP/1000/resource/clock/promotion inference.')
