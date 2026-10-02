"""Exact harness-only successor; all v3 RTL is byte-identical."""
import hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PARENT='rtl/tb/track_a4_core_v3.cpp'
PARENT_SHA='5b9d284578286c95b153c9594a765f36d44c99b1ab9c3b3740dec46689bca8b9'
CHILD='rtl/tb/track_a4_core_representative_v1.cpp'
REPLACEMENTS=(
    ('static_assert(A4_CORE_AW==5 || A4_CORE_AW==8,"small-N native whole-core gate");',
     'static_assert(A4_CORE_AW==5 || A4_CORE_AW==8 || A4_CORE_AW==16,"native representative whole-core gate");\n#include "track_a4_representative_recipe_v1.hpp"'),
    ('need(argc==2,"usage: a4_core vectors | --runtime-probe");',
     'need(argc==2 && std::string(argv[1])=="--representative","usage: a4_core --representative | --runtime-probe");'),
    ('std::ifstream input(argv[1]);need(bool(input),"A4_CORE_OPEN");',
     'std::istringstream input(a4_representative_vectors());need(bool(input),"A4_CORE_RECIPE");'),
    ('count>0 && count<10000','count==12*(1u<<aw)+20'),
)


def expected(text):
    for before,after in REPLACEMENTS:
        assert text.count(before)==1,before
        text=text.replace(before,after)
    return text


def verify(root=ROOT):
    raw=(root/PARENT).read_bytes()
    assert hashlib.sha256(raw).hexdigest()==PARENT_SHA
    assert (root/CHILD).read_text()==expected(raw.decode())
    return dict(rtl_changes=0,bench_changes='AW16 admission, native closed-form recipe input, exact recipe command count',
                parent_sha256=PARENT_SHA,ordinary_checks='all inherited response, phase, hold and reset checks unchanged')
