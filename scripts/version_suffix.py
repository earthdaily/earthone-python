"""
Script to update the version.py with a suffix e.g "b1" (Beta 1). Used before building library for pypi upload.
"""

import sys

file_path = sys.argv[1]
suffix = sys.argv[2].strip()

with open(file_path) as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if line.strip().startswith("__version__"):
        base_version = line.split("=")[1].strip().strip("\"'")
        print(f"{base_version = }")
        if suffix:
            new_version = f"{base_version}{suffix}"
            print(f"Adding suffix. {new_version = }")
            lines[i] = f'__version__ = "{new_version}"\n'
            break

with open(file_path, "w") as f:
    f.writelines(lines)
