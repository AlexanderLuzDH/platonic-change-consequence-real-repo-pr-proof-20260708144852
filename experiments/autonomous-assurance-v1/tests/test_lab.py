from __future__ import annotations
import importlib.util, sys, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def load(name,file):
    spec=importlib.util.spec_from_file_location(name,ROOT/file); mod=importlib.util.module_from_spec(spec); sys.modules[name]=mod; spec.loader.exec_module(mod); return mod
analyze=load('analyze_bugsinpy','analyze_bugsinpy.py')
cases=load('run_pysnooper_cases','run_pysnooper_cases.py')
class LabTests(unittest.TestCase):
    def test_metadata_and_upstream_commit_classification(self):
        with tempfile.TemporaryDirectory() as d:
            project=Path(d)/'projects/demo'; bug=project/'bugs/1'; bug.mkdir(parents=True)
            (project/'project.info').write_text('github_url="https://github.com/example/demo"\n')
            (bug/'bug.info').write_text('python_version="3.8"\nbuggy_commit_id="'+'a'*40+'"\nfixed_commit_id="'+'b'*40+'"\ntest_file="tests/test_parser.py"\n')
            (bug/'run_test.sh').write_text('pytest tests/test_parser.py::test_unicode_parser\n')
            (bug/'bug_patch.txt').write_text('diff --git a/src/parser.py b/src/parser.py\n--- a/src/parser.py\n+++ b/src/parser.py\n@@ -1 +1 @@\n-decode("ascii")\n+decode("utf-8")\n')
            metas=analyze.load_meta(Path(d)); self.assertEqual(len(metas),1)
            r=analyze.build(metas[0],{'status':'ok','url':'https://example','files':[{'path':'src/parser.py','status':'modified','previous':None},{'path':'tests/test_parser.py','status':'added','previous':None}]})
            self.assertTrue(r.relevant_test_added); self.assertTrue(r.relevant_test_changed); self.assertTrue(r.candidate_path_discoverable)
            self.assertEqual(analyze.summarize([r])['dataset']['api_success'],1)
    def test_path_and_repo_normalization(self):
        self.assertEqual(analyze.github_repo('https://github.com/org/repo.git'),'org/repo')
        self.assertTrue(analyze.is_test('tests/test_api.py')); self.assertFalse(analyze.is_test('src/contest.py')); self.assertIn('tests/test_tracer.py',analyze.candidates('src/tracer.py'))
    def test_case_mutation(self):
        self.assertEqual(len({c.case_id for c in cases.CASES}),3); c=cases.CASES[2]
        with tempfile.TemporaryDirectory() as d:
            repo=Path(d); p=repo/c.source_path; p.parent.mkdir(parents=True); p.write_text(c.old_fragment+'\n')
            result=cases.apply_mutation(repo,c); self.assertTrue(result['applied']); self.assertIn(c.mutant_fragment,p.read_text())
if __name__=='__main__': unittest.main()
