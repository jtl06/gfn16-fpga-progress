import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

FPGA = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('sta_outputs', FPGA/'tools/quartus_sta_output_guard_v1.py')
guard = importlib.util.module_from_spec(spec); spec.loader.exec_module(guard)
OBSERVATION = FPGA/'results/throughput-20260929/quartus-prefit-azure-diag-stage-v9/observed-sta-output-metadata-v1.json'


class OutputClassificationTests(unittest.TestCase):
    def test_actual_native_metadata_schema_and_exact_paths_only(self):
        self.assertEqual(hashlib.sha256(OBSERVATION.read_bytes()).hexdigest(), guard.OBSERVATION_SHA256)
        capture = json.loads(OBSERVATION.read_text())
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); inventory = {'qdb/compiled.cdb': 'a'*64, 'qdb/other.cache': 'b'*64}
            for model, (payload, _, _) in guard.PAIRS.items():
                for name in (model, payload):
                    path = root/name; path.parent.mkdir(parents=True, exist_ok=True)
                    raw = (json.dumps(capture['roots']['private_failed_v9'][name]['model']).encode() if name == model
                           else bytes.fromhex(guard.PAYLOAD_HEADER_HEX)+b'synthetic payload; actual captured native metadata only')
                    path.write_bytes(raw); inventory[name] = hashlib.sha256(raw).hexdigest()
            immutable, derived = guard.classify(root, inventory)
            self.assertEqual(immutable, {'qdb/compiled.cdb': 'a'*64, 'qdb/other.cache': 'b'*64})
            self.assertEqual(len(derived), 6)
            model = next(iter(guard.PAIRS)); path = root/model
            metadata = json.loads(path.read_text()); metadata['trait'] = 'COMPILED_INPUT'; path.write_text(json.dumps(metadata))
            inventory[model] = hashlib.sha256(path.read_bytes()).hexdigest()
            with self.assertRaises(ValueError):
                guard.classify(root, inventory)

    def test_missing_pair_and_wrong_native_header_fail_closed(self):
        model, (payload, _, _) = next(iter(guard.PAIRS.items()))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(ValueError):
                guard.classify(root, {model: 'a'*64, 'qdb/compiled.cdb': 'b'*64})
            metadata = json.loads(OBSERVATION.read_text())['roots']['private_failed_v9'][model]['model']
            for name, raw in ((model, json.dumps(metadata).encode()), (payload, b'not native')):
                path = root/name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(raw)
            inventory = {name: hashlib.sha256((root/name).read_bytes()).hexdigest() for name in (model, payload)}
            inventory['qdb/compiled.cdb'] = 'b'*64
            with self.assertRaises(ValueError):
                guard.classify(root, inventory)


if __name__ == '__main__':
    unittest.main()
