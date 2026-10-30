"""Sizes as sliders (REQ-D3.23). The chat names its key sizes as numeric
variables at the top of the code (`wall = 2;`); a slider change writes the
new number back into a copy of the code, with no call to the model."""

import re
from decimal import Decimal, InvalidOperation

NUMBER = r"[-+]?\d+(?:\.\d+)?"


def _pattern(name):
    return re.compile(rf"^(\s*{re.escape(name)}\s*=\s*)({NUMBER})(\s*;)", re.MULTILINE)


def value_in(code, name):
    m = _pattern(name).search(code or "")
    return Decimal(m.group(2)) if m else None


def apply(code, values):
    """`values` maps a variable name to its new number; each replaces only
    the first top-level assignment of that name."""
    for name, value in values.items():
        num = format(Decimal(str(value)).normalize(), "f")
        code = _pattern(name).sub(lambda m: f"{m.group(1)}{num}{m.group(3)}", code, count=1)
    return code


def _dec(value, default=None):
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return default


def clean(proposed, code, limit=12):
    """The chat's proposed sliders, kept only when the code really has that
    variable, with a value inside a sensible range."""
    out = []
    for i, p in enumerate(proposed or []):
        if not isinstance(p, dict):
            continue
        name = str(p.get("name") or "")
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,39}", name):
            continue
        current = value_in(code, name)
        if current is None:
            continue
        lo = _dec(p.get("min"), current / 2 if current > 0 else current - 10)
        hi = _dec(p.get("max"), current * 2 if current > 0 else current + 10)
        if lo > hi:
            lo, hi = hi, lo
        lo, hi = min(lo, current), max(hi, current)
        step = _dec(p.get("step"), Decimal("1"))
        if not step or step <= 0:
            step = Decimal("1")
        out.append({"name": name, "label": str(p.get("label") or name.replace("_", " ").capitalize())[:60],
                    "value": current, "minimum": lo, "maximum": hi, "step": step,
                    "unit": str(p.get("unit") or "")[:8], "position": i,
                    "needs_measuring": p.get("measure") is True, "dim": _dim(p, current)})
        if len(out) >= limit:
            break
    return tag(out)


def _point(v):
    import math

    if not (isinstance(v, (list, tuple)) and len(v) == 3):
        return None
    try:
        pt = [round(float(c), 3) for c in v]
    except (TypeError, ValueError):
        return None
    return pt if all(math.isfinite(c) and abs(c) < 1e5 for c in pt) else None


def _dim(p, value):
    """Where a size runs on the part, from the chat: two points, or None."""
    a, b = _point(p.get("from")), _point(p.get("to"))
    if a is None or b is None or a == b:
        return None
    return {"from": a, "to": b, "at": float(value)}


def tag(params):
    """M1, M2 for sizes to measure, D1, D2 for the others, in order."""
    m = d = 0
    for p in params:
        if p.get("needs_measuring"):
            m += 1
            p["tag"] = f"M{m}"
        else:
            d += 1
            p["tag"] = f"D{d}"
    return params
