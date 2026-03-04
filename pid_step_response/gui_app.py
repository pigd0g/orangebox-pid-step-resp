from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QObject, Qt, QThread, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QSizePolicy,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .analyzer import StepResponseAnalyzer
from .models import PIDParams, StepResponseResult


AXES = ["roll", "pitch", "yaw"]
SERIES_COLORS = [
    "#1f77b4",
    "#ff7f0e",
    "#2ca02c",
    "#d62728",
    "#9467bd",
    "#17becf",
    "#8c564b",
    "#e377c2",
]


def format_number(value: Optional[float], digits: int = 3) -> str:
    if value is None:
        return "—"
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return "—"
    if np.isnan(numeric):
        return "—"
    return f"{numeric:.{digits}f}"


def format_pid_value(value: Optional[float]) -> str:
    if value is None:
        return "—"
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return "—"
    if np.isnan(numeric):
        return "—"
    if numeric.is_integer():
        return str(int(numeric))
    return f"{numeric:.2f}"


def get_pid_for_axis(result: StepResponseResult, axis_name: str) -> PIDParams:
    axis_result = result.axes.get(axis_name)
    if axis_result and axis_result.pid_params:
        return axis_result.pid_params
    return PIDParams()


def pid_text(pid_params: PIDParams) -> str:
    return (
        f"P {format_pid_value(pid_params.p)} I {format_pid_value(pid_params.i)} "
        f"D {format_pid_value(pid_params.d)} FF {format_pid_value(pid_params.f)} "
        f"B {format_pid_value(pid_params.boost)}"
    )


@dataclass
class SeriesData:
    key: str
    log_id: str
    label: str
    color: str
    pid: PIDParams
    time_ms: np.ndarray
    response: np.ndarray
    peak: Optional[float]


@dataclass
class OverlaySeriesData:
    log_id: str
    label: str
    color: str
    time_ms: np.ndarray
    setpoint: np.ndarray
    gyro: np.ndarray


