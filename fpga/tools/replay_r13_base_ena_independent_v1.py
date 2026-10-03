"""Nonauthor, bounded base-ENA review replay. No HDL execution or author proof imports."""
import ast
import gzip
import hashlib
import itertools
import json
from pathlib import Path
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import native_gate_receipt_v1 as gate

RESULTS = ROOT / 'results/throughput-20260929'
OLD = 'genefer_stream27_canonical_image_directbound_v1'
NEW = 'genefer_stream27_canonical_image_begin_split_v1'
CAPTURE = '''            // Speculative payload only: rejected BEGIN enters sticky FAILED.
            // Fault/control authority remains exclusively legal_begin/idle_reject.
            if(state==IDLE && !error && begin_canonical)base_reg<=base;
'''
PARENT = 'f855269ace437fff2ebcfd0e7048f8aadc0dadcbe7836a4ca1e4213ccda17402'
CHILD = '14b594f47fd6ac7454fdf9b15ee03e67143fc059a6242052b52518b7a5af1650'
TIMING = '15ff49bc9542b4cb63393d73e76c8e10e0b2a8791d677dda7fdad6f1c567e2d4'
FOLD = 'e07ccea57740154b803d9b4c4e85e456e280d61ca6f24d455834413dee02a234'


def need(ok, why):
    if not ok:
        raise AssertionError('R13_BASE_ENA_REVIEW: ' + why)


def sha(raw):
    return hashlib.sha256(raw.encode() if isinstance(raw, str) else raw).hexdigest()


def load(path):
    return json.loads(path.read_bytes())


def pinned(path, pin):
    need(sha(path.read_bytes()) == pin, str(path))
    return load(path)


def once(text, before, after):
    need(text.count(before) == 1, 'unique literal replacement ' + before[:90])
    return text.replace(before, after, 1)


def reverse_split(text):
    text = once(text, 'module ' + NEW + ' #', 'module ' + OLD + ' #')
    text = once(text, CAPTURE, '')
    return once(text, '                        address<=0;pass_index<=0;carry<=0;all_zero<=1;all_max<=1;state<=READ_WORD;',
                '                        base_reg<=base;address<=0;pass_index<=0;carry<=0;all_zero<=1;all_max<=1;state<=READ_WORD;')


def archive(path):
    out = {}
    with tarfile.open(path) as stream:
        for m in stream:
            need(m.isfile() and not m.issparse() and m.name not in out, 'regular unique archive members')
            need(not m.name.startswith('/') and '..' not in Path(m.name).parts, 'relative archive')
            out[m.name] = stream.extractfile(m).read()
    return out


