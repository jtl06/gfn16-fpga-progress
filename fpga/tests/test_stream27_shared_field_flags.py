from fpga.reference import stream27_shared_field_flags as flags
from fpga.reference import stream27_shared_field_v5 as parent
import unittest


def test_zero_is_complete_parent_bundle():
    assert flags.prepare(256, 16, 0) == parent.prepare(256, 16, 0)
    before = parent.prepare(256, 16, 0)
    after = flags.bind(before, comm_stage_shared_mlab=1)
    assert 'COMM_STAGE_SHARED_MLAB' not in before['parameters']
    assert after['parameters']['COMM_STAGE_SHARED_MLAB'] == 1


def test_temporal_only_and_preserved_calendar():
    for p in (8, 16):
        for n in (32, 256):
            before = parent.prepare(n, p, 0)
            after = flags.prepare(n, p, 0, comm_stage_shared_mlab=1)
            assert before['geometry'] == after['geometry']
            changed = {name for name, text in before['files'].items()
                       if after['files'].get(name) != text}
            assert changed == {before['top']+'.sv',
                f'genefer_stream28_merged_ct_aw{n.bit_length()-1}_p{p}_f0_v1.sv',
                f'genefer_stream28_merged_gs_aw{n.bit_length()-1}_p{p}_f0_v1.sv'}
            assert after['shared_comm_temporal_stages'] == 2*(n.bit_length()-1-(p.bit_length()-1))
            for name, text in after['files'].items():
                if '_shared_comm_mlab_v1.sv' in name and 'merged_' in name:
                    assert 'shuffle_alignment_bad' not in text
                    assert text.count('shared_shuffle (') == n.bit_length()-1-(p.bit_length()-1)
                    assert 'cadence_bad' in text and 'slot_pipe[5]' in text
            root = after['files'][after['top']+'.sv']
            assert 'COMM_STAGE_SHARED_MLAB=1' in root
            assert 'COMM_STAGE_SHARED_MLAB!=1' in root


def test_composed_flags_keep_calendar_and_canonical_boundaries():
    for n in (32,256):
        before=parent.prepare(n,16,0,corr_serial_bfs=2)
        after=flags.prepare(n,16,0,corr_serial_bfs=2,comm_stage_shared_mlab=1,mont_factored=1)
        assert after['geometry']==before['geometry']
        assert after['parameters']['CORR_SERIAL_BFS']==2
        assert after['parameters']['COMM_STAGE_SHARED_MLAB']==1
        assert after['parameters']['MONT_FACTORED']==1
        assert 'genefer_stream27_montgomery_factored_v1.sv' in after['files']
        assert 'genefer_montgomery_mul27_sparse_pipe.sv' not in after['files']
        assert 'canonical_u' in next(text for name,text in after['files'].items() if 'merged_gs_' in name)
        assert after['montgomery_factored']['calendar_changed'] is False


class SourceTests(unittest.TestCase):
    def test_zero(self):test_zero_is_complete_parent_bundle()
    def test_temporal(self):test_temporal_only_and_preserved_calendar()
    def test_composition(self):test_composed_flags_keep_calendar_and_canonical_boundaries()


if __name__=='__main__':unittest.main()
