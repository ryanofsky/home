#!/usr/bin/env python3

from collections import OrderedDict
from datetime import datetime, timedelta
from email.utils import parsedate_tz, mktime_tz
from urllib.parse import urlparse
import argparse
import json
import os
import sqlite3


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--firefox", "-f", action="append",
        help="path to .mozilla/firefox/PROFILE/places.sqlite file")
    parser.add_argument(
        "--chrome", "-c", action="append",
        help="Path to .config/chromium/Default/History file")
    args = parser.parse_args()

    for db in args.chrome or ():
        with connect_readonly(db) as conn:
            c = conn.cursor()
            c.execute("""
                SELECT id, target_path, total_bytes, start_time, end_time,
                    referrer, last_modified FROM downloads
                ORDER BY start_time DESC
            """)
            s = conn.cursor()
            for (idx, filename, size, start_time, end_time, referrer,
                 last_modified) in c.fetchall():
                s.execute("""
                    SELECT url FROM downloads_url_chains WHERE id = ?
                    ORDER BY chain_index
                """, (idx, ))
                urls = [url for url, in s.fetchall()]
                save_info(
                    filename,
                    url=urls[-1],
                    redirects=urls[:-1],
                    referrer=referrer,
                    size=size,
                    dtime=chrome_to_ns(end_time or start_time),
                    mtime=http_to_ns(last_modified) if last_modified else None,
                    incomplete=not end_time)

    for db in args.firefox or ():
        with connect_readonly(db) as conn:
            c = conn.cursor()
            c.execute("""
                SELECT p.url, fn.content AS filename, m.content AS metadata,
                     v.visit_date, v.visit_type, v.from_visit
                FROM moz_annos AS fn
                INNER JOIN moz_places AS p ON p.id = fn.place_id
                LEFT JOIN moz_historyvisits AS v
                    -- Select MAX below is needed because firefox create two
                    -- otherwise indistinguishable moz_historyvisits entries for
                    -- each download. Normally the visit times are a few seconds
                    -- apart so they might reflect the start and end times of
                    -- the download.
                    ON v.id = (SELECT MAX(id) FROM moz_historyvisits
                               WHERE place_id = p.id and visit_type = ?)
                LEFT JOIN moz_annos AS m ON m.place_id = p.id
                    AND m.anno_attribute_id
                        = (SELECT id FROM moz_anno_attributes
                           WHERE name = 'downloads/metaData')
                WHERE fn.anno_attribute_id
                    = (SELECT id FROM moz_anno_attributes
                       WHERE name = 'downloads/destinationFileName')
                ORDER BY v.id DESC
            """, (TRANSITION_DOWNLOAD, ))
            s = conn.cursor()
            for (url, filename, metadata_str, visit_date, visit_type,
                 prev_visit) in c.fetchall():
                s.execute("""
                    WITH RECURSIVE
                        r(depth, from_visit, place_id, visit_type) AS (
                            SELECT 0, from_visit, place_id, visit_type
                                FROM moz_historyvisits
                                WHERE id = ?
                            UNION ALL
                            SELECT r.depth + 1, v.from_visit, v.place_id,
                                v.visit_type
                            FROM r
                            INNER JOIN moz_historyvisits AS v
                                ON v.id = r.from_visit
                            WHERE r.visit_type IN (?,?)
                        )
                    SELECT p.url FROM r
                    INNER JOIN moz_places AS p ON p.id = r.place_id
                    ORDER BY depth DESC
               """, (prev_visit, TRANSITION_REDIRECT_PERMANENT,
                     TRANSITION_REDIRECT_TEMPORARY))
                prev = [prev_url for prev_url, in s.fetchall()]

                if metadata_str is None:
                    dtime = visit_date * 1000
                    size = None
                else:
                    metadata = json.loads(metadata_str)
                    assert metadata["state"] == 1
                    size = metadata["fileSize"]
                    dtime = metadata["endTime"] * 1000 * 1000

                save_info(filename,
                          url,
                          redirects=prev[1:],
                          referrer=prev[0] if prev else None,
                          size=size,
                          dtime=dtime,
                          mtime=None,
                          incomplete=False)
                assert visit_type == TRANSITION_DOWNLOAD


def connect_readonly(filename):
    print("Open {!r}".format(filename))
    return sqlite3.connect("file:{}?mode=ro".format(filename), uri=True)


def save_info(filename, url, redirects, referrer, size, dtime, mtime,
              incomplete):
    base = os.path.basename(filename) if filename else os.path.basename(
        urlparse(url).path) or "_"
    if incomplete:
        base += ".incomplete"

    info = OrderedDict()
    info["url"] = url
    if redirects:
        info["redirects"] = redirects
    if referrer is not None:
        info["referrer"] = referrer
    if size is not None:
        info["size"] = size

    output_name = write_file(base, "", mtime or dtime)
    write_file(output_name + ".info",
               json.dumps(info, indent=4, separators=(',', ': ')),
               dtime)
    #print(json.dumps(info))


def write_file(path, contents, mtime):
    while os.path.exists(path):
        path += "_"
    with open(path, "w") as fp:
        fp.write(contents)
    os.utime(path, ns=(mtime, mtime))
    return path


def http_to_ns(http):
    return 1000 * 1000 * 1000 * mktime_tz(parsedate_tz(http))


def chrome_to_ns(chrome):
    return 1000 * (chrome + (datetime(1601, 1, 1) - datetime(1970, 1, 1)) /
                   timedelta(microseconds=1))


# From http://www.forensicswiki.org/wiki/Mozilla_Firefox_3_History_File_Format
TRANSITION_LINK = 1
TRANSITION_TYPED = 2
TRANSITION_BOOKMARK = 3
TRANSITION_EMBED = 4
TRANSITION_REDIRECT_PERMANENT = 5
TRANSITION_REDIRECT_TEMPORARY = 6
TRANSITION_DOWNLOAD = 7


if __name__ == "__main__":
    main()
