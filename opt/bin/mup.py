#!/usr/bin/env python3

"""Backup script"""

import sys
import subprocess
import argparse
import inspect
import re
import contextlib
import itertools

# TMPDIR= old save bup_dir name dir_path --exclude-from --pretend
# TMPDIR= old verify bup_dir name dir_path --exclude-from --pretend

# old encrypted dir
# find -name .encfs*
# old fat dir
# find / -type f -size +20M -printf 'size name' | sort -n
# old media dir
# find mp3

def main():
  parser = CommandParser()
  parser.add_argument("-p", "--pretend", action="store_true")
  parser.add_commands((Russ, Russp, Old))
  parser.run()

class Russ:
  def run(self, args):
    subprocess.call(["rsync", "-avH", "--delete",
                    ] + (args.pretend and ["--dry-run"] or []) + [
                     "/home/russ/.TaskCoach/tasks.tsk",
                     "/mnt/russp/info/task/tasks.tsk"])

class Russp:
  def run(self, args):
    subprocess.call(["rsync", "-avH", "--delete",
                    ] + (args.pretend and ["--dry-run"] or []) + [
                     "/mnt/russp/.keys/",
                     "/mnt/bup/russp.keys/"])
    subprocess.call(["rsync", "-avH", "--delete",
                    ] + (args.pretend and ["--dry-run"] or []) + [
                     "/mnt/russp/.git/",
                     "/mnt/bup/russp.git/"])

class Old:
  @classmethod
  def add_arguments(cls, parser):
    parser.add_commands((Save, Verify))

class OldCommand:
  @classmethod
  def add_arguments(cls, parser):
    parser.add_argument("--exclude-from")
    parser.add_argument("bup_dir")
    parser.add_argument("name")
    parser.add_argument("dir_path")

class Save(OldCommand):
  def run(self, args):
    print("cmd--old--save", args)

class Verify(OldCommand):
  def run(self, args):
    print("cmd--old--verify", args)

def human(num):
  for x in ['','K','M','G']:
    if num < 1024:
      break
    num /= 1024.0
  else:
    x = 'T'
  if num < 10:
    return "%.2f%s" % (num, x)
  elif num < 100:
    return "%.1f%s" % (num, x)
  else:
    return "%.0f%s" % (num, x)

class CommandParser(argparse.ArgumentParser):
  def add_commands(self, commands, *args, **kwargs):
    subparsers = self.add_subparsers(*args, **kwargs)
    for command in commands:
      if hasattr(command, "subparser"):
        subparser = command.subparser(subparsers)
      else:
       name = re.sub("(.)([A-Z])", r"\1_\2", command.__name__).lower()
       subparser = subparsers.add_parser(name)
      if hasattr(command, "add_arguments"):
        command.add_arguments(subparser)
      if hasattr(command, "run"):
        subparser.set_defaults(command=command)

  def run(self):
    args = self.parse_args()
    args.command().run(args)

if __name__ == "__main__":
  main()
