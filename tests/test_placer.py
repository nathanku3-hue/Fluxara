"""
Unit tests for the Aging-Aware operation placement solver.
Verifies that risk-aware placement routes high-sensitivity operations away from
degraded GPUs, reduces overall SDC risk by at least 30% versus a cost-only baseline,
keeps latency overhead under 5%, and supports file-loaded sensitivity score overrides.
"""

from __future__ import annotations

import json
import os
import pytest
from fluxara_core.hardware import HealthMap, OperatorSensitivity, AgingAwarePlacer


def test_placer_sdc_risk_reduction_and_routing() -> None:
    # 1. Setup health map with healthy, medium, and degraded GPUs
    health_map = HealthMap()
    # gpu_0: healthy (low SDC risk, p_sdc approx 0.002)
    health_map.update_gpu_telemetry("gpu_0", damage_index=0.0, xid_error_rate=0.0)
    # gpu_1: medium (p_sdc approx 0.119)
    health_map.update_gpu_telemetry("gpu_1", damage_index=1.0, xid_error_rate=1.0)
    # gpu_2: degraded (high SDC risk, p_sdc approx 0.880)
    health_map.update_gpu_telemetry("gpu_2", damage_index=3.0, xid_error_rate=2.0)

    gpus = [
        {"gpu_id": "gpu_0", "memory_capacity": 80.0, "compute_capacity": 100.0, "base_latency": 1.0, "comm_delay": 0.5},
        {"gpu_id": "gpu_1", "memory_capacity": 80.0, "compute_capacity": 100.0, "base_latency": 1.0, "comm_delay": 0.5},
        {"gpu_id": "gpu_2", "memory_capacity": 80.0, "compute_capacity": 100.0, "base_latency": 1.0, "comm_delay": 0.5},
    ]

    # 2. Setup operations with varied sensitivities
    op_sensitivity = OperatorSensitivity()
    ops = [
        {"op_id": "op_0", "op_type": "softmax", "memory": 10.0, "compute": 10.0},                  # Very High (10.0)
        {"op_id": "op_1", "op_type": "normalization", "memory": 10.0, "compute": 10.0},            # Very High (10.0)
        {"op_id": "op_2", "op_type": "attention_score_matmul", "memory": 10.0, "compute": 10.0},   # High (5.0)
        {"op_id": "op_3", "op_type": "ffn_gemm", "memory": 10.0, "compute": 10.0},                 # Medium (2.0)
        {"op_id": "op_4", "op_type": "relu", "memory": 10.0, "compute": 10.0},                     # Low (0.5)
        {"op_id": "op_5", "op_type": "redundant_eval", "memory": 10.0, "compute": 10.0},           # Low (0.5)
    ]

    placer = AgingAwarePlacer(lambda_latency=1.0, lambda_comm=1.0, lambda_balance=1.0)

    # 3. Solve Risk-Aware Placement
    risk_placement = placer.place(ops, gpus, health_map, op_sensitivity)
    
    # 4. Solve Cost-Only Placement (Health Map returns 0 SDC risk for all)
    clean_health_map = HealthMap()
    clean_health_map.cfg.beta_0 = -99.0  # forces sigmoid SDC probability to 0.0
    cost_placement = placer.place(ops, gpus, clean_health_map, op_sensitivity)

    # Evaluate physical risk of cost-only placement under TRUE health conditions
    cost_only_sdc_risk = 0.0
    cost_only_high_sensitivity_ops_on_degraded = 0
    for p in cost_placement["placements"]:
        gpu_id = p["assigned_gpu_id"]
        true_p_sdc = health_map.get_sdc_probability(gpu_id)
        cost_only_sdc_risk += p["sensitivity_eta"] * true_p_sdc
        if p["sensitivity_eta"] >= 5.0 and gpu_id == "gpu_2":
            cost_only_high_sensitivity_ops_on_degraded += 1

    # Evaluate physical risk of risk-aware placement
    risk_aware_sdc_risk = risk_placement["total_sdc_weighted_risk"]
    risk_aware_high_sensitivity_ops_on_degraded = sum(
        1 for p in risk_placement["placements"]
        if p["sensitivity_eta"] >= 5.0 and p["assigned_gpu_id"] == "gpu_2"
    )

    print(f"Cost-only SDC Risk under true health: {cost_only_sdc_risk:.4f}")
    print(f"Risk-aware SDC Risk: {risk_aware_sdc_risk:.4f}")
    print(f"High-sensitivity ops on degraded GPU (Cost-Only): {cost_only_high_sensitivity_ops_on_degraded}")
    print(f"High-sensitivity ops on degraded GPU (Risk-Aware): {risk_aware_high_sensitivity_ops_on_degraded}")
    print(f"Latency Overhead Percentage: {risk_placement['latency_overhead_pct']:.2f}%")

    # Verification Gates
    # Gate 1: High sensitivity ops on degraded GPU should be <= 50% of cost-only baseline
    assert risk_aware_high_sensitivity_ops_on_degraded <= 0.5 * cost_only_high_sensitivity_ops_on_degraded, (
        f"High-sensitivity ops on degraded GPU ({risk_aware_high_sensitivity_ops_on_degraded}) is not <= 50% of cost-only ({cost_only_high_sensitivity_ops_on_degraded})"
    )

    # Gate 2: SDC risk is reduced by at least 30% (risk-aware <= 0.70 * cost-only)
    assert risk_aware_sdc_risk <= 0.70 * cost_only_sdc_risk, (
        f"Risk-aware risk {risk_aware_sdc_risk:.4f} is not 30% lower than cost-only baseline {cost_only_sdc_risk:.4f}"
    )

    # Gate 3: Latency overhead is bounded <= 5%
    assert risk_placement["latency_overhead_pct"] <= 5.0, (
        f"Latency overhead {risk_placement['latency_overhead_pct']:.2f}% exceeds 5%"
    )

    # Gate 4: Memory and compute capacities are respected on all GPUs
    for gpu in gpus:
        gpu_id = gpu["gpu_id"]
        allocated_mem = sum(
            o["memory"] for p, o in zip(risk_placement["placements"], ops)
            if p["assigned_gpu_id"] == gpu_id
        )
        allocated_comp = sum(
            o["compute"] for p, o in zip(risk_placement["placements"], ops)
            if p["assigned_gpu_id"] == gpu_id
        )
        assert allocated_mem <= gpu["memory_capacity"]
        assert allocated_comp <= gpu["compute_capacity"]


