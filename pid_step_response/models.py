# PID Step Response Library - Data Models
# Copyright (C) 2024
# License: GPLv3

"""
Data models for step response analysis.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
import numpy as np


def _json_safe(value: Any) -> Any:
    """Convert numpy/tuple values to JSON-serializable Python types."""
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    return value


@dataclass
class PIDParams:
    """PID parameters for a single axis."""
    p: float = 0.0
    i: float = 0.0
    d: float = 0.0
    f: float = 0.0  # Feedforward term
    boost: float = 0.0  # Rotorflight boost term
    d_min: float = 0.0  # D-min term
    
    def __str__(self) -> str:
        return (
            f"P={self.p}, I={self.i}, D={self.d}, "
            f"F={self.f}, Boost={self.boost}, D_min={self.d_min}"
        )

    def to_dict(self) -> Dict[str, float]:
        """Return PID terms using clear mapped names for export."""
        return {
            'P': float(self.p),
            'I': float(self.i),
            'D': float(self.d),
            'FF': float(self.f),
            'Boost': float(self.boost),
            'D_min': float(self.d_min),
        }


@dataclass
class AxisResult:
    """Step response result for a single axis."""
    axis_name: str  # 'roll', 'pitch', or 'yaw'
    
    # Step response data
    time_ms: np.ndarray = field(default_factory=lambda: np.array([]))
    step_response: np.ndarray = field(default_factory=lambda: np.array([]))
    
    # Metrics
    rise_time_ms: float = 0.0  # Time to reach 50% of final value (matching PIDtoolbox latencyHalfHeight)
    max_overshoot: float = 0.0  # Maximum overshoot ratio (0-1, where 0.1 = 10%)
    settling_time_ms: float = 0.0  # Time to settle within 2% of final value
    
    # PID parameters for this axis
    pid_params: PIDParams = field(default_factory=PIDParams)
    
    # Original data (for plotting)
    setpoint: np.ndarray = field(default_factory=lambda: np.array([]))
    gyro: np.ndarray = field(default_factory=lambda: np.array([]))
    
    # Number of segments used in calculation
    num_segments: int = 0
    
    def __repr__(self) -> str:
        return (f"AxisResult(axis={self.axis_name}, "
                f"rise_time={self.rise_time_ms:.2f}ms, "
                f"overshoot={self.max_overshoot*100:.1f}%)")

    def to_dict(self) -> Dict[str, Any]:
        """Return axis step response data and summary metrics for export."""
        return {
            'time_ms': _json_safe(self.time_ms),
            'step_response': _json_safe(self.step_response),
            'summary': {
                'rise_time_ms': float(self.rise_time_ms),
                'max_overshoot': float(self.max_overshoot),
                'settling_time_ms': float(self.settling_time_ms),
                'num_segments': int(self.num_segments),
            },
            'pid': self.pid_params.to_dict(),
        }


@dataclass
class LogData:
    """Data extracted from a single log within a BBL file."""
    log_index: int
    
    # Time data in microseconds
    time_us: np.ndarray = field(default_factory=lambda: np.array([]))
    
    # Setpoint data for each axis (deg/s)
    setpoint_roll: np.ndarray = field(default_factory=lambda: np.array([]))
    setpoint_pitch: np.ndarray = field(default_factory=lambda: np.array([]))
    setpoint_yaw: np.ndarray = field(default_factory=lambda: np.array([]))
    
    # Gyro data for each axis (deg/s)
    gyro_roll: np.ndarray = field(default_factory=lambda: np.array([]))
    gyro_pitch: np.ndarray = field(default_factory=lambda: np.array([]))
    gyro_yaw: np.ndarray = field(default_factory=lambda: np.array([]))
    
    # Log rate (samples per ms, e.g. 4 for 4kHz)
    log_rate: float = 4.0
    
    # PID parameters for each axis
    roll_pid: PIDParams = field(default_factory=PIDParams)
    pitch_pid: PIDParams = field(default_factory=PIDParams)
    yaw_pid: PIDParams = field(default_factory=PIDParams)
    
    # Raw headers from the log
    headers: Dict = field(default_factory=dict)
    
    @property
    def duration_seconds(self) -> float:
        """Duration of the log in seconds."""
        if len(self.time_us) < 2:
            return 0.0
        return (self.time_us[-1] - self.time_us[0]) / 1_000_000
    
    @property
    def sample_count(self) -> int:
        """Number of samples in the log."""
        return len(self.time_us)


@dataclass
class StepResponseResult:
    """Complete step response analysis result for a BBL file."""
    file_path: str
    log_index: int
    
    # Results for each axis
    roll: AxisResult = field(default_factory=lambda: AxisResult(axis_name='roll'))
    pitch: AxisResult = field(default_factory=lambda: AxisResult(axis_name='pitch'))
    yaw: AxisResult = field(default_factory=lambda: AxisResult(axis_name='yaw'))
    
    # Log metadata
    log_rate: float = 4.0
    duration_seconds: float = 0.0
    sample_count: int = 0
    headers: Dict = field(default_factory=dict)
    
    # Analysis parameters used
    smooth_factor: int = 1  # 1=off, 2=low, 3=medium, 4=high
    min_input: float = 20.0  # Minimum input rate (deg/s)
    
    @property
    def axes(self) -> Dict[str, AxisResult]:
        """Return all axis results as a dictionary."""
        return {
            'roll': self.roll,
            'pitch': self.pitch,
            'yaw': self.yaw
        }
    
    def summary(self) -> str:
        """Return a summary string of the analysis results."""
        lines = [
            f"Step Response Analysis: {self.file_path} (Log #{self.log_index})",
            f"Duration: {self.duration_seconds:.2f}s, Samples: {self.sample_count}, Log Rate: {self.log_rate}kHz",
            "",
            "Results:",
        ]
        for name, axis in self.axes.items():
            lines.append(f"  {name.upper()}:")
            lines.append(f"    Rise Time: {axis.rise_time_ms:.2f} ms")
            lines.append(f"    Max Overshoot: {axis.max_overshoot*100:.1f}%")
            lines.append(f"    PID: {axis.pid_params}")
            lines.append(f"    Segments Used: {axis.num_segments}")
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        """Return full per-log export payload with headers and axis data."""
        return {
            'file_path': self.file_path,
            'log_index': int(self.log_index),
            'log_rate': float(self.log_rate),
            'duration_seconds': float(self.duration_seconds),
            'sample_count': int(self.sample_count),
            'headers': _json_safe(self.headers),
            'pid': {
                'roll': self.roll.pid_params.to_dict(),
                'pitch': self.pitch.pid_params.to_dict(),
                'yaw': self.yaw.pid_params.to_dict(),
            },
            'axes': {
                'roll': self.roll.to_dict(),
                'pitch': self.pitch.to_dict(),
                'yaw': self.yaw.to_dict(),
            },
        }
