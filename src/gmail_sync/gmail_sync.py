#!/usr/bin/python3

import datetime
import imaplib
import io
import json
import os
import urllib
import urllib.parse
import urllib.request
import yaml
import os
import contextlib
import collections
import re

CONFIG_OAUTH2_CLIENT_ID = "oauth2_client_id"
CONFIG_OAUTH2_CLIENT_SECRET = "oauth2_client_secret"
CONFIG_OAUTH2_REFRESH_TOKEN = "oauth2_refresh_token"
CONFIG_OAUTH2_URL = "oauth2_url"
CONFIG_USER = "user"
CONFIG_LAST_MODSEQ = "last_modseq"
CONFIG_NEXT_UID = "next_uid"
CONFIG_UIDVALIDITY = "uidvalidity"
NFO_GM_THRID = "gm_thrid"
NFO_GM_MSGID = "gm_msgid"
NFO_GM_LABELS = "gm_labels"
NFO_MODSEQ = "modseq"
NFO_DATE = "date"
NFO_FLAGS = "flags"

STORE_DIR = "~/store/mail/2013"
OAUTH2_URL = "https://accounts.google.com/o/oauth2/token"

def main():
  store = Store(os.path.expanduser(STORE_DIR))
  imap = connect(store)
  setup_capture(imap, store)
  store.start_capture()
  try:
    sync(store, imap)
    log_counters(store)
    imap.close()
    imap.logout()
  finally:
    store.stop_capture()

class Store:
  def __init__(self, directory):
    self.directory = directory
    self.config_path = os.path.join(directory, "config.yaml")
    self.log_path = os.path.join(directory, "log.txt")
    self.config = load_data(self.config_path)
    self.read_bytes = 0
    self.sent_bytes = 0

  def log(self, msg):
    with open(self.log_path, "a") as fp:
      fp.write("{} {}\n".format(datetime.datetime.utcnow().isoformat(), msg))

  def save_config(self):
    return save_data(self.config_path, self.config)

  def uid(self, uid):
    return os.path.join(self.directory, uid_path(uid))

  def msg_path(self, uid):
    return self.uid(uid) + ".txt"

  def nfo_path(self, uid):
    return self.uid(uid) + ".yaml"

  def del_path(self, uid):
    return self.uid(uid) + ".del"

  def start_capture(self):
    t = timestamp()
    assert not hasattr(self, "capture_fp")
    self.capture_fp = open(os.path.join(self.directory, t + ".cap"), "ab")
    self.capture_fp.write(t.encode("utf8"))
    self.capture_fp.write(b" open\n")

  def stop_capture(self):
    self.capture_fp.write(timestamp().encode("utf8"))
    self.capture_fp.write(b" close\n")
    self.capture_fp.close()
    del self.capture_fp

  def capture_read(self, string):
    self.read_bytes += len(string)
    self.capture_fp.write(timestamp().encode("utf8"))
    self.capture_fp.write(" server {}\n".format(len(string)).encode("utf8"))
    self.capture_fp.write(string)
    self.capture_fp.write(b"\n")

  def capture_write(self, string):
    self.sent_bytes += len(string)
    self.capture_fp.write(timestamp().encode("utf8"))
    self.capture_fp.write(" client {}\n".format(len(string)).encode("utf8"))
    self.capture_fp.write(string)
    self.capture_fp.write(b"\n")

def timestamp():
  return "{:%Y%m%dT%H%M%S.%f}".format(datetime.datetime.utcnow())

def connect(store):
  data_str = urllib.parse.urlencode({
    'client_id': store.config[CONFIG_OAUTH2_CLIENT_ID],
    'client_secret': store.config[CONFIG_OAUTH2_CLIENT_SECRET],
    'refresh_token': store.config[CONFIG_OAUTH2_REFRESH_TOKEN],
    'grant_type': 'refresh_token'
  })
  with urllib.request.urlopen(OAUTH2_URL, bytes(data_str, "utf8")) as fp:
    fp = io.TextIOWrapper(fp, "utf8")
    http = json.load(fp)
    oauth2_str = 'user=%s\001auth=Bearer %s\001\001' % (store.config[CONFIG_USER], http['access_token'])
    imap = imaplib.IMAP4_SSL('imap.gmail.com')
    imap.debug = 4
    imap.authenticate('XOAUTH2', lambda response: oauth2_str)
    return imap

