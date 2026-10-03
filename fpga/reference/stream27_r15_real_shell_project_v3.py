"""Collector-compatible control-only successor; all HDL/vendor bytes literal."""
import json
from . import stream27_r15_real_shell_project_v2 as parent

ROOT,BASE=parent.ROOT,parent.BASE
SELF='reference/stream27_r15_real_shell_project_v3.py'


def prepare(output):
    parent.prepare(output)
    p=parent.parent.Path(output).resolve();manifest=json.loads((p/'manifest.json').read_bytes())
    moved={'board_clocks.sdc':'probe.sdc',
           'application_cdc.sdc':'rtl/proofs/application_cdc.sdc',
           'application_registers.qsf':'rtl/proofs/application_registers.qsf'}
    qsf=(p/'probe.qsf').read_text()
    for old,new in moved.items():
        if qsf.count(old)!=1:raise ValueError('R15_REAL_PROJECT_CONTROL_PATH '+old)
        qsf=qsf.replace(old,new)
        (p/old).rename(p/new)
        manifest['control_sha256'][new]=manifest['control_sha256'].pop(old)
    (p/'probe.qsf').write_text(qsf)
    sha=parent.parent.sha;dump=parent.parent.json_bytes
    manifest['control_sha256']['probe.qsf']=sha(qsf.encode())
    descriptor=manifest['r15_real_shell']
    descriptor['clock_control_paths']={'base':'probe.sdc','cdc':'rtl/proofs/application_cdc.sdc',
                                      'registers':'rtl/proofs/application_registers.qsf'}
    descriptor['compatibility_caveats']=[
      'Aperture guard admits complete32-byte beat spans independent of byte enables. Partial enabled bytes at a slave boundary can be refused even if enabled bytes alone fit; arbitrary vendor partial-edge transaction compatibility is not qualified.',
      'A pre-fault accepted read still offered downstream but stalled remains held until acceptance or common reset; no fabricated read completion.',
      'Automatic link-down/retrain/FLR reset delivery and reconnect are not qualified. Recovery requires proven common reset, both-domain drain and DMA arena teardown.',
      'Real hardware board identity, E3 Gen3 timing and retained PHY-profile generation warnings require actual physical/board evidence; no source waiver or speed-grade change.']
    proof='rtl/proofs/real-shell.json';raw=dump(descriptor);(p/proof).write_bytes(raw)
    manifest['control_sha256'][proof]=sha(raw)
    manifest['preparation_source_sha256'][SELF]=sha((ROOT/SELF).read_bytes())
    (p/'manifest.json').write_bytes(dump(manifest))
    return dict(project=str(p),manifest_sha256=sha((p/'manifest.json').read_bytes()),
      custom_sources=len(manifest['source_sha256']),vendor_sources=len(descriptor['vendor_sources']),
      physical_mode=manifest['physical_mode'],status=manifest['status'])
