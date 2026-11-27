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
    """Streamed: a 3 MB spreadsheet's string table as a full tree once took a
    web worker's memory (PM-108)."""
    try:
        info = z.getinfo("xl/sharedStrings.xml")
    except KeyError:
        return []
    out = []
    si_tag, t_tag = f"{{{NS['m']}}}si", f"{{{NS['m']}}}t"
    with z.open(info) as fh:
        for _event, node in ET.iterparse(fh, events=("end",)):
            if node.tag == si_tag:
                out.append("".join(t.text or "" for t in node.iter(t_tag)))
                node.clear()
    return out


def _row_cells(row, strings):
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
    return cells


def sheets(path):
    with zipfile.ZipFile(path) as z:
        strings = _shared_strings(z)
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        targets = {rel.get("Id"): rel.get("Target") for rel in rels}
        out = {}
        row_tag = f"{{{NS['m']}}}row"
        for sheet in wb.find("m:sheets", NS):
            rid = sheet.get(f"{{{NS['r']}}}id")
            target = targets.get(rid, "")
            member = target if target.startswith("xl/") else "xl/" + target.lstrip("/")
            try:
                info = z.getinfo(member)
            except KeyError:
                continue
            rows = []
            # Streamed row by row, each row's tree dropped once read: the
            # whole sheet as one tree is what ran the server out of memory.
            with z.open(info) as fh:
                for _event, node in ET.iterparse(fh, events=("end",)):
                    if node.tag == row_tag:
                        rows.append(_row_cells(node, strings))
                        node.clear()
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
