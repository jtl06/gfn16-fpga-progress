"""Strict finite profile/completion integration seam output contract."""
import re
CASES=('header0','header3','reset-word3','reset-commit','reset-check','done0','done1','done2','error0','error1','error2')
def validate(stdout_text,stderr_text,returncode_int,config_dict,assets_text_map):
    if set(config_dict)!={'case'} or config_dict['case'] not in CASES or assets_text_map:raise ValueError('finite control seam config')
    case=config_dict['case'];m=re.fullmatch(r'ANEXT_CONTROL_PASS case=([a-z0-9-]+) injected=1 errors=([01]) recovered=1 words=32 quiet=12 ticks=([1-9][0-9]*)\n',stdout_text)
    if type(returncode_int) is not int or returncode_int!=0 or stderr_text or not m or m[1]!=case or int(m[2])!=int(not case.startswith('reset-')) or int(m[3])>=50000:raise ValueError('incomplete integration fault seam result')
    return dict(status='PASS_expected_contracts',case=case,recovered_words=32,quiet_edges=12,ticks=int(m[3]),promotion_allowed=False)
