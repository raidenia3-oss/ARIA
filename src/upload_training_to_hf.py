#!/usr/bin/env python3
"""One-time upload of aura_merged_training.jsonl to HuggingFace Hub.

Run from project root after setting HF_TOKEN env var:

    venv-training\Scripts\python upload_training_to_hf.py

or:

    set HF_TOKEN=hf_your_token_here
    venv-training\Scripts\python upload_training_to_hf.py
"""

import os
import sys

from huggingface_hub import HfApi

REPO_ID = "raiden456/aura-training-data"
FILENAME = "aura_merged_training.jsonl"


def main():
    token = os.environ.get("HF_TOKEN")
    if not token:
        print("ERROR: Set HF_TOKEN env var first.")
        print("  set HF_TOKEN=hf_your_token_here")
        print("  venv-training\\Scripts\\python upload_training_to_hf.py")
        sys.exit(1)

    if not os.path.exists(FILENAME):
        print(f"ERROR: {FILENAME} not found in project root.")
        sys.exit(1)

    api = HfApi()

    try:
        api.create_repo(repo_id=REPO_ID, repo_type="dataset", exist_ok=True, token=token)
        print(f"Created/confirmed dataset repo: {REPO_ID}")
    except Exception as e:
        print(f"Repo creation note: {e}")

    try:
        api.upload_file(
            path_or_fileobj=FILENAME,
            path_in_repo=FILENAME,
            repo_id=REPO_ID,
            repo_type="dataset",
            token=token,
            commit_message="Add 12,498 merged AURA training samples",
        )
        print(f"Uploaded {FILENAME} ({os.path.getsize(FILENAME)} bytes) to {REPO_ID}")
    except Exception as e:
        print(f"Upload failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
