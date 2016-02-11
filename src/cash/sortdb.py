#!/usr/bin/python3

import os
import sys
import re

def main():
    input_filename, output_filename, orderby_filename = sys.argv[1:]

    lineorder = {}
    with open(orderby_filename) as orderby_fp:
        lineno = 1
        for line_text in orderby_fp:
            if line_text in lineorder:
                lineorder[line_text] = 0
            else:
                lineorder[line_text] = lineno
            lineno += 1

    lines = []
    max_order = 0
    with open(input_filename) as input_fp:
        lineno = 1
        for line_text in input_fp:
            order = lineorder.get(line_text, 0)
            if order > 0:
                lines.append((order, 0, lineno, line_text))
            else:
                lines.append((max_order, 1, lineno, line_text))
            max_order = max(order, max_order)
            lineno += 1

    lines.sort()
    assert not os.path.exists(output_filename)
    with open(output_filename, "w") as output_fp:
        for line in lines:
            line_text = line[-1]
            output_fp.write(line_text)

if __name__ == "__main__":
    main()
