import json
import os
from config import DEVICE_METADATA
import argparse

def is_version_already_checked(device_id, region, latest_version):
    history_file = os.path.join("data", "history", f"{device_id}_{region}.json")
    if not os.path.exists(history_file):
        return False
    try:
        with open(history_file, "r") as f:
            data = json.load(f)
            if data and "history" in data and len(data["history"]) > 0:
                if data["history"][0]["version"] == latest_version:
                    return True
    except Exception as e:
        print(f"Error reading history for {device_id} {region}: {e}")
    return False

def generate_matrix(filter_unchanged=False):
    include_list = []
    
    # Temporary exclusions for failing devices
    EXCLUDE = [
        ("Find X8 Pro", "IN"), ("Find X8 Pro", "EU"), ("Find X8 Pro", "CN"),
        ("Find X8", "CN"), ("Find X8", "IN"),
        ("Find N3", "IN"), # Fails in check-variant
        ("9R", "IN"),
        ("10R", "IN"),
        ("Ace 5 Ultimate", "CN"),
        ("Find X5", "CN"),
        ("Find X5 Pro", "CN")
    ]

    for device_id, meta in DEVICE_METADATA.items():
        # Get all valid regions from the 'models' dictionary keys
        valid_regions = meta.get('models', {}).keys()
        
        for region in valid_regions:
            if (device_id, region) in EXCLUDE:
                continue
                
            if filter_unchanged:
                try:
                    from fetch_firmware import get_from_oos_api, get_signed_url_springer
                    
                    # Same resolution logic as fetch_firmware.py
                    clean_device_id = device_id.replace("oneplus_", "")
                    
                    print(f"Pre-checking {clean_device_id} {region} for updates...")
                    result = get_from_oos_api(clean_device_id, region)
                    if not result:
                        result = get_signed_url_springer(clean_device_id, region)
                        
                    if result and "version" in result:
                        latest_version = result["version"]
                        if is_version_already_checked(device_id, region, latest_version):
                            print(f"Skipping {device_id} {region}, already checked version: {latest_version}")
                            continue
                        else:
                            print(f"New version found for {device_id} {region}: {latest_version}")
                except Exception as e:
                    print(f"Failed to check {device_id} {region} during matrix generation: {e}")
                    # On failure, include it in matrix to be safe
                
            include_list.append({
                "device": device_id,
                "variant": region,
                "device_short": device_id,
                "device_name": meta['name']
            })
            
    # Output for GitHub Actions
    matrix_json = json.dumps({"include": include_list})
    
    # Write to GITHUB_OUTPUT if available, else print
    if "GITHUB_OUTPUT" in os.environ:
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"matrix={matrix_json}\n")
    else:
        print(matrix_json)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate GitHub Actions matrix.")
    parser.add_argument("--filter-unchanged", action="store_true", help="Filter out variants that already have the latest version in history")
    args = parser.parse_args()
    
    generate_matrix(filter_unchanged=args.filter_unchanged)
