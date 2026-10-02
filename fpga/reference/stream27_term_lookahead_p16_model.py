"""Pure integer edge/bit proof for payload lookahead, not RTL/NTT execution."""
MASK=(1<<32)-1
def lookup(cycle,banks,rows):
    result=(0,0)
    for bank in banks:
        age=(cycle-bank['first'])&MASK
        if bank['valid'] and age<rows:result=(bank['epoch'],age)
    return result
def reverse4(value):return int(f'{value:04b}'[::-1],2)
def check(rows,pw_first,sink_first):
    assert rows in (16,4096) and pw_first>1 and sink_first>=pw_first+rows
    edges=0;forwards=0;firsts=0;wraps=0
    for origin in (0,MASK-128):
        banks=[dict(valid=False,epoch=0,first=0,sink=0) for _ in range(2)]
        table=[[bank*100+j for j in range(16)] for bank in range(2)]
        starts={0:65534,rows+8:65535,sink_first+rows+8:0}
        for tick in range(2*sink_first+3*rows+32):
            cycle=(origin+tick)&MASK
            epoch,row=lookup((cycle+1)&MASK,banks,rows)
            target=(row+4)&(rows-1);group=target//(rows//16);index=reverse4(group)
            coeff=table[epoch&1][index]
            # Exercise a real simultaneous table write on every phase, both
            # parities, including firstPW/cache margins and epoch wrap.
            write_bank=(tick//3)&1;small_data=[(tick*37+j*17)&((1<<27)-1) for j in range(16)]
            if write_bank==(epoch&1):coeff=small_data[group];forwards+=1
            table[write_bank]=[small_data[reverse4(j)] for j in range(16)]
            assert coeff==table[epoch&1][index]
            new=[dict(bank) for bank in banks]
            if tick in starts:
                free=next(i for i,bank in enumerate(banks) if not bank['valid'])
                e=starts[tick];new[free]=dict(valid=True,epoch=e,first=(cycle+pw_first)&MASK,sink=(cycle+sink_first)&MASK)
                wraps+=e==0
            for i,bank in enumerate(banks):
                if bank['valid'] and ((cycle-bank['sink'])&MASK)==rows-1:new[i]['valid']=False
            actual=lookup((cycle+1)&MASK,new,rows)
            assert (epoch,row)==actual
            firsts+=actual[1]==0 and any(bank['valid'] and bank['first']==((cycle+1)&MASK) for bank in new)
            banks=new;edges+=1
    return dict(status='PASS_SCALAR_MODEL_ONLY',rows=rows,edges=edges,simultaneous_B_write_forwards=forwards,
        pointwise_firsts=firsts,epoch_wrap_admissions=wraps,full_N_numeric_performed=False)