def setup_capture(imap, store):
  wrapped_read = imap.read
  wrapped_readline = imap.readline
  wrapped_send = imap.send

  def read(size):
    ret = wrapped_read(size)
    store.capture_read(ret)
    return ret

  def readline():
    ret = wrapped_readline()
    store.capture_read(ret)
    return ret

  def send(data):
    store.capture_write(data)
    return wrapped_send(data)

  imap.read = read
  imap.readline = readline
  imap.send = send

def sync(store, imap):
  # FIXME: Should add on QRESYNC param when gmail supports it (rfc7162)
  imap.select('"[Gmail]/All Mail"', readonly=True)
  last_modseq = store.config.get(CONFIG_LAST_MODSEQ, 0)
  last_next_uid = store.config.get(CONFIG_NEXT_UID)
  last_uidvalidity = store.config.get(CONFIG_UIDVALIDITY)
  max_modseq = int(imap.untagged_responses["HIGHESTMODSEQ"][0])
  next_uid = int(imap.untagged_responses["UIDNEXT"][0])
  max_uid = next_uid - 1
  min_uid = last_next_uid if last_next_uid is not None else max_uid
  uidvalidity = int(imap.untagged_responses["UIDVALIDITY"][0])
  if last_uidvalidity is not None and last_uidvalidity != uidvalidity:
    raise Exception("uidvalidity {} expected {}".format(uidvalidity, last_uidvalidity))

  # Search for uids greater than last downloaded message.
  uids = search(imap, "{}:{}".format(min_uid, max_uid))
  uids = collections.OrderedDict((x, None) for x in sorted(uids))
  for uid in range(min_uid, next_uid):
    if uid not in uids:
      touch(store.del_path(uid))
      continue
    msg_path = store.msg_path(uid)
    if os.path.exists(msg_path):
      continue
    nfo, body = fetch(imap, uid, True)

    save_data(store.nfo_path(uid), nfo)
    make_parent_dirs(msg_path)
    with atomic_write(msg_path, binary=True) as fp:
      fp.write(body)

  store.config[CONFIG_NEXT_UID] = next_uid
  store.save_config()

  uids = search(imap, 'MODSEQ {}'.format(last_modseq))
  last_modseq = last_modseq
  for uid in uids:
    nfo, body = fetch(imap, uid, False)
    if last_modseq is None or last_modseq < nfo[NFO_MODSEQ]:
      last_modseq = nfo[NFO_MODSEQ]
    save_data(store.nfo_path(uid), nfo)
    make_parent_dirs(msg_path)

  store.config[CONFIG_LAST_MODSEQ] = last_modseq
  store.save_config()

def search(imap, query):
  status, data = imap.uid("SEARCH", None, query)
  if status != "OK":
     raise Exception("search failed status={!r} data={!r}".format(status, data))
  return map(int, re.match(b"[0-9 ]*", data[0]).group(0).split())


