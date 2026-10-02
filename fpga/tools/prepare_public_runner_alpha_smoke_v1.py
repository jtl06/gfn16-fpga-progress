"""Internal-only staging of the clean original alpha example; no native dispatch."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
PUBLIC = ROOT/'fpga-experiment-runner'
sys.path.insert(0, str(PUBLIC)); sys.dont_write_bytecode = True
from fpga_runner.common import archive, sha, write_json

OUT = ROOT/'fpga/results/throughput-20260929/public-runner-alpha-aethia-stage-v1'
NATIVE = '/home/jtl/gfn-fpga-lab/agent-work/fpga-experiment-runner-alpha-v1'


def main():
    if OUT.exists(): raise ValueError('fresh internal stage required')
    pins = {str(path.relative_to(PUBLIC)):sha(path) for path in PUBLIC.rglob('*') if path.is_file()}
    if any('__pycache__' in name or name.endswith('.pyc') for name in pins): raise ValueError('source-only public tree')
    OUT.mkdir(parents=True)
    archive(OUT/'package.tar.gz', PUBLIC, pins)
    config = dict(schema='fer-toolchain-config-v1', tools=dict(
        verilator='/home/jtl/gfn-fpga-lab/tools/verilator/usr/bin/verilator',
        verilator_bin='/home/jtl/gfn-fpga-lab/tools/verilator/usr/bin/verilator_bin',
        compiler='/usr/bin/x86_64-linux-gnu-g++-15', make='/usr/bin/make', python='/usr/bin/python3.14'),
        support_dirs=['/home/jtl/gfn-fpga-lab/tools/verilator/usr/share/verilator'],
        environment={'VERILATOR_ROOT':'/home/jtl/gfn-fpga-lab/tools/verilator/usr/share/verilator'})
    write_json(OUT/'toolchain.config.json', config)
    recipe = dict(schema='fer-plan-v1', trial='original-alpha-adder-aethia-v1', toolchain=NATIVE+'/toolchain.json',
        workspace=NATIVE+'/run-v1', cpus=[4,6], memory_bytes=4*1024**3, seconds=850,
        jobs=[dict(id='adder', snapshot=NATIVE+'/snapshot/snapshot.json', depends_on=[], seconds=600, reuse=None)])
    write_json(OUT/'recipe.json', recipe)
    manifest = dict(status='prepared_not_executed', native_root=NATIVE, files=pins, package_sha256=sha(OUT/'package.tar.gz'),
        config_sha256=sha(OUT/'toolchain.config.json'), recipe_sha256=sha(OUT/'recipe.json'),
        host='aethia', cpus=[4,6], memory_max_bytes=4*1024**3, memory_swap_max_bytes=0, cpu_quota_percent=200,
        outer_seconds=900, timeout_stop_seconds=15, kill_mode='control-group',
        limitation='Internal deployment data excluded from the clean alpha. Original adder only; no install, cloud or publication.')
    write_json(OUT/'manifest.json', manifest)
    print(json.dumps(dict(stage=str(OUT), files=len(pins), manifest_sha256=sha(OUT/'manifest.json'),
                         package_sha256=manifest['package_sha256']), indent=2))


if __name__ == '__main__': main()
