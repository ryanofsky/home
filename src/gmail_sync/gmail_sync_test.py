#!/usr/bin/env python3.4

import asyncio
import gmail_sync
import imaplib
import os
import shutil
import socket
import tempfile
import threading
import unittest
import yaml
from unittest import mock

imaplib.Debug = 4

@asyncio.coroutine
def expect_command(test, reader, writer, expected_request, *responses):
  tag, request = (yield from reader.readline()).split(None, 1)
  test.assertEqual(request, expected_request)
  for last, response in last_iter(responses):
    if last:
      writer.write(tag + b" " + response)
    else:
      writer.write(response)

@asyncio.coroutine
def test_sync(test, loop, tmpdir):
  def client_thread(host, port):
    store = gmail_sync.Store(tmpdir)
    imap = imaplib.IMAP4(host, port)
    gmail_sync.setup_capture(imap, store)
    store.start_capture()
    try:
      store.config[gmail_sync.CONFIG_UIDVALIDITY] = 11
      def store_log(msg):
        with open(store.log_path, "a") as fp:
          fp.write(msg + "\n")
      store.log = store_log
      gmail_sync.sync(store, imap)
      gmail_sync.log_counters(store)
      imap.close()
      imap.logout()
    finally:
      store.stop_capture()

  future_client = asyncio.Future()
  server = yield from asyncio.start_server(asyncio.coroutine(
      lambda *args: future_client.set_result(args)),
      host="", port=0)
  host, port = server.sockets[0].getsockname()
  loop.run_in_executor(None, client_thread, host, port)

  client_reader, client_writer = yield from future_client
  client_writer.write(b"* PREAUTH\r\n")

  yield from expect_command(test, client_reader, client_writer,
    b"CAPABILITY\r\n",
    b"* CAPABILITY IMAP4rev1\r\n",
    b"OK (Success)\r\n")
  yield from expect_command(test, client_reader, client_writer,
    b"EXAMINE \"[Gmail]/All Mail\"\r\n",
    b"* OK [UIDVALIDITY 11]\r\n",
    b"* OK [UIDNEXT 10]\r\n",
    b"* OK [HIGHESTMODSEQ 1248303]\r\n",
    b"OK (Success)\r\n")
  yield from expect_command(test, client_reader, client_writer,
    b"UID SEARCH 0:9\r\n",
    b"* SEARCH 5 9 (MODSEQ 1248339)\r\n",
    b"OK (Success)\r\n")
  yield from expect_command(test, client_reader, client_writer,
    b"UID FETCH 5 (X-GM-THRID X-GM-MSGID X-GM-LABELS MODSEQ INTERNALDATE FLAGS BODY.PEEK[])\r\n",
    b'* 4 FETCH (X-GM-THRID 1423005031746205660 X-GM-MSGID 1423005041855881429 X-GM-LABELS (1-info filter/netflix tag/all tag/info) UID 5 MODSEQ (1005137) INTERNALDATE "01-Jan-2013 23:36:00 +0000" FLAGS (\\Seen) BODY[] {5}\r\nhowdy)\r\n',
    b"OK (Success)\r\n")
  yield from expect_command(test, client_reader, client_writer,
    b"UID FETCH 9 (X-GM-THRID X-GM-MSGID X-GM-LABELS MODSEQ INTERNALDATE FLAGS BODY.PEEK[])\r\n",
    b'* 8 FETCH (X-GM-THRID 1423005031746205660 X-GM-MSGID 1423005041855881429 X-GM-LABELS (1-info filter/netflix tag/all tag/info) UID 9 MODSEQ (1005137) INTERNALDATE "01-Jan-2013 23:36:00 +0000" FLAGS (\\Seen) BODY[] {5}\r\nhowdy)\r\n',
    b"OK (Success)\r\n")
  yield from expect_command(test, client_reader, client_writer,
    b"UID SEARCH MODSEQ 0\r\n",
    b'* SEARCH 2 (MODSEQ 1248339)\r\n',
    b"OK SEARCH completed (Success)\r\n")
  yield from expect_command(test, client_reader, client_writer,
    b"UID FETCH 2 (X-GM-THRID X-GM-MSGID X-GM-LABELS MODSEQ INTERNALDATE FLAGS)\r\n",
    b'* 1 FETCH (X-GM-THRID 1423005031746205660 X-GM-MSGID 1423005041855881429 X-GM-LABELS (1-info filter/netflix tag/all tag/info) UID 2 MODSEQ (1005137) INTERNALDATE "01-Jan-2013 23:36:00 +0000" FLAGS (\\Seen))\r\n',
    b"OK (Success)\r\n")
  yield from expect_command(test, client_reader, client_writer,
    b"CLOSE\r\n",
    b"OK (Success)\r\n")
  yield from expect_command(test, client_reader, client_writer,
    b"LOGOUT\r\n",
    b"OK (Success)\r\n")
  eof = yield from client_reader.readline()
  test.assertEqual(eof, b"");
  server.close()

  output_files = {}
  for root, dirs, files in os.walk(tmpdir, topdown=False):
    for name in files:
      relpath = os.path.relpath(root, tmpdir) if root != tmpdir else ""
      relfile = os.path.join(relpath, name)
      absfile = os.path.join(root, name)
      with open(absfile, "rb") as fp:
        if name.endswith(".cap"):
          continue
        elif name.endswith(".yaml"):
          data = yaml.load(fp)
        else:
          data = fp.read()
        output_files[relfile] = data

  expected_files = {
      '0000/0000.del': b'',
      '0000/0001.del': b'',
      '0000/0002.del': b'',
      '0000/0002.yaml': {'date': '01-Jan-2013 23:36:00 +0000',
                         'flags': ['\\Seen'],
                         'gm_labels': ['1-info',
                                       'filter/netflix',
                                       'tag/all',
                                       'tag/info'],
                         'gm_msgid': 1423005041855881429,
                         'gm_thrid': 1423005031746205660,
                         'modseq': 1005137},
      '0000/0003.del': b'',
      '0000/0004.del': b'',
      '0000/0005.txt': b'howdy',
      '0000/0005.yaml': {'date': '01-Jan-2013 23:36:00 +0000',
                         'flags': ['\\Seen'],
                         'gm_labels': ['1-info',
                                       'filter/netflix',
                                       'tag/all',
                                       'tag/info'],
                         'gm_msgid': 1423005041855881429,
                         'gm_thrid': 1423005031746205660,
                         'modseq': 1005137},
      '0000/0006.del': b'',
      '0000/0007.del': b'',
      '0000/0008.del': b'',
      '0000/0009.txt': b'howdy',
      '0000/0009.yaml': {'date': '01-Jan-2013 23:36:00 +0000',
                         'flags': ['\\Seen'],
                         'gm_labels': ['1-info',
                                       'filter/netflix',
                                       'tag/all',
                                       'tag/info'],
                         'gm_msgid': 1423005041855881429,
                         'gm_thrid': 1423005031746205660,
                         'modseq': 1005137},
      'config.yaml': {'last_modseq': 1005137, 'next_uid': 10, 'uidvalidity': 11},
      'log.txt': b'read 926 write 350\n'}

  test.maxDiff = None
  test.assertEqual(output_files, expected_files);

class GmailSyncTest(unittest.TestCase):
  def test_sync(self):
    tmpdir = tempfile.mkdtemp()
    try:
      loop = asyncio.get_event_loop()
      loop.run_until_complete(test_sync(self, loop, tmpdir))
    finally:
      shutil.rmtree(tmpdir)

# http://stackoverflow.com/questions/1630320/what-is-the-pythonic-way-to-detect-the-last-element-in-a-python-for-loop
def last_iter(it):
  # Ensure it's an iterator and get the first field
  it = iter(it)
  prev = next(it)
  for item in it:
    # Lag by one item so I know I'm not at the end
    yield 0, prev
    prev = item
    # Last item
  yield 1, prev

if __name__ == '__main__':
  unittest.main()
