import weakref
import random
import bisect
import datetime
import io
import json
import os
import re
import sys
import time
import sqlite3
from itertools import groupby
from collections import namedtuple, deque, OrderedDict
from enum import IntEnum
from lxml import etree
from lxml.cssselect import CSSSelector
import csv


#
# Top-level functions called from shell.
#

def import_chase_txns(chase_dir, cash_db):
    with sqlite3.connect(cash_db) as conn:
        gnu = GnuCash(conn, "2016-02-27-pdfs")
        acct_balance = None
        for filename in sorted(os.listdir(chase_dir)):
            if not filename.endswith(".json"):
                continue
            _, _, _, acct_balance = merge_txns(
                gnu, read_pdf_txns(os.path.join(chase_dir, filename)),
                acct=gnu.checking_acct,
                acct_balance=acct_balance,
                reconcile_date=parse_statement_date(filename),
                compat=True)

        gnu.print_txns("== Unreconciled transactions ==",
                       lambda account, action, reconcile_state, **_:
                       account == gnu.checking_acct
                       and not action
                       and reconcile_state == 'y')
        gnu.commit()


def update_chase_memos(cash_db):
    with sqlite3.connect(cash_db) as conn:
        gnu = GnuCash(conn, "update_chase_memos")
        c = conn.cursor()
        c.execute("SELECT guid, memo FROM splits "
                  "WHERE account_guid = ? AND memo <> ''",
                  (gnu.checking_acct,))
        for guid, memo in c.fetchall():
            tstr = ChaseStr.parse_pdf_string(memo.split(" || "))
            assert tstr
            gnu.update_split(guid, memo_tstr=tstr, remove_txn_suffix=memo)
        gnu.commit()


def import_chase_update(filename, cash_db, **kwargs):
    rand_seed = os.path.basename(filename)
    with sqlite3.connect(cash_db) as conn:
        gnu = GnuCash(conn, rand_seed)
        if filename.endswith(".csv"):
            txns = read_csv_txns(filename)
        else:
            assert filename.endswith(".json")
            txns = read_pdf_txns(filename)

        first_date, last_date, split_guids, _ = merge_txns(
            gnu, txns, gnu.checking_acct, **kwargs)

        gnu.print_txns(
            "== Unreconciled transactions between {} and {} ==".format(
                first_date, last_date),
            lambda split_guid, account, action_date, post_date, **_:
                        account == gnu.checking_acct
                        and split_guid not in split_guids
                        and ((action_date
                              and action_date >= first_date
                              and action_date <= last_date)
                             or (not action_date
                                 and post_date >= first_date
                                 and post_date <= last_date)))

        gnu.commit()


def dump_chase_txns(pdftext_input_json_filename, txns_output_json_filename,
                    discarded_text_output_filename):
    txns, discarded_text = parse_chase_pdftext(pdftext_input_json_filename)
    with open(txns_output_json_filename, "w") as fp:
        json.dump(txns, fp, sort_keys=True, indent=4)
    with open(discarded_text_output_filename, "w") as fp:
        fp.write(discarded_text)


def import_paypal_csv(csv_dir, cash_db):
    csv_files = [filename for filename in sorted(os.listdir(csv_dir))
        if filename.endswith(".csv")]

    txns = read_paypal_txns(os.path.join(csv_dir, csv_file)
                            for csv_file in csv_files)

    for txn in txns:
        t = txn.memo
        s = t.as_string()
        p = TaggedStr.parse(s, False)
        check(s == p.as_string())
        check(p.lines == t.lines)
        check(p.tags == t.tags)
        print(t.as_string(), "\n")

    with sqlite3.connect(cash_db) as conn:
        gnu = GnuCash(conn, csv_files[-1])
        merge_paypal_txns(gnu, txns)
        gnu.commit()


def import_citi_tsv(tsv_filename, cash_db):
    rand_seed = os.path.basename(tsv_filename)
    with sqlite3.connect(cash_db) as conn:
        gnu = GnuCash(conn, rand_seed)
        txns = read_citi_tsv(tsv_filename)

        first_date, last_date, split_guids, _ = merge_txns(
            gnu, txns, gnu.citi_acct, debit_label="Debit",
            credit_label="Credit")

        gnu.commit()


def import_pay_txns(html_filename, cash_db):
    stubs = parse_mypay_html(html_filename)
    with sqlite3.connect(cash_db) as conn:
        gnu = GnuCash(conn, "2016-02-28-mypay")
        accts = create_mypay_accts(gnu)
        import_mypay_stubs(gnu, accts, stubs)
        gnu.commit()


def dump(cash_db):
    with sqlite3.connect(cash_db) as conn:
        gnu = GnuCash(conn, "")
        gnu.print_txns("== All transactions ==",  lambda **_: True)


def cleanup(cash_db):
    with sqlite3.connect(cash_db) as conn:
        gnu = GnuCash(conn, "cleanup")
        txns = set()

        # Manually delete old cash imbalance txn.
        txn = find_txn(gnu, 2020, 1, 1, "Cash")
        delete_split(gnu, txn, gnu.expense_acct, "", "", 400000)
        delete_split(gnu, txn, gnu.cash_acct, "", "", -400000)
        delete_txn(gnu, txn)

        # Manually fix mixed up mandel/gapps transactions.
        gapps_split, gapps_memo, mandel_txn = find_split(
            gnu, datetime.date(2015, 2, 11), "%Apps_Yanof%", -1000)
        mandel_split, mandel_memo, gapps_txn = find_split(
            gnu, datetime.date(2015, 2, 13), "%Mandel Vision%", -1000)
        gapps_memo = TaggedStr.parse(gapps_memo, check_tags=False)
        mandel_memo = TaggedStr.parse(mandel_memo, check_tags=False)
        gnu.update_split(mandel_split, txn=mandel_txn)
        gnu.update_split(gapps_split, txn=gapps_txn)
        gnu.update_split(gapps_split, memo_tstr=gapps_memo,
                         remove_txn_suffix=mandel_memo.as_string(tags=False))

        # Manually fix mixed up nirvanna/atm transactions
        hat_split, hat_memo, atm_txn = find_split(
            gnu, datetime.date(2010, 12, 10), "%12/11 Nirvanna Designs%", -6000)
        atm_split, atm_memo, hat_txn = find_split(
            gnu, datetime.date(2010, 12, 11), "%12/10 46 3Rd Ave%", -6000)
        gnu.update_split(hat_split, txn=hat_txn)
        gnu.update_split(atm_split, txn=atm_txn)

        # Manually merge unreconciled citi txn
        txn1 = find_txn(gnu, 2016, 2, 17, "Miami Airport: Snickers, Water")
        txn2 = find_txn(gnu, 2016, 2, 17, "Debit: NEWSLINK 31 MAIR       MIAMI         FL")
        txns.add(txn1)
        delete_split(gnu, txn1, gnu.citi_acct, "", "Payment", -618)
        delete_split(gnu, txn2, gnu.expense_acct, "", "", 618)
        gnu.update_split(select_split(gnu, txn2, gnu.citi_acct), txn=txn1)
        delete_txn(gnu, txn2)

        # Categorize expenses
        gnu.acct(("Expenses", "Auto"), acct_type="EXPENSE")
        gnu.acct(("Expenses", "Auto", "Recurring"), acct_type="EXPENSE")
        vanguard_acct = gnu.acct(("Assets", "Investments", "Vanguard"), acct_type="BANK")

        acct_names = gnu.acct_map(full=True)
        acct_guids = {name: guid for guid, name in acct_names.items()}
        move_expense(gnu, txns, acct_names, acct_guids, "%key foods%", "Groceries", "Key Foods", variants=("Key Food",))
        move_expense(gnu, txns, acct_names, acct_guids, "%c-town%", "Groceries", "C-Town")
        move_expense(gnu, txns, acct_names, acct_guids, "%associated market%", "Groceries", "Associated Market", variants=(("Associated Food"),))
        move_expense(gnu, txns, acct_names, acct_guids, "%cvs%", "Purchases", "CVS")
        move_expense(gnu, txns, acct_names, acct_guids, "%duane reade%", "Purchases", "Duane Reade", variants=("Duane reade",), override_expense_type=True)
        move_expense(gnu, txns, acct_names, acct_guids, "%walgreens%", "Purchases", "Walgreens")
        move_expense(gnu, txns, acct_names, acct_guids, "%targetcorpo%", "Purchases", "Target")
        move_expense(gnu, txns, acct_names, acct_guids, "%target t%", "Purchases", "Target")
        move_expense(gnu, txns, acct_names, acct_guids, "%laurenjenni%", "Laura", variants=("Laura (paypal)",), override_expense_type=True)
        move_expense(gnu, txns, acct_names, acct_guids, "%seamless%", "Restaurants", desc=False, override_expense_type=True)
        move_expense(gnu, txns, acct_names, acct_guids, "%seamlss%", "Restaurants", desc=False, override_expense_type=True)
        move_expense(gnu, txns, acct_names, acct_guids, "%eat24%", "Restaurants", desc=False)
        move_expense(gnu, txns, acct_names, acct_guids, "%starbucks%", "Restaurants", "Starbucks", override_expense_type=True)
        move_expense(gnu, txns, acct_names, acct_guids, "%mcdonald's%", "Restaurants", "McDonald's", override_expense_type=True,
                     desc_cb=lambda d: "McDonald's: Lunch" if d == "Lunch: McDonald's" else d)
        move_expense(gnu, txns, acct_names, acct_guids, "%chick-fil-a%", "Restaurants", "Chick-Fil-A", override_expense_type=True)
        move_expense(gnu, txns, acct_names, acct_guids, "%chipotle%", "Restaurants", "Chipotle")
        move_expense(gnu, txns, acct_names, acct_guids, "%mealsquares%", "Orders", "MealSquares")
        move_expense(gnu, txns, acct_names, acct_guids, "%thevitamins%", "Orders", "Vitamin Shoppe")
        move_expense(gnu, txns, acct_names, acct_guids, "%amazon mktplace%", "Orders", "Amazon.com", override_expense_type=True)
        move_expense(gnu, txns, acct_names, acct_guids, "%vanguard%", desc="Vanguard Transfer", acct=vanguard_acct)
        move_expense(gnu, txns, acct_names, acct_guids, "%citi autopay%", desc="Credit Card Payment", acct=gnu.citi_acct)
        move_expense(gnu, txns, acct_names, acct_guids, "%citi card online payment%", desc="Credit Card Payment", acct=lambda d: gnu.citi_acct if d.year >= 2015 else gnu.citi_3296)
        move_expense(gnu, txns, acct_names, acct_guids, "%autopay auto-pmt%", desc="Credit Card Payment", acct=gnu.checking_acct)
        move_expense(gnu, txns, acct_names, acct_guids, "%online payment, thank you%", desc="Credit Card Payment", acct=gnu.checking_acct)
        move_expense(gnu, txns, acct_names, acct_guids, "%atm withdrawal%", desc="ATM Withdrawal", acct=gnu.cash_acct)
        move_expense(gnu, txns, acct_names, acct_guids, "%mta vending machines%", "Transportation", "Metrocard", variants=(("MTA Card",)), override_expense_type=True)
        move_expense(gnu, txns, acct_names, acct_guids, "%amtrak%", "Transportation", desc=False, override_expense_type=True)
        move_expense(gnu, txns, acct_names, acct_guids, "%way2ride%", "Transportation", "Taxi")

        # One time expenses
        move_expense(gnu, txns, acct_names, acct_guids, "%milam's%", "Purchases", "Milam's")
        move_expense(gnu, txns, acct_names, acct_guids, "%84 tavern%", "Restaurants", desc=False, override_expense_type=True)
        move_expense(gnu, txns, acct_names, acct_guids, "%Blue Dog Kitchen%", "Restaurants", "Blue Dog Kitchen")
        move_expense(gnu, txns, acct_names, acct_guids, "%iron mind%", "Orders", "IronMind: Gripper, Egg")
        #move_expense(gnu, txns, acct_names, acct_guids, "%%", "Restaurants", "")
        move_expense(gnu, txns, acct_names, acct_guids, "%AMERICAN00123218517030%", "Transportation", "American Airlines Flight 1406, MIA -> JFK")
        #move_expense(gnu, txns, acct_names, acct_guids, "%%", "Transportation", "")
        move_expense(gnu, txns, acct_names, acct_guids, "%SPIRIT A48701238666090%", "Transportation", "Spirit Airlines Flight 171, LGA -> FLL")

        # Recurring expenses
        move_expense(gnu, txns, acct_names, acct_guids, "%apps_yanof%", "Recurring: Google Apps for Work", override_expense_type=True)
        move_expense(gnu, txns, acct_names, acct_guids, "%google *music%", "Recurring: Google Play Music", override_expense_type=True)
        move_expense(gnu, txns, acct_names, acct_guids, "%south brooklyn weightli%", "Recurring: SBWC", override_expense_type=True)
        move_expense(gnu, txns, acct_names, acct_guids, "%linode.com%", "Recurring: Linode", override_expense_type=True)
        move_expense(gnu, txns, acct_names, acct_guids, "%emilia sherifova%", "Recurring: Apartment Rent", override_expense_type=True)
        move_expense(gnu, txns, acct_names, acct_guids, "%conexis%", "Recurring: COBRA", override_expense_type=True)
        move_expense(gnu, txns, acct_names, acct_guids, "%kindle unlimited%", "Recurring: Kindle Unlimited", override_expense_type=True)
        move_expense(gnu, txns, acct_names, acct_guids, "%travelingma%", "Recurring: Traveling Mailbox", override_expense_type=True)
        move_expense(gnu, txns, acct_names, acct_guids, "%traveling mailbox%", "Recurring: Traveling Mailbox", override_expense_type=True)
        move_expense(gnu, txns, acct_names, acct_guids, "%newyorktime%", "Recurring: New York Times", override_expense_type=True)
        move_expense(gnu, txns, acct_names, acct_guids, "%okcupid%", "Recurring: OkCupid", override_expense_type=True)
        move_expense(gnu, txns, acct_names, acct_guids, "%soylent%", "Recurring: Soylent", override_expense_type=True)
        move_expense(gnu, txns, acct_names, acct_guids, "%t-mobile%", "Recurring: T-Mobile", override_expense_type=True)
        move_expense(gnu, txns, acct_names, acct_guids, "%experian%", "Recurring: Experian Scam", override_expense_type=True)
        move_expense(gnu, txns, acct_names, acct_guids, "%joe frank%", "Recurring: Joe Frank", variants=("Joe Frank (paypal)",), override_expense_type=True)
        move_expense(gnu, txns, acct_names, acct_guids, "%audible%", "Recurring: Audible", variants=("Audible.com",), override_expense_type=True)
        move_expense(gnu, txns, acct_names, acct_guids, "%spotify%", "Recurring: Spotify", override_expense_type=True)
        move_expense(gnu, txns, acct_names, acct_guids, "%time warner nyc%", "Recurring: Time Warner Cable", override_expense_type=True)
        move_expense(gnu, txns, acct_names, acct_guids, "%ymc* Greater ny%", "Recurring: YMCA", override_expense_type=True)
        move_expense(gnu, txns, acct_names, acct_guids, "%netflix%", "Recurring: Netflix", variants=("Paypal ??", "Netflix (paypal)"), override_expense_type=True)

        # Post-categorization cleanup.
        txn1 = find_txn(gnu, 2016, 2, 21, "Credit Card Payment")
        txn2 = find_txn(gnu, 2016, 2, 23, "Credit Card Payment")
        delete_split(gnu, txn1, gnu.checking_acct, "", "", -6127)
        delete_split(gnu, txn2, gnu.citi_acct, "", "", 6127)
        gnu.update_split(select_split(gnu, txn2, gnu.checking_acct), txn=txn1)
        delete_txn(gnu, txn2)

        # Print uncategorized
        gnu.print_txns("== Unmatched ==",
                       lambda txn_guid, account, desc, **_:
                       txn_guid not in txns
                       and not (account == gnu.cash_acct
                                or acct_names.get(account, "").startswith("Expenses: ")
                                or desc.startswith("Google Document")))


