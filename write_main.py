#!/usr/bin/env python3
"""Write content to a file. Usage: python write_main.py <filepath> <content_file>"""
import sys
import os

if len(sys.argv) < 3:
    print("Usage: python write_main.py <filepath> <content_file>")
    sys.exit(1)

filepath = sys.argv[1]
content_file = sys.argv[2]

with open(content_file, 'r', encoding='utf-8') as f:
    content = f.read()

os.makedirs(os.path.dirname(filepath), exist_ok=True)
with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print(f"Wrote {len(content)} bytes to {filepath}")