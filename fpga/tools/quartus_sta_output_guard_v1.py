"""Classify only three exact report/cache pairs observed during native STA v9.

The original full tree remains immutable. These six private-copy derived files
are retained and pinned separately, never silently called unchanged source DB.
All other QDB files (including other caches/models) remain immutable inputs.
"""
import hashlib
import json
from pathlib import Path
import re

OBSERVATION_SHA256 = '75cce465597624bc4ed8dce7735b689a97316046add475fe5deae1566191f348'
PAYLOAD_HEADER_HEX = '19000000ad0b000000000000aa00aa003300000056657273696f6e2032362e31'
PAIRS = {
 'qdb/_compiler/probe/_flat/26.1.0/_all/1/report.cmp.model': ('qdb/_compiler/probe/_flat/26.1.0/_all/1/report.cmp.rdb', 'rdb', 'undefined'),
 'qdb/_compiler/probe/_flat/26.1.0/_all/1/report.taw.model': ('qdb/_compiler/probe/_flat/26.1.0/_all/1/report.taw.rdb', 'rdb', 'undefined'),
 'qdb/_compiler/probe/root_partition/26.1.0/final/1/nightfury_io_sim_cache.900mv_ss_100c_slow.model': ('qdb/_compiler/probe/root_partition/26.1.0/final/1/.cache/nightfury_io_sim_cache.900mv_ss_100c_slow.hsd', 'hsd', 'cache')}


def classify(project, database_inventory):
    immutable = dict(database_inventory)
    derived = {}
    for model, (payload, kind, trait) in PAIRS.items():
        present = [name in immutable for name in (model, payload)]
        if not any(present):
            continue
        if not all(present):
            raise ValueError('incomplete observed STA output pair')
        metadata = json.loads((Path(project)/model).read_text())
        if (set(metadata) != {'type', 'trait', 'temp_payload_path', 'signature', 'bak'} or metadata['type'] != kind or
                metadata['trait'] != trait or metadata['temp_payload_path'] != '' or metadata['bak'] is not False or
                not re.fullmatch('[0-9a-f]{32}', metadata['signature'])):
            raise ValueError('STA output model does not match exact captured native schema/type/trait')
        for name in (model, payload):
            raw = (Path(project)/name).read_bytes()
            if name == payload and raw[:32].hex() != PAYLOAD_HEADER_HEX:
                raise ValueError('STA output payload does not match captured native 26.1 header')
            if hashlib.sha256(raw).hexdigest() != immutable[name]:
                raise ValueError('STA output identity changed during classification')
            derived[name] = dict(sha256=immutable.pop(name), bytes=len(raw), category='native_report' if kind == 'rdb' else 'native_io_delay_cache')
        derived[model]['model'] = metadata
    if not immutable:
        raise ValueError('nonempty compiled input DB required')
    return immutable, derived
