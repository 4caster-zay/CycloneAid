from dataclasses import replace
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from cycloneaid.session import SessionController, point_to_row
from cycloneaid.gui_session import SessionScreenMixin
from test_core import point


class IncrementalMapTests(unittest.TestCase):
    def test_stale_tiles_cannot_reappear_after_pan_or_zoom(self):
        try:
            from cycloneaid.map_widget import ManagedMapView
        except ImportError:
            self.skipTest('Optional map not installed')
        widget=Mock()
        widget.running=True
        widget.zoom=5
        current, moved, removed=Mock(),Mock(),Mock()
        current.tile_name_position=(3,12)
        moved.tile_name_position=(4,12)
        widget.canvas_tile_array=[[current,moved]]
        widget.image_load_queue_results=[((5,3,12),removed,'old'),
                                         ((5,3,12),moved,'moved'),
                                         ((4,3,12),current,'wrong zoom'),
                                         ((5,3,12),current,'correct')]
        ManagedMapView.update_canvas_tile_images(widget)
        removed.set_image.assert_not_called()
        moved.set_image.assert_not_called()
        current.set_image.assert_called_once_with('correct')

    def test_one_edit_preserves_markers_and_viewport(self):
        screen=object.__new__(SessionScreenMixin)
        screen.controller=SessionController()
        rows=tuple(point_to_row(point(i*6,lon=125+i*.001)) for i in range(1000))
        screen.controller.commit(rows=rows)
        screen.map_widget=Mock()
        screen.map_widget.set_marker.side_effect=lambda *a,**kw: Mock()
        screen._map_markers={}
        screen._map_state={}
        screen._map_path=None
        screen._fit_pending=False
        screen._theme=lambda: Mock(INTENSITY_COLORS={'TS':'blue'},PRIMARY_COLOR='cyan')
        screen._refresh_map()
        self.assertEqual(screen.map_widget.set_marker.call_count,1000)
        marker=screen._map_markers[rows[500].row_id]
        values=list(rows[500].values)
        values[2]='10.01'
        changed=list(rows)
        changed[500]=replace(rows[500],values=tuple(values))
        screen.controller.commit(rows=changed)
        screen._refresh_map()
        self.assertEqual(screen.map_widget.set_marker.call_count,1000)
        marker.set_position.assert_called_once()
        marker.delete.assert_not_called()
        screen.map_widget.set_position.assert_not_called()
        screen.map_widget.set_zoom.assert_not_called()
        screen._map_path.set_position_list.assert_called_once()

    def test_stale_preview_is_not_opened(self):
        from cycloneaid.rendering import RenderResult
        screen=object.__new__(SessionScreenMixin)
        screen.controller=SessionController()
        screen.controller.commit(rows=[point_to_row(point())])
        screen.renderer=Mock()
        screen.renderer.poll.return_value=RenderResult(1,0,'track',figure_bytes=b'invalid if deserialized')
        screen._set_buttons_loading=Mock()
        screen._set_status=Mock()
        screen._show_preview=Mock()
        screen.after=Mock()
        screen._poll_renderer()
        screen._show_preview.assert_not_called()
        self.assertIn('Obsolete',screen._set_status.call_args.args[0])