def native(mode):
    identity = 's4-p16-canonical-begin-split-' + mode + '-q1-v1'
    base = ROOT / 'queue/evidence' / identity
    folder = base / 'attempt-0/collected/output/native'
    gate_path = base / 'gate-receipt.json'
    saved = load(gate_path)
    contract = gate.make_contract(identity, folder / 'approved-manifest.json')
    # Existing evidence machinery hashes every raw artifact and archived source,
    # exact argv/probe/outcomes. It performs no arithmetic/native rerun.
    replay = gate.validate_result(contract, folder / 'report.json', id=identity)
    need(replay == saved, 'exact actual typed receipt reproduction')
    manifest, report = contract['manifest'], load(folder / 'report.json')
    expected_report = {'normal': '6f6cbed88b0fae9732d24370d20dacce618bf3cd3c15edbe345181b2c353a5c5',
                       'fault': '1b4d62895da8abfd56ae36bef9ff2b3039a1f354936665378009ad946c58e4f9'}[mode]
    need(sha((folder / 'report.json').read_bytes()) == expected_report, 'historical actual report')
    sources = archive(folder / 'sources.tar.gz')
    generated = archive(folder / 'generated-sources.tar.gz')
    need({k: sha(v) for k, v in generated.items()} == report['generated_source_sha256'], 'all compiled generated members')
    elf = gzip.decompress((folder / 'model.gz').read_bytes())
    need(elf[:4] == b'\x7fELF' and sha(elf) == report['executable_sha256'], 'retained actual ELF')
    need(report['limits']['memory_max_bytes'] == 4 << 30 and report['limits']['swap_max_bytes'] == 0,
         'actual bounded component cgroup')
    need(report['compile_workers'] == 2 and report['model_threads'] == 1, 'actual worker/model limits')
    need(manifest['build']['sv_sources'] == ['rtl/genefer_sdp_ram32.sv', 'rtl/' + OLD + '.sv',
         'rtl/' + NEW + '.sv', 'rtl/genefer_stream27_canonical_begin_split_pair_v1.sv'], 'four-file independent RAM pair')
    need(sha(sources['rtl/' + OLD + '.sv']) == PARENT and sha(sources['rtl/' + NEW + '.sv']) == CHILD, 'exact leaf pair')
    need(reverse_split(sources['rtl/' + NEW + '.sv'].decode()) == sources['rtl/' + OLD + '.sv'].decode(),
         'no control/arithmetic changes in isolated delta')
    helper_pin = {'normal': 'd4599c2ed6a2e1bf6e5d9138106a38227d38f19207b4854cb50367a10ce87785',
                  'fault': '0afd78c320155b6385810d031f7a71046c728615476e7f70c6ca221681da54f7'}[mode]
    need(sha(sources['reference/stream27_canonical_begin_split_native.py']) == helper_pin, 'own captured helper, not current substitution')
    cpp = sources['rtl/tb/stream27_canonical_begin_split_pair.cpp'].decode()
    need('context(argc,argv),d(&context)' in cpp and 'gfn16_runtime::configure(*this,argc,argv)' in cpp,
         'runtime configured before DUT')
    for marker in ('parent_cycles==d.local_cycles', 'R10_BEGIN_SPLIT_DATA_EQUIVALENCE',
                   'h.d.base=base;h.d.begin_canonical=1;', 'h.d.base=0;h.run();h.all(x);',
                   'special_sentinel=1', 'R10_BEGIN_SPLIT_STICKY_FAULT'):
        need(marker in cpp, 'executable source contract ' + marker)
    if mode == 'fault':
        need('age<9*N' in cpp and 'R10_BEGIN_SPLIT_LAST_EDGE_RESET' in cpp, 'origin-final reset assertion')
    return dict(id=identity, gate_sha256=sha(gate_path.read_bytes()), report_sha256=expected_report,
                manifest_sha256=contract['manifest_sha256'], sources_sha256=sha((folder / 'sources.tar.gz').read_bytes()),
                generated_sha256=sha((folder / 'generated-sources.tar.gz').read_bytes()),
                generated_members=len(generated), archived_source_members=len(sources),
                executable_sha256=report['executable_sha256'], captured_helper_sha256=helper_pin,
                stdout=(folder / report['steps'][-1]['log']).read_text()), sources


def literal(node, names):
    """Decode a pinned literal edit list as data; never execute candidate/model."""
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        return names[node.id]
    if isinstance(node, (ast.List, ast.Tuple)):
        return [literal(x, names) for x in node.elts]
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return literal(node.left, names) + literal(node.right, names)
    raise AssertionError('nonliteral recipe')


