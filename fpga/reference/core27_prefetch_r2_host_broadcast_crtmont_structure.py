"""Exact additive broadcast G4 delta; frozen parent and all guards retained."""
import hashlib
from pathlib import Path
from .core27_prefetch_r2_host_broadcast_core_structure import KERNEL_PINS as PARENT_KERNEL_PINS

ANCESTOR='genefer_square_core27_stream_prefetch_r2_host_broadcast'
CANDIDATE=ANCESTOR+'_crtmont'
OLD_BENCH='square_core27_stream_prefetch_r2_host_broadcast'
NEW_BENCH=OLD_BENCH+'_crtmont'
PARENT_PINS={
    'rtl/kernel/'+ANCESTOR+'.sv':'ea2b518880cb1c3191c71d35a232d2483aee82046ecd4d930d7ac7ffa07a80e1',
    'rtl/tb/'+OLD_BENCH+'.cpp':'9e11a73d910cf6ca4f89a6cec42a41c43310f8baa9d504cf0476b27220bc0644',
    'rtl/tb/'+OLD_BENCH+'_threaded.cpp':'7a21cd62a4879ab1f24e4a46f05e01131a4f7f271764c6b988da701fda58f2eb',
}
NEW_PINS={
    'rtl/kernel/genefer_crt3_27_mont_pipe.sv':'8bb5b62423c1f61e069f131b5d393dd3dbc84d05348fc1945f6e9c419c104c58',
    'rtl/kernel/'+CANDIDATE+'.sv':'790582b6b9d8f3279a8a7f0fb385a5d98e6869996eb4a725005a321cf4b23820',
    'rtl/tb/'+NEW_BENCH+'.cpp':'99216a00a5896461d9047466621841825fe5cc4cb4f4bb55355497607df33db0',
    'rtl/tb/'+NEW_BENCH+'_threaded.cpp':'d8c35cfce602ba42135787917257732b48fa21745a32f5aff1caf10c9acd3733',
}
REPLACEMENTS={'genefer_crt3_27_pipe.sv':'genefer_crt3_27_mont_pipe.sv',ANCESTOR+'.sv':CANDIDATE+'.sv'}
KERNEL_PINS={REPLACEMENTS.get(name,name):NEW_PINS['rtl/kernel/'+REPLACEMENTS[name]] if name in REPLACEMENTS else value
             for name,value in PARENT_KERNEL_PINS.items()}


def require(ok,message):
    if not ok:raise ValueError(message)


def sha(text):return hashlib.sha256(text.encode()).hexdigest()


def replace(text,old,new,count=1):
    require(text.count(old)==count,'ambiguous exact source delta: '+old)
    return text.replace(old,new)


def pinned(text,path):require(sha(text)==PARENT_PINS[path],'frozen parent changed: '+path)


def core_source(original):
    pinned(original,'rtl/kernel/'+ANCESTOR+'.sv')
    text=replace(original,'module '+ANCESTOR+' #(','module '+CANDIDATE+' #(')
    return replace(text,'genefer_crt3_27_pipe crt (','genefer_crt3_27_mont_pipe crt (')


def bench_source(original):
    pinned(original,'rtl/tb/'+OLD_BENCH+'.cpp')
    text=replace(original,'V'+ANCESTOR,'V'+CANDIDATE,2)
    text=replace(text,'frozen61-stage CRT, first coefficient acceptance','candidate16-stage CRT, first coefficient acceptance')
    text=replace(text,'is RESIDUES clock63;','is RESIDUES clock18;')
    text=replace(text,'d.crt_cycles>=63','d.crt_cycles>=18')
    return replace(text,'(n+15)/16+62+','(n+15)/16+17+')


def wrapper_source(original):
    pinned(original,'rtl/tb/'+OLD_BENCH+'_threaded.cpp')
    text=replace(original,'V'+ANCESTOR,'V'+CANDIDATE)
    return replace(text,'#include "'+OLD_BENCH+'.cpp"','#include "'+NEW_BENCH+'.cpp"')


def validate_files(root):
    root=Path(root)
    require((root/'rtl/kernel'/(CANDIDATE+'.sv')).read_text()==core_source((root/'rtl/kernel'/(ANCESTOR+'.sv')).read_text()),'unreviewed G4 RTL delta')
    for suffix,transform in (('.cpp',bench_source),('_threaded.cpp',wrapper_source)):
        require((root/'rtl/tb'/(NEW_BENCH+suffix)).read_text()==transform((root/'rtl/tb'/(OLD_BENCH+suffix)).read_text()),'unreviewed G4 bench delta')
    pins={'rtl/kernel/'+name:value for name,value in KERNEL_PINS.items()};pins.update(PARENT_PINS);pins.update(NEW_PINS)
    for name,value in pins.items():require(sha((root/name).read_text())==value,'pinned G4 source changed: '+name)
    require(len(KERNEL_PINS)==16,'closed16-kernel compile list')
    return pins
