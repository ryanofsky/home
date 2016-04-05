from ansible.plugins.action import ActionBase


class ActionModule(ActionBase):
    def run(self, tmp=None, task_vars=None):
        results = super(ActionModule, self).run(tmp, task_vars)
        arg = self._task.args.get("arg", None)
        mod_ret = self._execute_module(module_name="test_plugin",
                                       module_args={"mod_arg": arg},
                                       tmp=tmp,
                                       task_vars=task_vars)
        results.update(mod_ret)
        results["diff"] = dict(before="before", after="after")
        return results
