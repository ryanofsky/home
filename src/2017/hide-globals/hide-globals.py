import os
import subprocess
import re
import sys

IGNORE_GLOBS = {
    b'cs_args',
    b'fPrintToConsole',
    b'fPrintToDebugLog',
    b'fReopenDebugLog',
    b'fReopenDebugLog',
    b'_Z7mapArgsB5cxx11',
    b'_ZZ11LogPrintStrRKNSt7__cxx1112basic_stringIcSt11char_traitsIcESaIcEEEE15fStartedNewLine',
    b'fDebug',
    b'_ZGVZ17LogAcceptCategoryPKcE11ptrCategory',
    b'_ZZ17LogAcceptCategoryPKcE11ptrCategory',
    b'_ZN16CBaseChainParams7REGTESTB5cxx11E',
    b'_ZN16CBaseChainParams7REGTESTB5cxx11E',
    b'_ZN16CBaseChainParams7REGTESTB5cxx11E',
    b'_ZN16CBaseChainParams7TESTNETB5cxx11E',
    b'_ZN16CBaseChainParams4MAINB5cxx11E',
    b'BITCOIN_CONF_FILENAME',
    b'translationInterface',
    b'_Z12CLIENT_BUILDB5cxx11',
    b'_Z13strSubVersionB5cxx11',
}

DEBUG_SEARCH = [
    b"strSubVersion",
]

def get_libs():
    for dirpath, dirnames, filenames in os.walk("src"):
        for filename in filenames:
            if filename.endswith(".o") and filename.startswith("lib"):
                yield os.path.join(dirpath, filename)

def get_syms(path):
    with subprocess.Popen(["objdump", "--syms", path], stdout=subprocess.PIPE) as proc:
        for l in proc.stdout:
            m = re.match(rb"^([0-9A-Za-z]+) (.......) ([^\t]+)\t([0-9A-Za-z]+) (.*)\n$", l)
            if m:
                yield m.groups()

def get_globs():
    globs = set()
    for path in get_libs():
        for value, flags, section, alignment, name in get_syms(path):
            if flags in (b'g     O', b'l     O'):
                if not section.startswith(b".rodata") and name not in IGNORE_GLOBS:
                    globs.add(name)
    return globs

def get_deps():
    deps = {} # section -> sections depending on it
    for path in get_libs():
        with subprocess.Popen(["objdump", "--reloc", path], stdout=subprocess.PIPE) as proc:
            section = None
            for l in proc.stdout:
                if l == b'\n':
                    continue
                m = re.match(rb'^RELOCATION RECORDS FOR \[([^\]]+)]:\n$', l)
                if m:
                    section = m.group(1)
                    continue
                if l == b'OFFSET           TYPE              VALUE \n':
                    continue
                m = re.match(rb'^([0-9a-z]+) ([^ ]+) +(.*?)([-+]0x[0-9a-z]+)?\n$', l)
                if m:
                    addr, type, dep_sym, offset = m.groups()
                    deps.setdefault(dep_sym, []).append(section)
                    continue
                m = re.match(rb'^(.*?)+: +file format (.*?)\n$', l)
                if m:
                    continue
                raise NotImplementedError
    return deps

def add_deps(dep_section, deps, output, root=None):
    if root is None:
        root = dep_section
    if any(search in dep_section for search in DEBUG_SEARCH):
        print("    {!r},".format(root), file=sys.stderr)
    if dep_section not in output:
        output.setdefault(dep_section, root)
        for section in deps.get(dep_section) or ():
            if section.startswith(b".text."):
                add_deps(section[6:], deps, output, root)

globs = get_globs()
deps = get_deps()


hide = {}

for glob in globs:
    add_deps(glob, deps, hide)


print("set -e")
print("set -x")

for path in get_libs():
    syms = set()
    for value, flags, section, alignment, name in get_syms(path):
        if name in hide:
            syms.add(name)
    if syms:
        print("test -f {}.0 || mv -v {} {}.0".format(path, path, path))
        print("objcopy {} {}.0 {}".format(" ".join("-L{}".format(sym.decode()) for sym in syms), path, path))

"""
git clean -dfx
./autogen.sh
ccache -C
./configure CXXFLAGS="-fdata-sections -ffunction-sections"
make -j12 -C src qt/bitcoin-qt 2>&1 | less
python3 ~/src/2017/hide-globals/hide-globals.py > /tmp/t
bash /tmp/t
find -name '*.o' | xargs rm -v

make -j12 -C src qt/bitcoin-qt > /tmp/e 2>&1
python ~/src/2017/hide-globals/replace-syms.py < /tmp/e
"""
