"""S4 shadow-image protocol model, not a canonicalization or warm oracle.

Natural flat address b*T+row; signed host storage is deliberately unrestricted.
The scalar/row synchronous RAM response is observable after accepted E0. The
outer controller supplies source registers and consumes on later edges.
"""


def need(ok, tag):
    if not ok:
        raise ValueError(tag)


def geometry(aw, p):
    need(type(aw) is int and 5 <= aw <= 16 and type(p) is int and p in (8, 16),
         'HOST_IMAGE_GEOMETRY')
    n = 1 << aw
    return dict(aw=aw, p=p, n=n, t=n // p, row_width=aw-(p.bit_length()-1),
                shadow_bits=32*n, scalar_copy_edges=n,
                m20k_packing_proxy=p*((n//p+511)//512),
                read_edge='E0_after_NBA', read_II=1,
                payload_register_after_RAM=False,
                cost_scope='One extra shadow image; scalar copy outside warm recurrence; caller startup/drain extra.')


def signed96(word):
    need(type(word) is int and -(1 << 31) <= word <= (1 << 32)-1,
         'HOST_IMAGE_WORD32')
    raw = word & 0xffffffff
    return raw-(1 << 32) if raw & 0x80000000 else raw


class Image:
    """Bounded scalar model with RAM payload retained across eligibility reset."""
    def __init__(self, aw, p):
        self.g = geometry(aw, p)
        need(aw <= 8, 'HOST_IMAGE_NO_FULLN_LOCAL_NUMERIC')
        self.words = [None]*self.g['n']
        self.q = [None]*p
        self.bank = 0
        self.scalar_valid = self.row_valid = False

    def response(self):
        value = self.q[self.bank]
        return dict(read_valid=self.scalar_valid,
                    read_data=None if value is None else signed96(value),
                    row_read_valid=self.row_valid, row_read_data=tuple(self.q))

    def reset(self):
        self.scalar_valid = self.row_valid = False
        self.bank = 0
        return self.response()

    def edge(self, *, rst=True, access=True, load=False, read=False, address=0,
             word=0, row=False, row_address=0, commit=False, commit_address=0,
             commit_word=0):
        g = self.g
        need(all(type(x) is bool for x in (rst, access, load, read, row, commit)),
             'HOST_IMAGE_FLAGS')
        need(type(address) is int and 0 <= address < g['n'] and
             type(commit_address) is int and 0 <= commit_address < g['n'] and
             type(row_address) is int and 0 <= row_address < g['t'],
             'HOST_IMAGE_MODEL_ADDRESS')
        signed96(word); signed96(commit_word)
        if not rst:
            return self.reset()
        self.scalar_valid = self.row_valid = False
        if commit:
            self.words[commit_address] = commit_word & 0xffffffff
        elif row:
            self.q = [self.words[b*g['t']+row_address] for b in range(g['p'])]
            self.row_valid = True
        elif access:
            if load:
                self.words[address] = word & 0xffffffff
            elif read:
                self.bank, offset = divmod(address, g['t'])
                self.q[self.bank] = self.words[self.bank*g['t']+offset]
                self.scalar_valid = True
        return self.response()


def native_counts(aw, p):
    need(type(aw) is int and aw in (5, 8), 'HOST_IMAGE_FINITE_NATIVE')
    g = geometry(aw, p); n = g['n']; t = g['t']
    edges = 10*n+3*((n-1)//17)+7*t+9*p+25
    return dict(edges=edges, scalar=6*n+4*p+1, rows=7*t+p,
                row_words=7*n+p*p, host_writes=3*n+p, commits=n+p,
                ignored=n+t+3*p+2, write_priority=p, resets=3,
                before_checks=2*edges, shadow_bits=32*n, copy_cycles=n)
