# CycloneAid 🌀

**Tropical Cyclone Forecast Track & Intensity Analysis Suite**

CycloneAid (Alpha 0.9.1) is a comprehensive Python-based desktop application built for hurricane and typhoon forecasting. Created by Forecaster Zayed, the suite bridges the gap between raw tracking data and broadcast-ready graphics, featuring real-time interactive mapping and advanced spatial analysis.

---

## ✦ Features ✦

### 🗺️ Command Center Live Map (New in 0.9)
Interactive slippy map integrated directly into the data entry workflow.
- **Two-way Sync**: Table edits update map markers in real-time, and vice versa.
- **Right-Click Entry**: Add storm data points directly via the map interface.
- **Auto-Landfall**: Real-time detection using high-resolution land masks.
- **KML/KMZ Support**: Import spatial data directly from Google Earth and other GIS tools.

### 🗺️ Storm Track Plot
High-fidelity forecast track maps using `Cartopy`.
- Automated uncertainty cones and city proximity overlays.
- Tropical cyclone intensity classifications with standard color coding.
- **Spatial Indexing**: Lightning-fast city search using R-tree optimization.

### 📊 Prognostic Chart
Visualize intensity timelines and key storm lifecycle events.
- Auto-detected category changes and landfall timestamps.
- Integrated event table with nearest-city distance analysis.

### ⚡ Rapid Intensification (RI)
Detailed dV/dt intensity change rate analysis.
- WMO RI threshold highlighting (30kt / 24h).
- Peak-event annotation on dark-mode time-series plots.

### 📋 Data Management
Interactive table built specifically for rapid meteorological data entry.
- Excel-like row management: insert, duplicate, reorder, and edit cells via dropdowns.
- Supports importing and exporting CSV, GPX, and KML track files.

### 🎨 Export Presets
Switch easily between distinct styles for rendering output.
- **Forecaster Preset**: Deep dive technical labels and full metadata footprint.
- **Media Preset**: Clean, streamlined visualization ready for broadcast.

### ✅ Data Validation
Automatic QC checks keeping human errors at bay.
- Checks coordinate bounds, wind speed continuity, and time ordering.
- Classifies potential issues as hard errors or soft warnings.
- **Precision Masking**: Landfall verification using `global-land-mask`.

---

## 🛠️ Installation

**1. Clone the repository:**
```bash
git clone https://github.com/4caster-zay/cycloneaid.git
cd cycloneaid
```

**2. Create a virtual environment (recommended):**
```bash
python -m venv venv

# Windows
venv\Scripts\activate
# Mac / Linux
source venv/bin/activate
```

**3. Install dependencies:**
```bash
pip install -r requirements.txt
```
*Note: Due to geospatial boundaries and dependencies, `cartopy`, `shapely`, and `rtree` may require installing system level C-libraries if using older package managers.*

---

## 🚀 Usage

Launch the GUI application directly by running:

```bash
python storm_tracker_gui.py
```

The application relies on these specific scripts for modular plotting and functionality:
- `storm_tracker.py` : Handles Cartopy map projection, track plotting, and uncertainty circles.
- `storm_prognostic.py` : Generates intensity timescale charts.
- `storm_RI_plot.py` : Calculates pressure/wind differentials for Rapid Intensification plots.
- `export_preset.py` : Configures the visual outputs based on Forecaster/Media toggle.
- `validation.py` : Provides QC data validation logic.

Created exports are saved in the `Tracks/`, `Prognostics/`, and `RI_plots/` directories automatically.

## ⚠️ Disclaimer
**ALPHA — For testing and development only. Not for operational use.**
This toolkit is experimental (Alpha 0.9.1). Please verify outputs against official agency data (NHC, JTWC, JMA, PAGASA, etc.).

## 📝 License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
