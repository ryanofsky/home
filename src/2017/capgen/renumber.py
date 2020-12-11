#!/usr/bin/env python

import sys
import re

next = 0 if len(sys.argv) < 2 else int(sys.argv[1])

def f(m):
  global next
  next += 1
  return "@" + str(next - 1)

sys.stdout.write(re.sub(r"@\d+", f, sys.stdin.read()))
