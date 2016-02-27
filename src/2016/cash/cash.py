import bisect
import datetime
import io
import json
import re
import sys
from collections import namedtuple, deque
from enum import IntEnum
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

        netpay = parse_price(netpay)
        print(paydate, docid, netpay)

        assert len(tbody[5]) == 2
        assert tbody[5][0].attrib["colspan"] == "2"
        assert tbody[5][0].attrib["rowspan"] == "2"
        assert tbody[5][0][0][0].text == "Earnings"
        total = 0
        for label, details, current in tab(tbody[5][0], docid, PAY):
            current = parse_price(current, True)
            total += current
            print("  {}: {}{} -- {}".format(PAY, label, details, current))

        assert tbody[5][1].attrib["colspan"] == "3"
        assert tbody[5][1][0][0].text == "Deductions"
        for label, details, current in tab(tbody[5][1], docid, DED):
            current = parse_price(current, True)
            total -= current
            print("  {}: {}{} -- {}".format(DED, label, details, current))

        assert len(tbody[6]) == 1
        assert tbody[6][0].attrib["colspan"] == "3"
        assert tbody[6][0][0][0].text == "Taxes"
        for label, details, current in tab(tbody[6][0], docid, TAX):
            current = parse_price(current, True)
            total -= current
            print("  {}: {}{} -- {}".format(TAX, label, details, current))

        assert total == netpay
        assert len(tbody[8]) == 1
        assert tbody[8][0][0][0].text == "Pay summary"

def tab(el, docid, table_type):
    if table_type == PAY:
        if docid.startswith("RSU"):
            expected_cols = ['Pay type', 'Hours', 'Pay rate', 'Piece units',
                             'Piece Rate', 'current', 'YTD']
        else:
            expected_cols = ['Pay type', 'Hours', 'Pay rate', 'current', 'YTD']
    elif table_type == DED:
        expected_cols = ['Employee', 'Employer', 'Deduction', 'current', 'YTD',
                         'current', 'YTD']
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
                label, hours, rate, piece_units, piece_rate, current, ytd = \
                    bodycols
                assert piece_units == "0.000000"
                assert piece_rate == "$0.00"
            else:
                label, hours, rate, current, ytd = bodycols
            if hours != "0.0000" or rate != "$0.0000":
                details += " ({} hours, {}/hour)".format(hours, rate)
        elif table_type == DED:
            label, current, ytd, goog_current, goog_ytd, garbage = bodycols
            if goog_current != "$0.00":
                if label in ("401K Pretax", "Pretax 401 Flat",
                             "ER Benefit Cost"):
                    goog_401k = goog_current
                else:
                   assert False
            assert garbage == "\xa0"
        else:
            assert table_type == TAX
            label, income, current, ytd, garbage = bodycols
            assert garbage == "\xa0"
        if current != "$0.00":
          yield label, details, current

def parse_price(price_str, allow_negative=False):
    price = 1
    if allow_negative and price_str[0] == "(" and price_str[-1] == ")":
        price *= -1
        price_str = price_str[1:-1]
    if price_str[0] == "$":
        price_str = price_str[1:]
    dollars, cents = re.match(r"^([0-9,]+)\.([0-9]{2})$", price_str).groups()
    price *= int(cents) + 100 * int(dollars.replace(",", ""))
    return price

def dump_chase_txns(pdftext_input_json_filename, txns_output_json_filename,
                    discarded_text_output_filename):
    txns, discarded_text = parse_chase_pdftext(pdftext_input_json_filename)
    with open(txns_output_json_filename, "w") as fp:
        json.dump(txns, fp, sort_keys=True, indent=4)
    with open(discarded_text_output_filename, "w") as fp:
        fp.write(discarded_text)

