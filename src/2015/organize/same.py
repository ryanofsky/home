#!/usr/bin/env python3

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
    try:
      stat1 = os.stat(filepath1)
      stat2 = os.stat(filepath2)
    except FileNotFoundError:
      #print("MISSING", relfile)
      continue
    if (stat.S_ISREG(stat1.st_mode)
        and stat.S_ISREG(stat2.st_mode)
        and int(stat1.st_mtime) == int(stat2.st_mtime)
        and stat1.st_size == stat2.st_size
        and subprocess.call(["cmp", "-s", filepath1, filepath2]) == 0):

      #if stat1.st_mtime != stat2.st_mtime:
      #  print("TOUCH", relfile, stat1.st_mtime, stat2.st_mtime)
      print(relfile)
    #else:
    #  print("DIFF", relfile)