def find_txn(gnu, year, month, day, desc):
    c = gnu.conn.cursor()
    c.execute("SELECT guid FROM transactions "
              "WHERE description = ? AND post_date = ?",
              (desc, gnu.date_str(datetime.date(year, month, day))))
    rows = list(c.fetchall())
    check(len(rows) == 1)
    return rows[0][0]


def find_split(gnu, txn_date, split_memo, amount):
    c = gnu.conn.cursor()
    c.execute("SELECT s.guid, s.memo, t.guid "
              "FROM splits AS s, transactions AS t "
              "WHERE t.guid = s.tx_guid AND t.post_date = ? "
              "AND s.memo LIKE ? AND s.value_num = ? "
              "AND s.value_denom = 100 AND s.quantity_num = ? "
              "AND s.quantity_denom = 100",
              (gnu.date_str(txn_date), split_memo, amount, amount))
    rows = list(c.fetchall())
    check(len(rows) == 1, rows)
    return rows[0]


def move_expense(gnu, txns, acct_names, acct_guids, pattern, acct_name=None, desc=None, acct=None, variants=(), override_expense_type=False, desc_cb=None):
    if acct is None:
        acct_parts = ("Expenses", "Auto") + tuple(acct_name.split(": "))
        full_name = ": ".join(acct_parts)
        if full_name in acct_guids:
            acct = acct_guids[full_name]
        else:
            acct = acct_guids[full_name] = gnu.acct(acct_parts, acct_type="EXPENSE")
            acct_names[acct] = full_name
        if desc is None:
            desc = acct_parts[-1]
    else:
        assert desc is not None

    c = gnu.conn.cursor()
    c.execute("SELECT guid, tx_guid FROM splits "
              "WHERE lower(memo) LIKE ?", (pattern,))
    for split, txn, in c.fetchall():
        txns.add(txn)
        d = gnu.conn.cursor()

        # Fix txn desc
        d.execute("SELECT description, post_date FROM transactions "
                  "WHERE guid = ?", (txn,))
        rows = list(d.fetchall())
        check(len(rows) == 1)
        old_desc, post_date = rows[0]

        if desc_cb:
            new_desc = desc_cb(old_desc)
        else:
            new_desc = old_desc

        # Fix up transaction description
        if desc == False:
            pass
        elif (new_desc.startswith("Withdrawal: ")
              or new_desc.startswith("Deposit: ")
              or new_desc.startswith("Credit: ")
              or new_desc.startswith("Debit: ")
              or new_desc.startswith("Authorization: ")
              or new_desc.startswith("Payment Received: ")
              or new_desc.startswith("Preapproved Payment Sent: ")
              or new_desc.startswith("Payment Sent: ")
              or new_desc.startswith("Subscription Payment Sent: ")):
            new_desc = desc
        else:
            for variant in variants:
                if new_desc == variant:
                    new_desc = desc
                    break
                if new_desc.startswith(variant + ":"):
                    new_desc = desc + new_desc[len(variant):]
                    break
            else:
                check(new_desc == desc or new_desc.startswith(desc + ":"), (txn, new_desc))

        if new_desc != old_desc:
            gnu.update("transactions", "guid", txn,
                        (("description", new_desc),))

        # Fix expense account
        d.execute("SELECT guid, account_guid FROM splits "
                  "WHERE tx_guid = ? AND guid <> ?", (txn, split))
        rows = list(d.fetchall())
        expense_split = None
        expense_acct = None
        for other_split, other_acct in rows:
            n = acct_names[other_acct]
            if n == "Expenses" or n == "Income" or n.startswith("Expenses: "):
                expense_split = other_split
                expense_acct = other_acct
                break
            elif n == "Imbalance-USD":
                expense_split = other_split
                expense_acct = other_acct

        if callable(acct):
            new_acct = acct(gnu.date(post_date))
        else:
            new_acct = acct

        if expense_acct and expense_acct != new_acct:
            if ((override_expense_type
                 or not acct_names[expense_acct].startswith("Expenses: "))
                and not acct_names[expense_acct] == "Expenses: Work"):
                gnu.update("splits", "guid", expense_split,
                            (("account_guid", new_acct),))


def select_split(gnu, txn, acct):
    c = gnu.conn.cursor()
    c.execute("SELECT guid FROM splits WHERE tx_guid = ? AND account_guid = ? ", (txn, acct))
    rows = list(c.fetchall())
    check(len(rows) == 1, rows)
    return rows[0][0]


def delete_split(gnu, txn, acct, memo, action, amount):
    c = gnu.conn.cursor()
    c.execute("DELETE FROM splits WHERE tx_guid = ? AND account_guid = ? "
              "AND memo = ? AND action = ? AND value_num = ? "
              "AND value_denom = 100 AND quantity_num = ? "
              "AND quantity_denom = 100 AND lot_guid IS NULL",
              (txn, acct, memo, action, amount, amount))
    check(c.rowcount == 1)


def delete_txn(gnu, txn):
    c = gnu.conn.cursor()
    c.execute("SELECT * FROM splits WHERE tx_guid = ?", (txn,))
    rows = list(c.fetchall())
    check(len(rows) == 0, rows)
    c.execute("DELETE FROM transactions WHERE guid = ?", (txn,))
    check(c.rowcount == 1)


def test_parse_yearless_dates():
    txn_post_date = datetime.date(2013, 1, 1)
    while txn_post_date <= datetime.date(2014, 1, 1):
        for i in range(-179, 180):
            date = txn_post_date + datetime.timedelta(i)
            date_str = GnuCash.yearless_date_str(date)
            assert date == GnuCash.yearless_date(date_str, txn_post_date)
        txn_post_date += datetime.timedelta(1)


#
# Chase gnucash import functions.
#

def read_pdf_txns(json_filename):
    with open(json_filename) as fp:
        txns = json.load(fp)

    for date_str, prev_balance, balance, amount, desc in txns:
        assert balance == prev_balance + amount
        date = (datetime.datetime.strptime(date_str, "%Y-%m-%d")
                .date())
        tstr = ChaseStr.parse_pdf_string(desc)
        yield date, amount, balance, desc, tstr


def read_csv_txns(csv_filename):
    with open(csv_filename) as fp:
        rows = list(csv.reader(fp))

    header = ['Type', 'Post Date', 'Description', 'Amount', 'Check or Slip #']
    assert rows[0] == header

    for ttype, date_str, desc, amount_str, num in rows[:0:-1]:
        assert ttype in ('CREDIT', 'DEBIT', 'DSLIP', 'CHECK'), ttype
        assert not num, num
        date = datetime.datetime.strptime(date_str, "%m/%d/%Y").date()
        amount = parse_price(amount_str, allow_minus=True)
        tstr = ChaseStr.parse_csv_string(desc)
        yield date, amount, None, desc, tstr


