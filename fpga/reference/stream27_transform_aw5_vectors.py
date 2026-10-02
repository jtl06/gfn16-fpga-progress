"""Tiny P8/C1/P1 transform gate preparation; no native/HDL dispatch here.

Expected arithmetic comes directly from polynomial evaluation, independent of
the emitted stage/root compiler. Event calendars assert every physical row,
frame start, and terminal commit edge. No complete-field qualification claim.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from .stream27_field_compile import compile_transform
from .stream_ntt_model import bit_reverse


N = 32
P = 104857601
T = 4
FIRST_OUTPUT = 34  # 5 BFs*(k+5,next edge) + (L1+1)+(L2+1), minus terminal edge


def polynomial_oracle(words, inverse=False):
    """Return physical rows using direct sums, with unnormalized inverse."""
    omega = pow(3, (P - 1) // N, P)
    if inverse:
        # Input word position is the bit-reversed spectral slot.
        output = [sum(words[slot] * pow(omega, (-bit_reverse(slot, 5) * i) % N, P)
                      for slot in range(N)) % P for i in range(N)]
        return [tuple(output[bit_reverse(lane, 3) * T + row] for lane in range(8))
                for row in range(T)]
    output = [sum(words[i] * pow(omega, i * j % N, P) for i in range(N)) % P
              for j in range(N)]
    return [tuple(output[bit_reverse(row * 8 + lane, 5)] for lane in range(8))
            for row in range(T)]


def input_rows(words, inverse=False):
    return [tuple(words[row * 8 + lane if inverse else bit_reverse(lane, 3) * T + row]
                  for lane in range(8)) for row in range(T)]


def pattern(serial):
    choices = ([0] * N, [1] + [0] * (N - 1), [P - 1] * N,
               [(7919 * i + 104729 * serial + 17) % P for i in range(N)])
    return tuple(choices[serial % len(choices)])


def probe_source():
    """Integer INVERSE selects one complete transform, not two coupled fields."""
    return '''// Source-only tiny transform probe. Every canceled physical row still moves.
module genefer_stream27_transform_aw5_probe #(parameter int unsigned INVERSE=0) (
  input logic clk,rst_n,in_slot_valid,frame_start,context_enabled,
  input logic [7:0] generation_in,live_generation,
  input logic [215:0] data_in,
  output logic out_slot_valid,out_frame_start,out_eligible,out_error,fault_pending,
  output logic [7:0] generation_out,
  output logic [215:0] data_out,
  output logic commit_valid,commit_frame_start,
  output logic [7:0] commit_generation,
  output logic [215:0] commit_data);
  logic quarantine;
  generate if(INVERSE==0) begin : forward
    genefer_stream27_dif_aw5_p8_f0 #(.GEN_W(8)) transform (
      .clk,.rst_n,.in_slot_valid,.frame_start,.quarantine,.context_enabled,
      .generation_in,.live_generation,.data_in,.out_slot_valid,.out_frame_start,
      .out_eligible,.out_error,.fault_pending,.generation_out,.data_out);
  end else begin : inverse
    genefer_stream27_dit_aw5_p8_f0 #(.GEN_W(8)) transform (
      .clk,.rst_n,.in_slot_valid,.frame_start,.quarantine,.context_enabled,
      .generation_in,.live_generation,.data_in,.out_slot_valid,.out_frame_start,
      .out_eligible,.out_error,.fault_pending,.generation_out,.data_out);
  end endgenerate
  always_ff @(posedge clk or negedge rst_n) begin
    if(!rst_n) begin
      quarantine<=0; commit_valid<=0; commit_frame_start<=0;
    end else begin
      if(out_error) quarantine<=1;
      commit_valid<=0; commit_frame_start<=0;
      if(out_slot_valid && context_enabled && generation_out==live_generation &&
         !quarantine && !out_error && !fault_pending) begin
        commit_valid<=1; commit_frame_start<=out_frame_start;
        commit_generation<=generation_out; commit_data<=data_out;
      end
    end
  end
  // synthesis translate_off
  initial if(INVERSE>1) $fatal(1,"TRANSFORM_DIRECTION");
  // synthesis translate_on
endmodule
'''


class Calendar:
    def __init__(self, inverse):
        self.inverse = inverse
        self.events = []
        self.input_calendar = {}
        self.output_calendar = {}

    def frame(self, origin, generation, serial):
        words = pattern(serial)
        for row, values in enumerate(input_rows(words, self.inverse)):
            self.input_calendar[origin + row] = (True, row == 0, generation, values)
        for row, values in enumerate(polynomial_oracle(words, self.inverse)):
            self.output_calendar[origin + FIRST_OUTPUT + row] = (row == 0, generation, values)

    def segment(self, origins, *, cancel=None, disable=None, reset_age=None,
                malformed_age=None, malformed_kind=None):
        """Frames are complete, except the explicitly interrupted segment.

        Every case starts from reset. Midstream reset abandons old input and
        output calendars and launches a new coherent frame on the next edge.
        Generation numbers only advance; no live generation is recycled.
        """
        self.input_calendar = {}
        self.output_calendar = {}
        self.events.append((0, 0, 0, 1, 0, 0, (0,) * 8, -1, None, False, None))
        for serial, origin in enumerate(origins):
            self.frame(origin, 0, serial + 3)
        finish = max(origins) + T + FIRST_OUTPUT + 3
        if reset_age is not None:
            self.input_calendar = {tick: value for tick, value in self.input_calendar.items() if tick < reset_age}
            self.output_calendar = {tick: value for tick, value in self.output_calendar.items() if tick < reset_age}
            self.frame(reset_age + 1, 2, 91)
            finish = max(finish, reset_age + 1 + T + FIRST_OUTPUT + 3)
        remaining = 0
        owner = 0
        sticky = False
        for tick in range(finish):
            reset = tick == reset_age
            slot, start, gen, data = self.input_calendar.get(tick, (False, False, 0, (0,) * 8))
            if tick == malformed_age:
                if malformed_kind == 'hole':
                    slot, start = False, False
                elif malformed_kind == 'restart':
                    start = True
                elif malformed_kind == 'generation':
                    gen = 1
                elif malformed_kind == 'no-start':
                    start = False
                elif malformed_kind == 'empty-start':
                    slot, start = False, True
                else:
                    raise ValueError('TRANSFORM_BAD_FAULT_SPEC')
            live = 2 if reset_age is not None and tick > reset_age else int(cancel is not None and tick >= cancel)
            enabled = not(disable is not None and tick >= disable)
            bad = ((start and (not slot or remaining != 0)) or
                   (slot and not start and remaining == 0) or
                   (not slot and remaining != 0) or
                   (slot and not start and remaining != 0 and gen != owner))
            pending = sticky or bad
            if reset:
                sticky = False
                remaining = 0
                pending = -1
            else:
                sticky |= bad
                if slot and not sticky:
                    if start:
                        remaining, owner = T - 1, gen
                    else:
                        remaining -= 1
            physical = self.output_calendar.get(tick) if not(sticky or reset) else None
            previous = self.output_calendar.get(tick - 1)
            # A reset at the previous edge already erased that pending output.
            if reset_age is not None and tick - 1 == reset_age:
                previous = None
            commit = previous if previous and not(reset or pending) and enabled and previous[1] == live else None
            self.events.append((not reset, slot, start, enabled, gen, live, data,
                                pending, physical, sticky, commit))
        return self

    def text(self):
        lines = [f'TRAW5 {int(self.inverse)} {len(self.events)}']
        for reset_n, slot, start, enabled, gen, live, data, pending, physical, error, commit in self.events:
            out_flags = (bool(physical), bool(physical and physical[0]),
                         bool(physical and enabled and physical[1] == live), error)
            out_gen = physical[1] if physical else -1
            out_words = physical[2] if physical else (-1,) * 8
            commit_flags = (bool(commit), bool(commit and commit[0]), commit[1] if commit else -1)
            commit_words = commit[2] if commit else (-1,) * 8
            numbers = [reset_n, slot, start, enabled, gen, live, *data, pending,
                       *out_flags, out_gen, *out_words, *commit_flags, *commit_words]
            if len(numbers) != 39:
                raise AssertionError('TRANSFORM_VECTOR_WIDTH')
            lines.append(' '.join(str(int(number)) for number in numbers))
        return '\n'.join(lines) + '\n'


def vectors(inverse=False):
    corpus = Calendar(inverse)
    for gap in (0, 1, 3, 138):
        corpus.segment((0, T + gap, 2 * (T + gap), 3 * (T + gap)))
    # Input, each shuffle phase, first/last output, and output-to-commit race.
    for cancel in (0, 1, T - 1, T, 12, FIRST_OUTPUT - 1, FIRST_OUTPUT, FIRST_OUTPUT + T - 1, FIRST_OUTPUT + T):
        corpus.segment((0, T), cancel=cancel)
    for disabled in (FIRST_OUTPUT, FIRST_OUTPUT + 1, FIRST_OUTPUT + T):
        corpus.segment((0, T), disable=disabled)
    for age in range(FIRST_OUTPUT + 2 * T + 2):
        corpus.segment((0, T), reset_age=age)
    for kind, age in (('no-start', 0), ('empty-start', 0), ('hole', 1), ('restart', 1), ('generation', 1)):
        corpus.segment((0,), malformed_age=age, malformed_kind=kind)
    return corpus.text()


def prepare():
    files = {'genefer_stream27_transform_aw5_probe.sv': probe_source()}
    emitted = []
    vector_artifacts = {}
    for inverse in (False, True):
        result = compile_transform(32, inverse=inverse)
        files[result['module'] + '.sv'] = result['source']
        files.update(result['rom_files'])
        vector_text = vectors(inverse)
        files[f'transform-aw5-{int(inverse)}.txt'] = vector_text
        rows = [list(map(int, line.split())) for line in vector_text.splitlines()[1:]]
        metadata = dict(inverse=int(inverse), events=len(rows), slots=sum(row[15] for row in rows),
                        commits=sum(row[28] for row in rows), errors=sum(row[18] for row in rows),
                        resets=sum(not row[0] for row in rows), before_checks=2 * len(rows), edge_checks=len(rows))
        vector_artifacts[int(inverse)] = (vector_text, metadata)
        emitted.append(dict(inverse=int(inverse), module=result['module'],
                            ROM_words=sum(len(content.splitlines()) for content in result['rom_files'].values())))
    root = Path(__file__).resolve().parents[1]
    source_paths = ['reference/stream27_transform_aw5_vectors.py', 'reference/stream27_field_compile.py',
                    'reference/stream27_field_plan.py', 'rtl/kernel/genefer_stream27_root_rom_prefetch.sv',
                    'rtl/kernel/genefer_stream27_mdc_commutator_slots_v2.sv',
                    'rtl/kernel/genefer_stream27_mdc_commutator_sync.sv',
                    'rtl/kernel/genefer_ntt_banked27_engine.sv',
                    'rtl/kernel/genefer_montgomery_mul27_sparse_pipe.sv']
    return dict(files=files, source_dependencies=source_paths, vectors=vector_artifacts,
                generated_sha256={path: hashlib.sha256(content.encode()).hexdigest()
                for path, content in files.items()},
                source_sha256={path: hashlib.sha256((root / path).read_bytes()).hexdigest() for path in source_paths},
                top='genefer_stream27_transform_aw5_probe', directions=emitted,
                gate_class='tiny_complete_transform_only_not_complete_field',
                contexts=1, payload_bits=1, frame_rows=T, first_output=FIRST_OUTPUT,
                native_run_performed=False, full_N_numeric_NTT_run_performed=False)
