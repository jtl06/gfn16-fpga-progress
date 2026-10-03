"""Source handoff for one existing Azure reference recipe; does not launch."""
import hashlib
from pathlib import Path

from .r15_genefer_pl_fixture import check_upstream, UPSTREAM_PINS

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = 'results/throughput-20260929/r15-host-software-v1/genefer22-source-pl-v1'
MEMBERS = ('__init__.py', 'host/__init__.py', 'host/THIRD-PARTY-NOTICES',
    'host/r15_arithmetic.py', 'host/r15_genefer_proof.py',
    'host/r15_genefer_format_fixture.py', 'host/r15_genefer_pl_fixture.py',
    'host/r15_genefer_pl_oracle.cpp', 'host/r15_genefer_pl_output.py',
    'host/r15_genefer_pl_recipe.py')


def recipe():
    check_upstream(ROOT / UPSTREAM)
    names = MEMBERS + tuple(UPSTREAM + '/' + name for name in UPSTREAM_PINS)
    sources = {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in names}
    return dict(schema='r15-pinned-genefer-pl-recipe-v1',
        identity='r15-pinned-genefer-pl-gl-azure-v1', source_sha256=sources,
        argv=['{python}', '-B', '-m', 'fpga.host.r15_genefer_pl_fixture',
              '--upstream', '{source_root}/fpga/' + UPSTREAM,
              '--work', '{output_root}/genefer-pl-work', '--compiler', '/usr/bin/g++'],
        validator=dict(source='host/r15_genefer_pl_output.py', function='validate', config={}),
        resources=dict(cores=2, threads=1, ram_gib=8, scratch_gib=4),
        allowed_hosts=['azure-fit'], max_command_seconds=105, max_unit_seconds=120,
        expected_returncode=0,
        scope=dict(software_only=True, synthetic_GMP_transform=True,
                   upstream_PL_GL_methods=True, HDL=False, device=False,
                   full_N_PRP=False, BOINC_runtime=False, promotion=False))


if __name__ == '__main__':
    print(__import__('json').dumps(recipe(), sort_keys=True, indent=2))
