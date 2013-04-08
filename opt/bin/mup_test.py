# pylint: disable=R0904

import mup
import argparse
import unittest
import tempfile
import os
import subprocess
import io
import sys


class MupTests(unittest.TestCase):
  def setUp(self):
    self.tempdir = tempfile.mkdtemp()
    self.namespace = argparse.Namespace()
    self.namespace.dir_path = os.path.join(self.tempdir, "bup.in")
    self.repo_dir = os.path.join(self.tempdir, "bup.repo")
    self.in_dir = os.path.join(self.namespace.dir_path, "2011-01-01-test")
    self.make = "a/1 a/b/2 a/b/c/3 a/b/9 x/1 x/2"
    self.exclude = "a/b/9 x/"

    os.environ["MUP_DIR"] = self.repo_dir
    makepaths(self.in_dir, self.make)
    with open(os.devnull, "w") as fnull:
      subprocess.call(["bup", "init"], env=mup.bup_env(self.repo_dir),
                      stderr=fnull)

  def tearDown(self):
    mup.cleanup(self.tempdir)

  def test_old(self):
    self.namespace.branch_name = mup.Save().run(self.namespace)
    mup.Verify().run(self.namespace)


class BasicTests(unittest.TestCase):
  def setUp(self):
    self.tempdir = tempfile.mkdtemp()

  def tearDown(self):
    mup.cleanup(self.tempdir)

  def test_next_branch(self):
    git_dir = os.path.join(self.tempdir, "git_dir")
    env = os.environ.copy()
    env["GIT_DIR"] = git_dir
    with open(os.devnull, "w") as fnull:
      subprocess.call(["git", "init"], env=env, stdout=fnull)
    self.assertEqual("old.0", mup.next_branch(git_dir))
    subprocess.call(["git write-tree | xargs git commit-tree "
                     "| xargs git branch old.29"], shell=True, env=env)
    self.assertEqual("old.30", mup.next_branch(git_dir))

  def test_error(self):
    error = geterror(mup.error, "test")
    self.assertEqual("Error: test", error)

  def test_check_old_dir(self):
    makepaths(self.tempdir, "2012-01-01-joe/ 2011-02-03-a/jkj")
    error = geterror(mup.check_old_dir, self.tempdir)
    self.assertIsNone(error)
    makepaths(self.tempdir, "2012-01-01-file badpref/")
    error = geterror(mup.check_old_dir, self.tempdir)
    self.assertIsNotNone(error)
    error_list = sorted(error.split("\n  ")[1:])
    self.assertEqual(["'2012-01-01-file' is not a directory",
                      "'badpref' not prefixed with YYYY-MM-DD"],
                     error_list)


def makepaths(root, paths):
  for path in paths.split():
    dirname, filename = os.path.split(path)
    dirpath = os.path.join(root, dirname)
    if not os.path.isdir(dirpath):
      os.makedirs(dirpath)
    if filename:
      filepath = os.path.join(dirpath, filename)
      with open(filepath, "w") as fileout:
        fileout.write("%s\n" % filepath)


def geterror(func, *args, **kwargs):
  stdout = sys.stdout
  stderr = sys.stderr
  try:
    sys.stdout = io.StringIO()
    sys.stderr = io.StringIO()
    try:
      func(*args, **kwargs)
      return None
    except SystemExit:
      return sys.stderr.getvalue().strip()
  finally:
    sys.stdout = stdout
    sys.stderr = stderr
