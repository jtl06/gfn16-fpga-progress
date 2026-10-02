from pathlib import Path
from types import SimpleNamespace
from unittest import mock
import sys
import tempfile
import unittest

from fpga.reference import ntt27_prefetch_full_replay as gate


class FullReplayTests(unittest.TestCase):
    def test_reservation_tracks_own_allocations_not_other_jobs(self):
        self.assertEqual(gate.required_free(0,64<<20),10*gate.GiB+(964<<20))
        self.assertEqual(gate.required_free(100<<20,64<<20),10*gate.GiB+(864<<20))
        self.assertEqual(gate.required_free(1000<<20,64<<20),10*gate.GiB+(64<<20))
        with self.assertRaises(ValueError):gate.required_free(0,-1)

    def test_allocated_does_not_follow_external_symlink(self):
        with tempfile.TemporaryDirectory() as outer:
            root=Path(outer)/"new";root.mkdir()
            other=Path(outer)/"outside";other.write_bytes(b"x"*(1<<20))
            (root/"link").symlink_to(other)
            self.assertLess(gate.allocated_bytes(root),1<<20)

    def test_allocated_tolerates_removed_compiler_temporary(self):
        root=mock.Mock();root.rglob.return_value=[mock.Mock()]
        root.lstat.return_value=SimpleNamespace(st_dev=1,st_ino=2,st_blocks=8)
        root.rglob.return_value[0].lstat.side_effect=FileNotFoundError()
        self.assertEqual(gate.allocated_bytes(root),4096)

    def test_candidate_only_build_matches_legacy_profile(self):
        for field,(p,q) in enumerate(gate.base.FIELDS,1):
            argv=gate.candidate_command(field,Path("/fresh/model"),Path("/snapshot"),Path("/snapshot/bench.cpp"))
            for item in ("-GAW=16","-GLANES=64",f"-GP={p}",f"-GQ={q}"):self.assertIn(item,argv)
            self.assertEqual(argv[argv.index("-MAKEFLAGS")+1],"OPT_FAST=-Os OPT_SLOW= OPT_GLOBAL=-Os")
            self.assertEqual(argv[argv.index("--threads")+1],"1")
            self.assertEqual(argv[argv.index("-j")+1],"2")
            self.assertEqual(argv[argv.index("--prefix")+1],gate.base.PREFIX)
            self.assertIn("/snapshot/rtl/kernel/"+gate.TOP+".sv",argv)
            self.assertNotIn(str(gate.base.OLD_ROOT/"rtl/kernel/genefer_ntt_banked27_prefetch_engine.sv"),argv)
            self.assertEqual(len([x for x in argv if x.endswith(".sv")]),7)

    def test_actual_compile_log_rejects_overridden_slow_optimization(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp);prefix=gate.base.PREFIX
            (directory/(prefix+"_classes.mk")).write_text("VM_CLASSES_FAST += \\\n  fast\nVM_CLASSES_SLOW += slow\nVM_GLOBAL_FAST += verilated\nVM_GLOBAL_FAST += verilated_threads\n")
            (directory/(prefix+".cpp")).write_text(f"unsigned {prefix}::threads() const {{ return 1; }}")
            rows=[]
            for name in ("fast","slow","verilated","verilated_threads","ntt_banked27_prefetch_data27_engine"):
                opt="" if name=="slow" else "-Os"
                rows.append(f"g++ {opt} -DNTT_LANES=64 -DNTT_AW=16 -DNTT_P=104857601u -c -o {name}.o {name}.cpp")
            log=directory/"build.log";log.write_text("\n".join(rows))
            self.assertEqual(len(gate.verify_build_profile(directory,log,1)["actual_compile_commands"]),5)
            log.write_text("\n".join(rows).replace("g++  -D","g++ -O1 -D"))
            with self.assertRaisesRegex(RuntimeError,"optimization"):gate.verify_build_profile(directory,log,1)
            log.write_text("\n".join(rows[:-1]))
            with self.assertRaisesRegex(RuntimeError,"missing classes"):gate.verify_build_profile(directory,log,1)

    def test_pair_never_strips_counters_or_whitespace(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths=[Path(tmp)/str(i) for i in range(4)]
            content=b"RUN "+b" ".join(c+b"1" for c in gate.COUNTERS)+b"\nPASS runs=1 checks=1 aborts=0\n"
            for path in paths[:2]:path.write_bytes(content)
            for path in paths[2:]:path.write_bytes(b"1 2 3\n")
            self.assertEqual(gate.equal_pair(*paths)["runs"],1)
            paths[1].write_bytes(content.replace(b"cycles=1",b"cycles=2"))
            with self.assertRaisesRegex(RuntimeError,"stdout"):gate.equal_pair(*paths)
            paths[1].write_bytes(content);paths[3].write_bytes(b"1 2 3 \n")
            with self.assertRaisesRegex(RuntimeError,"residue"):gate.equal_pair(*paths)
            for path in paths[:2]:path.write_bytes(content.replace(b"wait_cycles=1",b""))
            with self.assertRaisesRegex(RuntimeError,"counters"):gate.equal_pair(*paths)

    def test_all_93_pairs_and_24_faults_keep_host_fuzz_and_high_bits(self):
        cases=[]
        for field in (1,2,3):
            for name in gate.base.expected_cases(field):
                cases.append({"field":field,"name":name,"vector":"/old/"+name,"sha256":"pinned",
                    "host_fuzz":name==f"transform-p{field}-aw16-n65536"})
        with tempfile.TemporaryDirectory() as tmp:
            job=gate.Executor(Path(tmp),0);calls=[]
            def run(name,command,timeout=600,reasons=()):
                calls.append((name,command,tuple(reasons)));return Path(tmp)/(name+".log")
            job.run=run;job.save=lambda:None
            models={f:(Path(f"/baseline{f}"),Path(f"/candidate{f}")) for f in (1,2,3)}
            with mock.patch.object(gate.base,"sha",return_value="pinned"),mock.patch.object(gate,"equal_pair",return_value={}):
                job.replay({"cases":cases},models)
            self.assertEqual(len(job.report["matched_cases"]),93)
            self.assertEqual(len(calls),210)
            normal=calls[:186];faults=calls[186:]
            self.assertEqual(sum(c[1][0]!="env" for c in normal),6)
            self.assertEqual(sum(c[1][0:2]==["env","NTT_SKIP_HOST_FUZZ=1"] for c in normal),180)
            for name,command,reasons in faults:
                self.assertTrue(command[1].startswith("NTT_NONCANON="))
                self.assertEqual(len(reasons),2 if "candidate" in name and name.endswith("-high") else 1)
                self.assertIn("noncanonical NTT27 data write",reasons)

    def test_disk_shortfall_fails_before_process_dispatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            job=gate.Executor(Path(tmp),64<<20)
            with mock.patch.object(gate.shutil,"disk_usage",return_value=SimpleNamespace(free=10*gate.GiB+(900<<20))),mock.patch.object(gate.subprocess,"Popen") as popen:
                with self.assertRaisesRegex(RuntimeError,"disk floor"):job.run("unused",["not-run"])
                popen.assert_not_called()

    def test_relink_never_builds_in_old_tree_and_copies_commands(self):
        row={"field":2,"directory":"/old/model","original_executable_sha256":"expected",
            "link_line":f"g++ oldbench.o verilated.o verilated_threads.o {gate.base.PREFIX}__ALL.a -pthread -lpthread -latomic -o {gate.base.PREFIX}",
            "compile_line":"g++ -I. -Os -c -o oldbench.o /old/bench.cpp"}
        with tempfile.TemporaryDirectory() as tmp:
            job=gate.Executor(Path(tmp),0);commands=[]
            job.run=lambda name,command,timeout:commands.append(list(command))
            from contextlib import nullcontext
            job.compile_lock=nullcontext
            with mock.patch.object(gate.base,"recheck"),mock.patch.object(gate.base,"sha",return_value="expected"):
                exe=job.relink(row,Path("/snapshot/newbench.cpp"),{})
            self.assertEqual(len(commands),3)
            self.assertTrue(commands[0][-1].endswith("original-reproduced"))
            self.assertTrue(commands[2][-1].endswith("baseline-diagnostic"))
            self.assertIn("-I/old/model",commands[1])
            self.assertEqual(commands[1][-1],"/snapshot/newbench.cpp")
            self.assertTrue(str(exe).startswith(tmp))
            for command in commands:self.assertNotIn("make",command)


if __name__=="__main__":unittest.main()
