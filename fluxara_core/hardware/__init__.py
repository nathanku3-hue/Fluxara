"""
hardware: Silicon fatigue modeling and aging-aware hardware dispatch (v0.3).
"""

from fluxara_core.hardware.health_map import HealthMap, HealthMapConfig, GPUTelemetry
from fluxara_core.hardware.op_sensitivity import OperatorSensitivity
from fluxara_core.hardware.aging_aware_placer import AgingAwarePlacer

__all__ = [
    "HealthMap",
    "HealthMapConfig",
    "GPUTelemetry",
    "OperatorSensitivity",
    "AgingAwarePlacer",
]
