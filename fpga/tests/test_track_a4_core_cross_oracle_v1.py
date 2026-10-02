"""Independent serial/block arithmetic replay of whole-integer command corpus.

This is supplemental evidence, not a mutation of the frozen native ticket.
Controller uses quadratic signed convolution and block carry, not integer square.
"""
import unittest
from fpga.reference.track_a4_core_vectors_v1 import corpus
from fpga.reference.track_a4_control_model_v1 import Controller


class WholeCoreCrossOracleTests(unittest.TestCase):
    def test_all_commands_against_block_carry_controller(self):
        names={0:"RELOAD_BEGIN",1:"LOAD_WORD",2:"READ",3:"WRITE",4:"SET_BASE",5:"SQUARE"}
        for aw in (5,8):
            text,report=corpus(aw)
            model=Controller(1<<aw)
            checked=0
            for index,line in enumerate(text.splitlines()[1:]):
                op,address,word,base,double,expected,valid,prefilled,cold,load=map(int,line.split())
                signed=word-(1<<32) if word&(1<<31) else word
                self.assertTrue(model.request(names[op],address=address,word=signed,base=base,double=double))
                response=model.finish()
                self.assertIsNone(response.error,(aw,index,response))
                self.assertEqual((response.word or 0)&0xffffffff,expected,(aw,index))
                self.assertEqual(model.image is not None and model.state=="ready",bool(valid),(aw,index))
                self.assertEqual(model.cache_valid,bool(prefilled),(aw,index))
                checked+=1
            self.assertEqual(checked,report["commands"])


if __name__ == "__main__":
    unittest.main()
