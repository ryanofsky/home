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
  parser.add_commands((Russ(), Russp(), Old()))
  parser.run()


class Russ:
  """Copy from ~russ to ~russp."""
  def run(self, args):
    errors = []
    rsync_all("/home/russ/.TaskCoach/tasks.tsk",
              "/mnt/russp/info/task/tasks.tsk", args.pretend, errors)
    error("Problems during sync:", errors)


class Russp:
  """Copy from ~russp to non-bup backups."""
  def run(self, args):
    errors = []
    rsync_all("/home/russ/opt/src/vpn/.git/",
              "/mnt/mup1/sync/vpn.git/", args.pretend, errors)
    rsync_all("/mnt/russp/.keys/",
              "/mnt/mup1/sync/russp.keys/", args.pretend, errors)
    rsync_all("/mnt/russp/.git/",
              "/mnt/mup1/sync/russp.git/", args.pretend, errors)
    error("Problems during sync:", errors)


class Old:
  """Import old data into bup."""
  def add_arguments(cls, parser):
    parser.add_commands((Save(), Verify()))

  def save(self, branch_name, src_path, dest_path, env):
    run(["bup", "index", "-vv", src_path], env=env)
    run(["bup", "save", "-n", branch_name, "--graft",
         src_path + "=/" + dest_path, src_path], env=env)

  def fuse_check(self, src_path, bup_path, env, errors):
    tempdir = tempfile.mkdtemp(prefix="mf-")
    try:
      run(["bup", "fuse", tempdir], errors, env=env)
      try:
        output = run(["rsync", "-irl", "--delete", src_path + "/",
             os.path.join(tempdir, bup_path) + "/"], errors, True)
        if output:
          errors.append("Unexpected rsync output.")
      finally:
        run(["fusermount", "-u", tempdir], errors)
    finally:
      warn(os.rmdir, tempdir)

  def restore_check(self, src_path, bup_path, env, delete=False):
    tempdir = tempfile.mkdtemp(prefix="mr-")
    try:
      run(["bup", "restore", bup_path + "/.", "-C", tempdir], env=env)
      if delete:
        args = ["-iacH", "--remove-source-files"] 
      else:
        args = ["-nia", "--delete"]
      run(["rsync"] + args + [src_path + "/", temp_path + "/"])
      if delete:
        rmdirs(src_path)
    finally:
      warn(shutil.rmtree, tempdir)


class Save(Old):
  """Save old directory tree"""
  def add_arguments(cls, parser):
    parser.add_argument("--delete", action="store_true")
    parser.add_argument("dir_path")
    parser.add_argument("name", nargs="?")

  def run(self, args):
    errors = []
    if args.name is None:
      check_old_dir(args.dir_path, errors)
      dest_path = "old"
    else:
      check_old_name(args.name, errors)
      dest_path = "old/{}".format(args.name)
    if errors:
      error("problems with %s" % repr(dir_path), errors)
      
    bup_dir = mup_dir()
    branch_name = next_branch(bup_dir)
    env = bup_env(bup_dir)
    src_path = os.path.abspath(args.dir_path)
    bup_path = os.path.join(branch_name, "latest", dest_path)
    self.save(branch_name, src_path, dest_path, env)
    self.fuse_check(src_path, bup_path, env, errors)
    error("Fuse rsync check failed.", errors)
    self.restore_check(src_path, bup_path, env, delete=args.delete)
    return branch_name


class Verify(Old):
  """Verify old directory tree."""
  def add_arguments(cls, parser):
    parser.add_argument("branch_name")
    parser.add_argument("dir_path")

  def run(self, args):
    bup_dir = mup_dir()
    branch_name = args.branch_name
    env = bup_env(bup_dir)
    src_path = os.path.abspath(args.dir_path)
    bup_path = os.path.join(branch_name, "latest", dest_path)
    self.restore_check(src_path, bup_path, env, delete=False)

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


def check_old_name(dir_name, errors):
  match = re.match(r"\d{4}-\d{2}-\d{2}-.", dir_name)
  if not match:
    errors.append("%s not prefixed with YYYY-MM-DD" % repr(dir_name))


def check_old_dir(dir_path, errors):
  """Verify a directory contains nothing but date prefixed subdirectories."""
  try:
    for path in os.listdir(dir_path):
      if not os.path.isdir(os.path.join(dir_path, path)):
        errors.append("%s is not a directory" % repr(path))
      check_old_name(path, errors)
  except OSError as exception:
    errors.append(str(exception))


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


def run(cmd, errors=None, tee=False, *args, **kwargs):
  """Run a command."""
  # FIXME: tee implementation sucks in that it redirects subprocess
  # standard error to the standard out. A better implementation would
  # capture errors while still allowing them to go the error stream.
  cmd_str = cmd if isinstance(cmd, str) else " ".join(map(pipes.quote, cmd))
  print(cmd_str)
  output = None
  testing = isinstance(sys.stdout, io.StringIO)
  try:
    if tee or testing:
      output = subprocess.check_output(
        cmd, *args, stderr=subprocess.STDOUT, **kwargs)
    else:
      subprocess.check_call(cmd, *args, **kwargs)
  except subprocess.CalledProcessError as exception:
    output = exception.output.decode()
    message = "Command failed with status {}: {}".format(exception.returncode, cmd_str))
    if errors is None:
      error(message)
    else:
      errors.append(error)
  if testing:
    sys.stdout.write(output.decode(errors="surrogateescape"))
  return output

  
def rsync_all(src, dest, pretend, errors):
  """Run rsync with directory mirroring options."""
  return run(["rsync", "-avH", "--delete"]
             + (pretend and ["--dry-run"] or [])
             + [src, dest], errors)

    
def rmdirs(dirpath):
  for dirpath, dirnames, filenames in os.walk(dirpath, topdown=False):
    for dirname in dirnames:
      warn(os.rmdir, os.path.join(dirpath, dirname))

   
def error(message, errors=None, status=1):
  """Print an error and optionally exit with an error code."""
  if errors is None or errors:
    first = "{}: {}".format("Warning" if status is None else "Error", message)
    print("\n  ".join([first] + (errors or [])), file=sys.stderr)
    if status is not None:
      sys.exit(status)

      
def warn(cmd, *args, *kwargs):
  try:
    cmd(*args, **kwargs)
  except OSError as exception:
    error("{} in {!r} *{!r} **{!r}".format(exception, cmd, args, kwargs), status=None))

    
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
    args.command.run(args)


if __name__ == "__main__":
  main()
