"""Newly promoted T5b lineage over the frozen exact-state numeric soak oracle.

Only source/lineage/harness bindings change. Independent integer arithmetic and
the distinction between chunks and an uninterrupted chain remain byte-pinned.
The frozen CRTMont results are neither overwritten nor relabeled.
"""
import hashlib
import json
from pathlib import Path
import re
import types

ROOT = Path(__file__).resolve().parents[1]
SELF = 'reference/core27_t5b_soak_v1.py'
BASE = 'reference/core27_crtmont_soak_v1.py'
BASE_SHA = '8075e2033a01b09b9bbc344b72f23df4ebbc90b8489caadfbd0546e6f3bcfe3a'
TOP = 'genefer_square_core27_stream_prefetch_r2_host_broadcast_orient8_rootfused_crtmont_prefill_pipe_v1'
CORE_SHA = '704f7fed433d724dbc8e56c7b725824ec36cce78d6ce8f021307837d2a96b8e7'
FIT = 'results/throughput-20260929/core27-t5b-provisional64-aws-fit-v1'
FIT_SHA = '1a1a67980f1744be70c0b089dcdf7e20c4cdd8714cbac26bd5798c28abbcc011'
QSF_SHA = '29ec658f30ef789f0ed1da0899300927e3d149c71110a2942360482b9df0d477'
AUDIT = 'results/throughput-20260929/core27-t5b-selected9668-audit-m8azn-v3/independent-review-v1.json'
AUDIT_SHA = 'bdc8295fc1dac155b28635b915c39c80b24e121001de9c6a8cba595de327bec2'
READINESS = 'results/throughput-20260929/core27-t5b-promotion-readiness-v3.json'
READINESS_SHA = '11960a89c87402455e7f08e811655a4a350050d12e02a5357e1a6f85839d203a'
ADVISOR = 'docs/briefs/2026-10-01-advisor-verification-T5b.md'
ADVISOR_SHA = '7a48c720b486799078fe6e4b0df4ef56840b0a295da576d6e7c2c93e1d28f04f'


def need(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def parent_sources():
    need(sha(ROOT/FIT/'manifest.json') == FIT_SHA and sha(ROOT/FIT/'probe.qsf') == QSF_SHA,
         'SOAK_T5B_PHYSICAL_PARENT_IDENTITY')
    for name, pin in ((AUDIT, AUDIT_SHA), (READINESS, READINESS_SHA), (ADVISOR, ADVISOR_SHA)):
        need(sha(ROOT/name) == pin, 'SOAK_T5B_ACCEPTED_PARENT_BINDING')
    manifest = json.loads((ROOT/FIT/'manifest.json').read_text())
    audit = json.loads((ROOT/AUDIT).read_text())
    readiness = json.loads((ROOT/READINESS).read_text())
    need(manifest['top'] == TOP and audit['status'] == 'PASS_scoped_T5b_whole64_selected9668ns_four_corner_internal_STA'
         and audit['pins']['physical_manifest_sha256'] == FIT_SHA
         and audit['pins']['candidate_core_sha256'] == readiness['candidate_core_sha256'] == CORE_SHA
         and readiness['physical_manifest_sha256'] == FIT_SHA, 'SOAK_T5B_RECEIPT_CANDIDATE_IDENTITY')
    # The original fit is deliberately retained as provisional history. The
    # separately hash-pinned advisor acceptance/main adoption changes status,
    # not that archived physical manifest or any RTL file.
    order = re.findall(r'^set_global_assignment -name SYSTEMVERILOG_FILE rtl/(\S+)$',
        (ROOT/FIT/'probe.qsf').read_text(), re.M)
    need(len(order) == 16 and set(order) == set(manifest['source_sha256']), 'SOAK_T5B_RTL_CLOSURE')
    pins = {}
    for name in order:
        relative = 'rtl/kernel/'+name; pin = manifest['source_sha256'][name]
        need(sha(ROOT/FIT/'rtl'/name) == sha(ROOT/relative) == pin, 'SOAK_T5B_RTL_DRIFT '+name)
        pins[relative] = pin
    need(pins['rtl/kernel/'+TOP+'.sv'] == CORE_SHA, 'SOAK_T5B_ACCEPTED_CORE')
    return order, pins


def reference():
    raw = (ROOT/BASE).read_bytes()
    need(hashlib.sha256(raw).hexdigest() == BASE_SHA, 'SOAK_T5B_FROZEN_NUMERIC_ORACLE')
    text = raw.decode()
    replacements = [
        ("SELF = 'reference/core27_crtmont_soak_v1.py'", "SELF = '"+SELF+"'"),
        ("BENCH = 'rtl/tb/core27_crtmont_soak_v1.cpp'", "BENCH = 'rtl/tb/core27_t5b_soak_v1.cpp'"),
        ("TEST = 'tests/test_core27_crtmont_soak_v1.py'", "TEST = 'tests/test_core27_t5b_soak_v1.py'"),
        ("TOP = 'genefer_square_core27_stream_prefetch_r2_host_broadcast_orient8_rootfused_crtmont'", "TOP = '"+TOP+"'"),
        ("PARENT = 'results/throughput-20260929/core27-rootfused-crtmont64-aws-fit-v1'", "PARENT = '"+FIT+"'"),
        ("PARENT_SHA = '93af1da3453947be920e73ad3f9ead17da3a8249966c7d7db5353f4502f6ece3'", "PARENT_SHA = '"+FIT_SHA+"'"),
        ("AUDIT = 'results/throughput-20260929/crtmont-96-selected-v1/independent-review-v1.json'", "AUDIT = '"+AUDIT+"'"),
        ("AUDIT_SHA = 'fe70997804d364f0b79058cc00f233e6be01552226568f31aca42bf2bae5708e'", "AUDIT_SHA = '"+AUDIT_SHA+"'"),
        ("QSF_SHA = '12fdd3fa0053f0d36be2a94cd78a1984ff9d7647daf0eaaec22a5f14ae91e96f'", "QSF_SHA = '"+QSF_SHA+"'"),
        ("lineage='promoted-crtmont'", "lineage='promoted-t5b'"),
        ('Exact promoted CRTMont parent, generic load/square/readback host driver. No RTL change, no T5b promotion.',
         'Exact newly promoted T5b parent, generic load/square/readback driver. No RTL change; old CRTMont runs stay separate.')]
    for old, new in replacements:
        need(text.count(old) == 1, 'SOAK_T5B_UNIQUE_SOURCE_ANCHOR')
        text = text.replace(old, new, 1)
    module = types.ModuleType('_t5b_frozen_numeric_oracle'); module.__file__ = str(ROOT/SELF)
    exec(compile(text, str(ROOT/BASE)+'[promoted-T5b-lineage]', 'exec'), module.__dict__)
    module.parent_sources = parent_sources
    return module


if __name__ == '__main__':
    reference().main()
