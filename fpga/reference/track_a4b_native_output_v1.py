"""Candidate-specific typed output adapter for the shared native packager.

No execution, file reads, policy overrides or inferred success from return0.
The shared launcher supplies only pinned assets as text and preserves this
validator's returned JSON as separate unreviewed native evidence.
"""

def validate(stdout_text,stderr_text,returncode_int,config_dict,assets_text_map):
    if not isinstance(stdout_text,str) or not isinstance(stderr_text,str) or type(returncode_int) is not int:
        raise ValueError('typed native output')
    if type(config_dict) is not dict or type(assets_text_map) is not dict:
        raise ValueError('typed validator configuration')
    mode=config_dict.get('mode')
    if mode=='normal':
        if set(config_dict)!={'mode','aw'} or config_dict['aw'] not in (5,8) or set(assets_text_map)!={'vectors'}:
            raise ValueError('exact small-N configuration and vector asset')
        if returncode_int!=0 or stderr_text:raise ValueError('normal native failure/stderr')
        from fpga.reference.track_a4_core_output_v3 import parse
        result=parse(stdout_text,assets_text_map['vectors'])
        if result['aw']!=config_dict['aw']:raise ValueError('native AW mismatch')
        return result
    if mode=='representative':
        if set(config_dict)!={'mode','aw'} or config_dict['aw'] not in (5,8,16) or assets_text_map:
            raise ValueError('exact representative configuration')
        if returncode_int!=0 or stderr_text:raise ValueError('representative native failure/stderr')
        from fpga.reference.track_a4_representative_output_v2 import parse
        return parse(stdout_text,config_dict['aw'])
    if mode=='boundary':
        if set(config_dict) not in ({'mode','case'},{'mode','case','mutant'}) or assets_text_map:
            raise ValueError('exact boundary configuration')
        from fpga.reference.track_a4_admission_boundary_v1 import parse_output
        return parse_output(stdout_text,stderr_text,returncode_int,config_dict['case'],config_dict.get('mutant'))
    raise ValueError('unsupported candidate output mode')
