import os
import subprocess
import re
import sys

IGNORE_GLOBS = {
    b'BITCOIN_CONF_FILENAME',
    b'BITCOIN_PID_FILENAME',
    b'DEFAULT_WALLET_DAT',
    b'_Z12CLIENT_BUILDB5cxx11',
    b'_Z13CURRENCY_UNITB5cxx11',
    b'_Z13strSubVersionB5cxx11',
    b'_Z19DEFAULT_TOR_CONTROLB5cxx11',
    b'_Z7mapArgsB5cxx11',
    b'_ZGVZ17LogAcceptCategoryPKcE11ptrCategory',
    b'_ZN16CBaseChainParams4MAINB5cxx11E',
    b'_ZN16CBaseChainParams7REGTESTB5cxx11E',
    b'_ZN16CBaseChainParams7TESTNETB5cxx11E',
    b'_ZZ11LogPrintStrRKNSt7__cxx1112basic_stringIcSt11char_traitsIcESaIcEEEE15fStartedNewLine',
    b'_ZZ17LogAcceptCategoryPKcE11ptrCategory',
    b'cs_args',
    b'fDebug',
    b'fPrintToConsole',
    b'fPrintToDebugLog',
    b'fReopenDebugLog',
    b'translationInterface',
    b'_ZL14pCurrentParams',
    b'_ZGVZ10EvalScriptRSt6vectorIS_IhSaIhEESaIS1_EERK7CScriptjRK20BaseSignatureChecker10SigVersionP13ScriptError_tE6bnZero',
    b'_ZGVZ10EvalScriptRSt6vectorIS_IhSaIhEESaIS1_EERK7CScriptjRK20BaseSignatureChecker10SigVersionP13ScriptError_tE7vchTrue',
    b'_ZGVZ10EvalScriptRSt6vectorIS_IhSaIhEESaIS1_EERK7CScriptjRK20BaseSignatureChecker10SigVersionP13ScriptError_tE7vchZero',
    b'_ZGVZ12VerifyScriptRK7CScriptS1_PK14CScriptWitnessjRK20BaseSignatureCheckerP13ScriptError_tE12emptyWitness',
    b'_ZL9pszBase58',
    b'_ZZ10EvalScriptRSt6vectorIS_IhSaIhEESaIS1_EERK7CScriptjRK20BaseSignatureChecker10SigVersionP13ScriptError_tE6bnTrue',
    b'_ZZ10EvalScriptRSt6vectorIS_IhSaIhEESaIS1_EERK7CScriptjRK20BaseSignatureChecker10SigVersionP13ScriptError_tE7vchTrue',
    b'_ZZ10EvalScriptRSt6vectorIS_IhSaIhEESaIS1_EERK7CScriptjRK20BaseSignatureChecker10SigVersionP13ScriptError_tE8vchFalse',
    b'_ZZ6SolverRK7CScriptR10txnouttypeRSt6vectorIS4_IhSaIhEESaIS6_EEE10mTemplates',
    b'_ZZN17LockedPoolManager14CreateInstanceEvE8instance',
    b'_ZN17LockedPoolManager9_instanceE',
    b'_ZZN17LockedPoolManager14CreateInstanceEvE8instance',
    b'_ZGVZN17LockedPoolManager14CreateInstanceEvE8instance',
    b'_ZGVZ17DateTimeStrFormatPKclE7classic',
    b'_ZZ17DateTimeStrFormatB5cxx11PKclE7classic',
    b'_ZZ12EncodeBase64B5cxx11PKhmE7pbase64',
    b'_ZGVZ6SolverRK7CScriptR10txnouttypeRSt6vectorIS4_IhSaIhEESaIS6_EEE10mTemplates',
    b'_ZL12csPathCached',
    b'_ZL18pCurrentBaseParams',
    b'_ZL10pathCached',
b'_ZL21pathCachedNetSpecific',
    b'_ZZ12EncodeBase32B5cxx11PKhmE7pbase32',
    b'_ZL9nMockTime',
    b"_ZL13_mapMultiArgs",
    b'_ZL7fileout',
    b'_ZL13mutexDebugLog',
    b'_ZL18debugPrintInitFlag',
    b'_ZL18vMsgsBeforeOpenLog',
    b'_ZN10NetMsgType10CMPCTBLOCKE',
    b'_ZN10NetMsgType10FILTERLOADE',
    b'_ZN10NetMsgType10GETHEADERSE',
    b'_ZN10NetMsgType11FILTERCLEARE',
    b'_ZN10NetMsgType11GETBLOCKTXNE',
    b'_ZN10NetMsgType11MERKLEBLOCKE',
    b'_ZN10NetMsgType11SENDHEADERSE',
    b'_ZN10NetMsgType2TXE',
    b'_ZN10NetMsgType3INVE',
    b'_ZN10NetMsgType4ADDRE',
    b'_ZN10NetMsgType4PINGE',
    b'_ZN10NetMsgType4PONGE',
    b'_ZN10NetMsgType5BLOCKE',
    b'_ZN10NetMsgType6REJECTE',
    b'_ZN10NetMsgType6VERACKE',
    b'_ZN10NetMsgType7GETADDRE',
    b'_ZN10NetMsgType7GETDATAE',
    b'_ZN10NetMsgType7HEADERSE',
    b'_ZN10NetMsgType7MEMPOOLE',
    b'_ZN10NetMsgType7VERSIONE',
    b'_ZN10NetMsgType8BLOCKTXNE',
    b'_ZN10NetMsgType8NOTFOUNDE',
    b'_ZN10NetMsgType9FEEFILTERE',
    b'_ZN10NetMsgType9FILTERADDE',
    b'_ZN10NetMsgType9GETBLOCKSE',
    b'_ZN10NetMsgType9SENDCMPCTE',
    b'_ZL22secp256k1_context_sign',
    b'secp256k1_nonce_function_rfc6979',
    b'logCategories',
    b'NullUniValue',
    b'_ZN12_GLOBAL__N_124secp256k1_context_verifyE',
    b'_ZZ10EvalScriptRSt6vectorIS_IhSaIhEESaIS1_EERK7CScriptjRK20BaseSignatureChecker10SigVersionP13ScriptError_tE5bnOne',
    b'_ZZ12VerifyScriptRK7CScriptS1_PK14CScriptWitnessjRK20BaseSignatureCheckerP13ScriptError_tE12emptyWitness',
    b'_ZGVZ10EvalScriptRSt6vectorIS_IhSaIhEESaIS1_EERK7CScriptjRK20BaseSignatureChecker10SigVersionP13ScriptError_tE5bnOne',
    b'_ZZ10EvalScriptRSt6vectorIS_IhSaIhEESaIS1_EERK7CScriptjRK20BaseSignatureChecker10SigVersionP13ScriptError_tE6bnZero',
    b'_ZGVZ10EvalScriptRSt6vectorIS_IhSaIhEESaIS1_EERK7CScriptjRK20BaseSignatureChecker10SigVersionP13ScriptError_tE8vchFalse',
}