def parse_chase_pdftext(json_filename):
    statement_date = datetime.date(*[int(g) for g in re.match(
        r"^.*?/([0-9]{4})-([0-9]{2})-([0-9]{2}).json$",
        json_filename).groups()])
    version = pdf_version(statement_date)
    newstyle = version >= Pdf.V2006_09

    # (date, description, additions, deductions, balance)
    if newstyle:
        columns = (700, 3500, None, 4500, 6000)
    else:
        columns = (700, 4100, 4800, 5400, 6000)

    with open(json_filename) as fp:
        fragments = [TextFragment(*fragment) for fragment in json.load(fp)]
    it = PeekIterator(fragments, lookahead=1, lookbehind=2)
    discarded_text = io.StringIO()
    # 2005-10-20 thru 2006-08-17
    #   - parses successfully
    # 2006-09-21
    #   - can't parse because transactions grouped by date
    #   - Switch to signed "AMOUNT" column instead of positive "Additions" and "Deductions" columns
    #   - Switch to "Beginning Balance" instead of "Opening Balance"
    #   - Fragments are now groups of words with spaces, instead of individual words
    #   - Transactions grouped by dates and only include daily balances, only way to distinguish them is by slightly larger vertical spacing
    #   - Dates no longer included on beginning/ending balance transaction lines
    #   - Has junk vertical barcode on side of statement that interferes with parsing
    #   - ALL CAPS transations with lots of extra wrapping, and multilevel indent
    # 2006-10-19 thru 2007-01-19
    #   - can't parse because transactions grouped by date
    #   - No more ALL CAPS transactions, no more multilevel indent
    # 2007-02-20 thru 2007-06-19
    #   - can't parse because deposit amounts are bolded, screw up read_line
    #   - Transactions no longer grouped by date
    # 2007-07-19
    #   - parses successfully
    #   - deposit bolding no longer moves stuff to new line and breaks parsing
    # 2007-08-17
    #   - can't parse because overdraft & negative balance
    # 2007-09-20 thru 2008-03-19
    #   - parses successfully
    # 2008-04-17 thru 2011-08-17
    #   - parses successfully
    #   - lines between transactions
    #   - slightly wider column
    # 2011-09-20 thru 2015-11-19
    #   - parses successfully
    #   - [" DATE", "DESCRIPTION", "AMOUNT", "BALANCE"] header is now image instead of text
    #   - Begin and ending header dates are no longer available
    found_begin, found_open = fragments_discard_until(
        it, discarded_text,
        re.compile(r"(^Beginning Balance$)|(^Opening$)")).groups()
    if newstyle:
        assert found_begin
        assert not found_open
        line = fragments_read_line(it)
        assert line[:-1] == ["Beginning Balance"], line
        opening_balance_str = line[-1]

        fragments_discard_until(it, discarded_text, "Ending Balance")
        line = fragments_read_line(it)
        assert line[:-1] == ["Ending Balance"], line
        closing_balance_str = line[-1]

        def discard_header(it):
            fragments_discard_until(it, discarded_text, "TRANSACTION DETAIL")
            it.__next__()
            if it.peek(1).text == " DATE":
                line = fragments_read_line(it)
                assert line == [" DATE", "DESCRIPTION", "AMOUNT", "BALANCE"]

        discard_header(it)

        line = fragments_read_line(it)
        assert line == ["Beginning Balance", opening_balance_str], line
    else:
        assert found_open
        assert not found_begin
        line = fragments_read_line(it)
        assert line[:3] == ["Opening", "Balance", "$"], line
        opening_balance_str = line[3]

        line = fragments_read_line(it)
        assert line[:-1] == ["Additions", "$"]
        parse_price(line[-1])

        line = fragments_read_line(it)
        assert line[:-1] == ["Deductions", "$"]
        parse_price(line[-1])

        line = fragments_read_line(it)
        assert line[:-1] == ["Ending", "Balance", "$"], line
        closing_balance_str = line[-1]

        def discard_header(it):
            line = fragments_read_line(it)
            assert line == ["Activity"], line

            line = fragments_read_line(it)
            assert line == ["Date", "Description", "Additions",
                            "Deductions", "Balance"], line

        discard_header(it)
        line = fragments_read_line(it)
        assert len(line) == 5 and line[1:4] == ["Opening", "Balance", "$"]
        assert opening_balance_str == line[4]
        opening_date = line[0] # unused for now

    txns = []
    while True:
        if it.peek(1).pageno != it.peek(0).pageno:
            # drop garbage from end of previous transaction
            fragments_discard_until(it, discarded_text, '(continued)')
            line = fragments_read_line(it)
            assert line == ["(continued)"], line
            discard_header(it)
            continue

        line_fragments = fragments_read_line_fragments(it)
        date, desc, add, ded, balance, junk = \
            fragments_split_columns(line_fragments, *columns)

        if 0:
            print("  -- line --")
            if date: print("     date {}".format(date))
            if desc: print("     desc {}".format(desc))
            if add: print("     add {}".format(add))
            if ded: print("     ded {}".format(ded))
            if balance: print("     balance {}".format(balance))
            if junk: print("     junk {}".format(junk))

        txn_date = None
        if date:
            assert len(date) == 1
            month, day = map(int, re.match(r"^(\d{2})/(\d{2})$",
                                           date[0].text).groups())
            txn_date = datetime.date(statement_date.year, month, day)

        # Detect non-transaction text
        # - Junk barcodes
        # - Page # of # footers
        # - Ending balance lines

        if junk:
            assert len(junk) == 1
            assert re.match("^[0-9]{20}$", junk[0].text)
            assert not date
            assert not desc
            assert not add
            assert not ded
            assert not balance
            continue

        if newstyle:
            if balance and balance[0].text == "Page":
                assert len(balance) == 4
                assert re.match(r" *\d+ *", balance[1].text)
                assert balance[2].text == "of"
                assert re.match(r" *\d+ *", balance[3].text)
                assert not date
                assert not desc
                assert not add
                assert not ded
                assert not junk
                continue

            assert len(desc) == 1
            if desc[0].text == "Ending Balance":
                assert not date
                assert not add
                assert not ded
                assert not junk
                assert len(balance) == 1
                assert balance[0].text == closing_balance_str
                break
        else:
            if (len(desc) > 1 and desc[0].text == 'Ending'
                and desc[1].text == 'Balance'):
                assert len(desc) == 2
                assert date # FIXME: could match
                closing_date = month, day # unused for now
                assert not add
                assert not ded
                assert not junk
                assert len(balance) == 2
                assert balance[0].text == "$"
                assert balance[1].text == closing_balance_str
                break

        # Parse transaction amount and balance

        txn_amount = None
        if add:
            assert not newstyle
            txn_amount = parse_price(add[-1].text)
            assert len(add) == 2
            assert add[0].text == "$"
        if ded:
            assert txn_amount is None
            txn_amount = parse_price(ded[-1].text)
            if newstyle:
                if len(ded) != 1:
                    assert len(ded) == 2
                    assert ded[0].text == "-"
                    txn_amount *= -1
            else:
                assert len(ded) == 2
                assert ded[0].text == "$"
                txn_amount *= -1

        txn_balance = None
        if balance:
            txn_balance = parse_price(balance[-1].text)
            if newstyle:
                assert len(balance) == 1
            else:
                assert len(balance) == 2
                assert balance[0].text == "$"

        if txn_date is not None or (newstyle and txn_amount is not None):
            txn = Txn()
            txn.date = txn_date
            txn.amount = txn_amount
            txn.balance = txn_balance
            txn.descs = [desc]
            txns.append(txn)
        else:
            assert txn_date is None
            if newstyle:
                assert txn_amount is None
                assert txn_balance is None
            else:
                if txn_amount is not None and txn.amount is None:
                    txn.amount = txn_amount
                if txn_balance is not None and txn.balance is None:
                    txn.balance = txn_balance
            txns[-1].descs.append(desc)

    fragments_discard_until(it, discarded_text, None)

    opening_balance = parse_price(opening_balance_str)
    closing_balance = parse_price(closing_balance_str)
    cur_balance = opening_balance
    txnit = PeekIterator(txns, lookahead=1, lookbehind=2)
    for txn in txnit:
        assert txn.descs[0] # true when amount precedes date, wrong date
        assert txn.amount is not None
        if txn.date is None:
            txn.date = txnit.peek(-1).date
        if txnit.prev_elems > 2:
            assert txn.peek(-1).date <= txn.date
        if txn.balance is None:
            txn.balance = cur_balance + txn.amount
        else:
            assert txn.balance == cur_balance + txn.amount
        txn.prev_balance = cur_balance
        cur_balance = txn.balance
        if 0: print("txn {} {} {}\n    {}".format(
                txn.date, txn.amount, txn.balance, "\n    ".join(
                    "||".join(frag.text for frag in desc)
                    for desc in txn.descs)))
        continue

    assert cur_balance == closing_balance

    return [(txn.date.isoformat(), txn.prev_balance, txn.balance, txn.amount,
             [" ".join(frag.text for frag in desc)
              for desc in txn.descs])
            for txn in txns], discarded_text.getvalue()


