"""Separate COMPLETE 65540-operation ordinal positive/typed-negative roles.

The P16 v4 1800-second timeout is retained. This source-only preparer does
not lengthen any runner or package bound: dispatcher owns the narrow single
model-step3300/overall3600/outer3700 adapter. No shortened count or bypass.
"""
import hashlib
import json
from pathlib import Path
from . import stream27_host_chain_native_v4 as parent

ROOT = parent.ROOT
PARENT_PIN = '0603c390082ddaa290caf7397b7aa3825eedd4ad829b0cc7f73b86fe96e12532'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def negative_source(text):
    old = 'bool ordinal=argc==2&&std::string(argv[1])=="--ordinal",negative=argc==4&&std::string(argv[3])=="--negative-feed";'
    new = 'bool ordinal_negative=argc==2&&std::string(argv[1])=="--ordinal-negative";\n    bool ordinal=(argc==2&&std::string(argv[1])=="--ordinal")||ordinal_negative,negative=argc==4&&std::string(argv[3])=="--negative-feed";'
    output = '        std::cout<<ORDINAL_LABEL<<" operations="<<c.operations'
    reject = '        need(context.threads()==1&&d.threads()==1,"S4_LONG_THREADS");\n        if(ordinal_negative)throw std::runtime_error("S4_LONG_ORDINAL_TYPED expected="+std::to_string(c.operations+1)+" actual="+std::to_string(c.operations));\n'
    if text.count(old) != 1 or text.count(output) != 1:
        raise ValueError('S4_ORDINAL_TYPED_EXACT_PARENT')
    return text.replace(old, new).replace(output, reject + output)


def prepare(destination, *, p=16, negative=False):
    if p not in (8, 16) or type(negative) is not bool:
        raise ValueError('S4_ORDINAL_TYPED_GEOMETRY_ROLE')
    if sha(ROOT / 'reference/stream27_host_chain_native_v4.py') != PARENT_PIN:
        raise ValueError('S4_ORDINAL_TYPED_PARENT_DRIFT')
    result = parent.prepare(destination, n=32, p=p, ordinal=True)
    destination = Path(destination).resolve()
    source = destination / 'inputs/fpga'
    cpp = source / 'rtl/tb/stream27_host_chain_v1.cpp'
    original_cpp_pin = sha(cpp)
    if negative:
        cpp.write_text(negative_source(cpp.read_text()))
    local = 'reference/stream27_host_chain_ordinal_native_v1.py'
    lineage = source / 'lineage' / local
    lineage.write_bytes((ROOT / local).read_bytes())
    path = destination / 'manifest.json'
    manifest = json.loads(path.read_text())
    if len(manifest['steps']) != 1:
        raise ValueError('S4_ORDINAL_EXACT_SINGLE_COMPLETE_STEP')
    if negative:
        manifest['steps'] = [dict(name='s4-long-ordinal-typed-negative',
            argv=['{exe}', '--ordinal-negative'], expected_returncode=1,
            expected_stdout='', expected_stderr='S4_LONG_ORDINAL_TYPED expected=65541 actual=65540\n')]
    manifest['sources'] = {str(path.relative_to(source)): sha(path)
                          for path in sorted(source.rglob('*')) if path.is_file()}
    path.write_text(json.dumps(manifest, indent=2) + '\n')
    result.update(status='prepared_source_ONLY_runner_bridge_pending',
        manifest_sha256=sha(path), source_count=len(manifest['sources']), ordinal=True,
        role='typed_negative' if negative else 'positive', p=p,
        complete_operation_count=65540, full_descriptor_count=65539,
        parent_cpp_sha256=original_cpp_pin, cpp_sha256=sha(cpp),
        required_runner_contract=dict(single_model_command_seconds=3300,
            existing_overall_seconds=3600, existing_outer_seconds=3700,
            ancillary_command_seconds=1800, native_threads=1),
        runner_policy_changed=False, queued=False, promotion_allowed=False,
        source_delta='positive CPP/RTL/assets unchanged; negative adds argv recognition and rejects only AFTER all65540 operations/allN words/full-width final ordinal/native thread check',
        limitations=['Not a runtime PASS or estimated upper bound',
            'Prior P16 model timeout at1800.098s is not arithmetic failure',
            'Separate complete typed-negative run; no doubled long steps inside one envelope'])
    (destination / 'preparation.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


if __name__ == '__main__':
    import sys
    print(json.dumps(prepare(sys.argv[1], p=int(sys.argv[2]),
        negative=len(sys.argv) == 4 and sys.argv[3] == 'negative'), indent=2))
