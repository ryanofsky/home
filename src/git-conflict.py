#!/usr/bin/python3

import sys
import re

_r = re.compile(r"^<<<<<<<[^\n]*\n(.*?)\|\|\|\|\|\|\|[^\n]*\n(.*?)=======[^\n]*\n(.*?)>>>>>>>[^\n]*\n", re.DOTALL | re.M)

def sub(m):
    d1, d2, d3 = m.groups()
    if d1 == d2:
        return d3
    elif d2 == d3 or d1 == d3:
        return d1
    return m.group(0)

for f in sys.argv[1:]:
    with open(f) as fp:
        s = fp.read()
    with open(f, "w") as fp:
        fp.write(_r.sub(sub, s))
