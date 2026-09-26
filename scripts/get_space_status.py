import os
import sys
import json
import requests

# Get token from command line argument or environment variable
token = sys.argv[1] if len(sys.argv) > 1 else os.getenv("HF_TOKEN")

if not token:
    print("Error: HF_TOKEN environment variable not set or token not provided as argument.")
    sys.exit(1)

repo = "raiden456/raiden456aura-chat"
url = f"https://huggingface.co/api/spaces/{repo}"
headers = {"Authorization": f"Bearer {token}"}

try:
    response = requests.get(url, headers=headers)
    response.raise_for_status()  # Raise an exception for HTTP errors
    data = response.json()

    runtime = data.get("runtime", {})
    stage = runtime.get("stage", "N/A")
    error = runtime.get("error", "N/A")
    logs_url = runtime.get("logsUrl", "N/A")
    space_url = f"https://raiden456-raiden456aura-chat.hf.space"

    print(f"Stage: {stage}")
    print(f"Error: {error}")
    print(f"Logs URL: {logs_url}")
    print(f"Space URL: {space_url}")

except requests.exceptions.RequestException as e:
    print(f"Error fetching space status: {e}")
    sys.exit(1)
except json.JSONDecodeError:
    print("Error: Could not decode JSON response from Hugging Face API.")
    sys.exit(1)