@unittest.skipUnless(os.environ.get('CYCLONEAID_GUI_TESTS')=='1','Set CYCLONEAID_GUI_TESTS=1 with a working X display')
class TkSessionTests(unittest.TestCase):
    def setUp(self):
        import tkinter as tk
        import storm_tracker_gui as ui
        self.tmp=TemporaryDirectory()
        self.patches=[patch('cycloneaid.gui_session.recovery_path',return_value=Path(self.tmp.name)/'recovery.json'),
                      patch.object(ui,'_HAS_MAP',False),patch('cycloneaid.gui_session.messagebox.showwarning'),
                      patch('cycloneaid.gui_session.messagebox.showerror')]
        for item in self.patches:
            item.start()
        self.root=tk.Tk()
        self.root.withdraw()
        self.callback_errors=[]
        self.root.report_callback_exception=lambda *args:self.callback_errors.append(args)
        self.screen=ui.DataEntryScreen(self.root,lambda:None)
        self.screen.pack()
        self.root.update()

    def tearDown(self):
        self.screen._discard=True
        self.screen.destroy()
        self.root.update()
        self.root.destroy()
        for item in reversed(self.patches):
            item.stop()
        self.tmp.cleanup()
        self.assertEqual(self.callback_errors,[])

    def test_edit_undo_settings_save_and_failed_import(self):
        screen=self.screen
        row=point_to_row(point())
        screen._commit(rows=[row])
        screen._on_cell_save(row.row_id,2,'11.5')
        self.assertEqual(screen._validated()[0][0].lat,11.5)
        screen.undo()
        self.assertEqual(screen._validated()[0][0].lat,10)
        screen.redo()
        self.assertEqual(screen._validated()[0][0].lat,11.5)
        # Direct widget mutations do not become authoritative forecast data.
        screen.tree.set(row.row_id,'Lat','99')
        self.assertEqual(screen._validated()[0][0].lat,11.5)
        screen._project_path=str(Path(self.tmp.name)/'project.json')
        self.assertTrue(screen.save_session())
        self.assertFalse(screen.controller.dirty)
        before=screen.controller.session
        path=Path(self.tmp.name)/'invalid.csv'
        path.write_text('invalid\nfile\n')
        with patch('cycloneaid.gui_session.filedialog.askopenfilename',return_value=str(path)):
            screen.import_csv()
        self.assertEqual(screen.controller.session,before)
        screen.session_settings()
        self.root.update()

    def test_busy_buttons_and_manual_landfall_sync(self):
        screen=self.screen
        row=point_to_row(point())
        screen._commit(rows=[row])
        screen.renderer._pending=(1,screen.controller.session.revision,'track')
        screen._on_cell_save(row.row_id,5,'True')
        self.assertTrue(all(str(button['state'])=='disabled' for button in screen._action_btns))
        self.assertTrue(screen._validated()[0][0].landfall)
        screen.renderer._pending=None

    def test_recovery_restores_session(self):
        from cycloneaid.session import load_project
        row=point_to_row(point())
        self.screen._commit(rows=[row])
        previous_timer=self.screen._autosave_after
        self.screen._autosave()
        self.assertNotIn(previous_timer,self.root.tk.call('after','info'))
        restored=load_project(Path(self.tmp.name)/'recovery.json')
        self.assertEqual(restored.rows,(row,))

    def test_worker_previews_and_snapshot_export_keep_tk_responsive(self):
        import time
        from cycloneaid.session import SessionSettings
        screen=self.screen
        screen._commit(rows=[point_to_row(point()),point_to_row(point(24,wind_kt=80))],
                       settings=SessionSettings(geography_mode='degraded'))
        def wait(predicate):
            deadline=time.monotonic()+45
            while not predicate() and time.monotonic()<deadline:
                self.root.update()
                time.sleep(.02)
            self.assertTrue(predicate(),str(screen.renderer._pending))
        for product in ('track','prognostic','ri'):
            screen._start_plot(product)
            wait(lambda: product in screen._previews)
        path=Path(self.tmp.name)/'saved.png'
        revision=screen.controller.session.revision
        with patch('cycloneaid.gui_session.filedialog.asksaveasfilename',return_value=str(path)):
            screen.save_track()
        row=screen.controller.session.rows[0]
        screen._on_cell_save(row.row_id,2,'10.1')
        self.assertGreater(screen.controller.session.revision,revision)
        ticks=[]
        def tick():
            ticks.append(time.monotonic())
            if screen.renderer.busy:
                self.root.after(20,tick)
        self.root.after(20,tick)
        wait(lambda:not screen.renderer.busy)
        self.assertTrue(path.read_bytes().startswith(b'\x89PNG'))
        self.assertGreater(len(ticks),1)
        from PIL import Image
        import json
        with Image.open(path) as image:
            metadata=json.loads(image.info['Description'])
            self.assertEqual(metadata['revision'],revision)
            self.assertEqual(metadata['points'][0]['lat'],10)

    def test_optional_map_reuses_real_markers(self):
        try:
            from cycloneaid.map_widget import ManagedMapView
        except ImportError:
            self.skipTest('Optional map not installed')
        screen=self.screen
        with patch.object(ManagedMapView,'request_image',
                          lambda widget,*args,**kwargs:widget.empty_tile_image):
            widget=ManagedMapView(self.root,width=500,height=350)
            widget.pack()
            from PIL import Image, ImageTk
            key=(widget.tile_server,5,3,12)
            widget.tile_image_cache[key]=Image.new('RGB',(256,256),'blue')
            self.assertIsInstance(widget.get_tile_image_from_cache(5,3,12),ImageTk.PhotoImage)
            self.assertIsInstance(widget.tile_image_cache[key],Image.Image)
            screen.map_widget=widget
            rows=[point_to_row(point()),point_to_row(point(6,lat=11,lon=126))]
            screen._commit(rows=rows)
            screen.after_cancel(screen._map_after)
            screen._refresh_map()
            marker=screen._map_markers[rows[0].row_id]
            zoom=widget.zoom
            screen._on_cell_save(rows[0].row_id,2,'10.1')
            screen.after_cancel(screen._map_after)
            screen._refresh_map()
            self.assertIs(screen._map_markers[rows[0].row_id],marker)
            self.assertEqual(widget.zoom,zoom)
            self.assertEqual(len(widget.canvas_marker_list),2)
            self.assertEqual(len(widget.canvas_path_list),1)
            widget.destroy()
            self.assertFalse(widget._scheduled_callbacks)
            screen.map_widget=None

    def test_sample_preview_replacement_resize_and_close(self):
        import time
        from cycloneaid.session import load_project
        sample=load_project(Path(__file__).resolve().parents[1]/'examples/sample.cycloneaid.json')
        screen=self.screen
        self.root.deiconify()
        modes=('degraded','full') if os.environ.get('CYCLONEAID_GEOGRAPHY_TESTS')=='1' else ('degraded',)
        with patch('cycloneaid.gui_session.messagebox.showerror') as errors:
            for mode in modes:
                screen._commit(rows=sample.rows,settings=replace(sample.settings,geography_mode=mode))
                for cycle in range(3):
                    for product in ('track','prognostic','ri'):
                        with self.subTest(mode=mode,cycle=cycle,product=product):
                            screen._start_plot(product)
                            deadline=time.monotonic()+90
                            while screen.renderer.busy and time.monotonic()<deadline:
                                self.root.update()
                                time.sleep(.02)
                            self.assertFalse(screen.renderer.busy,'Preview worker timed out')
                            self.assertFalse(errors.call_args_list,str(errors.call_args_list))
                            self.assertIn(product,screen._previews)
                            figure,window,_=screen._previews[product]
                            window.geometry('800x550')
                            self.root.update()
                            window.geometry('1100x750')
                            canvas=figure.canvas
                            canvas.draw_idle()
                            # Exercise closure while a Tk canvas redraw is queued.
                            if cycle==2:
                                window.destroy()
                                self.assertIsNone(canvas._idle_draw_id)
                            self.root.update()
                            self.assertFalse(self.callback_errors,str(self.callback_errors))

    def test_failed_preview_replacement_preserves_existing_window_and_releases_figure(self):
        import matplotlib.pyplot as plt
        screen=self.screen
        previous=plt.figure()
        screen._show_preview(previous,'ri',0)
        self.root.update()
        window=screen._previews['ri'][1]
        replacement=plt.figure()
        with patch('matplotlib.backends.backend_tkagg.FigureCanvasTkAgg',side_effect=RuntimeError('canvas init failed')):
            with self.assertRaisesRegex(RuntimeError,'canvas init failed'):
                screen._show_preview(replacement,'ri',0)
        self.assertTrue(window.winfo_exists())
        self.assertIs(screen._previews['ri'][0],previous)
        self.assertNotIn(replacement.number,plt.get_fignums())
