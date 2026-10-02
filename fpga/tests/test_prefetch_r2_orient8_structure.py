"""Exact source delta and abstract selector equivalence; no HDL execution."""
import itertools
from pathlib import Path
import random
import unittest
from unittest.mock import patch

from reference import prefetch_r2_orient8_structure as s


class OrientationTileStructureTests(unittest.TestCase):
    root=Path(__file__).resolve().parents[1]

    def read(self,name):return (self.root/'rtl/kernel'/(name+'.sv')).read_text()

    def test_three_pinned_isolated_clones_and_supported_pattern(self):
        pins=s.validate_files(self.root)
        self.assertEqual(len(pins),3)
        for old,new in s.NAMES.items():
            self.assertEqual(s.sha(self.read(old)),s.ANCESTORS[old])
            self.assertEqual(self.read(new),s.expected(old,self.read(old)))
        pattern=self.read(s.PATTERN_NAME)
        self.assertEqual(s.sha(pattern),s.PATTERN_SHA)
        self.assertIn('(* preserve, dont_merge *) logic orientation_e;',pattern)

    def test_wrapper_core_have_only_identity_and_child_substitutions(self):
        for old in (s.HOST,'genefer_square_core27_stream_prefetch_r2_host_broadcast'):
            new=s.NAMES[old];child=s.ENGINE if old==s.HOST else s.HOST
            normalized=self.read(new).replace('module '+new+' #(','module '+old+' #(')
            normalized=normalized.replace(s.NAMES[child]+' #(',child+' #(')
            self.assertEqual(normalized,self.read(old))

    def test_same_edge_unconditional_capture_and_unchanged_tags(self):
        new=self.read(s.NAMES[s.ENGINE]);old=self.read(s.ENGINE)
        self.assertNotIn('orientation_d',new)
        self.assertEqual(new.count('(* preserve, dont_merge *) logic orientation_q;'),1)
        self.assertEqual(new.count('else orientation_q<=orientation;'),1)
        self.assertEqual(new.count('if(!rst_n) orientation_q<=0;'),1)
        for word in ('u','v'):
            self.assertEqual(new.count('assign '+word+'=orientation_tiles[lane/ORIENT_TILE_LANES].orientation_q ?'),1)
        for anchor in ('orientation_pipe<={orientation_pipe[5:0],orientation};',
                       'point_half_pipe<={point_half_pipe[5:0],point_half};',
                       'orientation_pipe<=0;point_half_pipe<=0;',
                       'bf_write_option[p]=(orientation_pipe[6]',
                       "cycles<=cycles+1;",'.profile_format',
                       'data_we[bank]=vector_load_we;data_re[bank]=!vector_load_we;'):
            self.assertEqual(new.count(anchor),old.count(anchor))

    def test_geometry_tile_coverage_and_logical_cost(self):
        for lanes in (1,2,4,8,16,32,64):
            tiles=(lanes+7)//8
            members=[[lane for lane in range(lanes) if lane//8==tile] for tile in range(tiles)]
            self.assertEqual(sorted(sum(members,[])),list(range(lanes)))
            self.assertTrue(all(1<=len(group)<=8 for group in members))
            self.assertEqual(len(s.control_trace(['edge1'],lanes)[0][1]),tiles)
        self.assertEqual(3*((64+7)//8-1),21)

    def test_exhaustive_bounded_transition_sequences(self):
        # Every five-event sequence after a known reset, including assertions
        # without a clock, held reset, release, bubbles and orientation toggles.
        checks=0
        for lanes in (1,2,4,8,16,32,64):
            for actions in itertools.product(('edge0','edge1','assert','release'),repeat=5):
                for original,copies in s.control_trace(('assert','release')+actions,lanes):
                    self.assertTrue(all(value==original for value in copies));checks+=1
        self.assertEqual(checks,50176)

    def test_abstract_u_v_equivalence_all_lane_patterns(self):
        rng=random.Random(0x0A8)
        for lanes in (1,2,4,8,16,32,64):
            kw=(2*lanes).bit_length()-1
            # Arbitrary full32 data is stronger for selector equivalence than
            # canonical residues; no new arithmetic-domain claim is implied.
            data=[rng.getrandbits(32) for _ in range(2*lanes)]
            for p in range(kw):
                for orientation in (0,1):
                    original,copies=s.control_trace(['assert','release','edge'+str(orientation)],lanes)[-1]
                    for lane in range(lanes):
                        lo=(lane&((1<<p)-1))|((lane>>p)<<(p+1));hi=lo|(1<<p)
                        expected=(data[hi],data[lo]) if original else (data[lo],data[hi])
                        actual=(data[hi],data[lo]) if copies[lane//8] else (data[lo],data[hi])
                        self.assertEqual(actual,expected)

    def test_wrong_one_cycle_replica_counterexample(self):
        actions=('assert','release','edge1','edge0')
        correct=s.control_trace(actions,64)
        delayed=s.control_trace(actions,64,wrong_one_cycle=True)
        self.assertEqual(correct[2],(1,(1,)*8))
        self.assertEqual(delayed[2],(1,(0,)*8))
        self.assertNotEqual(correct,delayed)
        self.assertEqual(correct[3],(0,(0,)*8))
        self.assertEqual(delayed[3],(0,(1,)*8))

    def test_unreviewed_latency_reset_mapping_and_pipe_mutants_rejected(self):
        name=s.NAMES[s.ENGINE];path=self.root/'rtl/kernel'/(name+'.sv');original=self.read(name)
        read=Path.read_text
        for old,new in (('orientation_q<=orientation;','orientation_q<=orientation_pipe[0];'),
                        ('if(!rst_n) orientation_q<=0;','if(!rst_n) orientation_q<=1;'),
                        ('else orientation_q<=orientation;','else if(issue_fire) orientation_q<=orientation;'),
                        ('lane/ORIENT_TILE_LANES','lane%ORIENT_TILE_LANES'),
                        ('(* preserve, dont_merge *)','(* preserve *)'),
                        ('orientation_pipe[5:0],orientation','orientation_pipe[5:0],point_half')):
            self.assertIn(old,original);mutant=original.replace(old,new)
            def supplied(p,*args,**kwargs):return mutant if p==path else read(p,*args,**kwargs)
            with self.subTest(anchor=old),patch.object(Path,'read_text',supplied),self.assertRaises(ValueError):
                s.validate_files(self.root)

    def test_changed_ancestor_and_ambiguous_anchor_rejected(self):
        with self.assertRaisesRegex(ValueError,'ancestor identity'):s.expected(s.ENGINE,self.read(s.ENGINE)+'\n')
        with self.assertRaisesRegex(ValueError,'ambiguous'):s.once('xx','x','y')


if __name__=='__main__':unittest.main()
