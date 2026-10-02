"""One source-only packet for the existing P8 AWS saved-layout checkpoint."""
import importlib.util
import json
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('audit_adapter', ROOT/'cloud/plain_fit_audit_noexceptions_v1.py')
ad = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ad)
assert ad.sha(ROOT/'cloud/plain_fit_audit_noexceptions_v1.py') == 'dc2bf465823e04ad54d122d894b992944c8d8bc13687bfb9ff7e59f48ead0bd1'
assert ad.sha(ROOT/'tools/fit_audit_stage.py') == 'e60669aef65f32cca4776dc10e345e5112a533c7cef5f44140e720a5d2da2636'
assert not (ROOT/'docs/briefs/PAUSE').exists()
DEST = ROOT/'results/throughput-20260929/p8-aws-10000-14120-audit-v2'
TOOLS = DEST/'audit-tools-p8-aws-10000-14120-v2'
TOOLS.mkdir(parents=True)
runtime = ad.runtime_pins(ad.AWS, source_root=ROOT)
sources = {'plain_fit_audit_noexceptions_v1.py': ROOT/'cloud/plain_fit_audit_noexceptions_v1.py',
           ad.AUDIT: ROOT/'tools'/ad.AUDIT, ad.TCL: ROOT/'synthesis'/ad.TCL,
           'fit_audit_stage.py': ROOT/'tools/fit_audit_stage.py'}
sources.update({relative:ROOT/relative[5:] for relative in runtime if relative.startswith('fpga/')})
for relative, source in sources.items():
    target = TOOLS/relative
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('xb') as stream:
        stream.write(source.read_bytes())
remote = Path('/home/ubuntu/gfn16-worker')
config = dict(adapter=dict(path=str(remote/TOOLS.name/'plain_fit_audit_noexceptions_v1.py'), sha256=ad.sha(ROOT/'cloud/plain_fit_audit_noexceptions_v1.py')),
    host=ad.AWS, slot='b', unit='gfn16-p8-aws-10000-14120-audit-v2.service',
    project=str(remote/'p8-whole-host-10000-aws6-recovery-v1'),
    output=str(remote/'p8-aws-10000-14120-audit-v2'),
    original_request=dict(path=str(remote/'fit-queue-tools-p8-whole-host-10000-aws6/request.json'), sha256='8f1a0ff6d0d3514f4dbfa7228fc281f20b107184154711c98c7236382dd87c45'),
    terminal_receipt=dict(path=str(remote/'fit-queue-collection-p8-whole-host-10000-aws6/terminal-collection-v1.json'), sha256='87a49c98692f9e6c7ae27321d7af895a6fe7191eb49b1b721f2aefb9248414b2'),
    original_invocation='cc7b5b27c2de49edbb486bb237947310',
    manifest_sha256='762d765ac2518e19005ca5503e8f6110f55059f8bfdf54200c41894075f113ce',
    selected_period_ns='14.120', selection_reason='Explicit 10ns baseline plus measured4.110ns setup miss plus10ps reserve; selected testpoint only, not Fmax or highest clock.',
    provider_inputs=None, transition=None, cutoff_utc='2026-10-02T04:00:00Z')
ad.save(TOOLS/'config.json', config)
ad.save(DEST/'packet.json', dict(config_sha256=ad.sha(TOOLS/'config.json'),
    source_sha256=ad.sha(Path(__file__).resolve()),
    files={str(p.relative_to(TOOLS)):ad.sha(p) for p in TOOLS.rglob('*') if p.is_file()},
    budget=ad.meter(ad.AWS, ROOT).admit('aws-m8azn',2280), maximum_native_seconds=2100,
    maximum_service_plus_grace_seconds=2280, original_untouched=True))
archive = DEST/'package.tar.gz'
with tarfile.open(archive, 'x:gz') as stream:
    stream.add(TOOLS, arcname=TOOLS.name)
print(json.dumps(dict(directory=str(DEST), archive=str(archive), archive_sha256=ad.sha(archive), config_sha256=ad.sha(TOOLS/'config.json'))))
