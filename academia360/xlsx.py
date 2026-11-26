"""A tiny .xlsx reader, enough for the committee's spreadsheets (openpyxl is
not in this site's requirements, and the import needs only cell text).

`sheets(path)` returns {sheet name: rows}, each row a list of cell values
(str, float or None) indexed by column, with shared strings resolved.
"""

import re
import zipfile
from xml.etree import ElementTree as ET

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
      "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}


def _col_index(ref):
    letters = re.match(r"[A-Z]+", ref).group(0)
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def _shared_strings(z):
    try:
        root = ET.fromstring(z.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    out = []
    for si in root.findall("m:si", NS):
        out.append("".join(t.text or "" for t in si.iter(f"{{{NS['m']}}}t")))
    return out


def sheets(path):
    with zipfile.ZipFile(path) as z:
        strings = _shared_strings(z)
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        targets = {rel.get("Id"): rel.get("Target") for rel in rels}
        out = {}
        for sheet in wb.find("m:sheets", NS):
            rid = sheet.get(f"{{{NS['r']}}}id")
            target = targets.get(rid, "")
            member = target if target.startswith("xl/") else "xl/" + target.lstrip("/")
            try:
                root = ET.fromstring(z.read(member))
            except KeyError:
                continue
            rows = []
            for row in root.iter(f"{{{NS['m']}}}row"):
                cells = []
                for c in row.findall("m:c", NS):
                    idx = _col_index(c.get("r", "A1"))
                    while len(cells) <= idx:
                        cells.append(None)
                    kind = c.get("t")
                    v = c.find("m:v", NS)
                    if kind == "s" and v is not None:
                        cells[idx] = strings[int(v.text)]
                    elif kind == "inlineStr":
                        cells[idx] = "".join(t.text or "" for t in c.iter(f"{{{NS['m']}}}t"))
                    elif v is not None and v.text is not None:
                        try:
                            cells[idx] = float(v.text)
                        except ValueError:
                            cells[idx] = v.text
                rows.append(cells)
            out[sheet.get("name")] = rows
        return out


def text(cell):
    if cell is None:
        return ""
    if isinstance(cell, float):
        return str(int(cell)) if cell.is_integer() else str(cell)
    return str(cell).strip()


def number(cell):
    """A number from a cell, or None: '2,000', ' 50 ', 600.0 all count."""
    if cell is None:
        return None
    if isinstance(cell, float):
        return cell
    s = str(cell).replace(",", "").replace("‏", "").strip()
    m = re.fullmatch(r"-?\d+(?:\.\d+)?", s)
    return float(m.group(0)) if m else None
