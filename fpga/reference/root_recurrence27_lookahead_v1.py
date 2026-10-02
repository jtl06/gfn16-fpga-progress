"""Exact additive F2 source derivation and finite selector proof; no HDL execution."""
import hashlib
from itertools import product
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REC = 'genefer_root_recurrence27'
ENGINE = 'genefer_ntt_banked27_prefetch_r2_orient8_rootfused_engine'
HOST = 'genefer_ntt_banked27_prefetch_r2_host_broadcast_orient8_rootfused_engine'
PARENTS = {
    REC: 'c8adc265915192807efee46799a782f1649a4408313098baaed8b4a808afeb9e',
    ENGINE: 'd52351bdf53c6809208f7a466848b4376cbd8ff87c52f633dc8c2814026b47ee',
    HOST: 'b3d06d1e5f90e4944fdf88ff264cb7edbd73d0daf9f46ccf93389ab4889d9e3f',
}
NAMES = {REC: REC+'_lookahead_v1', ENGINE: ENGINE.replace('_engine','_lookahead_v1_engine'),
         HOST: HOST.replace('_engine','_lookahead_v1_engine')}


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('ambiguous source anchor: '+old[:70])
    return text.replace(old, new)


LOOKAHEAD = '''    // F2 only: select controls arrive with issued/context updates. Payload and
    // the four-cycle multiplier feedback are unchanged. A bubble must HOLD the
    // issued-dependent selectors, but bypass follows the arriving result.
    localparam int SELECT_TILE_LANES=8,SELECT_TILES=(LANES+7)/8;
    logic [2:0] update_fire_history;
    logic [16:0] select_issued,select_period,select_position;
    logic accept_start,select_bypass;
    assign accept_start=state==IDLE && start && config_ok;
    assign select_issued=accept_start ? 17'd0 : issued+17'(fire);
    assign select_period=accept_start ? config_period : repeat_period;
    assign select_position=select_period==0 ? select_issued : select_issued&(select_period-17'd1);
    // After this edge, multiplier out_valid is its old valid_pipe[2], and
    // context_pipe[3] is old context_pipe[2]. Never cache today's bypass.
    assign select_bypass=update_fire_history[2] && context_pipe[2]==select_issued[1:0];
    always_ff @(posedge clk or negedge rst_n)begin
        if(!rst_n)update_fire_history<=0;
        else update_fire_history<={update_fire_history[1:0],fire};
    end
    for(genvar tile=0;tile<SELECT_TILES;tile=tile+1)begin: select_tiles
        (* preserve, dont_merge *) logic use_seed_q,bypass_q,bank_q;
        (* preserve, dont_merge *) logic [1:0] seed_id_q,context_id_q;
        always_ff @(posedge clk or negedge rst_n)begin
            if(!rst_n)begin
                use_seed_q<=1;seed_id_q<=0;context_id_q<=0;bypass_q<=0;bank_q<=0;
            end else begin
                use_seed_q<=select_position<4;
                seed_id_q<=select_position[1:0];context_id_q<=select_issued[1:0];
                bypass_q<=select_bypass;
                bank_q<=accept_start ? config_bank : active_bank;
            end
        end
    end
'''


def expected(name, original):
    if name not in PARENTS or sha(original) != PARENTS[name]:
        raise ValueError('frozen ancestor hash: '+name)
    text = once(original, 'module '+name+' #(', 'module '+NAMES[name]+' #(')
    if name != REC:
        child = REC if name == ENGINE else ENGINE
        return once(text, child+' #(', NAMES[child]+' #(')
    text = once(text, '    assign position=repeat_period==0 ? issued : issued&(repeat_period-17\'d1);\n', LOOKAHEAD)
    text = once(text, '    assign context_id=issued[1:0];\n    assign seed_id=position[1:0];\n    assign use_seed=position<4;\n    assign bypass=update_valid[0] && context_pipe[3]==context_id;\n',
        '    assign context_id=select_tiles[0].context_id_q;\n'
        '    assign use_seed=select_tiles[0].use_seed_q;\n'
        '    assign bypass=select_tiles[0].bypass_q;\n')
    text = once(text, 'groups,repeat_period,issued,position;', 'groups,repeat_period,issued;')
    text = once(text, 'context_id,seed_id;', 'context_id;')
    return once(text,
        '        assign current_root[j]=use_seed ? seeds[active_bank][seed_id][j] :\n'
        '            bypass ? update_result[j] : context_value[context_id][j];',
        '        localparam int TILE=j/SELECT_TILE_LANES;\n'
        '        assign current_root[j]=select_tiles[TILE].use_seed_q ?\n'
        '            seeds[select_tiles[TILE].bank_q][select_tiles[TILE].seed_id_q][j] :\n'
        '            select_tiles[TILE].bypass_q ? update_result[j] :\n'
        '            context_value[select_tiles[TILE].context_id_q][j];')


def mutant(text):
    """Typed one-line fault: advancing the lookahead on a RUN bubble."""
    return once(text, "issued+17'(fire)", "issued+17'(state==RUN)")


