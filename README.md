# Orangebox PID Step Response GUI (Rotorflight)

[![PyPI version](https://badge.fury.io/py/orangebox.svg)](https://badge.fury.io/py/orangebox) 
[![Documentation Status](https://readthedocs.org/projects/orangebox/badge/?version=latest)](https://orangebox.readthedocs.io/en/latest/?badge=latest)

A Rotorflight-focused GUI workflow for tuning PID gains from blackbox step response analysis.

This project combines the orangebox BBL parser with PID step response analysis (inspired by [PIDtoolbox](https://github.com/bw1129/PIDtoolbox)). The recommended workflow is to run `gui_step_response.py`, analyze `.bbl` logs, and tune Roll/Pitch/Yaw gains based on measured rise time, overshoot, and settling behavior.

> **New to this?** If you have never used Python or the command line before, start with the [Prerequisites](#prerequisites) section below. It explains everything you need to install before running this application.

## What Does This Tool Do?

When you fly a Rotorflight helicopter, your flight controller records detailed sensor data into a **blackbox log** (a `.bbl` file stored on an SD card or onboard flash memory). This tool reads those logs and produces a **step response graph** — a visual measure of how quickly and smoothly each axis (Roll, Pitch, Yaw) responds to your stick inputs.

By comparing step response graphs across flights you can systematically raise or lower your PID gains to achieve the best possible flying feel without guesswork.

### Key terms for beginners

| Term | Plain-English meaning |
|---|---|
| **BBL file** | The raw flight log saved by your flight controller. Copy it from your SD card to your computer. |
| **Step response** | A graph showing how fast the helicopter starts and stops moving when you push the stick. A good response is fast, doesn't overshoot, and settles quickly. |
| **P gain** | The main tuning knob. Too low = sluggish response. Too high = oscillation/ringing. |
| **Rise time** | How quickly the helicopter reaches the commanded rotation rate (lower is snappier). |
| **Overshoot** | How much the rotation overshoots the target before settling (lower is more precise). |
| **Settling time** | How long until the response is stable (lower is better). |

## Prerequisites

Before running this application you need a few things installed on your computer. These are one-time setup steps.

### 1. Python 3.7 or newer

Python is the programming language this application is written in. You need it installed to run the tool.

- **Download Python**: [https://www.python.org/downloads/](https://www.python.org/downloads/)
- Click **"Download Python 3.x.x"** (the big yellow button) and run the installer.
- **Windows users**: During installation, make sure to tick **"Add Python to PATH"** before clicking Install.
- **macOS users**: After installing, open **Terminal** (press ⌘ Space, type "Terminal", press Enter) and run `python3 --version` to confirm it installed correctly.
- **Linux users**: Python 3 is typically pre-installed. Run `python3 --version` in a terminal to check.

`pip` (the Python package manager) is included automatically with Python 3.4 and later — you do not need to install it separately.

### 2. Git (optional — needed only to clone the repository)

If you prefer to download the code as a ZIP file instead of using Git, you can skip this step.

- **Download Git**: [https://git-scm.com/downloads](https://git-scm.com/downloads)
- Run the installer and accept the defaults.

---

## Features

- **Rotorflight Step Response Tuning**: GUI-first workflow for practical PID tuning
- **BBL File Parsing**: Parse blackbox logs and handle multiple logs per file
- **Step Response Analysis**: Calculate step response using FFT-based deconvolution
- **Metrics Calculation**:
  - Rise time (time to reach 63.2% of final value)
  - Maximum overshoot ratio
  - Settling time
- **PID Parameter Extraction**: Extract P, I, D, FF, Boost, and D-min when available
- **Interactive GUI**: Inspect Roll/Pitch/Yaw response curves and export JSON results

## How to Use (GUI)

### Step 0 — Get the code onto your computer

**Option A — Download as a ZIP (easiest, no Git required)**

1. Go to the repository page on GitHub.
2. Click the green **"Code"** button near the top right.
3. Select **"Download ZIP"**.
4. Extract the ZIP to a folder you will remember, for example `C:\Users\YourName\orangebox-pid-step-resp` on Windows or `~/orangebox-pid-step-resp` on macOS/Linux.

**Option B — Clone with Git**

Open a terminal (or Git Bash on Windows) and run:

```bash
git clone https://github.com/pigd0g/orangebox-pid-step-resp.git
cd orangebox-pid-step-resp
```

---

### Step 1 — Open a terminal in the project folder

You need to run the following commands from inside the project folder you downloaded or cloned.

- **Windows**: Open **File Explorer**, navigate to the folder, then type `cmd` in the address bar and press Enter.  
  Alternatively, hold **Shift** and right-click an empty area in the folder, then select **"Open PowerShell window here"**.
- **macOS**: Open **Terminal** (⌘ Space → "Terminal"), then type `cd ` (with a trailing space), drag the project folder onto the Terminal window, and press Enter.
- **Linux**: Open a terminal and use `cd /path/to/orangebox-pid-step-resp`.

---

### Step 2 — Create and activate a virtual environment

A virtual environment is an isolated copy of Python for this project only. It prevents conflicts with other software on your computer. This is a one-time step per installation.

**Windows PowerShell:**

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

> **Note for Windows users**: If you see a security error about running scripts, run this command first and then try again:  
> `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`

**Windows Command Prompt (`cmd`):**

```cmd
python -m venv venv
venv\Scripts\activate.bat
```

**macOS / Linux:**

```bash
python3 -m venv venv
source venv/bin/activate
```

Once activated, your terminal prompt will show `(venv)` at the start — this confirms the virtual environment is active. **You need to activate it every time you open a new terminal before running the application.**

---

### Step 3 — Install dependencies

With the virtual environment active, install all required packages:

```bash
pip install -r requirements.txt
```

This downloads and installs NumPy, PySide6, pyqtgraph, and matplotlib. It may take a minute or two on a slow connection. You only need to do this once per installation (or after updating the code).

---

### Step 4 — Run the GUI

```bash
python gui_step_response.py
```

The application window should open. If you see any error messages, refer to the [Troubleshooting](#troubleshooting) section below.

---

### Step 4b — Build a standalone Windows executable (optional)

If you want to share the tool with others who do not have Python installed, you can build a self-contained Windows `.exe`. **This step requires Windows.**

Install the additional build tool:

```bash
pip install -r requirements-windows-build.txt
```

Build the executable bundle:

```bash
python scripts/build_windows_exe.py
```

The packaged application will be created under `dist/orangebox-step-response/`. Run `dist/orangebox-step-response/orangebox-step-response.exe` to launch it — no Python installation required on the target machine.

Use `--onefile` if you prefer a single `.exe` file instead of a folder:

```bash
python scripts/build_windows_exe.py --onefile
```

---

### Step 5 — Analyze your Rotorflight log

1. Copy your `.bbl` file from your flight controller's SD card to your computer.
2. Click **Open** (or drag the `.bbl` file) in the GUI to load the log.
3. Click **Analyze**.
4. The GUI displays step response curves for Roll, Pitch, and Yaw, along with rise time, overshoot, and settling time metrics.
5. Optionally click **Export JSON** to save the numeric results to a file for comparison between flights.

## Rotorflight PID Tuning Best Practices (Step Response)

Use this as a repeatable baseline process across flights.

### Baseline setup (all three axes: Roll, Pitch, Yaw)

- Set **Feedforward (FF) = 0**.
- Set **Boost = 0**.
- Keep your mechanical setup unchanged during a tuning session (blades, head speed, filtering, weight).

### Flight-and-review loop

1. Fly a short tuning flight with consistent stick inputs.
2. Save the `.bbl` and analyze it in `gui_step_response.py`.
3. Review each axis step response for rise time, overshoot, and settling.
4. Increase **P gain** slightly (small increment) on the target axis.
5. Repeat over multiple flights, comparing responses after each increment.

### What to look for per axis

- **Roll**: Increase P until response becomes crisp but not oscillatory; avoid sustained ringing after step inputs.
- **Pitch**: Increase P similarly; watch for bounce-back or overshoot spikes during aggressive pitch commands.
- **Yaw**: Increase P carefully in smaller steps; check for tail wag or slow settling.

### Practical stopping criteria

- Stop increasing P when overshoot/ringing clearly increases or the axis starts to oscillate.
- Back off to the previous stable value.
- Keep FF and Boost at zero during this phase so P behavior is isolated and measurable.

## Troubleshooting

### "python is not recognized" (Windows)

Python was not added to your PATH during installation.  
**Fix**: Reinstall Python from [python.org](https://www.python.org/downloads/) and make sure to tick **"Add Python to PATH"** on the first installer screen.  
Alternatively, try `python3` instead of `python`.

### "running scripts is disabled on this system" (Windows PowerShell)

Windows blocks unsigned scripts by default.  
**Fix**: Run this once in PowerShell (as your normal user, not as Administrator):

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Then reactivate the virtual environment with `.\venv\Scripts\Activate.ps1`.

### `ModuleNotFoundError: No module named 'PySide6'` (or similar)

The dependencies were not installed, or the virtual environment is not active.  
**Fix**:
1. Activate the virtual environment (you must do this every time you open a new terminal):
   - Windows: `.\venv\Scripts\Activate.ps1`
   - macOS/Linux: `source venv/bin/activate`
2. Then install dependencies: `pip install -r requirements.txt`

### The GUI window doesn't open / crashes immediately

- Make sure you are using the minimum Python version listed in [Prerequisites](#prerequisites): run `python --version` to check.
- Make sure your virtual environment is active (you should see `(venv)` in your prompt).
- Re-install dependencies: `pip install --upgrade -r requirements.txt`.

### "No logs found" / the file won't load

- Make sure the file ends in `.bbl`. Some flight controllers save logs with a numbered suffix (e.g., `.bbl.001`) — rename or copy the file to end in `.bbl` if needed.
- Make sure blackbox logging was enabled in Rotorflight Configurator before the flight.

---

## Running Tests

```bash
python -m unittest
```

To run only the step-response tests with verbose output:

```bash
python -m unittest tests.test_step_response -v
```

## Contributing

* Contributions are very welcome!
* Please follow the [PEP8](https://www.python.org/dev/peps/pep-0008/) Style Guide.
* [More info](https://orangebox.readthedocs.io/#development) in the docs.

## Known issues

* No explicit validation of raw data against corruption (except for headers), but it's highly likely that a Python exception will be raised in these cases anyway
* Tested only on logs generated by Betaflight
* Not all event frames are parsed (see [TODO](orangebox/events.py) comments)
* Some decoders are missing (see [TODO](orangebox/decoders.py) comments)

## Acknowledgement

* Original blackbox data encoder and decoder was written by [Nicholas Sherlock](https://github.com/thenickdude).
* Step response algorithm based on [PIDtoolbox](https://github.com/bw1129/PIDtoolbox) by Brian White.

## License

This project is licensed under GPLv3.
