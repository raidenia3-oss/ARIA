"""
Merge all AURA training data into a single JSONL file for Colab training.
This script combines all training-data-*.jsonl files into one merged file.
"""

import json
import glob
import os
from pathlib import Path


def merge_training_data(output_file="aura_merged_training.jsonl", max_samples=None):
    """
    Merge all training data JSONL files into a single file.
    
    Args:
        output_file: Output filename for merged data
        max_samples: Maximum number of samples to include (None for all)
    """
    project_root = Path(__file__).parent.parent
    data_files = sorted(glob.glob(str(project_root / "training-data-*.jsonl")))
    
    # Also include main training-data.jsonl if it exists
    main_file = project_root / "training-data.jsonl"
    if main_file.exists():
        data_files = [str(main_file)] + data_files
    
    print(f"Found {len(data_files)} training data files:")
    for f in data_files:
        print(f"  - {os.path.basename(f)}")
    
    merged_data = []
    total_skipped = 0
    
    for filepath in data_files:
        filename = os.path.basename(filepath)
        print(f"\nProcessing: {filename}")
        
        with open(filepath, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                
                try:
                    entry = json.loads(line)
                    
                    # Normalize different formats to standard instruction format
                    if "text" in entry and "output" in entry:
                        # AURA format: text=input, output=response
                        merged_data.append({
                            "instruction": entry["text"],
                            "input": "",
                            "output": entry["output"]
                        })
                    elif "instruction" in entry and "output" in entry:
                        # Already in Alpaca format
                        merged_data.append({
                            "instruction": entry["instruction"],
                            "input": entry.get("input", ""),
                            "output": entry["output"]
                        })
                    else:
                        total_skipped += 1
                        
                except json.JSONDecodeError:
                    total_skipped += 1
                    continue
                
                if max_samples and len(merged_data) >= max_samples:
                    print(f"  Reached max_samples limit ({max_samples})")
                    break
        
        print(f"  Loaded so far: {len(merged_data)} samples")
        
        if max_samples and len(merged_data) >= max_samples:
            break
    
    # Write merged data
    output_path = project_root / output_file
    with open(output_path, 'w', encoding='utf-8') as f:
        for entry in merged_data:
            line = json.dumps(entry, ensure_ascii=False)
            f.write(line)
            f.write('\n')
    
    print(f"\n{'='*50}")
    print(f"[OK] Merged {len(merged_data)} samples")
    print(f"[WARN] Skipped {total_skipped} invalid entries")
    print(f"[FILE] Output: {output_path}")
    print(f"[INFO] File size: {output_path.stat().st_size / 1024 / 1024:.2f} MB")
    print(f"{'='*50}")
    
    return str(output_path)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Merge AURA training data for Colab")
    parser.add_argument("--output", default="aura_merged_training.jsonl", help="Output filename")
    parser.add_argument("--max-samples", type=int, default=None, help="Max samples to include")
    
    args = parser.parse_args()
    
    merge_training_data(args.output, args.max_samples)
