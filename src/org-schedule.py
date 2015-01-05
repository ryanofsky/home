#!/usr/bin/env python

import datetime
import re
import sys

_re = re.compile(r"SCHEDULED: <(\d{4})-(\d{2})-(\d{2}) [A-Z][a-z]{2}\b")

def replace(txt):
  orig_dates = []
  count = 0

  def fill_dates(m):
    orig_date = datetime.date(*map(int, m.groups()))
    if orig_date.year >= 2020:
      orig_dates.append((orig_date, m.group(0)))

  _re.sub(fill_dates, txt)
  orig_dates.sort()

  new_dates = {}
  prev_orig_date = None
  date = None
  for orig_date, orig_str in orig_dates:
    if prev_orig_date is None or prev_orig_date.year != orig_date.year:
      date = datetime.date(orig_date.year, 1, 2)
    elif prev_orig_date != orig_date:
      date += datetime.timedelta(2)
    new_dates[orig_str] = "SCHEDULED: <{:%Y-%m-%d %a}".format(date)
    prev_orig_date = orig_date

  def sub_dates(m):
    str = m.group(0)
    return new_dates.get(str) or str

  return _re.sub(sub_dates, txt)

def main():
  files = sys.argv[1:]
  if files:
    for f in files:
      with open(f) as fp:
        txt = replace(fp.read())
      with open(f, "w") as fp:
        fp.write(txt)
  else:
    sys.stdout.write(replace(sys.stdin.read()))

if __name__ == "__main__":
  main()
