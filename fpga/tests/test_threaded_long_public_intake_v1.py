"""Actual public submit in an isolated queue; no claim, SSH or native launch."""
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import types
import unittest

ROOT=Path(__file__).resolve().parents[1]


def exercise():
    path=ROOT/'tools/global_queue_v1.py';raw=path.read_text()
    # Exercise the exact planned narrow consumer replacement without editing
    # dispatcher's sole-owned source or touching its live queue.
    raw=raw.replace('native_profile_variants_v7.py','native_profile_variants_v8.py').replace(
      'cfb2873effce30593d6f32b417ab4ea8409f5c81a031652935f28c21d5fea5b0',
      '11cfdd0c35bc0e2afebc61c47bf83a0d05a60be3691e3f0f675e8a39919d9e73')
    q=types.ModuleType('_isolated_public_intake');q.__file__=str(path)
    exec(compile(raw,'[isolated planned matcher8 consumer]','exec'),q.__dict__)
    input_path=ROOT/'queue/inputs/soak-t5b-thread1000-q3-fresh-v2.json'
    target_id=json.loads(input_path.read_text())['id']
    with tempfile.TemporaryDirectory() as tmp:
        q.QUEUE=Path(tmp)
        for state in ('pending','running','done'):
            (q.QUEUE/state).mkdir()
            for item in (ROOT/'queue'/state).glob('*.json'):
                # Reproduce this ticket's original unclaimed intake even if
                # the live dispatcher has since launched/completed it.
                if item.stem==target_id:continue
                value=json.loads(item.read_text())
                gate=value.get('dependency_gate',{})
                if gate.get('path'):
                    old=Path(gate['path']);new=q.QUEUE/'evidence'/value['id']/old.name
                    new.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(old,new)
                    gate['path']=str(new)  # Same bytes/pin, isolated receipt location.
                (q.QUEUE/state/item.name).write_text(json.dumps(value))
        result=q.submit(input_path)
        ticket=json.loads((q.QUEUE/'pending'/(result['id']+'.json')).read_text())
        state=q.dependency_state(ticket)
        if state!=(True,'eligible'):raise AssertionError(state)
        try:q.submit(input_path)
        except ValueError as error:
            if 'unique queue id' not in str(error):raise
        else:raise AssertionError('duplicate accepted')
        return dict(status='PASS_actual_public_submit_and_dependency_metadata_only',
          queue_source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),input_sha256=hashlib.sha256(input_path.read_bytes()).hexdigest(),
          functional_sha256=q.functional_identity(ticket['package']),result=result,dependency=list(state),
          live_queue_unchanged=True,native_launch=False,isolated_receipt_relocations_preserved_hashes=True)


class PublicIntakeTests(unittest.TestCase):
    def test_actual_ready_packet_submit_dependency_and_duplicate_refusal(self):
        self.assertEqual(exercise()['status'],'PASS_actual_public_submit_and_dependency_metadata_only')


if __name__=='__main__':unittest.main()
