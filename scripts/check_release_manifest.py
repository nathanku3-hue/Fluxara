import json
import os
import subprocess
import sys

def check_single_manifest(manifest_path, tag_name):
    print(f"\nValidating manifest: {manifest_path} (Expected Tag: {tag_name})")
    if not os.path.exists(manifest_path):
        print(f"Error: Manifest not found at {manifest_path}")
        sys.exit(1)
        
    with open(manifest_path, "r", encoding="utf-8") as f:
        try:
            manifest = json.load(f)
        except Exception as e:
            print(f"Error: Failed to parse manifest JSON: {e}")
            sys.exit(1)
            
    # 1. Check CI run id
    ci_run_id = manifest.get("ci_run_id")
    if not ci_run_id:
        print("Error: Missing or empty ci_run_id in manifest")
        sys.exit(1)
    print(f"  ✓ Verified ci_run_id: {ci_run_id}")
        
    # 2. Check artifact paths exist
    report_path = manifest.get("acceptance_report_path")
    if not report_path or not os.path.exists(report_path):
        print(f"Error: Acceptance report path {report_path} not found")
        sys.exit(1)
    print(f"  ✓ Verified report path: {report_path}")
        
    for p in manifest.get("benchmark_artifact_paths", []):
        if not os.path.exists(p):
            print(f"Error: Benchmark artifact path {p} not found")
            sys.exit(1)
        print(f"  ✓ Verified benchmark path: {p}")
        
    for p in manifest.get("schema_paths", []):
        if not os.path.exists(p):
            print(f"Error: Schema path {p} not found")
            sys.exit(1)
        print(f"  ✓ Verified schema path: {p}")
        
    replay_script = manifest.get("replay_script_path")
    if replay_script:
        if not os.path.exists(replay_script):
            print(f"Error: Replay script path {replay_script} not found")
            sys.exit(1)
        print(f"  ✓ Verified replay script path: {replay_script}")
        
    for p in manifest.get("lock_paths", []):
        if not os.path.exists(p):
            print(f"Error: Lock/constraints path {p} not found")
            sys.exit(1)
        print(f"  ✓ Verified lock/constraints path: {p}")
            
    # 3. Check commit matches HEAD, HEAD~1, or tag_commit
    manifest_commit = manifest.get("commit")
    if not manifest_commit:
        print("Error: Missing commit in manifest")
        sys.exit(1)
        
    try:
        head_commit = subprocess.check_output(["git", "rev-parse", "HEAD"]).decode("utf-8").strip()
    except Exception as e:
        print(f"Error: Failed to get HEAD commit: {e}")
        sys.exit(1)
        
    try:
        parent_commit = subprocess.check_output(["git", "rev-parse", "HEAD~1"]).decode("utf-8").strip()
    except Exception:
        parent_commit = None
        
    try:
        tag_commit = subprocess.check_output(["git", "rev-parse", tag_name]).decode("utf-8").strip()
    except Exception:
        tag_commit = None
        
    print(f"  Manifest commit: {manifest_commit}")
    print(f"  HEAD commit:     {head_commit}")
    print(f"  Parent commit:   {parent_commit}")
    print(f"  Tag commit:      {tag_commit}")
    
    if manifest_commit != head_commit and manifest_commit != tag_commit and manifest_commit != parent_commit:
        print(f"Error: Manifest commit {manifest_commit} does not match HEAD ({head_commit}), Parent ({parent_commit}), or tag ({tag_commit})")
        sys.exit(1)
        
    print(f"  ✓ Manifest {manifest_path} is consistent.")

def main():
    try:
        subprocess.run(["git", "fetch", "--tags"], capture_output=True)
    except Exception as e:
        print(f"Warning: failed to fetch tags: {e}")

    check_single_manifest("artifacts/release_manifest_v0.4_research_alpha.json", "v0.4-research-alpha")
    check_single_manifest("artifacts/release_manifest_v0.4.1_repro_alpha.json", "v0.4.1-repro-alpha")
    
    print("\nAll release manifests passed validation successfully.")
    sys.exit(0)

if __name__ == "__main__":
    main()
