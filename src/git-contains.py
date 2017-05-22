#!/usr/bin/python3
"""
Check if git_dir2 is superset of git_dir1
"""

import argparse
import heapq
import os
import re
import sys
import subprocess
from itertools import groupby


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("git_dir1")
    parser.add_argument("git_dir2")
    args = parser.parse_args()
    obj1 = set()
    obj2 = set()
    fail = False
    for f, (in_git1, in_git2) in join_lists(
            list_files(args.git_dir1), list_files(args.git_dir2)):
        p1 = os.path.join(args.git_dir1, f) if in_git1 else None
        p2 = os.path.join(args.git_dir2, f) if in_git2 else None
        if any((p1 and add_objs(p1, obj1), p2 and add_objs(p2, obj2))):
            continue
        if not p1:
            continue
        if not p2:
            fail = True
            error("Missing {!r} in {!r}".format(p1, args.git_dir2))
            continue
        c = cmp(p1, p2)
        if c == 0 or c == 2:
            continue
        if f == "index":
            if not index_matches_head(args.git_dir1):
                fail = True
                if index_matches_head(args.git_dir2):
                    error("index {!r} different from HEAD (try {!r})".format(
                        args.git_dir1,
                        "GIT_DIR={} git diff-index --cached HEAD".format(
                            args.git_dir1)))
                else:
                    error("index files differ (try {!r})".format(
                        "diff -U10 <(GIT_DIR={} git ls-files --stage --debug) <(GIT_DIR={} git ls-files --stage --debug) | cdiff".
                        format(args.git_dir1, args.git_dir2)))
            continue
        r = Regex()
        if r.match("refs/", f):
            h1 = read(p1)
            h2 = read(p2)
            base = b"".join(
                run(["git", "merge-base", h1, h2],
                    env=dict(os.environ, GIT_DIR=args.git_dir2))).rstrip()
            if base != h1:
                fail = True
                error("Ref {!r} changed {} -> {} (base {})".format(f, h1, h2,
                                                                   base))
            continue

        fail = True
        error("Conflicting {!r} and {!r} (cmp={!r})".format(p1, p2, c))

    if not obj1.issubset(obj2):
        fail = True
        for missing in obj1 - obj2:
            error("Missing {} in {!r}".format(missing, args.git_dir2))
    if fail:
        print("Failure: {!r} is NOT a subset of {!r}".format(args.git_dir1,
                                                             args.git_dir2))
        sys.exit(1)
    else:
        print("Success: {!r} is a subset of {!r}".format(args.git_dir1,
                                                         args.git_dir2))


def list_files(path):
    """Return list of files underneath a directory."""
    for root, dirnames, filenames in os.walk(path, onerror=throw):
        for filename in filenames:
            if root == path:
                yield filename
            else:
                yield os.path.join(os.path.relpath(root, path), filename)


def throw(exception):
    raise exception


def join_lists(*lists):
    """Return superset of items in individual lists.

    Return value is list of (items, contains_tuple), where contain_tuple is a
    tuple with a boolean for each input list indicating whether the list
    contained the list item."""

    # Sorted list of (item, pos)
    merged = heapq.merge(* [[(item, pos) for item in sorted(list)]
                            for pos, list in enumerate(lists)])

    # Sorted list of (item, set of pos's))
    grouped = (
        (item, set(pos for item_, pos in group))
        for item, group in groupby(merged, lambda item_pos: item_pos[0]))

    # List of (item, contains_tuple)
    return ((item, tuple(pos in pos_set for pos in range(len(lists))))
            for item, pos_set in grouped)


def add_objs(path, objs):
    r = Regex()
    if r.match(".*?/objects/([0-9a-f]{2})/([0-9a-f]{38})$", path):
        objs.add((r.m.group(1) + r.m.group(2)).encode("ascii"))
        return True

    if r.match(r"(.*?/objects/pack/pack-[0-9a-f]{40})\.(pack|idx)$", path):
        base, ext = r.m.groups()
        if ext == "idx":
            return True

        for line in run(["git", "verify-pack", "-v", base + ".idx"]):
            if r.match(
                    br"^([0-9a-f]{40}) (commit|tree  |blob  |tag   ) [0-9]+ [0-9]+ [0-9]+.*",
                    line):
                objs.add(r.m.group(1))
            elif not r.match(
                    br"%s: ok$|non delta: [0-9]+ objects?$|chain length = [0-9]+: [0-9]+ objects?$"
                    % re.escape(path.encode()), line):
                raise Exception(
                    "Error: unexpected verify-pack output {!r}".format(line))
        return True

    return False


class Regex:
    def match(self, regex, string):
        self.m = re.match(regex, string)
        return self.m


def run(*args, **kwargs):
    with subprocess.Popen(*args, **kwargs, stdout=subprocess.PIPE) as p:
        yield from p.stdout
    if p.returncode:
        raise Exception("Exit code {!r} from popen(*{!r}, **{!r})".format(
            p.returncode, args, kwargs))


def cmp(f1, f2):
    """Return 0 if eq, 1 if eof on 1, 2 if eof on 2, else -1"""
    bufsize = 8192
    with open(f1, 'rb') as fp1, open(f2, 'rb') as fp2:
        while True:
            b1 = fp1.read(bufsize)
            b2 = fp2.read(bufsize)
            l1 = len(b1)
            l2 = len(b2)
            if l1 < l2:
                return 2 if b1 == b2[:l1] else -1
            if l2 < l1:
                return 1 if b1[:l2] == b2 else -1
            if b1 != b2:
                return -1
            if not b1:
                return 0


def read(filename):
    with open(filename, "rb") as f:
        return f.read().rstrip()


def index_matches_head(git_dir):
    return subprocess.run(
        ["git", "diff-index", "--cached", "--quiet", "HEAD"],
        env=dict(os.environ, GIT_DIR=git_dir)).returncode == 0


def error(str):
    print("Error: {}".format(str), file=sys.stderr)


if __name__ == '__main__':
    main()
