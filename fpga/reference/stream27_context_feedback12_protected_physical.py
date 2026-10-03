"""Protected R12 baseline only; frozen source and existing lean project untouched."""
import argparse
import json
from pathlib import Path
from .stream27_context_feedback12_physical import prepare as emit


def prepare(output,role,gate):
    return emit(output,role,gate,lean_production=0)


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--output',required=True,type=Path)
    p.add_argument('--native-role',required=True,type=Path)
    p.add_argument('--native-gate',required=True)
    a=p.parse_args()
    print(json.dumps(prepare(a.output,a.native_role,a.native_gate),indent=2))
