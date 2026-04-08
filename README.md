# CycloneAid 🌀

**Tropical Cyclone Forecast Track & Intensity Analysis Suite**

CycloneAid (Alpha 0.8.0) is a comprehensive Python-based desktop application built for visualizing hurricane and typhoon forecasts. Created by Forecaster Zayed, the tool brings the power of programmatic map rendering and intensity plotting into an intuitive graphical interface. It bridges the gap between raw tracking data (CSV/GPX) and broadcast-ready graphics, generating detailed track maps, intensity prognostic charts, and real-time rapid intensification diagnostic plots, all on dark-mode cartography.

---

## ✦ Features ✦

### 🗺️ Storm Track Plot
Generate high-fidelity forecast track maps using `Cartopy`.
- Automated uncertainty cones and city overlays.
- Tropical cyclone intensity classifications with custom color coding.
- Dark-mode stylized cartography to highlight key weather features.

### 📊 Prognostic Chart
Visualize intensity timelines to track storm evolution.
- Auto-detected category changes and landfall events.
- Easy-to-read proximity analysis for nearby cities.

### ⚡ Rapid Intensification (RI)
Detailed dV/dt intensity change rate analysis.
- WMO RI threshold highlighting.
- Peak-event annotation on dark-mode time-series plots.

### 📋 Data Management
Interactive table built specifically for rapid data entry.
- Excel-like row management: insert, duplicate, reorder, and edit cells via dropdowns.
- Supports importing and exporting both CSV and GPX track files.

### 🎨 Export Presets
Switch easily between distinct styles for rendering output.
- **Forecaster Preset**: Deep dive technical labels and full metadata footprint.
- **Media Preset**: Clean, streamlined visualization ready for broadcast.

### ✅ Data Validation
Automatic QC checks keeping human errors at bay.
- Checks coordinate bounds, wind speed continuity, and time ordering.
- Classifies potential issues as hard errors or soft warnings.

---

## 🛠️ Installation

**1. Clone the repository:**
```bash
git clone https://github.com/your-username/cycloneaid.git
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
This toolkit is highly experimental (Alpha 0.8.0). Please verify outputs against official agency data (NHC, JTWC, JMA, PAGASA, etc.).

## 📝 License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
