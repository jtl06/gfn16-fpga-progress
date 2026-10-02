import copy
from pathlib import Path
import unittest
from fpga.reference import verify_ntt27_prefetch_full_replay as check


def fixture():
    root=Path("/fresh/output");cases=[];steps=[];models=[];hashes={}
    for field in (1,2,3):
        for kind in ("baseline","candidate"):
            models.append({"field":field,"kind":kind,"path":f"/model/{field}/{kind}"})
        for name in check.gate.base.expected_cases(field):
            vector=str(check.gate.base.OLD_GATE/(name+".txt"));hashes[vector]="digest"
            fuzz=name==f"transform-p{field}-aw16-n65536"
            cases.append({"name":name,"field":field,"vector":vector,"host_fuzz":fuzz,"sha256":"digest"})
            for kind in ("baseline","candidate"):
                argv=[] if fuzz else ["env","NTT_SKIP_HOST_FUZZ=1"]
                argv += [f"/model/{field}/{kind}",vector,str(root/f"{name}-{kind}-dump.txt")]
                steps.append({"name":name+"-"+kind,"command":argv})
        for kind in ("baseline","candidate"):
            for mode in ("scalar","vector","scalar-high","vector-high"):
                name=f"fault-p{field}-{kind}-{mode}"
                steps.append({"name":name,"command":["env","NTT_NONCANON="+mode,
                    f"/model/{field}/{kind}",str(check.gate.base.OLD_GATE/f"transform-p{field}-aw16-n2.txt"),str(root/(name+"-dump.txt"))]})
    return {"executables":models,"actual_build_profiles":[{"field":f} for f in (1,2,3)],
        "source_archive":{"path":str(root/"source-closure.tar.gz")},"steps":steps}, {"cases":cases,"input_sha256":hashes}


class OfflineFullReceiptTests(unittest.TestCase):
    def test_complete_structure(self):
        report,manifest=fixture();self.assertEqual(len(check.structure(report,manifest)),6)

    def test_duplicate_model_and_profile_fields(self):
        report,manifest=fixture();report["executables"][-1]=copy.deepcopy(report["executables"][1])
        with self.assertRaisesRegex(AssertionError,"executable fields"):check.structure(report,manifest)
        report,manifest=fixture();report["actual_build_profiles"][-1]={"field":1}
        with self.assertRaisesRegex(AssertionError,"profiles"):check.structure(report,manifest)

    def test_duplicate_vector_case(self):
        report,manifest=fixture();manifest["cases"][-1]=copy.deepcopy(manifest["cases"][0])
        with self.assertRaisesRegex(AssertionError,"vector cases"):check.structure(report,manifest)

    def test_wrong_model_argv(self):
        report,manifest=fixture();report["steps"][0]["command"][2]="/wrong/executable"
        with self.assertRaisesRegex(AssertionError,"argv"):check.structure(report,manifest)

    def test_missing_and_incorrect_fuzz_settings(self):
        report,manifest=fixture();report["steps"][0]["command"]=report["steps"][0]["command"][2:]
        with self.assertRaisesRegex(AssertionError,"argv"):check.structure(report,manifest)
        report,manifest=fixture()
        step=next(s for s in report["steps"] if s["name"]=="transform-p1-aw16-n65536-candidate")
        step["command"]=["env","NTT_SKIP_HOST_FUZZ=1",*step["command"]]
        with self.assertRaisesRegex(AssertionError,"argv"):check.structure(report,manifest)

    def test_high_bit_mode_cannot_be_relabelled_scalar(self):
        report,manifest=fixture()
        step=next(s for s in report["steps"] if s["name"]=="fault-p2-candidate-vector-high")
        step["command"][1]="NTT_NONCANON=vector"
        with self.assertRaisesRegex(AssertionError,"fault mode"):check.structure(report,manifest)


if __name__=="__main__":unittest.main()
