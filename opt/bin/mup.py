#!/usr/bin/env python3

"""Backup script."""

MUP_DIR = "/mnt/bup/data"

import sys
import os
import subprocess
import argparse
import re
import pipes
import pygit2
import tempfile
import shutil
import io


def main():
  """Run mup."""
  parser = CommandParser()
  parser.add_argument("-p", "--pretend", action="store_true")
  parser.add_commands((Russ, Russp, Old))
  parser.run()


class Russ:
  """Copy from ~russ to ~russp."""
  def run(self, args):
    rsync_all("/home/russ/.TaskCoach/tasks.tsk",
              "/mnt/russp/info/task/tasks.tsk", args.pretend)


class Russp:
  """Copy from ~russp to non-bup backups."""
  def run(self, args):
    rsync_all("/mnt/russp/.keys/",
              "/mnt/bup/russp.keys/", args.pretend)
    rsync_all("/mnt/russp/.git/",
              "/mnt/bup/russp.git/", args.pretend)


class Old:
  """Import old data into bup."""
  @classmethod
  def add_arguments(cls, parser):
    parser.add_commands((Save, Verify))


class Save:
  """Save old directory tree"""
  @classmethod
  def add_arguments(cls, parser):
    parser.add_argument("dir_path")

  def run(self, args):
    check_old_dir(args.dir_path)

    bup_dir = mup_dir()
    branch_name = next_branch(bup_dir)

    env = bup_env(bup_dir)
    abs_dir_path = os.path.abspath(args.dir_path)
    run(["bup", "index", "-vv", abs_dir_path], env=env)
    run(["bup", "save", "-n", branch_name, "--graft", abs_dir_path + "=/old",
         abs_dir_path], env=env)
    return branch_name


class Verify:
  """Verify old directory tree."""
  @classmethod
  def add_arguments(cls, parser):
    parser.add_argument("branch_name")
    parser.add_argument("dir_path")

  def run(self, args):
    tempdir = tempfile.mkdtemp()
    try:
      run(["bup", "restore", args.branch_name + "/latest/old/.",
           "-C", tempdir], env=bup_env(mup_dir()))
      run(["rsync", "-nia", "--delete",
           os.path.abspath(args.dir_path) + "/", tempdir])
    finally:
      cleanup(tempdir)


def next_branch(bup_dir):
  """Find next free old.X branch number in bup repository."""
  if not os.path.isdir(bup_dir):
    error("bup directory %s not found.\n"
          "Try: BUP_DIR=%s bup init" %
          (repr(bup_dir), pipes.quote(bup_dir)))
  repo = pygit2.Repository(bup_dir)
  num = 0
  for ref in repo.listall_references():
    match = re.match(r"refs/heads/old.(\d+)$", ref)
    if match:
      num = max(num, int(match.group(1)) + 1)
  return "old.%i" % num


def check_old_dir(dir_path):
  """Verify a directory contains nothing but date prefixed subdirectories."""
  errors = []
  try:
    for path in os.listdir(dir_path):
      if not os.path.isdir(os.path.join(dir_path, path)):
        errors.append("%s is not a directory" % repr(path))
      match = re.match(r"\d{4}-\d{2}-\d{2}-.", path)
      if not match:
        errors.append("%s not prefixed with YYYY-MM-DD" % repr(path))
  except OSError as exception:
    errors.append(str(exception))
  if errors:
    error("\n  ".join(["problems with %s" % repr(dir_path)] + errors))


def human(num_bytes):
  """Return number of bytes in human readable form."""
  for suffix in ['', 'K', 'M', 'G']:
    if num_bytes < 1024:
      break
    num_bytes /= 1024.0
  else:
    suffix = 'T'
  if num_bytes < 10:
    return "%.2f%s" % (num_bytes, suffix)
  elif num_bytes < 100:
    return "%.1f%s" % (num_bytes, suffix)
  else:
    return "%.0f%s" % (num_bytes, suffix)


def mup_dir():
  """Get overridden bup directory, or the built in default."""
  return os.environ.get("MUP_DIR", MUP_DIR)


def bup_env(bup_dir):
  """Get environment block for passing to bup processes."""
  env = os.environ.copy()
  env["BUP_DIR"] = bup_dir
  return env


def run(cmd, *args, **kwargs):
  """Run a command."""
  if isinstance(cmd, str):
    print(cmd)
  else:
    print(" ".join(map(pipes.quote, cmd)))
  try:
    if isinstance(sys.stdout, io.StringIO):
      # capture output for tests
      sys.stdout.write(subprocess.check_output(
          cmd, *args, stderr=subprocess.STDOUT, **kwargs).decode())
    else:
      subprocess.check_call(cmd, *args, **kwargs)
  except subprocess.CalledProcessError as exception:
    if exception.output is not None:
      sys.stdout.buffer.write(exception.output.decode())
    return exception.returncode


def rsync_all(src, dest, pretend):
  """Run rsync with directory mirroring options."""
  return run(["rsync", "-avH", "--delete"]
             + (pretend and ["--dry-run"] or [])
             + [src, dest])


def cleanup(dirpath):
  """Remove directory tree, and just print an error and continue if unable."""
  try:
    shutil.rmtree(dirpath)
  except OSError as exception:
    error("could not remove %s\n%s" % (repr(dirpath), exception), status=None)


def error(message, status=1):
  """Print an error and optionally exit with an error code."""
  print("Error: %s" % message, file=sys.stderr)
  if status is not None:
    exit(status)


class CommandParser(argparse.ArgumentParser):
  """ArgumentParser subclass that handles and runs subcommands."""

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
