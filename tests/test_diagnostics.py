import contextlib
import io
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from cycloneaid.diagnostics import LOGGER, configure_logging, error_message


class DiagnosticsTests(unittest.TestCase):
    def test_worker_traceback_is_saved_and_location_is_reported(self):
        original=list(LOGGER.handlers)
        try:
            with TemporaryDirectory() as directory, contextlib.redirect_stderr(io.StringIO()) as terminal:
                path=configure_logging(Path(directory))
                message=error_message('track render (revision 5)','Rendering failed',
                                      'Traceback from worker\noriginal failure detail')
                self.assertIn('original failure detail',path.read_text(encoding='utf-8'))
                self.assertIn('revision 5',path.read_text(encoding='utf-8'))
                self.assertIn(str(path),message)
                self.assertIn('original failure detail',terminal.getvalue())
                for handler in list(LOGGER.handlers):
                    if handler not in original:
                        LOGGER.removeHandler(handler)
                        handler.close()
        finally:
            for handler in list(LOGGER.handlers):
                if handler not in original:
                    LOGGER.removeHandler(handler)
                    handler.close()
