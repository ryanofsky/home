#!/usr/bin/python

DOCUMENTATION = """
---
module: test_plugin
short_description: Test.
description:
     - The M(test_plugin) module.
options:
  arg:
    description:
      - Argument.
    required: true
"""

EXAMPLES = """
# Call test_plugin
- test_plugin: arg=arg
"""


def main():
    module = AnsibleModule(argument_spec=dict(mod_arg=dict(required=True,
                                                           type="path"), ), )

    mod_arg = module.params["mod_arg"]

    if not mod_arg:
        module.fail_json(msg="not mod_arg")

    res_args = {}
    res_args["changed"] = True
    res_args["mod_ret"] = "mod_ret from mod_arg {!r}".format(mod_arg)
    module.exit_json(**res_args)

# this is magic, see lib/ansible/module_common.py
from ansible.module_utils.basic import *

if __name__ == "__main__":
    main()
