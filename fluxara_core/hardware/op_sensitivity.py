"""
op_sensitivity.py

Operator sensitivity module for Fluxara R8-2.
Defines risk sensitivity coefficients eta(o) for different mathematical operations,
supporting runtime overrides and file-based score loading.
"""

from __future__ import annotations

import json
import os


class OperatorSensitivity:
    """Manages computation operation error/SDC sensitivities (eta)."""

    def __init__(self) -> None:
        # Defaults based on R8-2 roadmap classification placeholders
        self.scores: dict[str, float] = {
            # Very High
            "softmax": 10.0,
            "normalization": 10.0,
            "optimizer_state_update": 10.0,
            "loss_reduction": 10.0,
            "grad_norm_reduction": 10.0,
            # High
            "attention_score_matmul": 5.0,
            "logits_projection": 5.0,
            "all_reduce_gradients": 5.0,
            # Medium
            "ffn_gemm": 2.0,
            "embedding_lookup": 2.0,
            # Low
            "dropout_mask_generation": 0.5,
            "relu": 0.5,
            "gelu_approx": 0.5,
            "redundant_eval": 0.5,
        }

    def get_eta(self, op_type: str) -> float:
        """Retrieve the sensitivity coefficient for a given operation type."""
        return self.scores.get(op_type, 1.0)

    def update_eta(self, op_type: str, eta: float) -> None:
        """Update or insert a custom sensitivity coefficient."""
        self.scores[op_type] = float(eta)

    def load_sensitivity_scores(self, path: str) -> dict[str, float]:
        """Load sensitivity coefficients from a JSON file and update internal map."""
        if not os.path.exists(path):
            raise FileNotFoundError(f"JSON configuration file not found at: {path}")

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        for op_type, score in data.items():
            self.update_eta(op_type, score)

        return data
