"""Finite aethia-only host conversion measurement; no HDL/NTT/PRP work.

Prepared for the existing light finite queue, never a self-dispatching runner.
This measures synthetic full-size conversion/finalization, not B RTL equivalence.
"""
import argparse
import hashlib
import json
from pathlib import Path
import socket
import statistics
import sys
import time

from . import stream27_host_offload_model_v1 as model

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ['reference/stream27_host_offload_benchmark_v1.py',
           'reference/stream27_host_offload_model_v1.py',
           'reference/stream27_signed_boundary_oracle.py',
           'reference/stream27_blockcarry_param_model_v1.py',
           'reference/stream27_canonical_image_model_v1.py',
           'reference/stream_ntt_blockwrap2_proposal.py',
           'reference/stream_ntt_model.py']


def summarize(values):
    return dict(samples_seconds=values, minimum_seconds=min(values),
                median_seconds=statistics.median(values), maximum_seconds=max(values))


def run(*, repetitions=3):
    model.need(sys.platform.startswith('linux') and socket.gethostname().split('.')[0] == 'aethia',
               'BENCHMARK_AETHIA_ONLY')
    model.need(type(repetitions) is int and 1 <= repetitions <= 5, 'FINITE_REPETITIONS1_TO5')
    n, p, base, generation = 65536, 16, 604832956, 7
    # Synthetic ordinary dense/raw images. No claim these are a captured DUT
    # checkpoint, PRP, or the same-base production sample's complete chain.
    digits = tuple((j * 104729 + 17) % base for j in range(n))
    c0, c1 = tuple((j - 8) * 997 for j in range(p)), tuple((j - 8) * 991 for j in range(p))
    raw_words = [digits[lane * (n // p) + row] for row in range(n // p) for lane in range(p)]
    raw_words += list(c0) + list(c1)
    # Synthetic raw transport creation is deliberately outside conversion
    # timings. Decode/transpose of the received words is measured below.
    raw_final = b''.join((word & 0xffffffff).to_bytes(4, 'little') for word in raw_words)
    profile_wall, cold_wall, final_wall = [], [], []
    profile_cpu, cold_cpu, final_cpu = [], [], []
    deadline = time.monotonic() + 60
    first_digest = None
    for _ in range(repetitions):
        model.need(time.monotonic() < deadline, 'BENCHMARK_FINITE_DEADLINE')
        wall, cpu = time.perf_counter(), time.process_time()
        setup = model.profile(n, p, base, generation)
        profile_wall.append(time.perf_counter() - wall); profile_cpu.append(time.process_time() - cpu)
        wall, cpu = time.perf_counter(), time.process_time()
        packet = model.prepare_cold(digits, c0, c1, setup, context=1, epoch=65535)
        cold_bytes = model.cold_payload_bytes(packet)
        model.need(len(cold_bytes) == 4 * (3 * n + 6 * p), 'BENCHMARK_INPUT_BYTES')
        cold_wall.append(time.perf_counter() - wall); cold_cpu.append(time.process_time() - cpu)
        # The full56 owner is transport metadata, not an invented raw dump.
        owner = (31 << 24) | (65535 << 8) | generation
        wall, cpu = time.perf_counter(), time.process_time()
        final_packet = model.decode_final_payload(raw_final, setup, context=1, owner=owner)
        result = model.finalize(final_packet, expected_context=1, expected_owner=owner)
        final_bytes = b''.join((word & 0xffffffff).to_bytes(4, 'little') for word in result.digits)
        final_wall.append(time.perf_counter() - wall); final_cpu.append(time.process_time() - cpu)
        digest = hashlib.sha256(final_bytes).hexdigest()
        model.need(first_digest is None or first_digest == digest, 'REPEATED_OUTPUT_BYTES')
        first_digest = digest
    model.need(time.monotonic() <= deadline, 'BENCHMARK_FINITE_DEADLINE')
    import resource
    return dict(status='PASS_host_conversion_measurement_only', host=socket.gethostname(),
        platform=sys.platform, python=sys.version, n=n, p=p, base=base, repetitions=repetitions,
        input_residue_words=3 * n, final_digit_words=n, final_boundary_words=2 * p,
        profile_wall=summarize(profile_wall), cold_conversion_wall=summarize(cold_wall),
        finalization_wall=summarize(final_wall), profile_cpu=summarize(profile_cpu),
        cold_conversion_cpu=summarize(cold_cpu), finalization_cpu=summarize(final_cpu),
        max_self_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        output_sha256=first_digest,
        sources={name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in SOURCES},
        measured_backend_seconds=None, transport_seconds=None, prp_wall_seconds=None,
        native_core_equivalence=False, promotion_allowed=False,
        scope='Synthetic host-only full-size conversion/validation/packing and raw decode/transpose/finalization/packing; no native B core, PRP or chain proof.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repetitions', type=int, choices=range(1, 6), default=3)
    args = parser.parse_args()
    print(json.dumps(run(repetitions=args.repetitions), sort_keys=True))