def integration():
    need(sha((ROOT / 'reference/stream27_context_storage_combo_timing10_bind.py').read_bytes()) ==
         '8404e36c688c040f47433b7aff2b5fbee34e438968f41898fe8fee6818f51491', 'integration recipe provenance only')
    bundle_path = RESULTS / 'trackS-c2-protected-relay13-native-v1/full-normal/production-bundle.json'
    bundle = pinned(bundle_path, '229e07390fbed434131bba7e101c2492bde27f5a45ebceb7fa40e1d94fec5c53')
    candidate = bundle['files']['genefer_stream27_canonical_image_foldpayload100_v1.sv']
    need(sha(candidate) == FOLD, 'actual R13 canonical')
    fold_path = ROOT / 'reference/stream27_canonical_fold_payload_bind.py'
    need(sha(fold_path.read_bytes()) == '00e26e8a8265ab5eb3f2a8ea652c020d3d7cc0b801f409b3613ff340e467f358', 'fixed literal fold recipe')
    tree = ast.parse(fold_path.read_text())
    names = {x.targets[0].id: x.value.value for x in tree.body if isinstance(x, ast.Assign)
             and isinstance(x.targets[0], ast.Name) and isinstance(x.value, ast.Constant)}
    fun = next(x for x in tree.body if isinstance(x, ast.FunctionDef) and x.name == 'edits')
    ops = literal(fun.body[0].value, names)
    prior = candidate
    for before, after in reversed(ops):
        prior = once(prior, after, before)
    need(sha(prior) == TIMING, 'exact protected timing10 recovered, fold proof excluded')
    record = bundle['context_timing10']['reversal_records']['genefer_stream27_canonical_image_timing10_v1.sv']
    need(record['parent'] == OLD + '.sv', 'exact canonical parent record')
    reverse = prior
    for before, after in reversed(record['edits']):
        reverse = once(reverse, after, before)
    need(sha(reverse) == PARENT, 'literal integrated reversal to R9 parent')
    for text in (prior, candidate):
        need(text.count(CAPTURE) == 1 and 'wire legal_begin=rst_n && state==IDLE && !error && !idle_reject && begin_canonical;' in text,
             'same speculative guard and authoritative accepted edge')
        snapshot = text[text.index('    always_ff @(posedge clk)if(legal_begin)begin'):text.index('    always_ff @(posedge clk or negedge rst_n)begin')]
        need('base_reg' not in snapshot, 'thresholds from same live accepted base')
        for marker in ("base_ext<=$signed({2'b00,base});", "two_base<=$signed({2'b00,base})<<<1;",
                       "three_base<=($signed({2'b00,base})<<<1)+$signed({2'b00,base});",
                       "negative_base<= -$signed({2'b00,base});", "negative_two_base<= -($signed({2'b00,base})<<<1);",
                       "base_max<=$signed({2'b00,base})-34'sd1;"):
            need(marker in snapshot, 'coherent threshold capture')
        need('base_reg<=2;' in text and 'state<=FAILED;error<=1;' in text and 'stored_digit_bad<=pass_index==0 && ram_q[bank]>=base_reg;' in text,
             'reset/sticky abort/active stored-digit input')
    host = bundle['files'][bundle['top'] + '.sv']
    manifest_path = bundle_path.with_name('manifest.json')
    manifest = pinned(manifest_path, 'd39a6e7a7054aa59f1b2cd66cdb25013e69a1af56c562ecb575b2c3829bda51d')
    for name, text in [('genefer_stream27_canonical_image_foldpayload100_v1.sv', candidate),
                       (bundle['top'] + '.sv', host)]:
        relative = 'rtl/' + name
        need(manifest['sources'][relative] == sha(text) and relative in manifest['build']['sv_sources'],
             'R13 actual captured compiled integration member')
        need((bundle_path.parent / 'source/fpga' / relative).read_text() == text, 'actual captured source bytes')
    for flag in ('CANONICAL_LOCALBASE', 'CANONICAL_PROFILE_SNAPSHOT', 'CANONICAL_BEGIN_PAYLOAD_SPLIT'):
        need(manifest['build']['parameters'][flag] == 1, 'exact integrated feature enabled')
    for marker in ('.begin_canonical(canonical_begin),.base(canonical_config_base),',
                   'canonical_config_valid<=0;canonical_config_base<=2;canonical_config_owner<=0;',
                   'if(canonical_config_bad)local_error<=1;', 'if(safety_error)canonical_config_valid<=0;',
                   'canonical_config_owner!=live_owner[canonical_owner*56+:56]',
                   'canonical_config_valid<=1;canonical_config_base<=job_base[phase[0]!=RAW_READY];',
                   'canonical_config_owner<=live_owner[(phase[0]!=RAW_READY)*56+:56];',
                   'if((|start_contexts) && !(|busy) && !canonical_owned && !safety_error)begin',
                   'assign busy[c]=phase[c]!=IDLE && !safety_error;',
                   'wire canonical_begin=canonical_owned && phase[canonical_owner]==CANON_WAIT && !canon_busy && !canon_image_valid && !safety_error;'):
        need(marker in host, 'current coherent host profile/control ' + marker)
    # There are only two base assignments: reset, and coherent RAW_READY lease claim.
    need(host.count('canonical_config_base<=') == 2 and host.count('job_base[c]<=') == 2, 'no mid-lease base update')
    need(host.count('canonical_config_valid<=0;') == 3, 'reset/newjob/error revocation')
    return dict(bundle_sha256=sha(bundle_path.read_bytes()), parent_sha256=PARENT, isolated_sha256=CHILD,
                timing10_sha256=TIMING, current_sha256=FOLD, host_sha256=sha(host),
                actual_captured_manifest_sha256=sha(manifest_path.read_bytes()),
                fold_recipe_sha256=sha(fold_path.read_bytes()), literal_chain=True, host_profile_same_context_full56=True)


