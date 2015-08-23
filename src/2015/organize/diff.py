#!/usr/bin/python3

import sys
import os
import subprocess
import stat

assert len(sys.argv) == 3
dir1 = sys.argv[1]
dir2 = sys.argv[2]
assert os.path.isdir(dir1)
assert os.path.isdir(dir2)

for root, dirs, files in os.walk(dir1):
  relroot = os.path.relpath(root, dir1)
  for filename in files:
    relfile = os.path.join(relroot, filename)
    filepath1 = os.path.join(dir1, relfile)
    filepath2 = os.path.join(dir2, relfile)
    if not os.path.exists(filepath2):
      print("||| missing ", filepath2, file=sys.stderr)
      filepath2 = "/dev/null"
    print("diff", filepath1, filepath2)
    sys.stdout.flush()
    subprocess.call(["diff", filepath1, filepath2])
