"""Full64 coarse range contracts; NOT DATA framing/vendor/core qualification."""
LIMIT=(1<<64)-1
WRITE_RANGES=((0,0x400000),(0x1000000,0x1002000),(0x1002000,0x1004000))
READ_RANGES=((0,0x800000),)


def allowed(address,count,write):
    if type(address) is not int or type(count) is not int or not 0<=address<=LIMIT or not 1<=count<32:
        return False
    end=address+32*count
    return any(lo<=address<hi and end<=hi for lo,hi in (WRITE_RANGES if write else READ_RANGES))


class Burst:
    """First accepted address/count authority; later ones are don't-care."""
    def __init__(self):self.left=0;self.base=None;self.count=0
    def accept(self,address,count,write=True):
        if not self.left:
            if not allowed(address,count,write):raise ValueError('R15_DMA_APERTURE')
            self.base,self.count=address,count;self.left=count
        self.left-=1
        return self.base,self.count


CONTRACT={
 'address':'64-bit byte SYMBOLS (8bits); before any Qsys address narrowing',
 'write_ranges':WRITE_RANGES,'read_ranges':READ_RANGES,
 'alignment':'no new alignment or BE restriction; application/vendor slaves own those checks',
 'burst':'wholefirstbeatspan checked; falseconstantBurstBehavior continuationaddress/count ignored',
 'fault':'sticky terminal; one external_fault_valid/ready token; no new host admission/fwd afterfault',
 'tail':'previouslyadmitted/offered downstreamrequests remainhelduntilaccepted/reset; no rollback/flush',
 'reads':'downstream-accepted response credits drained zero; fault-origin invalid reads locally zero; prior delivered records cannot be revoked',
 'unaccepted_tail':'previously offered downstream read that remains stalled after fault requires reset; no eventual completion promise or fake credit',
 'storage':'onewritebeat+onereadrequest holdingregister; nopayloadsizedRAM',
 'scope':'AUTHOR only; no physical/vendorIP/wholecore/hostGL/nonauthorpromotion proof',
}
