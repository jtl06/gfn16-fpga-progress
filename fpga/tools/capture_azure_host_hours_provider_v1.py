"""Preserve shared authenticated read-only Azure HOST-HOURS provider inputs."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

FPGA = Path(__file__).resolve().parents[1]
CHECKER = FPGA/'cloud/host_hours_azure_v2.py'
if hashlib.sha256(CHECKER.read_bytes()).hexdigest() != 'b0875ec8fb12780c637548e9664d25d47a2b77bb8ef7d3ff997bbdfc640a8c9e':
    raise ValueError('shared pure checker source drift')
spec = importlib.util.spec_from_file_location('azure_shared_meter', CHECKER)
meter = importlib.util.module_from_spec(spec); spec.loader.exec_module(meter)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('destination', type=Path)
    destination = parser.parse_args().destination.resolve()
    if not destination.is_relative_to(FPGA/'results') or destination.exists():
        raise ValueError('fresh shared project-results output required')
    result = meter.provider_inputs()
    result['capture_helper_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    with destination.open('x') as stream:
        json.dump(result, stream, indent=2); stream.write('\n')
    print(json.dumps(dict(path=str(destination), sha256=hashlib.sha256(destination.read_bytes()).hexdigest(), observed_at_utc=result['observed_at_utc'])))