def fragments_discard_until(it, discarded_text, pattern):
    pattern_is_str = isinstance(pattern, str)
    while not it.at_end():
        fragment = it.peek(1)

        if pattern_is_str:
            if fragment.text == pattern: return
        elif pattern is not None:
            m = pattern.match(fragment.text)
            if m: return m

        if not it.at_start():
            prev_fragment = it.peek(0)
            discarded_text.write("\n" if prev_fragment.y != fragment.y else " ")
        discarded_text.write(fragment.text)
        it.__next__()

    if pattern is not None:
        raise Exception("unexpected end of file")

def fragments_read_line_fragments(it):
    words = []
    for fragment in it:
        words.append(fragment)
        if it.at_end() or it.peek(1).y != fragment.y:
            break
    return words

def fragments_read_line(it):
    return [fragment.text for fragment in fragments_read_line_fragments(it)]

def fragments_split_columns(fragments, *columns):
    ret = [[] for _ in range(len(columns)+1)]
    col_idx = 0
    for f in fragments:
        while (col_idx < len(columns)
               and (columns[col_idx] is None
                    or f.x > columns[col_idx])):
            col_idx += 1
        ret[col_idx].append(f)
    return ret

TextFragment = namedtuple("TextFragment", "pageno y x ord text")


Pdf = IntEnum("Pdf", "V2005_10 V2006_09 V2006_10 V2007_02 V2007_07 V2007_08 "
              "V2007_09 V2008_04 V2011_09")


