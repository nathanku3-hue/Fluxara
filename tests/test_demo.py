"""
Unit tests for the Fluxara demo script.
"""

from __future__ import annotations

import os
from fluxara_core.demo import main


def test_demo_main_loop() -> None:
    """Verify that main runs and generates the history CSV file, cleaning up afterwards."""
    csv_filename = "fluxara_history.csv"

    # Ensure clean start state
    if os.path.exists(csv_filename):
        os.remove(csv_filename)

    try:
        main()
        assert os.path.exists(csv_filename)
        assert os.path.getsize(csv_filename) > 0
    finally:
        # Clean up generated file
        if os.path.exists(csv_filename):
            os.remove(csv_filename)
