#!/usr/bin/python

import portage
import getopt
import sys
import os
import subprocess
import re
import md5

def usage():
  print "Usage: pkgclean.py [OPTIONS] DIRECTORY"
  print
  print "Remove application files from an old gentoo install"
  print
  print "Options:"
  print "  -p, --pretend  Don't change files, just print what would be done"
  print "  -v, --verbose  Print verbose output"
  print "  -h, --help     Display this help"

def error(s):
  print >> sys.stderr, "Error:", s
  print >> sys.stderr, "(run `pkgclean.py --help' for help)"
  sys.exit(1)

def main():
  pretend = False
  verbose = False

  short_opts = "pvh"
  long_opts = ["pretend", "verbose", "help"]

  try:
    opts, args = getopt.getopt(sys.argv[1:], short_opts, long_opts)
  except getopt.GetoptError, e:
    error(str(e))

  for o, a in opts:
    if o in ("-p", "--pretend"):
      pretend = True
    elif o in ("-v", "--verbose"):
      verbose += 1
    elif o == "--help":
      usage()
      sys.exit()

  if len(args) != 1 or not os.path.isdir(args[0]):
    error("expected one directory argument")

  root = args[0]
  db = os.path.join(root, "var/db/pkg")

  for file, sum, time, pkg in files(db):
    filepath = os.path.join(root, file)
    if os.path.isfile(filepath):
      if sum == md5sum(filepath):
        s = "D"
        if not pretend:
          os.unlink(filepath)
        elif not os.access(filepath, os.W_OK):
          error("Bad permissions on %s" % filepath)
      else:
        s = "M"
    else:
      s = "!"
    print "%s %s %s" % (s, pkg, filepath)

def files(db):
  "yields file, md5sum, time pkg"
  for category in os.listdir(db):
    catdir = os.path.join(db, category)
    if not os.path.isdir(catdir):
      continue
    for package in os.listdir(catdir):
      pkgdir = os.path.join(catdir, package)
      cntfile = os.path.join(pkgdir, "CONTENTS")
      if not os.path.isdir(pkgdir) or not os.path.isfile(cntfile):
        continue
      cnt = open(cntfile, "rt")
      while True:
        line = cnt.readline()
        if not line:
          break
        if not line.startswith("obj "):
          continue
        m = re.match("^obj /+(.*?) ([^ ]{32}) ([0-9]+)$", line)
        file, md5sum, time = m.groups()
        time = int(time)
        yield file, md5sum, time, "%s/%s" % (category, package)
      cnt.close()

def md5sum(path):
  fp = open(path, "rb")
  try:
    m = md5.new()
    while True:
      chunk = fp.read(65536)
      if not chunk:
        break
      m.update(chunk)
    return m.hexdigest()
  finally:
    fp.close()

if __name__ == "__main__":
  main()