def merge_txns(gnu, txns, acct, disable_memo_merge=False, acct_balance=None,
               reconcile_date=None, compat=False, debit_label="Withdrawal",
               credit_label="Deposit"):
    first_date = last_date = None
    split_guids = set()

    for date, amount, balance, desc, tstr in txns:
        if reconcile_date is not None:
            prev_balance = balance - amount
            if acct_balance is None:
                gnu.new_txn(
                    date=date,
                    desc="Opening Balance",
                    memo="",
                    acct=acct,
                    amount=prev_balance,
                    src_acct=gnu.opening_acct,
                    reconcile_date=reconcile_date)
            elif prev_balance != acct_balance:
                print ("Imbalance:", reconcile_date, date, prev_balance,
                       acct_balance)
                gnu.new_txn(
                    date=date,
                    desc="Missing transactions",
                    memo="",
                    acct=acct,
                    amount=prev_balance - acct_balance,
                    src_acct=gnu.imbalance_acct,
                    reconcile_date=reconcile_date)

        # If a pre-existing imported txn was found, update it.
        m = gnu.find_matching_txn(acct, date, amount, tstr,
                                  split_guids) if not compat else None
        if m:
            split_guid, merged_tstr = m
            if disable_memo_merge: merged_tstr = tstr
            gnu.update_split(split_guid, memo_tstr=merged_tstr)
        else:
            # Support untagged memo strings for backwards
            # compatibilitity with test code.
            if compat:
                memo = " || ".join(desc)
                memo_tstr = None
            else:
                memo = None
                memo_tstr = tstr

            # Try to find manually entered transaction that's close in
            # date with matching amount and merge with it, otherwise
            # add a new transaction.
            m = gnu.find_closest_txn([acct], date, amount,
                                     no_action=True)
            if m:
                split_guid, split_memo, txn_guid, txn_post_date = m
                assert not split_memo or split_memo in ('Checking',), split_memo
                gnu.update_split(split_guid,
                                  memo=memo,
                                  memo_tstr=memo_tstr,
                                  action=gnu.yearless_date_str(
                                      date, txn_post_date),
                                  reconcile_date=reconcile_date)
            else:
                txn_guid, split_guid = gnu.new_txn(
                    date=date,
                    desc="{}: {}".format(debit_label if amount <= 0 else credit_label,
                                         memo or memo_tstr.as_string(tags=False)),
                    memo=memo or memo_tstr.as_string(),
                    acct=acct,
                    amount=amount,
                    reconcile_date=reconcile_date)

        assert split_guid
        assert split_guid not in split_guids
        split_guids.add(split_guid)

        if not first_date: first_date = date

        assert last_date is None or date >= last_date
        last_date = date

        acct_balance = balance

    return first_date, last_date, split_guids, acct_balance


#
# Chase pdf parsing functions.
#

def parse_chase_pdftext(json_filename):
    statement_date = parse_statement_date(json_filename)
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
    #   - Switch to signed "AMOUNT" column instead of positive "Additions" and
    #     "Deductions" columns
    #   - Switch to "Beginning Balance" instead of "Opening Balance"
    #   - Fragments are now groups of words with spaces, instead of individual
    #     words
    #   - Transactions grouped by dates and only include daily balances, only
    #     way to distinguish them is by slightly larger vertical spacing
    #   - Dates no longer included on beginning/ending balance transaction lines
    #   - Has junk vertical barcode on side of statement that interferes with
    #     parsing
    #   - ALL CAPS transations with lots of extra wrapping, and multilevel
    #     indent
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
    #   - [" DATE", "DESCRIPTION", "AMOUNT", "BALANCE"] header is now image
    #     instead of text
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
            if txn_date > statement_date:
                txn_date = txn_date.replace(year=statement_date.year - 1)
                assert txn_date <= statement_date
            assert txn_date >= statement_date - datetime.timedelta(35), txn_date

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

            if desc and desc[0].text == "Ending Balance":
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
                assert txn_date == statement_date
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
            txn_balance = parse_price(balance[-1].text, allow_minus=True)
            if newstyle:
                assert len(balance) == 1
            else:
                assert len(balance) == 2
                assert balance[0].text == "$"

        # Determine whether line begins a new transaction. If line
        # contains a date it always indicates a new transaction. But
        # not every transaction has its own date (transactions are
        # grouped by date starting sep 2006, so also start a new
        # transaction when there is a tranaction amount. But avoid
        # doing this on oldstyle pdfs because they align amounts to
        # bottom of transaction instead of top.
        if txn_date is not None or (newstyle and txn_amount is not None):
            # If transaction is missing an amount value, look at
            # previous transaction to see if it consists solely of an
            # amount with no date, balance or description. If so,
            # remove that transaction and use the amount from it. This
            # is needed for a few statements starting feb 2007 which
            # add bolding to deposits amounts. The bolding moves up
            # the amount fragment text y positions slightly, isolating
            # them on their own lines.
            if newstyle and txn_amount is None:
                prev_txn = txns.pop()
                assert prev_txn.date is None
                assert prev_txn.amount is not None
                assert prev_txn.balance is None
                assert prev_txn.descs == [[]]
                txn_amount = prev_txn.amount
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
            assert desc
            txns[-1].descs.append(desc)

    fragments_discard_until(it, discarded_text, None)

    opening_balance = parse_price(opening_balance_str)
    closing_balance = parse_price(closing_balance_str)
    cur_balance = opening_balance
    txnit = PeekIterator(txns, lookahead=1, lookbehind=2)
    for txn in txnit:
        assert all(txn.descs)
        assert txn.amount is not None
        if txn.date is None:
            txn.date = txnit.peek(-1).date
        if txnit.prev_elems > 1:
            assert txnit.peek(-1).date <= txn.date
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


def parse_statement_date(json_filename):
    return datetime.date(*[int(g) for g in re.match(
        r"^(?:.*?/)?([0-9]{4})-([0-9]{2})-([0-9]{2}).json$",
        json_filename).groups()])


def pdf_version(statement_date):
    vstr = "V{:%Y_%m}".format(statement_date)
    return Pdf(bisect.bisect(list(Pdf.__members__.keys()), vstr))


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

#
# Paypal gnucash import functions.
#

def merge_paypal_txns(gnu, txns):
    for txn in txns:
        txn_value = txn.ending_balance["USD"] - txn.starting_balance["USD"]
        action = gnu.yearless_date_str(txn.date)

        # Look for existing paypal split entry. If found make sure
        # it is up to date and move on.
        c = gnu.conn.cursor()
        c.execute("SELECT s.guid, s.memo, s.value_num, t.guid "
                  "FROM splits AS s "
                  "INNER JOIN transactions AS t ON (t.guid = s.tx_guid) "
                  "WHERE s.account_guid = ? AND s.action = ? "
                  "    AND s.memo LIKE '%time=' || ? || '%'",
                  (gnu.paypal_acct, action, paypal_date_str(txn.date)))
        rows = c.fetchall()
        if rows:
            check(len(rows) == 1)
            split_guid, split_memo, split_value, txn_guid = rows[0]
            check(split_memo == txn.memo.as_string())
            check(split_value == txn_value)
            continue

        # Need to create paypal split. Look for existing bank
        # transaction to attach paypal split to.
        txn_guid = None
        bank_row, = [r for r in txn.rows
                     if r.bank_type or r.credit_type] or [None]
        if (txn_guid is None and bank_row and not bank_row.void
            and bank_row.net_amount):
            m = gnu.find_closest_txn(gnu.bank_accts, txn.date.date(),
                                      -bank_row.net_amount,
                                      no_split=gnu.paypal_acct,
                                      max_days=4)
            if m:
                txn_guid = m[2]

        # If no matching bank transaction, looking matcihng expense
        # transaction to attach paypal split to.
        main_row = txn.rows[txn.main_row]
        if (txn_guid is None and main_row and not main_row.void
            and main_row.net_amount):
            m = gnu.find_closest_txn([], txn.date.date(),
                                      -main_row.net_amount,
                                      no_split=gnu.paypal_acct,
                                      max_days=4)
            if m:
                txn_guid = m[2]

        # No existing transaction found. Create new transaction and splits.
        if txn_guid is None:
            txn_guid, split_guid = gnu.new_txn(
                date=txn.date.date(),
                desc="{}: {}".format(main_row.type, main_row.name),
                memo=txn.memo.as_string(),
                acct=gnu.paypal_acct,
                amount=txn_value,
                src_amount=(0 if main_row.void or main_row is bank_row
                            else -main_row.net_amount))
            gnu.balance_txn(txn_guid)

        # Existing transaction was found but need to add or update a
        # paypal split inside it.
        else:
            c.execute("SELECT guid, memo, action "
                      "FROM splits WHERE tx_guid = ? AND account_guid = ?",
                      (txn_guid,gnu.paypal_acct))
            rows = c.fetchall()
            if rows:
                check(len(rows) == 1)
                split_guid, split_memo, split_action = rows[0]
                check(not split_memo)
                check(not split_action)
                gnu.update_split(split_guid, action, memo_tstr=txn.memo,
                                 amount=txn_value)
            else:
                gnu.new_split(txn_guid, gnu.paypal_acct,
                              txn_value,
                              memo=txn.memo.as_string(),
                              action=action)
            gnu.balance_txn(txn_guid)


#
# Paypal csv parsing functions.
#

def read_paypal_txns(csv_filenames):
    balance = {"USD": 0, "EUR": 0}
    csv_fields = []     # List of fields from csv header rows.
    csv_field_idx = {}  # Map field name -> list position.
    txns = []           # List of transactions
    row_idx = {}        # Map transaction_id -> csv row
    for csv_filename in csv_filenames:
        txns.extend(read_paypal_csv(csv_filename,
                                    balance, csv_fields, csv_field_idx,
                                    row_idx, txns))
    check_paypal_txns(txns)
    generate_paypal_memos(txns, csv_fields)
    return txns