def downsample_stride(length: int, max_points: int = 12000) -> int:
    if max_points <= 0 or length <= max_points:
        return 1
    return max(1, length // max_points)


def darken_hex(color_value: str, factor: float = 0.65) -> str:
    color = QColor(color_value)
    if not color.isValid():
        return color_value
    red = max(0, min(255, int(color.red() * factor)))
    green = max(0, min(255, int(color.green() * factor)))
    blue = max(0, min(255, int(color.blue() * factor)))
    return f"#{red:02x}{green:02x}{blue:02x}"


class AnalysisWorker(QObject):
    started = Signal(int)
    progress = Signal(int, int, int)
    finished = Signal(list)
    failed = Signal(str)

    def __init__(self, file_path: str, smooth_factor: int = 1, min_input: float = 20.0):
        super().__init__()
        self.file_path = file_path
        self.smooth_factor = smooth_factor
        self.min_input = min_input

    def run(self) -> None:
        try:
            analyzer = StepResponseAnalyzer(
                smooth_factor=self.smooth_factor,
                min_input=self.min_input,
            )
            total_logs = analyzer.get_log_count(self.file_path)
            if total_logs <= 0:
                raise ValueError("No logs found in the selected BBL file.")

            self.started.emit(total_logs)
            results: List[StepResponseResult] = []
            for done_count, log_index in enumerate(range(1, total_logs + 1), start=1):
                log_results = analyzer.analyze(self.file_path, log_index=log_index)
                if log_results:
                    results.append(log_results[0])
                self.progress.emit(done_count, total_logs, log_index)

            self.finished.emit(results)
        except Exception as exc:
            self.failed.emit(str(exc))


class AxisChartWidget(QWidget):
    def __init__(self, axis_name: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.axis_name = axis_name
        self.selected_log_id: Optional[str] = None
        self.series: List[SeriesData] = []
        self.curves: Dict[str, pg.PlotDataItem] = {}

        layout = QVBoxLayout(self)
        self.title = QLabel(f"{axis_name.upper()} Step Response")
        self.title.setObjectName("chartTitle")
        layout.addWidget(self.title)

        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground("#ffffff")
        self.plot_widget.showGrid(x=True, y=True, alpha=0.2)
        self.plot_widget.setLabel("bottom", "Time (ms)")
        self.plot_widget.setLabel("left", "Response")
        self.plot_widget.setYRange(0.0, 2.0, padding=0)
        self.plot_widget.setMouseEnabled(x=True, y=False)
        self.plot_widget.getPlotItem().setMenuEnabled(False)
        self.plot_widget.getPlotItem().hideButtons()
        layout.addWidget(self.plot_widget)

        target_pen = pg.mkPen("#3d6db5", width=1.2, style=Qt.PenStyle.DashLine)
        zero_pen = pg.mkPen("#8a8f98", width=1.0, style=Qt.PenStyle.DotLine)
        self.target_line = pg.InfiniteLine(pos=1.0, angle=0, pen=target_pen)
        self.zero_line = pg.InfiniteLine(pos=0.0, angle=0, pen=zero_pen)
        self.plot_widget.addItem(self.target_line, ignoreBounds=True)
        self.plot_widget.addItem(self.zero_line, ignoreBounds=True)

        self.hover_label = QLabel("Hover over a line to see details.")
        self.hover_label.setObjectName("hoverLabel")
        layout.addWidget(self.hover_label)

        self.proxy = pg.SignalProxy(
            self.plot_widget.scene().sigMouseMoved,
            rateLimit=60,
            slot=self._handle_mouse_moved,
        )

    def set_series(self, series: List[SeriesData], selected_log_id: Optional[str]) -> None:
        self.series = series
        self.selected_log_id = selected_log_id
        self.curves.clear()
        self.plot_widget.clear()
        self.plot_widget.addItem(self.target_line, ignoreBounds=True)
        self.plot_widget.addItem(self.zero_line, ignoreBounds=True)

        if not self.series:
            self.hover_label.setText("No response data available for this axis.")
            self.plot_widget.setXRange(0, 500, padding=0)
            return

        all_times = np.concatenate([item.time_ms for item in self.series if len(item.time_ms)])
        x_max = 500.0
        if len(all_times):
            x_max = float(max(1.0, min(500.0, np.max(all_times))))
        self.plot_widget.setXRange(0, x_max, padding=0)

        for item in self.series:
            curve = self.plot_widget.plot(item.time_ms, item.response)
            self.curves[item.log_id] = curve

        self._apply_styles()
        self.hover_label.setText("Hover over a line to see details.")

    def set_selected_log(self, selected_log_id: Optional[str]) -> None:
        self.selected_log_id = selected_log_id
        self._apply_styles()

    def _apply_styles(self) -> None:
        for item in self.series:
            curve = self.curves.get(item.log_id)
            if curve is None:
                continue
            is_selected = not self.selected_log_id or item.log_id == self.selected_log_id
            if is_selected:
                pen = pg.mkPen(item.color, width=2.2)
            else:
                pen = pg.mkPen("#a3adbde0", width=1.6)
            curve.setPen(pen)

    def _handle_mouse_moved(self, event: object) -> None:
        if not self.series:
            return

        scene_pos = event[0]
        if not self.plot_widget.sceneBoundingRect().contains(scene_pos):
            return

        view_pos = self.plot_widget.getPlotItem().vb.mapSceneToView(scene_pos)
        target_x = float(view_pos.x())

        if self.selected_log_id:
            candidates = [item for item in self.series if item.log_id == self.selected_log_id]
        else:
            candidates = self.series

        nearest_item: Optional[SeriesData] = None
        nearest_idx = 0
        nearest_distance = float("inf")

        for item in candidates:
            if not len(item.time_ms):
                continue
            distances = np.abs(item.time_ms - target_x)
            index = int(np.argmin(distances))
            distance = float(distances[index])
            if distance < nearest_distance:
                nearest_distance = distance
                nearest_idx = index
                nearest_item = item

        if nearest_item is None:
            self.hover_label.setText("Hover over a line to see details.")
            return

        x_value = float(nearest_item.time_ms[nearest_idx])
        y_value = float(nearest_item.response[nearest_idx])
        pid = nearest_item.pid
        self.hover_label.setText(
            (
                f"{nearest_item.label} | {self.axis_name.upper()} t={format_number(x_value)} ms "
                f"| Response={format_number(y_value)} | Peak={format_number(nearest_item.peak)} "
                f"| PID: P={format_pid_value(pid.p)} I={format_pid_value(pid.i)} "
                f"D={format_pid_value(pid.d)} FF={format_pid_value(pid.f)} "
                f"B={format_pid_value(pid.boost)}"
            )
        )


class AxisOverlayWidget(QWidget):
    def __init__(self, axis_name: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.axis_name = axis_name
        self.selected_log_id: Optional[str] = None
        self.series: List[OverlaySeriesData] = []
        self.setpoint_curves: Dict[str, pg.PlotDataItem] = {}
        self.gyro_curves: Dict[str, pg.PlotDataItem] = {}

        layout = QVBoxLayout(self)
        self.title = QLabel(f"{axis_name.upper()} Setpoint / Gyro Overlay")
        self.title.setObjectName("chartTitle")
        layout.addWidget(self.title)

        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground("#ffffff")
        self.plot_widget.showGrid(x=True, y=True, alpha=0.2)
        self.plot_widget.setLabel("bottom", "Time (ms)")
        self.plot_widget.setLabel("left", "Rate (deg/s)")
        self.plot_widget.setMouseEnabled(x=True, y=True)
        self.plot_widget.getPlotItem().setMenuEnabled(False)
        self.plot_widget.getPlotItem().hideButtons()
        layout.addWidget(self.plot_widget)

        self.info_label = QLabel(
            "Solid line = setpoint, dashed line = gyro. Use legend selection above to focus one log."
        )
        self.info_label.setObjectName("hoverLabel")
        layout.addWidget(self.info_label)

    def set_series(self, series: List[OverlaySeriesData], selected_log_id: Optional[str]) -> None:
        self.series = series
        self.selected_log_id = selected_log_id
        self.setpoint_curves.clear()
        self.gyro_curves.clear()
        self.plot_widget.clear()

        if not self.series:
            self.info_label.setText("No setpoint/gyro data available for this axis.")
            return

        for item in self.series:
            setpoint_curve = self.plot_widget.plot(item.time_ms, item.setpoint)
            gyro_curve = self.plot_widget.plot(item.time_ms, item.gyro)
            self.setpoint_curves[item.log_id] = setpoint_curve
            self.gyro_curves[item.log_id] = gyro_curve

        self._apply_styles()
        self.info_label.setText(
            "Solid line = setpoint, dashed line = gyro. Use legend selection above to focus one log."
        )

    def set_selected_log(self, selected_log_id: Optional[str]) -> None:
        self.selected_log_id = selected_log_id
        self._apply_styles()

    def _apply_styles(self) -> None:
        for item in self.series:
            setpoint_curve = self.setpoint_curves.get(item.log_id)
            gyro_curve = self.gyro_curves.get(item.log_id)
            if setpoint_curve is None or gyro_curve is None:
                continue

            is_selected = not self.selected_log_id or item.log_id == self.selected_log_id
            if is_selected:
                setpoint_pen = pg.mkPen(item.color, width=1.8)
                gyro_pen = pg.mkPen(
                    darken_hex(item.color),
                    width=1.5,
                    style=Qt.PenStyle.DashLine,
                )
            else:
                setpoint_pen = pg.mkPen("#c5ccd8", width=1.1)
                gyro_pen = pg.mkPen("#d6dbe5", width=1.1, style=Qt.PenStyle.DashLine)

            setpoint_curve.setPen(setpoint_pen)
            gyro_curve.setPen(gyro_pen)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.selected_bbl_path: Optional[Path] = None
        self.results: List[StepResponseResult] = []
        self.selected_log_id: Optional[str] = None
        self.worker_thread: Optional[QThread] = None
        self.worker: Optional[AnalysisWorker] = None
        self.legend_buttons: Dict[str, QPushButton] = {}
        self.legend_base_styles: Dict[str, str] = {}
        self.legend_series_colors: Dict[str, str] = {}

        self.setWindowTitle("PID Step Response Viewer")
        self.resize(1720, 1080)

        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)

        title = QLabel("PID Step Response Viewer")
        title.setObjectName("pageTitle")
        subtitle = QLabel(
            "Open a blackbox log file, run analysis, and inspect all log responses interactively."
        )
        subtitle.setObjectName("subtitle")
        root_layout.addWidget(title)
        root_layout.addWidget(subtitle)

        main_layout = QHBoxLayout()
        root_layout.addLayout(main_layout, 1)

        left_pane = QWidget()
        left_pane.setMinimumWidth(470)
        left_pane.setMaximumWidth(620)
        left_layout = QVBoxLayout(left_pane)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)

        right_pane = QWidget()
        right_layout = QVBoxLayout(right_pane)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)

        main_layout.addWidget(left_pane, 0)
        main_layout.addWidget(right_pane, 1)

        controls_group = QGroupBox("Analysis Controls")
        controls_layout = QGridLayout(controls_group)
        self.open_button = QPushButton("Open BBL File")
        self.analyze_button = QPushButton("Analyze")
        self.export_button = QPushButton("Export Results JSON")
        self.export_button.setEnabled(False)
        controls_layout.addWidget(self.open_button, 0, 0)
        controls_layout.addWidget(self.analyze_button, 0, 1)
        controls_layout.addWidget(self.export_button, 0, 2)

        self.file_label = QLabel("No file selected")
        controls_layout.addWidget(self.file_label, 1, 0, 1, 3)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(0)
        controls_layout.addWidget(self.progress_bar, 2, 0, 1, 3)

        self.status_label = QLabel("Idle")
        controls_layout.addWidget(self.status_label, 3, 0, 1, 3)

        left_layout.addWidget(controls_group)

        meta_group = QGroupBox("Analysis Summary")
        meta_layout = QGridLayout(meta_group)
        self.meta_source = QLabel("—")
        self.meta_logs = QLabel("—")
        self.meta_duration = QLabel("—")
        meta_layout.addWidget(QLabel("Source file:"), 0, 0)
        meta_layout.addWidget(self.meta_source, 0, 1)
        meta_layout.addWidget(QLabel("Log count:"), 1, 0)
        meta_layout.addWidget(self.meta_logs, 1, 1)
        meta_layout.addWidget(QLabel("Duration range (s):"), 2, 0)
        meta_layout.addWidget(self.meta_duration, 2, 1)
        left_layout.addWidget(meta_group)

        legend_group = QGroupBox("Series Legend")
        legend_layout = QVBoxLayout(legend_group)
        legend_help = QLabel("Click a log entry to focus one series. Click again to show all series.")
        legend_layout.addWidget(legend_help)
        self.legend_content = QWidget()
        self.legend_content_layout = QVBoxLayout(self.legend_content)
        self.legend_content_layout.setContentsMargins(0, 0, 0, 0)
        self.legend_content_layout.setSpacing(4)
        legend_layout.addWidget(self.legend_content, 1)
        left_layout.addWidget(legend_group, 1)

        self.chart_widgets: Dict[str, AxisChartWidget] = {}
        self.overlay_widgets: Dict[str, AxisOverlayWidget] = {}

        self.chart_tabs = QTabWidget()
        step_response_tab = QWidget()
        overlay_tab = QWidget()
        step_response_layout = QVBoxLayout(step_response_tab)
        overlay_layout = QVBoxLayout(overlay_tab)

        for axis_name in AXES:
            axis_chart = AxisChartWidget(axis_name)
            axis_chart.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            axis_chart.setMinimumHeight(320)
            self.chart_widgets[axis_name] = axis_chart
            step_response_layout.addWidget(axis_chart)

            overlay_chart = AxisOverlayWidget(axis_name)
            overlay_chart.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            overlay_chart.setMinimumHeight(320)
            self.overlay_widgets[axis_name] = overlay_chart
            overlay_layout.addWidget(overlay_chart)

        self.chart_tabs.addTab(step_response_tab, "Step Response")
        self.chart_tabs.addTab(overlay_tab, "Setpoint / Gyro")
        right_layout.addWidget(self.chart_tabs)

        self.open_button.clicked.connect(self.select_bbl_file)
        self.analyze_button.clicked.connect(self.start_analysis)
        self.export_button.clicked.connect(self.export_results)

        self.setStyleSheet(
            """
            QLabel#pageTitle { font-size: 24px; font-weight: 700; }
            QLabel#subtitle { color: #526173; margin-bottom: 6px; }
            QLabel#chartTitle { font-size: 16px; font-weight: 600; }
            QLabel#hoverLabel {
                color: #f8fafc;
                background: #1f2937;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 6px 8px;
            }
            QGroupBox { font-weight: 600; margin-top: 8px; }
            QGroupBox::title { left: 10px; padding: 0 4px; }
            """
        )

    def select_bbl_file(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Blackbox Log",
            str(Path.cwd()),
            "Blackbox Logs (*.bbl);;All Files (*.*)",
        )
        if not file_path:
            return

        self.selected_bbl_path = Path(file_path)
        self.file_label.setText(str(self.selected_bbl_path))
        self.status_label.setText("Ready to analyze.")

    def start_analysis(self) -> None:
        if self.selected_bbl_path is None:
            QMessageBox.warning(self, "No File", "Please select a BBL file first.")
            return

        if not self.selected_bbl_path.exists():
            QMessageBox.warning(self, "Missing File", "The selected BBL file no longer exists.")
            return

        self.results = []
        self.selected_log_id = None
        self.export_button.setEnabled(False)
        self._set_controls_enabled(False)
        self._clear_legend_buttons()
        self._set_meta_from_results([])
        self._update_charts()

        self.worker_thread = QThread(self)
        self.worker = AnalysisWorker(str(self.selected_bbl_path))
        self.worker.moveToThread(self.worker_thread)

        self.worker_thread.started.connect(self.worker.run)
        self.worker.started.connect(self.on_worker_started)
        self.worker.progress.connect(self.on_worker_progress)
        self.worker.finished.connect(self.on_worker_finished)
        self.worker.failed.connect(self.on_worker_failed)
        self.worker.finished.connect(self.worker_thread.quit)
        self.worker.failed.connect(self.worker_thread.quit)
        self.worker_thread.finished.connect(self.worker_thread.deleteLater)

        self.progress_bar.setRange(0, 0)
        self.status_label.setText("Preparing analysis...")
        self.worker_thread.start()

    def on_worker_started(self, total_logs: int) -> None:
        self.progress_bar.setRange(0, total_logs)
        self.progress_bar.setValue(0)
        self.status_label.setText(f"Analyzing 0/{total_logs} logs...")

    def on_worker_progress(self, done_count: int, total_logs: int, log_index: int) -> None:
        self.progress_bar.setRange(0, total_logs)
        self.progress_bar.setValue(done_count)
        self.status_label.setText(f"Analyzed log {log_index} ({done_count}/{total_logs})")

    def on_worker_finished(self, results: List[StepResponseResult]) -> None:
        self.results = results
        self._set_controls_enabled(True)
        self.export_button.setEnabled(bool(self.results))
        self._set_meta_from_results(self.results)
        self._rebuild_legend()
        self._update_charts()
        self.progress_bar.setValue(self.progress_bar.maximum())
        self.status_label.setText(f"Analysis complete. Processed {len(self.results)} logs.")
        self.worker = None
        self.worker_thread = None

    def on_worker_failed(self, message: str) -> None:
        self._set_controls_enabled(True)
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(0)
        self.status_label.setText("Analysis failed.")
        QMessageBox.critical(self, "Analysis Error", message)
        self.worker = None
        self.worker_thread = None

    def export_results(self) -> None:
        if not self.results:
            QMessageBox.information(self, "No Results", "Analyze a file before exporting results.")
            return

        default_name = "analysis.json"
        if self.selected_bbl_path:
            default_name = f"{self.selected_bbl_path.stem}_analysis.json"
        suggested_path = str(Path.cwd() / default_name)

        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Analysis JSON",
            suggested_path,
            "JSON Files (*.json);;All Files (*.*)",
        )
        if not save_path:
            return

        output_path = Path(save_path)
        payload = [item.to_dict() for item in self.results]
        with output_path.open("w", encoding="utf-8") as file_handle:
            json.dump(payload, file_handle, indent=2)

        self.status_label.setText(f"Exported results to {output_path}")

    def _set_controls_enabled(self, is_enabled: bool) -> None:
        self.open_button.setEnabled(is_enabled)
        self.analyze_button.setEnabled(is_enabled)

    def _set_meta_from_results(self, results: List[StepResponseResult]) -> None:
        if not results:
            self.meta_source.setText("—")
            self.meta_logs.setText("—")
            self.meta_duration.setText("—")
            return

        durations = [float(item.duration_seconds) for item in results]
        min_duration = min(durations) if durations else 0.0
        max_duration = max(durations) if durations else 0.0
        self.meta_source.setText(results[0].file_path)
        self.meta_logs.setText(str(len(results)))
        self.meta_duration.setText(
            f"{format_number(min_duration, 3)} - {format_number(max_duration, 3)}"
        )

    def _clear_legend_buttons(self) -> None:
        while self.legend_content_layout.count():
            item = self.legend_content_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.legend_buttons.clear()
        self.legend_base_styles.clear()
        self.legend_series_colors.clear()

    def _rebuild_legend(self) -> None:
        self._clear_legend_buttons()
        for idx, result in enumerate(self.results):
            log_id = str(result.log_index if result.log_index else idx + 1)
            series_color = SERIES_COLORS[idx % len(SERIES_COLORS)]
            button = QPushButton(
                "\n".join(
                    [
                        f"Log {log_id}",
                        f"R PID: {pid_text(get_pid_for_axis(result, 'roll'))}",
                        f"P PID: {pid_text(get_pid_for_axis(result, 'pitch'))}",
                        f"Y PID: {pid_text(get_pid_for_axis(result, 'yaw'))}",
                    ]
                )
            )
            button.setCheckable(True)
            base_style = (
                f"text-align: left; padding: 8px; border-radius: 8px; "
                f"border: 1px solid rgba(255,255,255,0.55); "
                f"background: {series_color}; color: #ffffff;"
            )
            button.setStyleSheet(base_style)
            button.clicked.connect(
                lambda checked, value=log_id: self._toggle_selected_log(value)
            )
            self.legend_buttons[log_id] = button
            self.legend_base_styles[log_id] = base_style
            self.legend_series_colors[log_id] = series_color
            self.legend_content_layout.addWidget(button)

        self.legend_content_layout.addStretch()
        self._refresh_legend_styles()

    def _toggle_selected_log(self, log_id: str) -> None:
        if self.selected_log_id == log_id:
            self.selected_log_id = None
        else:
            self.selected_log_id = log_id
        self._refresh_legend_styles()
        for chart in self.chart_widgets.values():
            chart.set_selected_log(self.selected_log_id)
        for overlay in self.overlay_widgets.values():
            overlay.set_selected_log(self.selected_log_id)

    def _refresh_legend_styles(self) -> None:
        for log_id, button in self.legend_buttons.items():
            is_selected = self.selected_log_id == log_id
            is_muted = self.selected_log_id is not None and self.selected_log_id != log_id
            button.blockSignals(True)
            button.setChecked(is_selected)
            button.blockSignals(False)
            base_style = self.legend_base_styles.get(log_id, "")
            series_color = self.legend_series_colors.get(log_id, "#4b5d79")
            if is_selected:
                button.setStyleSheet(
                    base_style +
                    "font-weight: 700; border: 2px solid #ffffff; color: #ffffff;"
                )
            elif is_muted:
                button.setStyleSheet(
                    base_style +
                    f"font-weight: 500; background: {darken_hex(series_color, 0.55)}; "
                    "color: #ffffff; border: 1px solid rgba(255,255,255,0.35);"
                )
            else:
                button.setStyleSheet(
                    base_style +
                    "font-weight: 500; border: 1px solid rgba(255,255,255,0.55); color: #ffffff;"
                )

    def _update_charts(self) -> None:
        for axis_name, chart in self.chart_widgets.items():
            chart_series: List[SeriesData] = []
            overlay_series: List[OverlaySeriesData] = []
            for idx, result in enumerate(self.results):
                axis_result = result.axes.get(axis_name)
                if axis_result is None:
                    continue

                log_id = str(result.log_index if result.log_index else idx + 1)
                color = SERIES_COLORS[idx % len(SERIES_COLORS)]

                time_ms = np.asarray(axis_result.time_ms, dtype=float)
                response = np.asarray(axis_result.step_response, dtype=float)
                if len(time_ms) == 0 or len(response) == 0 or len(time_ms) != len(response):
                    pass
                else:
                    peak = float(np.max(response)) if len(response) else None
                    chart_series.append(
                        SeriesData(
                            key=f"{axis_name}-{log_id}",
                            log_id=log_id,
                            label=f"Log {log_id}",
                            color=color,
                            pid=get_pid_for_axis(result, axis_name),
                            time_ms=time_ms,
                            response=response,
                            peak=peak,
                        )
                    )

                setpoint = np.asarray(axis_result.setpoint, dtype=float)
                gyro = np.asarray(axis_result.gyro, dtype=float)
                if len(setpoint) and len(gyro) and len(setpoint) == len(gyro):
                    log_rate = float(result.log_rate) if result.log_rate else 1.0
                    if log_rate <= 0:
                        log_rate = 1.0
                    overlay_time = np.arange(len(setpoint), dtype=float) / log_rate
                    stride = downsample_stride(len(setpoint), max_points=12000)
                    overlay_time = overlay_time[::stride]
                    setpoint_ds = setpoint[::stride]
                    gyro_ds = gyro[::stride]
                    overlay_series.append(
                        OverlaySeriesData(
                            log_id=log_id,
                            label=f"Log {log_id}",
                            color=color,
                            time_ms=overlay_time,
                            setpoint=setpoint_ds,
                            gyro=gyro_ds,
                        )
                    )
            chart.set_series(chart_series, self.selected_log_id)
            self.overlay_widgets[axis_name].set_series(overlay_series, self.selected_log_id)


def run_gui_app() -> int:
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    pg.setConfigOptions(antialias=True)
    window = MainWindow()
    window.show()
    return app.exec()
