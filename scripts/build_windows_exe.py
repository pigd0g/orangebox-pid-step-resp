#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path
from typing import List, Optional


APP_NAME = "orangebox-step-response"
ENTRY_SCRIPT = "gui_step_response.py"


def build_pyinstaller_args(
    project_root: Path,
    dist_dir: Optional[Path] = None,
    work_dir: Optional[Path] = None,
    onefile: bool = False,
) -> List[str]:
    entry_script = project_root / ENTRY_SCRIPT
    if not entry_script.is_file():
        raise FileNotFoundError(f"Could not find GUI entry script: {entry_script}")

    args: List[str] = [
        str(entry_script),
        "--noconfirm",
        "--clean",
        "--windowed",
        "--name",
        APP_NAME,
        "--paths",
        str(project_root),
        "--collect-all",
        "PySide6",
        "--collect-all",
        "pyqtgraph",
        "--hidden-import",
        "numpy",
        "--hidden-import",
        "pyqtgraph.exporters",
    ]

    if dist_dir is not None:
        args.extend(["--distpath", str(dist_dir)])
    if work_dir is not None:
        args.extend(["--workpath", str(work_dir)])
    if onefile:
        args.append("--onefile")

    return args


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a Windows distributable executable for gui_step_response.py."
    )
    default_root = Path(__file__).resolve().parent.parent
    parser.add_argument(
        "--project-root",
        type=Path,
        default=default_root,
        help="Path to repository root containing gui_step_response.py",
    )
    parser.add_argument(
        "--dist-dir",
        type=Path,
        default=None,
        help="Optional custom output directory for final distributable",
    )
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=None,
        help="Optional custom build work directory",
    )
    parser.add_argument(
        "--onefile",
        action="store_true",
        help="Build a single-file executable instead of a directory bundle",
    )
    args = parser.parse_args()

    try:
        from PyInstaller import __main__ as pyinstaller_main
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "PyInstaller is required. Install build dependencies with "
            "'pip install -r requirements-windows-build.txt'."
        ) from exc

    try:
        project_root = args.project_root.resolve(strict=True)
    except FileNotFoundError as exc:
        raise SystemExit(f"Project root does not exist: {args.project_root}") from exc

    pyinstaller_main.run(
        build_pyinstaller_args(
            project_root=project_root,
            dist_dir=args.dist_dir,
            work_dir=args.work_dir,
            onefile=args.onefile,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
