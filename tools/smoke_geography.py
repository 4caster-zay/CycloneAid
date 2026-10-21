"""Explicit full-geography release smoke check; download only with --download."""
import argparse
from dataclasses import replace
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    from cycloneaid.launcher import configure_runtime
    configure_runtime()
    parser=argparse.ArgumentParser()
    parser.add_argument('--cache',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--download',action='store_true')
    args=parser.parse_args()
    import cartopy
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    cartopy.config['data_dir']=args.cache
    cartopy.config['pre_existing_data_dir']=args.cache
    from cycloneaid.geography import ensure_geography, geography_readiness
    from cycloneaid.imports import read_forecast
    from cycloneaid.session import load_project, validate_session
    from cycloneaid.rendering import RenderRequest, build_figure, export_figure
    if args.download:
        ensure_geography()
    if geography_readiness():
        raise SystemExit('Missing cached geography. Run again with --download while connected.')
    root=Path(__file__).resolve().parents[1]
    points,_=read_forecast(root/'forecast.csv')
    session=load_project(root/'examples/sample.cycloneaid.json')
    project_points,result=validate_session(session,regional=True)
    if result.has_errors() or tuple(points)!=project_points:
        raise SystemExit('The sample project must validate and match forecast.csv.')
    session=replace(session,settings=replace(session.settings,geography_mode='full'))
    # A fresh process with network blocked verifies warm on-disk cache readiness.
    with patch('cartopy.io.Downloader._urlopen',side_effect=AssertionError('Unexpected network request')):
        for product in ('track','prognostic','ri'):
            figure=build_figure(RenderRequest.from_session(session,product))
            export_figure(figure,args.output/f'{product}.png',dpi=120)
            plt.close(figure)
            print(f'{product}: full-geography offline render passed',flush=True)


if __name__=='__main__':
    main()
