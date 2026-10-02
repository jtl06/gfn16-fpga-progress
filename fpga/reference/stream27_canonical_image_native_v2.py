"""Dependency-only native oracle successor; frozen canonical RTL unchanged."""
from fpga.reference import stream27_canonical_image_native_v1 as old
from fpga.reference import stream27_canonical_image_corpus_v1 as corpus

ROOT=old.ROOT;TOP=old.TOP;SV=old.SV;RAM=old.RAM;model=old.model;sha=old.sha
CPP='rtl/tb/stream27_canonical_image_v2.cpp'
PINS=dict(old.PINS)
PINS.update({CPP:'401ee1d8bb0776f8805ec425266e091a22da2cfa65f9842934d298c9a3f779ee',
    'reference/stream27_canonical_image_native_v1.py':'9cd99c23ee475fb7a3f6729440b2361048706936d0cbff19a185b5a948487ad7',
    'reference/stream27_canonical_image_prepare_v1.py':'439158701196ecda3447c96f8bd6faf57769f9f7cb02ce56ec8dec7186bb1c3f',
    'reference/stream27_canonical_image_corpus_v1.py':'89c2c871c3645d9beae0236f96d8876cd7867d3859b9b9edfbd30b0e3d73e055'})


def region(text,start,end):
    model.need(text.count(start)==1 and text.count(end)==1,'CANON_CPP_DELTA_MARKER')
    return text[text.index(start):text.index(end)]


def verify(root=ROOT):
    for name,pin in PINS.items():
        path=root/name
        model.need(path.is_file() and not path.is_symlink() and sha(path.read_bytes())==pin,'CANON_V2_SOURCE_DRIFT '+name)
    before=(root/old.CPP).read_text();after=(root/CPP).read_text()
    model.need(region(before,'uint64_t random_word(','cpp_int signed_read96(')==
               region(after,'uint64_t random_word(','void check_oracle_checksum('),'CANON_NATIVE_VECTORS_UNCHANGED')
    for start,end in (('struct Outputs {','    void check_read('),
                      ('    // Leaves no pending E0 request.','} // namespace')):
        model.need(region(before,start,end)==region(after,start,end),'CANON_NATIVE_PROTOCOL_UNCHANGED')
    main=after[after.index('int main('):].replace('        limb_self_checks();\n','').replace('        check_oracle_checksum(trials);\n','')
    model.need(main==before[before.index('int main('):],'CANON_NATIVE_MAIN_CONTRACT_UNCHANGED')
    model.need('#include <boost/' not in after and 'cpp_int' not in after,'CANON_NATIVE_CLOSED_ORACLE')
    return dict(PINS)


def contracts(aw,p):
    result=old.contracts(aw,p)
    # V2 compares the complete signed96 words. Its diagnostic prints high:mid:
    # low rather than Boost's signed decimal; the fixed underlying expected
    # value/address/rc and positive footer do not change. No observed fallback.
    negative=dict(result['negative']);prefix,actual=negative['stderr'].rsplit('actual=',1)
    negative['stderr']=prefix+'actual=0:0:'+actual
    return dict(result,negative=negative)


def validate(stdout,stderr,returncode,config,assets):
    model.need(set(config)=={'aw','p','negative'} and type(config['negative']) is bool and assets=={},'CANON_NATIVE_CONFIG')
    expected=contracts(config['aw'],config['p'])['negative' if config['negative'] else 'normal']
    model.need((stdout,stderr,returncode)==(expected['stdout'],expected['stderr'],expected['returncode']),'CANON_NATIVE_TYPED_OUTPUT')
    return dict(status='PASS_expected_contracts',aw=config['aw'],p=config['p'],negative=config['negative'],promotion_allowed=False)
