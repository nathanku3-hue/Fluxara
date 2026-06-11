import hashlib
import os
import zipfile

def calculate_sha256(file_path):
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(8192):
            sha256.update(chunk)
    return sha256.hexdigest()

def main():
    target_files = [
        "artifacts/r8_acceptance_report.json",
        "artifacts/release_manifest_v0.4_research_alpha.json",
        "artifacts/release_manifest_v0.4.1_repro_alpha.json",
        "artifacts/release_tag_refs.json",
        "schemas/r8_acceptance_report.schema.json",
        "schemas/release_manifest.schema.json",
        "schemas/r8_3_crossover_surface.schema.json",
        "artifacts/r8_3_crossover_surface.csv",
        "artifacts/r8_3_falsification_benchmarks.md",
        "artifacts/benchmarks.md",
        "requirements.lock.txt",
        "constraints.txt",
        "scripts/replay_acceptance.py",
        "docs/R8_4_REPRODUCIBILITY.md",
    ]
    
    # 1. Verify files exist and calculate checksums
    print("Calculating checksums for bundle files...")
    checksum_lines = []
    for f_path in target_files:
        if not os.path.exists(f_path):
            print(f"Error: Target file {f_path} does not exist.")
            return False
        checksum = calculate_sha256(f_path)
        # Store relative paths in unified forward-slash format
        normalized_path = f_path.replace("\\", "/")
        checksum_lines.append(f"{checksum}  {normalized_path}\n")
        print(f"  {normalized_path}: {checksum}")
        
    # Write SHA256SUMS file
    sums_file = "SHA256SUMS"
    with open(sums_file, "w", encoding="utf-8") as sf:
        sf.writelines(checksum_lines)
    print(f"✓ Wrote {sums_file}")
    
    # 2. Package ZIP archive
    zip_path = "artifacts/fluxara_external_audit_bundle_v0.4.1.zip"
    os.makedirs("artifacts", exist_ok=True)
    
    print(f"Creating ZIP archive at {zip_path}...")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        # Write the checksums manifest file inside the zip root
        zipf.write(sums_file, arcname=sums_file)
        
        # Write all benchmark and configuration files preserving relative structure
        for f_path in target_files:
            normalized_path = f_path.replace("\\", "/")
            zipf.write(f_path, arcname=normalized_path)
            
    print("✓ ZIP archive successfully created.")
    
    # Clean up the local SHA256SUMS file after packaging
    if os.path.exists(sums_file):
        os.remove(sums_file)
        
    # 3. Calculate and write zip checksum
    zip_checksum = calculate_sha256(zip_path)
    zip_checksum_path = f"{zip_path}.sha256"
    with open(zip_checksum_path, "w", encoding="utf-8") as zcf:
        zcf.write(f"{zip_checksum}  {os.path.basename(zip_path)}\n")
    print(f"✓ Wrote archive checksum to {zip_checksum_path} ({zip_checksum})")
    print("Export complete.")
    return True

if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)
