"""Read-only, fail-closed source inventory and vendor pre-fit evidence gate.

Named sequential stages describe a transfer through a pipeline, not flops
"inside" a single STA register-to-register edge. Source anchors establish an
auditable inventory, not exhaustive synthesized connectivity or physical timing.
Whole-core admission additionally requires complete native crossing coverage
and a supported, complete Design Assistant report bound to these exact inputs.
"""
import hashlib
import json
from pathlib import Path
import re
import shlex

SCHEMA='prefit-structural-inventory-v1'

def need(ok,why):
    if not ok:raise ValueError(why)

def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()).hexdigest()

def file_digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def basenames(pins):
    result={Path(name).name:pin for name,pin in pins.items()}
    need(len(result)==len(pins),'unique baseline filenames')
    return result

def project_settings(root,spec,project):
    qsf_names=[name for name in spec['settings'] if Path(name).suffix=='.qsf']
    need(len(qsf_names)==1,'one pinned project QSF')
    qsf=root/qsf_names[0];globals_={};parameters={};compiled=[]
    for line in qsf.read_text().splitlines():
        words=shlex.split(line,comments=True)
        if not words:continue
        need(words[0] in ('set_global_assignment','set_instance_assignment','set_parameter'),'unsupported QSF command')
        if words[0]=='set_global_assignment':
            need(len(words)==4 and words[1]=='-name','literal global QSF assignment')
            if words[2]=='SYSTEMVERILOG_FILE':compiled.append(words[3])
            else:
                need(words[2] not in globals_,'duplicate global setting')
                globals_[words[2]]=words[3]
        elif words[0]=='set_parameter':
            need(len(words)==4 and words[1]=='-name' and words[2] not in parameters,'literal unique parameter')
            parameters[words[2]]=int(words[3])
    identity=spec['identity']
    need(globals_['TOP_LEVEL_ENTITY']==identity['top'] and globals_['DEVICE']==identity['device'] and int(globals_['SEED'])==identity['seed'],'actual QSF top/device/seed')
    need(parameters==identity['parameters'],'actual QSF parameters')
    need(len(compiled)==len(set(compiled)) and {(qsf.parent/p).resolve() for p in compiled}=={(root/p).resolve() for p in spec['sources']},'actual QSF compiled source closure')
    sdc=(qsf.parent/globals_['SDC_FILE']).resolve()
    need(sdc in {(root/p).resolve() for p in spec['settings']},'pinned SDC')
    periods=re.findall(r'^\s*create_clock\s+.*?-period\s+([0-9.]+)',sdc.read_text(),re.M)
    need(len(periods)==1 and float(periods[0])==identity['clock_period_ns'],'single exact declared clock period')

def file(root,name,pin):
    p=Path(name)
    need(type(name) is str and not p.is_absolute() and str(p)==name and '..' not in p.parts,'safe relative artifact')
    path=root/p
    need(path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(root),'regular bounded artifact')
    need(re.fullmatch('[0-9a-f]{64}',pin) is not None and file_digest(path)==pin,'artifact identity: '+name)
    return path

def identities(spec):
    source=digest(spec['sources']);settings=digest(spec['settings'])
    return dict(source_sha256=source,settings_sha256=settings,
        design_sha256=digest(dict(source_sha256=source,settings_sha256=settings,identity=spec['identity'])))

