#!/usr/bin/env python3

import argparse
import io
import os
import shutil
import sys
import tempfile
import unittest

import sym


class MupTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.mkdtemp()
        self.namespace = argparse.Namespace()
        self.namespace.pretend = False

    def tearDown(self):
        1 or shutil.rmtree(self.tempdir)

    def test_find(self):
        os.mkdir(self._path("1"))
        os.symlink("a", self._path("1/2"))
        mtime_1 = self._mtime("1")
        mtime_1_2 = self._mtime("1/2")

        self.namespace.regex = True
        self.namespace.sub = [r"prefix/\1"]
        self.namespace.directory = self.tempdir
        self.namespace.pattern = ["(.*)"]
        setattr(self.namespace, "0", False)
        code, out = getoutput(sym.Find().run, self.namespace)

        self.assertEqual(
            out, "ln -s prefix/a {} [previously a]".format(self._path("1/2")))
        self.assertEqual(os.readlink(self._path("1/2")), "prefix/a")
        self.assertEqual(mtime_1, self._mtime("1"))
        self.assertEqual(mtime_1_2, self._mtime("1/2"))

    def test_mirror(self):
        makepaths(self.tempdir, "a/1/2 a/1/3 a/1/4")

        self.namespace.src_dir = self._path("a")
        self.namespace.dst_dir = self._path("b")
        code, out = getoutput(sym.Mirror().run, self.namespace)

        self.assertEqual(out, "\n".join(["ln -s {} {}"] * 3).format(
            self._path("a/1/2"), self._path("b/1/2"), self._path("a/1/3"),
            self._path("b/1/3"), self._path("a/1/4"), self._path("b/1/4")))
        self.assertEqual(self._mtime("a/1"), self._mtime("b/1"))
        self.assertEqual(self._mtime("a"), self._mtime("b"))
        self.assertEqual(os.readlink(self._path("b/1/2")), self._path("a/1/2"))

    def test_reverse(self):
        makepaths(self.tempdir, "file")
        os.symlink(self._path("file"), self._path("link"))
        mtime_dir = self._mtime(os.curdir)
        mtime_file = self._mtime("file")

        self.namespace.symlink_path = [self._path("link")]
        code, out = getoutput(sym.Reverse().run, self.namespace)

        self.assertEqual(out, "mv {} {}\nln -s {} {}".format(
            self._path("file"), self._path("link"), self._path("link"),
            self._path("file")))
        self.assertEqual(os.readlink(self._path("file")), self._path("link"))
        self.assertEqual(mtime_file, self._mtime("file"))
        self.assertEqual(mtime_file, self._mtime("link"))
        self.assertEqual(mtime_dir, self._mtime(os.curdir))

    def _path(self, path):
        return os.path.join(self.tempdir, path)

    def _mtime(self, path):
        return os.stat(self._path(path), follow_symlinks=False).st_mtime_ns


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


if __name__ == "__main__":
    unittest.main()
