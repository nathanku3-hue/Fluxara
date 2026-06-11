import argparse
import csv
import json
import os
import sys
import numpy as np
import jsonschema

# Import benchmark functions from generate_acceptance_report
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
try:
    from generate_acceptance_report import run_market_loop, run_monte_carlo_safety, run_placer_benchmark
except ImportError as e:
    print(f"Failed to import from generate_acceptance_report: {e}")
    sys.exit(1)

def validate_json_schema(json_path, schema_path):
    if not os.path.exists(json_path):
        print(f"Error: JSON file {json_path} not found.")
        sys.exit(1)
    if not os.path.exists(schema_path):
        print(f"Error: Schema file {schema_path} not found.")
        sys.exit(1)
        
    with open(json_path, "r", encoding="utf-8") as jf:
        data = json.load(jf)
    with open(schema_path, "r", encoding="utf-8") as sf:
        schema = json.load(sf)
        
    try:
        jsonschema.validate(instance=data, schema=schema)
        print(f"✓ Validated {json_path} against {schema_path} successfully.")
    except jsonschema.ValidationError as e:
        print(f"✗ Schema validation failed for {json_path}: {e.message}")
        sys.exit(1)

def validate_csv_schema(csv_path, schema_path):
    if not os.path.exists(csv_path):
        print(f"Error: CSV file {csv_path} not found.")
        sys.exit(1)
    if not os.path.exists(schema_path):
        print(f"Error: Schema file {schema_path} not found.")
        sys.exit(1)
        
    with open(schema_path, "r", encoding="utf-8") as sf:
        schema = json.load(sf)
        
    rows = []
    with open(csv_path, "r", encoding="utf-8") as cf:
        reader = csv.DictReader(cf)
        for row in reader:
            typed_row = {}
            for k, v in row.items():
                if k == "is_caching_efficient":
                    typed_row[k] = int(v)
                elif k in ["temperature_c", "chi_hardware", "erased_bits_per_sec", "mem_energy_j", 
                           "cache_size_bits", "q_min_w", "q_actual_w", "caching_energy_j", "erasure_avoided_j"]:
                    typed_row[k] = float(v)
                else:
                    typed_row[k] = v
            rows.append(typed_row)
            
    try:
        jsonschema.validate(instance=rows, schema=schema)
        print(f"✓ Validated {csv_path} against {schema_path} successfully ({len(rows)} rows).")
    except jsonschema.ValidationError as e:
        print(f"✗ Schema validation failed for {csv_path}: {e.message}")
        sys.exit(1)