def source_inventory(root,spec):
    need(spec['schema']==SCHEMA and spec['scope'] in ('whole_core','component_probe','matched_component_benchmark'),'inventory schema/scope')
    need(set(spec['identity'])=={'top','device','parameters','clock_period_ns','seed'},'explicit physical design identity')
    need(spec['sources'] and spec['settings'],'source and settings closure required')
    texts={}
    for name,pin in spec['sources'].items():texts[name]=file(root,name,pin).read_text()
    for name,pin in spec['settings'].items():file(root,name,pin)
    manifests=[name for name in spec['settings'] if Path(name).name=='manifest.json']
    need(len(manifests)==1,'exact packaged project manifest')
    project=json.loads((root/manifests[0]).read_text())
    need(project['source_sha256']==basenames(spec['sources']),'project compiled source map match')
    controls=basenames(spec['settings']);controls.pop('manifest.json')
    need(project['control_sha256']==controls,'project control map match')
    need(all(project[k]==spec['identity'][k] for k in ('top','device','clock_period_ns','seed')),'project physical identity match')
    need(project['core_parameters']==spec['identity']['parameters'],'project parameter identity match')
    project_settings(root,spec,project)
    blocks=spec['blocks'];need(blocks and len(blocks)==len(set(blocks)),'unique macroblock inventory')
    crossings=[];all_stage_ids=set();findings=[]
    for transfer in spec['transfers']:
        name=transfer['id'];need(name not in crossings,'unique transfer id');crossings.append(name)
        need(transfer['producer'] in blocks and transfer['consumer'] in blocks,'known transfer endpoints')
        need(transfer['producer']!=transfer['consumer'],'cross-block transfer endpoints')
        need(transfer['signals'] and len(transfer['signals'])==len(set(transfer['signals'])),'explicit crossing signals')
        stages=transfer['registered_stages'];edges=[];stage_ids=set()
        for stage in stages:
            stage_id=stage['id'];need(stage_id not in stage_ids,'unique stage on transfer');stage_ids.add(stage_id);all_stage_ids.add(stage_id)
            need(stage['owner'] in blocks and stage['kind'] in ('flop','registered_ram_output'),'explicit sequential stage kind/owner')
            need(type(stage['edge']) is int and stage['edge']>=0,'stage edge index')
            edges.append(stage['edge'])
            need(stage['payload'] and stage['valid'] and type(stage['metadata']) is list,'payload/valid/metadata ledger')
            source=stage['source'];need(source in texts,'stage source in source closure')
            anchors=stage['anchors'];need(anchors and all(type(a) is str and a and texts[source].count(a)==1 for a in anchors),'unique exact sequential source anchors')
            need(any('<=' in a for a in anchors) if stage['kind']=='flop' else any('ram' in a.lower() for a in anchors),'sequential anchor required')
            need(stage.get('alignment')=='same_accepted_edge','explicit valid/payload/metadata alignment')
        need(edges==sorted(set(edges)),'ordered distinct sequential edges; no endpoint double counting')
        if len(stages)<2:
            exception=transfer.get('exception')
            if not exception or exception.get('kind') not in ('operation_latched_configuration','external_reset','phase_local_control'):
                findings.append(dict(transfer=name,reason='fewer_than_two_declared_registered_transfer_stages'))
            else:
                need(exception.get('reason') and exception.get('contract_anchors'),'bounded exception contract')
                for a in exception['contract_anchors']:
                    need(a['source'] in texts and texts[a['source']].count(a['text'])==1,'exception source contract')
        for control in transfer.get('control_reconvergence',[]):
            need(control['signal'] and control['sink'],'named combinational control reconvergence')
            if control.get('registered_barrier') not in stage_ids:
                findings.append(dict(transfer=name,signal=control['signal'],reason='unregistered_or_unlisted_control_reconvergence'))
    exclusions=spec['exclusions']
    for item in exclusions:
        need(item['kind'] in ('external_virtual_io','external_reset','inside_single_macroblock') and item['reason'] and item['endpoints'],'explicit bounded exclusion')
    need(spec.get('coverage_claim')=='declared_source_inventory_not_netlist_completeness','source evidence must not claim netlist completeness')
    return dict(transfers=crossings,stage_ids=sorted(all_stage_ids),findings=findings,exclusions=exclusions)

