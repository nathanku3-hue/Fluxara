"""
test_research_isolation.py

Verifies that the R8-3 research-only modules are strictly decoupled and never imported 
by any production components (solver, demo, bidding, hardware).
"""

from __future__ import annotations

import ast
import os


def check_file_imports_for_research(file_path: str) -> list[str]:
    """Parse the Python file and look for imports from fluxara_core.research or research."""
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    try:
        tree = ast.parse(content, filename=file_path)
    except SyntaxError:
        return []

    violating_imports = []

    for node in ast.walk(tree):
        # Handle 'import research' or 'import fluxara_core.research'
        if isinstance(node, ast.Import):
            for name in node.names:
                if "research" in name.name or "fluxara_core.research" in name.name:
                    violating_imports.append(name.name)
        # Handle 'from fluxara_core.research import ...' or 'from research import ...'
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                if "research" in node.module or "fluxara_core.research" in node.module:
                    violating_imports.append(f"from {node.module} import ...")

    return violating_imports


def test_research_decoupling_isolation() -> None:
    # Target directories to check for isolation violations
    production_paths = [
        "fluxara_core/solver.py",
        "fluxara_core/demo.py",
        "fluxara_core/bidding",
        "fluxara_core/hardware",
    ]

    violations = {}

    for path in production_paths:
        full_path = os.path.join(os.getcwd(), path)
        if os.path.isfile(full_path):
            violating = check_file_imports_for_research(full_path)
            if violating:
                violations[path] = violating
        elif os.path.isdir(full_path):
            for root, _, files in os.walk(full_path):
                for file in files:
                    if file.endswith(".py"):
                        file_path = os.path.join(root, file)
                        violating = check_file_imports_for_research(file_path)
                        if violating:
                            rel_path = os.path.relpath(file_path, os.getcwd())
                            violations[rel_path] = violating

    # Assert no violations exist
    assert not violations, f"Production paths imported research modules: {violations}"