def run_replay(seed):
    print(f"\nReplaying acceptance benchmarks with seed={seed}...")
    
    # 1. Run market loops
    exp_det, profit_det, success_det = run_market_loop(use_stochastic=False, seed=seed)
    exp_rand, profit_rand, success_rand = run_market_loop(use_stochastic=True, seed=seed)
    
    exp_ratio = exp_rand / exp_det if exp_det > 0 else 0.0
    profit_ratio = profit_rand / profit_det if profit_det > 0 else 0.0
    
    print(f"Market loop replayed:")
    print(f"  Deterministic - Exploitability: {exp_det:.4f}, Profit: ${profit_det:.2f}")
    print(f"  Randomized    - Exploitability: {exp_rand:.4f}, Profit: ${profit_rand:.2f}")
    print(f"  Ratios        - Exploitability Ratio: {exp_ratio:.4f}, Profit Ratio: {profit_ratio:.4f}")
    
    # 2. Run Monte Carlo safety
    mc_success, mc_cvar = run_monte_carlo_safety(N_trials=10000, seed=seed)
    print(f"Monte Carlo safety replayed:")
    print(f"  Success Rate: {mc_success:.4f}, 99% CVaR Shortfall: {mc_cvar:.4f} MW")
    
    # 3. Run Placer placement
    placer_metrics = run_placer_benchmark()
    risk_reduction = placer_metrics["cost_only_sdc_weighted_risk"] - placer_metrics["risk_aware_sdc_weighted_risk"]
    risk_reduction_pct = (risk_reduction / placer_metrics["cost_only_sdc_weighted_risk"]) * 100.0
    
    degraded_reduction = (
        placer_metrics["cost_only_high_sensitivity_on_degraded"] - placer_metrics["risk_aware_high_sensitivity_on_degraded"]
    )
    degraded_reduction_pct = (
        (degraded_reduction / placer_metrics["cost_only_high_sensitivity_on_degraded"] * 100.0)
        if placer_metrics["cost_only_high_sensitivity_on_degraded"] > 0 else 100.0
    )
    
    print(f"Placer benchmark replayed:")
    print(f"  SDC Risk Reduction: {risk_reduction_pct:.2f}%")
    print(f"  Degraded Placement Reduction: {degraded_reduction_pct:.2f}%")
    
    # Compare with report
    with open("artifacts/r8_acceptance_report.json", "r", encoding="utf-8") as f:
        report = json.load(f)
        
    rep_m = report["r8_1_market_security"]
    rep_det = rep_m["deterministic_baseline"]
    rep_rand = rep_m["randomized_policy"]
    rep_mc = rep_m["delivery_safety_monte_carlo"]
    rep_p = report["r8_2_aging_aware_routing"]["metrics"]
    
    if seed == 42:
        print("\nVerifying exact match with committed report (seed=42)...")
        assert abs(exp_det - rep_det["exploitability"]) < 1e-7, "Det exploitability mismatch"
        assert abs(profit_det - rep_det["expected_profit_usd"]) < 1e-7, "Det profit mismatch"
        assert abs(success_det - rep_det["delivery_success_rate"]) < 1e-7, "Det success mismatch"
        
        assert abs(exp_rand - rep_rand["exploitability"]) < 1e-7, "Rand exploitability mismatch"
        assert abs(profit_rand - rep_rand["expected_profit_usd"]) < 1e-7, "Rand profit mismatch"
        assert abs(success_rand - rep_rand["delivery_success_rate"]) < 1e-7, "Rand success mismatch"
        
        assert abs(mc_success - rep_mc["delivery_success_rate"]) < 1e-7, "MC success mismatch"
        assert abs(mc_cvar - rep_mc["shortfall_cvar_99_mw"]) < 1e-7, "MC CVaR mismatch"
        
        assert abs(placer_metrics["cost_only_sdc_weighted_risk"] - rep_p["cost_only_sdc_weighted_risk"]) < 1e-7, "Placer cost risk mismatch"
        assert abs(placer_metrics["risk_aware_sdc_weighted_risk"] - rep_p["aging_aware_sdc_weighted_risk"]) < 1e-7, "Placer risk risk mismatch"
        print("✓ All metrics match report EXACTLY.")
    else:
        print(f"\nVerifying metrics satisfy acceptance gates for seed={seed}...")
        # Check standard gates from generate_acceptance_report.py
        assert exp_ratio <= 0.90, f"Exploitability ratio too high: {exp_ratio}"
        assert profit_ratio >= 0.95, f"Profit ratio too low: {profit_ratio}"
        assert mc_success >= 0.999, f"MC success rate too low: {mc_success}"
        assert mc_cvar <= 0.05, f"MC CVaR shortfall too high: {mc_cvar}"
        assert risk_reduction_pct >= 30.0, f"Placer risk reduction too low: {risk_reduction_pct}%"
        assert degraded_reduction_pct >= 50.0, f"Placer degraded placement reduction too low: {degraded_reduction_pct}%"
        print("✓ All metrics satisfy acceptance gates under the replayed seed.")

def main():
    parser = argparse.ArgumentParser(description="Deterministic Acceptance Benchmark Replay")
    parser.add_argument("--seed", type=int, default=1337, help="Seed for reproducibility replay")
    args = parser.parse_args()
    
    print("==================================================")
    print("Running release artifact schema validations...")
    print("==================================================")
    validate_json_schema("artifacts/r8_acceptance_report.json", "schemas/r8_acceptance_report.schema.json")
    validate_json_schema("artifacts/release_manifest_v0.4_research_alpha.json", "schemas/release_manifest.schema.json")
    validate_csv_schema("artifacts/r8_3_crossover_surface.csv", "schemas/r8_3_crossover_surface.schema.json")
    
    print("\n==================================================")
    print("Running acceptance benchmark replay...")
    print("==================================================")
    run_replay(args.seed)
    
    print("\nAll reproducibility contracts and validations PASSED.")
    sys.exit(0)

if __name__ == "__main__":
    main()
