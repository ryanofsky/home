#!/usr/bin/python2

import datetime
import hashlib
import json
import os
import pickle
import re
import subprocess
import sys

from cStringIO import StringIO
from collections import OrderedDict
from deluge import bencode
from deluge.core.torrentmanager import TorrentState, TorrentManagerState


def tojson(in_dir, out_dir):
    """Convert deluge and vuze torrent state dirs to json format.

    Can run incrementally. New torrent data just replaces old torrent data in
    json dir."""
    torrents = load_torrents(out_dir)

    for f in os.listdir(in_dir):
        if not f.endswith(".torrent"):
            continue
        torrent_path = os.path.join(in_dir, f)
        data = bencode.bdecode(open(torrent_path).read())
        torrent_id = hashlib.sha1(bencode.bencode(data["info"])).hexdigest()
        torrent_name = f[:-len(".torrent")]
        if re.match("^[0-9a-f]{40}$", torrent_name):
            check(torrent_name == torrent_id, torrent_name)
        t = torrents.setdefault(torrent_id, OrderedDict())
        t["data"] = data
        t.setdefault("download", OrderedDict())["mtime"] = os.path.getmtime(torrent_path)

    state_file = os.path.join(in_dir, "torrents.state")
    if os.path.exists(state_file):
        state = pickle.load(open(state_file))
        check(set(obj_dict(state).keys()) == {"torrents"})
        default_torrent = TorrentState()
        for st in state.torrents:
            torrent_id = st.torrent_id
            t = torrents.setdefault(torrent_id, OrderedDict())
            t["state"]= tstate = sort_dicts(obj_dict(st))
            for k, v in tstate.items():
                if v == getattr(default_torrent, k):
                    del tstate[k]

    resume_file = os.path.join(in_dir, "torrents.fastresume")
    if os.path.exists(resume_file):
        resume = bencode.bdecode(open(resume_file).read())
        for torrent_id, rt in resume.iteritems():
            t = torrents.setdefault(torrent_id, OrderedDict())
            t["fastresume"] = bencode.bdecode(rt)

    # Sort dictionary keys
    for torrent_id, t in torrents.iteritems():
        sort_keys(t, ("data", "state", "fastresume", "download"))

    save_torrents(torrents, out_dir)


def fromjson(in_dir, out_dir):
    """Convert json torrent info to deluge state dir format.

    Not incremental. Output directory is created and populated from scratch."""
    torrents = load_torrents(in_dir)

    os.mkdir(out_dir)
    tm = TorrentManagerState()
    fr = OrderedDict()
    for torrent_id, t in sorted(torrents.items()):
        for k, v in t.iteritems():
            if k == "data":
                with open(os.path.join(out_dir, torrent_id + ".torrent"),
                          "w") as fp:
                    fp.write(bencode.bencode(v))
            elif k == "state":
                v = unsort_dicts(v)
                tm.torrents.append(TorrentState(**v))
            elif k == "fastresume":
                fr[torrent_id] = bencode.bencode(v)

    with open(os.path.join(out_dir, "torrents.state"), "w") as fp:
        pickle.dump(tm, fp)

    with open(os.path.join(out_dir, "torrents.fastresume"), "w") as fp:
        fp.write(bencode.bencode(fr))


def list_torrents(json_dir, torrent_dir):
    torrents = load_torrents(json_dir)
    metadata = []
    for torrent_id, torrent in torrents.items():
        tags = []
        if "data" in torrent:
            info = torrent["data"]["info"]
            priorities = field(torrent, "state", "file_priorities")
            md5s = field(torrent, "download", "md5")
            total_files = 0
            phys_files = 0
            sym_files = 0
            missing_files = 0
            skip_files = 0
            good_files = 0
            for i, (path, length) in enumerate(get_torrent_files(info)):
                abs_path = os.path.join(torrent_dir, torrent_id, path)

                total_files += 1

                if os.path.islink(abs_path):
                    if os.readlink(abs_path) not in (os.devnull, "/dev/zero"):
                        sym_files += 1
                elif os.path.exists(abs_path):
                    phys_files += 1

                if priorities and priorities[i] == 0:
                    skip_files += 1
                elif md5s and md5s[i]:
                    good_files += 1

            counts = "{:>3} {:>7} {:>7}".format(total_files, "{}/{}/{}".format(phys_files, sym_files, total_files - phys_files - sym_files), "{}/{}/{}".format(good_files, total_files - good_files - skip_files, skip_files))
            name = info["name"]
            if len(torrent["data"]) > 1:
                tags.append("vuze")
        else:
            counts = ""
            name = None

        timestamp = get_timestamp(torrent) or 0
        if "state" in torrent:
            tags.append("state")
        if "fastresume" in torrent:
            tags.append("fastresume")
        metadata.append((timestamp, name, torrent_id, counts, tags))

    metadata.sort()
    print("Date       Hash     Total  Phys/Sym/Missing  Good/Bad/Skip  Name  Tags")
    for timestamp, name, torrent_id, counts, tags in metadata:
        tags = " [{}]".format(", ".join(tags)) if tags else ""
        print("{:%Y-%m-%d} {} {:20} {!r}{}".format(
            datetime.datetime.fromtimestamp(timestamp), torrent_id[:8], counts, name, tags))


