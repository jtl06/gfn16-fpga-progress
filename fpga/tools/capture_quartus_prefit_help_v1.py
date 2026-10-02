"""Bounded native help capture on the existing worker; never opens a project."""
import argparse
import hashlib
import json
from pathlib import Path
import shlex
import subprocess

SSH = ['ssh', '-F', '/private/tmp/gfn16-aws.nxtVrY/ssh_config', 'gfn16-aws']
BIN = '/home/ubuntu/gfn16-worker/altera_pro/26.1/quartus/bin/'
PROBES = [
    ('legacy-drc-help', 'quartus_drc', ['--help'], None),
    ('da-help', 'quartus_da', ['--help'], None),
    ('da-stage-help', 'quartus_da', ['--help=stage'], None),
    ('da-drc-package', 'quartus_da', ['-s'],
     'load_package drc\nhelp -pkg drc\nhelp -cmd drc::check_design\nexit\n'),
    ('syn-da-help', 'quartus_syn', ['--help=design_assistant'], None),
    ('sta-api', 'quartus_sta', ['-s'],
     'help -cmd create_timing_netlist\nhelp -cmd report_timing\n'
     'help -cmd get_operating_conditions\nhelp -cmd set_operating_conditions\n'
     'help -cmd get_timing_paths\nhelp -cmd get_path_info\nexit\n'),
]
API_PROBES = [
    ('syn-drc-package', 'quartus_syn', ['-s'],
     'load_package drc\nhelp -pkg drc\nhelp -cmd drc::check_design\nexit\n'),
    ('syn-help', 'quartus_syn', ['--help'], None),
    ('report-api', 'quartus_syn', ['-s'],
     'load_package report\nhelp -cmd load_report\nhelp -cmd get_report_panel_names\n'
     'help -cmd get_report_panel_row\nhelp -cmd get_report_panel_data\nexit\n'),
    ('sta-operating-api', 'quartus_sta', ['-s'],
     'help -cmd get_available_operating_conditions\n'
     'help -cmd get_operating_conditions_info\nhelp -cmd get_node_info\n'
     'help -cmd report_min_pulse_width\nhelp -cmd project_open\nexit\n'),
]
DA_PROBES = [
    ('drc-objects-api', 'quartus_syn', ['-s'],
     'load_package drc\nhelp -cmd drc::get_objects\nhelp -cmd drc::get_property\n'
     'help -cmd drc::list_properties\nhelp -cmd drc::get_stage_info\n'
     'help -cmd drc::get_option\nhelp -cmd drc::set_option\n'
     'help -cmd drc::should_run_drc\nputs [info body drc::check_design]\nexit\n'),
    ('report-count-api', 'quartus_syn', ['-s'],
     'load_package report\nhelp -cmd get_report_panel_id\n'
     'help -cmd get_number_of_rows\nhelp -cmd get_number_of_columns\n'
     'help -cmd unload_report\nexit\n'),
]
METADATA_PROBES = [
    ('drc-metadata', 'quartus_syn', ['-s'],
     'load_package drc\nputs "PREFIT_STAGES=[drc::get_stage_info]"\n'
     'puts "PREFIT_SYN_STAGE=[drc::get_stage_info -executable quartus_syn]"\n'
     'foreach kind {rule_set rule check_operation} {\n'
     'set objects [drc::get_objects -type $kind]\n'
     'puts "PREFIT_OBJECTS $kind [llength $objects]"\n'
     'foreach object [lrange $objects 0 4] {\n'
     'puts "PREFIT_OBJECT $kind $object"\n'
     'foreach key [drc::list_properties -object $object] {\n'
     'puts [list PREFIT_PROPERTY $key [drc::get_property -object $object -name $key]]\n'
     '}\n}\n}\nexit\n'),
    ('design-api', 'quartus_syn', ['-s'],
     'load_package design\nhelp -cmd design::load_design\n'
     'help -cmd design::list_valid_snapshot_names\nexit\n'),
]
RULE_PROBES = [
    ('synthesis-rules', 'quartus_syn', ['-s'],
     'load_package drc\n'
     'proc hx {v} {binary encode hex [encoding convertto utf-8 $v]}\n'
     'foreach r [drc::get_objects -type rule] {\n'
     'set op [drc::get_property -object $r -name check_operation]\n'
     'set snaps [drc::get_property -object $op -name snapshots]\n'
     'set execs [drc::get_property -object $op -name executables]\n'
     'if {[lsearch -exact $snaps synthesized] < 0 || [lsearch -exact $execs quartus_syn] < 0} {continue}\n'
     'set id [drc::get_property -object $r -name name]\n'
     'set vals [list $id]\n'
     'foreach key {severity short_description} {lappend vals [hx [drc::get_property -object $r -name $key]]}\n'
     'lappend vals [hx [drc::get_property -object $op -name configs]] [hx [drc::get_property -object $op -name device_families]]\n'
     'puts "PREFIT_RULE\t[join $vals \t]"\n'
     'set rr rule_record:default:$id\n'
     'foreach key [drc::list_properties -object $rr] {puts "PREFIT_RECORD\t$id\t[hx $key]\t[hx [drc::get_property -object $rr -name $key]]"}\n'
     '}\nputs PREFIT_RULES_COMPLETE\nexit\n'),
]


