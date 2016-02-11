#!/usr/bin/python3

import os
import sys
import re

# s/INSERT INTO "commodities" VALUES('\([^']+\)',\([^)]+\));/src["\2"] = "\1"

src_dict = {}
src_dict["'CURRENCY','USD','US Dollar','840',100,1,'currency',''"] = "6cf5263a5f41bacf7061340103f41841"
src_dict["'CURRENCY','XXX','No currency','999',1000000,1,'currency',''"] = "effe9fd122e5b8050a6163617b2d8e59"
src_dict["'CURRENCY','XTS','Code for testing purposes','963',1000000,1,'currency',''"] = "f5a039b148e612c502b2516b7c7ca42d"
src_dict["'NASDAQ','SHFVX','LMP Fundamental VI A',NULL,1000,1,'usa',''"] = "bb6d21158a7613f9a9a807a28f019a09"
src_dict["'NASDAQ','SHAPX','LMP Appreciation A',NULL,1000,1,'usa',''"] = "5d9ffe1e83b7fdfca007776f50d937ae"
src_dict["'NASDAQ','SHRAX','LMP Aggr Growth A',NULL,1000,1,'usa',''"] = "6c6425aa121ce50c0cfc99a65dc4faef"
src_dict["'template','template','template','template',1,0,NULL,''"] = "0b9a1bfa5632b66694009982fe2bf867"

dst_dict = {}
dst_dict["'CURRENCY','USD','US Dollar','840',100,1,'currency',''"] = "bb06bfe4b2a2743ba8ec2304c6e6ded2"
dst_dict["'CURRENCY','XXX','No currency','999',1000000,1,'currency',''"] = "e89aa09b9a771b42e8ca67dda566ff0f"
dst_dict["'CURRENCY','XTS','Code for testing purposes','963',1000000,1,'currency',''"] = "646fa2aa520b205594d1f4cb476d2ca6"
dst_dict["'NASDAQ','SHFVX','LMP Fundamental VI A',NULL,1000,1,'usa',''"] = "424a64b1d3b647fd3da62fdf018c9813"
dst_dict["'NASDAQ','SHAPX','LMP Appreciation A',NULL,1000,1,'usa',''"] = "d1e9d5ac7c536b4345f100f18ee14998"
dst_dict["'NASDAQ','SHRAX','LMP Aggr Growth A',NULL,1000,1,'usa',''"] = "4cd723a24a944d94712021aa3f978a48"
dst_dict["'template','template','template','template',1,0,NULL,''"] = "f96655e2216ffc3d2e09011984b4aeb2"

replace = []
for src_key, src_val in src_dict.items():
    dst_val = dst_dict[src_key]
    replace.append((src_val, dst_val))

slot_dict = {}

def update_line(line):
    for src, dst in replace:
        assert dst not in line
        line = line.replace(src, dst)
    return line

slot_current = None
slot_placeholder = "__slot_placeholder__"

def remove_slot(line, input_file):
    global slot_current, slot_dict
    assert slot_placeholder not in line
    def callback(m):
        global slot_current
        slot_current += 1
        if m.group(2) != str(slot_current):
            print("Expected slot {} not {}".format(slot_current, m.group(2)), file=sys.stderr)
            slot_current = int(m.group(2))
        return m.group(1) + slot_placeholder
    line = re.sub(r'^(INSERT INTO "slots" VALUES\()(\d+)', callback, line)

    m = re.match(r"^(INSERT INTO \"slots\" VALUES\(.*?',9,0,NULL,0.0,NULL,')([0-9a-f]{32})(',0,1,NULL\);)$", line)
    if m:
        #print("!!!m=", m.groups())
        if not input_file:
            assert m.group(1) not in slot_dict
            slot_dict[m.group(1)] = m.group(2)
        else:
            replace.append((m.group(2), slot_dict[m.group(1)]))
            line = line.replace(*replace[-1])
            print("!!!", replace[-1])
    return line

def add_slot(line):
    global slot_current
    if slot_placeholder in line:
        slot_current += 1
        line = line.replace(slot_placeholder, str(slot_current))
    return line

def main():
    global slot_current
    input_filename, output_filename, orderby_filename = sys.argv[1:]

    lineorder = {}
    slot_final = 0
    with open(orderby_filename) as orderby_fp:
        lineno = 1
        slot_current = 0
        for line_text in orderby_fp:
            line_text = remove_slot(line_text, False)
            if slot_placeholder in line_text:
                slot_final = lineno
            if line_text in lineorder:
                lineorder[line_text] = 0
            else:
                lineorder[line_text] = lineno
            lineno += 1

    lines = []
    max_order = 0
    with open(input_filename) as input_fp:
        lineno = 1
        slot_current = 0
        for line_text in input_fp:
            line_text = update_line(line_text)
            line_text = remove_slot(line_text, True)
            order = lineorder.get(line_text, 0)
            if order > 0:
                lines.append((order, 0, lineno, line_text))
            elif slot_placeholder in line_text:
                lines.append((slot_final, 2, lineno, line_text))
            else:
                lines.append((max_order, 1, lineno, line_text))
            max_order = max(order, max_order)
            lineno += 1
            #print(lines[-1])

    lines.sort()
    assert not os.path.exists(output_filename)
    with open(output_filename, "w") as output_fp:
        slot_current = 0
        for line in lines:
            line_text = line[-1]
            line_text = add_slot(line_text)
            output_fp.write(line_text)

if __name__ == "__main__":
    main()
