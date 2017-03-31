import os
import regex
import sys

for source in sys.argv[1:]:
    print(source)
    with open(source) as fp:
        code = fp.read()

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

        pattern = r"""FIXME_IMPLEMENT_IPC_VALUE\(FIXME_IMPLEMENT_IPC_VALUE\(([^()]*{})\)\)""".format(paren_pattern)
        code = regex.sub(pattern, r"FIXME_IMPLEMENT_IPC_VALUE(\1)", code, flags=regex.VERBOSE)

    with open(source, "w") as fp:
        fp.write(code)
