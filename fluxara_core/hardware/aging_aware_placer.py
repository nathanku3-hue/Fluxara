"""
aging_aware_placer.py

Aging-aware operation placement solver for Fluxara R8-2.
Maps operator graphs to physical GPUs minimizing SDC risk, execution latency,
communication delay, and load imbalance, subject to hardware capacity constraints.
"""

from __future__ import annotations

import numpy as np
from typing import Any


class AgingAwarePlacer:
    """Solves the optimization problem of placing ML operations onto GPUs based on health."""

    def __init__(
        self,
        lambda_latency: float = 1.0,
        lambda_comm: float = 1.0,
        lambda_balance: float = 1.0,
    ) -> None:
        self.lambda_latency = lambda_latency
        self.lambda_comm = lambda_comm
        self.lambda_balance = lambda_balance

    def place(
        self,
        ops: list[dict[str, Any]],
        gpus: list[dict[str, Any]],
        health_map: Any,
        op_sensitivity: Any,
        colocations: list[tuple[str, str]] | None = None,
    ) -> dict[str, Any]:
        """Solve the placement problem. Falls back to a greedy heuristic if solver fails."""
        try:
            return self._place_cvxpy(ops, gpus, health_map, op_sensitivity, colocations)
        except Exception:
            return self._place_greedy(ops, gpus, health_map, op_sensitivity, colocations)

    def _place_cvxpy(
        self,
        ops: list[dict[str, Any]],
        gpus: list[dict[str, Any]],
        health_map: Any,
        op_sensitivity: Any,
        colocations: list[tuple[str, str]] | None = None,
    ) -> dict[str, Any]:
        import cvxpy as cp  # type: ignore

        N_gpus = len(gpus)
        N_ops = len(ops)

        # Decision variable: X[i, o] = 1 if op o is on GPU i
        X = cp.Variable((N_gpus, N_ops), boolean=True)
        # Helper for load imbalance L1 minimization
        d = cp.Variable(N_gpus)

        p_sdc = np.array([health_map.get_sdc_probability(g["gpu_id"]) for g in gpus])
        eta = np.array([op_sensitivity.get_eta(o["op_type"]) for o in ops])
        base_latency = np.array([g.get("base_latency", 1.0) for g in gpus])
        comm_delay = np.array([g.get("comm_delay", 0.5) for g in gpus])

        compute_req = np.array([o.get("compute", 1.0) for o in ops])
        total_compute = sum(compute_req)
        target_load = total_compute / N_gpus

        gpu_loads = X @ compute_req

        # Objective formulation
        sdc_risk = cp.sum(cp.multiply(X, np.outer(p_sdc, eta)))
        latency_cost = cp.sum(X.T @ base_latency)
        comm_cost = cp.sum(X.T @ comm_delay)

        constraints = []
        # Each op assigned to exactly one GPU
        constraints.append(cp.sum(X, axis=0) == 1)

        # Capacity constraints
        for i, g in enumerate(gpus):
            mem_cap = g.get("memory_capacity", 80.0)
            comp_cap = g.get("compute_capacity", 100.0)
            op_mem = np.array([o.get("memory", 1.0) for o in ops])
            op_comp = np.array([o.get("compute", 1.0) for o in ops])
            constraints.append(cp.sum(cp.multiply(X[i], op_mem)) <= mem_cap)
            constraints.append(cp.sum(cp.multiply(X[i], op_comp)) <= comp_cap)

        # Colocation constraints
        op_id_to_idx = {o["op_id"]: idx for idx, o in enumerate(ops)}
        if colocations:
            for op_a, op_b in colocations:
                if op_a in op_id_to_idx and op_b in op_id_to_idx:
                    idx_a = op_id_to_idx[op_a]
                    idx_b = op_id_to_idx[op_b]
                    constraints.append(X[:, idx_a] == X[:, idx_b])

        # Load balancing helpers
        for i in range(N_gpus):
            constraints.append(d[i] >= gpu_loads[i] - target_load)
            constraints.append(d[i] >= target_load - gpu_loads[i])

        balance_cost = cp.sum(d)

        total_cost = (
            sdc_risk
            + self.lambda_latency * latency_cost
            + self.lambda_comm * comm_cost
            + self.lambda_balance * balance_cost
        )

        problem = cp.Problem(cp.Minimize(total_cost), constraints)
        problem.solve()

        if X.value is None:
            raise RuntimeError("Solver returned no solution")

        placements = []
        for o_idx, o in enumerate(ops):
            gpu_idx = int(np.argmax(X.value[:, o_idx]))
            g = gpus[gpu_idx]
            p_val = p_sdc[gpu_idx]
            eta_val = eta[o_idx]

            placements.append({
                "op_id": o["op_id"],
                "op_type": o["op_type"],
                "sensitivity_eta": float(eta_val),
                "assigned_gpu_id": g["gpu_id"],
                "assigned_slice_id": None,
                "p_sdc": float(p_val),
                "risk_cost": float(eta_val * p_val),
                "latency_cost": float(base_latency[gpu_idx]),
                "comm_cost": float(comm_delay[gpu_idx]),
            })

        # Calculate final metrics
        total_risk = sum(p["risk_cost"] for p in placements)
        loads = [
            sum(
                ops[idx].get("compute", 1.0)
                for idx, p in enumerate(placements)
                if p["assigned_gpu_id"] == g["gpu_id"]
            )
            for g in gpus
        ]
        imbalance = max(loads) - min(loads)

        # Baseline latency (cost-only, placing all on the fastest GPU)
        min_lat_idx = int(np.argmin(base_latency))
        baseline_latency = base_latency[min_lat_idx] * len(ops)
        total_lat = sum(p["latency_cost"] for p in placements)
        latency_overhead_pct = (
            ((total_lat / baseline_latency) - 1.0) * 100.0 if baseline_latency > 0 else 0.0
        )

        return {
            "placements": placements,
            "objective_value": float(problem.value),
            "total_sdc_weighted_risk": float(total_risk),
            "latency_overhead_pct": float(latency_overhead_pct),
            "residual_life_imbalance": float(imbalance),
        }

    def _place_greedy(
        self,
        ops: list[dict[str, Any]],
        gpus: list[dict[str, Any]],
        health_map: Any,
        op_sensitivity: Any,
        colocations: list[tuple[str, str]] | None = None,
    ) -> dict[str, Any]:
        """Greedy placement heuristic fallback."""
        N_gpus = len(gpus)
        p_sdc = [health_map.get_sdc_probability(g["gpu_id"]) for g in gpus]
        base_latency = [g.get("base_latency", 1.0) for g in gpus]
        comm_delay = [g.get("comm_delay", 0.5) for g in gpus]

        gpu_mem_used = [0.0] * N_gpus
        gpu_comp_used = [0.0] * N_gpus

        op_id_to_idx = {o["op_id"]: idx for idx, o in enumerate(ops)}
        placements: list[dict[str, Any]] = [{} for _ in ops]

        # Process colocations first to treat them as single units
        co_map: dict[str, str] = {}
        if colocations:
            for op_a, op_b in colocations:
                co_map[op_a] = op_b
                co_map[op_b] = op_a

        # Sort operations by sensitivity descending
        sorted_indices = np.argsort([op_sensitivity.get_eta(o["op_type"]) for o in ops])[::-1]

        for o_idx in sorted_indices:
            if placements[o_idx]:
                continue  # already placed via colocation

            o = ops[o_idx]
            eta_val = op_sensitivity.get_eta(o["op_type"])

            # Find best GPU satisfying capacity
            best_gpu_idx = -1
            best_score = float("inf")

            for i, g in enumerate(gpus):
                mem_cap = g.get("memory_capacity", 80.0)
                comp_cap = g.get("compute_capacity", 100.0)
                req_mem = o.get("memory", 1.0)
                req_comp = o.get("compute", 1.0)

                # Check if colocated peer is also placed here
                peer_idx = -1
                if o["op_id"] in co_map:
                    peer_id = co_map[o["op_id"]]
                    peer_idx = op_id_to_idx[peer_id]
                    if placements[peer_idx]:
                        # Must match peer placement
                        peer_gpu_id = placements[peer_idx]["assigned_gpu_id"]
                        if g["gpu_id"] == peer_gpu_id:
                            best_gpu_idx = i
                            break
                        continue

                if gpu_mem_used[i] + req_mem > mem_cap or gpu_comp_used[i] + req_comp > comp_cap:
                    continue

                # Load imbalance surrogate
                target_load = sum(o.get("compute", 1.0) for o in ops) / N_gpus
                temp_load = gpu_comp_used[i] + req_comp
                balance_score = abs(temp_load - target_load)

                score = (
                    eta_val * p_sdc[i]
                    + self.lambda_latency * base_latency[i]
                    + self.lambda_comm * comm_delay[i]
                    + self.lambda_balance * balance_score
                )

                if score < best_score:
                    best_score = score
                    best_gpu_idx = i

            if best_gpu_idx == -1:
                # Fallback to GPU 0 if capacity bounds are hard violated
                best_gpu_idx = 0

            # Assign
            g = gpus[best_gpu_idx]
            gpu_mem_used[best_gpu_idx] += o.get("memory", 1.0)
            gpu_comp_used[best_gpu_idx] += o.get("compute", 1.0)

            placements[o_idx] = {
                "op_id": o["op_id"],
                "op_type": o["op_type"],
                "sensitivity_eta": float(eta_val),
                "assigned_gpu_id": g["gpu_id"],
                "assigned_slice_id": None,
                "p_sdc": float(p_sdc[best_gpu_idx]),
                "risk_cost": float(eta_val * p_sdc[best_gpu_idx]),
                "latency_cost": float(base_latency[best_gpu_idx]),
                "comm_cost": float(comm_delay[best_gpu_idx]),
            }

            # If colocated, assign peer too
            if o["op_id"] in co_map:
                peer_id = co_map[o["op_id"]]
                peer_idx = op_id_to_idx[peer_id]
                if not placements[peer_idx]:
                    placements[peer_idx] = placements[o_idx].copy()
                    placements[peer_idx]["op_id"] = peer_id
                    placements[peer_idx]["op_type"] = ops[peer_idx]["op_type"]
                    placements[peer_idx]["sensitivity_eta"] = float(
                        op_sensitivity.get_eta(ops[peer_idx]["op_type"])
                    )

        total_risk = sum(p["risk_cost"] for p in placements)
        total_lat = sum(p["latency_cost"] for p in placements)
        min_lat_idx = int(np.argmin(base_latency))
        baseline_latency = base_latency[min_lat_idx] * len(ops)
        latency_overhead_pct = (
            ((total_lat / baseline_latency) - 1.0) * 100.0 if baseline_latency > 0 else 0.0
        )
        imbalance = max(gpu_comp_used) - min(gpu_comp_used)

        return {
            "placements": placements,
            "objective_value": float(total_risk + total_lat + imbalance),
            "total_sdc_weighted_risk": float(total_risk),
            "latency_overhead_pct": float(latency_overhead_pct),
            "residual_life_imbalance": float(imbalance),
        }
