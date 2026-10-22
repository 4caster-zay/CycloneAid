"""Workspace contracts: packaged examples, project boundaries, and keyboard edits."""
from dataclasses import replace
from importlib.resources import files
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from cycloneaid.generation import generate_rows
from cycloneaid.session import ForecastSession, SessionController, SessionSettings


class WorkspaceCoreTests(unittest.TestCase):
    def test_packaged_sample_matches_documented_example(self):
        bundled = files('cycloneaid').joinpath('data/sample.cycloneaid.json').read_bytes()
        documented = (Path(__file__).resolve().parents[1]/'examples/sample.cycloneaid.json').read_bytes()
        self.assertEqual(bundled, documented)

    def test_project_reset_clears_history_without_reusing_render_revision(self):
        controller = SessionController()
        controller.commit(rows=generate_rows('2026-01-01 00:00', 6, 6), infer_issue_time=False)
        old_revision = controller.session.revision
        project = ForecastSession(settings=SessionSettings(storm_name=''))
        controller.reset(project)
        self.assertGreater(controller.session.revision, old_revision)
        self.assertEqual(controller.session.rows, ())
        self.assertFalse(controller.dirty)
        self.assertFalse(controller.undo())
        self.assertFalse(controller.redo())
        last = controller.session.revision
        controller.reset(project)
        self.assertGreater(controller.session.revision, last)

    def test_tile_status_uses_visible_tiles_not_chart_cache_or_old_failures(self):
        try:
            from cycloneaid.map_widget import ManagedMapView
        except ImportError:
            self.skipTest('Desktop map extra is not installed')
        pending, empty, loaded = object(), object(), object()
        tile = SimpleNamespace(image=pending, tile_name_position=(3, 12))
        widget = SimpleNamespace(canvas_tile_array=[[tile]], not_loaded_tile_image=pending,
                                 empty_tile_image=empty, zoom=5, tile_server='server', _failed_tiles=set())
        self.assertEqual(ManagedMapView.tile_availability(widget)[0], 'loading')
        widget._failed_tiles.add(('server', 5, 0, 0))
        self.assertEqual(ManagedMapView.tile_availability(widget)[0], 'loading')
        widget._failed_tiles.add(('server', 5, 3, 12))
        self.assertEqual(ManagedMapView.tile_availability(widget)[0], 'unavailable')
        tile.image = loaded
        self.assertEqual(ManagedMapView.tile_availability(widget)[0], 'ready')


