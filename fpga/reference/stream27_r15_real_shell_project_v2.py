"""Additive typed-mode/project-local descriptor capture; v1 is preserved."""
import json
from . import stream27_r15_real_shell_project_v1 as parent

ROOT,BASE=parent.ROOT,parent.BASE
SELF='reference/stream27_r15_real_shell_project_v2.py'


def prepare(output):
    parent.prepare(output)
    output=parent.Path(output).resolve()
    manifest=json.loads((output/'manifest.json').read_bytes())
    manifest['physical_mode']='r15_real_shell_v1'
    # The source descriptor saved for collection must be exactly the staged
    # descriptor, including project-local receipt/input and source-bundle refs.
    proof='rtl/proofs/real-shell.json'
    raw=parent.json_bytes(manifest['r15_real_shell'])
    (output/proof).write_bytes(raw)
    manifest['control_sha256'][proof]=parent.sha(raw)
    manifest['preparation_source_sha256'][SELF]=parent.sha((ROOT/SELF).read_bytes())
    (output/'manifest.json').write_bytes(parent.json_bytes(manifest))
    return dict(project=str(output),manifest_sha256=parent.sha((output/'manifest.json').read_bytes()),
      custom_sources=len(manifest['source_sha256']),vendor_sources=len(manifest['r15_real_shell']['vendor_sources']),
      physical_mode=manifest['physical_mode'],status=manifest['status'])
