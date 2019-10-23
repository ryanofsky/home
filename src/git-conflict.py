#!/usr/bin/python3

import sys
import re
import pathlib
import subprocess

_r = re.compile(r"^<<<<<<<[^\n]*\n(.*?)\|\|\|\|\|\|\|[^\n]*\n(.*?)=======[^\n]*\n(.*?)>>>>>>>[^\n]*\n", re.DOTALL | re.M)

def sub(m):
    d1, d2, d3 = m.groups()
    if d1 == d2:
        return d3
    elif d2 == d3 or d1 == d3:
        return d1
    conflict(d1, d2, d3)
    return m.group(0)

def conflict(d1, d2, d3):
    global fp1, fp2, fp3, f
    for fp, d in ((fp1, d1), (fp2, d2), (fp3, d3)):
        with fp.open("at") as out:
            out.write(f":::::: {f} ::::::\n{d}\n")

fp1 = pathlib.Path("d1")
fp2 = pathlib.Path("d2")
fp3 = pathlib.Path("d3")
if fp1.is_file() and fp2.is_file() and fp3.is_file(): fp1.unlink(), fp2.unlink(), fp3.unlink()


if len(sys.argv) == 1:
    args = subprocess.check_output("git diff --name-only --diff-filter=U".split()).decode("utf8").rstrip("\n").split("\n")
    print(f"Conflicts: {args!r}")
else:
    args = sys.argv[1:]

for f in args:
    with open(f) as fp:
        s = fp.read()
    with open(f, "w") as fp:
        fp.write(_r.sub(sub, s))
