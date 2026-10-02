"""Separate deliberate fault controls for the S4 two-context model proposal."""
import argparse
import sys

from .s4_two_context_model_v1 import ModelError, small_reference, source_guard


def cross_talk_negative(n=32,p=8,epochs=4):
    # Establish real normal coefficient/canonical agreement BEFORE corruption.
    normal=small_reference(n,p,epochs)
    try:
        small_reference(n,p,epochs,alias_context_banks=True)
    except ModelError as error:
        if error.code!='S4_TWO_CROSS_TALK':raise
        return normal
    raise ModelError('S4_TWO_NEGATIVE_NOT_DETECTED')


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--n',type=int,choices=(32,256),default=32)
    parser.add_argument('--p',type=int,choices=(8,16),default=8)
    args=parser.parse_args(argv);source_guard();cross_talk_negative(args.n,args.p)
    sys.stderr.write(f'S4_TWO_CONTEXT_CROSS_TALK_NEGATIVE_REJECT n={args.n} p={args.p}\n')
    return 1


if __name__=='__main__':raise SystemExit(main())
