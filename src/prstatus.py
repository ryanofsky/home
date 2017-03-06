"""
Generate status line for github issue.

mkdir -p /home/russ/cc/prstatus/cache
python3 prstatus.py 8775

"""

import aiohttp
import argparse
import asyncio
import os
import re
from collections import OrderedDict, namedtuple
from enum import Enum
import parse

CACHE_DIR = "/home/russ/cc/prstatus/cache"
HEADERS = {"Accept": "application/vnd.github.black-cat-preview+json"}

URLS = [
    ("https://api.github.com/repos/bitcoin/bitcoin/issues/{pr}", "{pr}-issue"),
    ("https://api.github.com/repos/bitcoin/bitcoin/issues/{pr}/comments",
     "{pr}-issue-comments"),
    ("https://api.github.com/repos/bitcoin/bitcoin/pulls/{pr}", "{pr}-pull"),
    ("https://api.github.com/repos/bitcoin/bitcoin/pulls/{pr}/comments",
     "{pr}-pull-comments"),
    ("https://api.github.com/repos/bitcoin/bitcoin/pulls/{pr}/reviews",
     "{pr}-pull-reviews"),
]

Attrib = namedtuple("Attrib", "abbrev label key")
_attribs = [
    Attrib(_abbrev, _label, _label.replace(" ", "_").upper())
    for _abbrev, _label in (_attrib.split(" ", 1) for _attrib in (
        "nw Needs Work",
        "nr Needs Review",
        "nm Needs Merge",
        "c Complete",
        "t Tested",
        "uc Unaddressed Comments",
        "ac All Comments Addressed",
        "rc Review Comments", ))
]
Attribs = namedtuple("Attribs", (_attrib.key
                                 for _attrib in _attribs))(*_attribs)
Labels = {_attrib.label: _attrib for _attrib in _attribs}

STATUS_FMT = "Status: {state}."


class Status:
    def __init__(self):
        self.state = None  # State
        self.reviewers = OrderedDict()  # username -> ACK
        self.attribs = set()  # Attrib

    def merge(self, base, other):
        pass

    def format(self):
        return STATUS_FMT.format(state=self.state.label)

    def parse(self, str):
        result = parse.parse(STATUS_FMT, str)
        self.state = Labels[result["state"]]

        #re.find("Status: <STATE>. (<ATTRIB>..., <ATTRIB>. Reviews from: <USERNAME> [utACK], .... Size <> lines, Age <> days, Wait <> days")


async def main(loop):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "-f",
        "--force",
        help="Force new download even if cached.",
        action="store_true")
    parser.add_argument("pr", type=int, help="bitcoin pr number")
    args = parser.parse_args()
    async with aiohttp.ClientSession(loop=loop) as session:
        downloads = [
            download_url(
                loop,
                session,
                url.format(pr=args.pr),
                os.path.join(
                    CACHE_DIR, filename.format(pr=args.pr)),
                args.force) for url, filename in URLS
        ]
        paths = await asyncio.gather(*downloads)

    print("paths")
    from pprint import pprint
    pprint(paths)


async def download_url(loop, session, url, filename, force):
    latest_fut = call(loop, latest_file, filename, force)
    if not force:
        latest = await latest_fut
        if latest is not None:
            print("skip", latest)
            return latest
        latest_fut = ret(filename)

    latest = None

    async def open_fut():
        nonlocal latest
        latest = await latest_fut
        return await AsyncFile.open(loop, latest, "wb")

    async with session.get(url, headers=HEADERS) as response:
        dest_file = await copy_stream(response.content, open_fut())
        await dest_file.close()

    return latest


class AsyncFile:
    @classmethod
    async def open(cls, loop, *args, **kwargs):
        return AsyncFile(loop, await call(loop, open, *args, **kwargs))

    def __init__(self, loop, fp):
        self.loop = loop
        self.fp = fp

    async def write(self, *args, **kwargs):
        return await call(self.loop, self.fp.write, *args, **kwargs)

    async def close(self):
        return await call(self.loop, self.fp.close)


async def copy_stream(source, dest_fut, buffer_size=16384):
    buf, dest = await asyncio.gather(source.read(buffer_size), dest_fut)
    while buf:
        res, buf = await asyncio.gather(
            dest.write(buf), source.read(buffer_size))
    return dest


async def ret(value):
    return value


async def call(loop, f, *args, **kwargs):
    return await loop.run_in_executor(None, lambda: f(*args, **kwargs))


def latest_file(path, new=False):
    dirname, filename = os.path.split(path)
    p = re.compile(re.escape(filename) + r"\.(\d+)$")
    found = None
    for f in os.listdir(dirname or os.curdir):
        if f == filename:
            if found is None:
                found = -1
        else:
            m = p.match(f)
            if m:
                n = int(m.group(1))
                if found is None or n > found:
                    found = n
    if found is None:
        return path if new else None
    elif new:
        found += 1
    return path if found == -1 else "{}.{}".format(path, found)


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main(loop))
