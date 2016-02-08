import json
import re
from collections import namedtuple
from lxml import etree
from lxml.cssselect import CSSSelector

PAY = "Pay"
DED = "Deduction"
TAX = "Tax"

def parse_mypay_html(filename):
    pay = etree.parse(filename, etree.HTMLParser())
    for check in CSSSelector('.payStatement')(pay):
        assert len(check) == 1
        tbody = check[0]
        assert tbody.tag == "tbody"

        assert len(tbody) == 9
        assert len(tbody[0]) == 5 # blank columns

        assert len(tbody[1]) == 1 # logo
        assert tbody[1][0].attrib["colspan"] == "5"
        assert tbody[1][0][1].attrib["id"] == "companyLogo"

        assert len(tbody[2]) == 2 # address, summary table
        assert len(tbody[2][1]) == 1
        assert tbody[2][1][0].tag == "table"
        assert len(tbody[2][1][0]) == 1
        inf = tbody[2][1][0][0]
        assert inf.tag == "tbody"
        assert len(inf) == 6
        assert inf[3][0][0].text == "Pay date"
        paydate = inf[3][1][0].text
        assert inf[4][0][0].text == "Document"
        docid = inf[4][1][0].text
        assert inf[5][0][0].text == "Net pay"
        netpay = inf[5][1][0].text

        assert len(tbody[3]) == 1
        assert tbody[3][0].attrib["colspan"] == "5"
        assert tbody[3][0][0][0].text == "Pay details"
        assert len(tbody[4]) == 5

        print(paydate, docid, netpay)

        assert len(tbody[5]) == 2
        assert tbody[5][0].attrib["colspan"] == "2"
        assert tbody[5][0].attrib["rowspan"] == "2"
        assert tbody[5][0][0][0].text == "Earnings"
        tab(tbody[5][0], docid, PAY)

        assert tbody[5][1].attrib["colspan"] == "3"
        assert tbody[5][1][0][0].text == "Deductions"
        tab(tbody[5][1], docid, DED)

        assert len(tbody[6]) == 1
        assert tbody[6][0].attrib["colspan"] == "3"
        assert tbody[6][0][0][0].text == "Taxes"
        tab(tbody[6][0], docid, TAX)

        assert len(tbody[8]) == 1
        assert tbody[8][0][0][0].text == "Pay summary"


def tab(el, docid, table_type):
    if table_type == PAY:
        if docid.startswith("RSU"):
            expected_cols = ['Pay type', 'Hours', 'Pay rate', 'Piece units', 'Piece Rate', 'current', 'YTD']
        else:
            expected_cols = ['Pay type', 'Hours', 'Pay rate', 'current', 'YTD']
    elif table_type == DED:
        expected_cols = ['Employee', 'Employer', 'Deduction', 'current', 'YTD', 'current', 'YTD']
    else:
        assert table_type == TAX
        expected_cols = ['Taxes', 'Based on', 'current', 'YTD']

    grids = CSSSelector("table.grid")(el)
    assert len(grids) == 1
    grid = grids[0]
    assert len(grid) == 2
    assert grid[0].tag == "thead"
    headcols = []
    for headrow in grid[0]:
        for headcol in headrow:
            if len(headcol) and headcol[0].tag != "img":
                headcols.append(headcol[0].text)
    assert expected_cols == headcols

    assert grid[1].tag == "tbody"
    for bodyrow in grid[1]:
        bodycols = []
        for colno, bodycol in enumerate(bodyrow):
            if colno == 0:
                bodycols.append(bodycol[0].attrib["data-title"])
            else:
                assert len(bodycol) == 0
                bodycols.append(bodycol.text)
        details = ""
        if table_type == PAY:
            if docid.startswith("RSU"):
                label, hours, rate, piece_units, piece_rate, current, ytd = bodycols
                assert piece_units == "0.000000"
                assert piece_rate == "$0.00"
            else:
                label, hours, rate, current, ytd = bodycols
            if hours != "0.0000" or rate != "$0.0000":
                details += " ({} hours, {}/hour)".format(hours, rate)
        elif table_type == DED:
            label, current, ytd, goog_current, goog_ytd, garbage = bodycols
            if goog_current != "$0.00":
                if label == "401K Pretax" or label == "Pretax 401 Flat" or label == "ER Benefit Cost":
                    goog_401k = goog_current
                else:
                   print("fuck", docid, label)
                   assert False
            assert garbage == "\xa0"
        else:
            assert table_type == TAX
            label, income, current, ytd, garbage = bodycols
            assert garbage == "\xa0"
        if current != "$0.00":
          print("  {}: {}{} -- {}".format(table_type, label, details, current))

def parse_chase_pdftext(json_filename):
    with open(json_filename) as fp:
        fragments = [TextFragment(*fragment) for fragment in json.load(fp)]
    stream = FragmentStream(fragments)
    stream.discard_until("Beginning Balance")
    opening_balance = next(stream).text
    stream.discard_until("Ending Balance")
    closing_balance = next(stream).text
    stream.discard_until("TRANSACTION DETAIL")
    assert next(stream).text == "Beginning Balance"
    assert next(stream).text == opening_balance
    next(stream)
    txns = []
    while True:
        if stream.fragment.pageno != stream.prev_fragment.pageno:
            print(stream.fragment)
            print(stream.prev_fragment)
            assert re.match(r"Page +\d+ +of +\d+", txns[-1].info[-1].strip()), txns[-1].info[-1]
            txns[-1].info.pop()
            stream.discard_until('(continued)')
            stream.discard_until('TRANSACTION DETAIL')
            next(stream)
            continue

        words = stream.readline()
        if not re.match(r"\d{2}/\d{2}", words[0]):
            txns[-1].info.append(" ".join(words))
            continue

        txn = Txn()
        txn.balance = words.pop()
        txn.amount = words.pop()
        if words[-1] == "-":
            words.pop()
            txn.debit = True
        else:
            txn.debit = False
        #words.append(repr(stream.fragment))
        txn.info = [" ".join(words)]
        txns.append(txn)

        if stream.fragment.text == "Ending Balance":
            break
    assert next(stream).text == closing_balance
    stream.discard_until(None)

    return txns, opening_balance, closing_balance, stream


TextFragment = namedtuple("TextFragment", "pageno y x ord text")

class Txn:
    pass

class FragmentStream:
    def __init__(self, fragments):
        self.iter = iter(fragments)
        self.discarded_text = ""
        self.fragment = None

    def __iter__(self):
        return self

    def __next__(self):
        self.prev_fragment = self.fragment
        self.fragment = None
        self.fragment = self.iter.__next__()
        assert self.fragment
        #print("GOT", self.fragment)
        return self.fragment

    def discard(self, fragment):
        if self.discarded_text:
            self.discarded_text += "\n" if self.on_newline() else " "
        self.discarded_text += fragment.text

    def discard_until(self, text):
        for fragment in self:
            if fragment.text == text:
                break
            self.discard(fragment)
        else:
            if text is not None:
                raise StopIteration

    def on_newline(self):
        return not self.prev_fragment or self.prev_fragment.y != self.fragment.y

    def readline(self):
        words = [self.fragment.text]
        for fragment in self:
            if self.on_newline():
                break
            words.append(fragment.text)
        return words
