"""Typed C host-only timing parser; no full-N arithmetic or FPGA inference."""
import hashlib
import json
import math
import re
import statistics
import struct

HEADER_PIN='7679e85713662635476124b0bad2e91954a08d8a27dd3f25db127b23da9d0720'
FROZEN_SYNTHETIC_OUTPUT='0d5d5824db19f08859f872cba76f17380e046bfd042180a40197126f9db60008'
PHASES=('profile_wall','cold_wall','final_wall','profile_cpu','cold_cpu','final_cpu')
KEYS={'status','host','n','p','base','generation','repetitions','selfchecks','header_sha256',
      'profile_wire_hex','final_wire_hex','special','carry',*PHASES,
      'backend_seconds','transport_seconds','overlap_seconds','prp_wall_seconds',
      'native_core_equivalence','promotion_allowed'}


def need(ok,why):
    if not ok:raise ValueError('R14_HOST_CPU_'+why)


def config(repetitions=3):
    return dict(repetitions=repetitions,header_sha256=HEADER_PIN,
                frozen_synthetic_output_sha256=FROZEN_SYNTHETIC_OUTPUT)


def validate(stdout,stderr,returncode,cfg,assets):
    need(type(cfg) is dict and cfg==config(cfg.get('repetitions')) and
         type(cfg['repetitions']) is int and 1<=cfg['repetitions']<=5 and assets=={},'CONFIG')
    need(type(stdout) is str and type(stderr) is str and type(returncode) is int and
         returncode==0 and stderr=='' and len(stdout)<1024*1024 and stdout.endswith('\n') and
         stdout.count('\n')==1 and stdout.startswith('R14_HOST_CPU_PASS '),'TYPED_OUTPUT')
    report=json.loads(stdout.removeprefix('R14_HOST_CPU_PASS '))
    need(type(report) is dict and set(report)==KEYS,'EXACT_KEYS')
    need(report['status']=='PASS_C_host_measurement_only' and report['host'] in ('aethia','gfn16-pilot-c4d') and
         report['header_sha256']==HEADER_PIN,'SOURCE_HOST_SCOPE')
    for key,expected in dict(n=65536,p=16,base=604832956,generation=7,repetitions=cfg['repetitions'],selfchecks=301).items():
        need(type(report[key]) is int and report[key]==expected,'EXACT_'+key)
    need(type(report['profile_wire_hex']) is str and re.fullmatch('[0-9a-f]{64}',report['profile_wire_hex']),
         'PROFILE_WIRE')
    # Scalar profile arithmetic is allowed at full geometry, never a full-N
    # digit/residue computation on the coordinator.
    n,base,generation=65536,604832956,7
    B=base-1;K=2*n+384;reciprocal=(1<<96)//base
    limit=2*((n+48)*B*B+64*B*K+16*K*K)
    words=([base,generation]+[(reciprocal>>(32*i))&0xffffffff for i in range(3)]+
           [(limit>>(32*i))&0xffffffff for i in range(3)])
    expected_profile=struct.pack('<8I',*words)
    need(bytes.fromhex(report['profile_wire_hex'])==expected_profile,'EXACT_PROFILE')
    need(type(report['final_wire_hex']) is str and len(report['final_wire_hex'])==8*65536 and
         re.fullmatch('[0-9a-f]+',report['final_wire_hex']),'FINAL_WIRE')
    digest=hashlib.sha256(bytes.fromhex(report['final_wire_hex'])).hexdigest()
    need(digest==FROZEN_SYNTHETIC_OUTPUT,'FROZEN_SYNTHETIC_FULL_BYTES')
    need(report['special'] is False and type(report['carry']) is list and len(report['carry'])==3 and
         all(type(v) is int and abs(v)<=(2 if i==0 else 1) for i,v in enumerate(report['carry'])),'CARRIES')
    need(report['native_core_equivalence'] is False and report['promotion_allowed'] is False and
         all(report[key] is None for key in ('backend_seconds','transport_seconds','overlap_seconds','prp_wall_seconds')),
         'NO_BACKEND_TRANSPORT_OVERLAP_PRP_INFERENCE')
    result={}
    for phase in PHASES:
        values=report[phase]
        need(type(values) is list and len(values)==cfg['repetitions'] and
             all(type(v) in (int,float) and math.isfinite(v) and 0<=v<60 for v in values),'FINITE_'+phase)
        result[phase]=dict(minimum_seconds=min(values),median_seconds=statistics.median(values),maximum_seconds=max(values))
    need(sum(sum(report[k]) for k in PHASES[:3])<60,'FINITE_TIMED_REGION')
    return dict(status='PASS_expected_contracts',synthetic_C_host_only=True,host=report['host'],
                timing=result,full_synthetic_output_sha256=digest,native_core_equivalence=False,
                measured_backend_seconds=None,transport_seconds=None,overlap_seconds=None,promotion_allowed=False)
