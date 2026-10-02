"""Source-only A11 derivative of the audited crtmont lineage.

Only the recurrence child changes; ancestor source pins come from the scoped
100 MHz independent review. No integration simulation or physical claim.
The existing periodmask component is reused byte-for-byte, not renamed V2:
V2 refers to the explicit-success-return paired C++ harness.
"""
import hashlib
from pathlib import Path

RECURRENCE = 'genefer_root_recurrence27'
ENGINE = 'genefer_ntt_banked27_prefetch_r2_orient8_rootfused_engine'
HOST = 'genefer_ntt_banked27_prefetch_r2_host_broadcast_orient8_rootfused_engine'
TOP = 'genefer_square_core27_stream_prefetch_r2_host_broadcast_orient8_rootfused_crtmont'
PINS = {
    RECURRENCE: 'c8adc265915192807efee46799a782f1649a4408313098baaed8b4a808afeb9e',
    ENGINE: 'd52351bdf53c6809208f7a466848b4376cbd8ff87c52f633dc8c2814026b47ee',
    HOST: 'b3d06d1e5f90e4944fdf88ff264cb7edbd73d0daf9f46ccf93389ab4889d9e3f',
    TOP: 'b6dbd4fccc6d7708fd295d3c82e2ebec444c4a2fbde8612851f10f979da04895',
}
NAMES = {RECURRENCE: RECURRENCE + '_periodmask',
         ENGINE: ENGINE.replace('_engine', '_periodmask_engine'),
         HOST: HOST.replace('_engine', '_periodmask_engine'),
         TOP: TOP + '_periodmask'}
PERIODMASK_SHA = '47d9f7e0db2c784424d4b148760f4235baeffef08969c4e790eb3c1e32a3e389'


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def once(text, old, new):
    require(text.count(old) == 1, 'ambiguous derivative anchor')
    return text.replace(old, new)


def expected(name, original):
    require(name in (ENGINE, HOST, TOP), 'supported hierarchy member')
    require(sha(original) == PINS[name], 'audited crtmont ancestor drift')
    text = once(original, 'module ' + name + ' #(', 'module ' + NAMES[name] + ' #(')
    child = {ENGINE: RECURRENCE, HOST: ENGINE, TOP: HOST}[name]
    return once(text, child + ' #(', NAMES[child] + ' #(')


def validate_files(root):
    kernel = Path(root) / 'rtl/kernel'
    for name, digest in PINS.items():
        require(sha((kernel / (name + '.sv')).read_text()) == digest, 'ancestor drift: ' + name)
    candidate = kernel / (NAMES[RECURRENCE] + '.sv')
    require(sha(candidate.read_text()) == PERIODMASK_SHA, 'qualified component source drift')
    result = {str(candidate.relative_to(root)): PERIODMASK_SHA}
    for name in (ENGINE, HOST, TOP):
        path = kernel / (NAMES[name] + '.sv')
        text = path.read_text()
        require(text == expected(name, (kernel / (name + '.sv')).read_text()),
                'unreviewed crtmont periodmask delta: ' + name)
        result[str(path.relative_to(root))] = sha(text)
    return result
