"""A single spawned Agg renderer. Tk owns only independent preview copies."""
from dataclasses import asdict, dataclass, replace
import multiprocessing as mp
import json
import textwrap
import os
from pathlib import Path
import pickle
import queue
import tempfile
import traceback

from cycloneaid.model import utc_timestamp
from cycloneaid.session import SessionSettings, validate_session


@dataclass(frozen=True)
class RenderRequest:
    revision: int
    product: str
    points: tuple
    settings: SessionSettings
    view_state: tuple = ()

    def __post_init__(self):
        object.__setattr__(self, 'points', tuple(self.points))
        state = tuple((tuple(map(float, xlim)), tuple(map(float, ylim))) for xlim, ylim in self.view_state)
        object.__setattr__(self, 'view_state', state)

    @property
    def figure_key(self):
        return self.revision, self.product, self.points, self.settings

    @classmethod
    def from_session(cls, session, product):
        if product not in ("track", "prognostic", "ri"):
            raise ValueError("Unknown chart product")
        points, result = validate_session(session, regional=product == "track")
        if result.has_errors():
            raise ValueError("\n".join(result.hard_errors))
        return cls(session.revision, product, points, session.settings)


@dataclass(frozen=True)
class RenderResult:
    job_id: int
    revision: int
    product: str
    figure_bytes: bytes = b""
    path: str = ""
    error: str = ""
    detail: str = ""
    cache_hit: bool = False


def build_figure(request):
    from cycloneaid.geography import ensure_geography, detect_landfalls
    from export_preset import get_preset
    from validation import validate_forecast_points
    settings, points = request.settings, request.points
    issue = utc_timestamp(settings.issue_time) if settings.issue_time else points[0].time
    events = ()
    if settings.geography_mode == "full" and request.product != "ri":
        ensure_geography()
        events = detect_landfalls(points)
    if request.product == "track":
        from storm_tracker import plot_storm_track
        context = get_preset(settings.preset).build_render_context(dict(
            forecast_points=points, issue_time=issue, valid_until=points[-1].time,
            has_interpolated=any(p.is_interpolated for p in points),
            forecaster_confidence=settings.confidence,
            validation_result=validate_forecast_points(points)))
        figure = plot_storm_track(points, settings.storm_name, issue, settings.confidence, context,
                                  geography_mode=settings.geography_mode, landfall_events=events)
    elif request.product == "prognostic":
        from storm_prognostic import plot_storm_prognostic
        figure = plot_storm_prognostic(points, settings.storm_name, issue,
                                      geography_mode=settings.geography_mode, landfall_events=events)
    else:
        from storm_RI_plot import plot_ri_from_forecast_points
        figure = plot_ri_from_forecast_points(points, storm_name=settings.storm_name)
    source = f"Source: {settings.source} | Wind averaging: {settings.wind_averaging_period} | Issue: {issue:%Y-%m-%d %H:%MZ}"
    overrides = [p.override_reason for p in points if p.override_reason]
    if settings.import_notes:
        source += " | Imported data notes: see project/PNG metadata"
    if overrides:
        source += f" | {len(overrides)} intensity override(s): see project/PNG metadata"
    figure.text(.5, .005, textwrap.fill(source, 160), fontsize=6, ha="center", va="bottom")
    figure._cycloneaid_provenance = {
        "revision": request.revision, "product": request.product, "settings": asdict(settings),
        "points": [dict(asdict(point), time=point.time.isoformat()) for point in points],
    }
    return figure


