"""Independent expected schedule/counters for the prepared paired host bench.

Pure Python flat-memory model; imports neither bench/runner nor HDL tools.
Does not derive counters from source parsing, simulator output, or receipts.
The source SHA identifies the reviewed schedule this model was written for.
Uninitialized reads are errors; reset invalidates software knowledge rather
than pretending RAM clears. Trace hashes bind inputs and expected memory events.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct

BENCH_SHA='5b56c0d69f5a3299d5923bc6d3e9c8301786cce3a2de6161bda6b18b9cb22cdd'
FIELDS={1:104857601,2:69206017,3:67239937}
COUNTERS=('edges','read_words','written_words','vector_reads','vector_writes','masked_poison',
          'clipped','descriptor_errors','profile_checks','busy_checks','quarters','halves')
STROBES=('load_we','read_en','vector_load_we','vector_read_en','start','profile_begin','profile_we','profile_commit')


def require(value,message):
    if not value:raise ValueError(message)


def xorshift32(state):
    require(type(state) is int and 0<=state<1<<32,'uint32 PRNG state')
    state=(state^(state<<13))&0xffffffff
    state=(state^(state>>17))&0xffffffff
    return (state^(state<<5))&0xffffffff


class MemorySchedule:
    def __init__(self,aw,field):
        require(type(aw) is int and 1<=aw<=16 and field in FIELDS,'supported AW/field')
        self.aw=aw;self.n=1<<aw;self.p=FIELDS[field]
        self.memory=[None]*self.n
        self.count={key:0 for key in COUNTERS}
        self.trace=hashlib.sha256();self.events={}
        self.s=dict.fromkeys(STROBES,0)
        self.s.update(instance_enable=3,rst_n=1,size_log2=aw,root_phase=0,op=1,inverse=0,dif=0,scale=0,
                      host_addr=0,write_data=0,vector_addr=0,vector_lane_mask=0,vector_write_data=[0]*16,
                      profile_modulus=self.p,profile_size_log2=aw,profile_format=2,profile_addr=0,profile_data=0)

    def set(self,**values):
        widths={'host_addr':self.aw,'vector_addr':self.aw,'size_log2':5,'profile_size_log2':5,
                'vector_lane_mask':16,'profile_addr':16,'root_phase':2,'op':2,'profile_format':8}
        for key,value in values.items():
            require(key in self.s,'unknown modeled input')
            self.s[key]=value&((1<<widths[key])-1) if key in widths else value

    def clear(self):
        for key in STROBES:self.s[key]=0

    def edge(self,kind,reads=(),writes=()):
        self.count['edges']+=1;self.events[kind]=self.events.get(kind,0)+1
        payload={'edge':self.count['edges'],'kind':kind,'inputs':self.s,'read':reads,'write':writes}
        self.trace.update(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()+b'\n')

    def reset(self):
        self.clear();self.set(rst_n=0);self.edge('reset_assert')
        self.memory=[None]*self.n
        self.set(rst_n=1);self.edge('reset_release')

    def ordinary(self,kind='ordinary'):
        s=self.s;c=self.count
        require(s['rst_n']==1 and s['instance_enable']==3 and not any(s[k] for k in
                ('start','profile_begin','profile_we','profile_commit')),'ordinary eligibility')
        extent=1<<s['size_log2'] if 1<=s['size_log2']<=self.aw else 0
        address=s['vector_addr'];scalar=s['host_addr'];request=bool(s['vector_load_we'] or s['vector_read_en'])
        valid=bool(extent and address%16==0 and address<extent)
        active=[i for i in range(16) if s['vector_lane_mask']>>i&1 and address+i<extent]
        written=[];read=[]
        if request and valid and s['vector_load_we']:
            c['vector_writes']+=1;c['quarters']|=1<<((address>>4)&3);c['halves']|=1<<((address>>6)&1)
            for i,word in enumerate(s['vector_write_data']):
                if i in active:
                    require(0<=word<self.p,'normal active vector payload canonical')
                    self.memory[address+i]=word;written.append((address+i,word));c['written_words']+=1
                elif word>=self.p:c['masked_poison']+=1
                if s['vector_lane_mask']>>i&1 and address+i>=extent:c['clipped']+=1
        elif not request and s['load_we']:
            require(0<=s['write_data']<self.p,'normal scalar write canonical')
            self.memory[scalar]=s['write_data'];written.append((scalar,s['write_data']));c['written_words']+=1
        if request and not valid:c['descriptor_errors']+=1
        if not request and s['read_en'] and not s['load_we']:
            require(self.memory[scalar] is not None,'uninitialized scalar read')
            read.append((scalar,self.memory[scalar]));c['read_words']+=1
        if request and valid and s['vector_read_en'] and not s['vector_load_we']:
            c['vector_reads']+=1
            for i in active:
                require(self.memory[address+i] is not None,'uninitialized masked vector read')
                read.append((address+i,self.memory[address+i]));c['read_words']+=1
        self.edge(kind,read,written)

    def initialize(self):
        self.clear();self.set(size_log2=self.aw,load_we=1,read_en=1)
        for i in range(self.n):
            self.set(host_addr=i,write_data=(i*2654435761+0x56789)%self.p);self.ordinary('initialize')
        self.clear()

    def scan(self):
        self.clear();self.set(read_en=1,size_log2=self.aw)
        for i in range(self.n):self.set(host_addr=i);self.ordinary('scan')
        self.clear();self.ordinary('scan_idle')

    def run(self):
        self.reset();self.initialize()
        for address in range(0,self.n,16):
            for mask in (0,1,0x8000,0x8001,0x5555,0xaaaa,0xffff):
                self.clear();self.set(vector_load_we=1,vector_read_en=1,vector_addr=address,vector_lane_mask=mask,
                    load_we=1,read_en=1,host_addr=(address+1)%self.n,write_data=self.p,
                    vector_write_data=[(address*31+i*127+mask)%self.p if mask>>i&1 and address+i<self.n
                                       else 0xffffffff for i in range(16)])
                self.ordinary('directed_write')
                self.clear();self.set(vector_read_en=1,vector_addr=address,vector_lane_mask=0xffff);self.ordinary('directed_read')
                if self.n>16:
                    self.clear();self.set(read_en=1,host_addr=(address+16)%self.n);self.ordinary('neighbor_read')
        for lg in range(1,self.aw+1):
            n=1<<lg;self.set(size_log2=lg)
            for address in (0,((n-1)//16)*16):
                self.clear();self.set(vector_addr=address,vector_load_we=1,vector_lane_mask=0xffff,
                    vector_write_data=[(n+i+1)%self.p if address+i<n else 0xffffffff for i in range(16)])
                self.ordinary('runtime_write');self.clear();self.set(vector_read_en=1);self.ordinary('runtime_read')
        for size in (0,self.aw+1,31,1):
            self.clear();self.set(size_log2=size,vector_load_we=1,vector_read_en=1,vector_addr=1,vector_lane_mask=0xffff,
                vector_write_data=[0xffffffff]*16,load_we=1,read_en=1,host_addr=0,write_data=self.p)
            self.ordinary('invalid_descriptor')
        if self.aw>=5:
            self.clear();self.set(size_log2=4,vector_addr=16,vector_read_en=1);self.ordinary('range_descriptor')
        state=0x91bb27+self.aw;calls=0
        def random():
            nonlocal state,calls
            state=xorshift32(state);calls+=1;return state
        for round_number in range(1200):
            self.clear();sizes=(0,1,self.aw,self.aw+1,min(4,self.aw))
            self.set(size_log2=sizes[random()%5],host_addr=random()%self.n,vector_addr=random()%self.n)
            if round_number&1:self.set(vector_addr=self.s['vector_addr']&~15)
            # Keep each C++ call in its exact order, even when a request is masked.
            self.set(load_we=random()&1,read_en=random()&1,vector_load_we=random()&1,vector_read_en=random()&1,
                write_data=random()%self.p,vector_lane_mask=random(),vector_write_data=[random()%self.p for _ in range(16)])
            self.ordinary('fuzz')
        self.scan()
        for kind in range(3):
            self.clear();self.set(profile_begin=int(kind==0),profile_we=int(kind==1),profile_commit=int(kind==2),
                profile_modulus=self.p+1,profile_size_log2=0,profile_format=2,profile_addr=0,profile_data=self.p,
                load_we=1,read_en=1,host_addr=0,write_data=self.p,vector_load_we=1,vector_read_en=1,vector_addr=1,vector_lane_mask=0xffff)
            self.edge('malformed_profile');self.count['profile_checks']+=1
            self.clear();self.ordinary('post_profile_idle');self.scan()
        self.clear();self.set(size_log2=self.aw,profile_begin=1,profile_modulus=self.p,profile_size_log2=self.aw,
            profile_format=2,vector_load_we=1,vector_addr=0,vector_lane_mask=0)
        self.edge('valid_profile_begin');self.count['profile_checks']+=1
        self.clear();self.set(profile_we=1,profile_addr=0,profile_data=self.p-1,load_we=1,host_addr=0,write_data=self.p)
        self.edge('valid_profile_word');self.count['profile_checks']+=1
        self.clear();self.set(profile_commit=1);self.edge('partial_profile_commit');self.count['profile_checks']+=1
        self.clear();self.ordinary('post_profile_idle');self.scan()
        self.clear();self.set(start=1,op=1,size_log2=self.aw,inverse=0,profile_begin=1,profile_we=1,profile_commit=1,
            profile_size_log2=0,vector_load_we=1,vector_read_en=1,vector_addr=1,vector_lane_mask=0xffff,
            load_we=1,read_en=1,write_data=self.p)
        self.edge('priority_start')
        for i in range(2):
            self.set(start=i&1,profile_begin=int(i==0),profile_we=int(i==1),profile_commit=0,size_log2=0)
            self.edge('priority_busy');self.count['busy_checks']+=1
        self.reset()
        for _ in range(12):self.edge('post_reset_drain')
        self.initialize();self.scan()
        require(calls==30000,'exact25 PRNG calls per fuzz round')
        require(all(x is not None for x in self.memory),'final memory initialized')
        return dict(counts=dict(aw=self.aw,p=self.p,**self.count),trace_sha256=self.trace.hexdigest(),
            final_memory_sha256=hashlib.sha256(b''.join(struct.pack('<I',x) for x in self.memory)).hexdigest(),
            schedule_events=self.events,prng_calls=calls,prng_final_state=state,bench_sha256=BENCH_SHA,
            scope='Independent expected host-memory schedule only; no RTL execution or observed result')


def expected_result(aw,field=1):return MemorySchedule(aw,field).run()


def canonical_footer(result):
    counts=result['counts']
    return 'PASS host_broadcast_memory_pair '+' '.join(key+'='+str(counts[key]) for key in ('aw','p',*COUNTERS))


def verify_bench_source(path):
    require(hashlib.sha256(Path(path).read_bytes()).hexdigest()==BENCH_SHA,'bench schedule identity changed')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--aw',type=int,required=True)
    parser.add_argument('--field',type=int,choices=(1,2,3),default=1);args=parser.parse_args()
    result=expected_result(args.aw,args.field);result['expected_footer']=canonical_footer(result)
    print(json.dumps(result,indent=2))
