"""Port-cycle proof for ROM-output / butterfly-weight register co-retiming.

Old: accepted row updates ROM prefetch and BF pre_w together. New: the same
edge updates ROM prefetch and its second output register; FIRST is selected
after that register. The multiplier samples the registered weight next edge.
Only accepted/valid weight tokens are compared across reset; public butterfly
valid/result/reset/hold logic is not changed by this contract.
"""


class WeightPair:
    def __init__(self, words, first, row_positions, frame_rows):
        self.words = tuple(words)
        self.first = first
        self.positions = tuple(row_positions)
        self.frame_rows = frame_rows
        assert frame_rows >= 2 and frame_rows & (frame_rows - 1) == 0
        assert len(words) == 1 << len(self.positions)
        assert len(set(self.positions)) == len(self.positions)
        assert all(0 <= bit < frame_rows.bit_length() - 1 for bit in self.positions)
        self.row = 0
        self.prefetch = None
        self.output = None
        self.first_q = False
        self.old_pre_w = 0
        self.valid_q = False
        self.checked_products = 0

    def edge(self, *, valid=False, first=False, rst_n=True):
        selected = self.first if self.first_q else self.output
        if not rst_n:
            self.row = 0
            self.first_q = False
            self.old_pre_w = 0
            self.valid_q = False
            # Memory, old prefetch and new memory-output payload retain.
            return None
        product_weight = None
        if self.valid_q:
            assert selected == self.old_pre_w
            product_weight = selected
            self.checked_products += 1
        if valid:
            following = 1 if first else (self.row + 1) % self.frame_rows
            address = sum(((following >> bit) & 1) << index
                          for index, bit in enumerate(self.positions))
            old_current = self.first if first else self.prefetch
            self.old_pre_w = old_current
            self.output = self.prefetch
            self.first_q = first
            self.prefetch = self.words[address]
            self.row = following
        self.valid_q = valid
        return product_weight


def fields_with_weight_register():
    return {'unchanged': ['pre_valid', 'pre_v', 'prefix_pipe', 'gs_pipe', 'tag_pipe',
                          'Montgomery_E3', 'out_valid', 'public_y0_y1_tag',
                          'reset_and_registered_fault_authority'],
            'co_retimed': 'BF pre_w27 -> shared packed root ROM output stage',
            'first_row': 'post-register FIRST mux with accepted frame_start flag',
            'hold': 'ROM address/output clock enable both use the exact BF/root accept',
            'total_butterfly_edges': 5, 'II': 1,
            'excluded': ['term_roots', 'final_GS_pair', 'whole_fit', 'area_credit']}
