"""Independent OFFLINE audit of the frozen L64/P1 periodmask component pair v2.

No saved binary or candidate Python module is executed. The only reused oracle
is the hash-frozen ordinary-integer logical-bank geometry proof. Raw vectors,
all deterministic harness counters, exact RTL/pair-harness deltas, native build
identity and artifact hashes are checked before a component qualification.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
import shlex
import tarfile

TOP='root_recurrence27_periodmask_pair'
BENCH=TOP+'_v2'
RUNNER='reference/root_recurrence27_periodmask_pair_v2_regression.py'
RUNNER_SHA='bd5fd981463b95bf5ac256a6678423dd7a6fb5998c56be340bdb7b4c43b23a10'
SOURCE='/home/jtl/gfn-fpga-lab/agent-work/root-recurrence27-periodmask-pair/snapshot-v2/fpga'
REMOTE=str(PurePosixPath(SOURCE).parent.parent/'l64-p1-v2'/('V'+TOP))
MANIFEST_SHA='6d1b10d06afb73681eae1c7aee3df658ca98093a2447f2edb074608a69eec013'
STAGE_ARCHIVE_SHA='1497f7277e56b4b98d536cf31dba99d09de63944588bc36e1ae8295f8ee89570'
VECTOR_SHA='64cf4b14a3fc4126dd8a39964285ec8b67357879756decd66abbdf383eb5e510'
PROFILE=dict(lanes=64,field=1,p=104857601,q=4190109697,tag_width=32)
PERIODS=(0,)+tuple(1<<i for i in range(17))
ORDER=('rtl/kernel/genefer_montgomery_mul27_sparse_pipe.sv',
       'rtl/kernel/genefer_root_recurrence27.sv',
       'rtl/kernel/genefer_root_recurrence27_periodmask.sv',
       'rtl/tb/'+TOP+'.sv','rtl/tb/'+BENCH+'_threaded.cpp')
SOURCE_PINS={
    "reference/__init__.py": "1c6df6d638965f2bc1c163f4e66f7f9038ebedc21e2139988aa5962c0ed47efb",
    "reference/prefetch_r2_periodmask_structure.py": "0bbe6b7fd08a8c00bcce437a10b1717b2ed16a11436ca8c7dc4846db34ef9dd1",
    "reference/root_recurrence27_periodmask_pair_v2_structure.py": "233725dfa66ad92462a7ac421ec47c5e46d528b1a2abf714a81bdf8edacc1eb8",
    "reference/root_recurrence27_periodmask_vectors.py": "fda0ee345cb1fe5577014fe32aaf98061a9964590c4b0b2eb146b1c5e1dc5a45",
    "reference/root_recurrence_proof.py": "41136efa238fed74562977010f4c91dcb073b779333400b243c48c26680f6cda",
    "rtl/kernel/genefer_montgomery_mul27_sparse_pipe.sv": "501d0ce309a3915f7aed0f3bde14ba1ee8d56ddc5f6abef1f2f5bb572d64db4b",
    "rtl/kernel/genefer_ntt_banked27_prefetch_r2_engine.sv": "552d273972af97c3363b77df0798e08a962d283869bcc95159f378a0f0070b17",
    "rtl/kernel/genefer_ntt_banked27_prefetch_r2_host_broadcast_engine.sv": "0960922332ea919a72a1ee591a70006bba76af7f26bc5308b68f50e327583e29",
    "rtl/kernel/genefer_ntt_banked27_prefetch_r2_host_broadcast_periodmask_engine.sv": "ae4567612a881974577e38ff2099a0187d07a5d44ba8c34a821d696148893ba8",
    "rtl/kernel/genefer_ntt_banked27_prefetch_r2_periodmask_engine.sv": "99b56338e2d73fbb3592a72040a5919a718cd9fbec742493c2e83fbcf5624cb9",
    "rtl/kernel/genefer_root_recurrence27.sv": "c8adc265915192807efee46799a782f1649a4408313098baaed8b4a808afeb9e",
    "rtl/kernel/genefer_root_recurrence27_periodmask.sv": "47d9f7e0db2c784424d4b148760f4235baeffef08969c4e790eb3c1e32a3e389",
    "rtl/kernel/genefer_square_core27_stream_prefetch_r2_host_broadcast.sv": "ea2b518880cb1c3191c71d35a232d2483aee82046ecd4d930d7ac7ffa07a80e1",
    "rtl/kernel/genefer_square_core27_stream_prefetch_r2_host_broadcast_periodmask.sv": "3fd005dfded5917f879b7d402228f2b32759324160e81e66bee309bf184e474b",
    "rtl/tb/root_recurrence27.cpp": "3e98fcb127349740c9fc0368ef43d557af5ca879d37887afa865ca8722ddce90",
    "rtl/tb/root_recurrence27_periodmask.cpp": "ed1ae516d8ada0d8381a07d5b261b09e92cc0c0dd926ac6b813a842494a86fae",
    "rtl/tb/root_recurrence27_periodmask_pair_v2.cpp": "089ffe0f9e157d063dbe4662bca8a07a65accfbdaccb55e550f72770a472a494",
    "rtl/tb/root_recurrence27_periodmask_pair.sv": "88c5bf5125e6b0717fdec46ef638dc4cbe5c06db7952be6956e79b8ba57956c0",
    "rtl/tb/root_recurrence27_periodmask_pair_v2_threaded.cpp": "9528cdfa9820968e583934df2c7fb1ac6ff789fada0d996b248b9e1409438cff"
}
SOURCE_PINS[RUNNER]=RUNNER_SHA
TOOL_PINS={
 '/usr/bin/python3.14':'52e0a13e60a981d8c4b6478be2ba5176f69da07948a056bf49cf6f077e30cb41',
 '/usr/bin/x86_64-linux-gnu-g++-15':'e6718f7e0c7d057c3ff77b550c603da9bc4030e3ede3c053705acce1293dbe4d',
 '/home/jtl/gfn-fpga-lab/tools/verilator/usr/bin/verilator':'672a1ccf3468902f66387049f001b04f254bbcece7d5e816e3861715889bf252'}
FOOTER_KEYS=('lanes','cases','runs','responses','checked_cycles','bubbles','seed_checks','aborts','rejects','pair_checks')
OUTPUTS=('request_ready','root_valid','roots','root_mask','root_tag','root_group',
         'busy','done','error','seed_error','cycles')
PORTS=('clk','rst_n','seed_we','seed_clear','seed_bank','seed_context','seed_lane','seed_data',
       'start','config_bank','config_groups','config_period','config_active_lanes','config_step',
       'request_valid','request_ready','request_tag','root_valid','roots','root_mask','root_tag',
       'root_group','busy','done','error','seed_error','cycles')


def require(ok,message):
    if not ok:raise ValueError(message)


def digest(data):return hashlib.sha256(data).hexdigest()


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def mapping_sha(value):return digest(json.dumps(value,sort_keys=True,separators=(',',':')).encode())


def local_file(root,name):
    require(isinstance(name,str),'artifact name type')
    root=Path(root).resolve();relative=PurePosixPath(name)
    require(str(relative)==name and not relative.is_absolute() and
            '..' not in relative.parts and name not in ('','.'),
            'unsafe artifact name')
    path=root/name
    require(path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(root),
            'missing/linked artifact: '+name)
    require(not any((root/Path(*relative.parts[:i])).is_symlink() for i in range(1,len(relative.parts))),
            'linked artifact parent')
    return path


def archive(path,pins=None,prefix=''):
    members={};total=0
    with tarfile.open(path,'r:gz') as stream:
        for entry in stream:
            name=entry.name
            require(entry.isfile() and not entry.issym() and not entry.islnk() and
                    0<=entry.size<=32<<20,'nonregular/oversized archive member')
            relative=PurePosixPath(name)
            require(str(relative)==name and not relative.is_absolute() and
                    '..' not in relative.parts and name.startswith(prefix),'unsafe archive path')
            name=name[len(prefix):]
            require(name and name not in members and len(members)<256,'duplicate/excess archive members')
            total+=entry.size;require(total<=64<<20,'archive uncompressed-size limit')
            members[name]=stream.extractfile(entry).read()
    if pins is not None:
        require(set(members)==set(pins),'exact archive member closure')
        require(all(digest(members[name])==value for name,value in pins.items()),'archive member pin drift')
    return members


def once(text,old,new):
    require(text.count(old)==1,'ambiguous independent source anchor')
    return text.replace(old,new)


def source_delta(members):
    """Literal independent derivative reconstruction; no candidate imports."""
    names={
      'genefer_root_recurrence27':'genefer_root_recurrence27_periodmask',
      'genefer_ntt_banked27_prefetch_r2_engine':'genefer_ntt_banked27_prefetch_r2_periodmask_engine',
      'genefer_ntt_banked27_prefetch_r2_host_broadcast_engine':'genefer_ntt_banked27_prefetch_r2_host_broadcast_periodmask_engine',
      'genefer_square_core27_stream_prefetch_r2_host_broadcast':'genefer_square_core27_stream_prefetch_r2_host_broadcast_periodmask'}
    children=dict(zip(list(names)[1:],list(names)[:-1]))
    for old,new in names.items():
        original=members['rtl/kernel/'+old+'.sv'].decode()
        wanted=once(original,'module '+old+' #(','module '+new+' #(')
        if old=='genefer_root_recurrence27':
            changes=(
              ('logic [16:0] groups,repeat_period,issued,position;','logic [16:0] groups,repeat_mask,issued,position;'),
              ("    assign position=repeat_period==0 ? issued : issued&(repeat_period-17'd1);",
               "    // Cache the 17-bit period-minus-one on accepted start; zero wraps to all ones.\n    assign position=issued&repeat_mask;"),
              ('groups<=0;repeat_period<=0;issued<=0;', "groups<=0;repeat_mask<=17'h1ffff;issued<=0;"),
              ('repeat_period<=config_period;active_lanes<=config_active_lanes;',
               "repeat_mask<=config_period-17'd1;active_lanes<=config_active_lanes;"))
            for a,b in changes:wanted=once(wanted,a,b)
        else:
            child=children[old];wanted=once(wanted,child+' #(',names[child]+' #(')
        require(members['rtl/kernel/'+new+'.sv'].decode()==wanted,'exact periodmask RTL delta')
    original=members['rtl/tb/root_recurrence27.cpp'].decode()
    require(original.count('Vgenefer_root_recurrence27')==2,'frozen baseline bench model anchors')
    wanted=original.replace('Vgenefer_root_recurrence27','Vgenefer_root_recurrence27_periodmask')
    wanted=once(wanted,'                d.start=1;d.config_groups=0;d.config_active_lanes=0;d.config_step=TEST_P;',
        '                d.start=1;d.config_groups=0;d.config_active_lanes=0;d.config_step=TEST_P;\n'
        '                d.config_period=(elapsed&1) ? 0u : 131071u; // Busy configuration must not alter the cached mask.')
    require(members['rtl/tb/root_recurrence27_periodmask.cpp'].decode()==wanted,'exact busy-config baseline bench delta')
    wanted=wanted.replace('Vgenefer_root_recurrence27_periodmask','V'+TOP)
    wanted=once(wanted,'V'+TOP+' d;','V'+TOP+' d{Verilated::threadContextp()};')
    wanted=once(wanted,'    auto tick=[&](){d.clk=0;d.eval();d.clk=1;d.eval();};',
        '    uint64_t pair_checks=0;\n'
        '    auto compare=[&](){pair_checks++;if(d.pair_mismatch)throw std::runtime_error("baseline/candidate port mismatch");};\n'
        '    auto tick=[&](){d.clk=0;d.eval();compare();d.clk=1;d.eval();compare();};')
    wanted=once(wanted,'                d.clk=0;d.eval();','                d.clk=0;d.eval();compare();')
    wanted=once(wanted,'                d.clk=1;d.eval();elapsed++;checks++;','                d.clk=1;d.eval();compare();elapsed++;checks++;')
    wanted=once(wanted,'if(c.groups>=8 && cases%17==0){','if(c.groups>=8 && (cases%17==0 || c.name.rfind("period-",0)==0)){')
    wanted=once(wanted,'<<" aborts="<<aborts<<" rejects="<<rejects<<"\\n";',
                '<<" aborts="<<aborts<<" rejects="<<rejects<<" pair_checks="<<pair_checks<<"\\n";')
    wanted=once(wanted,'\n}catch(const std::exception& e)','\n    return 0;\n}catch(const std::exception& e)')
    require(members['rtl/tb/'+BENCH+'.cpp'].decode()==wanted,'exact paired v2 comparison/reset/return bench delta')
    baseline=members['rtl/kernel/genefer_root_recurrence27.sv'].decode()
    header=baseline[baseline.index('module '):baseline.index(');')+2]
    header=once(header,'module genefer_root_recurrence27 #(','module '+TOP+' #(')
    header=once(header,'    output logic [63:0] cycles\n',
        '    output logic [63:0] cycles,\n    output logic pair_mismatch,\n'
        '    output logic [31:0] probe_lanes,probe_p,probe_q\n')
    wanted='// Paired component equivalence probe; no integration or physical claim.\n'+header+'\n'
    wanted+='    logic baseline_request_ready,baseline_root_valid,baseline_busy,baseline_done,baseline_error,baseline_seed_error;\n'
    wanted+='    logic [LANES*32-1:0] baseline_roots;\n    logic [LANES-1:0] baseline_root_mask;\n'
    wanted+='    logic [TAG_W-1:0] baseline_root_tag;\n    logic [16:0] baseline_root_group;\n'
    wanted+='    logic [63:0] baseline_cycles;\n'
    wanted+='    assign probe_lanes=LANES;assign probe_p=P;assign probe_q=Q;\n'
    for instance,module in (('baseline','genefer_root_recurrence27'),('candidate','genefer_root_recurrence27_periodmask')):
        wanted+='    '+module+' #(.LANES(LANES),.TAG_W(TAG_W),.P(P),.Q(Q)) '+instance+' (\n'
        wanted+='        '+',\n        '.join('.'+port+'('+('baseline_' if instance=='baseline' and port in OUTPUTS else '')+port+')' for port in PORTS)+'\n    );\n'
    wanted+='    assign pair_mismatch=\n        '+' ||\n        '.join('('+port+' !== baseline_'+port+')' for port in OUTPUTS)+';\nendmodule\n'
    require(members['rtl/tb/'+TOP+'.sv'].decode()==wanted,'exact all-eleven-port paired comparator')
    wanted=WRAPPER_TEXT
    require(members['rtl/tb/'+BENCH+'_threaded.cpp'].decode()==wanted,'exact explicit-context v2 wrapper')


WRAPPER_TEXT='''// Explicit context and runtime probe around the separately pinned pair bench.
#define main periodmask_pair_main
#include "root_recurrence27_periodmask_pair_v2.cpp"
#undef main
int main(int argc,char** argv) {
    VerilatedContext* const context=Verilated::threadContextp();
    context->threads(1);
    context->commandArgs(argc,argv);
    if(argc==2 && std::string(argv[1])=="--runtime-probe") {
        Vroot_recurrence27_periodmask_pair dut{context};
        dut.eval();
        std::cout<<"{\\"context_threads\\":"<<context->threads()
            <<",\\"model_threads\\":"<<dut.threads()
            <<",\\"lanes\\":"<<dut.probe_lanes<<",\\"p\\":"<<dut.probe_p
            <<",\\"q\\":"<<dut.probe_q<<"}\\n";
        return context->threads()==1 && dut.threads()==1 ? 0 : 2;
    }
    const int result=periodmask_pair_main(argc,argv);
    return context->threads()==1 ? result : 97;
}
'''


def integer_oracle():
    """Import only the reviewed, independent logical-address proof helper."""
    directory=Path(__file__).resolve().parent;path=directory/'root_recurrence_proof.py'
    require(sha(path)==SOURCE_PINS['reference/root_recurrence_proof.py'],'integer oracle source pin')
    require(__package__,'run as python -m fpga.reference.verify_root_recurrence27_periodmask_pair_offline')
    from . import root_recurrence_proof as oracle
    require(Path(oracle.__file__).resolve()==path and sha(path)==SOURCE_PINS['reference/root_recurrence_proof.py'],
            'integer oracle import identity')
    require(oracle.FIELDS==[(104857601,3),(69206017,5),(67239937,10)] and oracle.R==1<<32,
            'ordinary integer field constants')
    return oracle


def independent_cases():
    """Roots from reconstructed logical addresses and direct modular powers.

    No mask expression, RTL recurrence, candidate vector generator or pipeline
    model participates in expected root arithmetic.
    """
    oracle=integer_oracle();p=PROFILE['p'];lanes=PROFILE['lanes'];k=lanes.bit_length();mont=(1<<32)%p
    for lg in range(1,17):
        stages,point,_=oracle.check_geometry(lg,lanes);n=1<<lg
        psi=pow(3,(p-1)//(2*n),p);omega=psi*psi%p
        for inverse in (False,True):
            alpha=pow(omega,-1,p) if inverse else omega
            for stage,demand in enumerate(stages):
                active=min(lanes,1<<stage);repeat=1 if stage<k else 1<<(stage-k+1);shift=lg-1-stage
                step=mont if repeat<=4 else pow(alpha,1<<(k+shift+1),p)*mont%p
                rows=[]
                for indices,exponents in demand:
                    row=[None]*active
                    for index,exponent in zip(indices,exponents):
                        value=pow(alpha,exponent,p)*mont%p
                        require(row[index] is None or row[index]==value,'logical repeated-root consistency')
                        row[index]=value
                    require(all(value is not None for value in row),'complete logical root row');rows.append(row)
                contexts=min(4,repeat,len(rows))
                yield dict(name=f'lg{lg}-inv{int(inverse)}-stage{stage}',groups=len(rows),active=active,
                           period=repeat,step=step,contexts=contexts,seeds=rows[:contexts],rows=rows)
        for post in (False,True):
            alpha=pow(psi,-1,p) if post else psi;scale=pow(n,-1,p) if post else mont
            active=min(lanes,n);rows=[]
            for indices,addresses in point:
                row=[None]*active
                for index,address in zip(indices,addresses):row[index]=pow(alpha,address,p)*scale%p
                require(all(value is not None for value in row),'complete logical point row');rows.append(row)
            contexts=min(4,len(rows))
            yield dict(name=f'lg{lg}-post{int(post)}',groups=len(rows),active=active,period=0,
                       step=pow(alpha,4*lanes,p)*mont%p,contexts=contexts,seeds=rows[:contexts],rows=rows)
    for repeat in PERIODS:
        groups=min(65536,max(9,2*repeat+5)) if repeat else 65536
        contexts=min(4,groups,repeat or groups);seeds=[[19+31*index] for index in range(contexts)];rows=[]
        for issued in range(groups):
            position=issued%repeat if repeat else issued
            rows.append([seeds[position%4][0]*pow(7,position//4,p)%p])
        yield dict(name=f'period-{repeat}',groups=groups,active=1,period=repeat,
                   step=7*mont%p,contexts=contexts,seeds=seeds,rows=rows)


def audit_vectors(raw):
    """Compare every vector byte with a freshly regenerated integer oracle."""
    lines=iter(raw.decode('ascii').splitlines(keepends=True));cases=[];responses=words=resets=0
    def compare(line):require(next(lines,None)==line+'\n','ordinary-integer vector record mismatch')
    for case in independent_cases():
        index=len(cases);g=case['groups'];active=case['active'];contexts=case['contexts']
        compare(f"CASE {case['name']} {g} {active} {case['period']} {case['step']} {contexts}")
        compare(' '.join(str(value) for row in case['seeds'] for value in row))
        for row in case['rows']:
            require(len(row)==active and all(type(value) is int and 0<=value<PROFILE['p'] for value in row),
                    'canonical independent root words')
            compare(' '.join(map(str,row)))
        responses+=2*g;words+=2*g*active
        resets+=int(g>=8 and (index%17==0 or case['name'].startswith('period-')))
        cases.append({key:value for key,value in case.items() if key not in ('seeds','rows')})
    require(next(lines,None) is None,'extra vector record')
    return dict(cases=cases,case_count=len(cases),runs=2*len(cases),responses=responses,
                checked_root_words=words,aborts=4*resets+1,rejects=8+4*resets,
                legal_periods=list(PERIODS),sha256=digest(raw))


class MT19937:
    """The standard C++ mt19937 integer-seed algorithm, not Python random."""
    def __init__(self,seed):
        self.state=[seed&0xffffffff]
        for i in range(1,624):
            last=self.state[-1];self.state.append((1812433253*(last^(last>>30))+i)&0xffffffff)
        self.index=624

    def next(self):
        if self.index==624:
            for i in range(624):
                y=(self.state[i]&0x80000000)|(self.state[(i+1)%624]&0x7fffffff)
                self.state[i]=self.state[(i+397)%624]^(y>>1)^(0x9908b0df if y&1 else 0)
            self.index=0
        y=self.state[self.index];self.index+=1
        y^=y>>11;y^=(y<<7)&0x9d2c5680;y^=(y<<15)&0xefc60000;y^=y>>18
        return y&0xffffffff


def expected_counts(cases):
    """Integer event accounting for the exact frozen harness, not RTL output.

    RNG controls bubbles and tags only. Both-bank seed loading, four drain
    cycles, four reset depths and the one drain abort determine all counters.
    Pair checks include both evaluations of every helper tick and run cycle.
    """
    rng=MT19937(0x414193);seeds=1+4*PROFILE['lanes'];ticks=2+16;checked=bubbles=responses=runs=aborts=0;rejects=8
    drain_tested=False
    for index,case in enumerate(cases):
        groups=case['groups'];size=case['active']*case['contexts'];seeds+=1+size+4
        for rep in range(2):
            if rep==0:seeds+=1
            ticks+=1;issued=elapsed=prefetch=0
            while issued<groups:
                valid=rep==0 or rng.next()%3!=0
                rng.next() # request tag, including a rejected/bubbled request
                clear_bad=elapsed%43==11;active_bad=elapsed%19==7
                if not(rep==1 and elapsed==0) and not(clear_bad or active_bad) and prefetch<size:prefetch+=1
                elapsed+=1;checked+=1
                if valid:issued+=1;responses+=1
                else:bubbles+=1
            for _ in range(4):
                rng.next() # tags are still assigned while update results drain
                if not(elapsed%43==11 or elapsed%19==7) and prefetch<size:prefetch+=1
                elapsed+=1;checked+=1
            require(elapsed<3*groups+50,'frozen harness timeout accounting')
            seeds+=size-prefetch;runs+=1
        if groups>=8 and (index%17==0 or case['name'].startswith('period-')):
            for depth in range(1,5):
                seeds+=1+size;ticks+=depth+5;aborts+=1;rejects+=1
        if groups>=8 and not drain_tested:
            seeds+=1+size;ticks+=groups+5;aborts+=1;drain_tested=True
    return dict(zip(FOOTER_KEYS,(PROFILE['lanes'],len(cases),runs,responses,checked,bubbles,seeds,aborts,rejects,
                                 2*(ticks+seeds+checked))))


def strict_equal(actual,wanted,label):
    require(type(actual) is type(wanted),label+' type')
    if isinstance(wanted,dict):
        require(set(actual)==set(wanted),label+' keys')
        for key,value in wanted.items():strict_equal(actual[key],value,label+'.'+key)
    elif isinstance(wanted,(list,tuple)):
        require(len(actual)==len(wanted),label+' length')
        for a,b in zip(actual,wanted):strict_equal(a,b,label)
    else:require(actual==wanted,label+' value')


def check_normal(text,wanted):
    match=re.fullmatch('PASS '+' '.join(key+r'=(\d+)' for key in FOOTER_KEYS)+r'\n?',text)
    require(match is not None,'one exact normal footer')
    actual=dict(zip(FOOTER_KEYS,map(int,match.groups())))
    strict_equal(actual,wanted,'fresh deterministic normal counters')
    require(actual['checked_cycles']==actual['responses']+actual['bubbles']+4*actual['runs'],
            'normal response/bubble/drain accounting')
    return actual


def metadata(report,manifest):
    require(report.get('status')=='passed_component_pair' and 'error' not in report,'failed/incomplete native pair')
    require(report['scope']=='Standalone baseline/candidate recurrence paired output and cycle equivalence' and
            report['top']==TOP,'native pair scope/top')
    strict_equal(report['profile'],PROFILE,'report profile');strict_equal(manifest['profile'],PROFILE,'manifest profile')
    strict_equal(report['sources'],SOURCE_PINS,'twenty source identities');strict_equal(manifest['sources'],SOURCE_PINS,'manifest source identities')
    require(report['compiled_source_order']==manifest['compiled_source_order']==list(ORDER),'exact five-file compilation closure')
    require(manifest['status']=='prepared_not_executed' and manifest['source_root']==SOURCE and manifest['top']==TOP and
            manifest['archive_sha256']==STAGE_ARCHIVE_SHA and report['manifest_sha256']==MANIFEST_SHA,'frozen approved snapshot binding')
    bounds=dict(compile_workers=2,model_threads=1,scratch_reservation_bytes=768<<20,scratch_free_floor_bytes=2<<30,
        durable_reservation_bytes=64<<20,durable_free_floor_bytes=10<<30,host_memory_floor_bytes=4<<30,
        command_timeout_seconds=1800,lock_wait_timeout_seconds=1800)
    for name,wanted in bounds.items():strict_equal(report[name],wanted,'execution bound '+name)
    limits=report['limits'];strict_equal(limits['affinity'],[0,2],'CPU affinity')
    require(type(limits['memory_max_bytes']) is int and 0<limits['memory_max_bytes']<=6<<30,'finite aggregate memory limit')
    cpu=limits['cpu_max'];require(type(cpu) is list and len(cpu)==2 and all(type(v) is str and re.fullmatch(r'\d+',v) for v in cpu) and
        int(cpu[1])>0 and 0<int(cpu[0])<=2*int(cpu[1]),'finite <=200% aggregate CPU limit')
    cores=limits['physical_cores'];require(type(cores) is list and len(cores)==2 and all(type(row) is list and len(row)==2 and
        all(type(v) is int and v>=0 for v in row) for row in cores) and len({tuple(row) for row in cores})==2,'two distinct physical cores')
    require(type(limits['cgroup']) is str and limits['cgroup'].endswith('/gfn-root-periodmask-pair-l64-p1-v2.service'),'reviewed unit cgroup')
    require(re.fullmatch(r'/dev/shm/gfn16-periodmask-pair-v2-[a-z0-9_]+',report['scratch']) and
            report['compiler_temporary_directory']==report['scratch']+'/tmp','isolated tmpfs workspace')
    require(report['executable']==REMOTE and re.fullmatch('[0-9a-f]{64}',report['executable_sha256']),'native executable identity')
    strict_equal(report['tool_executable_sha256'],TOOL_PINS,'reviewed native tool identity receipts')
    require(type(report['python_version']) is str and report['python_version'].startswith('3.14.4 '),'recorded native Python version')
    names=['verilator-version','g++-version','build','probe','normal'];steps=report['steps']
    require(type(steps) is list and [step['name'] for step in steps]==names,'exact ordered five native steps')
    for step in steps:
        require(type(step['returncode']) is int and step['returncode']==0 and step['error'] is None,'failed/bool native step')
        require(type(step['seconds']) in (int,float) and math.isfinite(step['seconds']) and 0<=step['seconds']<=1802,
                'bounded finite step duration')
        require(step['log']==step['name']+'.log' and re.fullmatch('[0-9a-f]{64}',step['sha256']),'native step log binding')
    return {step['name']:step for step in steps}


def commands(report,steps):
    flags='-std=c++17 -Werror=return-type -DTEST_LANES=64 -DTEST_P=104857601u'
    wanted=['verilator','--cc','--exe','--build','-j','2','--threads','1','--top-module',TOP,
        '-GLANES=64','-GP=104857601','-GQ=4190109697','-GTAG_W=32','-CFLAGS',flags,
        '--Mdir',report['scratch']+'/build',*[SOURCE+'/'+name for name in ORDER]]
    for name,argv in {'verilator-version':['verilator','--version'],'g++-version':['g++','--version'],
                     'build':wanted,'probe':[REMOTE,'--runtime-probe'],'normal':[REMOTE,str(PurePosixPath(REMOTE).parent/'vectors.txt')]}.items():
        strict_equal(steps[name]['command'],argv,'native command '+name)


def generated_contract(members,build_log):
    """Check actual wrapper compilation, dimensions and generated context ABI."""
    prefix='V'+TOP
    require(all('/' not in name and PurePosixPath(name).suffix in ('.cpp','.h','.mk','.dat') for name in members),
            'flat generated source artifact roles')
    require(all(prefix+suffix in members for suffix in ('.cpp','.h','.mk','___024root.h','__verFiles.dat')),
            'required generated model identities')
    cpp=members[prefix+'.cpp'].decode();header=members[prefix+'.h'].decode();make=members[prefix+'.mk'].decode()
    require(re.search(r'unsigned '+prefix+r'::threads\(\) const \{ return 1; \}',cpp),'generated single-thread model')
    for token in ('VL_OUTW(&roots,2047,0,64);','VL_OUT64(&root_mask,63,0);','VL_OUT(&root_tag,31,0);',
                  'VL_OUT(&root_group,16,0);','VL_OUT64(&cycles,63,0);','VL_OUT8(&pair_mismatch,0,0);',
                  'explicit '+prefix+'(VerilatedContext* contextp, const char* name = "TOP");'):
        require(header.count(token)==1,'generated HDL/C++ width or context ABI')
    match=re.search(r'VM_USER_CFLAGS = \\\n(.*?)\n\n',make,re.S)
    require(match is not None and shlex.split(match.group(1).replace('\\',''))==
            ['-std=c++17','-Werror=return-type','-DTEST_LANES=64','-DTEST_P=104857601u'],'generated strict C++ macro flags')
    require('VM_USER_CLASSES = \\\n\t'+BENCH+'_threaded \\\n' in make,'only reviewed C++ translation unit')
    wrapper=SOURCE+'/rtl/tb/'+BENCH+'_threaded.cpp';rows=[]
    for line in build_log.splitlines():
        if line.startswith('g++ '):
            tokens=shlex.split(line)
            if '-c' in tokens and any(token.endswith('_threaded.cpp') for token in tokens):rows.append(tokens)
    require(len(rows)==1,'one actual wrapper compilation')
    tokens=rows[0]
    require(tokens[-1]==wrapper and tokens[tokens.index('-o')+1]==BENCH+'_threaded.o','compiled exact wrapper source/object')
    require([t for t in tokens if t.startswith('-DTEST_')]==['-DTEST_LANES=64','-DTEST_P=104857601u'] and
            tokens.count('-Werror=return-type')==1 and '-Wno-return-type' not in tokens and '-Wno-error=return-type' not in tokens,
            'actual compiler strict return and profile flags')
    require(not any(t.startswith('-U') for t in tokens) and '-w' not in tokens,'compiler warning/macro suppression')
    require('control reaches end of non-void function' not in build_log,'renamed-main UB compilation warning')


def verify(root):
    root=Path(root).resolve();report_file=local_file(root,'report.json');report=json.loads(report_file.read_text())
    manifest_file=local_file(root,'approved-manifest.json');require(sha(manifest_file)==MANIFEST_SHA,'approved manifest bytes')
    manifest=json.loads(manifest_file.read_text());steps=metadata(report,manifest);commands(report,steps)
    roles={'approved-manifest.json','sources.tar.gz','vectors.txt','generated-sources.tar.gz','V'+TOP,
           'verilator-version.log','g++-version.log','build.log','probe.log','normal.log'}
    require(set(report['artifacts'])==roles,'exact ten durable artifact roles')
    for name,value in report['artifacts'].items():
        require(type(value) is str and re.fullmatch('[0-9a-f]{64}',value) and sha(local_file(root,name))==value,'raw artifact hash: '+name)
    for name,step in steps.items():require(step['sha256']==report['artifacts'][step['log']],'step/artifact hash agreement')
    require(report['executable_sha256']==report['artifacts']['V'+TOP],'durable executable hash binding')
    sources=archive(local_file(root,'sources.tar.gz'),SOURCE_PINS);source_delta(sources)
    generated=archive(local_file(root,'generated-sources.tar.gz'))
    strict_equal({name:digest(payload) for name,payload in generated.items()},report['generated_source_sha256'],'generated member hashes')
    generated_contract(generated,local_file(root,'build.log').read_text())
    for tool in ('verilator','g++'):
        text=local_file(root,tool+'-version.log').read_text().strip()
        require(text==report[tool+'_version'],'raw version/report agreement')
    require(report['verilator_version']=='Verilator 5.032 2025-01-01 rev (Debian 5.032-1)' and
            report['g++_version'].startswith('g++ (Ubuntu 15.2.0-16ubuntu1) 15.2.0\n'),'reviewed native compiler versions')
    probe=json.loads(local_file(root,'probe.log').read_text());wanted=dict(context_threads=1,model_threads=1,lanes=64,p=PROFILE['p'],q=PROFILE['q'])
    strict_equal(probe,wanted,'raw compiled probe');strict_equal(report['probe'],wanted,'reported compiled probe')
    raw=local_file(root,'vectors.txt').read_bytes();require(digest(raw)==VECTOR_SHA,'frozen full vector bytes')
    coverage=audit_vectors(raw);strict_equal(report['vectors'],coverage,'regenerated vector coverage');strict_equal(manifest['vectors'],coverage,'manifest vector coverage')
    counts=check_normal(local_file(root,'normal.log').read_text(),expected_counts(coverage['cases']))
    strict_equal(report['normal_counts'],counts,'reported/raw normal counters')
    return dict(status='verified_component_pair',scope='Native frozen L64/P1 baseline/candidate paired two-state component only',
        profile=PROFILE,case_count=coverage['case_count'],checked_root_words=coverage['checked_root_words'],normal_counts=counts,
        source_members=len(sources),compiled_files=len(ORDER),generated_members=len(generated),artifacts=len(roles),
        report_sha256=sha(report_file),manifest_sha256=MANIFEST_SHA,source_archive_sha256=sha(local_file(root,'sources.tar.gz')),
        runner_sha256=RUNNER_SHA,verifier_sha256=sha(Path(__file__)),integer_oracle_sha256=SOURCE_PINS['reference/root_recurrence_proof.py'],
        vector_sha256=VECTOR_SHA,executable_sha256=report['executable_sha256'],
        pair_comparison='All eleven observable ports compared before/after both edges; exact pinned fatal checks, not message-presence inference.',
        limitation='No binary executed by this offline audit. One paired two-state component profile only: no whole-core integration, mutation qualification, FPGA fit/clock/board or PRP claim. Clocked reset depths and drain cancellation do not establish arbitrary asynchronous reset/release timing. Native tool hashes and prepared archive identity are receipt provenance, not offline tool reexecution or remote attestation.')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('archive',type=Path)
    parser.add_argument('--output',type=Path);args=parser.parse_args();result=verify(args.archive)
    payload=json.dumps(result,indent=2)+'\n'
    if args.output:
        require(not args.output.exists(),'fresh verification output')
        args.output.write_text(payload)
    print(payload,end='')


if __name__=='__main__':main()
