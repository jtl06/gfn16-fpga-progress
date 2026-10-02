"""Prepare the small real-SV shared-runner smoke; never dispatch."""
import argparse
import importlib.util
import json
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[1]


def prepare(out):
    spec=importlib.util.spec_from_file_location('_smoke_package',ROOT/'tools/native_package_v1.py')
    package=importlib.util.module_from_spec(spec);spec.loader.exec_module(package)
    package.need(not out.exists(),'fresh smoke stage');out.mkdir(parents=True)
    source=out/'source/fpga';source.mkdir(parents=True)
    files=['rtl/tb/native_infrastructure_smoke_v1.sv','rtl/tb/native_infrastructure_smoke_v1.cpp']
    for name in files:
        target=source/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,target)
    manifest=dict(schema='native-source-gate-v1',status='prepared_not_executed',host='gfn16-pilot-c4d',
        source_root='/unused/fpga',output_parent='/unused',sources={n:package.sha(source/n) for n in files},
        build=dict(top='native_infrastructure_smoke_v1',sv_sources=[files[0]],cpp_source=files[1],parameters={},cflags=['-std=c++17','-Werror=return-type','-O1']),
        probe=dict(argv=['{exe}','--runtime-probe'],expected_json=dict(context_threads=1,model_threads=1,expected_threads=1)),
        steps=[dict(name='control',argv=['{exe}'],expected_returncode=0,expected_stdout='NATIVE_SMOKE_PASS ticks=257 accepted=200 resets=7\n',expected_stderr='')])
    package.dump(out/'input-manifest.json',manifest)
    receipt_path=ROOT/'docs/briefs/replies/2026-10-01-fit-queue-allowance-0525-v1.json'
    receipt=json.loads(receipt_path.read_text());gcp=receipt['GCP']
    budget=dict(provider='gcp',observed_at=receipt['at_utc'],total_allowance_usd=gcp['allowance_usd'],
        planning_usd_per_hour=gcp['new_worker_planning_rate_usd_hour'],remaining_after_reserves_usd=gcp['estimated_remaining_usd'],
        actual_billing=False,source_receipt_sha256=package.sha(receipt_path))
    package.dump(out/'budget.json',budget)
    return package.prepare(out/'input-manifest.json',source,'gcp-c4d-sim01-v1','shared-infra-smoke-v1','run',out/'packet',out/'budget.json')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    print(json.dumps(prepare(parser.parse_args().output.resolve()),indent=2))
