"""Round-trip between .xls (xlrd/xlwt) and Luckysheet's JSON workbook format."""
import os

import xlrd
import xlwt


def xls_to_luckysheet(xls_path: str) -> list:
    """Read an .xls workbook and return Luckysheet-consumable sheet dicts.

    Cell shape: {"r": row_index, "c": col_index, "v": {"v": raw, "m": display}}.
    Empty cells are omitted so downstream JSON stays compact.
    """
    wb = xlrd.open_workbook(xls_path)
    sheets = []
    for i in range(wb.nsheets):
        ws = wb.sheet_by_index(i)
        celldata = []
        for r in range(ws.nrows):
            for c in range(ws.ncols):
                v = ws.cell_value(r, c)
                if v == '' or v is None:
                    continue
                display = _display(v)
                celldata.append({'r': r, 'c': c, 'v': {'v': v, 'm': display}})
        sheets.append({'name': ws.name, 'celldata': celldata})
    return sheets


def luckysheet_to_xls(sheets: list, xls_path: str) -> None:
    """Write Luckysheet workbook JSON to xls_path atomically."""
    wb = xlwt.Workbook(encoding='utf-8')
    for sheet in sheets:
        ws = wb.add_sheet(sheet['name'])
        for cd in sheet.get('celldata', []):
            r, c = cd['r'], cd['c']
            v = cd.get('v', {}).get('v', '')
            if v == '' or v is None:
                continue
            ws.write(r, c, v)
    tmp = xls_path + '.tmp'
    wb.save(tmp)
    os.replace(tmp, xls_path)


def _display(v):
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)
