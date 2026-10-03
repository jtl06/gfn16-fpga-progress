"""Real BOINC SDK standalone boundary over the frozen PRIVATE R15 job backend.

This does not accept Genefer/PrimeGrid jobs or emit project results. Upstream
Genefer d506 CLI supports n12..23 (N>=4096), not these small test jobs. A real
SDK linked test is distinct from an anonymous-platform deployment contract.
"""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import platform

from fpga.host.r15_arithmetic import need
from fpga.host.r15_boinc_wrapper import Status, run_offline_job, _decode, _read


class SDK:
    def __init__(self, library):
        need(platform.system() == 'Linux', 'SDK_AZURE_LINUX_ONLY')
        library = Path(library)
        need(library.is_absolute() and library.is_file() and not library.is_symlink(),
             'SDK_LIBRARY')
        need(not Path('init_data.xml').exists() and not Path('init_data.xml').is_symlink(),
             'SDK_NO_CLIENT_INIT_DATA')
        self.api = ctypes.CDLL(str(library))
        for name in ('init','standalone','status','checkpoint_due','checkpoint_done'):
            fn = getattr(self.api, 'r15_sdk_'+name)
            fn.argtypes = []; fn.restype = ctypes.c_int
        self.api.r15_sdk_resolve.argtypes = [ctypes.c_char_p,ctypes.c_char_p,ctypes.c_int]
        self.api.r15_sdk_resolve.restype = ctypes.c_int
        self.api.r15_sdk_progress.argtypes = [ctypes.c_double]
        self.api.r15_sdk_progress.restype = ctypes.c_int
        self.api.r15_sdk_fraction.argtypes = []; self.api.r15_sdk_fraction.restype = ctypes.c_double
        self.api.r15_sdk_finish.argtypes = [ctypes.c_int]; self.api.r15_sdk_finish.restype = ctypes.c_int
        need(self.api.r15_sdk_init() == 0 and self.api.r15_sdk_standalone() == 1,
             'SDK_REAL_STANDALONE_INIT')
        self.progress, self.checkpoints = [], 0

    def resolve(self, logical):
        need(logical in ('r15_test_input.json','r15_test_result.json'), 'SDK_PRIVATE_LOGICAL_NAME')
        output = ctypes.create_string_buffer(4096)
        need(self.api.r15_sdk_resolve(logical.encode(), output, len(output)) == 0,
             'SDK_FILENAME_RESOLUTION')
        result = Path(os.fsdecode(output.value))
        need(result.resolve() == (Path.cwd()/logical).resolve(), 'SDK_STANDALONE_LOCAL_ONLY')
        return result

    def status(self):
        flags = self.api.r15_sdk_status()
        need(flags >= 0 and flags <= 15, 'SDK_STATUS')
        return Status(bool(flags&1),bool(flags&2),bool(flags&4),bool(flags&8))

    def time_to_checkpoint(self):
        self.api.r15_sdk_checkpoint_due()
        return True  # application-elected durability; not a fabricated timer request

    def checkpoint_completed(self):
        need(self.api.r15_sdk_checkpoint_done() == 0, 'SDK_CHECKPOINT')
        self.checkpoints += 1

    def fraction_done(self, fraction):
        need(not self.progress or fraction >= self.progress[-1], 'SDK_PROGRESS_MONOTONIC')
        need(self.api.r15_sdk_progress(fraction) == 0, 'SDK_PROGRESS')
        self.progress.append(fraction)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--library', required=True, type=Path)
    p.add_argument('--resume', action='store_true')
    p.add_argument('--yield-one-window', action='store_true')
    a=p.parse_args()
    sdk=SDK(a.library)
    job=_decode(_read(sdk.resolve('r15_test_input.json')))
    outcome=run_offline_job(job,Path.cwd()/'private-checkpoint',enabled=True,engine='gmp',
                            resume=a.resume,callbacks=sdk,
                            max_windows=1 if a.yield_one_window else None)
    phase=outcome['phase']
    if phase=='complete':
        result=_read(Path('private-checkpoint/result.json'))
        target=sdk.resolve('r15_test_result.json')
        # Actual private result already fully verified/atomically committed.
        # Exclusive export is not a BOINC upload; the client is absent.
        with target.open('xb') as stream:
            stream.write(result); stream.flush(); os.fsync(stream.fileno())
        need(sdk.api.r15_sdk_fraction()==1.0, 'SDK_COMPLETE_PROGRESS')
        print('R15_REAL_SDK '+json.dumps(dict(standalone=True,phase=phase,
              result_sha256=hashlib.sha256(result).hexdigest(),
              checkpoints=sdk.checkpoints,progress_count=len(sdk.progress),
              real_boinc_api=True,project_abi=False,client=False,device=False)),flush=True)
        sdk.api.r15_sdk_finish(0)
        raise RuntimeError('SDK_FINISH_RETURNED')
    need(phase=='yielded' and a.yield_one_window and not Path('r15_test_result.json').exists(),
         'SDK_NO_PREMATURE_RESULT')
    print('R15_REAL_SDK '+json.dumps(dict(standalone=True,phase=phase,
          verified_completed=outcome['verified_completed'],real_boinc_api=True,
          project_abi=False,client=False,device=False)),flush=True)
    # This is a deliberate standalone test interruption, NOT success finish.
    return 75


if __name__=='__main__':
    raise SystemExit(main())
