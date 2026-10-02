from dataclasses import replace
import unittest
from fpga.reference.stream27_field_square_oracle import (
    PRIMES, SquareImage, coefficients, image_cases, physical_rows, residues,
)


class DirectFieldSquareOracle(unittest.TestCase):
    def test_integer_evaluation_of_signed_negacyclic_coefficients(self):
        # Whole-integer squaring provides an oracle independent of convolution
        # indexing, NTT roots, Montgomery constants and physical lane order.
        for _,image in image_cases():
            effective=image.effective();actual=coefficients(image)
            modulus=pow(image.base,image.n)+1
            value=sum(x*pow(image.base,i) for i,x in enumerate(effective))%modulus
            represented=sum(x*pow(image.base,i) for i,x in enumerate(actual))%modulus
            self.assertEqual(represented,value*value%modulus)
            for field,prime in enumerate(PRIMES):
                self.assertEqual(residues(image,field),physical_rows(tuple(x%prime for x in actual)))

    def test_known_minus_one_and_negative_wrap(self):
        image=SquareImage(172,0,(0,)*32,(-1,)+(0,)*7,(0,)*8)
        self.assertEqual(coefficients(image),(1,)+(0,)*31)
        image=replace(image,digits=(0,)*31+(1,),c0=(0,)*8)
        self.assertEqual(coefficients(image),(0,)*30+(-1,0))

    def test_both_correction_arrays_are_observable(self):
        image=dict(image_cases())['b1000000000-signed-boundaries']
        expected=residues(image)
        self.assertNotEqual(expected,residues(replace(image,c0=(0,)*8)))
        self.assertNotEqual(expected,residues(replace(image,c1=(0,)*8)))
        R=(1<<32)%PRIMES[0]
        wrong_domain=tuple(tuple(x*pow(R,-1,PRIMES[0])%PRIMES[0] for x in row) for row in expected)
        self.assertNotEqual(expected,wrong_domain)

    def test_reject_out_of_profile_or_local_numeric_scope(self):
        image=image_cases()[0][1]
        for changed,message in ((replace(image,base=171),'SUPPORTED_BASE'),
            (replace(image,digits=(-1,)+(0,)*31),'DIGIT_RANGE'),
            (replace(image,c0=(172,)+(0,)*7),'C0_RANGE'),
            (replace(image,c1=(257,)+(0,)*7),'C1_RANGE'),
            (replace(image,digits=(0,)*65536),'LOCAL_N32_TO256')):
            with self.assertRaisesRegex(ValueError,message):changed.validate()


if __name__=='__main__':unittest.main()
