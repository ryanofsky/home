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

  def test_idc(self):
    save = mup.Save()

    def verify_gay(save, what):
      self.assertEqual(1, 2) 
      mup.Save.verify_gay(save, what)
    
    with mock.patch.object(save, 'verify_gay', side_effect=verify_gay):
      checker = EmailChecker()
      print(checker.is_email_correct('1'))
      print(checker.is_email_correct('2'))
    

    
    
  def test_old_same(self):
    self.namespace.branch_name = mup.Save().run(self.namespace)
    mup.Verify().run(self.namespace)

  def test_old_diff(self):
    self.namespace.branch_name = mup.Save().run(self.namespace)
    makepaths(self.in_dir, "x/3")
    os.unlink(os.path.join(self.in_dir, "x/2"))
    code, output = getoutput(mup.Verify().run, self.namespace)
    self.assertIsNone(code)
    lines = output.split("\n")
    self.assertRegexpMatches(lines[0], "bup restore")
    self.assertRegexpMatches(lines[1], "rsync -nia")
    self.assertEqual([".d..t...... 2011-01-01-test/x/",
                      "*deleting   2011-01-01-test/x/2",
                      ">f+++++++++ 2011-01-01-test/x/3"],
                     lines[2:])

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
    code, output = getoutput(mup.error, "test")
    self.assertEqual(1, code)
    self.assertEqual("Error: test", output)

  def test_check_old_dir(self):
    makepaths(self.tempdir, "2012-01-01-joe/ 2011-02-03-a/jkj")
    code, output = getoutput(mup.check_old_dir, self.tempdir)
    self.assertIsNone(code)
    makepaths(self.tempdir, "2012-01-01-file badpref/")
    code, output = getoutput(mup.check_old_dir, self.tempdir)
    self.assertEqual(1, code)
    error_list = sorted(output.split("\n  ")[1:])
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


def getoutput(func, *args, **kwargs):
  stdout = sys.stdout
  stderr = sys.stderr
  try:
    sys.stdout = io.StringIO()
    sys.stderr = sys.stdout
    try:
      func(*args, **kwargs)
      code = None
    except SystemExit as exception:
      code = exception.code
    return code, sys.stdout.getvalue().strip()
  finally:
    sys.stdout = stdout
    sys.stderr = stderr
