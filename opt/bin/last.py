#!/usr/bin/python

import sys
import os
import time

def main(d):
  path = modified = None
  for dirpath, dirnames, filenames in os.walk(d):
    for filename in filenames:
      p = os.path.join(dirpath, filename)
      t = os.path.getmtime(p)
      if modified is None or t > modified:
        modified = t
        path = p
  print time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(modified)), path


if __name__ == "__main__":
  main(sys.argv[1])
