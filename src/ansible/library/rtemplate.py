#!/usr/bin/python

DOCUMENTATION = """
---
module: rtemplate
short_description: Recursively push templates.
description:
     - The M(rtemplate) module, recursively updates templates on the host.
options:
  src:
    description:
      - Local template source directory
    required: true
  dest:
    description:
      - Remote destination directory.
    required: true
"""

EXAMPLES = """
# Call rtemplate
- test_plugin: src=templates/etc dest=/etc
"""


def main():
    module = AnsibleModule(argument_spec=dict(mode=dict(required=True,
                                                        type="str"),
                                              files=dict(required=True,
                                                         type="list")))
    mode = module.params["mode"]
    files = module.params["files"]

    ret = dict(changed=False)
    if mode == "pull":
        pull_results = ret["pull_results"] = []
        for path, pushed_prev, key in files:
            upstream_path = temp_upstream_path = None
            exists = os.path.exists(path) or os.path.islink(path)
            if not pushed_prev and exists:
                upstream_path = path
            else:
                dirname, basename = os.path.split(path)
                cfgs = sorted(glob.glob(os.path.join(
                    glob_escape(dirname), "._cfg????_" + glob_escape(
                        basename))))
                if cfgs:
                    upstream_path = temp_upstream_path = cfgs[0]

            if upstream_path is not None:
                s = os.lstat(upstream_path)
                if stat.S_ISLNK(s.st_mode):
                    content = os.readlink(upstream_path)
                else:
                    content = open(upstream_path, "rb").read()
                content = base64.b64encode(content)
                pull_results.append((key, exists, content, (
                    s.st_mode, s.st_uid, s.st_gid, s.st_atime, s.st_mtime,
                    s.st_ctime), temp_upstream_path))
            else:
                pull_results.append((key, exists, None, None, None))
    elif mode == "push":
        ret["changed"] = False
        for path, content, symlink, delete in files:
            if delete:
                assert content is None
                os.unlink(path)
            else:
                prev_content = None
                prev_symlink = False
                if os.path.islink(path):
                    prev_content = os.readlink(path)
                    prev_symlink = True
                elif os.path.exists(path):
                    prev_content = open(path).read()

                if content == prev_content and symlink == prev_symlink:
                    continue

                dirname = os.path.dirname(path)
                if not os.path.exists(dirname):
                    os.makedirs(dirname)
                if symlink:
                    if prev_content is not None:
                        os.unlink(path)
                    os.symlink(content, path)
                else:
                    with open(path, "wb") as fp:
                        fp.write(content)
            ret["changed"] = True

    module.exit_json(**ret)


def glob_escape(pathname):
    # From python3 glob.escape.
    return re.sub('([*?[])', r'[\1]', pathname)

# this is magic, see lib/ansible/module_common.py
from ansible.module_utils.basic import *
import glob
import base64

if __name__ == "__main__":
    main()