def evaluate(root,spec,vendor=None,reference=None):
    root=Path(root).resolve();ids=identities(spec);source=source_inventory(root,spec)
    result=dict(schema='prefit-structural-result-v1',scope=spec['scope'],**ids,
        checker_sha256=file_digest(__file__),inventory_sha256=digest(spec),
        source_inventory=source,source_evidence_only=True,fit_allowed=False,
        promotion_allowed=False,physical_timing_proven=False,blockers=[])
    result['blockers'].extend(source['findings'])
    if spec['scope']=='matched_component_benchmark':
        if reference is None:
            result['blockers'].append(dict(reason='missing_matched_component_reference'))
        else:
            need(reference['schema']=='prefit-matched-component-reference-v1','matched reference schema')
            need(reference['scope']=='component_benchmark' and reference['native_completed'] is True,'completed component benchmark reference only')
            need(reference['sources']==spec['sources'] and reference['settings']==spec['settings'] and reference['identity']==spec['identity'],'byte-identical component design/settings; no changed blocks')
            need(reference['evidence'],'content-addressed native reference evidence')
            for name,pin in reference['evidence'].items():file(root,name,pin)
            for key in ('execution_context','native_receipt'):
                need(reference[key] in reference['evidence'],'native baseline evidence descriptor')
            context=json.loads((root/reference['execution_context']).read_text())
            receipt=json.loads((root/reference['native_receipt']).read_text())
            need(context['source_sha256']==basenames(spec['sources']) and context['control_sha256']==basenames(spec['settings']),'native baseline exact source/control maps')
            need(context['qsf_parameters']==spec['identity']['parameters'],'native baseline parameters')
            need(receipt['status']=='PASS_component_host_runtime_pilot_only' and receipt['matched_sources_controls_seed_workers'] is True,'completed matched native benchmark receipt')
            need(receipt['source_manifest_sha256']==context['manifest_sha256']==basenames(spec['settings'])['manifest.json'],'baseline manifest binding')
            need(len(spec['blocks'])==1 and not spec['transfers'],'unchanged single macroblock benchmark only')
            result['matched_reference_sha256']=digest(reference)
            result['applicability']='Exact unchanged single-component matched benchmark. No new whole-core cross-block or changed-block Design Assistant qualification is asserted.'
            result['source_evidence_only']=False
    else:
        if vendor is None:
            result['blockers'].append(dict(reason='missing_native_cross_block_and_design_assistant_evidence'))
        else:
            need(vendor['schema']=='quartus-prefit-evidence-v1','supported vendor evidence schema')
            need(all(vendor.get(k)==v for k,v in ids.items()),'native report source/settings/design binding')
            need(vendor.get('helper_sha256')==spec.get('vendor_helper_sha256') and spec.get('vendor_helper_sha256'),'pinned supported vendor helper')
            need(vendor.get('tool_sha256')==spec.get('vendor_tool_sha256') and spec.get('vendor_tool_sha256') and vendor.get('raw_report_sha256'),'exact native tool and raw report evidence')
            need(vendor.get('phase') in ('post_synthesis','post_place'),'supported native pre-fit phase')
            for name,pin in vendor['raw_report_sha256'].items():file(root,name,pin)
            execution=vendor.get('native_execution_context')
            if vendor.get('native_execution_identity_verified') is not True or not execution:
                result['blockers'].append(dict(reason='native_execution_identity_not_verified'))
            else:
                need(vendor['raw_report_sha256'].get(execution['path'])==execution['sha256'],'native execution context captured')
                context=json.loads(file(root,execution['path'],execution['sha256']).read_text())
                need(context.get('schema')=='quartus-prefit-execution-v1' and context.get('platform')=='Linux' and context.get('owner_admission_passed') is True and context.get('returncode')==0,'admitted successful native execution context')
                need(all(context.get(k)==v for k,v in ids.items()) and context.get('tool_sha256')==vendor['tool_sha256'],'execution context exact design/tools')
                need(context.get('helper_sha256')==vendor['helper_sha256'] and context.get('native_script_sha256')==vendor.get('native_script_sha256') and vendor.get('native_script_sha256'),'native helper/script binding')
                for name in ('source','settings'):
                    pins=spec['sources'] if name=='source' else spec['settings']
                    need(context.get(name+'_before_sha256')==pins and context.get(name+'_after_sha256')==pins,'native input before/after binding')
                need(context.get('raw_report_sha256')=={p:h for p,h in vendor['raw_report_sha256'].items() if p!=execution['path']},'native context raw-report binding')
                need(context.get('database_before_sha256') and context.get('database_before_sha256')==context.get('database_after_sha256'),'read-only native database identity before/after')
            coverage=vendor.get('cross_block_coverage',{})
            if coverage.get('supported') is not True or coverage.get('complete') is not True:
                result['blockers'].append(dict(reason='unsupported_or_incomplete_native_cross_block_coverage'))
            else:
                need(all(type(coverage.get(k)) is list for k in ('observed_crossings','uncovered_endpoints','unjustified_findings')),'complete native crossing report fields')
                if sorted(coverage['observed_crossings'])!=sorted(source['transfers']) or coverage['uncovered_endpoints']:
                    result['blockers'].append(dict(reason='native_crossing_inventory_mismatch_or_uncovered_endpoints'))
            if coverage.get('unjustified_findings'):
                result['blockers'].append(dict(reason='native_cross_block_findings',findings=coverage['unjustified_findings']))
            da=vendor.get('design_assistant',{})
            if da.get('supported') is not True or da.get('complete') is not True or not da.get('rules_checked'):
                result['blockers'].append(dict(reason='unsupported_or_incomplete_design_assistant'))
            else:
                need(all(type(da.get(k)) is list for k in ('rules_checked','high_severity_findings','new_high_severity_findings')),'complete native Design Assistant fields')
            if da.get('new_high_severity_findings'):
                result['blockers'].append(dict(reason='new_high_severity_design_assistant',findings=da['new_high_severity_findings']))
            if da.get('high_severity_findings') and da.get('high_severity_classification_complete') is not True:
                result['blockers'].append(dict(reason='unclassified_high_severity_design_assistant'))
            result['vendor_evidence_sha256']=digest(vendor)
            result['source_evidence_only']=False
    result['fit_allowed']=not result['blockers']
    result['status']=('PASS_scoped_prefit_admission' if result['fit_allowed'] else 'BLOCKED_prefit_evidence')
    return result

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True)
    p.add_argument('--spec',type=Path,required=True);p.add_argument('--vendor',type=Path);p.add_argument('--reference',type=Path)
    a=p.parse_args();read=lambda path:json.loads(path.read_text()) if path else None
    report=evaluate(a.root,read(a.spec),read(a.vendor),read(a.reference));print(json.dumps(report,indent=2))
    raise SystemExit(0 if report['fit_allowed'] else 2)
