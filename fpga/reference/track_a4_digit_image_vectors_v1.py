"""Digit-image contract oracle: flat signed-word memory, no NTT arithmetic.

The caller guarantees initialized words before reads and zero RAM before the
minus-one metadata marker. This model does not infer those outer preconditions.
"""
import hashlib
import random


def signed(word):
    return word - (1 << 32) if word & (1 << 31) else word


class Image:
    def __init__(self, aw):
        if type(aw) is not int or not 5 <= aw <= 16:
            raise ValueError('AW5..16')
        self.aw, self.n, self.t = aw, 1 << aw, 1 << (aw-4)
        self.k = 2*self.n+384
        self.minimum = max(2*self.n+5, (2*self.k+2)//3+1)
        self.memory = {}
        self.reset()

    def reset(self):
        self.configured = self.base = self.generation = 0
        self.c0, self.c1 = [0]*16, [0]*16
        self.shadow0, self.shadow1 = [0]*16, [0]*16
        self.sv0 = self.sv1 = 0
        self.read_valid = self.read_mask = self.read_tag = self.read_generation = 0
        self.words = [0]*16
        self.error = self.code = self.error_generation = 0

    def edge(self, e):
        if not e['rst']:
            self.reset()
            return self.output()
        cfg, re, we = e['configure'], e['read_en'], e['write_en']
        metadata = e['clear_corrections'] + e['set_minus_one'] + e['boundary_commit']
        request = bool(cfg or re or we or metadata)
        code = 0
        if request:
            if (cfg and (re or we or metadata)) or (metadata and (re or we)) or metadata > 1:
                code = 1
            elif (cfg and (not self.minimum <= e['base'] <= 10**9 or (not self.configured and not e['clear_image']))) or (not cfg and not self.configured):
                code = 2
            elif not cfg and e['generation'] != self.generation:
                code = 3
            elif (re and e['read_offset'] >= self.t) or (we and (e['write_offset'] >= self.t or e['write_kind'] == 3)):
                code = 4
            elif re and we and e['read_offset'] == e['write_offset'] and e['read_mask'] & e['write_mask']:
                code = 5
            elif we and any((not 0 <= w < self.base if e['write_kind'] != 2 else not -1 <= signed(w) < self.base)
                            for j, w in enumerate(e['write_words']) if e['write_mask'] >> j & 1):
                code = 6
            elif e['boundary_commit'] and any(not 0 <= lo < self.base or not -self.k <= signed(hi) <= self.k
                                              for lo, hi in zip(e['low'], e['high'])):
                code = 7
        self.error, self.code = int(bool(code)), code
        if code:
            self.error_generation = e['generation']
        self.read_valid, self.read_mask = 0, 0
        if request and not code:
            if cfg:
                self.configured, self.base, self.generation = 1, e['base'], e['generation']
                if e['clear_image']:
                    self.c0, self.c1, self.sv0, self.sv1 = [0]*16, [0]*16, 0, 0
            if re:
                self.read_valid, self.read_mask = 1, e['read_mask']
                self.read_tag, self.read_generation = e['read_tag'], e['generation']
                for j in range(16):
                    if self.read_mask >> j & 1:
                        value = self.memory[j*self.t+e['read_offset']]
                        correction = (self.c0[j] if e['read_offset'] == 0 else self.c1[j] if e['read_offset'] == 1 else 0)
                        self.words[j] = value + (correction if e['read_apply_corrections'] else 0)
            if we:
                row = e['write_offset']
                for j, word in enumerate(e['write_words']):
                    if e['write_mask'] >> j & 1:
                        self.memory[j*self.t+row] = signed(word)
                        if row in (0, 1):
                            shadows = self.shadow0 if row == 0 else self.shadow1
                            valid = self.sv0 if row == 0 else self.sv1
                            valid = valid | (1 << j) if e['write_kind'] == 0 else valid & ~(1 << j)
                            if e['write_kind'] == 0:
                                shadows[j] = word
                            if e['write_kind'] == 2:
                                (self.c0 if row == 0 else self.c1)[j] = 0
                            if row == 0:
                                self.sv0 = valid
                            else:
                                self.sv1 = valid
            if e['clear_corrections'] or e['set_minus_one']:
                self.c0, self.c1 = [0]*16, [0]*16
                if e['set_minus_one']:
                    self.c0[0] = -1
            if e['boundary_commit']:
                for source, (lo, hi) in enumerate(zip(e['low'], e['high'])):
                    dest = (source+1) % 16
                    self.c0[dest] = -lo if source == 15 else lo
                    self.c1[dest] = -signed(hi) if source == 15 else signed(hi)
        return self.output()

    def output(self):
        return ([self.configured, self.base, self.generation, self.read_valid, self.read_mask,
                 self.read_tag, self.read_generation, self.error, self.code, self.error_generation, self.sv0, self.sv1]
                + self.words + [v & 0xffffffff for v in self.c0+self.c1+self.shadow0+self.shadow1])


KEYS = ('rst','configure','clear_image','base','generation','read_en','read_offset','read_mask',
        'read_apply_corrections','read_tag','write_en','write_offset','write_mask','write_kind',
        'clear_corrections','set_minus_one','boundary_commit')


def corpus(aw):
    if type(aw) is not int or aw not in (5, 8):
        raise ValueError('bounded AW5/AW8 native corpus')
    image = Image(aw); rng = random.Random(0xA4D120261001+aw)
    rows = []; counts = dict(events=0, reads=0, words=0, errors=0, resets=0, configurations=0, boundary_commits=0)
    codes = {str(i): 0 for i in range(1, 8)}
    def emit(**kwargs):
        e = dict(rst=1, configure=0, clear_image=0, base=image.base or image.minimum,
                 generation=image.generation, read_en=0, read_offset=0, read_mask=65535,
                 read_apply_corrections=1, read_tag=0, write_en=0, write_offset=0, write_mask=65535,
                 write_kind=0, clear_corrections=0, set_minus_one=0, boundary_commit=0,
                 write_words=[0]*16, low=[0]*16, high=[0]*16)
        e.update(kwargs)
        for key in ('write_words', 'low', 'high'):
            e[key] = [x & 0xffffffff for x in e[key]]
        out = image.edge(e)
        rows.append([e[k] for k in KEYS] + e['write_words']+e['low']+e['high'] + out)
        counts['events'] += 1; counts['reads'] += out[3]; counts['words'] += out[4].bit_count()
        counts['errors'] += out[7]; counts['resets'] += not e['rst']
        counts['configurations'] += bool(e['rst'] and e['configure'] and not out[7])
        counts['boundary_commits'] += bool(e['rst'] and e['boundary_commit'] and not out[7])
        if out[7]:
            codes[str(out[8])] += 1
    emit(rst=0)
    emit(read_en=1)  # unconfigured
    emit(configure=1, clear_image=0, base=image.minimum, generation=11)
    emit(configure=1, clear_image=1, base=image.minimum-1, generation=11)
    emit(configure=1, clear_image=1, base=image.minimum, generation=11)
    for offset in range(image.t):
        emit(write_en=1, write_offset=offset, write_words=[(j*17+offset) % image.base for j in range(16)])
    for base in (image.minimum, 10**9):
        emit(configure=1, base=base, generation=image.generation+1)
        emit(boundary_commit=1, low=[base-1-j for j in range(16)], high=[(-image.k if j%2 else image.k) for j in range(16)])
        for row in range(image.t):
            emit(read_en=1, read_offset=row, read_tag=row)
            emit(read_en=1, read_offset=row, read_tag=(row+3) % image.n, read_apply_corrections=0)
        # Same row, disjoint banks accepted; intersecting banks rejected.
        emit(read_en=1, write_en=1, read_mask=0x5555, write_mask=0xaaaa, write_words=[base-1]*16)
        emit(read_en=1, write_en=1, write_words=[0]*16)
        emit(read_en=1, write_en=1, read_offset=0, write_offset=1, write_words=[base-1]*16)
        # Host replaces the complete effective word and invalidates its shadow.
        emit(write_en=1, write_kind=2, write_mask=1, write_words=[-1]+[0]*15)
        emit(read_en=1, read_mask=1, read_tag=0)
        emit(write_en=1, write_kind=1, write_offset=1, write_mask=2, write_words=[0]*16)
        emit(read_en=1, read_offset=1, read_mask=2, read_tag=image.t+1)
        emit(clear_corrections=1)
        for offset in range(image.t):
            emit(write_en=1, write_kind=1, write_offset=offset)
        emit(set_minus_one=1)
        emit(read_en=1, read_mask=1)
        emit(write_en=1, write_kind=2, write_mask=1, write_words=[base-1]+[0]*15)
        emit(read_en=1, read_mask=1)
        # Every error category and priority; every rejected write must be atomic.
        for bad in (
            dict(configure=1, read_en=1, clear_image=1, base=0, generation=image.generation+99),
            dict(clear_corrections=1, boundary_commit=1),
            dict(set_minus_one=1, write_en=1),
            dict(configure=1, base=10**9+1),
            dict(read_en=1, write_en=1, generation=image.generation+1, read_offset=image.t),
            dict(read_en=1, write_en=1, read_offset=image.t),
            dict(write_en=1, write_kind=3),
            dict(write_en=1, write_words=[base]+[0]*15),
            dict(write_en=1, write_kind=2, write_words=[-2]+[0]*15),
            dict(boundary_commit=1, low=[base]+[0]*15),
            dict(boundary_commit=1, high=[image.k+1]+[0]*15),
            dict(boundary_commit=1, high=[-(1<<31)]+[0]*15),
        ):
            emit(**bad); emit(read_en=1, read_offset=0)
        for index in range(256):
            kind = rng.randrange(9)
            if kind < 5:
                host = kind == 3
                emit(read_en=int(kind in (0, 2, 4)), write_en=int(kind in (1, 2, 3, 4)),
                     read_offset=rng.randrange(image.t), write_offset=rng.randrange(image.t),
                     read_mask=rng.randrange(65536), write_mask=rng.randrange(65536),
                     read_apply_corrections=rng.randrange(2), read_tag=rng.randrange(image.n),
                     write_kind=2 if host else rng.randrange(2),
                     write_words=[rng.randrange(-1 if host else 0, base) for _ in range(16)])
            elif kind == 5:
                emit(boundary_commit=1, low=[rng.randrange(base) for _ in range(16)],
                     high=[rng.randrange(-image.k, image.k+1) for _ in range(16)])
            elif kind == 6:
                emit(clear_corrections=1)
            elif kind == 7:
                emit(configure=1, generation=image.generation+1)
            else:
                emit()
        # Reset cancels pending read eligibility but retains initialized RAM.
        emit(read_en=1); emit(rst=0); emit(read_en=1)
        emit(configure=1, clear_image=1, base=base, generation=200+aw)
        emit(read_en=1)
    emit()
    text = f'A4IMAGE1 {aw} {len(rows)}\n' + '\n'.join(' '.join(map(str, row)) for row in rows) + '\n'
    return text, dict(aw=aw, **counts, error_codes=codes,
                     sha256=hashlib.sha256(text.encode()).hexdigest(), scope='source contract oracle only')
