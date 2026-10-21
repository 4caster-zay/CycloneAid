# Diagnostic performance measurements

Measured 21 October 2026 against review commit `592ca1f`, with five measured runs per operation after one warm-up. Both versions used the same Python 3.12.14 environment and deterministic synthetic inputs.

These measurements predate the TEST PALAU fixture and later UI refinements. The benchmark now explicitly shares the reviewed commit's forecast CSV between both versions, so changing the bundled sample cannot change one side of a comparison.

| Operation | Reviewed code median | 0.10.0a1 median | Ratio |
|---|---:|---:|---:|
| 100 nearest-city queries over 8,000 cities | 1,720.47 ms | 65.28 ms | 26.4× |
| Validate 1,000 table/session rows | 1,053.16 ms | 22.98 ms | 45.8× |
| Track builder's preview path | 3,307.92 ms | 145.46 ms | 22.7× |

The old city caller scans all cities; the candidate uses a corrected R-tree candidate search plus exact distance filtering. Index/exhaustive equivalence is independently covered by regression tests, including high latitudes and the antimeridian.

The old row path reparses Treeview strings; the candidate validates the session using cached parsed rows and additionally checks shared domain rules. GUI tests verify that one coordinate edit reuses markers and preserves the viewport, including a 1,000-row test double.

The historical track builder encodes a 300-DPI PNG during preview construction. The candidate builder performs no export. These builder timings **exclude candidate worker serialization, canvas painting, real basemaps, network access, and user interaction**. They demonstrate removed work, rather than end-to-end GUI latency. Track geometry and metadata also reflect correctness fixes, so pixels differ between versions.

Command used:

```bash
python tools/benchmark.py --baseline 592ca1f --iterations 5 --output /tmp/cycloneaid-benchmark-results.json
```

The historical source imports SciPy, so the comparison environment must include it. Current application dependencies no longer need SciPy. Timings are single-environment diagnostics, not performance guarantees or scientific skill measurements.
