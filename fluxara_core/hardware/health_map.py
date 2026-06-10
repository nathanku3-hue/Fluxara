"""
health_map.py

Silicon health map and Silent Data Corruption (SDC) risk model for Fluxara R8-2.
Converts GPU telemetry and cumulative damage into device health/risk scores.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass
class GPUTelemetry:
    damage_index: float = 0.0
    ecc_slope: float = 0.0
    leakage_drift: float = 0.0
    thermal_cycle_count: float = 0.0
    xid_error_rate: float = 0.0


@dataclass
class HealthMapConfig:
    # Sigmoid parameters for SDC risk model
    beta_0: float = -6.0
    beta_D: float = 2.0
    beta_E: float = 1.5
    beta_L: float = 1.0
    beta_T: float = 0.5
    beta_X: float = 2.0


class HealthMap:
    """Tracks physical health and SDC probability of GPU execution devices."""

    def __init__(self, config: HealthMapConfig | None = None) -> None:
        self.cfg = config or HealthMapConfig()
        self.gpus: dict[str, GPUTelemetry] = {}

    def get_telemetry(self, gpu_id: str) -> GPUTelemetry:
        """Retrieve or initialize telemetry records for a given GPU."""
        if gpu_id not in self.gpus:
            self.gpus[gpu_id] = GPUTelemetry()
        return self.gpus[gpu_id]

    def update_gpu_telemetry(
        self,
        gpu_id: str,
        damage_index: float | None = None,
        ecc_slope: float | None = None,
        leakage_drift: float | None = None,
        thermal_cycle_count: float | None = None,
        xid_error_rate: float | None = None,
    ) -> None:
        """Update historical telemetry metrics for a specific device."""
        record = self.get_telemetry(gpu_id)
        if damage_index is not None:
            record.damage_index = damage_index
        if ecc_slope is not None:
            record.ecc_slope = ecc_slope
        if leakage_drift is not None:
            record.leakage_drift = leakage_drift
        if thermal_cycle_count is not None:
            record.thermal_cycle_count = thermal_cycle_count
        if xid_error_rate is not None:
            record.xid_error_rate = xid_error_rate

    def get_sdc_probability(self, gpu_id: str) -> float:
        """Compute the Silent Data Corruption probability using the sigmoid model."""
        rec = self.get_telemetry(gpu_id)

        linear_term = (
            self.cfg.beta_0
            + self.cfg.beta_D * rec.damage_index
            + self.cfg.beta_E * rec.ecc_slope
            + self.cfg.beta_L * rec.leakage_drift
            + self.cfg.beta_T * rec.thermal_cycle_count
            + self.cfg.beta_X * rec.xid_error_rate
        )

        # Sigmoid function
        p_sdc = 1.0 / (1.0 + math.exp(-linear_term))
        return p_sdc

    def get_health_score(self, gpu_id: str) -> float:
        """Compute the general health score of a GPU in range [0.0, 1.0]."""
        return 1.0 - self.get_sdc_probability(gpu_id)
