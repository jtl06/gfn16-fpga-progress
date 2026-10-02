import gzip
import hashlib
from pathlib import Path
import tempfile
import unittest
from fpga.reference import stream27_small_carry_regression as gate
from fpga.reference.stream27_small_carry_vectors import corpus

ROOT=Path(__file__).resolve().parents[1]


class NativePreparation(unittest.TestCase):
    def test_exact_oracle_corpus_and_independent_row_replay(self):
        for aw in (5,16):
            text,summary=corpus(aw)
            self.assertEqual(summary['sha256'],gate.VECTOR_SHA[aw])
            rows=text.splitlines();self.assertEqual(rows[0],f'SCELL1 {aw} 8 16 {summary["events"]}')
            n=1<<aw;K=2*n+192;Q=2*n+184;minimum=max(2*n+5,(2*K+2)//3+1)
            digit=None;carry_out=0;payload=None
            counted=dict(events=0,good=0,errors=0,bubbles=0,resets=0,feedback=0,carry_mask=0)
            immediate_release=False;previous_reset=False
            for line in rows[1:]:
                rst,valid,start,b,y,c,feedback,tag,ev,ee,ed,ec,ep=map(int,line.split())
                if feedback:self.assertEqual(c,carry_out);counted['feedback']+=1
                legal=(minimum<=b<=10**9 and -2<=c<=3 and -Q<=y<=2*(b-1)+Q and
                       (not start or 0<=y<b))
                expected_valid=expected_error=0
                if not rst:carry_out=0;counted['resets']+=1
                elif not valid:counted['bubbles']+=1
                else:
                    payload=tag
                    if legal:
                        carry_out,digit=divmod(y+(0 if start else c),b)
                        expected_valid=1;counted['good']+=1;counted['carry_mask']|=1<<(carry_out+2)
                    else:expected_error=1;counted['errors']+=1
                self.assertEqual((ev,ee,ed,ec,ep),(expected_valid,expected_error,
                    -1 if digit is None else digit,carry_out,-1 if payload is None else payload))
                immediate_release |= previous_reset and bool(rst and valid)
                previous_reset=not rst;counted['events']+=1
            self.assertEqual(counted,{k:summary[k] for k in counted})
            self.assertTrue(immediate_release)
            self.assertEqual(summary['carry_mask'],63)

    def test_footer_exact_counts_and_every_field_tampering(self):
        _,expected=corpus(16,feedback_length=8)
        keys=('aw','p','events','good','errors','bubbles','resets','feedback','carry_mask','before_checks','edge_checks')
        output='SMALL_CARRY_PASS '+' '.join(f'{key}={expected[key]}' for key in keys)+'\n'
        self.assertEqual(gate.check_output(output,expected),{k:expected[k] for k in keys})
        for key in keys:
            with self.assertRaisesRegex(ValueError,'coverage'):
                gate.check_output(output.replace(f'{key}={expected[key]}',f'{key}={expected[key]+1}',1),expected)
        with self.assertRaisesRegex(ValueError,'one component'):gate.check_output(output*2,expected)
        with self.assertRaisesRegex(ValueError,'unique'):gate.check_output(output.strip()+' aw=16\n',expected)

    def test_probe_exact_context_and_model(self):
        self.assertEqual(gate.check_probe('{"context_threads":1,"model_threads":1,"expected_threads":1}')['model_threads'],1)
        for bad in ('{"context_threads":8,"model_threads":1,"expected_threads":1}',
                    '{"context_threads":1,"model_threads":8,"expected_threads":1}', '{}'):
            with self.assertRaises(ValueError):gate.check_probe(bad)

    def test_closed_proof_and_native_source_pins(self):
        pins=gate.source_pins(ROOT)
        self.assertEqual(len(pins),17)
        self.assertEqual(pins[gate.RTL],'eafee617681cbd84cedfe90874938f63bf5ae84123ba1c914410785b44a3e74f')
        self.assertEqual(pins[gate.REVIEW],gate.REVIEW_SHA)
        self.assertIn(gate.BENCH,pins)
        self.assertIn(gate.RUNNER,pins)

    def test_cpp_edge_reset_feedback_and_return_contract(self):
        source=(ROOT/gate.BENCH).read_text()
        for text in ('VerilatedContext context;context.threads(1)', 'SCELL_EXTERNAL_FEEDBACK_BEFORE_EDGE',
                     'SCELL_ASYNC_OR_COMBINATIONAL_LEAK','SCELL_FALLING_EDGE_LEAK','SCELL_INTEGER_OR_EDGE_MISMATCH',
                     'before.valid=0;before.error=0;before.carry=0;',
                     'feedback?(unsigned(d.carry_out)&7):(unsigned(carry)&7)','d.final();return 0;'):
            self.assertIn(text,source)

    def test_compressed_executable_preserves_original_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/'exe';target=Path(folder)/'exe.gz';payload=b'\x7fELF'+bytes(range(256))*8192
            source.write_bytes(payload);identity=gate.archive_executable(source,target)
            self.assertEqual(gzip.decompress(target.read_bytes()),payload)
            self.assertEqual(identity['executable_sha256'],hashlib.sha256(payload).hexdigest())
            self.assertEqual(identity['gzip_sha256'],gate.sha(target))
            self.assertEqual(source.read_bytes(),payload)

    def test_explicit_bounded_component_controls(self):
        source=(ROOT/gate.RUNNER).read_text()
        for token in ("cpus==[4,6]",'int(memory)<=4*GIB','int(quota[0])<=2*int(quota[1])',
                      'resource.RLIMIT_AS,(4*GIB,4*GIB)','resource.RLIMIT_CORE,(0,0)',
                      '32*MIB','10*GIB','256*MIB','2*GIB',"CCACHE_DISABLE='1'",'-Werror=return-type',
                      "'source-only imports'",'time.monotonic()-before<300','time.monotonic()-started<900',
                      "LOCK.open('r')",'os.killpg',"manifest['compiled']==[RTL]"):
            self.assertIn(token,source)
        self.assertNotIn('-Wno',source)
        self.assertNotIn('build_cache',source)


if __name__=='__main__':unittest.main()
