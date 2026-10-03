"""Private R14-F physical source preparation on literal FIELD100 controls."""
import hashlib
from pathlib import Path
import types
from . import stream27_host_offload_field100_v1 as chip

ROOT=chip.ROOT
SELF='reference/stream27_host_offload_field100_physical_v1.py'
OLD='reference/stream27_host_offload_physical_v1.py'
OLD_PIN='c6688510eba9cceade7abab39ef747f9008107d828e0a4cc38626e0c2f0253c8'
CHIP_PIN='6a9920ca2b704145553ed9f5fc13d0e6f97de78b0f89a960801bf7919b184633'
def engine():
    raw=(ROOT/OLD).read_bytes();chip.need(chip.sha(raw)==OLD_PIN,'FROZEN_PHYSICAL_RECIPE')
    text=raw.decode();changes=[
        ('from . import stream27_host_offload_chip_v1 as chip','from fpga.reference import stream27_host_offload_field100_v1 as chip'),
        ('trackS-c2-protected-relay13-physical-v1/physical-11500-v1','trackS-c2-protected-field100-physical-v1/physical-12000-v3'),
        ('d40c8bf31af7261a4efec1af50debf682beb92c6046bb77c37dc7ca34d7fce03',CHIP_PIN),
        ("count('-period 11.500')","count('-period 12.000')"),
        ("replace(b'-period 11.500'","replace(b'-period 12.000'")]
    for a,b in changes:
        chip.need(text.count(a)==1,'PHYSICAL_ADAPTER:'+a);text=text.replace(a,b,1)
    text=text.replace('protected R13','protected FIELD100').replace('exact frozen R13','exact frozen FIELD100').replace('R13 job','FIELD100 job').replace('R14','R14-F')
    module=types.ModuleType('_r14f_physical');module.__file__=str(ROOT/SELF)
    exec(compile(text,str(ROOT/SELF)+'[frozen physical transformations]','exec'),module.__dict__)
    return module
def build(*,period=12.0,seed=2):
    m,files,spec=engine().build(period=period,seed=seed)
    m.pop('context_protected_relay13',None)
    m['host_offload_field100']=chip.prepare(65536,host_offload=1)['host_offload_field100']
    m['notes']=[n for n in m['notes'] if '04:30' not in n]+[
        'r106: fresh AW8/full normal allows provisional physical exploration; own complete equivalence/long/independent/clock evidence gates promotion.',
        'Fixed cold RAM banks address frontend inference risk, but mapped M20K/FF resources are unmeasured.']
    encoded=engine().encoded
    spec['settings']['manifest.json']=chip.sha(encoded(m))
    return m,files,spec
