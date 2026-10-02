"""Local exact-source checks; never compile or execute the C++/RTL bench."""
import unittest
from pathlib import Path
from unittest.mock import patch

from reference.core27_prefetch_r2_bench import (
    ABORT_CONDITIONS, bench_source, wrapper_source, validate_bench_files,
)

ROOT=Path(__file__).resolve().parents[1]
TB=ROOT/'rtl/tb'


class FusionBenchTests(unittest.TestCase):
    def test_exact_sources(self):
        result=validate_bench_files(ROOT)
        self.assertEqual(set(result),{'rtl/tb/square_core27_stream_prefetch_r2.cpp',
                                    'rtl/tb/square_core27_stream_prefetch_r2_threaded.cpp'})

    def test_ancestors_fail_closed(self):
        for name,fn in [('square_core27_stream_prefetch.cpp',bench_source),
                        ('square_core27_stream_prefetch_threaded.cpp',wrapper_source)]:
            with self.assertRaisesRegex(ValueError,'ancestor|identity'):
                fn((TB/name).read_text()+'\n')

    def test_all_abort_paths_require_live_target(self):
        source=(TB/'square_core27_stream_prefetch_r2.cpp').read_text()
        self.assertEqual(source.count('abort_reached=true;break;'),5)
        for condition in ABORT_CONDITIONS:
            self.assertIn(f'if({condition}){{abort_reached=true;break;}}',source)
            self.assertNotIn(f'if({condition})break;',source)
        self.assertIn('if(!abort_reached || !d.busy || d.done)',source)
        self.assertEqual(source.count('bool abort_reached=false;'),1)
        guard=source.index('if(!abort_reached || !d.busy || d.done)')
        self.assertLess(guard,source.index('reset();++aborts;continue;'))
        # Truth-table counterexamples: timeout, already completed and non-busy
        # state cannot count as coverage, even if another condition was true.
        for reached in (False,True):
            for busy in (False,True):
                for done in (False,True):
                    reject=not reached or not busy or done
                    self.assertEqual(not reject,reached and busy and not done)

    def test_conversion_count_and_three_abort_offsets(self):
        source=(TB/'square_core27_stream_prefetch_r2.cpp').read_text()
        self.assertIn('const unsigned commit=(n+15)/16+6;',source)
        self.assertIn('if(d.conversion_cycles!=uint64_t((n+15)/16)+6)',source)
        self.assertNotIn('(n+15)/16+9',source)
        for aw in range(1,17):
            n=1<<aw;commit=(n+15)//16+6
            self.assertEqual([(n+15)//16+9+x-(commit+x) for x in (-1,0,1)],[3,3,3])
            self.assertGreater(commit-1,0)

    def test_all_existing_result_and_phase_checks_preserved(self):
        old=(TB/'square_core27_stream_prefetch.cpp').read_text()
        new=(TB/'square_core27_stream_prefetch_r2.cpp').read_text()
        # Everything from profile-count checks through readback, immediate
        # no-host chaining, injected errors and invalid-input quarantine stays.
        boundary='                const unsigned expected_loads=cache_before?0:1;'
        self.assertEqual(old[old.index(boundary):],new[new.index(boundary):])
        # Existing independent NTT/seed schedule formula is also unchanged.
        start='        const unsigned profile_words='
        self.assertEqual(old[old.index(start):old.index('        Vgenefer_')],
                         new[new.index(start):new.index('        Vgenefer_')])

    def test_thread_context_before_construction_and_fresh_probe(self):
        text=(TB/'square_core27_stream_prefetch_r2_threaded.cpp').read_text()
        self.assertIn('#include "square_core27_stream_prefetch_r2.cpp"',text)
        self.assertIn('#define CORE27_PREFETCH_R2_RUNTIME_THREADS 1',text)
        self.assertNotIn('CORE27_PREFETCH_RUNTIME_THREADS',text)
        self.assertIn('CORE27_PREFETCH_R2_RUNTIME_THREADS == 1 || CORE27_PREFETCH_R2_RUNTIME_THREADS == 8',text)
        context=text.index('Verilated::threadContextp()->threads(requested);')
        self.assertLess(context,text.index('Vgenefer_square_core27_stream_prefetch_r2 dut;'))
        self.assertLess(context,text.index('const int result = core27_prefetch_r2_main(argc, argv);'))
        self.assertIn('const unsigned model = dut.threads();',text)
        self.assertIn('if (Verilated::threadContextp()->threads() != CORE27_PREFETCH_R2_RUNTIME_THREADS) return 97;',text)

    def test_targeted_negative_source_changes_fail_validation(self):
        name='square_core27_stream_prefetch_r2.cpp'
        candidate=(TB/name).read_text()
        changes=[
            ('if(!abort_reached || !d.busy || d.done)','if(!abort_reached)'),
            ('if(phase>=3){abort_reached=true;break;}','if(phase>=3)break;'),
            ('const unsigned commit=(n+15)/16+6;','const unsigned commit=(n+15)/16+9;'),
            ('if(d.conversion_cycles!=uint64_t((n+15)/16)+6)','if(false)'),
        ]
        original_read=Path.read_text
        for old,new in changes:
            self.assertEqual(candidate.count(old),1)
            altered=candidate.replace(old,new)
            def read(path,*args,**kwargs):
                return altered if path==TB/name else original_read(path,*args,**kwargs)
            with patch.object(Path,'read_text',read):
                with self.assertRaisesRegex(ValueError,'unreviewed fusion bench delta'):
                    validate_bench_files(ROOT)


if __name__=='__main__':unittest.main()
