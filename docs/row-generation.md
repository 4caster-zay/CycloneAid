# Generate forecast rows

Choose **Generate rows…** beside **Add** in the forecast editor. Enter a start date and time in UTC, an interval in hours, and a horizon in hours. The interval defaults to 6 and the horizon to 120. For an empty table, enter the start time yourself. For an existing forecast, the dialog suggests the final timestamp plus the selected interval.

The preview updates as you type, showing the first timestamp, final timestamp, and row count. Review it, then choose **Append rows**. If an input is invalid, the dialog explains the problem and disables appending. **Cancel** leaves the forecast unchanged.

The range includes the start and final timestamp: a 120-hour horizon at six-hour intervals creates 21 rows. The horizon must be an exact multiple of the interval; both must be positive and finite. Fractional hours are supported. Each batch is limited to 1,000 rows to keep the desktop responsive.

Use an ISO date and time, such as `2026-10-22 00:00` or `2026-10-22T00:00Z`. This dialog treats dates without a timezone as UTC; a supplied timezone must also be UTC. Existing timestamps must be valid and strictly increasing, and the new start must follow the final existing timestamp. Fix any timestamp errors before appending. You can generate rows while coordinates or winds are still incomplete.

Only timestamps are generated. Coordinates and wind values remain blank, while categorical and boolean fields use the normal new-row defaults. Enter and validate the forecast values before previewing or exporting charts. Generating times does not estimate a track or wind forecast.

The batch is added as one undoable action. Existing rows and session settings are preserved, and existing chart previews are marked stale. Save and recovery work as usual. Project files record `time_origin="generated"` for these timestamps while keeping forecast-value provenance separate. Project schema version 1 and existing CSV/CLI commands remain supported.
