#!/usr/bin/python
# coding=utf8

import sys

def indent(n):
  n = n.replace("basic_string<char, std::char_traits<char>, std::allocator<char> >", "string")
  n = n.replace("basic_string<char, char_traits<char>, allocator<char> >", "string")
  n = n.replace("std::__cxx11::basic_string<char>", "string")
  n = n.replace("std::__cxx11::basic_string<char, std::char_traits<char>, std::allocator<char> >", "string")

  #print "(" * 5, n, ")" * 5

  o = ''
  indent = 0
  newline = False
  counts = []
  column = 0
  for c in n:
    if c in ">)]":
      if not counts:
        return n
      o += "{}{} {} ".format(" " * max(1, 60 - column), "#" * len(counts), counts[-1])
      counts.pop()
      indent -= 2
      newline = True

    if newline:
      o += "\n"
      o += (indent * " ")
      column = indent

    if not (c == ' ' and newline):
      o += c
      column += 1

    newline = False

    if c in "<([":
      counts.append(0)
      indent += 2
      newline = True
    elif c == ",":
      o += "{}{} {} ".format(" " * max(1, 60 - column), "#" * len(counts), counts[-1] if counts else "BadCount")
      if counts:
        counts[-1] += 1
      newline = True
  return o

#sys.stdout.write("\n'".join(map(indent, sys.stdin.read().split("'"))))

import re
sys.stdout.write(re.sub("(‘)(.*?)(’)", lambda m: m.group(1) + indent(m.group(2)) + m.group(3), sys.stdin.read()))