@unittest.skipUnless(os.environ.get('CYCLONEAID_GUI_TESTS') == '1', 'Requires Tk display')
class WorkspaceTkTests(unittest.TestCase):
    def setUp(self):
        import tkinter as tk
        import storm_tracker_gui as ui
        self.tmp = TemporaryDirectory()
        self.patches = [patch.object(ui, '_HAS_MAP', False),
                        patch('cycloneaid.gui_session.recovery_path', return_value=Path(self.tmp.name)/'recovery.json'),
                        patch('cycloneaid.gui_maps.geography_readiness', return_value=())]
        for item in self.patches:
            item.start()
        self.root = tk.Tk()
        self.root.geometry('1366x768')
        self.errors = []
        self.root.report_callback_exception = lambda *args: self.errors.append(args)
        self.screen = ui.DataEntryScreen(self.root, lambda: None)
        self.screen.pack(fill='both', expand=True)
        self.root.update()

    def tearDown(self):
        self.screen._discard = True
        self.screen.destroy()
        self.root.update()
        self.root.destroy()
        for item in reversed(self.patches):
            item.stop()
        self.tmp.cleanup()
        self.assertEqual(self.errors, [])

    def completed_rows(self):
        return tuple(replace(row, values=(row.values[0], '', '10', '125', '40', 'False', 'Tropical', 'TS', 'False'))
                     for row in generate_rows('2026-01-01 00:00', 6, 6))

    def test_layout_fits_supported_sizes_and_tabs_never_render(self):
        screen = self.screen
        with patch.object(screen.renderer, 'submit') as submit:
            for width, height in ((1920, 1080), (1366, 768), (1000, 650)):
                self.root.geometry(f'{width}x{height}')
                self.root.update()
                self.assertLessEqual(screen.theme_toggle.winfo_rootx()+screen.theme_toggle.winfo_width(),
                                     self.root.winfo_rootx()+self.root.winfo_width())
                self.assertGreater(screen.tree.winfo_height(), 180)
                self.assertGreater(screen.map_frame.winfo_height(), 100)
                ratio = screen._paned.sash_coord(0)[0]/screen._paned.winfo_width()
                self.assertAlmostEqual(ratio, .55, delta=.02)
                menu = screen._row_io_button
                self.assertLessEqual(menu.winfo_rootx()+menu.winfo_width(),
                                     menu.master.winfo_rootx()+menu.master.winfo_width())
                for tab in screen.output_notebook.tabs():
                    screen.output_notebook.select(tab)
                    self.root.update()
                submit.assert_not_called()
        self.assertEqual(screen._osm_map_state, 'not_installed')
        self.assertNotIn('Check connectivity', screen._osm_map_status)
        with patch('cycloneaid.gui_maps.geography_readiness', return_value=('missing-test-asset',)):
            screen._refresh_map_readiness()
            screen.output_notebook.select(screen.map_frame)
            self.root.update()
            for child in screen._map_host.winfo_children():
                self.assertLessEqual(child.winfo_y()+child.winfo_height(), screen._map_host.winfo_height())

    def test_both_themes_keep_text_readable_in_control_states(self):
        from tkinter import ttk
        import storm_tracker_gui as ui
        def luminance(color):
            values = [int(color[index:index+2], 16)/255 for index in (1, 3, 5)]
            linear = [value/12.92 if value <= .04045 else ((value+.055)/1.055)**2.4 for value in values]
            return sum(value*weight for value, weight in zip(linear, (.2126, .7152, .0722)))
        style = ttk.Style(self.root)
        for theme in ('Typhoon Dark', 'Sky Light'):
            ui.set_app_theme(theme, self.root, persist=False)
            for control in ('TButton', 'Accent.TButton', 'Workspace.TMenubutton', 'Theme.TRadiobutton',
                            'Workspace.TNotebook.Tab', 'TCombobox', 'TEntry', 'Error.TLabel'):
                for state in ((), ('active',), ('pressed',), ('focus',), ('disabled',), ('selected', 'active')):
                    with self.subTest(theme=theme, control=control, state=state):
                        foreground = style.lookup(control, 'foreground', state=state)
                        background = style.lookup(control, 'fieldbackground' if control in ('TCombobox', 'TEntry') else 'background', state=state)
                        bright, dark = sorted((luminance(foreground), luminance(background)), reverse=True)
                        self.assertGreaterEqual((bright+.05)/(dark+.05), 4.5)

    def test_fitted_preview_scales_title_and_preserves_original_export_copy(self):
        import matplotlib.pyplot as plt
        screen = self.screen
        figure = plt.figure(figsize=(12, 8), dpi=100)
        title = figure.suptitle('TEST PALAU — Forecast track issued 2026-10-22 00:00Z', fontsize=18)
        figure.add_subplot().plot([1, 2], [1, 2])
        screen._show_preview(figure, 'track', screen.controller.session.revision)
        screen.output_notebook.select(screen._output_pages['track'])
        for width, height in ((1920, 1080), (1366, 768), (1000, 650)):
            self.root.geometry(f'{width}x{height}')
            self.root.update()
            figure.canvas.draw()
            bounds = title.get_window_extent(figure.canvas.get_renderer())
            canvas_width = figure.canvas.get_tk_widget().winfo_width()
            self.assertGreaterEqual(bounds.x0, -2)
            self.assertLessEqual(bounds.x1, canvas_width+2)
            self.assertEqual(figure.canvas._preview_original_inches, (12., 8.))
            self.assertLessEqual(figure.dpi, 100)

    def test_tab_commits_moves_shift_tab_returns_and_escape_cancels(self):
        screen = self.screen
        rows = self.completed_rows()
        screen._commit(rows=rows, infer_issue_time=False)
        self.root.update()
        screen._edit_cell(rows[0].row_id, 2)
        first = screen.cell_editor
        first._value_var.set('11')
        first._navigate(1)
        self.assertEqual(screen.controller.session.rows[0].values[2], '11')
        self.assertEqual(screen.cell_editor.col_idx, 3)
        screen.cell_editor._navigate(-1)
        self.assertEqual(screen.cell_editor.col_idx, 2)
        editor = screen.cell_editor
        editor._value_var.set('99')
        editor.cancel()
        self.assertEqual(screen.controller.session.rows[0].values[2], '11')
        screen._edit_cell(rows[0].row_id, 2)
        screen.cell_editor._value_var.set('12')
        screen.cell_editor._finish()
        self.assertEqual(screen.controller.session.rows[0].values[2], '12')
        screen.undo()
        self.assertEqual(screen.controller.session.rows[0].values[2], '11')

    def test_unchanged_timestamp_edit_preserves_generated_provenance(self):
        screen = self.screen
        rows = self.completed_rows()
        screen._commit(rows=rows, infer_issue_time=False)
        revision = screen.controller.session.revision
        text = screen.tree.item(rows[0].row_id, 'values')[0]
        screen._on_cell_save(rows[0].row_id, 0, text)
        self.assertEqual(screen.controller.session.revision, revision)
        self.assertEqual(screen.controller.session.rows[0].time_origin, 'generated')

    def test_property_edits_do_not_fill_an_explicitly_blank_issue_time(self):
        rows = generate_rows('2026-01-01 00:00', 6, 6)
        self.screen._replace_project(ForecastSession(rows, SessionSettings(storm_name='', geography_mode='degraded')))
        self.screen.enable_maps()
        self.screen.storm_name_var.set('TEST')
        self.screen._flush_name_edit()
        self.screen.forecaster_confidence_var.set('Low')
        self.assertEqual(self.screen.controller.session.settings.issue_time, '')
        self.assertEqual(self.screen.controller.session.rows, rows)

    def test_generated_draft_times_remain_readable_before_other_cells_are_entered(self):
        rows = generate_rows('2026-01-01 00:00', 6, 6)
        self.screen._commit(rows=rows, infer_issue_time=False)
        self.assertEqual(self.screen.tree.item(rows[0].row_id, 'values')[0], '2026-01-01 00:00:00')
        self.assertEqual(self.screen.tree.item(rows[1].row_id, 'values')[0], '2026-01-01 06:00:00')
        self.assertEqual(self.screen.controller.session.rows, rows)
        self.assertFalse(self.screen._is_table_valid())

    def test_new_project_cancel_and_reset_history(self):
        screen = self.screen
        screen._commit(rows=self.completed_rows())
        before = screen.controller.session
        with patch('cycloneaid.gui_session.messagebox.askyesnocancel', return_value=None):
            screen.new_session()
        self.assertEqual(screen.controller.session, before)
        with patch('cycloneaid.gui_session.messagebox.askyesnocancel', return_value=False):
            screen.new_session()
        self.assertEqual(screen.controller.session.rows, ())
        self.assertEqual(screen.storm_name_var.get(), '')
        self.assertFalse(screen.controller.dirty)
        self.assertFalse(screen.controller.undo())
        self.assertEqual(screen.controller.session.settings.geography_mode, 'full')

    def test_session_details_close_when_project_is_replaced_imported_or_recovered(self):
        from cycloneaid.session import save_project
        screen = self.screen
        replacement = ForecastSession(self.completed_rows(), SessionSettings(storm_name='Replacement', source='NEW'))
        for action in ('replace', 'import', 'recovery'):
            with self.subTest(action=action):
                screen.session_settings()
                window = screen._settings_window
                self.assertTrue(window.winfo_exists())
                if action == 'replace':
                    screen._replace_project(replacement)
                elif action == 'import':
                    sample = Path(__file__).resolve().parents[1]/'forecast.csv'
                    with patch('cycloneaid.gui_session.filedialog.askopenfilename', return_value=str(sample)):
                        screen.import_csv()
                else:
                    save_project(replacement, Path(self.tmp.name)/'recovery.json')
                    with patch('cycloneaid.gui_session.messagebox.askyesno', return_value=True):
                        screen._offer_recovery()
                self.assertFalse(window.winfo_exists())
                self.assertIsNone(screen._settings_window)
                self.assertEqual(screen.controller.session.settings.source, 'NEW')

    def test_busy_progress_callbacks_are_cancelled_before_workspace_closes(self):
        self.screen._set_buttons_loading(True, 'Rendering preview…')
        self.screen._discard = True
        self.screen.destroy()
        callbacks = [str(self.root.tk.call('after', 'info', identifier))
                     for identifier in self.root.tk.call('after', 'info')]
        self.assertFalse(any('Autoincrement' in callback for callback in callbacks), callbacks)

    def test_previous_project_render_results_do_not_change_new_output_tabs(self):
        from cycloneaid.rendering import RenderResult
        screen = self.screen
        screen.after_cancel(screen._poll_after)
        screen._poll_after = None
        old_generation = screen._project_generation
        screen._replace_project(ForecastSession(settings=SessionSettings(storm_name='New project')))
        for result in (RenderResult(7, 0, 'track', error='old failure'),
                       RenderResult(7, 0, 'track', path='/tmp/earlier-project.png'),
                       RenderResult(7, 0, 'track', figure_bytes=b'not deserialized')):
            screen._chart_job_project = (7, old_generation)
            with patch.object(screen.renderer, 'poll', return_value=result):
                screen._poll_renderer()
            self.assertEqual(screen._output_state_kind['track'], 'empty')
            self.assertEqual(screen._output_states['track'].get(), 'No preview yet')
            self.assertFalse(screen._previews)
            screen.after_cancel(screen._poll_after)
            screen._poll_after = None

    def test_preview_arrival_preserves_name_and_cell_editor_focus(self):
        import matplotlib.pyplot as plt
        screen = self.screen
        screen.name_entry.focus_force()
        screen.storm_name_var.set('Still typing')
        self.root.update()
        screen._show_preview(plt.figure(), 'ri', screen.controller.session.revision)
        self.root.update()
        self.assertIs(self.root.focus_get(), screen.name_entry)
        self.assertEqual(screen.controller.session.settings.storm_name, '')
        self.assertTrue(screen._has_pending_name_edit())
        screen._flush_name_edit()
        rows = self.completed_rows()
        screen._commit(rows=rows)
        self.root.update()
        screen._edit_cell(rows[0].row_id, 2)
        editor = screen.cell_editor
        editor.editor.focus_force()
        editor._value_var.set('11')
        self.root.update()
        screen._show_preview(plt.figure(), 'ri', screen.controller.session.revision)
        self.root.update()
        self.assertIs(self.root.focus_get(), editor.editor)
        self.assertEqual(screen.controller.session.rows[0].values[2], '10')
        self.assertEqual(editor._value_var.get(), '11')
        editor.cancel()

    def test_name_keyboard_undo_redo_operates_on_one_committed_edit(self):
        screen = self.screen
        screen.name_entry.focus_force()
        screen.storm_name_var.set('TEST PALAU')
        self.root.update()
        screen.name_entry.event_generate('<Control-z>')
        self.root.update()
        self.assertEqual(screen.storm_name_var.get(), '')
        screen.name_entry.event_generate('<Control-y>')
        self.root.update()
        self.assertEqual(screen.storm_name_var.get(), 'TEST PALAU')

    def test_project_save_shortcut_does_not_trigger_matplotlib_export(self):
        import matplotlib.pyplot as plt
        screen = self.screen
        screen._show_preview(plt.figure(), 'ri', screen.controller.session.revision)
        screen.output_notebook.select(screen._output_pages['ri'])
        self.root.update()
        widget = screen._previews['ri'][1].figure_canvas.get_tk_widget()
        widget.focus_force()
        path = Path(self.tmp.name)/'project.cycloneaid.json'
        events = []
        canvas = screen._previews['ri'][1].figure_canvas
        canvas.mpl_connect('key_press_event', lambda event: events.append(event.key))
        with patch('cycloneaid.gui_session.filedialog.asksaveasfilename', return_value=str(path)), \
             patch.object(screen, '_start_plot') as export:
            widget.event_generate('<Control-s>')
            self.root.update()
        self.assertTrue(path.exists())
        export.assert_not_called()
        self.assertEqual(events, [])

    def test_later_map_selection_survives_preparation_completion(self):
        import tkinter as tk
        from tkinter import ttk
        from cycloneaid.rendering import RenderResult
        screen = self.screen
        screen._map_asset_job_id = 7
        screen._map_asset_request_generation = screen._project_generation
        screen._map_asset_enable_requested = True
        screen.session_settings()
        dialog = next(child for child in screen.winfo_children() if isinstance(child, tk.Toplevel))
        selection = next(child for child in dialog.winfo_children() if isinstance(child, ttk.Combobox))
        selection.set('Without basemap')
        apply = next(child for child in dialog.winfo_children() if isinstance(child, ttk.Button))
        apply.invoke()
        self.assertFalse(screen._map_asset_enable_requested)
        screen._handle_map_asset_result(RenderResult(7, -1, 'assets'))
        self.assertEqual(screen.controller.session.settings.geography_mode, 'degraded')

    def test_live_map_initialization_failure_does_not_disable_chart_maps(self):
        import storm_tracker_gui as ui
        with patch.object(ui, '_HAS_MAP', True), \
             patch.object(ui, 'ManagedMapView', side_effect=RuntimeError('tile widget unavailable')):
            self.screen._retry_live_map()
        self.assertIsNone(self.screen.map_widget)
        self.assertEqual(self.screen._osm_map_state, 'unavailable')
        self.assertEqual(self.screen.controller.session.settings.geography_mode, 'full')
        self.assertIn('tile widget unavailable', self.screen._osm_map_status)

    def test_live_map_retry_preserves_successful_tiles_and_viewport(self):
        from PIL import Image
        import storm_tracker_gui as ui
        if not hasattr(ui, 'ManagedMapView'):
            self.skipTest('Desktop map extra is not installed')
        with patch.object(ui, '_HAS_MAP', True), \
             patch.object(ui.ManagedMapView, 'request_image', return_value=None):
            self.screen._retry_live_map()
            self.root.update()
            previous = self.screen.map_widget
            previous.set_position(13.5, 124.5)
            previous.set_zoom(7)
            position, zoom = previous.get_position(), previous.zoom
            tile = previous.canvas_tile_array[0][0]
            key = (previous.tile_server, round(zoom), *tile.tile_name_position)
            image = Image.new('RGB', (256, 256), 'navy')
            previous.tile_image_cache[key] = image
            self.screen._retry_live_map()
            self.root.update()
            current = self.screen.map_widget
            self.assertIsNot(current, previous)
            self.assertIs(current.tile_image_cache[key], image)
            self.assertEqual(current.zoom, zoom)
            for actual, expected in zip(current.get_position(), position):
                self.assertAlmostEqual(actual, expected, places=6)


if __name__ == '__main__':
    unittest.main()
