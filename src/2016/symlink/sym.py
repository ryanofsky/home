#!/usr/bin/env python3

import argparse
import os
import re
import shlex
import stat
import sys


def main():
    """Run sym."""
    parser = CommandParser()
    parser.add_argument("-p", "--pretend", action="store_true")
    parser.add_commands((Mirror(), Find(), Reverse()))
    parser.run()


class Mirror:
    """Create a tree of symlinks in dst pointing at files in src.

    This command will fail if anything already exists at paths where
    symlinks would be created.

    If a file in src is itself a symlink, this will copy the symlink
    instead of creating a symlink to the symlink.
    """

    def add_arguments(self, parser):
        parser.add_argument("src_dir", help="Directory of files to mirror.")
        parser.add_argument("dst_dir", help="Directory of symlinks to create.")

    def run(self, args):
        # Needs topdown false so timestamps set on parent directories stick.
        for src_root, dirs, files in os.walk(args.src_dir, topdown=False):
            src_root_st = os.stat(src_root)
            rel = os.path.relpath(src_root, args.src_dir)
            dst_root = os.path.join(args.dst_dir, rel)
            if not os.path.exists(dst_root):
                os.makedirs(dst_root)
            for f in files:
                src_file = os.path.join(src_root, f)
                dst_file = os.path.join(dst_root, f)
                if os.path.islink(src_file):
                    attr = path_attr(src_file, follow_symlinks=False)
                    symlink(os.readlink(src_file), dst_file, args.pretend)
                    args.pretend or set_path_attr(dst_file,
                                                  attr,
                                                  follow_symlinks=False)
                else:
                    st = os.stat(src_file, follow_symlinks=False)
                    symlink(src_file, dst_file, args.pretend)
                    args.pretend or os.utime(
                        dst_file,
                        ns=(st.st_atime_ns, st.st_mtime_ns),
                        follow_symlinks=False)
            args.pretend or os.utime(
                dst_root,
                ns=(src_root_st.st_atime_ns, src_root_st.st_mtime_ns))


class Find:
    """Find symlinks in directory whose destination matches a string.

    Optionally replace the symlink destinations with a substitute string.

    All mtimes of symlinks and parent directories are preserved.
    """

    def add_arguments(self, parser):
        parser.add_argument(
            "-r",
            "--regex",
            action="store_true",
            help="Treat find and replace values as regex expressions "
            "instead of simple strings.")
        parser.add_argument(
            "-0",
            action="store_true",
            help="Print matching symlink paths to stdout seperated by "
            "null characters for use with xargs -0.")
        parser.add_argument(
            "-s",
            "--sub",
            action="append",
            help="String or regex replacement pattern to replace "
            "matching symlinks with.")
        parser.add_argument(
            "-A",
            "--absolute",
            action="store_true",
            help="Convert relative symlink to absolute symlink.")
        parser.add_argument(
            "-R",
            "--relative",
            action="store_true",
            help="Convert absolute symlink to relative symlink.")
        parser.add_argument(
            "directory",
            help="Directory to recursively search for symlinks.")
        parser.add_argument("pattern",
                            nargs="*",
                            help="Pattern to match symlinks against.")

    def run(self, args):
        sep = "\0" if getattr(args, "0") else "\n"
        for root, dirs, files in os.walk(args.directory):
            root_st = os.stat(root or os.curdir) if (
                args.sub or args.absolute or args.relative) else None
            root_modified = False
            for f in files:
                path = os.path.join(root, f)
                if not os.path.islink(path):
                    continue
                link = os.readlink(path)
                match = sub = None
                for i, pattern in enumerate(args.pattern):
                    match = re.match(pattern, link) if args.regex else (
                        link == pattern)
                    if match:
                        sub = args.sub[i] if args.sub and len(
                            args.sub) > i else None
                        break
                if not match:
                    continue

                new_link = link if sub is None else match.expand(
                    sub) if args.regex else sub

                if args.absolute and not os.path.isabs(new_link):
                    new_link = os.path.abspath(os.path.join(root, new_link))
                if args.relative and os.path.isabs(new_link):
                    new_link = os.path.relpath(new_link, root)

                if new_link != link:
                    root_modified = True
                    attr = path_attr(path, follow_symlinks=False)
                    args.pretend or os.unlink(path)
                    symlink(new_link, path, args.pretend,
                            " [previously {}]".format(shlex.quote(link)))
                    args.pretend or set_path_attr(path,
                                                  attr,
                                                  follow_symlinks=False)
                elif sub is None:
                    bprint(path + sep, newline=False)
            if root_modified:
                args.pretend or os.utime(
                    root or os.curdir,
                    ns=(root_st.st_atime_ns, root_st.st_mtime_ns))


