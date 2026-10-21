import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import timedelta

# ─── Category Colors ───
category_colors = {
    'L':   '#989898',  # Gray for Low pressure systems
    'TD':  '#5ebaff',  # Light blue
    'TS':  '#00faf4',  # Cyan
    'STS': '#00ef00',  # Green
    'C1':  '#ffffcc',  # Light yellow
    'C2':  '#ffe775',  # Yellow
    'C3':  '#ffc140',  # Orange
    'C4':  '#ff8f20',  # Dark orange
    'C5':  '#ff6060',  # Red
    'EX':  '#c07898',  # Mauve/purple for post-tropical systems
    'SD':  '#2d5d7e',  # Darker blue for subtropical depression
    'SS':  '#007d7a',  # Darker cyan for subtropical storm
}

from cycloneaid.model import INTENSITY_THRESHOLDS, utc_timestamp
from cycloneaid.geography import find_nearest_city
from validation import validate_forecast_points
CATEGORY_THRESHOLDS = {label: threshold*1.852 for threshold, label in INTENSITY_THRESHOLDS}

def plot_storm_prognostic(forecast_points, storm_name="STORM", issue_time=None, *, geography_mode="full", landfall_events=()):
    """
    Create a prognostic visualization showing storm intensity and key developments over time.
    Args:
        forecast_points (list of ForecastPoint): The forecast points to plot.
        storm_name (str): Name of the storm.
        issue_time (datetime): Issue time of the forecast.
    Returns:
        matplotlib.figure.Figure: The generated matplotlib figure.
    """
    if not forecast_points:
        raise ValueError("No forecast points provided")
        
    if not issue_time:
        issue_time = forecast_points[0].time

    result = validate_forecast_points(forecast_points)
    if result.has_errors():
        raise ValueError("\n".join(result.hard_errors))
    issue_time = utc_timestamp(issue_time)
    if pd.isna(issue_time) or issue_time > forecast_points[0].time:
        raise ValueError("Issue time must be valid and no later than the first point")

    # Dark-mode
    plt.style.use('dark_background')
    fig = plt.figure(figsize=(12, 8))

    # Create a grid with more space for the intensity chart and a dedicated info panel
    gs = fig.add_gridspec(2, 1, height_ratios=[2, 0.8], hspace=0.4)

    # 1. Enhanced Intensity Timeline (top)
    ax1 = fig.add_subplot(gs[0])
    
    # Extract data efficiently
    times = [pt.time for pt in forecast_points]
    winds = [pt.wind_kt * 1.852 for pt in forecast_points]  # Convert to km/h
    intensities = [pt.intensity_class for pt in forecast_points]
    storm_types = [pt.storm_type for pt in forecast_points]
    
    # Plot intensity line with gradient
    ax1.fill_between(times, winds, alpha=0.2, color='white')
    ax1.plot(times, winds, '-', color='white', linewidth=2)
    
    # Plot points and labels efficiently
    for t, w, intensity, storm_type in zip(times, winds, intensities, storm_types):
        color = category_colors.get(intensity, 'white')
        label = intensity
        if storm_type != 'Tropical':
            label += f" ({storm_type[:4]})"
        
        ax1.plot(t, w, 'o', color=color, markeredgecolor='white', 
                markeredgewidth=1.5, markersize=10)
        ax1.annotate(label, (t, w), xytext=(0, 10),
                    textcoords='offset points', ha='center', va='bottom',
                    color=color, fontweight='bold')

    # Add landfall markers efficiently
    for pt in forecast_points:
        if pt.landfall:
            wind_kmh = pt.wind_kt * 1.852
            ax1.plot(pt.time, wind_kmh, 'X', color='red', 
                    markersize=15, markeredgecolor='white', markeredgewidth=2)
            ax1.axvline(pt.time, color='red', linestyle='--', alpha=0.3)
            ax1.annotate('LANDFALL', (pt.time, wind_kmh),
                        xytext=(0, -20), textcoords='offset points',
                        ha='center', va='top', color='red', fontweight='bold',
                        bbox=dict(facecolor='#2f2f2f', edgecolor='red', alpha=0.7))

    # Customize intensity plot
    ax1.set_title('Storm Intensity Forecast', pad=10, fontsize=14)
    ax1.set_ylabel('Wind Speed (km/h)', fontsize=10)
    ax1.grid(True, alpha=0.2)
    
    # Add standard lead time indicators
    standard_leadtimes = [0, 12, 24, 36, 48, 72, 96, 120]
    for leadtime in standard_leadtimes:
        leadtime_time = issue_time + timedelta(hours=leadtime)
        if leadtime_time <= times[-1]:
            ax1.axvline(leadtime_time, color='white', linestyle=':', alpha=0.15)
            ax1.text(leadtime_time, 300, f'T+{leadtime}h',
                    color='white', alpha=0.6, fontsize=8,
                    ha='center', va='center',
                    bbox=dict(facecolor='#2f2f2f', alpha=0.3, pad=1))
    
    # Format x-axis dates
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d\n%HZ'))
    plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45, ha='right')

    # Intensity class bands
    filtered_cats = {i: s for i, s in CATEGORY_THRESHOLDS.items() 
                    if i in ['TD', 'TS', 'STS', 'C1', 'C2', 'C3', 'C4', 'C5']}
    sorted_cats = sorted(filtered_cats.items(), key=lambda x: x[1])
    
    for j, (intensity, lower) in enumerate(sorted_cats):
        upper = sorted_cats[j+1][1] if j+1 < len(sorted_cats) else max(300, max(winds)*1.1)
        color = category_colors.get(intensity, 'gray')
        ax1.axhspan(lower, upper, color=color, alpha=.04)
        ax1.axhline(lower, color=color, linestyle='--', alpha=.4)
        ax1.text(times[-1], (lower+upper)/2, intensity, color=color, fontsize=8)

    # 2. Information Panel (bottom)
    ax2 = fig.add_subplot(gs[1])
    ax2.axis('off')
    
    # Prepare table data efficiently
    table_data = []
    table_colors = []
    
    # Add events
    for i, pt in enumerate(forecast_points):
        is_event = False
        event_name = ""
        
        if i == 0:
            is_event = True
            event_name = "Initial Conditions"
        else:
            prev_pt = forecast_points[i-1]
            if pt.intensity_class != prev_pt.intensity_class or pt.storm_type != prev_pt.storm_type:
                is_event = True
                hours = (pt.time - issue_time).total_seconds()/3600
                event_name = f"Intensity Change (T+{hours}h)"
            if pt.landfall:
                is_event = True
                hours = (pt.time - issue_time).total_seconds()/3600
                event_name = f"Landfall (T+{hours}h)"
                location_color = 'red'
        
        if is_event:
            nearest = find_nearest_city(pt.lon, pt.lat) if geography_mode == 'full' else None
            location_str = f"{nearest[0]} ({nearest[3]:.0f}km)" if nearest else ""
            label = pt.intensity_class
            if pt.storm_type != 'Tropical':
                label += f" ({pt.storm_type[:4]})"
            
            table_data.append([
                f"{pt.time:%Y-%m-%d %H:%MZ}",
                event_name,
                label,
                f"{int(pt.wind_kt * 1.852)} km/h",
                location_str
            ])
            
            row_colors = ['white'] * 5
            row_colors[1] = 'red' if 'Landfall' in event_name else 'white'
            row_colors[2] = category_colors.get(pt.intensity_class, 'white')
            row_colors[4] = 'red' if 'Landfall' in event_name else 'white'
            table_colors.append(row_colors)

    for event in landfall_events:
        ax1.plot(event.time, event.wind_kt*1.852, 'X', color='red', markersize=10)
        ax1.axvline(event.time, color='red', linestyle=':', alpha=.4)
        nearest = find_nearest_city(event.lon, event.lat) if geography_mode == 'full' else None
        location = f"{nearest[0]} ({nearest[3]:.0f}km)" if nearest else f"{event.lat:.2f}N {event.lon:.2f}E"
        table_data.append([f"{event.time:%Y-%m-%d %H:%MZ}", "Approx. landfall", "—",
                           f"{event.wind_kt*1.852:.0f} km/h", location])
        table_colors.append(['red']*5)
    if landfall_events:
        pairs = sorted(zip(table_data, table_colors), key=lambda pair: pair[0][0])
        table_data, table_colors = map(list, zip(*pairs))

    figure_height = max(8, 6 + len(table_data)*.25)
    fig.set_size_inches(12, figure_height)
    gs.set_height_ratios([3, max(1.2, len(table_data)*.17)])
    fig.subplots_adjust(top=.86, bottom=.14, left=.08, right=.97, hspace=.85)
    table = ax2.table(
        cellText=table_data,
        colLabels=['Time (UTC)', 'Event', 'Category', 'Intensity', 'Location'],
        loc='center', cellLoc='left',
        colWidths=[0.2, 0.2, 0.15, 0.15, 0.3],
        bbox=[0, 0, 1, 1]
    )
    
    table.auto_set_font_size(False)
    table.set_fontsize(8)
    
    for i in range(5):
        table[0, i].set_facecolor('#2f2f2f')
        table[0, i].set_text_props(color='white', weight='bold')
        table[0, i].set_height(0.15)
    
    for i in range(len(table_data)):
        for j in range(5):
            cell = table[i + 1, j]
            cell.set_facecolor('#1f1f1f')
            cell.set_text_props(color=table_colors[i][j])
            cell.set_height(0.12)
            cell.set_edgecolor('#3f3f3f')

    plt.suptitle(f"{storm_name} Forecast Prognostic — Issued {issue_time:%Y-%m-%d %H:%MZ}",
                color='white', fontsize=16, y=0.98)
    
    from cycloneaid.metadata import __version__
    note = f"CycloneAid {__version__} | Landfall times are approximate coastline intersections"
    if geography_mode == "degraded":
        note += " | DEGRADED: cities and automatic landfall unavailable"
    fig.text(.5, .05, note, ha='center', fontsize=7)
    return fig

if __name__ == '__main__':
    from cycloneaid.cli import prognostic_main
    raise SystemExit(prognostic_main())
