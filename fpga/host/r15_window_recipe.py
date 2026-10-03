"""One literal existing-executor source closure, no runner or transport."""
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MEMBERS = ('__init__.py', 'host/__init__.py', 'tests/__init__.py',
    'host/THIRD-PARTY-NOTICES', 'host/r15_arithmetic.py', 'host/r15_genefer_proof.py',
    'host/r15_transport.py', 'host/r15_image_codec.py', 'host/r15_link_adapter.py',
    'host/r15_checkpoint_store.py', 'host/r15_canonical_job_session.py',
    'host/r15_window_selftest.py', 'host/r15_window_output.py', 'host/r15_window_recipe.py',
    'tests/test_r15_canonical_job_session.py', 'tests/test_r15_image_codec.py',
    'tests/test_r15_checkpoint_store.py', 'tests/test_r15_link_adapter.py',
    'reference/__init__.py', 'reference/stream27_r15_host_mmio_v1.py',
    'reference/stream27_r15_host_link_model_v1.py', 'reference/stream27_host_offload_model_v1.py',
    'reference/stream27_blockcarry_param_model_v1.py', 'reference/stream27_canonical_image_model_v1.py',
    'reference/stream27_signed_boundary_oracle.py', 'reference/stream_ntt_blockwrap2_proposal.py',
    'reference/stream_ntt_model.py')


def recipe():
    sources = {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in MEMBERS}
    return dict(schema='r15-host-software-window-recipe-v1',
        identity='r15-host-canonical-window-azure-v1', source_sha256=sources,
        argv=['{python}', '-B', '-m', 'fpga.host.r15_window_selftest', '--engine', 'gmp'],
        validator=dict(source='host/r15_window_output.py', function='validate',
                       config=dict(require_gmp=True)),
        resources=dict(cores=2, threads=1, ram_gib=8, scratch_gib=4),
        allowed_hosts=['azure-fit'], max_command_seconds=105, max_unit_seconds=120,
        expected_returncode=0, scope=dict(software_only=True, software_endpoint_model=True,
            HDL=False, device=False, BOINC_runtime=False, full_N_numeric=False, promotion=False))


if __name__ == '__main__':
    print(__import__('json').dumps(recipe(), sort_keys=True, indent=2))
