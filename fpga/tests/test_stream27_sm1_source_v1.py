from collections import deque
import random
import unittest
from fpga.reference.stream27_sm1_source_v1 import verify,pilot_counts


class SM1SourceTests(unittest.TestCase):
    def test_exact_commutator_delta(self):self.assertEqual(verify()['fault_latency_delta'],0)

    def test_queue_vs_ring_lookahead(self):
        rng=random.Random(731)
        for depth in (1,2,4,8,16,32,64):
            memory=[None]*depth;pointer=filled=0;prefetched=None;queue=deque()
            for edge in range(2048):
                reset=edge in (0,7,123,999);advance=not reset and rng.randrange(4)!=0;value=rng.getrandbits(38)
                if reset:pointer=filled=0;queue.clear()
                elif advance:
                    if depth==1:prefetched=value
                    else:prefetched=memory[(pointer+1)%depth]
                    memory[pointer]=value;pointer=(pointer+1)%depth;filled=min(depth,filled+1)
                    queue.append(value)
                    if len(queue)>depth:queue.popleft()
                self.assertEqual(prefetched if filled==depth else 0,queue[0] if len(queue)==depth else 0)

    def test_pilot_bounds(self):
        r=pilot_counts();self.assertEqual(r['resets'],5);self.assertEqual(r['advances']+r['holds']+r['resets'],4096)


if __name__=='__main__':unittest.main()
