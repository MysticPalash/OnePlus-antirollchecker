#!/usr/bin/env python3
import json
import os
import requests
from config import DEVICE_METADATA
from fetch_firmware import get_springer_versions

def generate_backfill_matrix():
    include_list = []
    
    target_device = os.environ.get("TARGET_DEVICE", "").strip().lower()
    target_variant = os.environ.get("TARGET_VARIANT", "").strip().lower()
    
    session = requests.Session()
    
    for device_id, meta in DEVICE_METADATA.items():
        if target_device and target_device != device_id.lower() and target_device != meta['name'].lower():
            continue
            
        valid_regions = meta.get('models', {}).keys()
        
        for region in valid_regions:
            if target_variant and target_variant != region.lower():
                continue
                
            print(f"Checking versions for {device_id} {region}...")
            res = get_springer_versions(device_id, region, session)
            
            if not res:
                continue
            
            versions, _ = res
            
            # Take top 5 versions (Springer usually lists newest first)
            target_versions = versions[:5]
            
            for version in target_versions:
                # We need to extract the version string carefully 
                # as Springer might return "Version (Date)"
                # But fetch_firmware.py handles substrings so it's fine
                
                include_list.append({
                    "device": device_id,
                    "variant": region,
                    "device_short": device_id,
                    "device_name": meta['name'],
                    "version": version
                })
                
    # Output for GitHub Actions
    matrix_json = json.dumps({"include": include_list})
    
    if "GITHUB_OUTPUT" in os.environ:
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"matrix={matrix_json}\n")
    else:
        print(matrix_json)

if __name__ == "__main__":
    generate_backfill_matrix()
