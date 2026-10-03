# SPDX-License-Identifier: Apache-2.0
"""Application-relative request planning; no BAR, DMA, or hardware execution.

Consumes the PCIe owner's authoritative codecs. Snapshot must be one fenced
core acknowledgement, not independently polled epoch/generation registers.
COMMIT publishes raw load authority only; retained START performs setup.
"""
from dataclasses import dataclass

from fpga.reference.stream27_r15_host_mmio_v1 import (header, register_writes,
    commit_writes, REG, CMD_BEGIN, CMD_CANCEL, CMD_START)
from fpga.reference.stream27_r15_host_link_model_v1 import Word, encode_word
from .r15_arithmetic import need
from .r15_transport import cold_words


@dataclass(frozen=True)
class CoreSnapshot:
    session: int
    context: int
    next_epoch: int
    prospective_generation: int
    fenced_acknowledgement: bool


class TransactionPlan:
    def __init__(self, n, base, count, mode, double_mask, snapshot, *, enabled=False):
        need(enabled is True, 'LINK_ADAPTER_OFF')
        need(type(snapshot) is CoreSnapshot and snapshot.fenced_acknowledgement is True and
             type(snapshot.session) is int and 0 <= snapshot.session < 1 << 32,
             'COHERENT_CORE_SNAPSHOT')
        need(type(snapshot.prospective_generation) is int and
             1 <= snapshot.prospective_generation <= 256, 'PROSPECTIVE_GENERATION')
        self.snapshot=snapshot
        # NEXT_GENERATION is already old+1; never increment it again.
        self.header=header(n,snapshot.context,base,count,mode,double_mask,
            core_next_epoch=snapshot.next_epoch,
            core_job_generation=snapshot.prospective_generation-1)

    def begin_writes(self):
        return register_writes(self.header,session=self.snapshot.session)+((REG['COMMAND'],CMD_BEGIN),)

    def data_records(self, lease, digits, c0, c1):
        need(type(lease) is int and 0 <= lease < 1 << 32,'LEASE32')
        words=cold_words(self.header.n,self.header.base,digits,c0,c1)
        for index,value in enumerate(words):
            yield encode_word(Word(self.snapshot.session,lease,self.header.context,
                                   self.header.owner,index,value))

    def commit_plan(self, lease, *, accepted, applied, coherent_idle_ack):
        need(coherent_idle_ack is True and type(accepted) is type(applied) is int and
             accepted == applied == self.header.n+32,'DESTINATION_ACK_COMPLETE')
        return commit_writes(self.snapshot.session,lease)

    def start_plan(self, *, committed_header, context_still_idle):
        need(committed_header==self.header and context_still_idle is True,'START_EXACT_HEADER')
        # Original START/PROFILE validates arithmetic setup. This request is
        # not evidence that its response/setup or a hardware launch succeeded.
        return ((REG['START_MASK'],1 << self.header.context),(REG['COMMAND'],CMD_START))

    def cancel_plan(self, lease):
        need(type(lease) is int and 0 <= lease < 1 << 32,'LEASE32')
        return ((REG['TOKEN_SESSION'],self.snapshot.session),(REG['TOKEN_LEASE'],lease),
                (REG['COMMAND'],CMD_CANCEL))
