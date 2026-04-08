"""
Export preset system for CycloneAid.

Presets control rendering only; they never modify underlying storm data.
Plotting functions consume RenderContext, not preset names.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

# Named layers used by track plotting. Each layer is toggleable via RenderContext.
LAYER_TRACK_LINE = "track_line"
LAYER_FORECAST_CONE = "forecast_cone"
LAYER_TRACK_POINTS = "track_points"
LAYER_CITY_LABELS = "city_labels"
LAYER_LANDFALL_MARKERS = "landfall_markers"
LAYER_LEAD_TIME_ANNOTATIONS = "lead_time_annotations"
LAYER_VALIDATION_WARNINGS = "validation_warnings"
LAYER_METADATA_FOOTER = "metadata_footer"

ALL_LAYERS = {
    LAYER_TRACK_LINE,
    LAYER_FORECAST_CONE,
    LAYER_TRACK_POINTS,
    LAYER_CITY_LABELS,
    LAYER_LANDFALL_MARKERS,
    LAYER_LEAD_TIME_ANNOTATIONS,
    LAYER_VALIDATION_WARNINGS,
    LAYER_METADATA_FOOTER,
}


@dataclass
class RenderContext:
    """
    Context controlling layer visibility, styling, and metadata for a single render.
    Built by a preset from storm data; plotting code uses only this context.
    """
    # Layer visibility
    layer_visible: Dict[str, bool] = field(default_factory=dict)

    # Styling
    track_line_style: str = "--"
    track_line_opacity: float = 1.0
    interpolated_line_opacity: float = 0.4
    track_point_opacity_interpolated: float = 0.5
    cone_opacity: float = 1.0

    # Annotations
    show_lead_time_annotations: bool = True
    show_error_radii_labels: bool = True
    label_density: str = "full"  # "full" | "simplified"
    # Simplified: intensity class only (e.g. TS, C3). Full: composite (e.g. C3 (Subt))

    # Cities
    city_tier: str = "all"  # "all" | "major_only"

    # Legend
    show_legend: bool = True
    show_intensity_legend: bool = True
    show_storm_type_legend: bool = True
    show_city_legend: bool = True
    show_interpolated_legend: bool = True

    # Metadata footer: list of lines to display (order preserved)
    metadata_lines: List[str] = field(default_factory=list)

    # Cached storm data for context (read-only usage)
    has_interpolated: bool = False
    forecaster_confidence: str = "Moderate"
    issue_time: Optional[Any] = None
    valid_until: Optional[Any] = None
    validation_warning_count: int = 0

    def is_layer_visible(self, layer_name: str) -> bool:
        return self.layer_visible.get(layer_name, True)

    def use_simplified_labels(self) -> bool:
        return self.label_density == "simplified"

    def major_cities_only(self) -> bool:
        return self.city_tier == "major_only"


class ExportPreset:
    """
    Defines name, audience, allowed layers, and rules for rendering.
    Presets never modify storm data — only control rendering.
    """

    def __init__(
        self,
        name: str,
        audience: str,
        allowed_layers: Set[str],
        styling_rules: Dict[str, Any],
        annotation_rules: Dict[str, Any],
        metadata_rules: Dict[str, Any],
    ):
        self.name = name
        self.audience = audience
        self.allowed_layers = allowed_layers
        self.styling_rules = styling_rules
        self.annotation_rules = annotation_rules
        self.metadata_rules = metadata_rules

    def build_render_context(self, storm_data: Dict[str, Any]) -> RenderContext:
        """
        Build a RenderContext from storm data and this preset's rules.
        storm_data is a dict with keys such as: forecast_points, issue_time, has_interpolated,
        forecaster_confidence, validation_result, etc.
        """
        layer_visible = {
            layer: layer in self.allowed_layers for layer in ALL_LAYERS
        }

        ctx = RenderContext(
            layer_visible=layer_visible,
            has_interpolated=storm_data.get("has_interpolated", False),
            forecaster_confidence=storm_data.get("forecaster_confidence", "Moderate"),
            issue_time=storm_data.get("issue_time"),
            valid_until=storm_data.get("valid_until"),
            validation_warning_count=storm_data.get("validation_warning_count", 0),
        )

        # Apply styling rules
        ctx.track_line_style = self.styling_rules.get("track_line_style", "--")
        ctx.track_line_opacity = self.styling_rules.get("track_line_opacity", 1.0)
        ctx.interpolated_line_opacity = self.styling_rules.get("interpolated_line_opacity", 0.4)
        ctx.track_point_opacity_interpolated = self.styling_rules.get(
            "track_point_opacity_interpolated", 0.5
        )
        ctx.cone_opacity = self.styling_rules.get("cone_opacity", 1.0)

        # Apply annotation rules
        ctx.show_lead_time_annotations = self.annotation_rules.get(
            "show_lead_time_annotations", True
        )
        ctx.show_error_radii_labels = self.annotation_rules.get(
            "show_error_radii_labels", True
        )
        ctx.label_density = self.annotation_rules.get("label_density", "full")
        ctx.city_tier = self.annotation_rules.get("city_tier", "all")

        # Apply legend rules
        ctx.show_legend = self.annotation_rules.get("show_legend", True)
        ctx.show_intensity_legend = self.annotation_rules.get("show_intensity_legend", True)
        ctx.show_storm_type_legend = self.annotation_rules.get("show_storm_type_legend", True)
        ctx.show_city_legend = self.annotation_rules.get("show_city_legend", True)
        ctx.show_interpolated_legend = self.annotation_rules.get(
            "show_interpolated_legend", True
        )

        # Build metadata footer from metadata_rules
        ctx.metadata_lines = self._build_metadata_lines(storm_data)

        return ctx

    def _build_metadata_lines(self, storm_data: Dict[str, Any]) -> List[str]:
        lines = []
        rules = self.metadata_rules
        issue_time = storm_data.get("issue_time")
        valid_until = storm_data.get("valid_until")
        has_interpolated = storm_data.get("has_interpolated", False)
        validation_warning_count = storm_data.get("validation_warning_count", 0)
        forecaster_confidence = storm_data.get("forecaster_confidence", "Moderate")

        if rules.get("include_generation_time", True):
            lines.append(f"Generated: {datetime.utcnow():%Y-%m-%d %H%MZ} UTC")

        if rules.get("include_forecast_disclaimer", False):
            lines.append("Forecast track subject to change.")

        if rules.get("include_forecaster_confidence", True):
            lines.append(f"Forecaster Confidence: {forecaster_confidence}")

        if rules.get("include_version", True):
            try:
                import storm_tracker_gui
                version = storm_tracker_gui.VERSION
            except (ImportError, AttributeError):
                version = "Alpha 0.8.0"
            lines.append(f"CycloneAid {version}")

        if rules.get("include_valid_range", True) and issue_time is not None and valid_until is not None:
            try:
                issue_str = issue_time.strftime("%Y-%m-%d %H00Z")
                valid_str = valid_until.strftime("%Y-%m-%d %H00Z")
                lines.append(f"Valid: {issue_str} to {valid_str}")
            except Exception:
                pass

        if rules.get("include_interpolation_warning", True) and has_interpolated:
            lines.append("This track contains interpolated points derived from GPX data.")

        if rules.get("include_validation_warnings", True) and validation_warning_count > 0:
            lines.append(f"{validation_warning_count} validation warning(s)")

        return lines


# --- Preset definitions ---

FORECASTER_PRESET = ExportPreset(
    name="Forecaster",
    audience="meteorologists / analysts",
    allowed_layers=ALL_LAYERS,
    styling_rules={
        "track_line_style": "--",
        "track_line_opacity": 1.0,
        "interpolated_line_opacity": 0.4,
        "track_point_opacity_interpolated": 0.5,
        "cone_opacity": 1.0,
    },
    annotation_rules={
        "show_lead_time_annotations": True,
        "show_error_radii_labels": True,
        "label_density": "full",
        "city_tier": "all",
        "show_legend": True,
        "show_intensity_legend": True,
        "show_storm_type_legend": True,
        "show_city_legend": True,
        "show_interpolated_legend": True,
    },
    metadata_rules={
        "include_version": True,
        "include_generation_time": True,
        "include_forecaster_confidence": True,
        "include_valid_range": True,
        "include_interpolation_warning": True,
        "include_validation_warnings": True,
        "include_forecast_disclaimer": False,
    },
)

MEDIA_PRESET = ExportPreset(
    name="Media",
    audience="public / journalists",
    allowed_layers={
        LAYER_TRACK_LINE,
        LAYER_FORECAST_CONE,
        LAYER_TRACK_POINTS,
        LAYER_CITY_LABELS,
        LAYER_LANDFALL_MARKERS,
        LAYER_METADATA_FOOTER,
        # Omit: LAYER_LEAD_TIME_ANNOTATIONS, LAYER_VALIDATION_WARNINGS
    },
    styling_rules={
        "track_line_style": "--",
        "track_line_opacity": 1.0,
        "interpolated_line_opacity": 0.4,
        "track_point_opacity_interpolated": 0.5,
        "cone_opacity": 1.0,
    },
    annotation_rules={
        "show_lead_time_annotations": False,
        "show_error_radii_labels": False,
        "label_density": "simplified",
        "city_tier": "major_only",
        "show_legend": True,
        "show_intensity_legend": True,
        "show_storm_type_legend": False,
        "show_city_legend": False,
        "show_interpolated_legend": False,
    },
    metadata_rules={
        "include_version": False,
        "include_generation_time": True,
        "include_forecaster_confidence": True,
        "include_valid_range": False,
        "include_interpolation_warning": False,
        "include_validation_warnings": False,
        "include_forecast_disclaimer": True,
    },
)

PRESETS_BY_NAME = {
    "Forecaster": FORECASTER_PRESET,
    "Media": MEDIA_PRESET,
}


def get_preset(name: str) -> ExportPreset:
    if name not in PRESETS_BY_NAME:
        return FORECASTER_PRESET
    return PRESETS_BY_NAME[name]
