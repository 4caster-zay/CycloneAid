from io import BytesIO
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from cycloneaid.ui_scroll import wheel_steps


class WheelTests(unittest.TestCase):
    def test_linux_windows_and_small_wheel_deltas(self):
        for event,expected in ((dict(num=4),1),(dict(num=5),-1),
                               (dict(delta=120),1),(dict(delta=-120),-1),
                               (dict(delta=1),1),(dict(delta=-1),-1),(dict(delta=0),0)):
            self.assertEqual(wheel_steps(SimpleNamespace(**event)),expected)

    def test_tile_downloads_do_not_create_tk_images(self):
        from PIL import Image
        try:
            from cycloneaid.map_widget import ManagedMapView
        except ImportError:
            self.skipTest('Optional map not installed')
        buffer=BytesIO()
        Image.new('RGB',(16,16),'blue').save(buffer,format='PNG')
        response=Mock(content=buffer.getvalue())
        context=Mock()
        context.__enter__=Mock(return_value=response)
        context.__exit__=Mock(return_value=False)
        widget=Mock(running=True,tile_server='https://example.invalid/{z}/{x}/{y}.png')
        widget.tile_image_cache={}
        with patch('cycloneaid.map_widget.requests.get',return_value=context) as download, \
             patch('cycloneaid.map_widget.ImageTk.PhotoImage',side_effect=AssertionError('Tk on downloader')):
            image=ManagedMapView.request_image(widget,5,3,12)
        self.assertIsInstance(image,Image.Image)
        self.assertIn((widget.tile_server,5,3,12),widget.tile_image_cache)
        self.assertEqual(download.call_args.kwargs['timeout'],(3,5))