def fetch(imap, uid, fetch_body):
  req_fields = ("(X-GM-THRID X-GM-MSGID X-GM-LABELS MODSEQ INTERNALDATE "
                "FLAGS{})".format(" BODY.PEEK[]" if fetch_body else ""))
  re_fields = (br"(\d+) \(X-GM-THRID (\d+) X-GM-MSGID (\d+) X-GM-LABELS "
               br"\(([^)]*)\) UID (\d+) MODSEQ \((\d+)\) INTERNALDATE \"([^\"]+)\""
               br" FLAGS \(([^)]*)\)" +
               (br" BODY\[\] {(\d+)}" if fetch_body else b""))
  status, data = imap.uid('fetch', str(uid).encode("utf8"), req_fields)
  if status != "OK":
    raise Exception("search failed status={!r} data={!r}".format(status, data))

  if fetch_body:
    if len(data) != 2 or len(data[0]) != 2 or data[1] != b")":
      raise Exception("search failed status={!r} data={!r}".format(status, data))
    nfo_str = data[0][0]
    body = data[0][1]
  else:
    if len(data) < 1:
      raise Exception("search failed status={!r} data={!r}".format(status, data))
    nfo_str = data[0]
    body = None

  m = re.match(re_fields, nfo_str)
  if not m:
    raise Exception("re_fields {!r} nfo_str {!r}".format(re_fields, nfo_str))
    raise Exception("search failed status={!r} data={!r}".format(status, data))
  seq_num = int(m.group(1))
  gm_thrid = int(m.group(2))
  gm_msgid = int(m.group(3))
  gm_labels = m.group(4).decode("utf8").split()
  uid_num = int(m.group(5))
  if uid_num != uid:
    raise Exception("expect uid {} got uid {}".format(uid, uid_num))
  modseq = int(m.group(6))
  date = m.group(7).decode("utf8")
  flags = m.group(8).decode("utf8").split()
  if fetch_body:
    body_len = int(m.group(9))
    if body_len != len(body):
       raise Exception("search failed status={!r} data={!r}".format(status, data))
  nfo = collections.OrderedDict()
  nfo[NFO_GM_THRID] = gm_thrid
  nfo[NFO_GM_MSGID] = gm_msgid
  nfo[NFO_GM_LABELS] = gm_labels
  nfo[NFO_MODSEQ] = modseq
  nfo[NFO_DATE] = date
  nfo[NFO_FLAGS] = flags
  return nfo, body

def make_parent_dirs(filename):
  dirname = os.path.dirname(filename)
  if dirname and not os.path.exists(dirname):
    os.makedirs(dirname)

def touch(filename):
  make_parent_dirs(filename)
  with open(filename, 'a'):
    pass

def load_data(filename):
  data = {}
  if os.path.exists(filename):
    with open(filename, "r") as fp:
      data = ordered_load(fp) or data
  return data

def save_data(filename, data):
  make_parent_dirs(filename)
  with atomic_write(filename, binary=False) as fp:
    ordered_dump(data, stream=fp)

def uid_path(uid):
  if uid < 0 or uid > 99999999 or not isinstance(uid, int):
    raise Exception("Invalid uid {!r}".format(uid))
  digits = "{:0>8}".format(uid)
  assert len(digits) == 8
  return os.path.join(digits[:4], digits[4:])

def log_counters(store):
  store.log("read {} write {}".format(store.read_bytes, store.sent_bytes))

# http://stackoverflow.com/questions/5121931/in-python-how-can-you-load-yaml-mappings-as-ordereddicts
def ordered_load(stream, Loader=yaml.Loader, object_pairs_hook=collections.OrderedDict):
  class OrderedLoader(Loader):
    pass
  def construct_mapping(loader, node):
    loader.flatten_mapping(node)
    return object_pairs_hook(loader.construct_pairs(node))
  OrderedLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    construct_mapping)
  return yaml.load(stream, OrderedLoader)

def ordered_dump(data, stream=None, Dumper=yaml.Dumper, **kwds):
  class OrderedDumper(Dumper):
    pass
  def _dict_representer(dumper, data):
    return dumper.represent_mapping(
      yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
      data.items())
  OrderedDumper.add_representer(collections.OrderedDict, _dict_representer)
  return yaml.dump(data, stream, OrderedDumper, **kwds)

# http://stackoverflow.com/questions/2333872/atomic-writing-to-file-with-python
@contextlib.contextmanager
def atomic_write(filepath, binary=False, fsync=True):
  tmppath = filepath + '~'
  while os.path.isfile(tmppath):
    tmppath += '~'
  try:
    with open(tmppath, 'wb' if binary else 'w') as file:
      yield file
      if fsync:
        file.flush()
        os.fsync(file.fileno())
    os.rename(tmppath, filepath)
  finally:
    try:
      os.remove(tmppath)
    except (IOError, OSError):
      pass

if __name__ == "__main__":
  main()
