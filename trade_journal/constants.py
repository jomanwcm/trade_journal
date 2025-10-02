# constants.py — line-by-line annotated walkthrough
# (Domain data and table layout used by the app)

from collections import OrderedDict  # not strictly needed here; safe to remove if unused
from pathlib import Path
import json

# Preset button labels for each category. Strings with "()" are templates that
# will prompt the user for a one-shot detail (e.g., "Decent bull bar(inside)").
BULL_POINTS_DEFAULT = [
    "above EMA", "DB()", "Decent bull leg()", "Decent bull bar()",
    "連續bull bar()", "Bad follow after bear bar",
    "未穿 50% PB", "升穿 50% PB"
]

BEAR_POINTS_DEFAULT = [
    "below EMA", "DT()", "Decent bear leg()",
    "Decent bear bar()", "連續bear bar()", "Bad follow after bull",
    "未穿 50% PB", "跌穿 50% PB"
]

TR_POINTS_DEFAULT = [
    "strongly overlap()", "moderately overlap()",
    "ii()", "ioi()", "ioii()", "iii()"
]

BIAS_POINTS_DEFAULT = [
    "Bullish", "Bullish/TR", "TR", "Bearish/TR", "Bearish"
]

def _load_project_presets():
    """
    Try to load presets.json from project-relative locations:
    1) same folder as constants.py
    2) repo root (one level up)
    Falls back to *_DEFAULT lists on any error.
    """
    base_dir = Path(__file__).resolve().parent
    candidates = [
        base_dir / "presets.json",
        base_dir.parent / "presets.json",
    ]

    for path in candidates:
        try:
            if path.is_file():
                with path.open("r", encoding="utf-8") as f:
                    data = json.load(f)

                # defensive normalization
                def _norm(key, fallback):
                    v = data.get(key, fallback)
                    if not isinstance(v, list):
                        return fallback
                    return [str(x) for x in v]

                return (
                    _norm("bull", BULL_POINTS_DEFAULT),
                    _norm("bear", BEAR_POINTS_DEFAULT),
                    _norm("tr",   TR_POINTS_DEFAULT),
                    _norm("bias", BIAS_POINTS_DEFAULT),
                )
        except Exception:
            # any parse or IO error -> ignore and try next candidate / fallback
            pass

    # fallback to baked-in defaults
    return (
        BULL_POINTS_DEFAULT,
        BEAR_POINTS_DEFAULT,
        TR_POINTS_DEFAULT,
        BIAS_POINTS_DEFAULT,
    )


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

# ---------------------------
# Public names used everywhere else
# ---------------------------
BULL_POINTS, BEAR_POINTS, TR_POINTS, BIAS_POINTS = _load_project_presets()