"""Exact finite normal recipe handoff to the EXISTING reference executor.

This module does not launch, create a queue, or select an unapproved host.
Dispatcher owns the Azure preparation/execution seam. No source regeneration.
"""
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ID = 'r15-host-software-normal-azure-v1'
MEMBERS = (
    '__init__.py', 'host/__init__.py', 'host/THIRD-PARTY-NOTICES',
    'host/r15_arithmetic.py', 'host/r15_genefer_proof.py', 'host/r15_transport.py',
    'host/r15_host_selftest.py', 'host/r15_host_output.py', 'host/r15_host_recipe.py',
    'tests/__init__.py', 'tests/test_r15_host_arithmetic.py', 'tests/test_r15_host_transport.py',
    'reference/__init__.py', 'reference/stream27_r15_host_link_model_v1.py',
    'reference/stream27_host_offload_model_v1.py', 'reference/stream27_blockcarry_param_model_v1.py',
    'reference/stream27_canonical_image_model_v1.py', 'reference/stream27_signed_boundary_oracle.py',
    'reference/stream_ntt_blockwrap2_proposal.py', 'reference/stream_ntt_model.py',
)
LINK_PIN = '24444c207982c037b713ae4d0394e05455bce20dfe70ad54fd02cf1c47f9eff7'


def recipe():
    sources = {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in MEMBERS}
    if sources['reference/stream27_r15_host_link_model_v1.py'] != LINK_PIN:
        raise ValueError('R15_HOST_LINK_ABI_DRIFT')
    return dict(schema='r15-host-software-recipe-handoff-v1', identity=ID,
        source_sha256=sources, argv=['{python}', '-B', '-m', 'fpga.host.r15_host_selftest',
                                    '--engine', 'gmp'],
        validator=dict(source='host/r15_host_output.py', function='validate',
                       config=dict(require_gmp=True)),
        resources=dict(cores=2, threads=1, ram_gib=4, scratch_gib=4),
        allowed_hosts=['azure-fit'], max_command_seconds=105, max_unit_seconds=120,
        expected_returncode=0, scope=dict(software_only=True, HDL=False, device=False,
                                         BOINC_runtime=False, promotion=False))


if __name__ == '__main__':
    import json
    print(json.dumps(recipe(), indent=2, sort_keys=True))
