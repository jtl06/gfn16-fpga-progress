"""Independent event/port proof for proposed final-post NTT to CRT forwarding.

No RTL is changed. A cycle-model result is not a measured integration result.
Run only on aethia; output must be a new path.
"""
import argparse
from collections import deque
import hashlib
import json
from pathlib import Path
import random
import socket


def bank(address, aw, kw):
    result=0
    for bit in range(aw): result ^= ((address>>bit)&1) << (bit%kw)
    return result


def schedule(aw, lanes, delay, mode, seed=0):
    n=1<<aw; width=min(16,n); packet=min(lanes,n)
    groups=(n+packet-1)//packet; rows=n//width
    kw=(2*lanes).bit_length()-1
    # Frozen producer: RAM read at edge1+g, result commit at edge1+D+g.
    commit=[1+delay+g for g in range(groups)]
    pending=deque(); queue=deque(); next_packet=0; consumed=[]
    reads=[]; peak_slots=0; stalls=0; rng=random.Random(seed)
    for edge in range(1,20*n+200):
        ready=mode!='blocked' or (edge%37 not in range(8,23) and rng.randrange(5)!=0)
        # Each packet slot has a registered capture edge. Newly captured words
        # are not consumed at that same edge (no combinational fall-through).
        if queue and ready:
            item=queue[0]; base=item[0]+item[1]*width
            consumed.append((edge,base))
            item[1]+=1
            if item[1]*width==packet: queue.popleft()
        elif consumed and len(consumed)<rows and ready: stalls+=1
        while pending and pending[0][0]==edge:
            _,base=pending.popleft(); queue.append([base,0])
        occupied=len(queue)+len(pending)
        if next_packet<groups and occupied<2 and commit[next_packet]<edge:
            base=next_packet*packet
            requested={bank(base+j,aw,kw) for j in range(packet)}
            active=edge-1
            producer=set() if active>=groups else {bank(active*packet+j,aw,kw) for j in range(packet)}
            if not requested & producer:
                # The write edge must already have passed; never rely on a
                # mixed-port same-address read/write interpretation.
                assert commit[next_packet]<edge
                assert len(requested)==packet
                reads.append((edge,base))
                pending.append((edge+1,base)); next_packet+=1
        peak_slots=max(peak_slots,len(queue)+len(pending))
        assert peak_slots<=2
        if len(consumed)==rows:
            assert [base for _,base in consumed]==list(range(0,n,width))
            assert [base for _,base in reads]==list(range(0,n,packet))
            assert not queue and not pending and next_packet==groups
            # CRT accepts the rows above; 61-stage out_valid is t+60, and
            # carry coefficient RAM captures that result at t+61.
            final_commit=consumed[-1][0]+61
            # Existing core: final NTT start at edge0, counted NTT B+D+2,
            # then T+62 CRT phase. Edge of final coefficient commit is -1.
            baseline_final=groups+delay+2+rows+62-1
            return dict(aw=aw,n=n,lanes=lanes,latency=delay,mode=mode,
                packet_words=packet,first_crt=consumed[0][0],last_crt=consumed[-1][0],
                final_coefficient_commit=final_commit,baseline_final_commit=baseline_final,
                modeled_saved_clocks=baseline_final-final_commit,crt_input_bubbles=stalls,
                peak_packet_slots=peak_slots,reads=len(reads),rows=rows)
    raise AssertionError('bounded schedule did not drain')


def direct_fifo(n, lanes, delay=8):
    width=min(16,n); packet=min(lanes,n); groups=n//packet
    pending=0; peak=0; sent=0
    for edge in range(n+1):
        if pending>=width: pending-=width; sent+=width
        if edge<groups: pending+=packet
        peak=max(peak,pending)
        if sent==n:
            assert peak==n-width*(groups-1)
            # edge0 below is the first producer result commit at physical
            # edge1+D. The first CRT input is the following edge.
            final_commit=1+delay+edge+61
            baseline_final=groups+delay+2+n//width+62-1
            return dict(peak_coefficients=peak,modeled_saved_clocks=baseline_final-final_commit,
                        final_coefficient_commit=final_commit)
    raise AssertionError('FIFO failed to drain')


def arithmetic():
    checks=0
    for p,g in ((104857601,3),(69206017,5),(67239937,10)):
        r=1<<32; rinv=pow(r,-1,p)
        for aw in range(1,17):
            n=1<<aw; psi=pow(g,(p-1)//(2*n),p)
            assert pow(psi,n,p)==p-1
            for j in sorted({0,1,n//2,n-1}):
                for value in (0,1,p-1,(j*271828183+17)%p):
                    inverse_word=value*n*pow(psi,j,p)*r%p
                    ordinary_post=pow(n,-1,p)*pow(pow(psi,j,p),-1,p)%p
                    result=inverse_word*ordinary_post*rinv%p
                    assert result==value
                    checks+=1
    return checks


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if socket.gethostname()!='aethia': raise RuntimeError('aethia only')
    results=[]; layout_checks=0
    for aw in range(1,17):
        for lanes in (16,64):
            n=1<<aw; packet=min(lanes,n); kw=(2*lanes).bit_length()-1
            assert len({(bank(a,aw,kw),a>>kw) for a in range(n)})==n
            for base in range(0,n,packet):
                base_bank=bank(base,aw,kw)
                for offset in range(packet):
                    assert bank(base+offset,aw,kw)==(base_bank^offset)
                    assert (base+offset)>>kw==base>>kw
                    layout_checks+=1
            for delay in (7,8):
                for mode in ('ready','blocked'):
                    results.append(schedule(aw,lanes,delay,mode,20260929))
    report=dict(status='passed',kind='independent model, not RTL measurement',
                layout_checks=layout_checks,radix32_checks=arithmetic(),schedules=results,
                direct_fifo_models={str(l):direct_fifo(65536,l) for l in (16,64)},
                source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    with args.output.open('x') as handle: json.dump(report,handle,indent=2);handle.write('\n')
    print('PASS',len(results),'schedules;',layout_checks,'layout checks')
    for item in results:
        if item['aw']==16 and item['mode']=='ready': print(json.dumps(item,sort_keys=True))
    print('Direct FIFO',report['direct_fifo_models'])


if __name__=='__main__': main()