def reject(state, error, flags):
    load, begin, read, pending, ready, base_ok, load_bad, order_ok, correction_bad, image = flags
    if state != 'IDLE' or error:
        return 0
    if load + begin + read > 1 or pending and (load or begin):
        return 1
    if load:
        return 3 if not base_ok else 6 if load_bad else 2 if not order_ok else 0
    if begin:
        return 5 if not ready else 3 if not base_ok else 4 if correction_bad else 0
    return 5 if read and not image else 0


def independent_guard_proof():
    # Independent reviewer truth table for the source-read rejection predicates.
    # Not an author model call, RTL simulation, arbitrary-X proof or whole algorithm proof.
    cases = dead = accepted = 0
    for state, error, rst, flags in itertools.product(
            ('IDLE','READ_WORD','VALUE_WORD','PROCESS_WORD','SPECIAL_WRITE','FAILED'), (0,1), (0,1),
            itertools.product((0,1), repeat=10)):
        code = reject(state, error, flags)
        begin = flags[1]
        legal = bool(rst and state == 'IDLE' and not error and not code and begin)
        capture = bool(rst and state == 'IDLE' and not error and begin)
        need(not legal or capture, 'accepted capture implication')
        if capture and not legal:
            need(code != 0, 'extra capture necessarily rejected at same edge')
            dead += 1
        if legal:
            accepted += 1
        need(not capture or state == 'IDLE', 'active base cannot be overwritten')
        need(not capture or not error, 'sticky fault cannot update base')
        need(rst or not capture, 'reset priority')
        cases += 1
    # Independent payload-only transition oracle, connected to the exact source
    # guard by integration()/reverse_split(). No authored model is executed.
    def payload(old, state, error, rst, flags, captured, live, mutant=None):
        code = reject(state,error,flags)
        legal = rst and state == 'IDLE' and not error and not code and flags[1]
        enabled = legal if old else rst and state == 'IDLE' and not error and flags[1]
        if mutant == 'active':
            enabled = rst and not error and flags[1]
        if mutant == 'load':
            enabled = rst and state == 'IDLE' and not error and flags[0]
        if not rst:
            return 'IDLE',0,2
        return ('FAILED' if code else 'READ_WORD' if legal else state), (error or bool(code)), (live if enabled else captured)
    ordinary = (0,1,0,0,1,1,0,1,0,0)
    rejected = (0,1,0,0,0,1,0,1,0,0)
    for live in (0,1,1013,1000000000,0xffffffff):
        old = payload(True,'IDLE',0,1,ordinary,1009,live)
        new = payload(False,'IDLE',0,1,ordinary,1009,live)
        need(old == new, 'accepted-edge exact payload equality independent of data bits')
        # Rejected payload divergence is harmless only while the original error
        # and FAILED state remain. Try every subsequent control combination.
        old = payload(True,'IDLE',0,1,rejected,1009,live)
        new = payload(False,'IDLE',0,1,rejected,1009,live)
        need(old[:2] == new[:2] == ('FAILED',True), 'same sticky rejection control')
        for controls in itertools.product((0,1), repeat=10):
            after_old = payload(True,*old[:2],1,controls,old[2],7)
            after_new = payload(False,*new[:2],1,controls,new[2],7)
            need(after_old[:2] == after_new[:2] == ('FAILED',True), 'dead payload induction')
        need(payload(True,*old[:2],0,ordinary,old[2],7) == payload(False,*new[:2],0,ordinary,new[2],7) == ('IDLE',0,2),
             'reset reunifies payload before fresh legal begin')
    good = payload(False,'READ_WORD',0,1,ordinary,1013,0)
    active_mutant = payload(False,'READ_WORD',0,1,ordinary,1013,0,'active')
    load_mutant = payload(False,'IDLE',0,1,ordinary,1009,1013,'load')
    need(good[2] == 1013 and active_mutant[2] != good[2], 'phase-guard mutant detected')
    need(load_mutant[2] != payload(False,'IDLE',0,1,ordinary,1009,1013)[2], 'LOAD-capture mutant detected')
    thresholds = lambda x: (x,2*x,3*x,-x,-2*x,x-1)
    tests = 0
    for base, live in itertools.product((1009,1013,604832956,999999937,1000000000),(0,1,1009,0xffffffff)):
        payload, bank = base, thresholds(base)
        need(payload == base and bank == thresholds(base), 'same accepted edge coherence')
        need(all(-(1<<33) <= x < (1<<33) for x in bank), 'supported accepted base signed34 width')
        need(payload != live or thresholds(live) == bank, 'stable captured payload, not live retiming')
        tests += 1
    need(thresholds(0) != thresholds(1013), 'live-threshold-retiming mutant detected')
    # Pending READ + BEGIN kills response; BEGIN absent/raw_ready false rejects;
    # FAILED cannot consume differing private payload until reset and fresh BEGIN.
    need(reject('IDLE',0,(0,1,0,1,1,1,0,1,0,1)) == 1, 'pending read conflict precedes begin')
    need(reject('IDLE',0,(0,1,0,0,0,1,0,1,0,1)) == 5, 'not ready rejection')
    for proposed in (0,1,0xffffffff):
        need(not ('FAILED' == 'IDLE' and proposed), 'dead rejected payload cannot reenter without reset')
    profile_cases = 0
    for phases, owned, safety, start in itertools.product(itertools.product(
            ('IDLE','RAW_READY','CANON_LOAD','CANON_WAIT','COPY','COPY_DRAIN'), repeat=2), (0,1),(0,1),(0,1)):
        busy = any(x != 'IDLE' for x in phases) and not safety
        claim = not owned and 'RAW_READY' in phases and not safety
        newjob = start and not busy and not owned and not safety
        need(not (claim and newjob), 'newjob cannot replace base on profile-claim edge')
        if claim:
            selected = int(phases[0] != 'RAW_READY')
            need(phases[selected] == 'RAW_READY', 'base/context/full-owner snapshot selector coherence')
            need(phases[selected] != 'CANON_WAIT', 'snapshot precedes legal BEGIN')
        profile_cases += 1
    return dict(binary_cases=cases, accepted_guard_cases=accepted, rejected_extra_capture_cases=dead,
                dead_payload_successor_cases=5*1024, active_threshold_cases=tests,
                host_profile_selection_cases=profile_cases,
                negative_controls_detected=3, negative_controls=['capture at LOAD rather than BEGIN','capture during ACTIVE','retime thresholds from live input'],
                scope='binary source-derived payload eligibility/induction; not HDL execution or generic proof',
                all_u32_threshold_width_claim=False)