def test_placer_dynamic_sensitivity_override_from_file(tmp_path) -> None:
    # 1. Setup health and op sensitivity
    health_map = HealthMap()
    # gpu_0: healthy, gpu_1: degraded
    health_map.update_gpu_telemetry("gpu_0", damage_index=0.0)
    health_map.update_gpu_telemetry("gpu_1", damage_index=3.0, xid_error_rate=2.0)

    gpus = [
        {"gpu_id": "gpu_0", "memory_capacity": 100.0, "compute_capacity": 100.0, "base_latency": 1.0, "comm_delay": 0.5},
        {"gpu_id": "gpu_1", "memory_capacity": 100.0, "compute_capacity": 100.0, "base_latency": 1.0, "comm_delay": 0.5},
    ]

    # op_0 is type relu. Default sensitivity of relu is Low (0.5).
    # Since gpu_1 is degraded, the placer would normally place relu on gpu_1 to prioritize placing high-sensitivity ops on gpu_0.
    ops = [
        {"op_id": "op_0", "op_type": "relu", "memory": 10.0, "compute": 10.0},
        {"op_id": "op_1", "op_type": "softmax", "memory": 10.0, "compute": 10.0}, # Very High (10.0)
    ]

    op_sensitivity = OperatorSensitivity()
    placer = AgingAwarePlacer()

    # Base placement
    base_res = placer.place(ops, gpus, health_map, op_sensitivity)
    op0_gpu_base = next(p["assigned_gpu_id"] for p in base_res["placements"] if p["op_id"] == "op_0")
    # Normally, relu goes to degraded gpu_1 because softmax (10.0) takes healthy gpu_0
    assert op0_gpu_base == "gpu_1"

    # 2. Write custom JSON overrides to change relu sensitivity to Ultra High (25.0)
    override_data = {"relu": 25.0}
    json_file = tmp_path / "custom_sensitivity.json"
    with open(json_file, "w") as f:
        json.dump(override_data, f)

    # Load overrides
    op_sensitivity.load_sensitivity_scores(str(json_file))
    assert op_sensitivity.get_eta("relu") == 25.0

    # 3. Re-run placement with overridden sensitivity scores
    override_res = placer.place(ops, gpus, health_map, op_sensitivity)
    op0_gpu_overridden = next(p["assigned_gpu_id"] for p in override_res["placements"] if p["op_id"] == "op_0")
    
    # Under override, relu is now Ultra High (25.0), higher than softmax (10.0).
    # So relu must move to healthy gpu_0!
    assert op0_gpu_overridden == "gpu_0"