def find_files(json_dir, src_dir, torrent_dir):
    """Populate torrent_dir with symlinks to downloaded files in src_dirs.

    Doesn't change json_dir or src_dirs content, only creates/updates symlinks
    in torrent_dir.

    Can run incrementally. New symlinks will be added besides existing ones,
    and existing ones will only be replaced if they point to /dev/null.
    If a new symlink would conflict with an existing one this will throw an
    exception."""

    torrents = load_torrents(json_dir)
    base_idx = {}  # File basename -> torrent_id, file name
    for torrent_id, torrent in torrents.items():
        if not "data" in torrent:
            continue
        info = torrent["data"]["info"]
        for path, length in get_torrent_files(info):
            basename = os.path.basename(path)
            if basename not in base_idx:
                base_idx[basename] = torrent_id, path
            elif base_idx[basename] not in (None, (torrent_id, path)):
                print("Ignoring non-unique basename {!r} in {} and {}".format(basename, (torrent_id, path), base_idx[basename]))
                base_idx[basename] = None

    # Crawl source directory and make matches
    file_idx = {}  # torrent_id, file number -> source file
    subs = set()  # Set of torrent -> source path substiutions.
    for root, dirs, files in os.walk(src_dir):
        if root == torrent:
            del dirs[:]
            continue
        rel = os.path.relpath(root, src_dir)
        for f in files:
            file_info = base_idx.get(f)
            if file_info:
                src_path = os.path.join(root, f)
                file_idx.setdefault(file_info, src_path)
                torrent_id, torrent_path = file_info
                src_parts = src_path.split(os.sep)
                torrent_parts = torrent_path.split(os.sep)
                while src_parts and torrent_parts and src_parts[-1] == torrent_parts[-1]:
                    src_parts.pop()
                    torrent_parts.pop()
                subs.add((os.sep.join(torrent_parts + [""]), os.sep.join(src_parts + [""])))

    subs = sorted(subs)

    # Create torrent dirs inferring file locations with file_idx and subs.
    for torrent_id, torrent in torrents.items():
        if not "data" in torrent:
            continue
        info = torrent["data"]["info"]

        timestamp = get_timestamp(torrent)
        touch_paths = set()

        priorities = field(torrent, "state", "file_priorities")
        for i, (path, length) in enumerate(get_torrent_files(info)):
            # Look for direct match when file has unique basename.
            src_path = file_idx.get((torrent_id, path))

            # Look for indirect match based on direct match locations.
            if not src_path:
                for old, new in subs:
                    if not old:
                        new_path = new + path
                    elif path.startswith(old):
                        new_path = path.replace(old, new, 1)
                    else:
                        continue
                    if os.path.exists(new_path):
                        src_path = new_path
                        break

                    # Look for paths where vuze replaced unicode characters with ?.
                    try:
                        utf8_new_path = new_path.decode("utf8")
                    except UnicodeDecodeError:
                        pass
                    else:
                        ascii_new_path = utf8_new_path.encode("ascii", errors="replace")
                        if ascii_new_path != new_path and os.path.exists(ascii_new_path):
                            src_path = ascii_new_path
                            break

            if not src_path:
                if priorities and priorities[i] == 0:
                    src_path = "/dev/zero"
                else:
                    src_path = os.devnull

            # Create parent dirs and save paths for later call to touch.
            torrent_dirname = os.path.dirname(os.path.join(torrent_id, path))
            torrent_dir_parts = torrent_dirname.split(os.sep)
            torrent_dir_parents = [os.path.join(torrent_dir, *torrent_dir_parts[:i+1])
                                   for i in range(len(torrent_dir_parts))]
            for torrent_dir_parent in torrent_dir_parents:
                touch_paths.add(torrent_dir_parent)
                if not os.path.exists(torrent_dir_parent):
                    os.mkdir(torrent_dir_parent)

            # Create symlink.
            torrent_path = os.path.join(torrent_dir, torrent_id, path)
            if os.path.islink(torrent_path):
                old_src_path = os.readlink(torrent_path)
                if old_src_path == src_path:
                    continue
                check(old_src_path, os.devnull)
                os.unlink(torrent_path)
            elif os.path.exists(torrent_path):
                continue
            os.symlink(src_path, torrent_path)
            touch_paths.add(torrent_path)

        subprocess.check_call(["touch", "-hd@{}".format(timestamp)]
                              + list(touch_paths))