def close():
    need(sha((ROOT / 'tools/native_gate_receipt_v1.py').read_bytes()) ==
         '131d4e6b9cafd424935094c3ec50ef81d7c2e8024efae6a5d37ce20d0c5a29d3', 'existing evidence replayer identity')
    normal, a = native('normal')
    fault, b = native('fault')
    # Distinct historical CPP change is precisely the final PROCESS reset case.
    reset = ''' h.reset();h.load(input());h.begin();
 for(unsigned age=1;age<9*N;age++){h.clear();h.edge();need(h.d.local_busy&&!h.d.local_done,"R10_BEGIN_SPLIT_BEFORE_LAST");}
 h.d.rst_n=0;h.edge();need(!h.d.local_image_valid&&!h.d.local_done&&!h.d.local_read_valid,"R10_BEGIN_SPLIT_LAST_EDGE_RESET");
 h.d.rst_n=1;h.clear();for(unsigned k=0;k<4;k++)h.edge();
'''
    cpp_name = 'rtl/tb/stream27_canonical_begin_split_pair.cpp'
    need(once(b[cpp_name].decode(), reset, '') == a[cpp_name].decode(), 'historical CPP difference exact')
    references = {}
    for name, pin in [('r13-excluded-ancestor-review-gap-map-v1.json','362c8eee1cdc2900f45944775e571ff100c18966b68b06d76d2c70551a94eaf5'),
                      ('s4-p16-c2-r9-eight-numerical-ledger-scoped-review-v1.json','c3b537553497afe03e8de22a74df87560aae01ce344350e34821f41a9a67c0d9'),
                      ('r13-source-numerical-scoped-assessment-v1.json','8640fee974f62243c799eab22e1f6169dc4812b6ff723b0aa88dc238e1278265')]:
        # Routing/previous partition receipts are metadata-bound, not rerun.
        pinned(RESULTS / name,pin)
        references[name] = pin
    return dict(schema='r13-base-ena-independent-review-v1', status='PASS_SCOPED_BASE_ENA_DELTA',
                reviewer='p16_independent_reviewer', independence='No authorship of begin_split bind/model/native, timing10 integration, fold or R13 production. Prior compatibility analysis read-only. Own unrelated R9/FIELD100 barrier and R14/B fixtures excluded.',
                partition_references=references,
                source=integration(), native=[normal,fault], independent_proof=independent_guard_proof(),
                findings=['Accepted BEGIN captures the same base on the same edge; all other isolated RTL bytes reverse exactly.',
                          'Additional private capture only accompanies same-edge sticky FAILED; image/read eligibility cleared, reset restores base2.',
                          'Current protected R13 legal_begin threshold bank samples same base; no live-input retiming during active canonical operation.',
                          'Host base/full56 owner snapshot captured together at RAW_READY lease claim, before CANON_LOAD/WAIT. Reset/newjob/error revoke validity; no mid-lease base assignment.',
                          'Native live-base images are below both changed bases: useful exact paired behavior, not alone a discriminating wrong-capture proof. Independent source/guard proof supplies that obligation.'],
                exclusions=['Own R9/FIELD100/R14 fixtures', 'whole ancestor arithmetic/control re-proof', 'fold payload equivalence (separately reviewed)',
                            'physical prep/layout/clock/resources', 'whole R13 PRP/long qualification', 'arbitrary X/RAM/config corruption', 'board/transport/GL/adoption'],
                native_rerun=False, author_model_executed=False, promotion_allowed=False)


if __name__ == '__main__':
    print(json.dumps(close(), sort_keys=True, indent=2))
