import datetime
import re
import fractions
import decimal
from collections import namedtuple


FIFO = False


class Asset:
    def __init__(self, value, name, date, comment):
        self.value = value
        self.name = name
        self.date = date
        self.comment = comment
        self.value_remaining = value
        self.replaced_by = []  # List of assets replaced by.
        self.replaces = None
        self.replaces_fraction = None  # Fraction of self.replaces value this was traded for.

    def replace(self, value, replaced_by):
        """Mark `value` portion of this asset as being replaced by (traded for) another asset."""
        self.value_remaining -= value
        assert replaced_by.replaces is None
        assert replaced_by.replaces_fraction is None
        replaced_by.replaces = self
        replaced_by.replaces_fraction = value / self.value if self.value else 1
        self.replaced_by.append(replaced_by)

    @staticmethod
    def parse(amount_str, date, comment, mult=1):
        value, name = parse_amount(amount_str)
        return Asset(value * mult, name, date, comment)


class Basis:
    def __init__(self):
        self.assets = {}  # asset name -> list of Assets

    def add_dest(self, source, source_amount, dest_str, frac, date, comment):
        dest = Asset.parse(dest_str, date, comment, frac)
        source.replace(source_amount, dest)
        assert dest.name != source.name
        self.assets.setdefault(dest.name, []).append(dest)

    def add(self, date_str, source_str, dest_str, comment=None):
        date = parse_date(date_str)
        source_value, source_name = parse_amount(source_str)
        if source_name == "usd":
            source = Asset(source_value, source_name, date, comment)
            self.add_dest(source, source_value, dest_str, 1, date, comment)
        else:
            source_needed = source_value
            assets = self.assets[source_name]
            for source in reversed(assets) if FIFO else assets:
                assert source_needed >= 0
                if not source_needed:
                    break
                assert source.value_remaining >= 0
                if not source.value_remaining:
                    continue
                source_replace = min(source_needed, source.value_remaining)
                self.add_dest(source, source_replace, dest_str, source_replace
                              / source_value, date, comment)
                source_needed -= source_replace
            assert not source_needed

    def dump(self):
        assets = [
            asset for name, assets in self.assets.items() for asset in assets
            if asset.value_remaining and asset.replaces is not None
        ]
        assets.sort(key=lambda asset: asset.date)
        for asset in assets:
            print("======== {} {:>13} {}{} ========".format(
                date_str(asset.date),
                value_str(asset.value_remaining), asset.name,
                comment_str(asset.comment)))
            basis = asset
            frac = fractions.Fraction(1)
            while basis.replaces is not None:
                frac = frac * basis.replaces_fraction
                print("         {} {:>13}, {:3.0f}% of {:>13} {}{}".format(
                    date_str(basis.replaces.date),
                    value_str(frac * basis.replaces.value),
                    float(100 * frac),
                    value_str(basis.replaces.value), basis.replaces.name,
                    comment_str(basis.replaces.comment)))
                basis = basis.replaces


def value_str(value, precision=8):
    return "{:.{}f}".format(
        decimal.Decimal(round(100000000 * value)) / decimal.Decimal(100000000),
        precision)


def parse_amount(amount_str):
    m = re.match(r"([0-9.]+) (.*)", amount_str)
    value, name = m.groups()
    return fractions.Fraction(value), (name)


def parse_date(str):
    return datetime.datetime.strptime(str, "%Y-%m-%d %H:%M:%S %z")


def date_str(date):
    return date.astimezone().isoformat()


def comment_str(str):
    return " ({})".format(str) if str else ""


def test():
    b = Basis()
    b.add("2012-01-01 12:00:00 +0000", "100.00 usd", "1000.00 coinbase")
    b.add("2012-01-02 12:00:00 +0000", "300.00 coinbase", "300.00 armory")
    b.add("2012-01-03 12:00:00 +0000", "20.00 armory", "150.0 usd",
          "purchase")
    b.add("2012-01-04 12:00:00 +0000", "280.00 armory", "279.0 coinbase")
    b.add("2012-01-05 12:00:00 +0000", "979.00 coinbase", "1000.00 usd")
    b.dump()
