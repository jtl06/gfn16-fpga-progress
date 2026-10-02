"""Additive whole-engine route-v2 binding; frozen v1 derivatives untouched."""
import hashlib
from pathlib import Path

from fpga.reference import track_a4_blockroute_source_v1 as parent_guard

ROOT=Path(__file__).resolve().parents[1]
GUARD_SHA="eef6537b92717c58de4010139f8b81ce97337bc622dc14d5f110049aafd6d0a2"
ROUTE_SHA="0d292ef6072f250f9255b758319e0754b0265a3d26be694601bb96b25a9e1cfa"
ENGINE_NEW=parent_guard.ENGINE_NEW.replace("blockroute_v1", "blockroute_v2")
ADAPTER_NEW=parent_guard.ADAPTER_NEW.replace("blockroute_v1", "blockroute_v2")


def expected(parent):
    if hashlib.sha256(Path(parent_guard.__file__).read_bytes()).hexdigest()!=GUARD_SHA:
        raise ValueError("v1 exact source guard drift")
    if hashlib.sha256((ROOT/"rtl/kernel/genefer_track_a4_blockroute_v2.sv").read_bytes()).hexdigest()!=ROUTE_SHA:
        raise ValueError("route v2 source drift")
    text=parent_guard.expected(parent)
    if parent==parent_guard.ENGINE:
        text=parent_guard.replace_once(text,"module "+parent_guard.ENGINE_NEW+" #(","module "+ENGINE_NEW+" #(")
        text=parent_guard.replace_once(text,"genefer_track_a4_blockroute_v1 #(","genefer_track_a4_blockroute_v2 #(")
    else:
        text=parent_guard.replace_once(text,"module "+parent_guard.ADAPTER_NEW+" #(","module "+ADAPTER_NEW+" #(")
        text=parent_guard.replace_once(text,parent_guard.ENGINE_NEW+" #(",ENGINE_NEW+" #(")
    return text


def verify():
    result={}
    for parent,new in ((parent_guard.ENGINE,ENGINE_NEW),(parent_guard.ADAPTER,ADAPTER_NEW)):
        path=ROOT/"rtl/kernel"/(new+".sv")
        text=expected(parent)
        if path.read_text()!=text:
            raise ValueError("unguarded v2 engine derivative edit")
        result[str(path.relative_to(ROOT))]=hashlib.sha256(text.encode()).hexdigest()
    return result