def compute_sums(json_dir, torrent_dir):
    """Verify torrent sha1 piece checksums and add file md5 checksums to json.

    md5 file checksums will be added to json data for files whose sha1
    piece checksums validate. md5 checksums for files with pieces that
    don't validate are set to "" in the json file.

    This function runs incrementally, and skips hashing any files that
    already have md5 checksums in the JSON.

    This function only modifies the json dir files. It leaves the
    torrent_dir directory unchanged."""
    for torrent_id in list_json_torrents(json_dir):
        torrent = load_json_torrent(json_dir, torrent_id)
        make_str(torrent)

        if not "data" in torrent:
            continue

        print("== {} ==".format(torrent_id))
        info = torrent["data"]["info"]
        download = torrent.setdefault("download", OrderedDict())
        download_md5 = download.setdefault("md5", [])
        if not download_md5:
            for _ in get_torrent_files(info):
                download_md5.append("")

        total_length = sum(length for name, length in get_torrent_files(info))
        piece_length = info["piece length"]
        total_bytes = 0  # Current byte position in torrent data.
        piece_bytes = 0  # Current byte position in piece.
        sha1 = hashlib.sha1()
        shas = StringIO(info["pieces"])  # SHA1 checksums of pieces.
        check(((total_length + piece_length - 1) // piece_length)*20 == len(shas.getvalue()))
        md5s = []  # MD5 checksums of files starting with md5_file.
        md5_file = 0  # Index of first file in md5s array.

        for i, (rel_path, file_length) in enumerate(get_torrent_files(info)):
            assert total_bytes % piece_length == piece_bytes
            abs_path = os.path.join(torrent_dir, torrent_id, rel_path)
            size = os.path.getsize(abs_path)
            file_skip_bytes = 0  # Number of bytes to skip from reading current file.
            piece_skip_bytes = 0  # Above plus number of bytes in skipped piece before file if file begins at odd piece boundary.
            if size != file_length:
                print >> sys.stderr, ("Bad file size {!r}, expected {} bytes, found {}.".format(rel_path, file_length, size))
                file_skip_bytes = file_length
            elif download_md5[i]:
                file_skip_bytes = file_length
                # If there is another file following current file.
                if total_bytes + file_skip_bytes < total_length:
                    # Subtract size of the last piece in the file to cause
                    # that piece to be read.
                    file_skip_bytes -= min((file_skip_bytes + piece_bytes) % piece_length,
                                            file_skip_bytes)
            if file_skip_bytes:
                piece_skip_bytes = piece_bytes + file_skip_bytes
                total_bytes += file_skip_bytes
                piece_bytes = (piece_bytes + file_skip_bytes) % piece_length
                sha1 = hashlib.sha1()
                md5s = []
                md5_file = i + 1

            print("  file {} {!r} tot {}/{} piece {}/{} file {} skip {}".format(i, rel_path, total_bytes, total_length, piece_bytes, piece_length, file_length, file_skip_bytes))
            if file_skip_bytes != file_length:
                assert file_skip_bytes < file_length
                file_bytes = 0
                md5 = hashlib.md5()
                with open(abs_path, "rb") as fp:
                    if file_skip_bytes > 0:
                        fp.seek(file_skip_bytes)
                        file_bytes += file_skip_bytes
                        md5 = None
                    while file_bytes < file_length:
                        assert total_bytes % piece_length == piece_bytes
                        piece = fp.read(piece_length - piece_bytes)
                        total_bytes += len(piece)
                        piece_bytes += len(piece)
                        file_bytes += len(piece)
                        sha1.update(piece)
                        if md5:
                            md5.update(piece)
                            if file_bytes == file_length:
                                md5s.append(md5.hexdigest())
                        if piece_bytes == piece_length or total_bytes == total_length:
                            assert file_skip_bytes == 0
                            assert md5
                            sha1_digest = sha1.digest()
                            sha = shas.read(20)
                            check(len(sha) == 20, repr(sha))
                            if sha == sha1_digest:
                                for j, md5_hexdigest in enumerate(md5s, md5_file):
                                    assert md5_hexdigest
                                    check(not download_md5[j] or download_md5[j] == md5_hexdigest)
                                    download_md5[j] = md5_hexdigest
                            piece_bytes = 0
                            sha1 = hashlib.sha1()
                            md5_file += len(md5s)
                            del md5s[:]

                            if sha != sha1_digest:
                                print >> sys.stderr, "Bad checksum {!r} pos {}".format(rel_path, file_bytes - len(piece))
                                file_skip_bytes = file_length - file_bytes
                                if total_bytes + file_skip_bytes < total_length:
                                    file_skip_bytes -= file_skip_bytes % piece_length
                                piece_skip_bytes = file_skip_bytes
                                total_bytes += file_skip_bytes
                                piece_bytes = (piece_bytes + file_skip_bytes) % piece_length
                                md5_file = i + 1

                                file_bytes += file_skip_bytes
                                fp.seek(file_bytes)
                                md5 = None

                    check(not fp.read())

            if piece_skip_bytes:
                for _ in range(piece_skip_bytes // piece_length):
                    sha = shas.read(20)
                    check(len(sha) == 20, repr(sha))
                if piece_skip_bytes % piece_length != 0 and total_bytes == total_length:
                    sha = shas.read(20)
                    check(len(sha) == 20, repr(sha))

        check(total_bytes == total_length)
        r = shas.read()
        check(len(r) == 0, len(r))

        make_unicode(torrent)
        save_json_torrent(torrent, json_dir, torrent_id)


def make_symlink_tree(src_dir, dst_dir):
    """Create symlink directory tree at dst_mirroring src_dir tree.

    This function is generic and doesn't assume anything about json or
    torrent files. It can a create a symlink tree mirroring any arbitrary
    source directory.

    This function isn't meant to run incrementally and will fail if
    anything already exists at paths where symlinks would be created."""
    for src_root, dirs, files in os.walk(src_dir, topdown=False):
        rel = os.path.relpath(src_root, src_dir)
        dst_root = os.path.join(dst_dir, rel)
        if not os.path.exists(dst_root): os.makedirs(dst_root)
        for f in files:
            src_file = os.path.join(src_root, f)
            dst_file = os.path.join(dst_root, f)
            if os.path.islink(src_file):
                subprocess.check_call(["cp", "-an", "--reflink", src_file, dst_file])
            else:
                subprocess.check_call(["ln", "-s", src_file, dst_file])
                subprocess.check_call(["touch", "-hr", src_file, dst_file])
        subprocess.check_call(["touch", "-r", src_root, dst_root])


def move_torrents(src_dir, torrent_dir):
    """Move any torrent files out of src_dir into torrent_dir.

    This function replaces any symlinks in torrent_dir pointing into
    src_dir with the actual file content from src_dir (moving that
    content from src_dir to torrent_dir), and replaces the content
    moved out of src_dir with /mnt/download/torrent symlinks.

    Can run incrementally. Doesn't modify any file in torrent_dir
    that is not a symlink into src_dir, and doesn't modify any files
    in src_dir not pointed to by a symlink in torrent_dir."""
    subprocess.check_call(["touch", "/tmp/torrent_dir_mtime"])
    subprocess.check_call(["touch", "/tmp/src_dir_mtime"])

    for torrent_dir_path, dirs, files in os.walk(torrent_dir):
        rel = os.path.relpath(torrent_dir_path, torrent_dir)
        subprocess.check_call(["touch", "-hr", torrent_dir_path, "/tmp/torrent_dir_mtime"])

        for f in files:
            torrent_file_path = os.path.join(torrent_dir_path, f)
            if not os.path.islink(torrent_file_path):
                continue

            src_file_path = os.readlink(torrent_file_path)
            if not starts(src_file_path, src_dir):
                continue

            src_dir_path = os.path.dirname(src_file_path)
            subprocess.check_call(["touch", "-hr", src_dir_path, "/tmp/src_dir_mtime"])
            os.rename(src_file_path, torrent_file_path)
            os.symlink(os.path.join("/mnt/download/torrent", rel, f), src_file_path)
            subprocess.check_call(["touch", "-hr", torrent_file_path, src_file_path])
            subprocess.check_call(["touch", "-hr", "/tmp/src_dir_mtime", src_dir_path])

        subprocess.check_call(["touch", "-hr", "/tmp/torrent_dir_mtime", torrent_dir_path])

    os.unlink("/tmp/torrent_dir_mtime")
    os.unlink("/tmp/src_dir_mtime")

def save_torrents(torrents, json_dir):
    make_unicode(torrents)
    for torrent_id, t in torrents.iteritems():
        save_json_torrent(t, json_dir, torrent_id)

def load_torrents(json_dir):
    torrents = {}
    for torrent_id in list_json_torrents(json_dir):
        torrents[torrent_id] = load_json_torrent(json_dir, torrent_id)
    make_str(torrents)
    return torrents


def save_json_torrent(torrent, json_dir, torrent_id):
    with open(os.path.join(json_dir, torrent_id + ".json"), "w") as fp:
        json.dump(torrent, fp, indent=4, separators=(",", ": "))


def load_json_torrent(json_dir, torrent_id):
    with open(os.path.join(json_dir, torrent_id + ".json")) as fp:
        return json.load(fp, object_pairs_hook=OrderedDict)


def list_json_torrents(json_dir):
    for f in os.listdir(json_dir):
        if not f.endswith(".json"):
            continue
        yield  f[:-len(".json")]


def get_torrent_files(info):
    if "files" in info:
        for file_info in info["files"]:
            yield os.path.join(info["name"], *file_info["path"]), file_info["length"]
    else:
        yield info["name"], info["length"]


def get_timestamp(torrent):
   return (field(torrent, "state", "time_added")
           or field(torrent, "fastresume", "added_time")
           or field(torrent, "download", "mtime"))


def torrent_file(torrent, i):
    info = torrent["data"]["info"]
    if "files" in info:
        return os.path.join(info["name"], info["files"][i]["path"])
    check(i == 0, i)
    return info["name"]


def obj_dict(obj):
    assert set(dir(obj)) - set(obj.__dict__.keys()) == {
        "__doc__", "__init__", "__module__"}
    return obj.__dict__.copy()


def sort_dicts(obj):
    return update_obj(obj, lambda v: OrderedDict(
        x for x in sorted(v.items())) if isinstance(v, dict) else v)


def unsort_dicts(obj):
    return update_obj(obj, lambda v: dict(v.items())
                           if isinstance(v, OrderedDict) else v)


def make_unicode(obj):
    return update_obj(obj,
                      lambda v: decode_ascii_surrogateescape(v)
                      if isinstance(v, str) else v)


def make_str(obj):
    return update_obj(obj,
                      lambda v: encode_ascii_surrogateescape(v)
                      if isinstance(v, unicode) else v)

def update_obj(obj, cb):
    obj = cb(obj)
    if hasattr(obj, "items"):
        for k, v in obj.items():
            del obj[k]
            obj[cb(k)] = update_obj(v, cb)
    elif hasattr(obj, "__setitem__"):
        for k, v in enumerate(obj):
            obj[k] = update_obj(v, cb)
    return obj


def sort_keys(ordered_dict, keys):
    update = []
    for key in keys:
        try:
            update.append((key, ordered_dict[key]))
        except KeyError:
            pass
        else:
            del ordered_dict[key]
    check(not ordered_dict)
    ordered_dict.update(update)


# Equivalent to python3: bytestr.decode("ascii", errors="surrogateescape"))
def decode_ascii_surrogateescape(bytestr):
    assert isinstance(bytestr, str)
    return u"".join(unichr(b if b < 128 else b + 0xdc00)
                    for b in map(ord, bytestr))


# Equivalent to python3: unicodestr.encode("ascii", errors="surrogateescape"))
def encode_ascii_surrogateescape(unicodestr):
    assert isinstance(unicodestr, unicode)
    return "".join(chr(c if c < 128 else c - 0xdc00)
                   for c in map(ord, unicodestr))


def field(obj, *path, **kwargs):
    default_value = kwargs.pop("default_value", None)
    assert not kwargs
    for component in path:
        if component not in obj:
            return default_value
        obj = obj[component]
    return obj


def starts(path, start):
    l = len(start)
    return path.startswith(start) and (len(path) == l or path[l] == os.sep)


def check(cond, error=None):
    if not cond:
        raise Exception(error)


def monkeypatch_bencode():
    """Change deluge bencode decoder to preserve dict key order."""
    def decode_dict(x, f):
        r, f = OrderedDict(), f+1
        while x[f] != "e":
            k, f = bencode.decode_string(x, f)
            r[k], f = bencode.decode_func[x[f]](x, f)
        return (r, f + 1)

    bencode.decode_dict = decode_dict
    bencode.decode_func["d"] = decode_dict

    def encode_ordered_dict(x,r):
        r.append('d')
        for k, v in x.iteritems():
            r.extend((str(len(k)), ':', k))
            bencode.encode_func[type(v)](v, r)
        r.append('e')

    bencode.encode_func[OrderedDict] = encode_ordered_dict


monkeypatch_bencode()
