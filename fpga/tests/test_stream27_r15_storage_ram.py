import copy
import hashlib
import json
import itertools
from pathlib import Path
import unittest
from fpga.reference import stream27_r15_storage_ram_bind as b
from fpga.reference import stream27_r15_storage_ram_model as model

BASE = b.ROOT / 'results/throughput-20260929/trackS-c2-protected-field100-native-v1'
CAPTURES = (
    ('aw8-normal', 'dd8d9196a5ac79381b8e701d021d19a067dde4d319b15799b13f8d8f61441a00', 30),
    ('full-normal-v2', 'f5f0617d989b64bb965b612a0d0cb8b6074c1ecd4f85f01ed66f970dfbf521f2', 38))


def check_exact_field100_default_reverse(name, pin, width):
    raw = (BASE / name / 'production-bundle.json').read_bytes()
    assert hashlib.sha256(raw).hexdigest() == pin
    before = json.loads(raw)
    old = copy.deepcopy(before)
    disabled = b.bind(before, 0)
    assert disabled == before and disabled is not before and disabled['files'] is not before['files']
    after = b.bind(before, 1,crt_metadata_mlab=1,crt_r1_mlab=0,crt_d3_mlab=0,crt_x12_mlab=0)
    assert before == old
    meta = after['r15_storage_ram']
    assert meta['word_width'] == width and meta['latency_delta'] == 0
    assert len(after['files']) == 59
    changed = set(after['files']) - set(before['files'])
    changed |= {n for n in before['files'] if after['files'][n] != before['files'][n]}
    assert changed == set(meta['changed_members'])
    assert b.unbind_arithmetic(after['files'][meta['original_arithmetic']]) == before['files'][meta['original_arithmetic']]
    assert after['parameters'] == before['parameters']
    assert after['two_context_schedule'] == before['two_context_schedule']
    assert after['files'][b.P2] == before['files'][b.P2]
    assert meta['declared_ff_upper_bound_only'] == (411 if width == 30 else 523)
    assert not meta['mapped_saving_measured'] and not meta['term_payload_cut_enabled']


def test_unconditional_address_and_reset_equivalence():
    rows = model.run()
    assert all(r['collisions'] == 0 and r['latency_delta'] == 0 for r in rows)


class StorageRAMTests(unittest.TestCase):
    def test_exact_aw8(self):
        check_exact_field100_default_reverse(*CAPTURES[0])

    def test_exact_full(self):
        check_exact_field100_default_reverse(*CAPTURES[1])

    def test_model(self):
        test_unconditional_address_and_reset_equivalence()

    def test_numeric_all_individual_switches_and_reverse(self):
        for name,pin,_ in CAPTURES:
            before=json.loads((BASE/name/'production-bundle.json').read_text())
            for r1,d3,x12 in itertools.product((0,1),repeat=3):
                if not (r1 or d3 or x12):
                    continue
                after=b.bind(before,1,crt_r1_mlab=r1,crt_d3_mlab=d3,crt_x12_mlab=x12)
                assert set(after['r15_storage_ram']['changed_members']) == {b.CRT,b.NUMERIC_LEAF}
                assert b.unbind_crt(after['files'][b.CRT],r1=r1,d3=d3,x12=x12)==before['files'][b.CRT]
                assert after['geometry']==before['geometry'] and after['parameters']==before['parameters']
                root=after['r15_storage_ram']['original_arithmetic']
                assert after['files'][root]==before['files'][root]
                assert 'valid_pipe' in after['files'][b.CRT] and "if(!rst_n)begin valid_pipe<=0;out_valid<=0;coefficient<=0;end" in after['files'][b.CRT]

    def test_numeric_data_before_and_after_edge(self):
        result=model.numeric_run()
        assert all(r['raw_head_comparisons']>r['edges'] and r['eligible_CRT_preedge_samples']>0 and
                   r['latency_delta']==0 and r['collisions']==0 for r in result)

    def test_source_guard(self):
        before = json.loads((BASE / 'aw8-normal/production-bundle.json').read_text())
        name = next(n for n,t in before['files'].items() if b.DECL in t)
        with self.assertRaisesRegex(ValueError, 'ALL_CONSUMERS'):
            b.bind_arithmetic(before['files'][name] + '\nwire unexpected=crt_tag[15][0];', 1)
        with self.assertRaisesRegex(ValueError, 'BINARY_SWITCH'):
            b.bind(before, 2)


if __name__ == '__main__':
    unittest.main()
