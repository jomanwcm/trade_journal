# constants.py — line-by-line annotated walkthrough
# (Domain data and table layout used by the app)

from collections import OrderedDict  # not strictly needed here; safe to remove if unused

# Preset button labels for each category. Strings with "()" are templates that
# will prompt the user for a one-shot detail (e.g., "Decent bull bar(inside)").
BULL_POINTS = [
    "above EMA", "DB()", "Decent bull leg()", "Decent bull bar()",
    "連續bull bar()", "Bad follow after bear bar",
    "未穿 50% PB", "升穿 50% PB"
]

BEAR_POINTS = [
    "below EMA", "DT()", "Decent bear leg()",
    "Decent bear bar()", "連續bear bar()", "Bad follow after bull",
    "未穿 50% PB", "跌穿 50% PB"
]

TR_POINTS = [
    "strongly overlap()", "moderately overlap()",
    "ii()", "ioi()", "ioii()", "iii()"
]

BIAS_POINTS = [
    "Bullish", "Bullish/TR", "TR", "Bearish/TR", "Bearish"
]

# Column names for the tksheet header row. The order is referenced everywhere.
COLUMNS = ("Bar", "Bull", "Bear", "TR", "Bias")

# Fast lookup from column name → index (0..4).
COL_INDEX = {name: i for i, name in enumerate(COLUMNS)}

# Map from a sheet column index to the key used inside each row's data dict.
# Column 0 ("Bar") is intentionally not mapped (it doesn't store a list).
KINDS_BY_COL = {
    COL_INDEX["Bull"]: "bull",
    COL_INDEX["Bear"]: "bear",
    COL_INDEX["TR"]:   "tr",
    COL_INDEX["Bias"]: "bias",
}

# Fixed order of rows in a session: two labels + integers 1..81.
BAR_ORDER = ["RTH", "ETH"] + list(range(1, 82))
