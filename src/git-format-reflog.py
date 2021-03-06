#!/usr/bin/env python

import os.path
import sys
import re
import email.utils
import datetime
import subprocess

def getsubj(str):
  return str.split(": ", 1)[1]

def popen(cmd, git_dir=None):
  env = None
  if git_dir:
    env = os.environ.copy()
    env["GIT_DIR"] = os.path.abspath(git_dir)
  return subprocess.Popen(cmd, shell=isinstance(cmd, basestring), stdout=subprocess.PIPE, env=env).stdout

def bash_base(path, commit):
  return (popen(["git-echo-base.sh", commit], path).read().strip(),
          popen(["git-echo-cl.sh", commit], path).read().strip())

def bash_syms(path, commit):
  min = None
  min_key = None
  for line in popen(["git-echo-commit-name.sh", commit], path):
    exact, desc, rhash = line.strip().split()
    exact = bool(int(exact))
    m = re.search(r"(?:work|export)-.+?\.(\d+)", desc)
    key = int(m.group(1)) if m else ""
    key = key, "work-" not in desc, "export-" not in desc
    if min_key is None or key < min_key:
      min_key = key
      min = exact, desc, rhash
  return [min] if min else []

def bash_lines(path, *revs):
  return popen(("ocd-diffstat-lines.sh",) + revs, path).read().strip()

def geturl(path, h, hp=None, log=False):
  proj = os.path.basename(os.path.dirname(path))
  parts = ["p={}".format(proj), "a={}".format("log" if log else "commitdiff"),
           "h={}".format(h)]
  if hp:
    parts.append("hp={}".format(hp))
  return "http://ryanofsky:3000/gitweb/?{}".format(";".join(parts))

def reflog(path, raw_print, pretty_print, filter_date):
  prev = {}
  head = None
  first = True
  for branch, old, new, user, date, log in crawl(path):
    if snip:
      date_ok = filter_date is None or filter_date <= datetime.date.fromtimestamp(date)
    else:
      date_ok = filter_date is None or filter_date == datetime.date.fromtimestamp(date)

    m = log and _re_checkout.match(log)
    if m:
      old_head, new_head = m.groups()
      if date_ok and not (head is None or old_head == head or new_head == head):
        if first and not snip:
          print "=== %s ===" % path
          first = False
        print >> sys.stderr, ("Error path=%r head=%r old_head=%r, new_head=%r" %
            (path, head, old_head, new_head))
      head = branch_name(new_head)
    if branch == "HEAD":
      branch_s = "(%s)" % head
    else:
      branch_s = branch
    branch_s = "%-16s" % branch_s
    date_s = email.utils.formatdate(int(date), True)
    old_s = old[:7] if old != prev.get(branch) else "-------"
    new_s = new[:7]
    if raw_print:
      if date_ok:
        if snip:
          type = None
          if not log:
            pass
          elif log.startswith("cherry-pick: {}".format(branch_s)):
            # Maybe print this with [export] and cl number
            pass
          elif log.startswith("commit (amend):"):
            type = "amend"
            msg = getsubj(log)
            url = geturl(path, new, old)
            lines = bash_lines(path, old, new)
          elif log.startswith("commit:"):
            type = "commit"
            msg = getsubj(log)
            url = geturl(path, new)
            lines = bash_lines(path, new)
          else:
            m = re.match("rebase.*?finish.*?onto", log)
            if m:
              url = geturl(path, new, old)
              b1, cl1 = bash_base(path, old)
              b2, cl2 = bash_base(path, new)
              lines = bash_lines(path, b1, old, b2, new)
              msg = "[[{}][@{}]]".format(geturl(path, b2, log=True), cl2)
              if b1 == b2:
                type = "rebase"
              else:
                type = "overlay" if cl1 == cl2 else "sync"
                msg += " from [[{}][@{}]]".format(geturl(path, b1, log=True), cl1)
          if type:
            print "{time:%m-%d %H:%M} [[{url}][{type}]] {lines} {sym}{msg}".format(
              time = datetime.datetime.fromtimestamp(int(date)),
              url=url, type=type, lines=lines,
              sym=", ".join("[[{}][{}{}]]".format(
                  geturl(path, rhash, log=True), describe,
                  ("" if exact else "*"))
                  for exact, describe, rhash in bash_syms(path, new))
              or "orphaned from [[{}][{}]]".format(
                  geturl(path, head if branch == "HEAD" else branch, log=True), branch_s.strip()),
              msg=msg and " {}".format(msg) or "")
        else:
          if first:
            print "=== %s ===" % path
            first = False
          print branch_s, date_s, old_s, new_s, log
    prev[branch] = new

def crawl(repo):
  # name, fp, row
  branches = [["HEAD",
               open(os.path.join(repo, "logs/HEAD")),
               None]]
  if os.path.islink((os.path.join(repo, "logs/refs"))):
    print >> sys.stderr, "Skipping repo %r refs" % repo
  else:
    for head in os.listdir(os.path.join(repo, "logs/refs/heads")):
      if not os.path.isfile(os.path.join(repo, "logs/refs/heads", head)):
        continue
      branches.append([head,
                       open(os.path.join(repo, "logs/refs/heads", head)),
                       None])
  current_date = None
  while branches:
    earliest_date = None
    for info in branches:
      branch, fp, row = info
      if row is None:
        line = fp.readline()
        if not line:
          fp.close()
          branches.remove(info)
          continue
        old, new, user, date, log = _re_reflog.match(line).groups()
        date = int(date)
      else:
        old, new, user, date, log = row
      if earliest_date is None or date < earliest_date:
        earliest_date = date
      if date == current_date:
        yield branch, old, new, user, date, log
        info[2] = None
        break
      else:
        info[2] = old, new, user, date, log
    current_date = earliest_date

def branch_name(ref):
  if _re_scommit.match(ref) or _re_commit.match(ref):
    return None
  return ref

_re_reflog = re.compile(r"^([0-9a-z]{40}) ([0-9a-z]{40}) ([^>]+>) "
                        r"(\d+) [+-]\d{4}(?:\t(.*))?$")
_re_checkout = re.compile(r"^checkout: moving from (.*?) to (.*)$")
_re_scommit = re.compile(r"^[0-9a-f]{7}$")
_re_commit = re.compile(r"^[0-9a-f]{40}(\^\d+)?$")

if __name__ == "__main__":
  snip = False
  if sys.argv[-1] == "+":
    snip = True
    sys.argv.pop()
  try:
    DATE = datetime.datetime.strptime(sys.argv[-1], "%Y/%m/%d").date()
    repos = sys.argv[1:-1]
  except ValueError:
    DATE = None
    repos = sys.argv[1:]

  for REPO in repos:
    RAW = False
    RAW = True
    PRETTY = False
    PRETTY = True
    reflog(REPO, RAW, PRETTY, DATE)