def read_paypal_csv(csv_filename, balance, csv_fields, csv_field_idx, row_idx,
                    prev_txns):
    ORDER_TYPE = "Order"
    ITEM_TYPE = "Shopping Cart Item"
    VOID_TYPES = (ITEM_TYPE, ORDER_TYPE, "eBay Payment Canceled",
                  "Cancelled Fee", "Authorization")
    UPDATE_TYPE_PREFIX = "Update to "
    BANK_NAME = "Bank Account"
    BANK_TYPES = ("Add Funds from a Bank Account",
                  "Withdraw Funds to Bank Account",
                  "Update to Add Funds from a Bank Account")
    CREDIT_NAME = "Credit Card"
    CREDIT_TYPES = ("Charge From Credit Card", "Credit to Credit Card")
    AVOID_MAIN_TYPES = VOID_TYPES + BANK_TYPES + CREDIT_TYPES + (
        "Temporary Hold", "Payment Review", "Currency Conversion")

    avoid_main_idx = {t: n for n, t in enumerate(AVOID_MAIN_TYPES)}

    with open(csv_filename) as fp:
        rows = list(csv.reader(fp))

    # Make sure field list is the same in all csv files.
    f = [csv_field.strip().lower().replace(" ", "_") for csv_field in rows[0]]
    if csv_fields:
        check(csv_fields == f)
    else:
        check(not csv_field_idx)
        csv_fields.extend(f)
        csv_field_idx.update((csv_field, i)
                             for i, csv_field in enumerate(csv_fields))
    check(len(csv_fields) == len(csv_field_idx), "Dup fields")

    # Cached position in prev_txns array.
    prev_txns_pos = None

    # Group rows together by date.
    for date, rows in groupby(CsvRow.wrap(rows[:0:-1], csv_field_idx),
                              key=paypal_date):
        txn = Txn()
        txn.date = date
        txn.rows = list(rows)
        txn.updates = None
        txn.updated_by = None
        txn.starting_balance = balance.copy()

        # Allow multiple CSV files from overlapping date ranges to be
        # read without error as long as the transactions in the date
        # ranges match up.
        if prev_txns:
            if prev_txns_pos is None:
                prev_txns_pos = bisect.bisect_left([t.date for t in prev_txns],
                                                   date)
            prev_txn = (prev_txns[prev_txns_pos]
                        if prev_txns_pos < len(prev_txns) else None)
            prev_txns_pos += 1
            if prev_txn:
                check(len(txn.rows) == len(prev_txn.rows))
                check(all(t.row == p.row
                          for t, p in zip(txn.rows, prev_txn.rows)))
                continue

        for row in txn.rows:
            # Parse net, gross, fee, and balance amounts.
            # Consolidate and check redundant net and gross columns
            # into single net_amount column.
            if row.type == ORDER_TYPE:
                check(row.balance == "...")
                row.balance_amount = None
                check(row.net == "...")
                row.net_amount = parse_price(row.gross, allow_minus=1)
                check(row.fee == "...")
                row.fee_amount = None
            else:
                row.balance_amount = parse_price(row.balance, allow_minus=1)
                balance[row.currency] = row.balance_amount
                if row.type == ITEM_TYPE:
                    check(not row.net)
                    row.net_amount = parse_price(row.gross, allow_minus=1)
                    check(not row.fee)
                    row.fee_amount = None
                else:
                    row.net_amount = parse_price(row.net, allow_minus=1)
                    row.fee_amount = (parse_price(row.fee, allow_minus=1)
                                      if row.fee != "..." else None)
                    check(parse_price(row.gross, allow_minus=1)
                          == row.net_amount - (row.fee_amount or 0))

            # Add transaction and updates/updated_by pointers.
            row.txn = weakref.proxy(txn)
            row.updates = None
            row.updated_by = None
            if row.type.startswith(UPDATE_TYPE_PREFIX):
                row.updates = weakref.proxy(row_idx[row.reference_txn_id])
                check(row.updates.updated_by is None)
                row.updates.updated_by = weakref.proxy(row)

                check(txn.updates is None)
                txn.updates = row.updates.txn
                check(txn.updates.updated_by is None)
                txn.updates.updated_by = weakref.proxy(txn)

            # Record whether row affects bank account, credit card, or
            # paypal balances. Rows with void types are informational
            # and don't affect the paypal account balance.
            row.void_type = row.type in VOID_TYPES
            row.bank_type = False
            row.credit_type = False
            if row.type in BANK_TYPES:
                check(row.name == BANK_NAME)
                row.bank_type = True
            elif row.type in CREDIT_TYPES:
                check(row.name == CREDIT_NAME)
                row.credit_type = True
            else:
                check(BANK_NAME not in row.type)
                check(CREDIT_NAME not in row.type)

            # Check uniqueness of transaction_ids, except for
            # shopping cart item rows, which duplicate the
            # main transaction id they are associated with.
            check(row.transaction_id not in row_idx
                  or row_idx[row.transaction_id].type == ITEM_TYPE)
            row_idx[row.transaction_id] = row

        txn.ending_balance = balance.copy()

        # Main row describing the whole transaction (as opposed to
        # other rows that describe parts of the transaction like
        # currency conversions, fees, shopping cart items, bank
        # transfers) is typically the last row in the transaction that
        # isn't a void or review or bank transfer type.
        txn.main_row = min(range(len(txn.rows)), key=lambda n:
                           (avoid_main_idx.get(txn.rows[n].type, -1), -n))

        yield txn


def paypal_date(row):
    date = datetime.datetime.strptime(row.date, "%m/%d/%Y")
    time = datetime.datetime.strptime(row.time, "%H:%M:%S")
    tz = datetime.timezone(datetime.timedelta(
        hours={"PST":-8, "PDT":-7}[row.time_zone]))
    return (datetime.datetime(date.year, date.month, date.day, time.hour,
                              time.minute, time.second, time.microsecond, tz)
            .astimezone(datetime.timezone.utc))


def check_paypal_txns(txns):
    """Make sure transactions are in order and row balances match amounts."""
    prev_txn = None
    for txn in txns:
        # Initialize calculated balance for the transaction which will
        # be updated with changes from each row in the transaction,
        # and then compared for equality against the transaction
        # ending balance.
        txn.calc_balance = txn.starting_balance.copy()

        # If this transaction updates a previous transaction, the
        # previous transaction might have had rows that didn't show up
        # in its ending balance because the changes described in those
        # rows were delayed pending the update. Add those changes in
        # here to verify they now show up in the ending balance for
        # this transaction.
        if txn.updates:
            for currency in txn.updates.calc_balance:
                txn.calc_balance[currency] += (
                    txn.updates.calc_balance[currency]
                    - txn.updates.ending_balance[currency])

        # Update calculated balance with net change from each row in
        # this transaction.
        for row in txn.rows:
            # If the row is updated (replaced) by a later row, or has
            # a void (cancelled or informational) type, then it will
            # not affect the paypal account balance.
            row.void = row.updated_by is not None or row.void_type
            if not row.void:
                txn.calc_balance[row.currency] += row.net_amount

            # Verify the row either doesn't list a balance amount, or
            # that the row balance amount equals the calculated
            # balance.
            if (row.balance_amount is not None
                and row.balance_amount != txn.calc_balance[row.currency]):
                # Allow unusual case where row balance doesn't match the
                # calculated balance, but instead equals the ending
                # balance of the transaction containing the row. This
                # seems to happen unpredictably, for most but not all
                # shopping cart item rows and for some very old rows
                # before 2007.
                check(row.balance_amount == txn.ending_balance[row.currency])

        # Verify the transaction ending balance equals the calculated
        # balance, unless a row in this transaction is updated by a
        # row in a later transaction. In this case, the changes from
        # rows in this transaction might not show up until the later
        # transaction. In this case, the changes will be added up and
        # verified when that transaction is processed (see txn.updates
        # code above).
        if txn.updated_by is None:
            check(txn.ending_balance == txn.calc_balance, txn.date)
        else:
            check(txn.updated_by.date > txn.date)

        # Check for increasing transaction dates.
        check(prev_txn is None or txn.date > prev_txn.date)
        prev_txn = txn

def generate_paypal_memos(txns, csv_fields):
    """Add txn.memo fields."""

    # Show fields in this order.
    field_order = (
        "void", "amount", "fee", "shipping", "insurance", "tax", "cc", "bank",
        "name", "type", "time", "updated", "txn", "status", "ref", "from", "to",
        "counterparty", "shipping_address", "address_status", "item_title",
        "item_id", "auction_site", "item_url", "closing_date", "buyer_id",
        "quantity", "receipt_id", "invoice_number", "contact_phone_number",
        "custom_number", "option_1_name", "option_1_value", "option_2_name",
        "option_2_value",
    )
    field_order_set = set(field_order)

    # Discard these fields after the first row in the transaction if the
    # values are duplicates of values already showing up in the first row.
    discard_dups = set(("time", "name", "txn", "from", "to", "counterparty",
                        "shipping_address", "address_status", "quantity",
                        "invoice_number", "item_title", "item_id",
                        "custom_number"))

    # Allow these fields after the first row in the transaction to
    # duplicate values already showing up in the first row. An error
    # will be triggered on any field duplicating a value from the
    # first row, unless the field is listed in either discard_dups, or
    # allow_dups.
    allow_dups = set(("void", "amount", "ref"))

    for txn in txns:
        # Iterate over transaction rows with main row first, so later rows can
        # set & compare against override values in the main row.
        rows = txn.rows.copy()
        rows.insert(0, rows.pop(txn.main_row))

        # First pass over transaction rows, filling row.override
        # dictionary with field values that replace or hide CSV field
        # values.
        # Two passes are needed because later bank account/credit card
        # rows will make changes to the first row's overrride
        # dictionary.
        for row in rows:
            row.override = {}

            # Mark amounts not added to paypal balance.
            row.override["void"] = row.void

            # Collapse balance/net/gross fields into amount.
            row.override["amount"] = "{:.2f}{}".format(
                row.net_amount/100.0, row.currency)
            row.override["balance"] = None
            row.override["net"] = None
            row.override["gross"] = None
            row.override["currency"] = None

            # Collapse and abbreviate fee, tax, etc fields.
            row.override["fee"] = row.fee if row.fee_amount else None
            row.override["shipping"] = (
                row.shipping_and_handling_amount
                if row.shipping_and_handling_amount!="0.00" else None)
            row.override["shipping_and_handling_amount"] = None
            row.override["tax"] = (
                row.sales_tax if row.sales_tax != "0.00" else None)
            row.override["sales_tax"] = None
            row.override["insurance"] = (
                row.insurance_amount if row.insurance_amount!="0.00" else None)
            row.override["insurance_amount"] = None

            # Collapse seperate date/time fields into one timestamp.
            row.override["time"] = paypal_date_str(txn.date)
            row.override["date"] = None
            row.override["time_zone"] = None

            # Add update date.
            if row.updated_by:
              row.override["updated"] = paypal_date_str(row.updated_by.txn.date)

            # Abbreviate transaction_id and status.
            row.override["txn"] = row.transaction_id
            row.override["transaction_id"] = None
            if row.status == "Completed":
                row.override["status"] = None

            # Abbreviate some other field names.
            row.override["ref"] = row.reference_txn_id
            row.override["reference_txn_id"] = None
            row.override["from"] = row.from_email_address
            row.override["from_email_address"] = None
            row.override["to"] = row.to_email_address
            row.override["to_email_address"] = None
            row.override["counterparty"] = row.counterparty_status
            row.override["counterparty_status"] = None

            # Move bank transfer amount into the main row, where it is
            # more easily visible than in the bank account row. Also
            # delete redundant ref and name fields in the bank account
            # row.
            if row.bank_type:
                row.override["name"] = None
                if not row.void:
                    check("bank" not in rows[0].override)
                    rows[0].override["bank"] = row.override.pop("amount")
                if row.reference_txn_id and not row.updates:
                    check(row.reference_txn_id == rows[0].transaction_id)
                    row.override["ref"] = None

            # Move credit card amount into the main row, where it is
            # more easily visible than in the credit card row. Also
            # delete redundant ref and name fields in the credit card
            # row.
            if row.credit_type:
                row.override["name"] = None
                if not row.void:
                    check("cc" not in rows[0].override)
                    rows[0].override["cc"] = row.override.pop("amount")
                check(row.reference_txn_id
                      in (rows[0].transaction_id, row.reference_txn_id))
                row.override["ref"] = None

            # Check for and delete duplicate field values after the
            # main row, following discard_dups and allow_dups
            # variables.
            if row is not rows[0]:
                for name in field_order:
                    new_value = paypal_row_value(row, name)
                    if (new_value
                        and new_value == paypal_row_value(rows[0], name)):
                        if name in discard_dups:
                            row.override[name] = None
                        else:
                            check(name in allow_dups, name)

        # Second pass over transaction rows, using csv field and
        # override values to fill the transaction memo string.
        txn.memo = TaggedStr()
        for i, row in enumerate(rows):
            for name in field_order:
                value = paypal_row_value(row, name)
                if value:
                    if (i == 0 and not txn.memo.lines
                        and name in ("name", "type")):
                        txn.memo.lines.append(value)
                    else:
                        tag = name.replace("_", "-")
                        if i > 0:
                            tag = "{}-{}".format(i, tag)
                        txn.memo.tags[tag] = (
                            [value] if isinstance(value, str) else value)

            for name, value in row.override.items():
                check(not value or name in field_order_set, name)

            for j, value in enumerate(row.row):
                check(not value or csv_fields[j] in row.override
                      or csv_fields[j] in field_order_set, csv_fields[j])


def paypal_row_value(row, name):
  if name in row.override:
      return row.override[name]
  elif name in row.field_idx:
      return row.row[row.field_idx[name]]


def paypal_date_str(date):
    return date.strftime("%Y-%m-%dT%H:%M:%S")


#
# Citicard tsv parsing function.
#

