from ansible import constants as C
from ansible.plugins.action import ActionBase
from ansible.utils.unicode import to_bytes, to_unicode
from collections import OrderedDict
import datetime
import yaml
import time
import os
import re
import stat


class TemplateFile:
    def __init__(self):
        self.template_path = None
        self.info_path = None
        self.upstream_paths = set()
        self.temp_upstream_path = None


class ActionModule(ActionBase):
    def run(self, tmp=None, task_vars=None):
        results = super(ActionModule, self).run(tmp, task_vars)
        src = self._task.args.get("src", None)
        dest = self._task.args.get("dest", None)
        hostname = task_vars["inventory_hostname"]

        # Group src files into TemplateFiles.
        tfiles = {}  # template_path -> TemplateFile
        for root, dirs, files in os.walk(src):
            rel = os.path.relpath(root, src)
            for filename in files:
                path = os.path.join(rel, filename)
                m = re.match(r"^(.*?)\.upstream(\..*)?$", path)
                tfile = tfiles.setdefault(
                    path if not m else m.group(1), TemplateFile())
                if m:
                    if m.group(2) == ".info":
                        assert tfile.info_path is None
                        tfile.info_path = path
                    else:
                        assert path not in tfile.upstream_paths
                        tfile.upstream_paths.add(path)
                else:
                    assert tfile.template_path is None
                    tfile.template_path = path

        # Build pull request.
        files = []
        for path, tfile in tfiles.items():
            if tfile.info_path is None:
                tfile.info_path = path + ".upstream.info"
                tfile.info = OrderedDict()
            else:
                with open(os.path.join(src, tfile.info_path)) as fp:
                    tfile.info = ordered_load(fp, yaml.SafeLoader)

            tfile.upstream_path = path + ".upstream." + hostname
            if tfile.upstream_path not in tfile.upstream_paths:
                tfile.upstream_path = path + ".upstream"

            remote_path = os.path.join(dest, path)
            pushed_prev = tfile.upstream_path in tfile.info
            key = path
            files.append((remote_path, pushed_prev, key))

        pull_result = self._execute_module(module_name="rtemplate",
                                           module_args=dict(mode="pull",
                                                            files=files),
                                           task_vars=task_vars)
        if "exception" in pull_result:
            raise Exception(pull_result["exception"])

        for (key, content, st,
             temp_upstream_path) in pull_result["pull_results"]:
            tfile = tfiles[key]
            tfile.temp_upstream_path = temp_upstream_path
            if content is not None:
                with open(os.path.join(src, tfile.upstream_path), "wb") as fp:
                    fp.write(content)
            info = tfile.info.setdefault(tfile.upstream_path, OrderedDict())
            if st is not None:
                st_mode, st_uid, st_gid, st_atime, st_mtime, st_ctime = st
                info["st_mode"] = st_mode
                info["st_uid"] = st_uid
                info["st_gid"] = st_gid
                info["st_atime"] = st_atime
                info["st_mtime"] = st_mtime
                info["st_ctime"] = st_ctime
            with open(os.path.join(src, tfile.info_path), "wb") as fp:
                ordered_dump(tfile.info, fp, yaml.SafeDumper)
            ordered_dump(info, Dumper=yaml.SafeDumper)

        changes = []
        for path, tfile in tfiles.items():
            if tfile.template_path is not None:
                remote_path = os.path.join(dest, path)
                source = os.path.join(src, tfile.template_path)
                content = self._fill_template(source, task_vars)

                symlink = tfile.upstream_path in tfile.info and stat.S_ISLNK(
                    tfile.info[tfile.upstream_path].get("st_mode", 0))
                delete = False
                changes.append((remote_path, content, symlink, delete))

            if tfile.temp_upstream_path is not None:
                remote_path = tfile.temp_upstream_path
                content = None
                symlink = None
                delete = True
                changes.append((remote_path, content, symlink, delete))

        push_result = self._execute_module(module_name="rtemplate",
                                           module_args=dict(mode="push",
                                                            files=changes),
                                           task_vars=task_vars)
        if "exception" in push_result:
            raise Exception(push_result["exception"])

        results.update(pull_result=pull_result,
                       push_result=push_result,
                       changed=push_result["changed"])
        return results


    def _fill_template(self, source, task_vars):
            # Copied from https://github.com/ansible/ansible/blob/devel/lib/ansible/plugins/action/template.py
            with open(source, 'r') as f:
                template_data = to_unicode(f.read())

            try:
                template_uid = pwd.getpwuid(os.stat(source).st_uid).pw_name
            except:
                template_uid = os.stat(source).st_uid

            temp_vars = task_vars.copy()
            temp_vars['template_host']     = os.uname()[1]
            temp_vars['template_path']     = source
            temp_vars['template_mtime']    = datetime.datetime.fromtimestamp(os.path.getmtime(source))
            temp_vars['template_uid']      = template_uid
            temp_vars['template_fullpath'] = os.path.abspath(source)
            temp_vars['template_run_date'] = datetime.datetime.now()

            managed_default = C.DEFAULT_MANAGED_STR
            managed_str = managed_default.format(
                host = temp_vars['template_host'],
                uid  = temp_vars['template_uid'],
                file = to_bytes(temp_vars['template_path'])
            )
            temp_vars['ansible_managed'] = time.strftime(
                managed_str,
                time.localtime(os.path.getmtime(source))
            )

            # Create a new searchpath list to assign to the templar environment's file
            # loader, so that it knows about the other paths to find template files
            searchpath = [self._loader._basedir, os.path.dirname(source)]
            if self._task._role is not None:
                if C.DEFAULT_ROLES_PATH:
                    searchpath[:0] = C.DEFAULT_ROLES_PATH
                searchpath.insert(1, self._task._role._role_path)

            self._templar.environment.loader.searchpath = searchpath

            old_vars = self._templar._available_variables
            self._templar.set_available_variables(temp_vars)
            resultant = self._templar.template(template_data, preserve_trailing_newlines=True, escape_backslashes=False, convert_data=False)
            self._templar.set_available_variables(old_vars)

            return resultant


# From http://stackoverflow.com/questions/5121931/in-python-how-can-you-load-yaml-mappings-as-ordereddicts
def ordered_load(stream, Loader=yaml.Loader, object_pairs_hook=OrderedDict):
    class OrderedLoader(Loader):
        pass

    def construct_mapping(loader, node):
        loader.flatten_mapping(node)
        return object_pairs_hook(loader.construct_pairs(node))

    OrderedLoader.add_constructor(
        yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, construct_mapping)
    return yaml.load(stream, OrderedLoader)


def ordered_dump(data, stream=None, Dumper=yaml.Dumper, **kwds):
    class OrderedDumper(Dumper):
        pass

    def _dict_representer(dumper, data):
        return dumper.represent_mapping(
            yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, data.items())

    OrderedDumper.add_representer(OrderedDict, _dict_representer)
    return yaml.dump(data, stream, OrderedDumper, **kwds)
