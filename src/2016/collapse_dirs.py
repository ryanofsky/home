# grep -ani 'mp3$' old.* | sed 's,old\.\([0-9]\+\).*  old/,/mnt/data/old.\1/latest/old/,' > tmp/mp3



import os
import sys

def starts(path, root):
  return path.startswith(root) and (len(path) == len(root) or path[len(root)] == os.sep)

prev_root = None
prev_file = None
prev_root_dir = None
prev_root_base = None
count = 0
for line in sys.stdin:
  line = line.rstrip("\n")
  count += 1
  if prev_root is not None:
    if starts(line, prev_root):
      continue
    if starts(line, prev_root_dir):
      prev_file = os.path.join(prev_root_base, prev_file)
      prev_root = prev_root_dir
      prev_root_dir = os.path.dirname(prev_root)
      assert prev_root_dir
      continue
  if prev_root is not None:
    print("{} {}         {}".format(count, prev_root, prev_file))
    count = 0
  prev_root, prev_file = os.path.split(line)
  prev_root_dir, prev_root_base = os.path.split(prev_root)
  assert prev_root_dir
  
if prev_root is not None:
    print("{} {}         {}".format(count, prev_root, prev_file))
    
