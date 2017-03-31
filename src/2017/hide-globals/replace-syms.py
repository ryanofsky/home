import os
import regex
import sys

sources = {} # filename -> Source

class Source:
    def __init__(self, path):
       self.path = path
       self.syms = set()

for dirpath, dirnames, filenames in os.walk("src/qt"):
    for filename in filenames:
        if filename.endswith(".cpp"):
            sources[filename] = Source(os.path.join(dirpath, filename))

for line in sys.stdin:
  m = regex.match("^([^:]+):.*? undefined reference to `(.*?)'$", line)
  if m:
      filename, sym = m.groups()
      if filename in sources:
          sources[filename].syms.add(sym)

for source in sources.values():
    with open(source.path) as fp:
        code = fp.read()

    for sym in source.syms:
        p = sym.find("(")
        if p < 0:
            pattern = r"\b(" + sym + r")\b"
            code = regex.sub(pattern, r"FIXME_IMPLEMENT_IPC_VALUE(\1)", code)
        else:
            fun = regex.search(r"([A-Za-z0-9_]+)(\[abi:cxx11])?\(", sym).group(1)
            print(source.path, fun)

            # http://stackoverflow.com/questions/5454322/python-how-to-match-nested-parentheses-with-regex/12280660#12280660
            paren_pattern = r"""
                (?<rec> #capturing group rec
                \( #open parenthesis
                (?: #non-capturing group
                [^()]++ #anyting but parenthesis one or more times without backtracking
                | #or
                (?&rec) #recursive substitute of group rec
                )*
                \) #close parenthesis
                )
            """

            pattern = r"""
                (([A-Za-z0-9_]+(::|\.|->))*\b{fun}\b{paren_pattern})
            """.format(fun=fun, paren_pattern=paren_pattern)

            code = regex.sub(pattern, r"FIXME_IMPLEMENT_IPC_VALUE(\1)", code, flags=regex.VERBOSE)

    with open(source.path, "w") as fp:
        fp.write(code)
