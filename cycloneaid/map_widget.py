"""Optional map widget with explicit ownership of scheduled Tk callbacks."""
from io import BytesIO
import threading
import time
import requests
from PIL import Image, ImageTk
from tkintermapview import TkinterMapView
from cycloneaid.ui_scroll import wheel_steps
from cycloneaid.metadata import __version__


class ManagedMapView(TkinterMapView):
    def __init__(self, *args, **kwargs):
        self._scheduled_callbacks = set()
        self._tk_tile_cache = {}
        self._failed_tiles = set()
        super().__init__(*args, **kwargs)

    def pre_cache(self):
        # Fetch visible tiles on demand; the upstream prefetcher creates Tk images
        # in a background thread and downloads hundreds of unused tiles.
        return

    def request_image(self, zoom, x, y, db_cursor=None):
        if not self.running or not (0 <= x < 2**zoom and 0 <= y < 2**zoom):
            return None
        key = (self.tile_server, zoom, x, y)
        try:
            url = self.tile_server.format(z=zoom, x=x, y=y)
            with requests.get(url, timeout=(3, 5), headers={'User-Agent': f'CycloneAid/{__version__} (TkinterMapView)'}) as response:
                response.raise_for_status()
                with Image.open(BytesIO(response.content)) as source:
                    image = source.convert('RGB')
            if self.running:
                self._failed_tiles.discard(key)
                self.tile_image_cache[key] = image
                if len(self.tile_image_cache) > 512:
                    self.tile_image_cache.pop(next(iter(self.tile_image_cache)), None)
                return image
        except (requests.RequestException, OSError, ValueError):
            self._failed_tiles.add(key)
            if len(self._failed_tiles) > 512:
                self._failed_tiles.pop()
        return None

    def tile_availability(self):
        """Report actual visible tile evidence; call only from the Tk thread."""
        tiles = [tile for column in self.canvas_tile_array for tile in column]
        if not tiles:
            return "loading", ""
        placeholders = (self.not_loaded_tile_image, self.empty_tile_image)
        loaded = sum(tile.image not in placeholders for tile in tiles)
        if loaded == len(tiles):
            return "ready", ""
        zoom = round(self.zoom)
        visible = {(self.tile_server, zoom, *tile.tile_name_position) for tile in tiles}
        if visible.intersection(self._failed_tiles):
            return "unavailable", f"{loaded}/{len(tiles)} visible tiles loaded; cached coverage may be partial."
        return "loading", f"{loaded}/{len(tiles)} visible tiles loaded."

    def load_images_background(self):
        while self.running:
            try:
                coordinates, tile = self.image_load_queue_tasks.pop()
            except IndexError:  # Another loader or zoom can empty the queue.
                time.sleep(.02)
                continue
            image = self.get_tile_image_from_cache(*coordinates)
            if image is False:
                image = self.request_image(*coordinates)
            if image is not None and self.running:
                self.image_load_queue_results.append((coordinates, tile, image))
            image = None

    def get_tile_image_from_cache(self, zoom, x, y):
        key = (self.tile_server, zoom, x, y)
        image = self.tile_image_cache.get(key, False)
        if isinstance(image, Image.Image) and threading.current_thread() is threading.main_thread():
            if key not in self._tk_tile_cache:
                self._tk_tile_cache[key] = ImageTk.PhotoImage(image, master=self.canvas)
                # CanvasTile owns visible images; eviction cannot blank those tiles.
                if len(self._tk_tile_cache) > 256:
                    self._tk_tile_cache.pop(next(iter(self._tk_tile_cache)))
            return self._tk_tile_cache[key]
        return image

    def update_canvas_tile_images(self):
        live = {id(tile) for column in self.canvas_tile_array for tile in column}
        while self.image_load_queue_results and self.running:
            (zoom, x, y), tile, image = self.image_load_queue_results.pop(0)
            if (zoom != round(self.zoom) or id(tile) not in live
                    or tuple(tile.tile_name_position) != (x, y)):
                continue
            if isinstance(image, Image.Image):
                image = self.get_tile_image_from_cache(zoom, x, y)
                if image is False:
                    continue
            tile.set_image(image)
        if self.running:
            self.after(20, self.update_canvas_tile_images)

    def mouse_zoom(self, event):
        self.fading_possible = False  # Stop drag inertia before changing scale.
        self.set_zoom(round(self.zoom) + wheel_steps(event),
                      relative_pointer_x=event.x/max(1, self.width),
                      relative_pointer_y=event.y/max(1, self.height))
        return 'break'

    def update_dimensions(self, event):
        if event.width > 1 and event.height > 1:
            super().update_dimensions(event)

    def after(self, milliseconds, function=None, *args):
        if function is None:
            return super().after(milliseconds)
        pending = {}
        def dispatch():
            self._scheduled_callbacks.discard(pending['id'])
            if self.winfo_exists():
                function(*args)
        identifier = super().after(milliseconds, dispatch)
        pending['id'] = identifier
        self._scheduled_callbacks.add(identifier)
        return identifier

    def after_cancel(self, identifier):
        self._scheduled_callbacks.discard(identifier)
        return super().after_cancel(identifier)

    def destroy(self):
        self.running = False
        for identifier in tuple(self._scheduled_callbacks):
            self.after_cancel(identifier)
        super().destroy()
        self._tk_tile_cache.clear()
