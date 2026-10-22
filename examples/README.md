# TEST PALAU forecast fixture

The repository's [forecast.csv](../forecast.csv) and [sample.cycloneaid.json](sample.cycloneaid.json) contain the same **synthetic forecast**. The dates are fixed for testing; this is not a current advisory. Open the project file in CycloneAid to retain the TEST title, source, issue time, and wind averaging assumption in charts and PNG metadata. You can also choose **Project → Open sample** in the application.

The nominal issue time is **21 October 2026 at 00:00 UTC**, with 13 positions through **26 October at 00:00 UTC (T+120h)**. Sampling is every 6 hours initially, then every 12 hours, with all timestamps in UTC. Every row, including the initial analyzed position, was created for this test scenario. None represents an observation or a value interpolated by the software.

| Phase | Scenario behavior |
| --- | --- |
| T+0 to T+12h | A 30-kt depression starts at 7.3°N, 135.5°E, about 100 km east of Palau, and passes the island group while beginning to strengthen. |
| T+24 to T+48h | Offshore strengthening from 45 to 80 kt supplies an exact **35-kt / 24-hour** increase for RI testing. |
| T+60 to T+72h | Winds peak at 90 kt east of the Philippines, using the application's C2 classification. |
| T+84 to T+108h | The center crosses the eastern/central Philippines and weakens from 80 to 50 kt. |
| T+120h | The center is west of Mindoro at 12.8°N, 120.0°E, with modest recovery to 55 kt over water. |

Successive positions move about **13–18 km/h** along a smooth west-northwest course. The intensity profile assumes favorable offshore conditions, disruption during island crossings, and partial recovery over water. These are scenario design choices; no atmospheric analysis, numerical guidance, or forecast probabilities were used.

Winds are maximum sustained winds in **knots**, using **1-minute averaging** for this scenario. This convention is documented for JTWC data in the [NOAA-hosted Pacific ENSO Update, page 2](https://www.weather.gov/media/peac/PEU/PEU52.pdf). The sample itself is synthetic and has no agency source. Application labels TD/TS/STS/C1/C2 follow CycloneAid's documented thresholds rather than an agency classification system. The 35-kt increase exceeds the [NHC definition of RI](https://prod-west-nhc.woc.noaa.gov/aboutgloss.shtml#r), at least 30 kt over 24 hours.

Expected checks:

- Both files validate without coordinate, timestamp, classification, or motion warnings, and preserve the same 13 values on project round-trip.
- RI includes the exact T+24h to T+48h increase of 35 kt. The window starting at T+18h ends between forecast points and must be marked estimated. No result extends past T+120h.
- Full geography detects approximate crossings near Palau and across the Philippines, including crossings between offshore forecast points. Manual `landfall` flags are all false so derived events can be checked independently. Coastline interpolation may produce fractional timestamps; these are estimates, not precise forecasts of landfall.
- The track envelope ends at T+120h and retains its **legacy heuristic / uncalibrated** qualification. Charts retain the TEST PALAU label and synthetic source.
- The project starts **without a basemap**, allowing a first run without map downloads. Choose **Enable maps** above the workspace tabs, completing one-time setup if needed, to test basemaps, cities, and automatic coastline events. Those events are omitted while maps are disabled.

To generate all three full-geography test graphics from a prepared cache:

```bash
.venv/bin/python tools/smoke_geography.py --cache /path/to/cartopy-cache --output .cache/test-outputs/palau
```

Add `--download` only when populating the cache while connected. A single plausible fixture tests software behavior; broader historical verification and forecaster review remain release requirements.
