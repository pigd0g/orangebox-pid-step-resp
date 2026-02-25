Repository: orangebox-pid-step-resp — Copilot instructions for coding agents

Purpose

- Help AI coding agents become productive quickly by calling out the project's architecture, key entry points, developer workflows, and repo-specific conventions.

Big picture

- This project analyzes blackbox (BBL) flight logs to compute PID step responses. Main responsibilities are:
  - `orangebox/` — third-party/packaged Blackbox parsing helpers used to read frames and headers.
  - `pid_step_response/` — core analysis library: `parser.py` (extracts headers/frames/PID params), `analyzer.py` (orchestrates per-log analysis), `calculator.py` (signal processing and metrics), `models.py` (data classes), and `plotter.py` (visualization).
  - `example_step_response.py` — example CLI that runs analysis and produces plots and a consolidated JSON export in `logs/analysis`.

Key data flows and boundaries

- Parsing: `pid_step_response.parser.parse_bbl_file()` returns a `LogData` containing `headers` and numeric arrays.
- Analysis: `StepResponseAnalyzer.analyze()` consumes `LogData` and produces `StepResponseResult` (per-log), which contains `AxisResult` objects holding `time_ms`, `step_response`, and computed metrics.
- Export: `StepResponseResult.to_dict()` serializes results for JSON export; `example_step_response.py` writes `<stem>_analysis.json` into `logs/analysis`.

Important behaviors & conventions

- Headers vs results: raw `headers` are available in `LogData` during parsing and are now copied into `StepResponseResult.headers` during analysis — preserve this propagation when changing parsing/analysis.
- PID mapping: parser supports multiple firmware styles (Betaflight-style arrays and Rotorflight). Rotorflight `rollPID`/`pitchPID`/`yawPID` arrays may contain 5 elements mapped to P,I,D,FF,Boost. `d_min` is optional and often absent for Rotorflight — `PIDParams` includes `boost` and `d_min`.
- Numpy arrays: internal models use `numpy.ndarray`. Serializers convert arrays to Python lists via `_json_safe()` in `models.py`. When editing models or serializers, ensure numpy scalars/arrays are converted to JSON-native types.

Developer workflows (commands)

- Run unit tests (uses unittest in this repo):
  - python -m unittest
  - or run specific tests: `python -m unittest tests.test_step_response.TestModels`
- Run the example (requires dependencies):
  - pip install -r requirements.txt
  - python example_step_response.py logs/<your.bbl>
  - Output: plots and `logs/analysis/<stem>_analysis.json`

Dependencies and environment

- Key runtime libraries: `numpy`, `matplotlib` (for plotting), and `orangebox` for BBL parsing. Ensure these are present in the Python environment before running examples or tests.

Patterns to follow when coding

- Preserve existing public model shapes (`LogData`, `StepResponseResult`, `AxisResult`, `PIDParams`) — callers (example, tests) expect these fields.
- When adding serialization, always use `_json_safe()`-style conversion for numpy arrays and numpy scalar types.
- When changing parsing rules, add tests that exercise both Betaflight and Rotorflight header formats (see new tests in `tests/test_step_response.py`).

Files to inspect first when troubleshooting

- `pid_step_response/parser.py` — header extraction, Rotorflight detection logic
- `pid_step_response/analyzer.py` — how `LogData` is converted to `StepResponseResult`
- `pid_step_response/models.py` — canonical data shapes and `to_dict()` helpers
- `pid_step_response/calculator.py` — contains signal processing, smoothing, deconvolution, and metric computation
- `example_step_response.py` — shows typical integration and outputs JSON + plots

When making changes

- Keep changes minimal and local: prefer adding `to_dict()` or small fields to models rather than changing function signatures used across multiple files.
- Add unit tests under `tests/` for any parsing or output behavior you modify.
- Run `python -m unittest` locally (requires dependencies) before opening PR.

If you need clarification

- Ask which example logs (Betaflight vs Rotorflight) to validate against, and whether raw setpoint/gyro traces should be included in JSON exports (current export contains step-response arrays + summary metrics only).

Please review and flag anything missing or unclear; I will iterate the file per your feedback.
