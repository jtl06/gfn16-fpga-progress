"""Exact local whole-core host-broadcast substitution; no HDL execution.

The standalone host-memory gate does not qualify this integrated candidate.
Only the top name and host-wrapper instance type change in RTL. Bench model
names/include paths change; all independent expected-vector comparisons,
strict abort eligibility and phase/counter assumptions remain byte-identical.
The 16-kernel compiled closure does not include the old top or old wrapper.
No runner, remote transfer, fit, board image, or measured saving is implied.
"""
import hashlib
from pathlib import Path

ANCESTOR='genefer_square_core27_stream_prefetch_r2'
CANDIDATE=ANCESTOR+'_host_broadcast'
OLD_HOST='genefer_ntt_banked27_prefetch_r2_host_engine'
NEW_HOST='genefer_ntt_banked27_prefetch_r2_host_broadcast_engine'
OLD_BENCH='square_core27_stream_prefetch_r2'
NEW_BENCH=OLD_BENCH+'_host_broadcast'
ANCESTOR_PINS={
    'rtl/kernel/'+ANCESTOR+'.sv':'452dbb922c4cd6145fc733a4036d526b9d5d465bfe92a93fd0e69f129f060af6',
    'rtl/kernel/'+OLD_HOST+'.sv':'b0fc9014b73eac3a989ce416b15e8c802a2a2fe54922af3c77489237679e0302',
    'rtl/tb/'+OLD_BENCH+'.cpp':'3537fdb2d83c25a94deb3fccbf177b09807db72e686ac13e6e290ab1ead70c4f',
    'rtl/tb/'+OLD_BENCH+'_threaded.cpp':'1f9ac5aa5e70775417b8fa7a4d9f422c2825653d7e5aff43c250f187d9bf6ae9',
}
KERNEL_PINS={
    'genefer_montgomery_mul27_sparse_pipe.sv':'501d0ce309a3915f7aed0f3bde14ba1ee8d56ddc5f6abef1f2f5bb572d64db4b',
    'genefer_digit_reduce27_pipe.sv':'61e14bb13c2dbcc13b5030756578a0d0358269beb24fb207a5641b98795883e8',
    'genefer_sdp_ram32.sv':'993567fb68fdc216b9ff04489d1810f743b86564434e4b48261ad606b25d53b0',
    'genefer_ntt_banked27_engine.sv':'7ae89e702b671e3fbe8a1f90beb99ea595c832729e5e94232bf82515f1d74fe9',
    'genefer_root_recurrence27.sv':'c8adc265915192807efee46799a782f1649a4408313098baaed8b4a808afeb9e',
    'genefer_ntt_banked27_prefetch_r2_engine.sv':'552d273972af97c3363b77df0798e08a962d283869bcc95159f378a0f0070b17',
    NEW_HOST+'.sv':'0960922332ea919a72a1ee591a70006bba76af7f26bc5308b68f50e327583e29',
    'genefer_root_profile27_r2_rom.sv':'cb851bec51f518a71d216d4a993ffa3aa937b8230474c38898b061e7ad42dea6',
    'genefer_mod64_pipe.sv':'e582dba87dce51794a38039fd02574f443c53750bcafc8fcb1f4d0d50fc60839',
    'genefer_crt3_27_pipe.sv':'279c6c8c3185eeaaa505283f858fd04904c6daccd30720f6b3bf78e14a6fa160',
    'genefer_sp_ram.sv':'b97d2f43db1b1e1aa60b9b7fc2b720af1e302bd5ff9e35854c89b30e5fb610df',
    'genefer_div_recip_narrow.sv':'eef327cee81d41895a068b746a3715daba95d43bea919edbddf9b498ecfc38bf',
    'genefer_carry_prefix_stream_pipe.sv':'9838c6852cac57f7901f8b57dcbb4ee11b7fa129ef86e40158d67cc789b06e5e',
    'genefer_div_recip_precision.sv':'832021ed0b3410dc867d92ac4436a725d5717f9630d233073e39896789ebbd7c',
    'genefer_carry_prefix_stream_precision.sv':'ba7ce9d0c1a99ad959bfe9909c62f341fabd537c76f196c5bcb6394c161296d3',
    CANDIDATE+'.sv':'ea2b518880cb1c3191c71d35a232d2483aee82046ecd4d930d7ac7ffa07a80e1',
}
BENCH_PINS={
    'rtl/tb/'+NEW_BENCH+'.cpp':'9e11a73d910cf6ca4f89a6cec42a41c43310f8baa9d504cf0476b27220bc0644',
    'rtl/tb/'+NEW_BENCH+'_threaded.cpp':'7a21cd62a4879ab1f24e4a46f05e01131a4f7f271764c6b988da701fda58f2eb',
}


def require(value,message):
    if not value:raise ValueError(message)


def sha(text):return hashlib.sha256(text.encode()).hexdigest()


def pinned(text,name):
    require(name in ANCESTOR_PINS and sha(text)==ANCESTOR_PINS[name],'frozen ancestor identity: '+name)


def replace(text,old,new,count=1):
    require(text.count(old)==count,'ambiguous source anchor: '+old)
    return text.replace(old,new)


def core_source(original):
    pinned(original,'rtl/kernel/'+ANCESTOR+'.sv')
    text=replace(original,'module '+ANCESTOR+' #(','module '+CANDIDATE+' #(')
    return replace(text,OLD_HOST+' #(',NEW_HOST+' #(')


def bench_source(original):
    pinned(original,'rtl/tb/'+OLD_BENCH+'.cpp')
    return replace(original,'V'+ANCESTOR,'V'+CANDIDATE,2)


def wrapper_source(original):
    pinned(original,'rtl/tb/'+OLD_BENCH+'_threaded.cpp')
    text=replace(original,'V'+ANCESTOR,'V'+CANDIDATE)
    # Keep the same explicit context macro and private renamed-main symbol:
    # this wrapper is independently compiled, not linked with its ancestor.
    return replace(text,'#include "'+OLD_BENCH+'.cpp"','#include "'+NEW_BENCH+'.cpp"')


def validate_bench_files(root):
    root=Path(root)
    for suffix,transform in (('.cpp',bench_source),('_threaded.cpp',wrapper_source)):
        expected=transform((root/'rtl/tb'/(OLD_BENCH+suffix)).read_text())
        relative='rtl/tb/'+NEW_BENCH+suffix
        actual=(root/relative).read_text()
        require(actual==expected and sha(actual)==BENCH_PINS[relative],'unreviewed bench delta: '+relative)
    return dict(BENCH_PINS)


def validate_files(root):
    root=Path(root)
    for name,wanted in ANCESTOR_PINS.items():
        require(sha((root/name).read_text())==wanted,'frozen ancestor changed: '+name)
    original=(root/'rtl/kernel'/(ANCESTOR+'.sv')).read_text()
    candidate=(root/'rtl/kernel'/(CANDIDATE+'.sv')).read_text()
    require(candidate==core_source(original),'unreviewed whole-core delta')
    result={}
    for name,wanted in KERNEL_PINS.items():
        relative='rtl/kernel/'+name
        require(sha((root/relative).read_text())==wanted,'compiled kernel identity: '+relative)
        result[relative]=wanted
    result.update(validate_bench_files(root))
    return result
