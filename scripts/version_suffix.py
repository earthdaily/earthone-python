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
        base_version = line.split("=")[1].strip().strip('"\'')
        lines[i] = f'__version__ = "{base_version}{suffix}"\n'
        break

with open(file_path, "w") as f:
    f.writelines(lines)