DEBUG_SEARCH = [
    b"DateTimeStrFormat",
    b"EncodeBase64",
    b"ExtractDestination",
    b"GetDataDir",
    b"GetNodeStats",
    b"LogAcceptCategory",
    b"LogPrintStr",
    b"PrintExceptionContinue",
    b"ReadConfigFile",
    b"ToString",
    b"ToStringIP",
    b"Z6Paramsv",
    b"SignCompact",
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
                    globs.add(section)
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
        root = dep_section,
    if any(search in section for search in DEBUG_SEARCH for section in root):
        print("    {!r},".format(root), file=sys.stderr)
    if dep_section not in output:
        output.setdefault(dep_section, root)
        for section in deps.get(dep_section) or ():
            if section.startswith(b".text."):
                add_deps(section[6:], deps, output, root + (section,))

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
make -j12 -C src qt/bitcoin-qt
python3 ~/src/2017/hide-globals/hide-globals.py > /tmp/t
bash /tmp/t
find -name '*.o' | xargs rm -v

make -j12 -C src qt/bitcoin-qt > /tmp/e 2>&1
python ~/src/2017/hide-globals/replace-syms.py < /tmp/e

# wallet replace
patch -p1 <<<EOS
--- a/src/Makefile.am
+++ b/src/Makefile.am
@@ -358,7 +358,7 @@ nodist_libbitcoin_util_a_SOURCES = $(srcdir)/obj/build.h
 #
 
 # bitcoind binary #
-bitcoind_SOURCES = bitcoind.cpp
+bitcoind_SOURCES = bitcoind.cpp $(libbitcoin_wallet_a_SOURCES)
 bitcoind_CPPFLAGS = $(AM_CPPFLAGS) $(BITCOIN_INCLUDES)
 bitcoind_CXXFLAGS = $(AM_CXXFLAGS) $(PIE_FLAGS)
 bitcoind_LDFLAGS = $(RELDFLAGS) $(AM_LDFLAGS) $(LIBTOOL_APP_LDFLAGS)
EOS
find -name '*.o' | xargs rm -v
make -j12 -C src bitcoind
python3 ~/src/2017/hide-globals/hide-globals.py > /tmp/t
grep -v src/wallet < /tmp/t > /tmp/u
bash /tmp/u
make -j12 -k -C src bitcoind > /tmp/e 2>&1
python ~/src/2017/hide-globals/replace-syms.py < /tmp/e
"""
