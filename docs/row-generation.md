# Generate forecast rows

Open the data-entry screen and choose **Generate rows…** beside **Add**. Enter a start date and time in UTC, an interval in hours, and a horizon in hours. The interval defaults to 6 and the horizon to 120. An empty table leaves the start blank; an existing table suggests its final timestamp plus the selected interval.

The preview updates as you edit the inputs, showing the first timestamp, final timestamp, and number of rows. Inspect it, then choose **Append rows** to apply. Invalid inputs disable appending and display an explanation. Cancel leaves the forecast unchanged.

The range includes the start and final timestamp: a 120-hour horizon at six-hour intervals creates 21 rows. The horizon must be an exact multiple of the interval; both must be positive and finite. Fractional hours are supported. Each batch is limited to 1,000 rows to keep the desktop responsive.

Use an ISO date with a time, such as `2026-10-22 00:00` or `2026-10-22T00:00Z`. A timezone-free value is explicitly interpreted as UTC in this dialog; a supplied timezone must be UTC. Existing rows must have valid, strictly increasing timestamps, and the new start must follow the final existing timestamp. Fix timestamp errors before appending; incomplete coordinates or winds do not prevent generation.

Only timestamps are generated. Coordinates and wind values remain blank, while categorical and boolean fields use the normal new-row defaults. Enter and validate the forecast values before previewing or exporting charts. Generating times does not estimate a track or wind forecast.

The addition is one undoable action. Existing rows and session settings are preserved, existing chart previews become stale, and normal project saving and recovery apply. Project files retain `time_origin="generated"`; forecast values are not labeled interpolated merely because timestamps were generated. Project schema version 1 and existing CSV/CLI workflows remain supported.
