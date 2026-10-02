"""Independent whole-integer oracle for autonomous RTL squareDup. Aethia only."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import random
import re
import shlex
import shutil
import signal
import subprocess
import sys
import sysconfig
import time


def pack(digits,base):
    """Divide-and-conquer radix conversion, independent of RNS/NTT/carry RTL."""
    if len(digits)==1:return digits[0]
    half=len(digits)//2
    return pack(digits[:half],base)+pow(base,half)*pack(digits[half:],base)


def unpack(value,base,n):
    if n==1:return [value]
    half=n//2
    high,low=divmod(value,pow(base,half))
    return unpack(low,base,half)+unpack(high,base,half)


def write_vectors(path,aw,seed,prefix_carry=False,stream_carry=False):
    n=1<<aw;rng=random.Random(seed+aw);lines=[str(n)];case_count=0;readback_count=0;fermat_chains=[]
    def load(label,base,digits,keep=False):
        command="LOAD_KEEP" if keep else "LOAD"
        lines.extend((f"{command} {label} {base}"," ".join(map(str,digits))))
    def scenario(label,base,digits,bits,keep=False,readback_each=True):
        nonlocal case_count,readback_count
        load(label,base,digits,keep)
        modulus=pow(base,n)+1;x=pack(digits,base)%modulus
        for step,bit in enumerate(bits):
            x=x*x*(2 if bit else 1)%modulus
            expected=[-1]+[0]*(n-1) if x==modulus-1 else unpack(x,base,n)
            checked=readback_each or step==len(bits)-1
            command="RUN" if checked else "RUN_NOREAD"
            lines.extend((f"{command} {label}-s{step}-d{bit} {bit}"," ".join(map(str,expected))))
            case_count+=1
            readback_count+=int(checked)
        return x
    lines.extend(("BADBASE 0","BADBASE 1","BADBASE 1000000001",
                  "BADDIGIT 1000000000 -2","BADDIGIT 1000000000 1000000000"))
    for bad_at in (range(n) if aw<=5 else (0,n-1)):
        lines.append(f"BADDIGIT_AT 1000000000 -2 {bad_at}")
    minimum_base=2*n+5 if prefix_carry else 2
    if prefix_carry:lines.extend((f"BADBASE {2*n+4}",f"BADBASE {2*n+3}","BADBASE 2"))
    if aw<=5:
        for base in (minimum_base,minimum_base+1,97,604832956,1000000000):
            patterns={"zero":[0]*n,"one":[1]+[0]*(n-1),"minusone":[-1]+[0]*(n-1),
                "max":[base-1]*n,"alternating":[(base-1)*(i%2) for i in range(n)],
                "high":[0]*(n-1)+[base-1],"random":[rng.randrange(base) for _ in range(n)]}
            for name,digits in patterns.items():scenario(f"b{base}-{name}",base,digits,(0,1,1))
        if aw==1:
            for base in (minimum_base,minimum_base+1):
                for x in range(base**n+1):
                    digits=[-1]+[0]*(n-1) if x==base**n else unpack(x,base,n)
                    scenario(f"exhaust-b{base}-x{x}",base,digits,(0,1))
        abort_phases=("conversion","root","ntt","crt","carry","root0","root1","root2","root3")
        if stream_carry and aw==5:abort_phases+=("crt-active",)
        for phase in abort_phases:
            load("abort-"+phase,97,[rng.randrange(97) for _ in range(n)])
            lines.append(f"ABORT {phase} 1")
            # Reset from ABORT must invalidate any partially or fully filled
            # phase cache; reload data without another reset and run immediately.
            scenario("recovered-"+phase,97,[rng.randrange(97) for _ in range(n)],(0,1),keep=True)
        scenario("after-aborts",97,[rng.randrange(97) for _ in range(n)],(0,1))
        for base in (minimum_base,604832956,1000000000,97):
            scenario(f"no-reset-b{base}",base,[rng.randrange(base) for _ in range(n)],(0,1),keep=True)
        even_base=minimum_base+(minimum_base%2)
        for base in (even_base,even_base+1):
            exponent=pow(base,n);bits=tuple(map(int,bin(exponent)[2:]))
            residue=scenario(f"fermat-b{base}",base,[1]+[0]*(n-1),bits,keep=True)
            direct=pow(2,exponent,exponent+1)
            if residue!=direct:raise AssertionError("Fermat squareDup chain disagrees with direct pow")
            fermat_chains.append({"base":base,"steps":len(bits),"residue_hex":hex(direct)})
    else:
        base=604832956
        scenario("full-random",base,[rng.randrange(base) for _ in range(n)],(0,1,1,0,1))
        scenario("full-minusone",base,[-1]+[0]*(n-1),(1,0))
        scenario("full-max-b1000000000",1000000000,[999999999]*n,(0,1),keep=True)
    chain_base=97 if aw<=5 else 604832956
    chain_bits=(0,1,1,0,1,0,0,1) if aw<=5 else (0,1,1)
    scenario("no-host-chain",chain_base,[rng.randrange(chain_base) for _ in range(n)],
             chain_bits,keep=True,readback_each=False)
    path.write_text("\n".join(lines)+"\n")
    return {"squares":case_count,"readbacks":readback_count,"seed":seed,"fermat_chains":fermat_chains,"sha256":hashlib.sha256(path.read_bytes()).hexdigest()}


def collect_metrics(output):
    metrics=[]
    pattern=re.compile(r"^(\S+) cycles=(\d+) conversion=(\d+) roots=(\d+) ntt=(\d+) crt=(\d+) carry=(\d+) passes=(\d+)(?: base=(\d+))?(?: cache_before=(\d+) root_loads=(\d+) root_hits=(\d+))?(?: readback=(\d+))?$")
    for path in sorted(output.glob("test-aw*.log")):
        aw=int(path.stem.removeprefix("test-aw"))
        for line in path.read_text().splitlines():
            match=pattern.fullmatch(line)
            if match:
                values=dict(zip(("cycles","conversion","roots","ntt","crt","carry","passes"),map(int,match.groups()[1:8])))
                if values["cycles"]!=sum(values[k] for k in ("conversion","roots","ntt","crt","carry")):
                    raise RuntimeError("phase accounting mismatch in log "+line)
                cache_before=int(match[10]) if match[10] else None
                metrics.append({"aw":aw,"n":1<<aw,"base":int(match[9]) if match[9] else None,"case":match[1],
                    "cache_before":cache_before,"root_cache_warm":cache_before==15 if cache_before is not None else None,
                    "root_loads":int(match[11]) if match[11] else None,"root_hits":int(match[12]) if match[12] else None,
                    "readback":bool(int(match[13])) if match[13] is not None else None,**values})
    return metrics


def cache_context(directory):
    """Conservative toolchain closure; unkeyed compiler overrides fail closed."""
    from .build_cache import BuildCache, fingerprint_toolchain
    overrides=("CC CXX AS LD AR ARFLAGS RANLIB CPPFLAGS CFLAGS CXXFLAGS LDFLAGS LD_PRELOAD LD_AUDIT LD_LIBRARY_PATH LD_RUN_PATH LIBRARY_PATH "
        "CPATH C_INCLUDE_PATH CPLUS_INCLUDE_PATH OBJC_INCLUDE_PATH MAKEFLAGS MFLAGS GNUMAKEFLAGS MAKEFILES "
        "GCC_EXEC_PREFIX COMPILER_PATH PERL5LIB PERLLIB PERL5OPT").split()
    overrides += [k for k in os.environ if k.startswith(("CCACHE_","DISTCC_","GCC_","VERILATOR_","PYTHON"))
                  and k!="VERILATOR_ROOT"]
    unsupported=sorted({k for k in overrides if os.environ.get(k)})
    if unsupported:
        raise RuntimeError("cached mode does not fingerprint custom tool overrides: "+", ".join(unsupported))
    compiler=shutil.which("g++")
    if compiler is None:raise RuntimeError("g++ unavailable")
    def compiler_path(option):
        return Path(subprocess.check_output([compiler,option],text=True).strip()).resolve()
    files=[Path("/bin/sh"),compiler_path("-print-prog-name=cc1plus"),compiler_path("-print-prog-name=collect2")]
    for name in ("libstdc++.so","libgcc_s.so.1","libgcc.a","libc.so","libc.so.6",
                 "libm.so","libm.so.6","libatomic.so","libpthread.so.0",
                 "crtbeginS.o","crtendS.o","crti.o","crtn.o","Scrt1.o"):
        path=compiler_path("-print-file-name="+name)
        if path.exists():files.append(path)
    # verilator_includer lives in bin/ and is executed with Python, not Perl.
    # Hash interpreter module trees too, rather than relying only on versions.
    trees=[Path("/usr/include"),compiler_path("-print-file-name=include"),
           Path(os.environ["VERILATOR_ROOT"]),Path(sysconfig.get_path("stdlib"))]
    perl_roots=subprocess.check_output(["perl","-e",'print join("\\n", @INC)'],text=True).splitlines()
    trees.extend(Path(p) for p in perl_roots if Path(p).is_dir())
    fixed=compiler_path("-print-file-name=include-fixed")
    if fixed.is_dir():trees.append(fixed)
    commands={
        "verilator":["verilator","-V"],"verilator_bin":["verilator_bin","--version"],
        "compiler":[compiler,"--version"],"compiler_specs":[compiler,"-dumpspecs"],
        "make":["make","--version"],"assembler":["as","--version"],
        "linker":["ld","--version"],"archiver":["ar","--version"],
        "ranlib":["ranlib","--version"],"verilator_interpreter":["perl","-V"],
        "includer_interpreter":["python3","--version"],"dynamic_dependencies":["ldd","--version"],
        "compile_lock":["flock","--version"],
    }
    # Include transitive shared libraries of trusted installed build tools.
    # A library update must invalidate a hit even if --version stays unchanged.
    binaries=[*files,*(Path(shutil.which(cmd[0])) for cmd in commands.values())]
    libraries=set()
    for binary in binaries:
        result=subprocess.run(["ldd",str(binary)],capture_output=True,text=True,timeout=30)
        for word in result.stdout.split():
            if word.startswith("/") and Path(word).is_file():libraries.add(Path(word))
    files.extend(sorted(libraries))
    toolchain=fingerprint_toolchain(commands,files=files,trees=sorted(set(trees)))
    toolchain["platform"]={"system":platform.system(),"machine":platform.machine(),"python":platform.python_version()}
    names=set(overrides+"PATH LD_LIBRARY_PATH VERILATOR_ROOT SOURCE_DATE_EPOCH LANG LC_ALL TZ".split())
    names.update(k for k in os.environ if k.startswith("LC_"))
    environment={k:os.environ.get(k) for k in sorted(names)}
    return BuildCache(directory,log=lambda message:print(message,flush=True)),toolchain,environment


def main():
    ap=argparse.ArgumentParser();ap.add_argument("--output",type=Path,required=True)
    ap.add_argument("--aw",type=int,nargs="+",default=[1,3,5,16]);ap.add_argument("--seed",type=int,default=20260929)
    ap.add_argument("--mutations",action="store_true")
    ap.add_argument("--mutation-opt",type=int,choices=[0,1,2,3],help="optional C++ optimization override for fault models only; normal RTL builds stay unchanged")
    ap.add_argument("--build-cache",type=Path,help="opt-in verified executable cache; all correctness oracles still run")
    ap.add_argument("--command-timeout",type=int,default=600,help="bounded seconds per compile/oracle subprocess (default600)")
    ap.add_argument("--compile-lock",type=Path,help="optional shared flock file serializing two-thread compiles while independent oracles overlap")
    ap.add_argument("--difdit",action="store_true",help="use opt-in DIF forward / DIT inverse engine")
    ap.add_argument("--lanes",type=int,choices=[1,2,4,8,16,64],default=1,help="NTT compute lanes;64 requires fast vector IO with16 carry lanes")
    ap.add_argument("--prefix-carry",action="store_true",help="compile bounded-domain prefix carry and test explicit small-base rejection")
    ap.add_argument("--root-cache",action="store_true",help="keep four root phases resident across squares; requires --difdit")
    ap.add_argument("--banked-ntt",action="store_true",help="use bank-centric cached NTT; requires --difdit and --root-cache")
    ap.add_argument("--carry-lanes",type=int,choices=[1,2,4,8,16],default=1,help="prefix carry lanes; >1 requires --prefix-carry")
    ap.add_argument("--vector-io",action="store_true",help="matching-width internal conversion/CRT transfers; requires banked cached NTT and prefix carry")
    ap.add_argument("--fast-arith",action="store_true",help="shared/predecoded NTT and pipelined narrow carry; requires --vector-io")
    ap.add_argument("--fuse-input-mont",action="store_true",help="ordinary input register plus R-squared twist roots; current31-bit profile, requires --fast-arith")
    ap.add_argument("--stream-carry",action="store_true",help="start carry during NTT and stream CRT groups without coefficient staging RAM; requires fast vector IO at4/16 carry lanes")
    ap.add_argument("--summarize-only",action="store_true",help="add parsed metrics to an existing run without rerunning simulations")
    args=ap.parse_args()
    if args.command_timeout<1:ap.error("--command-timeout must be positive")
    if args.lanes>1 and not args.difdit:ap.error("--lanes >1 requires --difdit")
    if args.root_cache and not args.difdit:ap.error("--root-cache requires --difdit")
    if args.banked_ntt and not (args.root_cache and args.difdit):ap.error("--banked-ntt requires --root-cache and --difdit")
    if args.lanes>8 and not args.banked_ntt:ap.error("--lanes >8 requires --banked-ntt")
    if args.carry_lanes>1 and not args.prefix_carry:ap.error("--carry-lanes >1 requires --prefix-carry")
    host_adapter=args.fast_arith and args.vector_io and args.lanes==64 and args.carry_lanes==16
    if args.lanes==64 and not host_adapter:ap.error("--lanes 64 requires --fast-arith --vector-io --carry-lanes 16")
    if args.vector_io and not (args.banked_ntt and args.root_cache and args.prefix_carry and (args.lanes==args.carry_lanes or host_adapter) and args.carry_lanes>1):ap.error("--vector-io requires banked cached NTT, prefix carry and matching lanes >1, or verified fast64/16 profile")
    if args.fast_arith and not args.vector_io:ap.error("--fast-arith requires --vector-io")
    if args.fuse_input_mont and not (args.fast_arith and args.vector_io):ap.error("--fuse-input-mont requires --fast-arith and --vector-io")
    if args.stream_carry and not (args.fast_arith and args.vector_io and args.carry_lanes in (4,16)):ap.error("--stream-carry requires fast vector IO with4 or16 carry lanes")
    if platform.system()!="Linux" or platform.node()!="aethia":raise SystemExit("Run on aethia only")
    root=Path(__file__).resolve().parents[1];out=args.output.resolve()
    if args.summarize_only:
        report=json.loads((out/"report.json").read_text())
        report["metrics"]=collect_metrics(out)
        report["metrics_parser_sha256"]=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        (out/"report.json").write_text(json.dumps(report,indent=2)+"\n")
        print("Parsed",len(report["metrics"]),"case metrics",flush=True)
        return
    out.mkdir(parents=True,exist_ok=False)
    src=[root/"rtl/kernel"/f"{name}.sv" for name in ("genefer_montgomery_mul32_pipe","genefer_ntt_butterfly32",
        "genefer_ntt_stream_engine","genefer_ntt_difdit_engine","genefer_ntt_parallel_engine","genefer_ntt_parallel_cached_engine","genefer_ntt_banked_engine","genefer_sdp_ram32","genefer_ntt_banked_modulemem_engine","genefer_root_stream32","genefer_mod64_pipe","genefer_crt3_pipe",
        "genefer_carry_fast","genefer_div96_recip_prefix","genefer_carry_prefix","genefer_carry_transfer_tree","genefer_carry_prefix_wide","genefer_sp_ram","genefer_carry_prefix_wide_ram","genefer_ntt_banked_vector_engine","genefer_carry_prefix_vector_ram","genefer_ntt_banked_shared_engine","genefer_div_recip_narrow","genefer_carry_prefix_vector_pipe_v2","genefer_ntt_banked_wide_engine","genefer_ntt_banked_host_engine","genefer_root_stream32_r2","genefer_carry_prefix_stream","genefer_square_core")]
    cpp=root/"rtl/tb/square_core.cpp"
    report={"host":platform.node(),"status":"running","configuration":{"difdit":args.difdit,"ntt_lanes":args.lanes,"prefix_carry":args.prefix_carry,"root_cache":args.root_cache,"banked_ntt":args.banked_ntt,"carry_lanes":args.carry_lanes,"vector_io":args.vector_io,"fast_arith":args.fast_arith,"io_lanes":args.carry_lanes if args.vector_io else 1,"host_adapter":host_adapter},"sources":{str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in src+[cpp,Path(__file__)]},"vectors":{},"steps":[]}
    report["configuration"]["fuse_input_mont"]=args.fuse_input_mont
    report["configuration"]["stream_carry"]=args.stream_carry
    report["montgomery_radix_bits"]=32
    report["command_timeout_seconds"]=args.command_timeout
    report["compile_lock"]=str(args.compile_lock.resolve()) if args.compile_lock else None
    if args.compile_lock:args.compile_lock.resolve().parent.mkdir(parents=True,exist_ok=True)
    if args.build_cache:
        report["build_cache"]=[]
        for path in (root/"reference/build_cache.py",root/"tests/test_build_cache.py"):
            report["sources"][str(path.relative_to(root))]=hashlib.sha256(path.read_bytes()).hexdigest()
    parameters=[f"-GDIFDIT=1'b{int(args.difdit)}",f"-GNTT_LANES={args.lanes}",f"-GPREFIX_CARRY=1'b{int(args.prefix_carry)}",f"-GROOT_CACHE=1'b{int(args.root_cache)}",f"-GBANKED_NTT=1'b{int(args.banked_ntt)}",f"-GCARRY_LANES={args.carry_lanes}",f"-GVECTOR_IO=1'b{int(args.vector_io)}",f"-GFAST_ARITH=1'b{int(args.fast_arith)}"]
    parameters.append(f"-GFUSE_INPUT_MONT=1'b{int(args.fuse_input_mont)}")
    parameters.append(f"-GSTREAM_CARRY=1'b{int(args.stream_carry)}")
    simulation_args=["cache"] if args.root_cache else []
    def run(name,cmd,reject=None):
        then=time.monotonic()
        proc=subprocess.Popen(cmd,cwd=root,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,start_new_session=True)
        try:stdout,_=proc.communicate(timeout=args.command_timeout)
        except subprocess.TimeoutExpired:
            # Also stop make/compiler children and release any inherited flock;
            # never leave an orphaned compile writing a discarded private stage.
            try:os.killpg(proc.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            stdout,_=proc.communicate()
            (out/f"{name}.log").write_text(stdout)
            report["steps"].append({"name":name,"command":cmd,"returncode":proc.returncode,
                "seconds":time.monotonic()-then,"timed_out":True,"expected_rejection":reject})
            raise RuntimeError(name+" timed out")
        (out/f"{name}.log").write_text(stdout)
        report["steps"].append({"name":name,"command":cmd,"returncode":proc.returncode,"seconds":time.monotonic()-then,"expected_rejection":reject})
        print(name,proc.returncode,stdout[-1800:],flush=True)
        if reject is None:
            if proc.returncode:raise RuntimeError(name+" failed")
        else:
            diagnostics=reject if isinstance(reject,list) else [reject]
            if proc.returncode!=1 or not any(message in stdout for message in diagnostics):
                raise RuntimeError(name+" did not detect the injected fault")
    cache=None
    def build(name,aw,sources,directory,extra=()):
        flags=["--cc","--exe","--build","-j","2","--top-module","genefer_square_core",f"-GAW={aw}",*parameters,*extra]
        def compile_into(target):
            command=["verilator",*flags,"--Mdir",str(target),*map(str,sources),str(cpp)]
            if args.compile_lock:
                command=["flock","--timeout",str(args.command_timeout),str(args.compile_lock.resolve()),*command]
            run(name,command)
        if cache is None:
            compile_into(directory)
            return str(directory/"Vgenefer_square_core")
        from .build_cache import BuildSpec,BuildProduct
        ordered=[*sources,cpp]
        spec=BuildSpec.capture(sources={f"source_{k:02}":p for k,p in enumerate(ordered)},
            configuration={"flags":flags,"ordered_sources":list(map(str,ordered)),"cwd":str(root),
                           "build_directory":"<private-stage>","executable":"Vgenefer_square_core"},
            toolchain=toolchain,environment=environment)
        def cached_compile(target):
            compile_into(target)
            dependencies=set()
            for depfile in target.glob("*.d"):
                content=depfile.read_text().replace(chr(92)+chr(10)," ")
                for rule in content.splitlines():
                    if ":" not in rule:continue
                    for word in shlex.split(rule.split(":",1)[1]):
                        path=Path(word);dependencies.add(path if path.is_absolute() else target/path)
            return BuildProduct("Vgenefer_square_core",tuple(dependencies))
        result=cache.obtain(spec,cached_compile)
        record={"name":name,"key":result.key,"status":result.cache_status,
                "executable_sha256":result.executable_sha256,"manifest":str(result.manifest)}
        report["build_cache"].append(record)
        (out/f"{name}-cache.json").write_text(json.dumps(record,indent=2)+"\n")
        return str(result.executable)
    try:
        if args.build_cache:
            run("build-cache-unit-tests",[sys.executable,"-m","unittest","tests.test_build_cache","-v"])
            cache,toolchain,environment=cache_context(args.build_cache)
        for aw in args.aw:
            vfile=out/f"vectors-aw{aw}.txt";report["vectors"][str(aw)]=write_vectors(vfile,aw,args.seed,args.prefix_carry,args.stream_carry)
            exe=build(f"build-aw{aw}",aw,src,out/f"build-aw{aw}")
            run(f"test-aw{aw}",[exe,str(vfile),*simulation_args])
        if args.mutations:
            # An aligned-address perturbation must move to a distinct group.
            # N<width has only one group; advancing by IO_STEP would wrap back
            # to the same AW-bit address and produce an equivalent mutant.
            mutation_aw=max(3,args.carry_lanes.bit_length()) if args.vector_io else 3
            vfile=out/"mutation-vectors.txt";write_vectors(vfile,mutation_aw,args.seed,args.prefix_carry,args.stream_carry)
            report["mutation_aw"]=mutation_aw
            report["mutation_cpp_opt"]=args.mutation_opt
            mutation_options=["-CFLAGS",f"-O{args.mutation_opt}"] if args.mutation_opt is not None else []
            # This fault specifically requires an immediate start after done.
            # Isolate the same independently generated chain rather than run
            # hundreds of unrelated earlier cases in an unoptimized model.
            chain_lines=vfile.read_text().splitlines()
            chain_start=next(i for i,line in enumerate(chain_lines) if line.startswith("LOAD_KEEP no-host-chain "))
            chain_file=out/"mutation-immediate-chain.txt"
            chain_file.write_text("\n".join([chain_lines[0],*chain_lines[chain_start:]])+"\n")
            mutations=[
                ("double", "carry_input=double_reg ? (coefficient <<< 1) : coefficient", "carry_input=coefficient", "square mismatch"),
                ("inverse-root", "step==3 ? 2'd2 : 2'd3", "step==3 ? 2'd1 : 2'd3", "square mismatch"),
                ("coefficient-address", "carry_load=!VECTOR_IO; carry_addr=AW'(write_count)", "carry_load=!VECTOR_IO; carry_addr=AW'(write_count+1)", "square mismatch"),
                ("convert", ".rhs(R2[f])", ".rhs(32'd1)", "square mismatch"),
                ("immediate-start", "IDLE: if(start) begin", "IDLE: if(start && !done) begin", "start mismatch"),
            ]
            if args.vector_io:
                mutations[0]=("double","double_reg ? (coefficient_words[h] <<< 1) : coefficient_words[h]","coefficient_words[h]","square mismatch")
                mutations[2]=("coefficient-address","assign carry_vector_addr=state==CONVERT ? AW'(issue_count) : AW'(write_count)","assign carry_vector_addr=state==CONVERT ? AW'(issue_count) : AW'(write_count+IO_STEP)","completion mismatch")
                mutations.extend([
                    ("conversion-word", "assign ordinary=carry_words[h]==-96'sd1 ? P[f]-1 : carry_words[h][31:0]", "assign ordinary=carry_words[0]==-96'sd1 ? P[f]-1 : carry_words[0][31:0]", "square mismatch"),
                    ("crt-word", "double_reg ? (coefficient_words[h] <<< 1) : coefficient_words[h]", "double_reg ? (coefficient_words[0] <<< 1) : coefficient_words[0]", "square mismatch"),
                    ("digit-word", "convert_input_valid && convert_mask[h] && carry_words[h]", "convert_input_valid && convert_mask[h] && h==0 && carry_words[h]", "invalid digit accepted"),
                    ("start-host", "if(state==IDLE && !start)", "if(state==IDLE)", "square mismatch"),
                    ("busy-read", "assign read_valid=state==IDLE && carry_valid", "assign read_valid=carry_valid || carry_vector_valid", "busy host read leaked"),
                ])
            if args.fuse_input_mont:
                # The old input multiplier is not instantiated in this profile.
                # Corrupt the matching root format instead of testing dead logic.
                mutations=[("convert", "genefer_root_stream32_r2 #", "genefer_root_stream32 #", reject)
                           if name=="convert" else (name,old,new,reject)
                           for name,old,new,reject in mutations]
            if args.stream_carry:
                mutations.extend([
                    ("stream-start", "state==CONVERT && (&conversion_valid) && int'(write_count)==N-IO_STEP", "1'b0", "completion mismatch"),
                    ("stream-mask", ".stream_mask(IO_MASK)", ".stream_mask(IO_MASK ^ {{(IO_WIDTH-1){1'b0}},1'b1})", "completion mismatch"),
                    ("stream-last", ".stream_valid(state==RESIDUES && crt_valid)", ".stream_valid(state==RESIDUES && crt_valid && int'(write_count)!=N-IO_STEP)", "completion mismatch"),
                ])
            if args.prefix_carry:
                # Corrupt arithmetic may either produce a wrong residue or be
                # rejected by the bounded-domain carry's coefficient guard.
                mutations=[(name,old,new,[reject,"square mismatch","completion mismatch"]) for name,old,new,reject in mutations]
                mutations.append(("prefix-domain","(PREFIX_CARRY && base <= 32'(2*N+4))","1'b0","invalid base accepted"))
            if args.root_cache:
                mutations=[(name,old,new,([*reject,"cache contract mismatch"] if isinstance(reject,list) else [reject,"cache contract mismatch"])) for name,old,new,reject in mutations]
                mutations.extend([
                    ("cache-reset","root_phases_loaded<=0; root_cache_hits<=0; root_cache_valid<=0;",
                        "root_phases_loaded<=0; root_cache_hits<=0; root_cache_valid<=15;","cache reset mismatch"),
                    ("cache-premature","if(ROOT_CACHE) root_cache_valid[root_phase]<=1'b1;",
                        "if(ROOT_CACHE) root_cache_valid<=15;","cache contract mismatch"),
                    ("cache-reload","ROOT_CACHE && root_cache_valid[0]","1'b0","cache contract mismatch"),
                ])
            for name,old,new,reject in mutations:
                mdir=out/f"mutation-{name}";mdir.mkdir()
                content=src[-1].read_text()
                if content.count(old)!=1:raise RuntimeError("mutation anchor mismatch: "+name)
                modified=mdir/src[-1].name;modified.write_text(content.replace(old,new))
                exe=build(f"mutation-{name}-build",mutation_aw,[*src[:-1],modified],mdir/"build",mutation_options)
                fault_vectors=chain_file if name=="immediate-start" else vfile
                run(f"mutation-{name}-reject",[exe,str(fault_vectors),*simulation_args],reject=reject)
        report["status"]="passed"
    except BaseException:
        report["status"]="failed"
        raise
    finally:
        report["metrics"]=collect_metrics(out)
        (out/"report.json").write_text(json.dumps(report,indent=2)+"\n")

if __name__=="__main__":main()