class Reverse():
    """Reverse a symlink.

    Overwrite symlink with file it points to. Add a symlink pointing
    to the new file location at the old location.

    Symlink and file must be in same filesystem so rename works.

    Timestamp of the replaced symlink will NOT be preserved (could be
    an option, just not currently needed. New symlink will be given
    the same timestamp of the renamed file.

    Parent directory mtimes are preserved.
    """

    def add_arguments(self, parser):
        parser.add_argument("symlink_path",
                            nargs="*",
                            help="Path to symlink to be reversed.")

    def run(self, args):
        for path in args.symlink_path:
            check(os.path.islink(path), repr(path))
            path_parent = os.path.dirname(path)
            path_parent_st = os.stat(path_parent)
            link = os.readlink(path)
            link_parent = os.path.dirname(link)
            link_parent_st = os.stat(os.path.join(path_parent, link_parent))
            rename(link, path, args.pretend)
            symlink(path, link, args.pretend)
            path_st = os.stat(path, follow_symlinks=False)
            if not args.pretend:
                os.utime(link,
                         ns=(path_st.st_atime_ns, path_st.st_mtime_ns),
                         follow_symlinks=False)
                os.utime(path_parent,
                         ns=(path_parent_st.st_atime_ns,
                             path_parent_st.st_mtime_ns))
                os.utime(link_parent,
                         ns=(link_parent_st.st_atime_ns,
                             link_parent_st.st_mtime_ns))


class CommandParser(argparse.ArgumentParser):
    """ArgumentParser subclass that handles and runs subcommands."""

    def add_commands(self, commands, *args, **kwargs):
        subparsers = self.add_subparsers(*args, **kwargs)
        for command in commands:
            if hasattr(command, "subparser"):
                # If command object provides subparser() method, let
                # it call subparsers.add_parser itself to create a
                # custom subparser.
                subparser = command.subparser(subparsers)
            else:
                # If command object doesn't provide subparser()
                # method, call subparsers.add_parser on its behalf and
                # derive the commands name from the command object
                # name.
                name = re.sub("(.)([A-Z])", r"\1_\2",
                              command.__class__.__name__).lower()
                subparser = subparsers.add_parser(name)
            if hasattr(command, "add_arguments"):
                # Let command object add it's own arguments and
                # subsubcommands to the subparser. Subparser object
                # will be an instance of the CommandParser class, so
                # it will have nice add_argument / add_command
                # methods.
                command.add_arguments(subparser)
            if hasattr(command, "run"):
                # Stash reference to the command object in the
                # subparser defaults, so the CommandParser.run
                # implementation below can access the command object
                # and call run() on it.
                subparser.set_defaults(_saved_subcommand=command)

    def run(self):
        args = self.parse_args()
        # Call run on the args.command object stashed by set_defaults above.
        if not hasattr(args, "_saved_subcommand"):
            self.print_help()
            sys.exit(2)
        args._saved_subcommand.run(args)


def symlink(src, dst, pretend, note=""):
    bprint("ln -s {} {}{}".format(shlex.quote(src), shlex.quote(dst), note))
    if not pretend:
        os.symlink(src, dst)


def rename(src, dst, pretend, note=""):
    bprint("mv {} {}{}".format(shlex.quote(src), shlex.quote(dst), note))
    if not pretend:
        os.rename(src, dst)


def path_attr(path, follow_symlinks):
    "Return (atime_ns, mtime_ns, mode, flags, [(xattr, value),...])"
    st = os.stat(path, follow_symlinks=follow_symlinks)
    atime_ns = st.st_atime_ns
    mtime_ns = st.st_mtime_ns
    mode = stat.S_IMODE(st.st_mode)
    flags = st.st_flags if hasattr(st, "st_flags") else None
    xattr = []
    names = os.listxattr(path, follow_symlinks=follow_symlinks)
    for name in names:
        xattr.append(name,
                     os.getxattr(path,
                                 name,
                                 follow_symlinks=follow_symlinks))
    return atime_ns, mtime_ns, mode, flags, tuple(xattr)


def set_path_attr(path, attr, follow_symlinks):
    atime_ns, mtime_ns, mode, flags, xattr = attr
    os.utime(path, ns=(atime_ns, mtime_ns), follow_symlinks=follow_symlinks)
    try:
        os.chmod(path, mode, follow_symlinks=follow_symlinks)
    except SystemError:
        pass
    if flags is not None:
        os.chflags(path, flags, follow_symlinks=follow_symlinks)
    for name, value in xattr:
        os.setxattr(path, name, value, follow_symlinks=follow_symlinks)


def check(cond, *args, **kwargs):
    if not cond:
        raise Exception(*args, **kwargs)


def bprint(str, newline=True):
    sys.stdout.buffer.write(str.encode("utf-8", "surrogateescape"))
    if newline:
        sys.stdout.buffer.write(b'\n')


if __name__ == "__main__":
    main()
