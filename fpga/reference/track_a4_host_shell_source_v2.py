"""Exact additive fixes for the preserved v1 shell build-only warning failure."""
import hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PARENTS={
    "rtl/kernel/genefer_track_a4_canonical_controller_v1.sv":"f7f1eaaf1637553f4c8e11880c312ddb841f8514cbb5177c9c4f1b5d979351f5",
}
SHELL_TICKET=ROOT/"docs/briefs/replies/2026-10-01-B20260930A-A4-host-shell-exploratory-ticket-v1.json"
TICKET_SHA="3a603e97db2c3b24cc46a1f32e974e82750db415cafddf85cf8d9cfc4bbacef0"


def once(text,old,new):
    if text.count(old)!=1:raise ValueError("v2 exact delta anchor drift: "+old[:80])
    return text.replace(old,new,1)


def expected(path):
    import json
    if hashlib.sha256(SHELL_TICKET.read_bytes()).hexdigest()!=TICKET_SHA:raise ValueError("v1 ticket drift")
    pins=json.loads(SHELL_TICKET.read_text())["source_sha256"]
    pin=PARENTS.get(path,pins.get(path))
    if pin is None:raise ValueError("unbound parent")
    text=(ROOT/path).read_text()
    if hashlib.sha256(text.encode()).hexdigest()!=pin:raise ValueError("frozen parent drift: "+path)
    new=path.replace("_v1.","_v2.")
    old_name=Path(path).stem
    new_name=Path(new).stem
    if path.endswith(".sv"):
        text=once(text,"module "+old_name+" #(","module "+new_name+" #(")
    if "canonical_controller_v1.sv" in path:
        text=once(text,"    wire write_ok=cell_tag==AW'(written) && int'(written)<N;\n",
                  "    wire write_ok=cell_tag==AW'(written) && int'(written)<N;\n    wire [3:0] write_bank=4'(cell_tag>>(AW-4));\n")
        if text.count("int'(cell_tag>>(AW-4))")!=2:raise ValueError("expected two bank uses")
        text=text.replace("int'(cell_tag>>(AW-4))","int'(write_bank)")
    elif "control_fsm_v1.sv" in path:
        text=once(text,"                       bus.canonical_passes>3 || bus.canonical_max_digit>=base_reg)",
                       "                       bus.canonical_max_digit>=base_reg)")
        if "bus.canonical_passes==0" not in text:raise ValueError("zero-pass guard lost")
    elif "host_shell_v1.sv" in path:
        text=once(text,"genefer_track_a4_control_fsm_v1 #(","genefer_track_a4_control_fsm_v2 #(")
        text=once(text,"genefer_track_a4_canonical_controller_v1 #(","genefer_track_a4_canonical_controller_v2 #(")
    elif path.endswith("host_shell_v1.cpp"):
        if text.count("Vgenefer_track_a4_host_shell_v1")!=2:raise ValueError("bench rename anchors")
        text=text.replace("Vgenefer_track_a4_host_shell_v1","Vgenefer_track_a4_host_shell_v2")
    else:raise ValueError("unsupported source successor")
    return new,text


def verify():
    paths=["rtl/kernel/genefer_track_a4_canonical_controller_v1.sv","rtl/kernel/genefer_track_a4_control_fsm_v1.sv",
           "rtl/kernel/genefer_track_a4_host_shell_v1.sv","rtl/tb/track_a4_host_shell_v1.cpp"]
    result={}
    for path in paths:
        new,text=expected(path)
        if (ROOT/new).read_text()!=text:raise ValueError("unguarded v2 edit: "+new)
        result[new]=hashlib.sha256(text.encode()).hexdigest()
    return result
