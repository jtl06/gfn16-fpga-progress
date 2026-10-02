"""One immutable design ticket; settings are data, never a hand-built variant."""
import argparse
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('standing_fit_submit_primitives', HERE/'fit_dispatch.py')
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)


def submit(queue, identifier, project, period, seed, slot_shapes, scope, source_contract,
           workers='auto', priority=50, requires=None, after=None, after_collection_action=None,
           profile_ref=None, track='S', purpose='whole',mode='full',native_source_gate=None,runtime_profile=None,optimization_mode=None,memory_gib=None,resource_basis=None,provisional_geometry=None):
    profile_ref = profile_ref or d.reference(d.FPGA/'cloud/fit-host-profiles-v1.json')
    ticket = dict(schema='standing-fit-ticket-v1', id=identifier, priority=priority, track=track, purpose=purpose, scope=scope,
                  snapshot=d.snapshot(project), settings=d.settings(period, seed, workers,optimization_mode),
                  slot_shapes=slot_shapes, source_contract=source_contract, requires=requires or [],
                  after=after or [], after_collection_action=after_collection_action)
    if mode!='full' or native_source_gate is not None:
        ticket.update(mode=mode,native_source_gate=native_source_gate)
    if runtime_profile is not None:ticket['runtime_profile']=runtime_profile
    if memory_gib is not None:ticket['memory_gib']=memory_gib
    if resource_basis is not None:ticket['resource_basis']=resource_basis
    if provisional_geometry is not None:ticket['provisional_geometry']=provisional_geometry
    d.validate_ticket(ticket, profile_ref)
    queue = Path(queue).resolve()
    d.need(queue.is_relative_to(d.FPGA), 'owned standing queue')
    target = queue/'tickets'/(identifier+'.json')
    if target.exists():
        d.need(d.read(d.reference(target)) == ticket, 'same logical ID cannot replace source/settings')
    else:
        # Publish atomically: dispatch never sees half a ticket. One submit
        # lock also makes same-ID retries deterministic across owner processes.
        q = d.frozen_queue()
        with q.controller_lock(queue/'submit'):
            if target.exists():
                d.need(d.read(d.reference(target)) == ticket, 'concurrent source/settings drift')
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                temporary = target.parent/(identifier+'.pending')
                if temporary.exists():
                    d.need(d.read(d.reference(temporary)) == ticket, 'partial submission source/settings drift')
                else:
                    d.save(temporary, ticket)
                temporary.rename(target)
    return d.reference(target)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--queue', type=Path, required=True)
    parser.add_argument('--id', required=True)
    parser.add_argument('--project', type=Path, required=True)
    parser.add_argument('--period-ns', required=True)
    parser.add_argument('--seed', type=int, required=True)
    parser.add_argument('--workers', default='auto')
    parser.add_argument('--slot-shape', action='append', required=True, help='azure4[:a,b,c,d] or aws6[:a,b]')
    parser.add_argument('--scope', choices=('whole_core', 'component_probe'), required=True)
    parser.add_argument('--priority', type=int, default=50)
    parser.add_argument('--track', choices=('S', 'A'), required=True)
    parser.add_argument('--purpose', choices=('whole', 'sizing', 'two_context', 'p16_diet', 'clock_push', 'a10_pending'), required=True)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--exemption', choices=('constraint_seed_only', 'component_sizing_probe','synthesis_only_resource_screen','place_only_resource_probe'))
    source.add_argument('--structural-spec', type=Path)
    parser.add_argument('--structural-spec-sha256')
    parser.add_argument('--requires', type=Path, help='pinned field-contract list; actual native prerequisites remain mandatory')
    parser.add_argument('--requires-sha256')
    parser.add_argument('--after', type=Path)
    parser.add_argument('--after-sha256')
    parser.add_argument('--audit-search', action='store_true')
    parser.add_argument('--mode',choices=('full','synthesis_only','place_only'),default='full')
    parser.add_argument('--native-source-gate',help='Actual normal queue ID; dispatch waits for typed PASS and every RTL source match')
    parser.add_argument('--runtime-profile',choices=(d.P8_FULL['kind'],d.P16_FULL['kind']),help='Explicit whole AW16 P8 3h or P16 4h full flow; default remains 6h; timeout preserves partial failure, never extends/retries')
    parser.add_argument('--optimization-mode',choices=('High Performance Effort','Aggressive Area'),help='Installed supported compiler strategy; absent keeps frozen source setting')
    parser.add_argument('--memory-gib',type=int,choices=(32,40),help='32GiB whole P16, or AWS aws6:a --workers12 whole-host40GiB; aggregate ceilings unchanged')
    parser.add_argument('--resource-basis',type=Path)
    parser.add_argument('--resource-basis-sha256')
    parser.add_argument('--provisional-geometry',type=Path,help='Explicit AW8-only normal plus exact same-generator full geometry derivation')
    parser.add_argument('--provisional-geometry-sha256')
    args = parser.parse_args()
    profile = d.reference(d.FPGA/'cloud/fit-host-profiles-v1.json')
    shapes = d.profiles(profile)['shapes']
    selected = {}
    for value in args.slot_shape:
        shape, _, slots = value.partition(':')
        d.need(shape in shapes and shape not in selected, 'unique existing fit shape')
        selected[shape] = slots.split(',') if slots else list(shapes[shape]['slots'])
    contract = dict(exemption=args.exemption) if args.exemption else dict(structural_spec=dict(path=str(args.structural_spec.resolve()), sha256=args.structural_spec_sha256))
    refs = lambda path,pin:d.read(dict(path=str(path.resolve()), sha256=pin)) if path else []
    result = submit(args.queue, args.id, args.project, args.period_ns, args.seed, selected, args.scope, contract,
                    workers='auto' if args.workers == 'auto' else int(args.workers), priority=args.priority,
                    requires=refs(args.requires, args.requires_sha256), after=refs(args.after, args.after_sha256),
                    after_collection_action=dict(kind='timing_audit_search', max_selected=8) if args.audit_search else None,
                    track=args.track, purpose=args.purpose,mode=args.mode,native_source_gate=args.native_source_gate,runtime_profile=args.runtime_profile,optimization_mode=args.optimization_mode,memory_gib=args.memory_gib,
                    resource_basis=dict(path=str(args.resource_basis.resolve()),sha256=args.resource_basis_sha256) if args.resource_basis else None,
                    provisional_geometry=dict(path=str(args.provisional_geometry.resolve()),sha256=args.provisional_geometry_sha256) if args.provisional_geometry else None)
    print(d.json.dumps(result))


if __name__ == '__main__':
    main()