def pdf_version(statement_date):
    vstr = "V{:%Y_%m}".format(statement_date)
    return Pdf(bisect.bisect(list(Pdf.__members__.keys()), vstr))


class Txn:
    pass


class PeekIterator:
    """Iterator wrapper allowing peek at next and previous elements in sequence.

    Wrapper does not change underlying sequence at all, so for example:

        it = PeekIterator([2, 4, 6, 8, 10], lookahead=1, lookbehind=2):
        for x in it:
            print(x)

    will simply print the sequence 2, 4, 6, 8, 10.

    The main feature the iterator provides is a peek() method allowing
    access to preceding and following elements. So for example, when x
    is 6 it.peek(1) will return 8, it.peek(-1) will return(4), and
    it.peek(0) will return 6.
    """
    def __init__(self, it, lookahead=0, lookbehind=0):
        self.it = iter(it)
        self.lookahead = lookahead
        self.lookbehind = lookbehind
        self.cache = deque()
        self.prev_elems = 0  # cached elements previously returned by __next__.

        # Add next values from underlying iterator to lookahead cache.
        for _ in range(lookahead):
            try:
                self.cache.append(self.it.__next__())
            except StopIteration:
                break

    def __iter__(self):
        return self

    def __next__(self):
        # Add next value from underlying iterator to lookahead
        # cache. The if condition avoids a redundant call to
        # it.__next__() if a previous call raised StopIteration (in
        # which the lookahead section of the cache will have unused
        # capacity).
        if len(self.cache) >= self.lookahead + self.prev_elems:
            try:
                self.cache.append(self.it.__next__())
            except StopIteration:
                pass

        try:
            # If next sequence element is present in the cache, return
            # it and increment prev_elems. Otherwise the sequence is
            # over, so raise StopIteration.
            if self.prev_elems < len(self.cache):
                self.prev_elems += 1
                return self.cache[self.prev_elems - 1]
            else:
                assert self.prev_elems == len(self.cache)
                raise StopIteration

        finally:
            # Pop a value from the lookbehind cache if it is over
            # capacity from the append above.
            if self.prev_elems > self.lookbehind:
                self.cache.popleft()
                self.prev_elems -= 1
                assert self.prev_elems == self.lookbehind

    def peek(self, offset):
        """Return element of sequence relative to current iterator position.

        Value of "offset" argument controls which sequence element the
        peek call returns, according to chart below:

         Offset   Return value
          -2      ...
          -1      element that was returned by last last __next__() call
           0      element that was returned by last __next__() call
           1      element that will be returned by next __next__() call
           2      element that will be returned by next next __next__() call
           3      ...

        Call will fail if offset is not in range (-lookbind_size,
        lookahead_size] or if there is attempt to read values from
        after the end, or before the beginning of the sequence.
        """
        assert offset <= self.lookahead, \
            "PeekIterator lookahead value {} is too low to support peeks at " \
            "offset {}. Must increase lookahead to at least {}.".format(
                self.lookahead, self.offset, self.offset)
        assert offset > -self.lookbehind, \
            "PeekIterator lookbehind value {} is too low to support peeks at " \
            " offset {}. Must increase lookbehind to at least {}.".format(
                self.lookbehind, self.offset, 1 - self.offset)
        pos = self.prev_elems - 1 + offset
        assert pos >= 0, "Can't peek before first element in sequence."
        assert pos < len(self.cache), "Can't peek beyond last element in sequence."
        return self.cache[pos]

    def at_end(self):
        assert self.lookahead > 0, \
            "at_end method only available with lookahead > 0"
        return self.prev_elems >= len(self.cache)

    def at_start(self):
        assert self.lookbehind > 0, \
            "at_start method only available with lookbehind > 0"
        return self.prev_elems == 0