def verify(root=ROOT):
    result = {}
    for name, new in NAMES.items():
        path = root/'rtl/kernel'/(new+'.sv')
        original = (root/'rtl/kernel'/(name+'.sv')).read_text()
        actual = path.read_text()
        if actual != expected(name, original):
            raise ValueError('unreviewed lookahead source delta: '+new)
        result[str(path.relative_to(root))] = sha(actual)
    return result


def engine_pair(original):
    """Identical one-field host surfaces; data compare only when meaningful."""
    import re
    if sha(original) != PARENTS[HOST]:
        raise ValueError('host ancestor identity')
    header = original[original.index('module '):original.index(');')+2]
    header = once(header, 'module '+HOST+' #(', 'module root_lookahead_engine_pair_v1 #(')
    header = once(header, 'root_reads,wait_cycles\n', 'root_reads,wait_cycles,\n    output logic pair_mismatch\n')
    declarations = list(re.finditer(r'\b(input|output) logic\s*(\[[^\]]+\])?\s*([^\n]+)',
        original[original.index(') (')+3:original.index(');')]))
    ports, outputs, wires = [], [], []
    for match in declarations:
        direction, width, names = match.groups()
        for name in names.strip().rstrip(',').split(','):
            ports.append(name)
            if direction == 'output':
                outputs.append(name)
                wires.append('    logic '+((width+' ') if width else '')+'baseline_'+name+';')
    text = '// Paired AW5 integration probe; not a physical top.\n'+header+'\n'+'\n'.join(wires)+'\n'
    for instance, module in [('baseline', HOST), ('candidate', NAMES[HOST])]:
        text += '    '+module+' #(.AW(AW),.LANES(LANES),.HOST_LANES(HOST_LANES),.P(P),.Q(Q)) '+instance+' (\n'
        text += ',\n'.join('        .'+port+'('+('baseline_' if instance == 'baseline' and port in outputs else '')+port+')' for port in ports)+'\n    );\n'
    checks = ['('+p+' !== baseline_'+p+')' for p in outputs if p not in ('read_data','vector_read_data')]
    checks += ['(read_valid && read_data !== baseline_read_data)']
    checks += ['(vector_read_valid && vector_read_mask['+str(i)+'] && vector_read_data['+str(32*i)+'+:32] !== baseline_vector_read_data['+str(32*i)+'+:32])' for i in range(16)]
    return text+'    assign pair_mismatch=\n        '+' ||\n        '.join(checks)+';\nendmodule\n'


def selector(issued, period, valid, context):
    # Independent mathematical modulo form, not the RTL mask expression.
    position = issued % period if period else issued
    return position < 4, position % 4, issued % 4, bool(valid and context == issued % 4)


def prove_selectors():
    """Exhaust every legal period/issued and both fires; arbitrary pipeline tails.

    The bypass proof quantifies over the next arriving valid/context pair,
    including bubbles. Start chooses zero with no extra pipeline edge. This is
    finite Python reasoning, not Verilog simulation or a formal-tool proof.
    """
    checks = 0
    for period in [0]+[1 << k for k in range(17)]:
        for issued in range(65537):
            for fire in (0, 1):
                if issued+fire > 65536:
                    continue
                nxt = issued+fire
                pos = nxt if period == 0 else nxt & (period-1)
                assert (pos < 4, pos & 3, nxt & 3) == selector(nxt, period, False, 0)[:3]
                checks += 1
    for issued, valid, context in product(range(8), (False, True), range(4)):
        assert bool(valid and context == (issued & 3)) == selector(issued, 0, valid, context)[3]
        checks += 1
    return checks


def trace(period, gaps, groups=12, broken=False):
    """Mirrored-valid timing model vs baseline, payload oracle is separate.

    Each tuple is pre-edge (issued, selectors, ready). Ready is derived with
    explicit context availability/writeback. context_pipe shifts even on gaps.
    """
    issued = 0
    history = [False]*4
    contexts = [0]*4
    available = [False]*4
    q = selector(0, period, False, 0)
    out = []
    ticks = 0
    while issued < groups or any(history):
        baseline = selector(issued, period, history[3], contexts[3])
        ready = issued < groups and (baseline[0] or available[issued % 4] or baseline[3])
        candidate_ready = issued < groups and (q[0] or available[q[2]] or q[3])
        out.append((issued, baseline, q, ready, candidate_ready))
        request = bool(gaps[ticks]) if ticks < len(gaps) else True
        fire = bool(ready and request)
        if history[3]:
            available[contexts[3]] = True
        if fire:
            available[issued % 4] = False
        advance = int(issued < groups) if broken else int(fire)
        next_issued = issued+advance
        pos = next_issued if not period else next_issued & (period-1)
        q = (pos < 4, pos & 3, next_issued & 3,
             bool(history[2] and contexts[2] == (next_issued & 3)))
        contexts = [issued % 4]+contexts[:3]
        history = [fire]+history[:3]
        issued += int(fire)
        ticks += 1
        assert ticks <= groups+len(gaps)+4
    return out
