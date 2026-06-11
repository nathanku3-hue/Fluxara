import hashlib
import os
import tempfile
import zipfile

def calculate_sha256(file_path):
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(8192):
            sha256.update(chunk)
    return sha256.hexdigest()

def main():
    zip_path = "artifacts/fluxara_external_audit_bundle_v0.4.1.zip"
    zip_checksum_path = f"{zip_path}.sha256"
    
    # 1. Verify zip checksum path exists and matches
    if not os.path.exists(zip_path):
        print(f"Error: ZIP file {zip_path} not found.")
        return False
    if not os.path.exists(zip_checksum_path):
        print(f"Error: Checksum file {zip_checksum_path} not found.")
        return False
        
    with open(zip_checksum_path, "r", encoding="utf-8") as f:
        content = f.read().strip()
        expected_zip_checksum = content.split()[0]
        
    actual_zip_checksum = calculate_sha256(zip_path)
    print(f"Verifying ZIP checksum:")
    print(f"  Expected: {expected_zip_checksum}")
    print(f"  Actual:   {actual_zip_checksum}")
    if actual_zip_checksum != expected_zip_checksum:
        print("Error: ZIP archive checksum mismatch!")
        return False
    print("✓ ZIP archive checksum verified successfully.")
    
    # 2. Extract and verify internal files
    with tempfile.TemporaryDirectory() as tmpdir:
        print(f"Extracting archive contents to temporary directory: {tmpdir}...")
        with zipfile.ZipFile(zip_path, "r") as zipf:
            zipf.extractall(tmpdir)
            
        sums_file = os.path.join(tmpdir, "SHA256SUMS")
        if not os.path.exists(sums_file):
            print("Error: SHA256SUMS file not found inside ZIP archive!")
            return False
            
        print("Verifying individual file checksums inside bundle...")
        with open(sums_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split(None, 1)
                if len(parts) < 2:
                    continue
                expected_hash, rel_path = parts
                
                # Check path existance inside temp directory
                full_path = os.path.join(tmpdir, rel_path)
                if not os.path.exists(full_path):
                    print(f"Error: File {rel_path} listed in checksum manifest was not extracted!")
                    return False
                    
                actual_hash = calculate_sha256(full_path)
                if actual_hash != expected_hash:
                    print(f"Error: Checksum mismatch for {rel_path}!")
                    print(f"  Expected: {expected_hash}")
                    print(f"  Actual:   {actual_hash}")
                    return False
                print(f"  ✓ {rel_path}: OK")
                
    print("\n✓ All bundle files verified successfully against SHA256 signatures.")
    return True

if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)
