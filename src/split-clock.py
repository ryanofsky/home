#!/usr/bin/python

import sys
import re

l = sys.stdin.readline()

m = re.compile("(.*?)(\\[[0-9]{4}-[0-9]{2}-[0-9]{2} [A-Z][a-z]{2} [0-9]{2}:[0-9]{2})(]--)(\\[[0-9]{4}-[0-9]{2}-[0-9]{2} [A-Z][a-z]{2} )([0-9]{2}:[0-9]{2})(].*)", re.DOTALL).match(l)
if m:
  prefix, first, sep, date, time, suffix = m.groups()
  stime = sys.argv[1] if len(sys.argv) > 1 else time
  sys.stdout.write(prefix + first + sep + date + stime + suffix + prefix + date + stime + sep + date + time + suffix)
else:
  sys.stdout.write(l)
sys.stdout.write(sys.stdin.read())