def read_citi_tsv(tsv_filename):
    with open(tsv_filename) as fp:
        head = fp.readline()
        body = fp.read()
    check(head == "Status\tDate\tDescription\tDebit\tCredit\n")
    pos = 0
    txns = []
    while pos < len(body):
        m = re.compile(r"([^\t\n]+)\t([^\t\n]+)\t([^\t]+)\t([^\t\n]*)"
                       r"(?:\t([^\t\n]*))?(?:\n|$)").match(body, pos)
        pos = m.end()
        status, date_str, desc, debit, credit = m.groups()
        check(status == "Cleared")
        date = datetime.datetime.strptime(date_str, "%m/%d/%Y").date()
        tstr = CitiStr()
        tstr.lines.extend(desc.rstrip("\n").split("\n"))
        tstr.set_tag("tsv", True)
        if debit:
            check(not credit)
            amount = -parse_price(debit)
        else:
            check(credit)
            amount = parse_price(credit)
        txns.append((date, amount, None, None, tstr))
    txns.sort(key=lambda x: x[0])
    return txns


#
# Mypay gnucash import functions.
#

def create_mypay_accts(gnu):
    """Create mypay accounts, return mapping:

        (cat, title, desc) -> (account guid, goog_account_guid, flags)
    """
    splits = (
        (PAY, 'Group Term Life', "<p>Value of Life Insurance (as defined by "
         "IRS) for tax calculation. <div style=font-style:italic;>This has a "
         "matching deduction offset and is not paid out through Payroll.</div>"
         "</p><br><a href='https://sites.google.com/a/google.com/us-benefits/"
         "health-wellness/life-insurance-1' target='_blank'>Click here to "
         "learn more</a>",
         ("Income", "Taxable Benefits", "Google Life Insurance"), None, NONNEG),

        (PAY, 'Regular Pay', '<p>Regular wages for time worked at base salary '
         '/ hourly rate</p>',
         ("Income", "Salary", "Google Regular Pay"), None, NONNEG),

        (PAY, 'Vacation Pay', '<p>Vacation time taken against balance.</p>',
         ("Income", "Salary", "Google Vacation Pay"), None, NONNEG),

        # Taxable benefits folder tracks cost to google of non-cash
        # benefits that google pays for and i receive as goods or
        # services, and also owe taxes on
        #
        # Untaxed benefits folder tracks cost to google of non-cash
        # benefits that google pays for and i receive as good or
        # service, and do not owe any taxes on
        #
        # Actual benefits received are tracked in Expenses ->
        # Subsidized Hierarchy and show value of benefit that i
        # receive.
        #
        # Downside of this arrangement, is that neither account shows
        # money i personally pay for benefit. have to manually
        # subtract gym expense balance from gym benenfit balance to
        # see how much my decision to join gym actually costs me.
        #
        # An alternative to this arrangement would use one account
        # instead of two for each benefit, and balance would reflect
        # my actual cash expenditure. But then there would be no
        # account showing my tax liability, and also the gnucash ui
        # sucks when multiple lines in same account.
        (PAY, 'Gym Reim Txbl', '<p>Taxable Gym Reimbursement</p>',
         ("Income", "Taxable Benefits", "Google Gym Membership"), None, NONNEG),

        (PAY, 'Annual Bonus', "<p>Annual Bonus plan</p><br><a href='https://"
         "support.google.com/mygoogle/answer/4596076' target='_blank'>Click "
         "here to learn more</a>",
         ("Income", "Salary", "Google Annual Bonus"), None, NONNEG),

        (PAY, 'Prize/ Gift', '<p>Value of Prizes and Gifts for tax '
         'calculation. <div style=font-style:italic;>This has a matching '
         'deduction offset and is not paid out through Payroll.</div></p>',
         ("Income", "Taxable Benefits", "Google Holiday Gift"), None, NONNEG),

        (PAY, 'Prize/ Gift', '<p>Company-paid tax offset for Prizes and '
         'Gifts.</p>',
         ("Income", "Taxable Benefits", "Google Holiday Gift Tax Offset"),
         None, NONNEG),

        (PAY, 'Holiday Gift', '<p>Company-paid tax offset for Holiday '
         'Gift.</p>',
         ("Income", "Taxable Benefits", "Google Holiday Gift Tax Offset"),
         None, NONNEG),

        (PAY, 'Holiday Gift', '<p>Value of Holiday Gift for tax calculation. '
         '<div style=font-style:italic;>This has a matching deduction offset '
         'and is not paid out through Payroll.</div></p>',
         ("Income", "Taxable Benefits", "Google Holiday Gift"), None, NONNEG),

        (PAY, 'Peer Bonus', "<p>Peer Bonus payment. Thank you!</p><br><a "
         "href='https://support.google.com/mygoogle/answer/6003818?hl=en&"
         "ref_topic=3415454' target='_blank'>Click here to learn more</a>",
         ("Income", "Salary", "Google Peer Bonus"), None, NONNEG),

        (PAY, 'Patent Bonus', "<p>Patent Bonus payment</p><br><a href='https://"
         "sites.google.com/a/google.com/patents/patents/awards/monetary-"
         "awards' target='_blank'>Click here to learn more</a>",
         ("Income", "Salary", "Google Patent Bonus"), None, NONNEG),

        (PAY, 'Goog Stock Unit', "<p>Value of Google Stock Units (GSU) for tax "
         "calculation. <div style=font-style:italic;>This is not paid out "
         "through Payroll.</div></p><br><a href='https://sites.google.com/a/"
         "google.com/stock-admin-landing-page/' target='_blank'>Click here to "
         "learn more</a>",
         ("Income", "Taxable Benefits", "Google Stock Units"), None, NONNEG),

        (PAY, 'Retroactive Pay', '<p>Adjustment to wages from a previous pay '
         'period.</p>',
         ("Income", "Salary", "Google Wage Adjustment"), None, 0),

        (PAY, 'Refund Report', '<p>Non-pay-impacting code for metadata '
         'tracking</p>',
         ("Income", "Salary", "Google Wage Adjustment"), None, 0),

        (PAY, 'Placeholder', '<p>Non-pay-impacting code for metadata '
         'tracking</p>',
         ("Income", "Salary", "Google Wage Adjustment"), None, 0),

        (PAY, 'Spot Bonus', "<p>Spot Bonus payment</p><br><a href='https://"
         "support.google.com/mygoogle/answer/6003815?hl=en&ref_topic=3415454' "
         "target='_blank'>Click here to learn more</a>",
         ("Income", "Salary", "Google Spot Bonus"), None, NONNEG),

        (PAY, 'Vacation Payout', '<p>Liquidation of Vacation balance.</p>',
         ("Income", "Salary", "Google Vacation Payout"), None, NONNEG),

        (DED, 'Group Term Life', '<p>Offset deduction; see matching earning '
         'code for more info</p>',
         ("Expenses", "Subsidized", "Google Life Insurance"), None, NONNEG),

        (DED, '401K Pretax', '<p>Pre-tax 401k contribution defined as a '
         'percentage or dollar election of eligible earnings</p>\n<p><a href='
         '"https://support-content-draft.corp.google.com/mygoogle/topic/'
         '6205846?hl=en&ref_topic=6206133" target="_blank">Click here to learn '
         'more</a></p>',
         ("Assets", "Investments", "401K"),
         ("Income", "Untaxed Benefits", "Google Employer 401K Contribution"),
         NONNEG),

        (DED, 'Medical', "<p>Employee contribution towards Medical Insurance "
         "plan</p><br><a href='https://sites.google.com/a/google.com/us-"
         "benefits/health-wellness/medical-benefits' target='_blank'>Click "
         "here to learn more</a>",
         ("Expenses", "Subsidized", "Google Medical Insurance"), None, NONNEG),

        (DED, 'Gym Deduction', "<p>Employee contribution towards Gym "
         "Membership</p><br><a href='https://sites.google.com/a/google.com/"
         "us-benefits/health-wellness/gyms-and-fitness-g-fit' target='_blank'>"
         "Click here to learn more</a>",
         ("Expenses", "Subsidized", "Google Gym Membership"), None, NONNEG),

        (DED, 'Pretax 401 Flat', '<p>Pre-tax 401k contribution defined as a '
         'dollar amount per pay cycle</p>\n<p><a href="https://support-content-'
         'draft.corp.google.com/mygoogle/topic/6205846?hl=en&ref_topic='
         '6206133" target="_blank">Click here to learn more</a></p>',
         ("Assets", "Investments", "401K"),
         ("Income", "Untaxed Benefits", "Google Employer 401K Contribution"),
         NONNEG),

        (DED, 'Dental', "<p>Employee contribution towards Dental Insurance "
         "premiums</p><br><a href='https://sites.google.com/a/google.com/"
         "us-benefits/health-wellness/dental-insurance' target='_blank'>Click "
         "here to learn more</a>",
         ("Expenses", "Subsidized", "Google Dental Insurance"), None, NONNEG),

        (DED, 'Vision', "<p>Employee contribution towards Vision Insurance "
         "premiums</p><br><a href='https://sites.google.com/a/google.com/us-"
         "benefits/health-wellness/vision-insurance' target='_blank'>Click "
         "here to learn more</a>",
         ("Expenses", "Subsidized", "Google Vision Insurance"), None, NONNEG),

        (DED, 'Prize Gross Up', '<p>Offset deduction; see matching earning '
        'code for more info</p>',
         ("Expenses", "Subsidized", "Google Holiday Gift"), None, NONNEG),

        (DED, 'Holiday Gift', '<p>Offset deduction; see matching earning code '
        'for more info</p>',
         ("Expenses", "Subsidized", "Google Holiday Gift"), None, NONNEG),

        (DED, 'RSU Stock Offst', '<p>Offset deduction; see matching earning '
        'code for more info</p>',
         ("Assets", "Investments", "Google Stock Units"), None, NONNEG),

        (DED, 'GSU Refund', '<p>Refund for overage of stock withholding.<bt >'
        '</bt>When your stock vests, Google is required to recognize its value '
        'for taxes and executes enough units of stock to cover these taxes. '
        'Since Google can only execute stock in whole units, there is often a '
        'remainder amount from the sale which is returned to you through this '
        'deduction code.</p>',
         ("Assets", "Investments", "Google Stock Units"), None, NONPOS),

        # https://www.irs.gov/Affordable-Care-Act/Form-W-2-Reporting-of-Employer-Sponsored-Health-Coverage
        # W2 Box 12, Code DD
        (DED, 'ER Benefit Cost', '<p>Total contributions by Employer towards '
         'benefits for W-2 reporting</p>',
         ("Expenses", "Subsidized", "Google Medical Insurance"),
         ("Income", "Untaxed Benefits", "Google Employer Medical Insurance "
          "Contribution"), NONNEG | GOOG_ONLY),

        # FIXME: notmuch search for 14.95 charge on 9/2014 to see what
        # this was, then add expense transaction to 0 out liability
        # balance
        (DED, 'GCard Repayment', '<p>Collection for personal charges on a '
         'GCard</p>',
         ("Liabilities", "Google GCard"), None, NONNEG),

        (TAX, 'Employee Medicare', '',
         ("Expenses", "Taxes", "Medicare"), None, NONNEG),

        (TAX, 'Federal Income Tax', '',
         ("Expenses", "Taxes", "Federal"), None, NONNEG),

        (TAX, 'New York R', '<p>New York R City Tax</p>',
         ("Expenses", "Taxes", "NYC Resident"), None, NONNEG),

        (TAX, 'NY Disability Employee', '<p>New York Disability</p>',
         ("Expenses", "Taxes", "NY State Disability Insurance (SDI)"), None,
         NONNEG),

        (TAX, 'NY State Income Tax', '<p>New York State Income Tax</p>',
         ("Expenses", "Taxes", "NY State Income"), None, NONNEG),

        (TAX, 'Social Security Employee Tax', '',
         ("Expenses", "Taxes", "Social Security"), None, NONNEG),
    )

    def acct_type(names):
        # Verify account names begin with Google, with exceptions for
        # taxes and 401k.
        assert (names[-1].startswith("Google")
                or names[:2] == ("Expenses", "Taxes")
                or names == ("Assets", "Investments", "401K"))

        # Do the actual work.
        if names[0] == "Expenses":
            return "EXPENSE"
        if names[0] == "Income":
            return "INCOME"
        if names[0] == "Assets":
            return "BANK"
        if names[0] == "Liabilities":
            return "CREDIT"
        assert False, names

    # Create placeholder accts
    gnu.acct(("Expenses", "Subsidized"), acct_type="EXPENSE")
    gnu.acct(("Income", "Untaxed Benefits"), acct_type="INCOME")

    accts = {}
    for cat, title, desc, acct, goog_acct, flags in splits:
        assert (cat, title, desc) not in accts
        acct = gnu.acct(acct, acct_type=acct_type(acct))
        if goog_acct:
          goog_acct = gnu.acct(goog_acct, acct_type=acct_type(goog_acct))
        accts[(cat, title, desc)] = acct, goog_acct, flags

    return accts


