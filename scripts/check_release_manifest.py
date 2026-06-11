import json
import os
import subprocess
import sys

def main():
    manifest_path = "artifacts/release_manifest_v0.4_research_alpha.json"
    if not os.path.exists(manifest_path):
        print(f"Manifest not found at {manifest_path}")
        sys.exit(1)
        
    with open(manifest_path, "r", encoding="utf-8") as f:
        try:
            manifest = json.load(f)
        except Exception as e:
            print(f"Failed to parse manifest JSON: {e}")
            sys.exit(1)
            
    # 1. Check CI run id
    ci_run_id = manifest.get("ci_run_id")
    if not ci_run_id:
        print("Missing or empty ci_run_id in manifest")
        sys.exit(1)
    print(f"Verified ci_run_id: {ci_run_id}")
        
    # 2. Check artifact paths exist
    report_path = manifest.get("acceptance_report_path")
    if not report_path or not os.path.exists(report_path):
        print(f"Acceptance report path {report_path} not found")
        sys.exit(1)
    print(f"Verified report path: {report_path}")
        
    benchmark_paths = manifest.get("benchmark_artifact_paths", [])
    for p in benchmark_paths:
        if not os.path.exists(p):
            print(f"Benchmark artifact path {p} not found")
            sys.exit(1)
        print(f"Verified benchmark path: {p}")
            
    # 3. Check commit matches HEAD or the v0.4-research-alpha tag target
    manifest_commit = manifest.get("commit")
    if not manifest_commit:
        print("Missing commit in manifest")
        sys.exit(1)
        
    try:
        subprocess.run(["git", "fetch", "--tags"], capture_output=True)
    except Exception as e:
        print(f"Warning: failed to fetch tags: {e}")

    try:
        head_commit = subprocess.check_output(["git", "rev-parse", "HEAD"]).decode("utf-8").strip()
    except Exception as e:
        print(f"Failed to get HEAD commit: {e}")
        sys.exit(1)
        
    try:
        tag_commit = subprocess.check_output(["git", "rev-parse", "v0.4-research-alpha"]).decode("utf-8").strip()
    except Exception:
        tag_commit = None
        
    print(f"Manifest commit: {manifest_commit}")
    print(f"HEAD commit:     {head_commit}")
    print(f"Tag commit:      {tag_commit}")
    
    if manifest_commit != head_commit and manifest_commit != tag_commit:
        print(f"Manifest commit {manifest_commit} does not match HEAD ({head_commit}) or v0.4-research-alpha tag ({tag_commit})")
        sys.exit(1)
        
    print("Manifest check passed successfully.")
    sys.exit(0)

if __name__ == "__main__":
    main()
