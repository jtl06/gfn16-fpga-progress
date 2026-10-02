import tempfile
import unittest
from pathlib import Path
from synthesis.prepare import prepare, TARGETS, FIELD_CONSTANTS_27, FIELD_CONSTANTS_36


class SynthesisPrepareTests(unittest.TestCase):
    def test_rowcompact_targets_keep_orient8_controls_and_exclude_rootfusion(self):
        from reference.prefetch_r2_rowcompact_structure import NAMES, validate_files
        validated=validate_files(Path(__file__).resolve().parents[1])
        pins={Path(name).name:digest for name,digest in validated.items()}
        pairs=[('ntt27_prefetch_r2_host_broadcast_orient8_64',
                'ntt27_prefetch_r2_host_broadcast_orient8_rowcompact_64',field,7,2)
               for field in (1,2,3)]
        pairs.append(('square_core27_stream_prefetch_r2_host_broadcast_orient8_ntt64_carry16',
                      'square_core27_stream_prefetch_r2_host_broadcast_orient8_rowcompact_ntt64_carry16',1,16,3))
        for baseline,candidate,field,count,replaced in pairs:
            with self.subTest(target=candidate,field=field),tempfile.TemporaryDirectory() as d:
                a,b=Path(d)/'old',Path(d)/'new'
                old=prepare(a,baseline,aw=16,period=10.0,field=field,processors=4)
                new=prepare(b,candidate,aw=16,period=10.0,field=field,processors=4)
                expected={NAMES.get(name[:-3],name[:-3])+'.sv':
                          pins[NAMES[name[:-3]]+'.sv'] if name[:-3] in NAMES else digest
                          for name,digest in old['source_sha256'].items()}
                self.assertEqual(new['source_sha256'],expected)
                self.assertEqual(len(expected),count)
                self.assertEqual(sum(name[:-3] in NAMES for name in old['source_sha256']),replaced)
                self.assertTrue(all('rootfused' not in name for name in expected))
                allowed={'target','top','source_sha256','arithmetic_profile','matched_probe_group','matched_baseline_target'}
                self.assertEqual({k:v for k,v in old.items() if k not in allowed},
                                 {k:v for k,v in new.items() if k not in allowed})
                qsf=(a/'probe.qsf').read_text()
                for before,after in NAMES.items():qsf=qsf.replace(before,after)
                self.assertEqual(qsf,(b/'probe.qsf').read_text())
                for name in ('probe.sdc','probe.qpf','run.tcl'):
                    self.assertEqual((a/name).read_bytes(),(b/name).read_bytes())
                self.assertEqual(new['root_profile_format'],2)
                self.assertEqual(new['status'],'prepared_not_vendor_validated')
                self.assertFalse(new['bitstream_generation'])
                self.assertEqual(new['allowed_stages'],['syn','fit','sta'])
                if count==7:
                    self.assertEqual(new['matched_baseline_target'],baseline)
                    self.assertEqual(new['host_lanes'],16)
                    self.assertEqual(new['arithmetic_lanes'],64)
                    self.assertEqual(new['field_parameters'],{'P':FIELD_CONSTANTS_27[field-1][0],
                                                              'Q':FIELD_CONSTANTS_27[field-1][1]})
                    self.assertEqual(new['montgomery_radix_bits'],32)
                else:
                    self.assertEqual(new['core_parameters'],{'NTT_LANES':64})
                    self.assertEqual(new['core_montgomery_radix_bits'],32)

    def test_root_fusion_targets_change_only_sources_and_identity(self):
        from reference.prefetch_r2_rootfused_structure import NAMES, validate_files
        root=Path(__file__).resolve().parents[1]
        validated=validate_files(root)
        candidate_pins={Path(name).name:digest for name,digest in validated.items()}
        pairs=[('ntt27_prefetch_r2_host_broadcast_orient8_64',
                'ntt27_prefetch_r2_host_broadcast_orient8_rootfused_64',field,7,2)
               for field in (1,2,3)]
        pairs.append(('square_core27_stream_prefetch_r2_host_broadcast_orient8_ntt64_carry16',
                      'square_core27_stream_prefetch_r2_host_broadcast_orient8_rootfused_ntt64_carry16',1,16,3))
        for baseline,candidate,field,count,replaced in pairs:
            # Ephemeral preparation fixtures only: no durable physical probe,
            # staging, HDL compiler, synthesis or fitting is invoked here.
            with self.subTest(target=candidate,field=field),tempfile.TemporaryDirectory() as d:
                a,b=Path(d)/'old',Path(d)/'new'
                old=prepare(a,baseline,aw=16,period=10.0,field=field,processors=4)
                new=prepare(b,candidate,aw=16,period=10.0,field=field,processors=4)
                expected={NAMES.get(name[:-3],name[:-3])+'.sv':
                          candidate_pins[NAMES[name[:-3]]+'.sv'] if name[:-3] in NAMES else digest
                          for name,digest in old['source_sha256'].items()}
                self.assertEqual(new['source_sha256'],expected)
                self.assertEqual(len(expected),count)
                self.assertEqual(sum(name[:-3] in NAMES for name in old['source_sha256']),replaced)
                allowed={'target','top','source_sha256','arithmetic_profile','matched_probe_group','matched_baseline_target'}
                self.assertEqual({k:v for k,v in old.items() if k not in allowed},
                                 {k:v for k,v in new.items() if k not in allowed})
                qsf=(a/'probe.qsf').read_text()
                for before,after in NAMES.items():qsf=qsf.replace(before,after)
                self.assertEqual(qsf,(b/'probe.qsf').read_text())
                for name in ('probe.sdc','probe.qpf','run.tcl'):
                    self.assertEqual((a/name).read_bytes(),(b/name).read_bytes())
                self.assertEqual(new['root_profile_format'],2)
                self.assertFalse(new['bitstream_generation'])
                self.assertEqual(new['allowed_stages'],['syn','fit','sta'])
                self.assertEqual(new['status'],'prepared_not_vendor_validated')
                if count==7:
                    self.assertEqual(new['matched_baseline_target'],baseline)
                    self.assertEqual(new['host_lanes'],16)
                    self.assertEqual(new['arithmetic_lanes'],64)
                    self.assertEqual(new['field_parameters'],{'P':FIELD_CONSTANTS_27[field-1][0],
                                                              'Q':FIELD_CONSTANTS_27[field-1][1]})
                    self.assertEqual(new['montgomery_radix_bits'],32)
                else:
                    self.assertEqual(new['core_parameters'],{'NTT_LANES':64})
                    self.assertEqual(new['core_montgomery_radix_bits'],32)

    def test_orientation_replica_targets_preserve_physical_controls(self):
        from reference.prefetch_r2_orient8_structure import NAMES, CANDIDATE_PINS, validate_files
        validate_files(Path(__file__).resolve().parents[1])
        pairs=[('ntt27_prefetch_r2_host_broadcast64','ntt27_prefetch_r2_host_broadcast_orient8_64',field,7)
               for field in (1,2,3)]
        pairs.append(('square_core27_stream_prefetch_r2_host_broadcast_ntt64_carry16',
                      'square_core27_stream_prefetch_r2_host_broadcast_orient8_ntt64_carry16',1,16))
        for baseline,candidate,field,count in pairs:
            with self.subTest(target=candidate,field=field),tempfile.TemporaryDirectory() as d:
                a,b=Path(d)/'old',Path(d)/'new'
                old=prepare(a,baseline,aw=16,field=field,processors=4)
                new=prepare(b,candidate,aw=16,field=field,processors=4)
                expected={NAMES.get(name[:-3],name[:-3])+'.sv':
                          CANDIDATE_PINS[NAMES[name[:-3]]] if name[:-3] in NAMES else digest
                          for name,digest in old['source_sha256'].items()}
                self.assertEqual(new['source_sha256'],expected)
                self.assertEqual(len(expected),count)
                allowed={'target','top','source_sha256','arithmetic_profile','matched_probe_group','matched_baseline_target'}
                self.assertEqual({k:v for k,v in old.items() if k not in allowed},
                                 {k:v for k,v in new.items() if k not in allowed})
                qsf=(a/'probe.qsf').read_text()
                for before,after in NAMES.items():qsf=qsf.replace(before,after)
                self.assertEqual(qsf,(b/'probe.qsf').read_text())
                for name in ('probe.sdc','probe.qpf','run.tcl'):
                    self.assertEqual((a/name).read_bytes(),(b/name).read_bytes())
                self.assertEqual(new['root_profile_format'],2)
                self.assertFalse(new['bitstream_generation'])

    def test_whole_core_broadcast_probe_has_only_two_source_substitutions(self):
        from reference.core27_prefetch_r2_host_broadcast_core_structure import KERNEL_PINS
        with tempfile.TemporaryDirectory() as d:
            a,b=Path(d)/'r2',Path(d)/'broadcast'
            old=prepare(a,'square_core27_stream_prefetch_r2_ntt64_carry16',aw=16,processors=4)
            new=prepare(b,'square_core27_stream_prefetch_r2_host_broadcast_ntt64_carry16',aw=16,processors=4)
            self.assertEqual(new['source_sha256'],KERNEL_PINS)
            self.assertEqual(len(new['source_sha256']),16)
            self.assertEqual(new['root_profile_format'],2)
            self.assertFalse(new['bitstream_generation'])
            allowed={'target','top','source_sha256','arithmetic_profile'}
            self.assertEqual({k:v for k,v in old.items() if k not in allowed},
                             {k:v for k,v in new.items() if k not in allowed})
            qsf=(a/'probe.qsf').read_text()
            for before,after in (
                ('genefer_square_core27_stream_prefetch_r2','genefer_square_core27_stream_prefetch_r2_host_broadcast'),
                ('genefer_ntt_banked27_prefetch_r2_host_engine','genefer_ntt_banked27_prefetch_r2_host_broadcast_engine')):
                qsf=qsf.replace(before,after)
            self.assertEqual(qsf,(b/'probe.qsf').read_text())
            for name in ('probe.sdc','probe.qpf','run.tcl'):
                self.assertEqual((a/name).read_bytes(),(b/name).read_bytes())

    def test_host_broadcast_probes_match_wrapper_boundary_all_fields(self):
        import json
        root=Path(__file__).resolve().parents[1]
        frozen=json.loads((root/'synthesis/host_broadcast_memory_pair_plan.json').read_text())['source_sha256']
        baseline='genefer_ntt_banked27_prefetch_r2_host_engine'
        candidate='genefer_ntt_banked27_prefetch_r2_host_broadcast_engine'
        common=['genefer_sdp_ram32.sv','genefer_montgomery_mul27_sparse_pipe.sv',
                'genefer_ntt_banked27_engine.sv','genefer_sp_ram.sv','genefer_root_recurrence27.sv',
                'genefer_ntt_banked27_prefetch_r2_engine.sv']
        for field,(p,q,_) in enumerate(FIELD_CONSTANTS_27,1):
            with self.subTest(field=field),tempfile.TemporaryDirectory() as d:
                a,b=Path(d)/'baseline',Path(d)/'candidate'
                old=prepare(a,'ntt27_prefetch_r2_host64',aw=16,field=field,processors=4)
                new=prepare(b,'ntt27_prefetch_r2_host_broadcast64',aw=16,field=field,processors=4)
                for manifest,top,role in ((old,baseline,'baseline'),(new,candidate,'candidate')):
                    self.assertEqual(manifest['top'],top)
                    self.assertEqual(list(manifest['source_sha256']),common+[top+'.sv'])
                    self.assertEqual(manifest['source_sha256'],
                        {name:frozen['rtl/kernel/'+name] for name in common+[top+'.sv']})
                    self.assertEqual(manifest['field_parameters'],{'P':p,'Q':q})
                    self.assertEqual(manifest['field_profile'],'experimental27')
                    self.assertEqual(manifest['montgomery_radix_bits'],32)
                    self.assertEqual(manifest['host_lanes'],16)
                    self.assertEqual(manifest['arithmetic_lanes'],64)
                    self.assertEqual(manifest['root_profile_format'],2)
                    self.assertEqual(manifest['matched_probe_group'],'prefetch_r2_host_broadcast64_v1')
                    self.assertEqual(manifest['matched_probe_role'],role)
                    self.assertFalse(manifest['bitstream_generation'])
                    self.assertEqual(manifest['status'],'prepared_not_vendor_validated')
                different={'target','top','source_sha256','matched_probe_role'}
                self.assertEqual({k:v for k,v in old.items() if k not in different},
                                 {k:v for k,v in new.items() if k not in different})
                # Exact QSF delta is wrapper top/source only, not raw-child ports
                # or geometry. No placement/clock/seed/worker differences hide here.
                self.assertEqual((a/'probe.qsf').read_text().replace(baseline,candidate),
                                 (b/'probe.qsf').read_text())
                qsf=(b/'probe.qsf').read_text()
                for assignment in ('set_parameter -name AW 16','set_parameter -name LANES 64',
                    'set_parameter -name HOST_LANES 16','set_global_assignment -name SEED 1',
                    'set_global_assignment -name NUM_PARALLEL_PROCESSORS 4'):
                    self.assertIn(assignment+'\n',qsf)
                for name in ('probe.sdc','probe.qpf','run.tcl'):
                    self.assertEqual((a/name).read_bytes(),(b/name).read_bytes())

    def test_host_broadcast_virtual_ports_match_actual_wrapper_interface(self):
        import re
        root=Path(__file__).resolve().parents[1]
        for target in ('ntt27_prefetch_r2_host64','ntt27_prefetch_r2_host_broadcast64'):
            top,_,pins=TARGETS[target]
            text=(root/'rtl/kernel'/(top+'.sv')).read_text()
            header=text.split(') (',1)[1].split(');',1)[0]
            ports=[]
            for declaration in header.split(',\n'):
                plain=re.sub(r'\[[^]]+\]','',declaration)
                plain=re.sub(r'\b(input|output|logic)\b','',plain)
                ports.extend(x.strip() for x in plain.split(',') if x.strip())
            self.assertEqual(set(ports)-{'clk'},{pin.removesuffix('[*]') for pin in pins})
            self.assertEqual(len(pins),len(set(pins)))
            self.assertNotIn('root_we',pins)
            self.assertNotIn('clk',pins)
        # Isolated targets add no annotations/parameters to the old raw engine.
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'old';manifest=prepare(out,'ntt27_prefetch64',aw=16)
            self.assertNotIn('host_lanes',manifest)
            self.assertNotIn('root_profile_format',manifest)
            self.assertNotIn('HOST_LANES',(out/'probe.qsf').read_text())

    def test_canonical_helper_probe_matches_sparse_controls_all_fields(self):
        with tempfile.TemporaryDirectory() as d:
            for field in (1,2,3):
                a,b=Path(d)/f'old-{field}',Path(d)/f'new-{field}'
                old=prepare(a,'multiplier27_sparse',field=field,processors=4)
                new=prepare(b,'multiplier27_canonical',field=field,processors=4)
                self.assertEqual(new['source_sha256'],{
                    'genefer_montgomery_mul27_canonical_pipe.sv':
                    '1d29fffb22b5ab9414d83b2cdde4d4068d605b51d60bda6d7b5d47688e181352'})
                for key in ('device','field','field_parameters','field_profile',
                            'montgomery_radix_bits','compile_processors','clock_period_ns',
                            'allowed_stages','bitstream_generation'):
                    self.assertEqual(new[key],old[key])
                self.assertEqual(new['field_profile'],'experimental27')
                self.assertEqual(new['montgomery_radix_bits'],32)
                self.assertFalse(new['bitstream_generation'])
                def controls(path):
                    return [line for line in (path/'probe.qsf').read_text().splitlines()
                        if not line.startswith(('set_global_assignment -name TOP_LEVEL_ENTITY ',
                                                'set_global_assignment -name SYSTEMVERILOG_FILE '))]
                self.assertEqual(controls(a),controls(b))
                for name in ('probe.sdc','probe.qpf','run.tcl'):
                    self.assertEqual((a/name).read_bytes(),(b/name).read_bytes())

    def test_r2_fusion_keeps_prefetch_physical_controls(self):
        from reference.core27_prefetch_r2_structure import NAMES
        with tempfile.TemporaryDirectory() as d:
            a,b=Path(d)/'parent',Path(d)/'fusion'
            old=prepare(a,'square_core27_stream_prefetch_ntt64_carry16',aw=16,processors=4)
            new=prepare(b,'square_core27_stream_prefetch_r2_ntt64_carry16',aw=16,processors=4)
            rename={k+'.sv':v+'.sv' for k,v in NAMES.items()}
            self.assertEqual(list(new['source_sha256']),[rename.get(n,n) for n in old['source_sha256']])
            self.assertEqual(new['root_profile_format'],2)
            self.assertEqual(new['arithmetic_profile'],'atomic27_stream_precision_prefetch_r2_format2_v1')
            self.assertFalse(new['bitstream_generation'])
            self.assertEqual(new['status'],'prepared_not_vendor_validated')
            for key in ('device','address_width','core_parameters','clock_period_ns','compile_processors',
                        'allowed_stages','core_field_basis','core_montgomery_radix_bits'):
                self.assertEqual(new[key],old[key])
            for name in set(old['source_sha256']) & set(new['source_sha256']):
                self.assertEqual(old['source_sha256'][name],new['source_sha256'][name])
            def controls(path):
                return [line for line in (path/'probe.qsf').read_text().splitlines()
                    if not line.startswith(('set_global_assignment -name TOP_LEVEL_ENTITY ',
                                            'set_global_assignment -name SYSTEMVERILOG_FILE '))]
            self.assertEqual(controls(a),controls(b))
            self.assertIn('set_global_assignment -name VERILOG_CONSTANT_LOOP_LIMIT 10000',controls(b))
            for name in ('probe.sdc','probe.qpf','run.tcl'):
                self.assertEqual((a/name).read_bytes(),(b/name).read_bytes())

    def test_explicit_effort_experiment_changes_only_one_qsf_assignment(self):
        with tempfile.TemporaryDirectory() as d:
            a,b=Path(d)/'baseline',Path(d)/'effort'
            old=prepare(a,'ntt27_tiled64',aw=16,processors=4)
            new=prepare(b,'ntt27_tiled64',aw=16,processors=4,optimization_mode='High Performance Effort')
            self.assertNotIn('requested_optimization_mode',old)
            self.assertEqual(new['requested_optimization_mode'],'High Performance Effort')
            self.assertFalse(new['optimization_mode_effective_verified'])
            self.assertEqual({k:v for k,v in new.items() if k not in
                {'requested_optimization_mode','optimization_mode_effective_verified'}},old)
            extra='set_global_assignment -name OPTIMIZATION_MODE "High Performance Effort"\n'
            candidate=(b/'probe.qsf').read_text()
            self.assertEqual(candidate.count(extra),1)
            self.assertEqual(candidate.replace(extra,''),(a/'probe.qsf').read_text())
            for name in ('probe.sdc','probe.qpf','run.tcl'):
                self.assertEqual((a/name).read_bytes(),(b/name).read_bytes())

    def test_reject_unsupported_effort_before_creating_output(self):
        with tempfile.TemporaryDirectory() as d:
            for i,(mode,edition) in enumerate((('not-a-mode','pro'),('High Performance Effort','standard'),
                                             ('High Performance Effort"\nset x 1','pro'))):
                path=Path(d)/str(i)
                with self.assertRaises(ValueError):
                    prepare(path,'ntt27_tiled64',optimization_mode=mode,edition=edition)
                self.assertFalse(path.exists())

    def test_prefetch_data_width_probe_preserves_parent_constraints(self):
        for field in (1,2,3):
            with self.subTest(field=field),tempfile.TemporaryDirectory() as d:
                a,b=Path(d)/'parent',Path(d)/'candidate'
                old=prepare(a,'ntt27_prefetch64',aw=16,field=field,processors=4)
                new=prepare(b,'ntt27_prefetch_data27_64',aw=16,field=field,processors=4)
                self.assertEqual(new['field_profile'],'experimental27')
                self.assertEqual(new['montgomery_radix_bits'],32)
                for key in ('field_parameters','address_width','clock_period_ns','compile_processors','allowed_stages'):
                    self.assertEqual(new[key],old[key])
                self.assertFalse(new['bitstream_generation'])
                self.assertEqual(new['status'],'prepared_not_vendor_validated')
                self.assertEqual(set(new['source_sha256']),
                    (set(old['source_sha256'])-{'genefer_ntt_banked27_prefetch_engine.sv'}) |
                    {'genefer_ntt_banked27_prefetch_data27_engine.sv','genefer_sdp_ram27_residue.sv'})
                for name in set(old['source_sha256']) & set(new['source_sha256']):
                    self.assertEqual(old['source_sha256'][name],new['source_sha256'][name])
                def controls(path):
                    return [line for line in (path/'probe.qsf').read_text().splitlines()
                            if not line.startswith(('set_global_assignment -name TOP_LEVEL_ENTITY ',
                                                    'set_global_assignment -name SYSTEMVERILOG_FILE '))]
                self.assertEqual(controls(a),controls(b))
                for name in ('probe.sdc','probe.qpf','run.tcl'):
                    self.assertEqual((a/name).read_bytes(),(b/name).read_bytes())
                self.assertEqual(TARGETS['ntt27_prefetch_data27_64'][2],TARGETS['ntt27_prefetch64'][2])

    def test_isolated_routing_probes_preserve_parent_constraints(self):
        import hashlib
        root=Path(__file__).resolve().parents[1]
        for parent,target,oldtop,newtop in (
            ('ntt27_tiled64','ntt27_rootpipe64','genefer_ntt_banked27_tiled_engine','genefer_ntt_banked27_rootpipe_engine'),
            ('ntt27_pair_checked64','ntt27_pair_row64','genefer_ntt_banked27_pair_checked_engine','genefer_ntt_banked27_pair_row_engine')):
            for field in (1,2,3):
                with self.subTest(target=target,field=field),tempfile.TemporaryDirectory() as d:
                    a,b=Path(d)/'parent',Path(d)/'candidate'
                    old=prepare(a,parent,aw=16,field=field,processors=4)
                    new=prepare(b,target,aw=16,field=field,processors=4)
                    self.assertEqual(new['top'],newtop)
                    self.assertEqual(new['field_profile'],'experimental27')
                    self.assertEqual(new['montgomery_radix_bits'],32)
                    self.assertEqual(new['status'],'prepared_not_vendor_validated')
                    self.assertFalse(new['bitstream_generation'])
                    for key in ('field_parameters','address_width','clock_period_ns','compile_processors','allowed_stages'):
                        self.assertEqual(new[key],old[key])
                    self.assertEqual(set(new['source_sha256']),
                        (set(old['source_sha256'])-{oldtop+'.sv'})|{newtop+'.sv'})
                    for name,digest in new['source_sha256'].items():
                        self.assertEqual(digest,hashlib.sha256((root/'rtl/kernel'/name).read_bytes()).hexdigest())
                        if name!=newtop+'.sv':self.assertEqual(digest,old['source_sha256'][name])
                    def controls(path):
                        return [line for line in (path/'probe.qsf').read_text().splitlines()
                                if not line.startswith(('set_global_assignment -name TOP_LEVEL_ENTITY ',
                                                        'set_global_assignment -name SYSTEMVERILOG_FILE '))]
                    self.assertEqual(controls(a),controls(b))
                    for name in ('probe.sdc','probe.qpf','run.tcl'):
                        self.assertEqual((a/name).read_bytes(),(b/name).read_bytes())
                    self.assertNotIn(newtop,str(TARGETS['square_core27_stream_ntt64_carry16']))

    def test_checked_pair64_component_keeps_cached_interface_and_constraints(self):
        from reference.ntt27_pair_checked_regression import NAMES
        with tempfile.TemporaryDirectory() as d:
            for field in (1,2,3):
                a=Path(d)/f'baseline{field}';b=Path(d)/f'pair{field}'
                old=prepare(a,'ntt27_64',aw=16,field=field,processors=4)
                new=prepare(b,'ntt27_pair_checked64',aw=16,field=field,processors=4)
                self.assertEqual(new['top'],'genefer_ntt_banked27_pair_checked_engine')
                self.assertEqual(list(new['source_sha256']),NAMES)
                self.assertEqual(new['field_profile'],'experimental27')
                self.assertEqual(new['montgomery_radix_bits'],32)
                self.assertEqual(new['field_parameters'],old['field_parameters'])
                self.assertFalse(new['bitstream_generation'])
                def controls(path):
                    return [x for x in (path/'probe.qsf').read_text().splitlines()
                        if not x.startswith(('set_global_assignment -name TOP_LEVEL_ENTITY ',
                                             'set_global_assignment -name SYSTEMVERILOG_FILE '))]
                self.assertEqual(controls(a),controls(b))
                for name in ('probe.sdc','probe.qpf','run.tcl'):
                    self.assertEqual((a/name).read_bytes(),(b/name).read_bytes())

    def test_fixed_profile_rom_only_declares_real_field_parameters(self):
        with tempfile.TemporaryDirectory() as directory:
            for lanes in (16,64):
                for field,(p,q,g) in enumerate(FIELD_CONSTANTS_27,1):
                    path=Path(directory)/f'{lanes}-{field}'
                    m=prepare(path,f'root_profile27_{lanes}',aw=16,field=field,processors=4)
                    self.assertEqual(m['top'],'genefer_root_profile27_rom')
                    self.assertEqual(set(m['source_sha256']),{'genefer_root_profile27_rom.sv'})
                    self.assertEqual(m['field_parameters'],{'P':p,'GENERATOR':g})
                    self.assertEqual(m['field_profile'],'experimental27')
                    self.assertEqual(m['montgomery_radix_bits'],32)
                    qsf=(path/'probe.qsf').read_text()
                    self.assertIn(f'set_parameter -name LANES {lanes}',qsf)
                    self.assertNotIn('set_parameter -name Q ',qsf)
                    self.assertIn(f"set_parameter -name GENERATOR 32'd{g}",qsf)
                    self.assertFalse(m['bitstream_generation'])
                    self.assertIn('set_global_assignment -name VERILOG_CONSTANT_LOOP_LIMIT 10000\n',qsf)

    def test_profile_rom_loop_override_does_not_change_other_probes(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'plain'
            prepare(path,'square_core27_stream_ntt64_carry16',aw=16)
            self.assertNotIn('VERILOG_CONSTANT_LOOP_LIMIT',(path/'probe.qsf').read_text())

    def test_tiled_component_keeps_folded_controls_all_fields(self):
        # Logical replicas are a different RTL candidate, not a timing exception.
        with tempfile.TemporaryDirectory() as directory:
            for lanes in (16,64):
                for field in (1,2,3):
                    paths=[Path(directory)/f'{variant}-{lanes}-{field}'
                           for variant in ('folded','tiled')]
                    manifests=[prepare(path,f'ntt27_{variant}{lanes}',aw=16,
                                       field=field,period=10,processors=4)
                               for path,variant in zip(paths,('folded','tiled'))]
                    old,new=manifests
                    self.assertEqual(new['top'],'genefer_ntt_banked27_tiled_engine')
                    self.assertEqual(new['field_profile'],'experimental27')
                    self.assertEqual(new['montgomery_radix_bits'],32)
                    for key in ('field_parameters','address_width','clock_period_ns',
                                'compile_processors','allowed_stages','bitstream_generation'):
                        self.assertEqual(new[key],old[key])
                    self.assertEqual(set(new['source_sha256']),
                        (set(old['source_sha256'])-{'genefer_ntt_banked27_folded_engine.sv'}) |
                        {'genefer_ntt_banked27_tiled_engine.sv'})
                    for filename in set(old['source_sha256']) & set(new['source_sha256']):
                        self.assertEqual(old['source_sha256'][filename],new['source_sha256'][filename])
                    def controls(path):
                        return [line for line in (path/'probe.qsf').read_text().splitlines()
                                if not line.startswith(('set_global_assignment -name TOP_LEVEL_ENTITY ',
                                                        'set_global_assignment -name SYSTEMVERILOG_FILE '))]
                    self.assertEqual(controls(paths[0]),controls(paths[1]))
                    for filename in ('probe.sdc','probe.qpf','run.tcl'):
                        self.assertEqual((paths[0]/filename).read_bytes(),(paths[1]/filename).read_bytes())
                    self.assertEqual(TARGETS[f'ntt27_tiled{lanes}'][2],TARGETS[f'ntt27_folded{lanes}'][2])
                    self.assertNotIn('tiled',str(TARGETS['square_core27_stream_ntt64_carry16']))

    def test_folded_core_changes_only_routing_source_selection_and_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            for lanes in (16,64):
                old=prepare(Path(directory)/f"old{lanes}", f"square_core27_ntt{lanes}_carry16", aw=16)
                new=prepare(Path(directory)/f"new{lanes}", f"square_core27_folded_ntt{lanes}_carry16", aw=16)
                self.assertEqual(new['top'], 'genefer_square_core27_folded')
                self.assertEqual(new['arithmetic_profile'], 'atomic27_cached_folded_v1')
                for key in ('core_parameters','core_field_basis','core_montgomery_radix_bits',
                            'address_width','clock_period_ns','compile_processors'):
                    self.assertEqual(new[key],old[key])
                self.assertEqual(set(new['source_sha256']),
                    (set(old['source_sha256'])-{'genefer_ntt_banked27_host_engine.sv','genefer_square_core27.sv'}) |
                    {'genefer_ntt_banked27_folded_engine.sv','genefer_ntt_banked27_folded_host_engine.sv',
                     'genefer_square_core27_folded.sv'})
                self.assertIn('genefer_carry_prefix_vector_pipe_v2.sv',new['source_sha256'])
                self.assertNotIn('genefer_carry_prefix_stream_precision.sv',new['source_sha256'])

    def test_atomic27_stream_precision_is_explicit_separate_integration(self):
        with tempfile.TemporaryDirectory() as directory:
            for lanes in (16,64):
                path=Path(directory)/str(lanes)
                m=prepare(path, f"square_core27_stream_ntt{lanes}_carry16", aw=16, processors=4)
                self.assertEqual(m["top"], "genefer_square_core27_stream")
                self.assertEqual(m["arithmetic_profile"], "atomic27_stream_precision_v1")
                self.assertEqual(m["core_parameters"], {"NTT_LANES":lanes})
                self.assertEqual(m["core_montgomery_radix_bits"], 32)
                self.assertEqual(m["core_field_basis"], [
                    {"P":p,"Q":q,"GENERATOR":g,"R2":pow(2,64,p)} for p,q,g in FIELD_CONSTANTS_27])
                self.assertEqual(len(m["source_sha256"]), 14)
                for name in ("genefer_carry_prefix_stream_pipe.sv", "genefer_div_recip_precision.sv",
                             "genefer_carry_prefix_stream_precision.sv", "genefer_square_core27_stream.sv",
                             "genefer_crt3_27_pipe.sv", "genefer_ntt_banked27_host_engine.sv"):
                    self.assertIn(name,m["source_sha256"])
                for name in ("genefer_square_core27.sv", "genefer_crt3_27_pair_pipe.sv",
                             "genefer_ntt_banked27_prefetch_engine.sv"):
                    self.assertNotIn(name,m["source_sha256"])
                qsf=(path/"probe.qsf").read_text()
                self.assertEqual([line for line in qsf.splitlines() if line.startswith("set_parameter")],
                    ["set_parameter -name AW 16", f"set_parameter -name NTT_LANES {lanes}"])
                self.assertFalse(m["bitstream_generation"])

    def test_prefetch_probe_retains_generated_profile_and_matched_controls(self):
        with tempfile.TemporaryDirectory() as directory:
            for lanes in (16, 64):
                for field in (1, 2, 3):
                    paths = [Path(directory)/f"{variant}-{lanes}-{field}"
                             for variant in ("generated", "prefetch")]
                    manifests = [prepare(path, f"ntt27_{variant}{lanes}", aw=16,
                                         field=field, period=10, processors=4)
                                 for path, variant in zip(paths, ("generated", "prefetch"))]
                    self.assertEqual(manifests[1]["top"], "genefer_ntt_banked27_prefetch_engine")
                    self.assertEqual(manifests[1]["field_parameters"], manifests[0]["field_parameters"])
                    self.assertEqual(manifests[1]["field_profile"], "experimental27")
                    self.assertEqual(manifests[1]["montgomery_radix_bits"], 32)
                    self.assertEqual(set(manifests[1]["source_sha256"]),
                        (set(manifests[0]["source_sha256"]) - {"genefer_ntt_banked27_generated_engine.sv"}) |
                        {"genefer_ntt_banked27_prefetch_engine.sv"})
                    def controls(path):
                        return [line for line in (path/"probe.qsf").read_text().splitlines()
                                if not line.startswith(("set_global_assignment -name TOP_LEVEL_ENTITY ",
                                                        "set_global_assignment -name SYSTEMVERILOG_FILE "))]
                    self.assertEqual(controls(paths[0]), controls(paths[1]))
                    for name in ("probe.sdc", "run.tcl"):
                        self.assertEqual((paths[0]/name).read_bytes(), (paths[1]/name).read_bytes())

    def test_pair_crt_keeps_matched_controls_and_distinct_source_closure(self):
        with tempfile.TemporaryDirectory() as directory:
            projects = [Path(directory)/name for name in ("pair", "retimed")]
            manifests = [prepare(path, target, period=5, processors=4)
                         for path, target in zip(projects, ("crt27_pair", "crt27_retimed"))]
            self.assertEqual(manifests[0]["top"], "genefer_crt3_27_pair_pipe")
            self.assertEqual(set(manifests[0]["source_sha256"]), {
                "genefer_mod27_pair_pipe.sv", "genefer_crt3_27_pair_pipe.sv"})
            for manifest in manifests:
                self.assertEqual(manifest["compile_processors"], 4)
                self.assertFalse(manifest["bitstream_generation"])
            def controls(path):
                return [line for line in (path/"probe.qsf").read_text().splitlines()
                        if not line.startswith(("set_global_assignment -name TOP_LEVEL_ENTITY ",
                                                "set_global_assignment -name SYSTEMVERILOG_FILE "))]
            self.assertEqual(controls(projects[0]), controls(projects[1]))
            for name in ("probe.sdc", "probe.qpf", "run.tcl"):
                self.assertEqual((projects[0]/name).read_bytes(), (projects[1]/name).read_bytes())

    def test_folded_root_probe_keeps_basis_and_cached_api(self):
        with tempfile.TemporaryDirectory() as directory:
            for lanes in (16,64):
                path=Path(directory)/str(lanes)
                manifest=prepare(path,f"ntt27_folded{lanes}",aw=16,field=3)
                self.assertEqual(manifest["top"],"genefer_ntt_banked27_folded_engine")
                self.assertEqual(manifest["field_parameters"]["P"],FIELD_CONSTANTS_27[2][0])
                self.assertEqual(manifest["montgomery_radix_bits"],32)
                self.assertEqual(set(manifest["source_sha256"]),{
                    "genefer_sdp_ram32.sv", "genefer_montgomery_mul27_sparse_pipe.sv",
                    "genefer_ntt_banked27_engine.sv", "genefer_ntt_banked27_folded_engine.sv"})
                self.assertIn("-to {root_we}",(path/"probe.qsf").read_text())

    def test_retimed_crt_is_separate_from_frozen_crt(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest=prepare(Path(directory)/"crt27-retimed","crt27_retimed",period=5)
            self.assertEqual(manifest["top"],"genefer_crt3_27_retimed_pipe")
            self.assertEqual(set(manifest["source_sha256"]),{
                "genefer_mod64_pipe.sv","genefer_crt3_27_retimed_pipe.sv"})

    def test_divider_retime_has_distinct_top_and_frozen_scan_helper(self):
        with tempfile.TemporaryDirectory() as directory:
            for lanes in (4,16):
                path=Path(directory)/str(lanes)
                manifest=prepare(path,f"carry_stream_divpipe{lanes}",aw=16,period=5)
                self.assertEqual(manifest["top"],"genefer_carry_prefix_stream_divpipe")
                self.assertEqual(set(manifest["source_sha256"]),{"genefer_sp_ram.sv",
                    "genefer_div_recip_narrow_pipe.sv","genefer_carry_prefix_stream_pipe.sv",
                    "genefer_carry_prefix_stream_divpipe.sv"})
                self.assertIn("-to {stream_ready}",(path/"probe.qsf").read_text())
                self.assertIn(f"set_parameter -name LANES {lanes}",(path/"probe.qsf").read_text())

    def test_atomic27_core_exposes_only_real_parameters_and_whole_basis(self):
        with tempfile.TemporaryDirectory() as directory:
            for lanes in (16,64):
                path=Path(directory)/str(lanes)
                manifest=prepare(path,f"square_core27_ntt{lanes}_carry16",aw=16)
                self.assertEqual(manifest["top"],"genefer_square_core27")
                self.assertEqual(manifest["address_width"],16)
                self.assertEqual(manifest["arithmetic_profile"],"atomic27_cached_v1")
                self.assertEqual(manifest["core_montgomery_radix_bits"],32)
                self.assertEqual(manifest["core_parameters"],{"NTT_LANES":lanes})
                self.assertEqual(manifest["core_field_basis"],[
                    {"P":p,"Q":q,"GENERATOR":g,"R2":pow(2,64,p)} for p,q,g in FIELD_CONSTANTS_27])
                sources=manifest["source_sha256"]
                self.assertEqual(len(sources),13)
                for name in ("genefer_digit_reduce27_pipe.sv","genefer_crt3_27_pipe.sv",
                             "genefer_ntt_banked27_host_engine.sv","genefer_square_core27.sv"):
                    self.assertIn(name,sources)
                for name in ("genefer_square_core.sv","genefer_crt3_pipe.sv",
                             "genefer_root_stream32.sv"):
                    self.assertNotIn(name,sources)
                parameters=[line for line in (path/"probe.qsf").read_text().splitlines()
                            if line.startswith("set_parameter")]
                self.assertEqual(parameters,["set_parameter -name AW 16",f"set_parameter -name NTT_LANES {lanes}"])

    def test_routepipe_probe_preserves_cached_interface_and_frozen_butterfly(self):
        with tempfile.TemporaryDirectory() as directory:
            for lanes in (16,64):
                path=Path(directory)/str(lanes)
                manifest=prepare(path,f"ntt27_routepipe{lanes}",aw=16,field=2)
                self.assertEqual(manifest["top"],"genefer_ntt_banked27_routepipe_engine")
                self.assertEqual(manifest["field_parameters"]["P"],FIELD_CONSTANTS_27[1][0])
                self.assertEqual(manifest["montgomery_radix_bits"],32)
                self.assertEqual(set(manifest["source_sha256"]),{
                    "genefer_sdp_ram32.sv", "genefer_montgomery_mul27_sparse_pipe.sv",
                    "genefer_ntt_banked27_engine.sv", "genefer_ntt_banked27_routepipe_engine.sv"})
                self.assertIn("-to {root_we}",(path/"probe.qsf").read_text())

    def test_generated_roots_probe_has_explicit_profile_not_root_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            for lanes in (16,64):
                for field in (1,2,3):
                    path=Path(directory)/f"{lanes}-{field}"
                    manifest=prepare(path,f"ntt27_generated{lanes}",aw=16,field=field)
                    self.assertEqual(manifest["top"],"genefer_ntt_banked27_generated_engine")
                    self.assertEqual(manifest["field_profile"],"experimental27")
                    self.assertEqual(manifest["montgomery_radix_bits"],32)
                    self.assertEqual(manifest["field_parameters"],dict(zip(("P","Q"),FIELD_CONSTANTS_27[field-1][:2])))
                    self.assertEqual(set(manifest["source_sha256"]),{
                        "genefer_sdp_ram32.sv", "genefer_sp_ram.sv",
                        "genefer_montgomery_mul27_sparse_pipe.sv", "genefer_ntt_banked27_engine.sv",
                        "genefer_root_recurrence27.sv", "genefer_ntt_banked27_generated_engine.sv"})
                    qsf=(path/"probe.qsf").read_text()
                    self.assertNotIn("-to {root_we}",qsf)
                    self.assertIn("-to {profile_commit}",qsf)
                    self.assertIn("-to {seed_setup_cycles[*]}",qsf)
                    self.assertIn(f"set_parameter -name LANES {lanes}",qsf)

    def test_pipelined_stream_has_frozen_separate_dependency_closure(self):
        with tempfile.TemporaryDirectory() as directory:
            for lanes in (4,16):
                path=Path(directory)/str(lanes)
                manifest=prepare(path,f"carry_stream_pipe{lanes}",aw=16,period=5)
                self.assertEqual(manifest["top"],"genefer_carry_prefix_stream_pipe")
                self.assertEqual(set(manifest["source_sha256"]),{"genefer_sp_ram.sv",
                    "genefer_div_recip_narrow.sv","genefer_carry_prefix_stream_pipe.sv"})
                self.assertIn("-to {stream_ready}",(path/"probe.qsf").read_text())
                self.assertIn(f"set_parameter -name LANES {lanes}",(path/"probe.qsf").read_text())

    def test_64_ntt_with_16_io_uses_explicit_verified_adapter_dependencies(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"core64"
            manifest=prepare(path,"square_core_fast64_carry16",aw=16)
            self.assertEqual(manifest["core_parameters"]["NTT_LANES"],64)
            self.assertEqual(manifest["core_parameters"]["CARRY_LANES"],16)
            self.assertEqual(manifest["core_parameters"]["FAST_ARITH"],1)
            self.assertEqual(manifest["core_parameters"]["VECTOR_IO"],1)
            self.assertEqual(len(manifest["source_sha256"]),27)
            for name in ("genefer_ntt_banked_wide_engine.sv","genefer_ntt_banked_host_engine.sv"):
                self.assertIn(name,manifest["source_sha256"])

    def test_36bit_modular_constants_are_sized_not_truncated(self):
        from reference.ntt36_experiment import select_basis
        self.assertEqual(FIELD_CONSTANTS_36,[(f["p"],f["q"]) for f in select_basis()])
        with tempfile.TemporaryDirectory() as directory:
            for field,(p,q) in enumerate(FIELD_CONSTANTS_36,1):
                path=Path(directory)/str(field)
                manifest=prepare(path,"multiplier36_sparse",field=field)
                self.assertEqual(manifest["montgomery_radix_bits"],36)
                self.assertEqual(manifest["field_profile"],"experimental36")
                self.assertEqual(manifest["field_parameters"],{"P":p,"Q":q})
                text=(path/"probe.qsf").read_text()
                self.assertIn(f"set_parameter -name P 36'd{p}",text)
                self.assertIn(f"set_parameter -name Q 36'd{q}",text)

    def test_ntt27_probe_selects_matching_basis_and_radix(self):
        with tempfile.TemporaryDirectory() as directory:
            for lanes in (16,64):
                for field in (1,2,3):
                    path=Path(directory)/f"{lanes}-{field}"
                    manifest=prepare(path,f"ntt27_{lanes}",aw=16,field=field)
                    self.assertEqual(manifest["field_profile"],"experimental27")
                    self.assertEqual(manifest["montgomery_radix_bits"],32)
                    self.assertEqual(manifest["field_parameters"]["P"],FIELD_CONSTANTS_27[field-1][0])
                    self.assertEqual(set(manifest["source_sha256"]),{"genefer_sdp_ram32.sv",
                        "genefer_montgomery_mul27_sparse_pipe.sv","genefer_ntt_banked27_engine.sv"})
                    self.assertIn(f"set_parameter -name LANES {lanes}",(path/"probe.qsf").read_text())

    def test_raw_multiply_is_not_a_modular_field_probe(self):
        with tempfile.TemporaryDirectory() as directory:
            for name,width,split in (("raw_mul27",27,0),("raw_mul36",36,0),("raw_mul36_split",36,1)):
                path=Path(directory)/name
                manifest=prepare(path,name,period=5)
                self.assertIsNone(manifest["field_parameters"])
                self.assertIsNone(manifest["montgomery_radix_bits"])
                self.assertEqual(manifest["raw_multiplier_parameters"],{"WIDTH":width,"SPLIT18":split})
                self.assertIn(f"set_parameter -name WIDTH {width}",(path/"probe.qsf").read_text())
                self.assertIn(f"set_parameter -name SPLIT18 {split}",(path/"probe.qsf").read_text())

    def test_eight_processors_default_and_bounded_override(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"default"
            manifest=prepare(path,"multiplier")
            self.assertEqual(manifest["compile_processors"],8)
            self.assertIn("NUM_PARALLEL_PROCESSORS 8",(path/"probe.qsf").read_text())
            for count in (1,2,4,16):
                path=Path(directory)/str(count)
                manifest=prepare(path,"multiplier",processors=count)
                self.assertEqual(manifest["compile_processors"],count)
            for count in (0,17,True,2.5):
                with self.assertRaises(ValueError):prepare(Path(directory)/"bad","multiplier",processors=count)

    def test_edition_selects_correct_synthesis_executable(self):
        with tempfile.TemporaryDirectory() as directory:
            for edition,tool in [("pro","syn"),("standard","map")]:
                path=Path(directory)/edition
                manifest=prepare(path,"multiplier",edition=edition)
                self.assertEqual(manifest["allowed_stages"],[tool,"fit","sta"])
                self.assertIn(f"execute_module -tool {tool}",(path/"run.tcl").read_text())
                self.assertNotIn("@SYNTH_TOOL@",(path/"run.tcl").read_text())

    def test_all_probes_are_snapshotted_compute_only(self):
        with tempfile.TemporaryDirectory() as directory:
            for target in TARGETS:
                path=Path(directory)/target
                manifest=prepare(path,target)
                qsf=(path/"probe.qsf").read_text()
                script=(path/"run.tcl").read_text()
                self.assertNotIn("set_location_assignment",qsf)
                self.assertNotIn("-to {clk}",qsf)
                self.assertNotIn("-tool asm",script)
                self.assertNotIn("quartus_pgm",script)
                self.assertFalse(manifest["bitstream_generation"])
                self.assertTrue(manifest["source_sha256"])
                with self.assertRaises(FileExistsError): prepare(path,target)

    def test_rejects_unbounded_parameters(self):
        with tempfile.TemporaryDirectory() as directory:
            for target,aw,period in [("unknown",8,10),("ntt",17,10),("carry",8,0),("ntt",8,float("nan"))]:
                with self.assertRaises(ValueError): prepare(Path(directory)/"probe",target,aw,period)

    def test_streaming_fields_and_address_width(self):
        with tempfile.TemporaryDirectory() as directory:
            for field in (1,2,3):
                path=Path(directory)/str(field)
                manifest=prepare(path,"root_stream",aw=16,field=field)
                self.assertEqual(manifest["field"],field)
                self.assertIn("set_parameter -name AW 16",(path/"probe.qsf").read_text())
                self.assertIn("set_parameter -name GENERATOR",(path/"probe.qsf").read_text())

    def test_opt_in_integrated_difdit(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"core"
            manifest=prepare(path,"square_core_difdit",aw=16)
            self.assertEqual(manifest["top"],"genefer_square_core")
            self.assertIn("genefer_ntt_difdit_engine.sv",manifest["source_sha256"])
            self.assertIn("set_parameter -name DIFDIT 1",(path/"probe.qsf").read_text())
            path4=Path(directory)/"core4"
            prepare(path4,"square_core_parallel4",aw=16)
            self.assertIn("set_parameter -name NTT_LANES 4",(path4/"probe.qsf").read_text())

    def test_module_memory_lane_counts_and_dependencies(self):
        with tempfile.TemporaryDirectory() as directory:
            for memory in ("modulemem", "packed"):
                for lanes in (4, 16):
                    path = Path(directory)/f"{memory}{lanes}"
                    manifest = prepare(path, f"ntt_{memory}{lanes}", aw=16, field=3)
                    qsf = (path/"probe.qsf").read_text()
                    self.assertIn(f"set_parameter -name LANES {lanes}", qsf)
                    self.assertIn("set_parameter -name AW 16", qsf)
                    self.assertEqual(manifest["field"], 3)
                    self.assertIn("genefer_sdp_ram32.sv", manifest["source_sha256"])
                    self.assertIn(f"genefer_ntt_banked_{memory}_engine.sv", manifest["source_sha256"])

    def test_integrated_banked_lane_parameters(self):
        with tempfile.TemporaryDirectory() as directory:
            for lanes in (4, 16):
                path = Path(directory)/str(lanes)
                manifest = prepare(path, f"square_core_banked{lanes}_carry{lanes}", aw=16)
                qsf = (path/"probe.qsf").read_text()
                for name in ("genefer_sdp_ram32.sv", "genefer_ntt_banked_modulemem_engine.sv",
                             "genefer_sp_ram.sv", "genefer_carry_prefix_wide_ram.sv"):
                    self.assertIn(name, manifest["source_sha256"])
                for key, value in {"DIFDIT": 1, "NTT_LANES": lanes, "PREFIX_CARRY": 1,
                                   "ROOT_CACHE": 1, "BANKED_NTT": 1, "CARRY_LANES": lanes}.items():
                    self.assertEqual(manifest["core_parameters"][key], value)
                    self.assertIn(f"set_parameter -name {key} {value}", qsf)

    def test_vector_probe_ports_are_virtual(self):
        with tempfile.TemporaryDirectory() as directory:
            for variant in ("vector", "predecode"):
                path = Path(directory)/variant
                manifest = prepare(path, f"ntt_{variant}16", aw=16)
                qsf = (path/"probe.qsf").read_text()
                self.assertIn(f"genefer_ntt_banked_{variant}_engine.sv", manifest["source_sha256"])
                for port in ("vector_load_we", "vector_read_en", "vector_addr[*]", "vector_lane_mask[*]",
                             "vector_write_data[*]", "vector_read_valid", "host_error", "vector_read_mask[*]", "vector_read_data[*]"):
                    self.assertIn(f"set_instance_assignment -name VIRTUAL_PIN ON -to {{{port}}}", qsf)

    def test_vector_core_selects_explicit_internal_width_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            for lanes in (4,16):
                path=Path(directory)/str(lanes)
                manifest=prepare(path,f"square_core_vector{lanes}",aw=16)
                self.assertEqual(manifest["core_parameters"]["VECTOR_IO"],1)
                self.assertEqual(manifest["core_parameters"]["NTT_LANES"],lanes)
                self.assertEqual(manifest["core_parameters"]["CARRY_LANES"],lanes)
                self.assertIn("genefer_carry_prefix_vector_ram.sv",manifest["source_sha256"])
                self.assertIn("genefer_ntt_banked_vector_engine.sv",manifest["source_sha256"])

    def test_narrow_multiplier_comparison_uses_identical_proven_fields(self):
        from reference.ntt27_experiment import select_basis
        self.assertEqual(FIELD_CONSTANTS_27, [(p.p,p.q,p.generator) for p in select_basis()])
        with tempfile.TemporaryDirectory() as directory:
            for field in (1,2,3):
                left=prepare(Path(directory)/f"narrow{field}","multiplier27",field=field)
                right=prepare(Path(directory)/f"wide{field}","multiplier27_reference32",field=field)
                self.assertEqual(left["field_parameters"],right["field_parameters"])
                self.assertEqual(left["field_profile"],"experimental27")
                self.assertEqual(left["top"],"genefer_montgomery_mul27_pipe")
                self.assertEqual(right["top"],"genefer_montgomery_mul32_pipe")
                sparse=prepare(Path(directory)/f"sparse{field}","multiplier27_sparse",field=field)
                self.assertEqual(sparse["field_parameters"],left["field_parameters"])
                self.assertEqual(sparse["field_profile"],"experimental27")
                self.assertEqual(left["montgomery_radix_bits"],32)
                self.assertEqual(right["montgomery_radix_bits"],32)
                self.assertEqual(sparse["montgomery_radix_bits"],32)
                self.assertEqual(sparse["top"],"genefer_montgomery_mul27_sparse_pipe")
                self.assertEqual(set(sparse["source_sha256"]),{"genefer_montgomery_mul27_sparse_pipe.sv"})

    def test_fast_core_is_explicit_not_implicit_upgrade(self):
        with tempfile.TemporaryDirectory() as directory:
            for lanes in (4,16):
                fast=prepare(Path(directory)/f"fast{lanes}",f"square_core_fast{lanes}",aw=16)
                baseline=prepare(Path(directory)/f"base{lanes}",f"square_core_vector{lanes}",aw=16)
                self.assertEqual(fast["core_parameters"]["FAST_ARITH"],1)
                self.assertEqual(baseline["core_parameters"]["FAST_ARITH"],0)
                self.assertEqual(fast["core_parameters"]["VECTOR_IO"],1)
                self.assertEqual(fast["core_parameters"]["NTT_LANES"],lanes)
                for name in ("genefer_ntt_banked_shared_engine.sv","genefer_div_recip_narrow.sv",
                             "genefer_carry_prefix_vector_pipe_v2.sv"):
                    self.assertIn(name,fast["source_sha256"])

    def test_wide_and_retimed_probes_remain_separate(self):
        with tempfile.TemporaryDirectory() as directory:
            for lanes in (32,64):
                path=Path(directory)/f"ntt{lanes}"
                manifest=prepare(path,f"ntt_wide{lanes}",aw=16)
                self.assertIn(f"set_parameter -name LANES {lanes}",(path/"probe.qsf").read_text())
                self.assertEqual(manifest["top"],"genefer_ntt_banked_wide_engine")
            carry=prepare(Path(directory)/"carry","carry_pipe2_16",aw=16)
            self.assertIn("genefer_carry_prefix_wide_pipe_v2.sv",carry["source_sha256"])
            self.assertNotIn("genefer_carry_prefix_wide_pipe.sv",carry["source_sha256"])
            crt=prepare(Path(directory)/"crt","crt27_pipe")
            self.assertIn("genefer_crt3_27_pipe.sv",crt["source_sha256"])
            self.assertNotIn("genefer_crt3_pipe.sv",crt["source_sha256"])

    def test_streaming_carry_has_explicit_input_and_host_ports(self):
        with tempfile.TemporaryDirectory() as directory:
            for lanes in (4,16):
                path=Path(directory)/str(lanes)
                manifest=prepare(path,f"carry_stream{lanes}",aw=16)
                self.assertEqual(manifest["top"],"genefer_carry_prefix_stream")
                qsf=(path/"probe.qsf").read_text()
                self.assertIn(f"set_parameter -name LANES {lanes}",qsf)
                for port in ("stream_valid","stream_ready","stream_data[*]","vector_read_data[*]"):
                    self.assertIn("-to {"+port+"}",qsf)
