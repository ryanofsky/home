#!/usr/bin/python3

import sys
import subprocess
import os
import re
import posixpath
import datetime
import errno


def main():
    args = sys.argv[1:]
    if not args:
        save()
    elif args == ["apply"]:
        apply()
    elif args == ["apply", "-u"]:
        apply(unmodified=True)
    else:
        raise Exception("bad arguments")


def save():
    root = git_root()

    with open(os.path.join(root, ".git-mtime"), "wb") as fp:
        prev_path = []
        for path in git_mtimes(root):
            # Avoid self-reference.
            if path == [".git-mtime"]:
                continue

            # Print containing directory if different from previous.
            if path[:-1] != prev_path[:-1] or not prev_path:
                # Print directory with /. suffix if previously was in child directory.
                # Point of suffix is just to make directory listing easier for a human
                # to scan, doesn't actually convey any new information.
                suffix = ["."] if len(prev_path) > len(
                    path) and prev_path[:len(path) - 1] == path[:-1] else []
                dirpath = "/" + "/".join(path[:-1] + suffix) + "\n"
                bpath = dirpath.encode("utf-8", "surrogateescape")
                fp.write(bpath)
            fp.write("\t{}\t{}\n".format(
                mtime(os.path.join(root, *path)), path[-1]).encode(
                    "utf-8", "surrogateescape"))
            prev_path = path


def apply(unmodified=False):
    root = git_root()
    skip = set(get_files(root, modified=True)) if unmodified else set()
    with open(os.path.join(root, ".git-mtime"), "rb") as fp:
        dirpath_cur = None
        for line in fp:
            line = line.decode("utf-8", "surrogateescape")
            m = re.match(
                r"^(?:/(.*))|(?:\t(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\.(\d{9})\t(.*))\n$",
                line)
            dirpath, time, ns, filename = m.groups()
            if dirpath is not None:
                if dirpath.endswith("/.") or dirpath == ".":
                    dirpath_cur = dirpath[:-2]
                else:
                    dirpath_cur = dirpath
                continue
            mtime_ns = int(datetime.datetime.strptime(
                time, "%Y-%m-%d %H:%M:%S").replace(
                    tzinfo=datetime.timezone.utc).timestamp(
                    )) * 1000000000 + int(ns)
            path = posixpath.join(dirpath_cur, filename)
            if path in skip:
                print("Skipping modified {!r}".format(root_path))
                continue
            root_path = os.path.join(root, path)
            try:
                st = os.lstat(root_path)
            except OSError as e:
                if e.errno == errno.ENAMETOOLONG or e.errno == errno.EBADMSG:
                    print("Skipping {!r}".format(root_path), file=sys.stderr)
                    continue
            if mtime_ns != st.st_mtime_ns:
                print(repr(path), format_mtime(mtime_ns), format_mtime(st.st_mtime_ns))
                os.utime(root_path,
                         ns=(st.st_atime_ns, mtime_ns),
                         follow_symlinks=False)


def git_mtimes(root):
    prev_f = None
    prev_path = []
    for f in get_files(root):
        path = f.split("/")
        # Git only tracks files, so need following loop to add parent
        # directories to the listing.
        for i in range(len(path)):
            if path[:i] != prev_path[:i]:
                yield path[:i]
        yield path
        if prev_f is not None and f < prev_f:
            raise Exception("Unexpected {!r} >= {!r}".format(prev_f, f))
        prev_f = f
        prev_path = path


def mtime(path):
    ns = os.lstat(path).st_mtime_ns
    return format_mtime(ns)


def format_mtime(ns):
    return "{}.{:09}".format(
        datetime.datetime.utcfromtimestamp(ns // 1000000000), ns % 1000000000)


def get_files(root, modified=False, buf_size=16384):
    command = ["git", "ls-files", "--full-name", "-z"] + (["-m"] if modified else []) + [root]
    process = subprocess.Popen(command, stdout=subprocess.PIPE)
    buf = b""
    buf_pos = 0
    filename = b""
    while True:
        if buf_pos >= len(buf):
            buf = process.stdout.read()
            pos_pos = 0
            if not buf:
                break
        p = buf.find(b"\0", buf_pos)
        if p < 0:
            filename += buf[buf_pos:]
        else:
            filename += buf[buf_pos:p]
            yield filename.decode("utf-8", "surrogateescape")
            filename = b""
            buf_pos = p + 1
    if filename:
        yield filename.decode("utf-8", "surrogateescape")
    retcode = process.wait()
    if retcode != 0:
        raise subprocess.CalledProcessError(retcode, command)


def git_root():
    return subprocess.check_output(["git", "rev-parse", "--show-toplevel"
                                    ]).rstrip(b"\n").decode()


if __name__ == "__main__":
    main()
