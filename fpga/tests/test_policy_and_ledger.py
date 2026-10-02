from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from autolab.ledger import Ledger
from autolab.policy import PolicyError, load_candidate


class PolicyAndLedgerTests(unittest.TestCase):
    def make_workspace(self, source: str, *, clock: str = "simulation") -> tuple[Path, tempfile.TemporaryDirectory[str]]:
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        (root / "rtl" / "kernel").mkdir(parents=True)
        (root / "candidates").mkdir()
        (root / "rtl" / "kernel" / "candidate.sv").write_text(source, encoding="utf-8")
        manifest = {
            "id": "candidate-1",
            "sources": ["rtl/kernel/candidate.sv"],
            "parameters": {"clock_profile": clock, "lanes": 1, "pipeline_stages": 1},
        }
        (root / "candidates" / "candidate.json").write_text(json.dumps(manifest), encoding="utf-8")
        return root, temporary

    def test_accepts_bounded_compute_rtl(self) -> None:
        root, temporary = self.make_workspace("module candidate(input logic clk); endmodule\n")
        self.addCleanup(temporary.cleanup)
        candidate = load_candidate(root, Path("candidates/candidate.json"))
        self.assertEqual(candidate.candidate_id, "candidate-1")
        self.assertEqual(len(candidate.digest), 64)

    def test_rejects_external_interface(self) -> None:
        root, temporary = self.make_workspace("module candidate; pcie_endpoint dangerous(); endmodule\n")
        self.addCleanup(temporary.cleanup)
        with self.assertRaisesRegex(PolicyError, "external high-speed I/O"):
            load_candidate(root, Path("candidates/candidate.json"))

    def test_rejects_preprocessor_and_simulator_escape(self) -> None:
        for source in (
            "`define HIDDEN pcie_endpoint\nmodule candidate; endmodule\n",
            'module candidate; import "DPI-C" function void escape(); endmodule\n',
            'module candidate; initial $fopen("/etc/passwd", "r"); endmodule\n',
            "module candidate; altpll clock_primitive(); endmodule\n",
        ):
            with self.subTest(source=source):
                root, temporary = self.make_workspace(source)
                try:
                    with self.assertRaises(PolicyError):
                        load_candidate(root, Path("candidates/candidate.json"))
                finally:
                    temporary.cleanup()

    def test_rejects_hardware_clock_profile(self) -> None:
        root, temporary = self.make_workspace("module candidate; endmodule\n", clock="safe_200mhz")
        self.addCleanup(temporary.cleanup)
        with self.assertRaisesRegex(PolicyError, "simulation clock"):
            load_candidate(root, Path("candidates/candidate.json"))

    def test_ledger_is_deduplicated(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            ledger = Ledger(Path(temporary) / "results.sqlite3")
            try:
                first = ledger.record("a", "digest", "mock", "pass", {"score": 1})
                self.assertEqual(first["metrics"]["score"], 1)
                self.assertIsNotNone(ledger.get("digest", "mock"))
                with self.assertRaises(Exception):
                    ledger.record("b", "digest", "mock", "pass", {"score": 2})
            finally:
                ledger.close()


if __name__ == "__main__":
    unittest.main()
