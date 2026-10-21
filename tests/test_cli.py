from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

ROOT=Path(__file__).resolve().parents[1]


class CLITests(unittest.TestCase):
    def test_scripts_export_sample_and_fail_unsuccessfully(self):
        commands=[('storm_tracker.py',['Moderate','TEST']),
                  ('storm_prognostic.py',[]),('storm_RI_plot.py',[])]
        with TemporaryDirectory() as directory:
            for script,prefix in commands:
                output=Path(directory)/(script+'.png')
                common=[sys.executable,str(ROOT/script),*prefix]
                result=subprocess.run([*common,str(ROOT/'forecast.csv'),'--degraded','--output',str(output)],
                                      cwd=directory,capture_output=True,text=True)
                self.assertEqual(result.returncode,0,result.stderr)
                self.assertTrue(output.read_bytes().startswith(b'\x89PNG'))
                bad=subprocess.run([*common,str(Path(directory)/'missing.csv'),'--degraded'],
                                   cwd=directory,capture_output=True,text=True)
                self.assertNotEqual(bad.returncode,0)
                self.assertIn('Error:',bad.stderr)
