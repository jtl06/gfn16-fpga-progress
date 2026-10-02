"""Internal additive successor for the reviewed original alpha; no dispatch."""
import importlib.util
from pathlib import Path

path = Path(__file__).with_name('prepare_public_runner_alpha_smoke_v1.py')
spec = importlib.util.spec_from_file_location('_alpha_preparation_v1', path)
preparation = importlib.util.module_from_spec(spec); spec.loader.exec_module(preparation)
preparation.OUT = preparation.ROOT/'fpga/results/throughput-20260929/public-runner-alpha-aethia-stage-v2'
preparation.NATIVE = '/home/jtl/gfn-fpga-lab/agent-work/fpga-experiment-runner-alpha-v2'

if __name__ == '__main__': preparation.main()
