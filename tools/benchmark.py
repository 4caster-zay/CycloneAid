"""Repeated diagnostic medians against a Git ref, with identical synthetic inputs.

Basemaps are disabled to separate computation from downloads. Use the review
Python environment (which also has SciPy for the historical code). This does
not represent end-to-end GUI or cold-start performance.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

ROOT=Path(__file__).resolve().parents[1]


def worker(mode, root, iterations, forecast=None):
    sys.path.insert(0,str(root))
    import statistics
    import time
    import random
    from unittest.mock import patch
    import pandas as pd
    import matplotlib.pyplot as plt
    from cartopy.mpl.geoaxes import GeoAxes
    from rtree.index import Index
    if mode=='baseline':
        import storm_tracker_gui as gui
        tracker=gui.storm_tracker
    else:
        import storm_tracker as tracker
        import cycloneaid.geography as geography
        from cycloneaid.session import ForecastSession, ForecastRow, validate_session, SessionSettings
    from export_preset import MEDIA_PRESET
    rng=random.Random(42)
    cities=[(rng.uniform(100,150),rng.uniform(0,40),f'City {i}',1000,False) for i in range(8000)]
    idx=Index()
    for i,(lon,lat,*_) in enumerate(cities):
        idx.insert(i,(lon,lat,lon,lat))
    queries=[(rng.uniform(110,140),rng.uniform(5,35)) for _ in range(100)]
    sample=pd.read_csv(forecast or root/'forecast.csv',comment='#')
    points=[tracker.ForecastPoint(**row._asdict()) for row in sample.itertuples(index=False)]
    context=MEDIA_PRESET.build_render_context({'issue_time':points[0].time})
    rows=[(f'{pd.Timestamp("2026-01-01T00:00Z")+pd.Timedelta(hours=i*6)}','0','10','125','40','False','Tropical','TS','False') for i in range(1000)]
    class Tree:
        def get_children(self):
            return range(len(rows))
        def item(self,index,option=None,**kwargs):
            return rows[index] if option=='values' else None
    def city_queries():
        for lon,lat in queries:
            if mode=='baseline':
                tracker.find_nearest_city(lon,lat,cities)
            else:
                geography.find_nearest_city(lon,lat,cities,city_index=idx)
    def validation():
        if mode=='baseline':
            gui.DataEntryScreen._is_table_valid(type('Screen',(),{'tree':Tree()})())
        else:
            validate_session(session)
    if mode!='baseline':
        session=ForecastSession(tuple(ForecastRow(tuple(row)) for row in rows),SessionSettings())
    def preview():
        kwargs={} if mode=='baseline' else {'geography_mode':'full'}
        figure=tracker.plot_storm_track(points,storm_name='BENCHMARK',render_context=context,**kwargs)
        plt.close(figure)
    def measure(function):
        function()  # Warm library and parsed-row caches.
        samples=[]
        for _ in range(iterations):
            start=time.perf_counter()
            function()
            samples.append((time.perf_counter()-start)*1000)
        return round(statistics.median(samples),2)
    patches=[patch.object(GeoAxes,'add_feature'),patch.object(GeoAxes,'coastlines'),
             patch.object(tracker,'_get_ph_provinces',return_value=[])]
    if mode=='baseline':
        patches.append(patch.object(tracker,'_get_city_data',return_value=(cities,idx)))
    else:
        patches.append(patch.object(geography,'get_city_data',return_value=(cities,idx)))
    for item in patches:
        item.start()
    try:
        print(json.dumps({'city_queries_100_ms':measure(city_queries),
                          'validate_1000_rows_ms':measure(validation),
                          'track_preview_ms':measure(preview)}))
    finally:
        for item in reversed(patches):
            item.stop()
        plt.close('all')
        idx.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline',default='592ca1f')
    parser.add_argument('--iterations',type=int,default=5)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--worker',choices=('baseline','candidate'))
    parser.add_argument('--module-root',type=Path)
    parser.add_argument('--forecast',type=Path,help=argparse.SUPPRESS)
    args=parser.parse_args()
    if args.worker:
        worker(args.worker,args.module_root,args.iterations,args.forecast)
        return
    if args.iterations<1:
        parser.error('iterations must be positive')
    with TemporaryDirectory(prefix='cycloneaid-benchmark-') as directory:
        temporary=Path(directory)
        baseline=temporary/'baseline'
        baseline.mkdir()
        for name in ('storm_tracker.py','storm_tracker_gui.py','storm_prognostic.py','storm_RI_plot.py',
                     'validation.py','export_preset.py','forecast.csv'):
            result=subprocess.run(['git','show',f'{args.baseline}:{name}'],cwd=ROOT,check=True,capture_output=True)
            (baseline/name).write_bytes(result.stdout)
        results={'baseline_ref':args.baseline,'iterations':args.iterations,'measurements':{}}
        for mode,root in (('baseline',baseline),('candidate',ROOT)):
            work=temporary/mode/'outputs'
            work.mkdir(parents=True)
            result=subprocess.run([sys.executable,str(Path(__file__).resolve()),'--worker',mode,
                                   '--module-root',str(root),'--iterations',str(args.iterations),
                                   '--forecast',str(baseline/'forecast.csv')],
                                  cwd=work,env=dict(os.environ,MPLBACKEND='Agg',PYTHONDONTWRITEBYTECODE='1'),
                                  capture_output=True,text=True)
            if result.returncode:
                raise SystemExit(f'{mode} benchmark failed:\n{result.stderr}')
            results['measurements'][mode]=json.loads(result.stdout)
        print(json.dumps(results,indent=2))
        if args.output:
            args.output.write_text(json.dumps(results,indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':
    main()