def export_figure(figure, path, *, dpi=300, view_state=()):
    """Atomic explicit PNG export; caller retains figure ownership."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    original = [(ax.get_xlim(), ax.get_ylim(), ax.get_autoscalex_on(), ax.get_autoscaley_on()) for ax in figure.axes]
    try:
        for ax, (xlim, ylim) in zip(figure.axes, view_state):
            ax.set_xlim(xlim)
            ax.set_ylim(ylim)
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".cycloneaid-", suffix=".png", delete=False) as handle:
            temporary = Path(handle.name)
        from cycloneaid.metadata import __version__
        metadata = {"Software": f"CycloneAid {__version__}",
                    "Description": json.dumps(dict(getattr(figure, '_cycloneaid_provenance', {}), view_state=view_state))}
        figure.savefig(temporary, format="png", dpi=dpi, bbox_inches="tight", pad_inches=.2,
                       facecolor=figure.get_facecolor(), metadata=metadata)
        os.replace(temporary, path)
    finally:
        for ax, (xlim, ylim, auto_x, auto_y) in zip(figure.axes, original):
            ax.set_xlim(xlim)
            ax.set_ylim(ylim)
            ax.set_autoscalex_on(auto_x)
            ax.set_autoscaley_on(auto_y)
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _worker(commands, results):
    import matplotlib
    matplotlib.use("Agg", force=True)
    import matplotlib.pyplot as plt
    cache = {}
    try:
        while True:
            command = commands.get()
            if command[0] == "stop":
                return
            if command[0] == "invalidate":
                for product, (request, figure) in list(cache.items()):
                    if request.revision != command[1]:
                        plt.close(figure)
                        del cache[product]
                continue
            _, job_id, request, path, view_state = command
            before = set(plt.get_fignums())
            try:
                if request == "assets":
                    from cycloneaid.geography import ensure_geography
                    ensure_geography()
                    results.put(RenderResult(job_id, -1, "assets"))
                    continue
                hit = request.product in cache and cache[request.product][0].figure_key == request.figure_key
                if not hit:
                    if request.product in cache:
                        plt.close(cache.pop(request.product)[1])
                    figure = build_figure(request)
                    # Cache only completed, renderable figures.
                    figure.canvas.draw()
                    cache[request.product] = (request, figure)
                figure = cache[request.product][1]
                if path:
                    export_figure(figure, path, view_state=view_state)
                    payload = b""
                else:
                    payload = pickle.dumps(figure, protocol=pickle.HIGHEST_PROTOCOL)
                results.put(RenderResult(job_id, request.revision, request.product, payload,
                                         str(path or ""), cache_hit=hit))
            except Exception as exc:
                for number in set(plt.get_fignums())-before:
                    if not any(fig.number == number for _, fig in cache.values()):
                        plt.close(number)
                results.put(RenderResult(job_id, getattr(request, "revision", -1),
                                         getattr(request, "product", "assets"), error=str(exc),
                                         detail=traceback.format_exc()))
    finally:
        plt.close("all")


class RenderCoordinator:
    def __init__(self):
        context = mp.get_context("spawn")
        self._commands, self._results = context.Queue(), context.Queue()
        self._process = None
        self._context = context
        self._job_id = 0
        self._pending = None
        self.revision = 0
        self.closed = False

    @property
    def busy(self):
        return self._pending is not None

    def _start(self):
        if self.closed:
            raise RuntimeError("Renderer is closed")
        if self._process is None:
            self._process = self._context.Process(target=_worker, args=(self._commands, self._results), daemon=True)
            self._process.start()

    def submit(self, request, path=None, view_state=()):
        if self.busy:
            raise RuntimeError("A render/export is already running")
        if isinstance(request, RenderRequest):
            request = replace(request, view_state=tuple(view_state) or request.view_state)
            view_state = request.view_state
        self._start()
        self._job_id += 1
        self._pending = (self._job_id, getattr(request, "revision", -1), getattr(request, "product", "assets"))
        self._commands.put(("render", self._job_id, request, path, view_state))
        return self._job_id

    def invalidate(self, revision):
        self.revision = revision
        if self._process is not None and not self.busy:
            self._commands.put(("invalidate", revision))

    def poll(self):
        try:
            result = self._results.get_nowait()
        except queue.Empty:
            if self.busy and self._process is not None and not self._process.is_alive():
                job, revision, product = self._pending
                self._pending = None
                self._process.join(timeout=.1)
                self._process = None
                # Discard queues from a crashed process before restarting.
                self._commands.cancel_join_thread()
                self._results.cancel_join_thread()
                self._commands.close()
                self._results.close()
                self._commands, self._results = self._context.Queue(), self._context.Queue()
                return RenderResult(job, revision, product, error="Rendering process stopped unexpectedly; retry the operation")
            return None
        self._pending = None
        if self._process is not None:
            self._commands.put(("invalidate", self.revision))
        return result

    def close(self):
        if self.closed:
            return
        self.closed = True
        if self._process is not None:
            self._commands.put(("stop",))
            self._process.join(timeout=.5)
            if self._process.is_alive():
                self._process.terminate()
                self._process.join(timeout=1)
        self._commands.close()
        self._results.close()
        self._commands.cancel_join_thread()
        self._results.cancel_join_thread()
        self._pending = None