def import_mypay_stubs(gnu, accts, stubs):
    for paydate_str, docid, netpay, splits in stubs:
        paydate = datetime.datetime.strptime(paydate_str, "%m/%d/%Y").date()
        description = "Google Document {} Net Pay ${:,}.{:02}".format(
            docid, netpay // 100, netpay % 100)

        closest_offset = None
        if netpay:
            c = gnu.conn.cursor()
            c.execute("SELECT s.guid, t.guid, t.post_date, t.description "
                      "FROM splits AS s "
                      "INNER JOIN transactions AS t ON (t.guid = s.tx_guid) "
                      "WHERE s.account_guid = ? AND s.value_num = ?",
                      (gnu.checking_acct, netpay))
            for sguid, tguid, post_date_str, desc in c.fetchall():
                post_date = gnu.date(post_date_str)
                offset = abs((post_date - paydate).days)
                if (closest_offset is None or offset < closest_offset):
                    closest_offset = offset
                    closest_split = sguid
                    closest_txn = tguid
                    closest_desc = desc

        if closest_offset is None:
            assert not netpay
            txn_guid = gnu.guid()
            gnu.insert("transactions",
                        (("guid", txn_guid),
                        ("currency_guid", gnu.commodity_usd),
                        ("num", ""),
                        ("post_date", gnu.date_str(paydate)),
                        ("enter_date", gnu.date_str(paydate)),
                        ("description", description)))
        else:
            assert (closest_desc in ("Google 0", "Google 1",
                                     "Google Bonus", "Google")
                    or closest_desc.startswith("Deposit: Google Inc       "
                                               "Payroll                    "
                                               "PPD ID: "))
            assert closest_offset < 7
            txn_guid = closest_txn
            gnu.update("transactions", "guid", txn_guid,
                       (("post_date", gnu.date_str(paydate)),
                        ("enter_date", gnu.date_str(paydate)),
                        ("description", description)))

            delete_splits = []
            c.execute("SELECT guid, tx_guid, account_guid, memo, action, "
                      "    reconcile_state, reconcile_date, value_num, "
                      "    value_denom, quantity_num, quantity_denom, lot_guid "
                      "FROM splits WHERE tx_guid = ?", (txn_guid,))
            for (guid, tx_guid, account_guid, memo, action, reconcile_state,
                 reconcile_date, value_num, value_denom, quantity_num,
                 quantity_denom, lot_guid) in c.fetchall():
                if guid == closest_split:
                    continue
                assert action == ""
                assert memo in ("", 'Federal Income Tax', 'Employee Medicare',
                                'Social Security E', 'NY State Income T',
                                'New York R', 'NY Disability Emp', 'Dental',
                                'Medical', 'Pretax 401 Flat', 'Vision',
                                'Group Term Life', 'Regular', 'Gym Deduction',
                                'Taxable Gym Reim', 'Annual Bonus',
                                'Med Dent Vis', 'Vacation Pay', '401K Pretax',
                                'Social Security', 'NY State Income'), memo
                assert reconcile_state == "n"
                assert reconcile_date is None
                assert lot_guid is None
                delete_splits.append(guid)

            c.execute("DELETE FROM splits WHERE guid IN ({})".format(
                ",".join("?" for _ in delete_splits)), (delete_splits))
            assert c.rowcount == len(delete_splits)

        for cat, (title, desc), details, amount, goog_amount in splits:
            acct, goog_acct, flags = accts[cat, title, desc]
            assert flags & NONNEG == 0 or amount >= 0
            assert flags & NONPOS == 0 or amount <= 0
            assert flags & GOOG_ONLY == 0 or amount == 0
            assert flags & NONNEG == 0 or goog_amount >= 0
            assert flags & NONPOS == 0 or goog_amount <= 0
            assert goog_acct or goog_amount == 0
            assert amount or goog_amount

            if cat == PAY:
                amount *= -1

            if amount:
                memo = "{}: {}{}".format(cat, title, details)
                gnu.new_split(txn_guid, acct, amount, memo)

            if goog_amount:
                assert cat == DED
                memo = "Employer contribution: {}{}".format(title, details)
                gnu.new_split(txn_guid, goog_acct, -goog_amount, memo)
                memo = "Employer deduction: {}{}".format(title, details)
                gnu.new_split(txn_guid, acct, goog_amount, memo)


#
# Mypay html parsing functions.
#

def print_mypay_html(html_filename):
    for paydate_str, docid, netpay, splits in parse_mypay_html(html_filename):
        print(paydate_str, docid, netpay)
        for cat, label, details, amount in splits:
            print("  {}: {}{} -- {}".format(cat, label, details, amount))


def parse_mypay_html(filename):
    pay = etree.parse(filename, etree.HTMLParser())
    stubs = []
    for check in CSSSelector('.payStatement')(pay):
        assert len(check) == 1
        tbody = check[0]
        assert tbody.tag == "tbody"

        if len(tbody) == 10:
            # delete extra company logo column in newer html file
            assert len(tbody[1]) == 1 # logo
            assert tbody[1][0].attrib["colspan"] == "5"
            assert tbody[1][0][0].tag == "img"
            del tbody[1:2]

        assert len(tbody) == 9
        assert len(tbody[0]) == 5 # blank columns

        assert len(tbody[1]) == 1 # logo
        assert tbody[1][0].attrib["colspan"] == "5"
        assert tbody[1][0][-1].attrib["id"] == "companyLogo"

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

        assert len(tbody[5]) == 2
        assert tbody[5][0].attrib["colspan"] == "2"
        assert tbody[5][0].attrib["rowspan"] == "2"
        assert tbody[5][0][0][0].text == "Earnings"
        total = 0
        splits = []
        for label, details, current, goog_current in tab(tbody[5][0], docid, PAY):
            current = parse_price(current, True)
            goog_current = parse_price(goog_current, True)
            total += current
            splits.append((PAY, label, details, current, goog_current))

        assert tbody[5][1].attrib["colspan"] == "3"
        assert tbody[5][1][0][0].text == "Deductions"
        for label, details, current, goog_current in tab(tbody[5][1], docid, DED):
            current = parse_price(current, True)
            goog_current = parse_price(goog_current, True)
            total -= current
            splits.append((DED, label, details, current, goog_current))

        assert len(tbody[6]) == 1
        assert tbody[6][0].attrib["colspan"] == "3"
        assert tbody[6][0][0][0].text == "Taxes"
        for label, details, current, goog_current in tab(tbody[6][0], docid, TAX):
            current = parse_price(current, True)
            goog_current = parse_price(goog_current, True)
            total -= current
            splits.append((TAX, label, details, current, goog_current))

        stubs.append((paydate, docid, netpay, splits))

        assert total == netpay, (total, netpay)
        assert len(tbody[8]) == 1
        assert tbody[8][0][0][0].text == "Pay summary"

    return stubs

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
                title = bodycol[0].attrib["data-title"]
                title2 = bodycol[0].text.strip()
                assert title == title2
                desc = bodycol[0].attrib["data-content"]
                bodycols.append((title, desc))
            else:
                assert len(bodycol) == 0
                bodycols.append(bodycol.text)
        details = ""
        goog_current = "$0.00"
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
            assert garbage == "\xa0"
        else:
            assert table_type == TAX
            label, income, current, ytd, garbage = bodycols
            income_val = parse_price(income)
            current_val = parse_price(current)
            if income_val == 0:
                details += " (based on {})".format(income)
            else:
                details += " ({:.3f}% × {})".format(current_val / income_val * 100.0, income)
            assert garbage == "\xa0"
        if current != "$0.00" or goog_current != "$0.00":
          yield label, details, current, goog_current


#
# General utility functions.
#

def parse_price(price_str, allow_negative=False, allow_minus=False):
    price = 1
    if allow_negative and price_str[0] == "(" and price_str[-1] == ")":
        price *= -1
        price_str = price_str[1:-1]
    if allow_minus and price_str[0] == "-":
        price *= -1
        price_str = price_str[1:]
    if price_str[0] == "$":
        price_str = price_str[1:]
    dollars, cents = re.match(r"^([0-9,]+)\.([0-9]{2})$", price_str).groups()
    price *= int(cents) + 100 * int(dollars.replace(",", ""))
    return price


def s(elem):
    return etree.tostring(elem, pretty_print=True).decode()


def check(condition, message=""):
    if not condition:
        raise Exception(message)


#
# Enums and constants.
#

# Mypay account flags.
NONNEG = 1
NONPOS = 2
GOOG_ONLY = 4

# Mypay split types.
PAY = "Pay"
DED = "Deduction"
TAX = "Tax"

# Pdf versions.
Pdf = IntEnum("Pdf", "V2005_10 V2006_09 V2006_10 V2007_02 V2007_07 V2007_08 "
              "V2007_09 V2008_04 V2011_09")


#
# Class types.
#

TextFragment = namedtuple("TextFragment", "pageno y x ord text")

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
        assert pos < len(self.cache), "Can't peek after last sequence element."
        return self.cache[pos]

    def at_end(self):
        assert self.lookahead > 0, \
            "at_end method only available with lookahead > 0"
        return self.prev_elems >= len(self.cache)

    def at_start(self):
        assert self.lookbehind > 0, \
            "at_start method only available with lookbehind > 0"
        return self.prev_elems == 0


class CsvRow:
    """Wrapper for accessing csv rows with many columns."""
    def __init__(self, row, field_idx):
        self.row = row
        self.field_idx = field_idx

    def __getattr__(self, field):
        return self.row[self.field_idx[field]]

    @classmethod
    def wrap(cls, row_seq, field_idx):
        for row in row_seq:
            yield cls(row, field_idx)


class GnuCash:
    def __init__(self, conn, seed):
        self.random = random.Random()
        self.random.seed(seed)
        self.force_guids = []

        self.conn = conn
        self.conn.isolation_level = None
        self.conn.cursor().execute("BEGIN")
        self.commodity_usd = self.currency("USD")
        self.opening_acct = self.acct(("Equity", "Opening Balances"))
        self.imbalance_acct = self.acct(("Imbalance-USD",))
        self.expense_acct = self.acct(("Expenses",))
        self.income_acct = self.acct(("Income",))
        self.checking_acct = self.acct(("Assets", "Current Assets",
                                        "Checking Account"))
        self.citi_acct = self.acct(("Liabilities", "Citibank 6842"))
        self.citi_3296 = self.acct(("Liabilities", "Citibank 3296"))
        self.paypal_acct = self.acct(( "Assets", "Current Assets", "Paypal"))
        self.bank_accts = [self.checking_acct, self.citi_acct, self.citi_3296,
                           self.acct(("Liabilities", "Chase")),
                           self.acct(("Liabilities", "Citibank 7969"))]
        self.cash_acct = self.acct(("Assets", "Current Assets", "Cash"))

    def commit(self):
        self.conn.cursor().execute("COMMIT")
        del self.conn

    def insert(self, table, vals):
        c = self.conn.cursor()
        s = "INSERT INTO {} ({}) VALUES ({})".format(
            table,
            ",".join(k for k, v in vals),
            ",".join("?" for k, v, in vals))
        c.execute(s, tuple(v for k, v in vals))

    def update(self, table, id_col, id_val, vals):
        c = self.conn.cursor()
        s = "UPDATE {} SET {} WHERE {} = ?".format(
            table,
            ",".join("{} = ?".format(k) for k, v in vals),
            id_col)
        c.execute(s, tuple(v for k, v in vals) + (id_val,))
        assert c.rowcount == 1

    def guid(self):
        if self.force_guids: return self.force_guids.pop()
        return '%032x' % self.random.randrange(16**32)

    def acct(self, names, acct_type=None, create_parents=False):
        c = self.conn.cursor()
        c.execute("SELECT guid FROM accounts "
                  "WHERE name = ? AND parent_guid IS NULL",
                  ("Root Account",))
        rows = c.fetchall()
        assert len(rows) == 1
        guid, = rows[0]

        it = PeekIterator(names, lookahead=1)
        for name in it:
            c.execute("SELECT guid FROM accounts "
                      "WHERE name = ? AND parent_guid = ?", (name, guid))
            rows = c.fetchall()
            if len(rows) == 1:
                guid, = rows[0]
                continue

            assert len(rows) == 0
            assert acct_type is not None
            assert it.at_end() or create_parents, names
            guid = self.new_acct(guid, name, acct_type)

        return guid

    def currency(self, mnemonic):
        c = self.conn.cursor()
        c.execute("SELECT guid FROM commodities WHERE mnemonic = ?",
                  (mnemonic,))
        rows = c.fetchall()
        assert len(rows) == 1
        guid, = rows[0]
        return guid

    def new_acct(self, parent_guid, name, acct_type="ASSET"):
        guid = self.guid()
        self.insert("accounts",
                    (("guid", guid),
                     ("name", name),
                     ("account_type", acct_type),
                     ("commodity_guid", self.commodity_usd),
                     ("commodity_scu", 100),
                     ("non_std_scu", 0),
                     ("parent_guid", parent_guid),
                     ("code", ""),
                     ("description", ""),
                     ("hidden", 0),
                     ("placeholder", 0)))
        return guid

    def new_txn(self, date, desc, memo, acct, amount, src_acct=None,
                src_amount=None, reconcile_date=None):
        if src_amount is None:
            src_amount = -amount
        if src_acct is None:
            src_acct = self.income_acct if src_amount < 0 else self.expense_acct

        txn_guid = self.guid()

        self.insert("transactions",
                    (("guid", txn_guid),
                     ("currency_guid", self.commodity_usd),
                     ("num", ""),
                     ("post_date", self.date_str(date)),
                     ("enter_date", self.date_str(date)),
                     ("description", description if desc is None else desc)))

        src_split = dict(txn_guid=txn_guid,
                         acct=src_acct,
                         amount=src_amount,
                         memo="")

        dst_split = dict(txn_guid=txn_guid,
                         acct=acct,
                         amount=amount,
                         memo=memo,
                         action=self.yearless_date_str(date),
                         reconcile_date=reconcile_date)

        if src_amount == 0:
            dst_guid = self.new_split(**dst_split)
        elif src_amount > 0:
            # Reverse next two guids for test.sh backwards compatibility.
            self.force_guids.extend((self.guid(), self.guid()))
            dst_guid = self.new_split(**dst_split)
            src_guid = self.new_split(**src_split)
        else:
            src_guid = self.new_split(**src_split)
            dst_guid = self.new_split(**dst_split)
        return txn_guid, dst_guid

    def new_split(self, txn_guid, acct, amount, memo, action="",
                  reconcile_date=None):
        split_guid = self.guid()
        self.insert("splits",
                    (("guid", split_guid),
                      ("tx_guid", txn_guid),
                      ("account_guid", acct),
                      ("memo", memo),
                      ("action", action),
                      ("reconcile_state", "y" if reconcile_date else "n"),
                      ("reconcile_date", self.date_str(reconcile_date)
                       if reconcile_date else None),
                      ("value_num", amount),
                      ("value_denom", 100),
                      ("quantity_num", amount),
                      ("quantity_denom", 100),
                      ("lot_guid", None)))
        return split_guid

    def update_split(self, split_guid, action=None, memo=None, memo_tstr=None,
                     reconcile_date=None, remove_txn_suffix=None, amount=None,
                     txn=None):
        fields = []

        if action is not None:
            fields.append(("action", action))

        if memo is not None:
            assert memo_tstr is None
            fields.append(("memo", memo))

        if memo_tstr is not None:
            fields.append(("memo", memo_tstr.as_string()))

            # Update transaction description with new memo, if
            # previous transaction description contained a copy of the
            # previous memo.
            c = self.conn.cursor()
            c.execute("SELECT s.memo, t.guid, t.description "
                      "FROM splits AS s "
                      "INNER JOIN transactions AS t ON (t.guid = s.tx_guid) "
                      "WHERE s.guid = ?", (split_guid,))
            rows = list(c.fetchall())
            assert len(rows) == 1
            prev_memo, txn_guid, txn_desc = rows[0]
            if prev_memo:
                if remove_txn_suffix is None:
                    remove_txn_suffix = memo_tstr.__class__.parse(
                        prev_memo).as_string(tags=False)
                if remove_txn_suffix and txn_desc.endswith(remove_txn_suffix):
                    self.update("transactions", "guid", txn_guid,
                        (("description", txn_desc[:-len(remove_txn_suffix)]
                                         + memo_tstr.as_string(tags=False)),))
        else:
            assert remove_txn_suffix is None

        if amount is not None:
            fields.append(("value_num", amount))

        if reconcile_date is not None:
            if reconcile_date:
                fields.append(("reconcile_state", "y"))
                fields.append(("reconcile_date", self.date_str(reconcile_date)))
            else:
                fields.append(("reconcile_state", "n"))
                fields.append(("reconcile_date", None))

        if txn is not None:
            fields.append(("tx_guid", txn))

        self.update("splits", "guid", split_guid, fields)

    def balance_txn(self, txn_guid):
        c = self.conn.cursor()
        c.execute("SELECT guid, account_guid, value_num "
                  "FROM splits WHERE tx_guid = ?", (txn_guid,))
        value_sum = 0
        imbalance_split = None
        imbalance_value = None
        for guid, account_guid, value_num in c.fetchall():
            value_sum += value_num
            if account_guid == self.imbalance_acct and imbalance_split is None:
                check(imbalance_split is None)
                imbalance_split = guid
                imbalance_value = value_num
        if value_sum != 0:
            if imbalance_split is None:
                self.new_split(txn_guid, self.imbalance_acct, -value_sum, "")
            else:
                self.update_split(imbalance_split,
                                  amount=imbalance_value - value_sum)

    def find_matching_txn(self, acct, date, amount, memo_tstr, ignore_splits):
        """Find transaction with a split having exact or near exact matching
        account, date, action, and memo information."""

        # Start looking for any splits that have matching dates and
        # amounts. Both are ambiguous, especially dates since dates
        # stored in the action column are yearless.
        action = self.yearless_date_str(date)
        c = self.conn.cursor()
        c.execute("SELECT s.guid, s.memo, t.post_date "
                  "FROM splits AS s "
                  "INNER JOIN transactions AS t ON (t.guid = s.tx_guid) "
                  "WHERE s.account_guid = ? AND s.value_num = ? "
                  "    AND s.action = ?", (acct, amount, action))

        # Go through returned splits discarding any that aren't from
        # the right year or have incompatible memo strings where
        # merge_from returns false or are in ignored_splits. Save the
        # best possible match as "match" to be returned later,
        # generally choosing the first match but prefering later
        # matches if they don't have the mismatched_date_property.
        match = None
        no_exact_date = True
        debug_matches = []
        for split_guid, split_memo, txn_post_date_str in c.fetchall():
            txn_post_date = self.date(txn_post_date_str)
            if self.yearless_date(action, txn_post_date) != date:
                continue
            merged_tstr = memo_tstr.__class__.parse(split_memo)
            if not merged_tstr.merge_from(memo_tstr):
                continue

            # It's useful to in see splits in debug_matches even if
            # they wouldn't actually be returned because their guids
            # are in ignore_splits.
            debug_matches.append((split_guid, split_memo, merged_tstr))

            if split_guid not in ignore_splits:
                has_mismatched_date = merged_tstr.has_mismatched_date()
                if (match is None
                    or (no_exact_date and not has_mismatched_date)):
                    match = split_guid, merged_tstr
                    no_exact_date = has_mismatched_date

        # Print warnings if this case is ambiguous.
        if len(debug_matches) > 1:
            print(80 * "-", file=sys.stderr)
            print("Warning imported txn matches multiple existing txns: "
                  "{} {} {!r}".format(date, amount, memo_tstr.as_string()),
                  file=sys.stderr)
            for split_guid, split_memo, merged_tstr in debug_matches:
                tags = []
                if match and split_guid == match[0]:
                    tags.append("selected")
                if merged_tstr.has_mismatched_date():
                    tags.append("baddate")
                tag_str = "[{}]".format(",".join(tags)) if tags else ""
                print("    {} {:10} {!r}".format(
                    split_guid[:8], tag_str, split_memo, file=sys.stderr))

        return match

    def find_closest_txn(self, accts, date, amount, no_action=False,
                         no_split=None, max_days=10):
        """Find transaction with a split matching the amount and acct and
        having a close date."""

        c = self.conn.cursor()
        c.execute("SELECT s.guid, s.memo, t.guid, t.post_date "
                  "FROM splits AS s "
                  "INNER JOIN transactions AS t ON (t.guid = s.tx_guid) "
                  "WHERE s.value_num = ? "
                  + (" AND s.account_guid IN (" + ",".join("?" for _ in accts)
                     + ") " if accts else "")
                  + (" AND s.action = ''" if no_action else "")
                  + (" AND NOT EXISTS(SELECT * FROM splits AS s2 "
                     "WHERE s2.tx_guid = s.tx_guid AND s2.account_guid = ? "
                     "AND s2.action <> '')" if no_split else ""),
               (amount,) + tuple(accts) + ((no_split,) if no_split else ()))

        match = None
        closest_offset = None
        for split_guid, split_memo, txn_guid, txn_post_date_str in c.fetchall():
            txn_post_date = self.date(txn_post_date_str)
            offset = abs((txn_post_date - date).days)
            if offset < max_days and (closest_offset is None
                                      or offset < closest_offset):
                match = split_guid, split_memo, txn_guid, txn_post_date
                closest_offset = offset

        return match

    def acct_map(self, full=False):
        acct_map = {}
        c = self.conn.cursor()
        if full:
            sql = """
                WITH RECURSIVE
                    r(guid, name) AS (
                        SELECT guid, name
                            FROM accounts
                            WHERE parent_guid = (
                               SELECT guid FROM accounts
                               WHERE name = 'Root Account')
                        UNION ALL
                        SELECT accounts.guid, r.name || ': ' || accounts.name
                            FROM r
                            JOIN accounts ON (accounts.parent_guid = r.guid)
                    )
                SELECT guid, name FROM r;
            """
        else:
            sql = "SELECT guid, name FROM accounts"
        c.execute(sql)
        for guid, name in c.fetchall():
            acct_map[guid] = name
        return acct_map

    def print_txns(self, header, split_filter):
        acct_map = self.acct_map(True)

        c = self.conn.cursor()
        c.execute("SELECT guid, post_date, description FROM transactions "
                  "ORDER BY post_date, rowid")
        for guid, post_date_str, description in c.fetchall():
            post_date = self.date(post_date_str)

            d = self.conn.cursor()
            d.execute("SELECT guid, account_guid, memo, action, value_num, "
                      "reconcile_state "
                      "FROM splits WHERE tx_guid = ? ORDER BY rowid", (guid,))

            found_split = False
            splits = []
            for split_guid, account, memo, action, value, reconcile_state in \
                d.fetchall():
                splits.append((split_guid, account, memo, action, value))
                if split_filter(txn_guid=guid, split_guid=split_guid,
                                account=account, desc=description,
                                memo=memo, action=action, value=value,
                                reconcile_state=reconcile_state,
                                post_date=post_date,
                                action_date=self.yearless_date(
                                    action, post_date)):
                    found_split = True

            if found_split:
                if header:
                    print(header)
                    header = None
                print(post_date, guid[:7], description)
                for split, account, memo, action, value in splits:
                  print(" {:9.2f} {} {}{}{}{}{}".format(
                      value/100.0, split[:7], acct_map.get(account, account),
                      action and "--", action,
                      memo and " -- ", memo))

    @staticmethod
    def date(date_str):
        """Convert gnucash date string to python date.

        Gnucash date string for a date bizarrely is the UTC timestemp
        of the moment when it is 00:00:00 in the LOCAL timezone. If
        you give gnucash the timestamp of the moment when it is
        00:00:00 in the UTC timezone, gnucash will display the
        previous day's date in the UI (in any timezone where clocks
        are set earlier than the current UTC time.)

        GnuCash date strings are used in transactions.post_date,
        transactions.enter_date, and splits.reconcile_date fields.

        The transaction.post_date field is always preserved and never
        overrwritten by import code in this file. This way manually
        entered transaction dates get more prominence over imported
        electronic dates in the gnucash UI, since elecronic dates can
        lag behind actual transactions by a day or more.  While the
        post_date field is not overwritten, post dates are used to
        help interpret yearless dates in other fields.

        The transactions.entered_date field also is never overwritten by
        import code in this file. The field isn't displayed in the
        gnucash either.

        The splits.reconcile_date field will be overwritten with the
        statement date when the merge_txns reconcile date option
        is set.

        Aside from the dates above stored in gnucash format, the
        import code here also records other dates as freeform text in
        split.action and split.memo fields.

        The split.action field is used to the main upstream date from
        chase or paypal associated with the transaction.

        The split.memo field can hold various other dates in freeform
        text format, see ChaseStr and PaypalStr classes for details.
        """
        return datetime.datetime.fromtimestamp(
            datetime.datetime.strptime(date_str, "%Y%m%d%H%M%S")
            .replace(tzinfo=datetime.timezone.utc).timestamp()).date()

    @staticmethod
    def date_str(date):
        """Convert python date to gnucash date string."""
        if isinstance(date, datetime.datetime):
            date = date.date()
        return datetime.datetime.utcfromtimestamp(
            time.mktime(date.timetuple())).strftime("%Y%m%d%H%M%S")

    @staticmethod
    def yearless_date(yearless_date_str, txn_post_date):
        """Convert yearless date string to python date."""
        m = re.match(r"^(\d{2})/(\d{2})$", yearless_date_str)
        if not m:
            return
        month, day = map(int, m.groups())
        date = datetime.date(txn_post_date.year, month, day)
        offset = (txn_post_date - date).days
        if offset > 180:
            date = datetime.date(txn_post_date.year + 1, month, day)
        elif offset < -180:
            date = datetime.date(txn_post_date.year - 1, month, day)
        assert abs((txn_post_date - date).days) < 180, (date, txn_post_date)
        return date

    @staticmethod
    def yearless_date_str(yearless_date, txn_post_date=None):
        """Convert python datetime to gnucash date string."""
        if txn_post_date is not None:
            assert abs((txn_post_date - yearless_date).days) < 180, (
                "Yearless date {} is too far away from post date {} to be "
                "represented in MM/DD format.".format(
                    yearless_date, txn_post_date))
        return yearless_date.strftime("%m/%d")


class TaggedStr:
    """Tagged string parser/formatter.

    Hacky but could be improved without affecting other code if ever needed."""

    def __init__(self):
        self.lines = []
        self.tags = OrderedDict(self.allowed_tags)

    def tag(self, tag):
        return self.tags[tag]

    def set_tag(self, tag, value):
        assert tag in self.tags
        self.tags[tag] = value

    def merge_tags(self, other):
        for tag, value in other.tags.items():
            if value:
                if not self.tags[tag]:
                    self.tags[tag] = value
                elif self.tags[tag] != value:
                    return False
        return True

    def as_string(self, tags=True):
        line_str = self._lines_str(self.lines)
        if not tags:
            return line_str.rstrip()

        tag_str = []
        for tag, value in self.tags.items():
            assert re.match("^[a-z0-9-]+$", tag), tag
            if value == True:
                tag_str.append(tag)
            elif value != False and value is not None:
                line = self._lines_str(value)
                if re.search(r'[ ",\\]', line):
                    tag_str.append('{}="{}"'.format(
                        tag, line.replace('"', r'\"')))
                else:
                    tag_str.append('{}={}'.format(tag, line))

        return "{} [{}]".format(line_str, ", ".join(tag_str))

    def merge_from(self, other):
        return self.tags == other.tags and self.lines == other.lines

    def has_mismatched_date(self):
        return False

    @classmethod
    def parse(cls, string, check_tags=True):
        m = re.match(r"^(.*?) \[(.*?)\]$", string)
        if not m:
            return
        textstr, tagstr = m.groups()

        ret = cls()
        ret.lines.extend(cls._parse_lines(textstr))

        pos = 0
        while pos < len(tagstr):
            m = (re.compile('([A-Za-z0-9-]+)'
                            '(?:=(?:([^",]*)|"((?:[^"]|\\\\")*)"))?(?:$|, )')
                 .match(tagstr, pos))
            assert m.end() > pos
            pos = m.end()
            tag, value, quoted_value = m.groups()
            if quoted_value is not None:
                assert value is None
                value = quoted_value

            if check_tags and tag not in ret.tags:
                return
            if value is None:
                ret.tags[tag] = True
            else:
                ret.tags[tag] = cls._parse_lines(value)
        return ret

    @staticmethod
    def _lines_str(lines):
        return " || ".join(re.sub(r"([[\]\\|])", r"\\\1", line)
                           for line in lines)

    @staticmethod
    def _parse_lines(lines_str):
        lines = [""]
        pos = 0
        while pos < len(lines_str):
            m = re.compile(r"\\(.)| \|\| ").search(lines_str, pos)
            if m:
                lines[-1] += lines_str[pos:m.start()]
                if m.group(1) is not None:
                    lines[-1] += m.group(1)
                else:
                    lines.append("")
                pos = m.end()
            else:
                lines[-1] += lines_str[pos:]
                pos = len(lines_str)
        return lines

    allowed_tags = ()


class ChaseStr(TaggedStr):
    """Tagged string class for chase checking memo field"""

    allowed_tags = (
        # Whether string includes information pdf or csv or both.
        ("pdf", False),
        ("csv", False),
        # Card number from 'Card 9651' or 'Card 8636' pdf boilerplate
        ("card", None),
        # Reference number and date from '375369  03/18' csv boilerplate
        ("ref", None),
        ("date", None),
    )

    @classmethod
    def parse_pdf_string(cls, lines):
        for line in lines:
            assert re.match("^[A-Za-z0-9 #$%&'()*+,./:;@_`-]*$", line), line
        line = "\n".join(lines)

        tstr = cls()
        tstr.set_tag("pdf", True)

        m = re.compile(r"^(.*?)[ \n]+C(?:ard|ARD)[ \n]+(\d{4}) *(\n.*)?$",
                       re.DOTALL).match(line)
        if m:
            prefix, card, suffix = m.groups()
            tstr.set_tag("card", [card])
            line = prefix + (suffix or "")

        # Unused PDF patterns. Could extract if interesting.
        #     r"^Card Purchase           (\d{2}/\d{2}) "
        #     r"^Card Purchase With Pin  (\d{2}/\d{2}) "
        #     r"^Recurring Card Purchase (\d{2}/\d{2}) "

        tstr.lines.extend(line.split("\n"))
        return tstr

    @classmethod
    def parse_csv_string(cls, line):
        assert re.match("^[A-Za-z0-9 #$&'()*+,./:_-]*$", line), line

        tstr = cls()
        tstr.set_tag("csv", True)

        m = re.match(r"^(.{37})(\d{6})  (\d{2}/\d{2})(.*)$", line)
        if m:
            prefix, ref, date, suffix = m.groups()
            tstr.set_tag("date", [date])
            tstr.set_tag("ref", [ref])
            tstr.lines.append(prefix.rstrip())
            if suffix:
                tstr.lines.append(suffix)
        else:
            m = re.match(r"^(.{45})(\d{2}/\d{2})(.*)$", line)
            if m:
                prefix, date, suffix = m.groups()
                tstr.set_tag("date", [date])
                tstr.lines.append(prefix.rstrip())
                if suffix:
                    tstr.lines.append(suffix)
            else:
                m = re.match(r"^(.*?) (\d{2}/\d{2})$", line)
                if m:
                    prefix, date = m.groups()
                    tstr.set_tag("date", [date])
                    tstr.lines.append(prefix)
                else:
                    tstr.lines.append(line)

        return tstr

    def merge_from(self, other):
        if self.tag("pdf") == other.tag("pdf"):
            if not self.lines == other.lines:
                return False
        else:
            if self.tag("pdf"):
                pdf_lines = self.lines
                csv_lines = other.lines
            else:
                pdf_lines = other.lines
                csv_lines = self.lines
                # Overwrite csv string with pdf string
                self.lines = pdf_lines

            # Make sure pdf string is superset of csv string
            csv_segments = []
            for csv_line in csv_lines:
                m = re.compile("^(.*?)(MX Nu Peso)(.*)$", re.I).match(csv_line)
                if m:
                    csv_segments.extend(m.groups())
                    continue
                m = re.match("^(DEPOSIT)  ID NUMBER (\d+)$", csv_line)
                if m:
                    csv_segments.extend(m.groups())
                    continue
                csv_segments.append(csv_line)

            pdf_line = re.sub(" +", " ", " ".join(pdf_lines).lower())
            for csv_segment in csv_segments:
                csv_segment = re.sub(" +", " ", csv_segment.lower()).strip()
                if csv_segment not in pdf_line:
                    return False

        return self.merge_tags(other)

    def has_mismatched_date(self):
        """Check if CSV date doesn't match PDF date.

        CSV dates are extracted into "date" tag since they show up in
        a consistent format and are also difficult to read in the
        original CSV string (sometimes) glommed before subsequent text
        without even a space separating.

        PDF dates are not extracted because they show up in
        inconsistent formats (card, card with pin, recurring card, ATM
        withdrawal, online payment) so extraction is harder, and also
        not worth anything since original text is already readable.

        Mismatches between the two dates can occur in two cases:

        (1) Apparently very rare case where chase simply returns
            different dates for the the same transaction. Only saw two
            case of this: a 2015-07-27 online payment, and an
            2014-08-11 cash withdrawal (quarters for laundry).

        (2) Transient cases where CSV importing code looking for
            matching gnucash transactions encounters multiple
            transactions with exact same descriptions and post dates,
            but different text dates. The CSV import code calls this
            function to detect these cases and prefer the matches with
            identical dates. In this case the ChaseStr objects with
            mixed dates are only temporary and are never actually
            stored to the database.
        """
        pdf_dates = set(date
                        for line in self.lines
                        for date in re.findall(r"\b\d{2}/\d{2}\b", line))
        csv_dates = self.tag("date")
        return (pdf_dates and csv_dates
                and any(csv_date not in pdf_dates for csv_date in csv_dates))


class CitiStr(TaggedStr):
    """Tagged string class for citicard memo field"""

    allowed_tags = (
        # Whether string includes information from tsv file.
        ("tsv", False),
    )
