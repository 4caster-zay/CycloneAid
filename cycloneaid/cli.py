"""Compatible script entry points with shared input validation and explicit export."""
import argparse
from pathlib import Path
import re
import sys
from cycloneaid.imports import read_forecast
from cycloneaid.session import ForecastSession, SessionSettings, point_to_row
from cycloneaid.rendering import RenderRequest, build_figure, export_figure


def _run(product, argv=None):
    parser = argparse.ArgumentParser(description=f"CycloneAid {product} chart")
    if product == "track":
        parser.add_argument("confidence", nargs="?", default="Moderate", type=str.title,
                            choices=("High", "Moderate", "Low"))
        parser.add_argument("storm", nargs="?", default="TYPHOON")
        parser.add_argument("input", nargs="?", default="forecast.csv")
    elif product == "ri":
        parser.add_argument("input", nargs="?", default="forecast.csv")
        parser.add_argument("storm", nargs="?", default="STORM")
        parser.add_argument("threshold", nargs="?", type=float, default=30)
    else:
        parser.add_argument("input", nargs="?", default="forecast.csv")
        parser.add_argument("storm", nargs="?", default="STORM")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--degraded", action="store_true", help="Explicitly omit map assets, cities and automatic landfall")
    parser.add_argument("--landmask-qc", action="store_true", help="Enable optional point QC; loads an approximately 1 GB global mask")
    parser.add_argument("--start", help="UTC start for missing timestamps")
    parser.add_argument("--interval-hours", type=float)
    args = parser.parse_args(argv)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    figure = None
    try:
        points, warnings = read_forecast(args.input, start=args.start, interval_hours=args.interval_hours)
        for warning in warnings:
            print("Warning: " + warning, file=sys.stderr)
        settings = SessionSettings(storm_name=args.storm, confidence=getattr(args, "confidence", "Moderate"),
                                   issue_time=points[0].time.isoformat(),
                                   geography_mode="degraded" if args.degraded else "full", landmask_qc=args.landmask_qc)
        session = ForecastSession(tuple(point_to_row(point) for point in points), settings)
        request = RenderRequest.from_session(session, product)
        if product == "ri" and args.threshold != 30:
            from storm_RI_plot import plot_ri_from_forecast_points
            figure = plot_ri_from_forecast_points(points, ri_threshold_kt_24h=args.threshold, storm_name=args.storm)
        else:
            figure = build_figure(request)
        stem = re.sub(r"[^\w.-]+", "_", args.storm).strip(".") or "STORM"
        directory = {"track":"Tracks", "prognostic":"Prognostics", "ri":"RI_plots"}[product]
        path = args.output or Path(directory)/f"{stem}_{points[0].time:%Y%m%d%H%M}_{product}.png"
        export_figure(figure, path)
        print(f"Saved: {path}")
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    finally:
        if figure is not None:
            plt.close(figure)
        plt.close("all")


def track_main(argv=None):
    return _run("track", argv)


def prognostic_main(argv=None):
    return _run("prognostic", argv)


def ri_main(argv=None):
    return _run("ri", argv)


def gui_main():
    from cycloneaid.launcher import main
    return main()