def capture(destination, probes=PROBES):
    destination.mkdir(parents=True, exist_ok=False)
    receipts = {}
    for name, executable, arguments, stdin in probes:
        request = {'argv': [BIN+executable, *arguments], 'stdin': stdin}
        # Every call gets an isolated directory. Missing executables, API errors,
        # timeouts and nonzero exits are retained; no rc==0 capability inference.
        program = (
            'import hashlib,json,pathlib,subprocess,tempfile; '
            'q=json.loads('+repr(json.dumps(request))+'); '
            'd=tempfile.mkdtemp(prefix="gfn-quartus-prefit-help-",dir="/tmp"); '
            'p=pathlib.Path(q["argv"][0]); '
            'paths=[p,p.parent.parent/"linux64"/p.name]; '
            'pins={str(x):hashlib.sha256(x.read_bytes()).hexdigest() '
            'for x in paths if x.is_file()}; '
            'r=subprocess.run(["/usr/bin/timeout","--kill-after=2s","35s",'
            '*q["argv"]],input=q["stdin"],cwd=d,stdout=subprocess.PIPE,'
            'stderr=subprocess.STDOUT,text=True,timeout=40); '
            'print(json.dumps(dict(request=q,cwd=d,returncode=r.returncode,'
            'tool_sha256=pins,raw=r.stdout)))'
        )
        command = SSH + ['python3 -c '+shlex.quote(program)]
        result = subprocess.run(command, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, timeout=50)
        transport = result.stdout.encode()
        (destination/(name+'.transport.log')).write_bytes(transport)
        receipt = {'command': command, 'transport_returncode': result.returncode,
                   'transport_sha256': hashlib.sha256(transport).hexdigest()}
        try:
            record = json.loads(result.stdout)
            raw = record.pop('raw').encode()
            (destination/(name+'.log')).write_bytes(raw)
            receipt.update(record, sha256=hashlib.sha256(raw).hexdigest())
        except (ValueError, TypeError, KeyError) as error:
            receipt['transport_error'] = str(error)
        receipts[name] = receipt
        # Write immediately so a later failure cannot discard earlier evidence.
        (destination/'capture.json').write_text(json.dumps(receipts, indent=2)+'\n')
        print(name, receipt.get('returncode', result.returncode), flush=True)
    return receipts


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination', type=Path)
    parser.add_argument('--api', action='store_true')
    parser.add_argument('--da-api', action='store_true')
    parser.add_argument('--metadata', action='store_true')
    parser.add_argument('--rules', action='store_true')
    args = parser.parse_args()
    capture(args.destination, RULE_PROBES if args.rules else METADATA_PROBES if args.metadata else
            DA_PROBES if args.da_api else API_PROBES if args.api else PROBES)
