import contextlib
import io
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from cycloneaid import launcher


class LauncherTests(unittest.TestCase):
    def test_project_interpreter_selection_and_active_environment(self):
        with TemporaryDirectory() as directory:
            root=Path(directory)
            self.assertIsNone(launcher.project_python(root))
            (root/'pyproject.toml').touch()
            candidate=root/'.venv'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
            candidate.parent.mkdir(parents=True)
            candidate.touch()
            self.assertEqual(launcher.project_python(root),candidate)
            with patch.object(sys,'prefix',str(root/'.venv')):
                self.assertIsNone(launcher.project_python(root))

    def test_local_caches_preserve_explicit_configuration(self):
        with TemporaryDirectory() as directory, patch.dict(os.environ,{},clear=True):
            root=Path(directory)
            (root/'pyproject.toml').touch()
            (root/'.cache/cartopy').mkdir(parents=True)
            launcher.configure_runtime(root)
            self.assertEqual(os.environ['MPLCONFIGDIR'],str(root/'.cache/matplotlib'))
            self.assertEqual(os.environ['CARTOPY_DATA_DIR'],str(root/'.cache/cartopy'))
            os.environ['MPLCONFIGDIR']='custom-matplotlib'
            os.environ['CARTOPY_DATA_DIR']='custom-cartopy'
            launcher.configure_runtime(root)
            self.assertEqual(os.environ['MPLCONFIGDIR'],'custom-matplotlib')
            self.assertEqual(os.environ['CARTOPY_DATA_DIR'],'custom-cartopy')

    def test_missing_dependencies_give_setup_instructions(self):
        errors=io.StringIO()
        with patch.object(launcher,'project_python',return_value=None), \
             patch.object(launcher,'configure_runtime'), \
             patch.object(launcher,'check_environment',return_value=['pandas: not installed']), \
             contextlib.redirect_stderr(errors):
            self.assertEqual(launcher.main(['--check']),1)
        self.assertIn('pandas',errors.getvalue())
        self.assertIn('setup.',errors.getvalue())

    def test_missing_display_gives_an_actionable_error(self):
        import tkinter as tk
        with patch.object(launcher,'project_python',return_value=None), \
             patch.object(launcher,'configure_runtime'), \
             patch.object(launcher,'check_environment',return_value=[]), \
             patch('storm_tracker_gui.StormTrackerApp',side_effect=tk.TclError('cannot open display')), \
             contextlib.redirect_stderr(io.StringIO()) as errors:
            self.assertEqual(launcher.main([]),1)
        self.assertIn('graphical desktop session',errors.getvalue())

    def test_base_python_bootstraps_the_project_environment(self):
        root=Path(__file__).resolve().parents[1]
        candidate=root/'.venv'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
        if not candidate.exists():
            self.skipTest('No checkout-local .venv; use setup or uv sync to exercise bootstrap')
        result=subprocess.run([sys._base_executable,str(root/'storm_tracker_gui.py'),'--check'],
                              cwd=root.parent,capture_output=True,text=True,timeout=45)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn(str(candidate),result.stdout)
        self.assertIn('Required dependencies and Tk: OK',result.stdout)

    def test_sample_project_is_valid_and_ready_without_downloads(self):
        import pandas as pd
        from cycloneaid.imports import read_forecast
        from cycloneaid.session import load_project,validate_session
        from storm_RI_plot import compute_dv_dt
        root=Path(__file__).resolve().parents[1]
        sample=load_project(root/'examples/sample.cycloneaid.json')
        points,result=validate_session(sample,regional=True)
        self.assertFalse(result.has_errors(),result.hard_errors)
        csv_points,notes=read_forecast(root/'forecast.csv')
        self.assertEqual(tuple(csv_points),points)
        self.assertFalse(notes)
        self.assertFalse(result.soft_warnings)
        self.assertEqual(sample.settings.geography_mode,'degraded')
        self.assertIn('TEST',sample.settings.storm_name)
        self.assertIn('Synthetic',sample.settings.source)
        self.assertIn('1-minute',sample.settings.wind_averaging_period)
        self.assertEqual(points[-1].time-points[0].time,pd.Timedelta(hours=120))
        values=compute_dv_dt(pd.DataFrame([{'time':p.time,'wind_kt':p.wind_kt} for p in points]))
        exact=values.loc[values.time==points[0].time+pd.Timedelta(hours=24)].iloc[0]
        self.assertAlmostEqual(exact.dv_dt_kmh_per_window/1.852,35)
        self.assertFalse(exact.is_interpolated)
        estimated=values.loc[values.time==points[0].time+pd.Timedelta(hours=18)].iloc[0]
        self.assertTrue(estimated.is_interpolated)
        self.assertLessEqual(values.window_end.max(),points[-1].time)


@unittest.skipUnless(os.environ.get('CYCLONEAID_GUI_TESTS')=='1','Requires a working X display')
class ApplicationStartupTests(unittest.TestCase):
    def test_home_launch_sample_open_navigation_and_close(self):
        import storm_tracker_gui as ui
        from cycloneaid.session import load_project
        root=Path(__file__).resolve().parents[1]
        with TemporaryDirectory() as directory, \
             patch('cycloneaid.gui_session.recovery_path',return_value=Path(directory)/'recovery.json'), \
             patch.object(ui,'_HAS_MAP',False):
            app=ui.StormTrackerApp()
            errors=[]
            app.report_callback_exception=lambda *args:errors.append(args)
            try:
                app.update()
                self.assertIsInstance(app.current_frame,ui.HomeScreen)
                home=app.current_frame
                before=home._canvas.yview()[0]
                home._canvas.event_generate('<Button-5>')
                app.update()
                self.assertGreater(home._canvas.yview()[0],before)
                home._canvas.event_generate('<MouseWheel>',delta=1)
                app.update()
                self.assertLess(home._canvas.yview()[0],before+.01)
                self.assertEqual(home._canvas.bbox(home._cw_id)[0],0)
                app.current_frame.on_start()
                app.update()
                screen=app.current_frame
                self.assertIsInstance(screen,ui.DataEntryScreen)
                with patch('cycloneaid.gui_session.filedialog.askopenfilename',
                           return_value=str(root/'examples/sample.cycloneaid.json')):
                    screen.open_session()
                app.update()
                self.assertEqual(screen.controller.session.rows,load_project(root/'examples/sample.cycloneaid.json').rows)
                self.assertEqual(screen.storm_name_var.get(),'TEST PALAU')
                # Scrolling after leaving Home must not call its destroyed canvas.
                app.event_generate('<MouseWheel>',delta=-120)
                app.update()
                screen._on_back_guarded()
                app.after(200,app.quit)
                app.mainloop()
                self.assertIsInstance(app.current_frame,ui.HomeScreen)
                self.assertEqual(errors,[])
            finally:
                app._close()
