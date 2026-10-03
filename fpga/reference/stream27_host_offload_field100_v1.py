"""Private R14-F: literal captured FIELD100 OFF, banked HOST_OFFLOAD ON.

Reuses the frozen boundary transformations, never a relay-disabled R13 graph.
Only cold staging representation changes: fixed 1R1W field/lane banks.
No full-N numerical work or native/physical qualification occurs here.
"""
import copy
import hashlib
import json
from pathlib import Path
import types

ROOT=Path(__file__).resolve().parents[1]
SELF='reference/stream27_host_offload_field100_v1.py'
OLD='reference/stream27_host_offload_chip_v1.py'
OLD_PIN='d40c8bf31af7261a4efec1af50debf682beb92c6046bb77c37dc7ca34d7fce03'
LEAF='rtl/kernel/genefer_stream27_host_offload_ingress_field100_v1.sv'
PARENTS={256:('aw8-normal','dd8d9196a5ac79381b8e701d021d19a067dde4d319b15799b13f8d8f61441a00'),
 65536:('full-normal-v2','f5f0617d989b64bb965b612a0d0cb8b6074c1ecd4f85f01ed66f970dfbf521f2')}
def sha(raw):return hashlib.sha256(raw.encode() if isinstance(raw,str) else raw).hexdigest()
def need(ok,why):
    if not ok:raise ValueError('R14F_'+why)
def engine():
    raw=(ROOT/OLD).read_bytes();need(sha(raw)==OLD_PIN,'FROZEN_BOUNDARY_TRANSFORM')
    text=raw.decode()
    edits=[("SELF='reference/stream27_host_offload_chip_v1.py'",f"SELF={SELF!r}"),
        ("LEAF='rtl/kernel/genefer_stream27_host_offload_ingress_v1.sv'",f"LEAF={LEAF!r}"),
        ("PARENTS={256:('aw8','151d34a10beed71441b23e7abf3b779d37eaae852a456bda37b6bb37302432d5'),\n         65536:('full','229e07390fbed434131bba7e101c2492bde27f5a45ebceb7fa40e1d94fec5c53')}",f'PARENTS={PARENTS!r}'),
        ('trackS-c2-protected-relay13-native-v1/{stage}-normal/production-bundle.json','trackS-c2-protected-field100-native-v1/{stage}/production-bundle.json'),
        ("name[:-3]+'_host_offload_v1'","name[:-3]+'_host_offload_field100_v1'"),
        ("b['top']+'_r14_v1'","b['top']+'_r14f_v1'"),
        (' genefer_stream27_host_offload_ingress_v1 #(', ' genefer_stream27_host_offload_ingress_field100_v1 #(')]
    for old,new in edits:
        need(text.count(old)==1,'EXACT_PRIVATE_ADAPTATION:'+old);text=text.replace(old,new,1)
    module=types.ModuleType('_private_r14f_boundary');module.__file__=str(ROOT/SELF)
    exec(compile(text,str(ROOT/SELF)+'[frozen boundary transformations]','exec'),module.__dict__)
    return module
_impl=engine()
PORTS=_impl.PORTS
def capture(n):return _impl.capture(n)
def reverse(text,ops):return _impl.reverse(text,ops)
def prepare(n=256,*,host_offload=0,relay13_enabled=0):
    need(type(relay13_enabled)is int and relay13_enabled==0,'NO_R13_RELAYS')
    b=capture(n)
    need(not any(flag in b['parameters'] for flag in ('INVERSE_INGRESS_REG','TERM_JOIN_TRANSPORT_REG','FORWARD_INGRESS_REG')),'LITERAL_FIELD100_PARAMETERS')
    out=_impl.prepare(n,host_offload=host_offload)
    if not host_offload:
        need(out==b,'EXACT_LITERAL_FIELD100_OFF');return out
    need(len(out['files'])==66 and all(out['files'][name]==text for name,text in b['files'].items()),'PARENT58_RETAINED')
    need('relay13' not in out['top'] and len(out['host_offload']['source_edits'])==6,'SIX_FIELD100_GRAPH_ADAPTATIONS')
    deps=list(dict.fromkeys(out['source_dependencies']+[OLD]))
    out['source_dependencies']=deps;out['source_sha256']={name:sha((ROOT/name).read_bytes()) for name in deps}
    out['host_offload_field100']=dict(identity='R14-F',parent='literal protected FIELD100',relay13_enabled=0,
        frozen_boundary_transform_sha256=OLD_PIN,host_offload_default=0,
        cold_storage='48 independent field/lane single-read single-write banks; context is address bit',
        bank_count=48,bank_depth=2*(n//16),data_width=27,logical_image_bits=6*n*27,
        cold_response_edges=1,host_ABI_unchanged=True,high_c1_residue_unscaled=True,
        prior_R14_results_inherited=False,physical_inference_unmeasured=True)
    return out
